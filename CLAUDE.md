# Project rules

## Ground-truth isolation

- `supplyzpro_agent_logs.db` contains a hidden `ground_truth` table plus `sessions.outcome` / `sessions.metadata`.
  `data/out_of_template_sessions.json` carries a `label` per session.
- Only `evaluate.py` may read labels. AgentLens code (`agentlens/`, `scripts/replay.py`) may only use the
  `events` data. `tests/test_pipeline.py` checks that verdicts are identical with the labels removed.
- Never tune a rule against `data/out_of_template_sessions.json`. It exists to measure generalization.

## Layout

- `agentlens/` detection engine and API. `taxonomy.py` is the single source of outcome and subtype names.
- `evaluate.py` scoring, `generate_dataset.py` dataset generator (seed 42 is the committed dataset).
- `dashboard/` React + Vite frontend. Its mock data is a snapshot of real API responses, used only with `VITE_USE_MOCK=1`.
  Follow `dashboard/DESIGN.md` for any UI change.

## Checks before committing

```bash
.venv/bin/python -m pytest -q
.venv/bin/python evaluate.py --mode rules --min-accuracy 0.95 --min-macro-f1 0.95
cd dashboard && npm run build
```

Never report a metric in the docs that did not come from running `evaluate.py`.
