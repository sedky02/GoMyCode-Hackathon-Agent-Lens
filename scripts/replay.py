"""Replay the synthetic dataset into AgentLens through the SDK, as if an agent were logging live.

Only the `events` table is read — never ground_truth or session labels.

    python scripts/replay.py --wave 1   # everything except the tail of ~10 sessions
    python scripts/replay.py --wave 2   # the withheld tails (these sessions "change")
    python scripts/replay.py --wave all
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agentlens.demo import load_source_events, split_waves  # noqa: E402
from agentlens.sdk import AgentLensClient  # noqa: E402


def print_progress(status):
    total, done = status.get("total") or 0, status.get("done") or 0
    line = (f"\r  {status.get('phase', '')}: {done}/{total} sessions analyzed, "
            f"{status.get('skipped', 0)} skipped, {status.get('judge_calls', 0)} LLM judge calls")
    print(line.ljust(90), end="", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wave", choices=["1", "2", "all"], default="all")
    parser.add_argument("--api", default="http://localhost:8100")
    parser.add_argument("--analyze", action="store_true", help="trigger analysis after sending")
    args = parser.parse_args()

    events = load_source_events()
    wave1, wave2 = split_waves(events)
    selected = {"1": wave1, "2": wave2, "all": events}[args.wave]

    client = AgentLensClient(args.api)
    for e in selected:
        client.log_event(e)
    client.flush()
    sessions = len({e["session_id"] for e in selected})
    print(f"Sent {len(selected)} events across {sessions} sessions (wave {args.wave}).")

    if args.analyze:
        print("Analyzing (safe to Ctrl+C: the analysis keeps running on the server)...")
        run = client.analyze(on_progress=print_progress)
        print(f"\nAnalysis run: {run}")


if __name__ == "__main__":
    main()
