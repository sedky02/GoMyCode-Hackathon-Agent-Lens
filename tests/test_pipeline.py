import shutil
import sqlite3
import time

from agentlens import demo, store
from agentlens.pipeline import analyze_rows, run_incremental
from conftest import ROOT


def wait_for_run(client):
    deadline = time.time() + 60
    while time.time() < deadline:
        status = client.get("/v1/analyze/status").json()
        if not status["running"]:
            assert status["error"] is None
            return status["last_run"]
        time.sleep(0.05)
    raise AssertionError("analysis did not finish")


def test_second_run_only_reanalyzes_changed_sessions(offline_embeddings):
    wave1, wave2 = demo.waves()
    conn = store.connect()
    store.insert_events(conn, wave1)
    first = run_incremental(conn, mode="rules")
    assert (first["analyzed"], first["skipped"]) == (120, 0)

    store.insert_events(conn, wave2)
    second = run_incremental(conn, mode="rules")
    assert (second["analyzed"], second["skipped"]) == (10, 110)

    third = run_incremental(conn, mode="rules")
    assert (third["analyzed"], third["skipped"]) == (0, 120)


def test_truncated_sessions_change_verdict_once_their_tail_arrives(offline_embeddings):
    wave1, wave2 = demo.waves()
    changed = sorted({e["session_id"] for e in wave2})
    conn = store.connect()
    store.insert_events(conn, wave1)
    run_incremental(conn, mode="rules")
    placeholders = ",".join("?" * len(changed))
    query = f"SELECT session_id, outcome, ambiguity_type, trace_hash FROM analyses WHERE session_id IN ({placeholders})"
    before = {r["session_id"]: dict(r) for r in conn.execute(query, changed)}
    assert {b["ambiguity_type"] for b in before.values()} == {"incomplete_trace"}

    store.insert_events(conn, wave2)
    run_incremental(conn, mode="rules")
    after = {r["session_id"]: dict(r) for r in conn.execute(query, changed)}
    assert all(after[s]["trace_hash"] != before[s]["trace_hash"] for s in changed)
    assert all(after[s]["ambiguity_type"] != "incomplete_trace" for s in changed)


def test_demo_flow_through_the_api(client, offline_embeddings):
    assert client.post("/v1/demo/waves/1").json()["accepted"] == 818
    client.post("/v1/analyze")
    assert wait_for_run(client)["analyzed"] == 120

    assert client.post("/v1/demo/waves/2").json()["accepted"] == 20
    client.post("/v1/analyze")
    run = wait_for_run(client)
    assert (run["analyzed"], run["skipped"]) == (10, 110)

    overview = client.get("/v1/overview").json()
    assert overview["totals"]["sessions"] == 120 and overview["totals"]["events"] == 838
    assert sum(overview["outcomes"].values()) == 120

    issues = client.get("/v1/issues").json()
    assert [i["priority"] for i in issues] == sorted((i["priority"] for i in issues), reverse=True)
    assert sum(i["session_count"] for i in issues) == overview["outcomes"]["failed"]
    top = client.get(f"/v1/issues/{issues[0]['issue_id']}").json()
    assert len(top["sessions"]) == issues[0]["session_count"]

    failed = client.get("/v1/sessions", params={"outcome": "failed"}).json()
    detail = client.get(f"/v1/sessions/{failed[0]['session_id']}").json()
    event_ids = {e["event_id"] for e in detail["events"]}
    assert detail["findings"] and set(detail["analysis"]["evidence_event_ids"]) <= event_ids

    assert client.post("/v1/demo/reset").json()["reset"] is True
    assert client.get("/v1/overview").json()["totals"] == {"sessions": 0, "events": 0, "findings": 0, "issues": 0}


def test_verdicts_do_not_depend_on_the_hidden_labels(tmp_path, monkeypatch):
    stripped = tmp_path / "no_labels.db"
    shutil.copy(ROOT / "supplyzpro_agent_logs.db", stripped)
    conn = sqlite3.connect(stripped)
    conn.executescript("DROP TABLE ground_truth; UPDATE sessions SET outcome = 'hidden', metadata = NULL;")
    conn.commit()
    conn.close()

    def verdicts():
        by_session = {}
        for event in demo.load_source_events():
            by_session.setdefault(event["session_id"], []).append(event)
        return {sid: analyze_rows(sid, rows, "rules", None)[0] for sid, rows in by_session.items()}

    with_labels = verdicts()
    monkeypatch.setattr(demo, "SOURCE_DB", stripped)
    assert verdicts() == with_labels
