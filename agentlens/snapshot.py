"""Git-like session snapshots: only re-analyze sessions whose trace (or the analyzer) changed."""

import hashlib
import json
from datetime import datetime

ANALYSIS_VERSION = "1.0"
HASHED_FIELDS = ["event_id", "sequence_number", "timestamp", "event_type", "content", "tool_name",
                 "tool_arguments_json", "tool_result_json", "tool_status"]


def trace_hash(rows):
    canonical = json.dumps([[r.get(f) for f in HASHED_FIELDS] for r in rows], sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def needs_analysis(conn, session_id, digest, version):
    row = conn.execute("SELECT trace_hash, analysis_version FROM session_snapshots WHERE session_id = ?",
                       (session_id,)).fetchone()
    return row is None or row["trace_hash"] != digest or row["analysis_version"] != version


def save_snapshot(conn, session_id, rows, digest, version):
    conn.execute(
        "INSERT OR REPLACE INTO session_snapshots VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, len(rows), rows[-1]["event_id"] if rows else None, digest, version,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
