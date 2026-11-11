import json
import os
import sqlite3
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("AGENTLENS_DB", ROOT / "agentlens.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id            INTEGER PRIMARY KEY,
    session_id          TEXT NOT NULL,
    sequence_number     INTEGER NOT NULL,
    timestamp           TEXT NOT NULL,
    event_type          TEXT NOT NULL,
    role                TEXT,
    content             TEXT,
    tool_name           TEXT,
    tool_arguments_json TEXT,
    tool_result_json    TEXT,
    tool_status         TEXT,
    latency_ms          INTEGER
);
CREATE INDEX IF NOT EXISTS idx_ev_session ON events(session_id, sequence_number);

CREATE TABLE IF NOT EXISTS session_snapshots (
    session_id       TEXT PRIMARY KEY,
    event_count      INTEGER NOT NULL,
    last_event_id    INTEGER,
    trace_hash       TEXT NOT NULL,
    analysis_version TEXT NOT NULL,
    last_analyzed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    session_id         TEXT PRIMARY KEY,
    outcome            TEXT NOT NULL,
    failure_type       TEXT,
    recovery_type      TEXT,
    ambiguity_type     TEXT,
    confidence         REAL NOT NULL,
    source             TEXT NOT NULL,
    reason             TEXT,
    evidence_event_ids TEXT NOT NULL,
    trace_hash         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS findings (
    finding_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id         TEXT NOT NULL,
    failure_type       TEXT NOT NULL,
    severity           TEXT NOT NULL,
    confidence         REAL NOT NULL,
    tool               TEXT,
    signature          TEXT NOT NULL,
    reason             TEXT,
    details_json       TEXT NOT NULL,
    evidence_event_ids TEXT NOT NULL,
    issue_id           INTEGER
);
CREATE INDEX IF NOT EXISTS idx_findings_session ON findings(session_id);

CREATE TABLE IF NOT EXISTS issues (
    issue_id       INTEGER PRIMARY KEY,
    title          TEXT NOT NULL,
    failure_type   TEXT NOT NULL,
    severity       TEXT NOT NULL,
    session_count  INTEGER NOT NULL,
    avg_confidence REAL NOT NULL,
    priority       REAL NOT NULL,
    tools_json     TEXT NOT NULL,
    finding_ids    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_cache (
    cache_key     TEXT PRIMARY KEY,
    response_json TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    analyzed    INTEGER NOT NULL,
    skipped     INTEGER NOT NULL,
    judge_calls INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    mode           TEXT,
    judge_failures INTEGER NOT NULL DEFAULT 0
);
"""
# Columns added after the first release; databases created before then are upgraded on connect.
ADDED_COLUMNS = {"analysis_runs": {"mode": "TEXT", "judge_failures": "INTEGER NOT NULL DEFAULT 0"}}

EVENT_COLUMNS = [
    "event_id", "session_id", "sequence_number", "timestamp", "event_type", "role", "content",
    "tool_name", "tool_arguments_json", "tool_result_json", "tool_status", "latency_ms",
]


_schema_lock = threading.Lock()
_schema_ready = set()


def connect(path=None):
    path = Path(path or DB_PATH)
    # FastAPI may open a request's connection in one threadpool thread and use it in another.
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn, path)
    return conn


def _ensure_schema(conn, path):
    """Create or upgrade the schema once per database file.
    Concurrent connections switching to WAL at the same time fail with "database is locked"."""
    with _schema_lock:
        if path in _schema_ready and _has_tables(conn):
            return
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        for table, columns in ADDED_COLUMNS.items():
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            for name, definition in columns.items():
                if name not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        conn.commit()
        _schema_ready.add(path)


def _has_tables(conn):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'events'").fetchone() is not None


def _json_text(value):
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value)


def insert_events(conn, events):
    rows = []
    for e in events:
        rows.append((
            e.get("event_id"), e["session_id"], e["sequence_number"], e["timestamp"], e["event_type"],
            e.get("role"), e.get("content"), e.get("tool_name"),
            _json_text(e.get("tool_arguments_json", e.get("tool_arguments"))),
            _json_text(e.get("tool_result_json", e.get("tool_result"))),
            e.get("tool_status"), e.get("latency_ms"),
        ))
    cur = conn.executemany(
        f"INSERT OR IGNORE INTO events ({', '.join(EVENT_COLUMNS)}) VALUES ({', '.join('?' * len(EVENT_COLUMNS))})",
        rows,
    )
    conn.commit()
    return cur.rowcount


def session_ids(conn):
    return [r[0] for r in conn.execute("SELECT DISTINCT session_id FROM events ORDER BY session_id")]


def session_events(conn, session_id):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM events WHERE session_id = ? ORDER BY sequence_number", (session_id,))]


def parse_event(row):
    e = dict(row)
    e["tool_arguments"] = json.loads(e.pop("tool_arguments_json")) if e.get("tool_arguments_json") else None
    e["tool_result"] = json.loads(e.pop("tool_result_json")) if e.get("tool_result_json") else None
    e.pop("tool_arguments_json", None)
    e.pop("tool_result_json", None)
    return e
