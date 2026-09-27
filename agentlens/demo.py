"""Demo trace source: splits the synthetic dataset's events into two arrival waves.

Reads only the `events` table of the dataset — never ground_truth or session labels.
"""

import sqlite3
from functools import lru_cache

from .store import EVENT_COLUMNS, ROOT

SOURCE_DB = ROOT / "supplyzpro_agent_logs.db"
WAVE2_EVERY = 12  # every 12th session gets its last 2 events withheld until wave 2 (10 sessions)


def load_source_events():
    conn = sqlite3.connect(SOURCE_DB)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(f"SELECT {', '.join(EVENT_COLUMNS)} FROM events ORDER BY session_id, sequence_number")
        return [dict(r) for r in rows]
    finally:
        conn.close()


def split_waves(events):
    by_session = {}
    for e in events:
        by_session.setdefault(e["session_id"], []).append(e)
    wave1, wave2 = [], []
    for i, sid in enumerate(sorted(by_session), start=1):
        evs = by_session[sid]
        if i % WAVE2_EVERY == 0 and len(evs) >= 4:
            wave1.extend(evs[:-2])
            wave2.extend(evs[-2:])
        else:
            wave1.extend(evs)
    return wave1, wave2


@lru_cache(maxsize=1)
def waves():
    return split_waves(load_source_events())
