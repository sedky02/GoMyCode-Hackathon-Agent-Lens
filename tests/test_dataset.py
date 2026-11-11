"""The committed dataset must be exactly what generate_dataset.py produces for seed 42."""

import hashlib
import sqlite3

import generate_dataset
from conftest import ROOT

COMMITTED_DB = ROOT / "supplyzpro_agent_logs.db"


def table_hashes(db_path):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        hashes = {}
        for table in tables:
            digest = hashlib.sha256()
            for row in conn.execute(f"SELECT * FROM {table} ORDER BY 1"):
                digest.update(repr(row).encode())
            hashes[table] = digest.hexdigest()
        return hashes
    finally:
        conn.close()


def generate(tmp_path, seed):
    path = tmp_path / f"seed{seed}.db"
    generate_dataset.main(seed, str(path))
    return path


def test_regenerating_seed_42_reproduces_the_committed_dataset(tmp_path):
    regenerated = table_hashes(generate(tmp_path, 42))
    committed = table_hashes(COMMITTED_DB)
    assert set(regenerated) == {"customers", "events", "ground_truth", "invoices", "orders", "products",
                                "sessions", "tool_definitions"}
    assert regenerated == committed


def test_a_different_seed_produces_different_sessions(tmp_path):
    other = table_hashes(generate(tmp_path, 7))
    committed = table_hashes(COMMITTED_DB)
    assert other["events"] != committed["events"]
    assert other["ground_truth"] != committed["ground_truth"]
