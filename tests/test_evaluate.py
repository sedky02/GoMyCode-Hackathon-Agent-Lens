import subprocess
import sys

import pytest

import evaluate
import generate_dataset
from conftest import ROOT


def run_evaluate(*args):
    return subprocess.run([sys.executable, str(ROOT / "evaluate.py"), "--mode", "rules", *args],
                          capture_output=True, text=True, cwd=ROOT)


def test_score_counts_outcome_subtype_and_evidence_overlap():
    truth = {
        "A": {"outcome": "failed", "failure_type": "wrong_record", "evidence_event_ids": "[1, 2, 3]"},
        "B": {"outcome": "success"},
        "C": {"outcome": "recovered", "recovery_type": "retry_success"},
        "D": {"outcome": "ambiguous", "ambiguity_type": "multiple_orders"},
    }
    preds = {
        "A": {"outcome": "failed", "failure_type": "no_progress", "evidence_event_ids": [2, 3, 4]},
        "B": {"outcome": "success"},
        "C": {"outcome": "success"},
        "D": {"outcome": "ambiguous", "ambiguity_type": "multiple_orders"},
    }
    metrics = evaluate.score(preds, truth)
    assert metrics["accuracy"] == 0.75
    assert metrics["subtype_accuracy"] == 0.5
    assert metrics["evidence_jaccard"] == 0.5
    assert metrics["per_class"]["recovered"]["recall"] == 0.0


@pytest.mark.parametrize("seed", [7, 2026])
def test_held_out_seed_can_be_scored_without_touching_the_report(tmp_path, seed):
    heldout = tmp_path / "heldout.db"
    generate_dataset.main(seed, str(heldout))
    report = ROOT / "eval_report.json"
    before = report.read_bytes() if report.exists() else None
    result = run_evaluate("--db", str(heldout), "--min-accuracy", "0.95", "--min-macro-f1", "0.95")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (report.read_bytes() if report.exists() else None) == before


def test_threshold_failure_exits_non_zero(tmp_path):
    result = run_evaluate("--report", str(tmp_path / "report.json"), "--min-accuracy", "1.01")
    assert result.returncode != 0
    assert "FAILED threshold" in result.stderr
