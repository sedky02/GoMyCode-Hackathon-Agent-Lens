"""AgentLens API.   Run:  uvicorn agentlens.api:app --port 8100"""

import json
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from . import demo
from .job import AnalysisJob
from .pipeline import default_mode, run_incremental
from .store import ROOT, connect, insert_events, parse_event, session_events
from .taxonomy import OUTCOMES

app = FastAPI(title="AgentLens", version="0.2")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
EVAL_REPORT = ROOT / "eval_report.json"
RESETTABLE_TABLES = ["events", "session_snapshots", "analyses", "findings", "issues", "analysis_runs"]
job = AnalysisJob()


def db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


Outcome = Literal[OUTCOMES]
MAX_BATCH_EVENTS = 5000


class Event(BaseModel):
    session_id: str = Field(min_length=1)
    sequence_number: int
    timestamp: str = Field(min_length=1)
    event_type: Literal["user_message", "agent_message", "tool_call", "tool_result"]
    event_id: int | None = None
    role: str | None = None
    content: str | None = None
    tool_name: str | None = None
    tool_arguments: dict | list | None = None
    tool_arguments_json: str | None = None
    tool_result: dict | list | None = None
    tool_result_json: str | None = None
    tool_status: Literal["success", "error"] | None = None
    latency_ms: int | None = None

    @field_validator("tool_arguments_json", "tool_result_json")
    @classmethod
    def must_be_json(cls, value):
        if value is not None:
            json.loads(value)
        return value


class EventBatch(BaseModel):
    events: list[Event] = Field(max_length=MAX_BATCH_EVENTS)


def _analysis(row):
    if row is None:
        return None
    a = dict(row)
    a["evidence_event_ids"] = json.loads(a["evidence_event_ids"])
    a.pop("trace_hash", None)
    return a


def _issue(row):
    i = dict(row)
    i["tools"] = json.loads(i.pop("tools_json"))
    i.pop("finding_ids")
    return i


@app.post("/v1/events")
def ingest(batch: EventBatch, conn=Depends(db)):
    return {"accepted": insert_events(conn, [e.model_dump(exclude_none=True) for e in batch.events])}


@app.get("/healthz")
def health():
    return {"status": "ok"}


# ---- analysis runs in a background thread; clients poll /v1/analyze/status ----

def _run_analysis(progress):
    conn = connect()
    try:
        return run_incremental(conn, progress=progress)
    finally:
        conn.close()


@app.post("/v1/analyze")
def analyze():
    started = job.start(default_mode(), _run_analysis)
    return {"started": started, **job.snapshot()}


@app.get("/v1/analyze/status")
def analyze_status():
    return job.snapshot()


# ---- demo controls: replay dataset waves from the dashboard ----

def _wave_info(conn, wave_events):
    ids = [e["event_id"] for e in wave_events]
    present = 0
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        present += conn.execute(f"SELECT COUNT(*) FROM events WHERE event_id IN ({','.join('?' * len(chunk))})",
                                chunk).fetchone()[0]
    return {"events": len(ids), "sessions": len({e["session_id"] for e in wave_events}),
            "sent": present == len(ids) and present > 0, "partial": 0 < present < len(ids)}


@app.get("/v1/demo/status")
def demo_status(conn=Depends(db)):
    wave1, wave2 = demo.waves()
    return {"wave1": _wave_info(conn, wave1), "wave2": _wave_info(conn, wave2),
            "events_ingested": conn.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            "analysis_running": job.running, "mode": default_mode()}


@app.post("/v1/demo/waves/{wave}")
def send_wave(wave: int, conn=Depends(db)):
    if wave not in (1, 2):
        raise HTTPException(404, "wave must be 1 or 2")
    events = demo.waves()[wave - 1]
    accepted = insert_events(conn, events)
    return {"wave": wave, "accepted": accepted, "events": len(events),
            "sessions": len({e["session_id"] for e in events})}


@app.post("/v1/demo/reset")
def reset(conn=Depends(db)):
    if job.running:
        raise HTTPException(409, "an analysis run is in progress; wait for it to finish")
    for table in RESETTABLE_TABLES:
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    job.clear()
    return {"reset": True, "kept": "llm_cache (cached LLM verdicts make the next run fast)"}


# ---- read endpoints ----

@app.get("/v1/overview")
def overview(conn=Depends(db)):
    outcomes = dict.fromkeys(OUTCOMES, 0)
    for r in conn.execute("SELECT outcome, COUNT(*) AS n FROM analyses GROUP BY outcome"):
        outcomes[r["outcome"]] = r["n"]
    last = conn.execute("SELECT * FROM analysis_runs ORDER BY run_id DESC LIMIT 1").fetchone()
    count = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    return {
        "totals": {"sessions": count("SELECT COUNT(DISTINCT session_id) FROM events"),
                   "events": count("SELECT COUNT(*) FROM events"),
                   "findings": count("SELECT COUNT(*) FROM findings"),
                   "issues": count("SELECT COUNT(*) FROM issues")},
        "outcomes": outcomes,
        "last_run": dict(last) if last else None,
        "evaluation": json.loads(EVAL_REPORT.read_text()) if EVAL_REPORT.exists() else None,
    }


@app.get("/v1/issues")
def issues(conn=Depends(db)):
    return [_issue(r) for r in conn.execute("SELECT * FROM issues ORDER BY priority DESC")]


@app.get("/v1/issues/{issue_id}")
def issue(issue_id: int, conn=Depends(db)):
    row = conn.execute("SELECT * FROM issues WHERE issue_id = ?", (issue_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "issue not found")
    sessions = conn.execute(
        "SELECT f.session_id, f.confidence, f.reason, MIN(e.timestamp) AS started_at "
        "FROM findings f JOIN events e ON e.session_id = f.session_id "
        "WHERE f.issue_id = ? GROUP BY f.finding_id ORDER BY f.confidence DESC, f.session_id", (issue_id,))
    return {**_issue(row), "sessions": [dict(s) for s in sessions]}


@app.get("/v1/sessions")
def sessions(outcome: Outcome | None = None, conn=Depends(db)):
    sql = ("SELECT e.session_id, MIN(e.timestamp) AS started_at, MAX(e.timestamp) AS ended_at, "
           "COUNT(*) AS event_count, a.outcome, a.failure_type, a.recovery_type, a.ambiguity_type, "
           "a.confidence, a.source FROM events e LEFT JOIN analyses a ON a.session_id = e.session_id ")
    params = ()
    if outcome:
        sql += "WHERE a.outcome = ? "
        params = (outcome,)
    sql += "GROUP BY e.session_id ORDER BY e.session_id"
    return [dict(r) for r in conn.execute(sql, params)]


@app.get("/v1/sessions/{session_id}")
def session(session_id: str, conn=Depends(db)):
    rows = session_events(conn, session_id)
    if not rows:
        raise HTTPException(404, "session not found")
    analysis = conn.execute("SELECT * FROM analyses WHERE session_id = ?", (session_id,)).fetchone()
    findings = []
    for f in conn.execute("SELECT * FROM findings WHERE session_id = ?", (session_id,)):
        f = dict(f)
        f["details"] = json.loads(f.pop("details_json"))
        f["evidence_event_ids"] = json.loads(f["evidence_event_ids"])
        findings.append(f)
    return {"session_id": session_id, "started_at": rows[0]["timestamp"], "ended_at": rows[-1]["timestamp"],
            "events": [parse_event(r) for r in rows], "analysis": _analysis(analysis), "findings": findings}
