# AgentLens portfolio pack

Everything here is built from features that run today. Numbers come from `evaluate.py` in
rules-only mode; rerun it before publishing if the code has changed.

## Screenshot list

Start from a clean state for all of them: `docker compose up --build`, open
http://localhost:5173, click **Reset demo** if any data is present. Use a 1440 px wide browser
window and hide the bookmarks bar. The dashboard has one theme (light).

Screens 1, 2 and 4 are already captured in `docs/img/` (1556 px wide, top of each page only).
Retake them at full size for the portfolio.

| # | Screen | State it must be in |
| --- | --- | --- |
| 1 | Session detail, `/sessions/S008` (hero image) | Both waves sent and analyzed. The "Claim check" strip shows Requested "Samsung TV 43-inch", Queried and Returned "Samsung TV 65-inch", Claimed "Samsung TV 43-inch"; the transcript shows the 65-inch values underlined in red and the evidence events marked in yellow; the Analysis panel shows Failed, `wrong_record`, 92%. |
| 2 | Overview after the second run | Both waves sent, analysis run twice. "Last analysis run" shows Analyzed 10, Skipped 110. Outcome bar shows 62 / 24 / 21 / 13. Top-right badge says "Live API". |
| 3 | Overview, Evaluation section | Scroll so the scores and the confusion matrix are both visible. Mode `rules`. |
| 4 | Issues list, `/issues` | Five issues ranked by priority, "Unsupported success" first at priority 95.0 with 6 sessions. |
| 5 | Issue detail, `/issues/1` | The six affected sessions with their one-line reasons visible. |
| 6 | Session detail, `/sessions/S045` | An `incomplete_request` case: the tool returned `delivery_date: null` and the agent promised delivery tomorrow. |
| 7 | Terminal: evaluation | Output of `python evaluate.py --mode rules --show-errors` showing the confusion matrix. |
| 8 | Terminal: out-of-template evaluation | Output of `python evaluate.py --mode rules --db data/out_of_template_sessions.json --show-errors`, including the "Misclassified" list. This is the honesty shot. |
| 9 | Terminal: tests | `python -m pytest -q` ending in `32 passed`. |

## Demo video script (about 80 seconds)

Record at 1440 px width. Start with the demo reset and the Overview page open.

| Time | On screen | Voiceover |
| --- | --- | --- |
| 0:00 to 0:10 | Overview page, empty state | "AI agents usually fail quietly. The tool call succeeds, the agent sounds confident, and the answer is still wrong. AgentLens finds those sessions." |
| 0:10 to 0:22 | Click **Send wave 1**, then **Run analysis**; progress bar runs | "Here I replay 120 recorded sessions of an ERP assistant and analyze them. Deterministic rules compare what the user asked, what the tools returned, and what the agent claimed." |
| 0:22 to 0:30 | Outcome bar: 62 success, 24 recovered, 21 failed, 13 ambiguous | "21 sessions failed. Most of them have no error anywhere in the logs." |
| 0:30 to 0:38 | Open **Issues**; hover the top issue | "Failures are grouped into issues and ranked by how many sessions they affect, their severity and the confidence." |
| 0:38 to 0:58 | Open **Sessions**, filter Failed, open **S008**. Pause on the verdict sentence and the "Claim check" strip, then scroll the transcript to the red-underlined values | "This is the important part. The user asked about the 43-inch TV. The agent looked up the 65-inch model. The tool returned success, and the agent reported 11 units as if they were the 43-inch stock. AgentLens shows the exact events that prove it." |
| 0:58 to 1:08 | Back to Overview; click **Send wave 2**, then **Run analysis** | "When new events arrive, only the sessions that changed are re-analyzed: 10 analyzed, 110 skipped." |
| 1:08 to 1:20 | Scroll to the Evaluation section, then cut to the terminal with the out-of-template result | "Against hidden labels the rules score 100 percent on this dataset and on held-out seeds. On hand-written sessions from a different domain they drop to 75 percent accuracy and miss four of six failures, which is why there is an optional LLM judge for the cases rules can't decide." |

## Upwork portfolio item

**Title** (61 characters)

AgentLens: finding AI agent sessions that silently failed

**Role**

Solo developer: detection engine, API, evaluation harness, dashboard, CI and Docker setup.

**Description**

AI agents inside business software often fail without any error: the tool call succeeds, the
agent answers confidently, and the user still gets the wrong answer. Error rates and status codes
don't catch this, and reading traces by hand doesn't scale.

I built AgentLens, an observability layer that ingests agent traces through a small Python SDK or
HTTP, checks each session's final claim against what the tools actually returned, and labels it as
success, recovered, failed or ambiguous with the exact events that prove the verdict. Failures are
grouped into ranked issues and shown in a React dashboard. The backend is FastAPI with SQLite,
analysis is incremental (only changed sessions are re-analyzed), and an optional LLM judge on any
OpenAI-compatible endpoint can review the cases the rules are unsure about.

The detector is scored by a separate evaluator against labels it never reads, and CI fails if the
score drops. On the 120-session synthetic dataset and on five held-out random seeds the rules
reach 100% accuracy. On 16 hand-written sessions from a different domain they reach 75% accuracy
with no false alarms but catch only 2 of 6 failures, which I report in the README as the current
limit. All data is synthetic and the LLM judge has not been benchmarked yet.

**Skills**

Python, FastAPI, React, SQLite, LLM Evaluation, AI Agent Observability, Docker, GitHub Actions

## Two-sentence version (portfolio site and CV)

AgentLens detects AI agent sessions that look successful but failed, by checking the agent's final
claim against what its tools actually returned, and shows the evidence for every verdict in a
dashboard. Scored against hidden labels, its rules reach 100% accuracy on a 120-session synthetic
dataset and held-out seeds, and 75% on hand-written sessions from an unseen domain.

## GitHub description and topics

**Description**

Finds AI agent sessions that look successful but failed: checks each final claim against the tool
results, ranks the failures into issues, and shows the evidence. Scored against hidden labels.

**Topics**

`ai-agents`, `llm-observability`, `agent-evaluation`, `llm-evaluation`, `fastapi`, `react`,
`sqlite`, `python`, `hackathon`
