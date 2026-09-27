# Project rules

## phish-monitor/ is off-limits

`phish-monitor/` is a separate, unrelated project that happens to live in this folder.

- Never read, list, search, grep, glob, edit, create, delete or run anything inside `phish-monitor/`.
- Never import from it or reference its code, config, `.env` or data.
- Exclude it from any file discovery: globs, grep, test discovery (pytest `testpaths`), linters, bundlers, `git add`.
- If a command would recurse into the project root, scope it so it skips `phish-monitor/`.

## Ground-truth isolation

- `supplyzpro_agent_logs.db` contains a hidden `ground_truth` table plus `sessions.outcome` / `sessions.metadata`.
- Only `evaluate.py` may read `ground_truth`. AgentLens code (`agentlens/`, `scripts/replay.py`) may only use the `events` data. It must never read labels.
