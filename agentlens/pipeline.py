"""Incremental analysis: hash → skip unchanged → rules → (LLM judge if needed) → findings → issues."""

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from . import judge
from .classify import classify
from .grouping import build_issues
from .reconstruct import build_session
from .rules import Signal, run_rules
from .snapshot import ANALYSIS_VERSION, needs_analysis, save_snapshot, trace_hash
from .store import connect, session_events, session_ids
from .taxonomy import SUBTYPE_FIELD

logger = logging.getLogger(__name__)
JUDGE_BELOW_CONFIDENCE = 0.7


def default_mode():
    mode = os.environ.get("AGENTLENS_MODE", "").strip().lower()
    if mode in ("rules", "llm", "hybrid"):
        return mode if mode == "rules" or judge.enabled() else "rules"
    return "hybrid" if judge.enabled() else "rules"


def effective_version(mode):
    model = judge.config()["model"] if mode != "rules" and judge.enabled() else "none"
    return f"{ANALYSIS_VERSION}|{mode}|{model}"


def judge_workers(mode):
    if mode == "rules":
        return 1
    return max(1, int(os.environ.get("AGENTLENS_JUDGE_CONCURRENCY", "4")))


def _agrees(analysis, verdict):
    if analysis["outcome"] != verdict["outcome"]:
        return False
    key = SUBTYPE_FIELD.get(verdict["outcome"])
    return key is None or analysis[key] == verdict[key]


def analyze_rows(session_id, rows, mode, conn):
    """Analyze one session. Returns (analysis, failure_signals, live_judge_call, judge_failed)."""
    session = build_session(session_id, rows)
    signals = run_rules(session)
    analysis, uncertain = classify(session, signals)
    failures = [s for s in signals if s.kind == "failure"]

    wants_judge = mode == "llm" or (mode == "hybrid" and (uncertain or analysis["confidence"] < JUDGE_BELOW_CONFIDENCE))
    if not wants_judge:
        return analysis, failures, False, False

    verdict, live = judge.judge(session, trace_hash(rows), conn)
    if verdict is None:
        return analysis, failures, live, True

    if _agrees(analysis, verdict):
        analysis = {**analysis, "source": "hybrid",
                    "confidence": max(analysis["confidence"], verdict["confidence"]),
                    "reason": f"{analysis['reason']} LLM judge agrees: {verdict['reason']}"}
        return analysis, failures, live, False

    if mode == "llm" or verdict["confidence"] >= analysis["confidence"]:
        analysis = {**verdict, "evidence_event_ids": verdict["evidence_event_ids"] or analysis["evidence_event_ids"]}
        failures = []
        if verdict["outcome"] == "failed" and verdict["failure_type"]:
            ftype = verdict["failure_type"]
            failures = [Signal("failure", ftype, verdict["confidence"], verdict["reason"],
                               analysis["evidence_event_ids"],
                               details={"judge_reason": verdict["reason"]},
                               signature=f"{ftype} | detected by LLM judge | {verdict['reason']}")]
    return analysis, failures, live, False


def _analyze_job(session_id, rows, mode):
    conn = connect()
    try:
        return analyze_rows(session_id, rows, mode, conn)
    finally:
        conn.close()


def analyze_many(items, mode):
    """Analyze (session_id, rows) pairs, judge calls in parallel.
    Yields (session_id, rows, analysis, failures, live_call, judge_failed) as each finishes."""
    workers = judge_workers(mode)
    if workers == 1:
        for sid, rows in items:
            yield (sid, rows, *_analyze_job(sid, rows, mode))
        return
    with ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(_analyze_job, sid, rows, mode): (sid, rows) for sid, rows in items}
        for fut in as_completed(futures):
            sid, rows = futures[fut]
            yield (sid, rows, *fut.result())


def _write(conn, session_id, analysis, failures, digest):
    conn.execute(
        "INSERT OR REPLACE INTO analyses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (session_id, analysis["outcome"], analysis["failure_type"], analysis["recovery_type"],
         analysis["ambiguity_type"], analysis["confidence"], analysis["source"], analysis["reason"],
         json.dumps(analysis["evidence_event_ids"]), digest))
    conn.execute("DELETE FROM findings WHERE session_id = ?", (session_id,))
    for f in failures:
        conn.execute(
            "INSERT INTO findings (session_id, failure_type, severity, confidence, tool, signature, reason, "
            "details_json, evidence_event_ids) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, f.type, f.severity, f.confidence, f.tool, f.signature, f.reason,
             json.dumps(f.details), json.dumps(f.evidence)))


def run_incremental(conn=None, mode=None, progress=None):
    """Analyze only changed sessions. `progress(**status)` is called as work advances.
    Each session is committed as soon as it is done, so an interrupted run loses nothing."""
    conn = conn or connect()
    mode = mode or default_mode()
    version = effective_version(mode)
    report = progress or (lambda **_: None)
    started = time.time()

    changed, skipped = [], 0
    for sid in session_ids(conn):
        rows = session_events(conn, sid)
        if needs_analysis(conn, sid, trace_hash(rows), version):
            changed.append((sid, rows))
        else:
            skipped += 1

    analyzed = judge_calls = judge_failures = 0
    report(phase="analyzing", mode=mode, total=len(changed), done=0, skipped=skipped,
           judge_calls=0, judge_failures=0, current=None)
    for sid, rows, analysis, failures, live, judge_failed in analyze_many(changed, mode):
        digest = trace_hash(rows)
        _write(conn, sid, analysis, failures, digest)
        if judge_failed:
            judge_failures += 1  # no snapshot saved, so the next run retries the judge for this session
        else:
            save_snapshot(conn, sid, rows, digest, version)
        conn.commit()
        analyzed += 1
        judge_calls += int(live)
        report(done=analyzed, judge_calls=judge_calls, judge_failures=judge_failures, current=sid)

    if analyzed or not conn.execute("SELECT 1 FROM issues LIMIT 1").fetchone():
        report(phase="grouping", current=None)
        build_issues(conn)

    summary = {"started_at": datetime.fromtimestamp(started).strftime("%Y-%m-%d %H:%M:%S"),
               "analyzed": analyzed, "skipped": skipped, "judge_calls": judge_calls,
               "judge_failures": judge_failures, "duration_ms": int((time.time() - started) * 1000),
               "mode": mode}
    cur = conn.execute(
        "INSERT INTO analysis_runs (started_at, analyzed, skipped, judge_calls, duration_ms, mode, judge_failures) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (summary["started_at"], analyzed, skipped, judge_calls, summary["duration_ms"], mode, judge_failures))
    conn.commit()
    logger.info("analysis run %s: %s", cur.lastrowid, summary)
    return {"run_id": cur.lastrowid, **summary}


if __name__ == "__main__":
    print(run_incremental(progress=lambda **s: print(s)))
