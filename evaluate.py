"""Score AgentLens against the hidden ground truth.

This is the ONLY file allowed to read `ground_truth`. It runs the analyzer on the raw events of
every session and compares its verdicts to the labels.

    python evaluate.py                # rules, plus llm and hybrid if the judge is configured
    python evaluate.py --mode rules
    python evaluate.py --show-errors
    python evaluate.py --db heldout.db --min-accuracy 0.95    # another dataset, fail below a threshold
"""

import argparse
import json
import sqlite3
from pathlib import Path

from agentlens import judge
from agentlens.pipeline import analyze_many

ROOT = Path(__file__).resolve().parent
SOURCE_DB = ROOT / "supplyzpro_agent_logs.db"
REPORT = ROOT / "eval_report.json"
LABELS = ["success", "recovered", "failed", "ambiguous"]
SUBTYPE = {"failed": "failure_type", "recovered": "recovery_type", "ambiguous": "ambiguity_type"}
EVENT_COLUMNS = ["event_id", "session_id", "sequence_number", "timestamp", "event_type", "role", "content",
                 "tool_name", "tool_arguments_json", "tool_result_json", "tool_status", "latency_ms"]


def load(db_path=SOURCE_DB):
    src = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    sessions = {}
    for r in src.execute(f"SELECT {', '.join(EVENT_COLUMNS)} FROM events ORDER BY session_id, sequence_number"):
        sessions.setdefault(r["session_id"], []).append(dict(r))
    truth = {r["session_id"]: dict(r) for r in src.execute("SELECT * FROM ground_truth")}
    return sessions, truth


def predict(sessions, mode):
    preds, failed = {}, 0
    for sid, _rows, analysis, _failures, _live, judge_failed in analyze_many(list(sessions.items()), mode):
        preds[sid] = analysis
        failed += judge_failed
        print(f"\r  [{mode}] {len(preds)}/{len(sessions)} sessions", end="", flush=True)
    print(f"  ({failed} judge calls failed, fell back to rules; rerun to retry)" if failed else "")
    return preds


def score(preds, truth):
    sids = sorted(truth)
    y_true = [truth[s]["outcome"] for s in sids]
    y_pred = [preds[s]["outcome"] for s in sids]
    matrix = [[sum(1 for t, p in zip(y_true, y_pred) if t == a and p == b) for b in LABELS] for a in LABELS]

    def prf(label):
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
                "support": sum(1 for t in y_true if t == label)}

    per_class = {label: prf(label) for label in LABELS}
    failed = per_class["failed"]

    subtype_hits = subtype_total = 0
    for s in sids:
        outcome = truth[s]["outcome"]
        if outcome in SUBTYPE and preds[s]["outcome"] == outcome:
            subtype_total += 1
            subtype_hits += preds[s][SUBTYPE[outcome]] == truth[s][SUBTYPE[outcome]]

    jaccards = []
    for s in sids:
        if truth[s]["outcome"] == "failed" and preds[s]["outcome"] == "failed":
            gt_ids, pred_ids = set(json.loads(truth[s]["evidence_event_ids"])), set(preds[s]["evidence_event_ids"])
            if gt_ids | pred_ids:
                jaccards.append(len(gt_ids & pred_ids) / len(gt_ids | pred_ids))

    return {
        "accuracy": round(sum(t == p for t, p in zip(y_true, y_pred)) / len(sids), 3),
        "macro_precision": round(sum(c["precision"] for c in per_class.values()) / 4, 3),
        "macro_recall": round(sum(c["recall"] for c in per_class.values()) / 4, 3),
        "macro_f1": round(sum(c["f1"] for c in per_class.values()) / 4, 3),
        "per_class": per_class,
        "failure_detection": {k: failed[k] for k in ("precision", "recall", "f1")},
        "subtype_accuracy": round(subtype_hits / subtype_total, 3) if subtype_total else None,
        "evidence_jaccard": round(sum(jaccards) / len(jaccards), 3) if jaccards else None,
        "confusion_matrix": {"labels": LABELS, "matrix": matrix},
        "sessions": len(sids),
    }


def print_report(mode, m):
    print(f"\n=== mode: {mode} ({m['sessions']} sessions) ===")
    print(f"Accuracy:        {m['accuracy']:.1%}")
    print(f"Macro precision: {m['macro_precision']:.1%}   recall: {m['macro_recall']:.1%}   F1: {m['macro_f1']:.1%}")
    fd = m["failure_detection"]
    print(f"Failure detection  P {fd['precision']:.1%}  R {fd['recall']:.1%}  F1 {fd['f1']:.1%}")
    if m["subtype_accuracy"] is not None:
        print(f"Subtype accuracy (failure/recovery/ambiguity type): {m['subtype_accuracy']:.1%}")
    if m["evidence_jaccard"] is not None:
        print(f"Evidence overlap (Jaccard, failed sessions): {m['evidence_jaccard']:.2f}")
    print("\nPer-class recall:")
    for label, c in m["per_class"].items():
        print(f"  {label.upper():<10} {c['recall']:>6.1%}   (precision {c['precision']:.1%}, n={c['support']})")
    print("\nConfusion matrix (rows = truth, cols = predicted):")
    print("            " + "".join(f"{l[:9]:>11}" for l in LABELS))
    for label, row in zip(LABELS, m["confusion_matrix"]["matrix"]):
        print(f"  {label:<10}" + "".join(f"{v:>11}" for v in row))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["rules", "llm", "hybrid", "all"], default="all")
    parser.add_argument("--show-errors", action="store_true")
    parser.add_argument("--db", type=Path, default=SOURCE_DB, help="dataset to score (default: the committed one)")
    parser.add_argument("--report", type=Path,
                        help=f"where to write the JSON report (default: {REPORT.name}, only for the default dataset)")
    parser.add_argument("--min-accuracy", type=float, help="exit non-zero if accuracy is below this (0-1)")
    parser.add_argument("--min-macro-f1", type=float, help="exit non-zero if macro F1 is below this (0-1)")
    args = parser.parse_args()

    modes = ["rules", "llm", "hybrid"] if args.mode == "all" else [args.mode]
    if not judge.enabled():
        if args.mode in ("llm", "hybrid"):
            raise SystemExit("LLM judge not configured (AGENTLENS_LLM_BASE_URL / AGENTLENS_LLM_MODEL).")
        modes = ["rules"]

    sessions, truth = load(args.db)
    results = {}
    for mode in modes:
        preds = predict(sessions, mode)
        results[mode] = score(preds, truth)
        print_report(mode, results[mode])
        if args.show_errors:
            print("\nMisclassified:")
            for sid in sorted(truth):
                t, p = truth[sid], preds[sid]
                t_sub = t[SUBTYPE[t["outcome"]]] if t["outcome"] in SUBTYPE else None
                p_sub = p.get(SUBTYPE[p["outcome"]]) if p["outcome"] in SUBTYPE else None
                if (t["outcome"], t_sub) != (p["outcome"], p_sub):
                    print(f"  {sid}: truth={t['outcome']}/{t_sub}  predicted={p['outcome']}/{p_sub}  "
                          f"[{p['source']}] {p['reason'][:140]}")

    primary = "hybrid" if "hybrid" in results else modes[-1]
    report_path = args.report or (REPORT if args.db.resolve() == SOURCE_DB.resolve() else None)
    if report_path:
        report = {"mode": primary, **results[primary],
                  "modes": {m: {"accuracy": r["accuracy"], "macro_f1": r["macro_f1"]} for m, r in results.items()}}
        report_path.write_text(json.dumps(report, indent=2))
        print(f"\nWrote {report_path.name} (primary mode: {primary})")

    below = [f"{name} {results[primary][key]:.3f} < {minimum}"
             for name, key, minimum in (("accuracy", "accuracy", args.min_accuracy),
                                        ("macro F1", "macro_f1", args.min_macro_f1))
             if minimum is not None and results[primary][key] < minimum]
    if below:
        raise SystemExit(f"\nFAILED threshold ({primary}): " + "; ".join(below))


if __name__ == "__main__":
    main()
