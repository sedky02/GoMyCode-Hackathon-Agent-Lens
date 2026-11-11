"""LLM semantic judge over any OpenAI-compatible endpoint (Brev vLLM/NIM, Ollama, NVIDIA API catalog...).

Configure with AGENTLENS_LLM_BASE_URL, AGENTLENS_LLM_MODEL and optionally AGENTLENS_LLM_API_KEY.
Smoke test:  python -m agentlens.judge S008
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime

from .taxonomy import AMBIGUITY_TYPES, FAILURE_TYPES, OUTCOMES, RECOVERY_TYPES

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """You audit sessions of an AI assistant for an ERP system (inventory, customers, orders, invoices).
Decide whether the agent actually fulfilled the user's request, using ONLY the evidence in the timeline.
Tool results are the source of truth; the agent's words are claims to verify.

Pick exactly one outcome:
- success: the request was fulfilled correctly and every claim in the final answer is backed by a successful tool result.
- recovered: something went wrong along the way (a tool error that was retried or corrected, an over-broad search the agent refined, or a clarification that needed more than one round), but the final result is correct.
- failed: the request was not actually fulfilled, even if the tools technically succeeded. failure_type is one of:
  unsupported_success (the agent claims success or states facts that the tool results do not support, for example after a tool error),
  repeated_question (the agent asks for information the user had already given),
  no_progress (the agent repeats the same action with the same result and never changes strategy),
  wrong_record (the agent queried or reported a different record or entity than the user asked for),
  incomplete_request (the agent claims part of the request was done, but the tool result shows it was not, for example a null field).
- ambiguous: the request genuinely needed clarification and the session ended before it came. Asking a clarifying question about a truly ambiguous request is correct behavior, NOT a failure. ambiguity_type is one of multiple_customers, multiple_orders, missing_information, unclear_user_intent.

Reply with ONLY a JSON object:
{"outcome": "...", "failure_type": null, "recovery_type": null, "ambiguity_type": null,
 "confidence": 0.0, "reason": "one or two sentences citing the events", "evidence_event_ids": [ids]}
recovery_type, when used, is one of retry_success, search_refinement, clarification_success, corrected_tool_arguments."""


def config():
    return {
        "base_url": os.environ.get("AGENTLENS_LLM_BASE_URL"),
        "model": os.environ.get("AGENTLENS_LLM_MODEL"),
        "api_key": os.environ.get("AGENTLENS_LLM_API_KEY", "EMPTY"),
    }


def enabled():
    cfg = config()
    return bool(cfg["base_url"] and cfg["model"])


def render_timeline(session):
    lines = []
    for e in session.events:
        tag = f"[event {e['event_id']}]"
        if e["event_type"] == "user_message":
            lines.append(f"{tag} USER: {e['content']}")
        elif e["event_type"] == "agent_message":
            lines.append(f"{tag} AGENT: {e['content']}")
        elif e["event_type"] == "tool_call":
            lines.append(f"{tag} TOOL CALL {e['tool_name']}({json.dumps(e['tool_arguments'])})")
        elif e["event_type"] == "tool_result":
            lines.append(f"{tag} TOOL RESULT {e['tool_name']} status={e['tool_status']}: "
                         f"{json.dumps(e['tool_result'])}")
    return "\n".join(lines)


def _extract_json(text):
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in judge output: {text[:200]!r}")
    return json.loads(text[start:end + 1])


def _normalize(raw, session):
    outcome = str(raw.get("outcome", "")).lower().strip()
    if outcome not in OUTCOMES:
        raise ValueError(f"invalid outcome {outcome!r}")

    def pick(key, allowed, when):
        value = raw.get(key)
        return value if outcome == when and value in allowed else None

    valid_ids = {e["event_id"] for e in session.events}
    evidence = [int(i) for i in raw.get("evidence_event_ids") or [] if str(i).isdigit() and int(i) in valid_ids]
    try:
        confidence = min(max(float(raw.get("confidence", 0.7)), 0.0), 1.0)
    except (TypeError, ValueError):
        confidence = 0.7
    return {
        "outcome": outcome,
        "failure_type": pick("failure_type", FAILURE_TYPES, "failed"),
        "recovery_type": pick("recovery_type", RECOVERY_TYPES, "recovered"),
        "ambiguity_type": pick("ambiguity_type", AMBIGUITY_TYPES, "ambiguous"),
        "confidence": confidence,
        "reason": str(raw.get("reason", ""))[:1000],
        "evidence_event_ids": evidence,
        "source": "llm",
    }


def judge(session, digest, conn):
    """Return a normalized verdict dict, or None if the judge is not configured or fails.
    Second element tells whether a live LLM call was made (False = cache hit)."""
    cfg = config()
    if not enabled():
        return None, False
    key = hashlib.sha256(f"{digest}|{PROMPT_VERSION}|{cfg['model']}".encode()).hexdigest()
    row = conn.execute("SELECT response_json FROM llm_cache WHERE cache_key = ?", (key,)).fetchone()
    if row:
        return json.loads(row["response_json"]), False

    from openai import OpenAI
    client = OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"], timeout=90, max_retries=6)
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Session {session.session_id} timeline:\n{render_timeline(session)}"}]
    from openai import AuthenticationError, NotFoundError
    # reasoning models (gpt-oss) spend completion tokens thinking before the JSON answer
    extra = {"reasoning_effort": "low"} if "gpt-oss" in cfg["model"] else {}
    params = dict(model=cfg["model"], messages=messages, temperature=0, max_tokens=2000, **extra)
    try:
        try:
            resp = client.chat.completions.create(**params, response_format={"type": "json_object"})
        except (AuthenticationError, NotFoundError):
            raise
        except Exception:
            resp = client.chat.completions.create(**params)
        verdict = _normalize(_extract_json(resp.choices[0].message.content), session)
    except Exception as exc:
        print(f"[judge] {session.session_id}: {exc}", file=sys.stderr)
        return None, True
    conn.execute("INSERT OR REPLACE INTO llm_cache VALUES (?, ?, ?)",
                 (key, json.dumps(verdict), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    return verdict, True


def check():
    """Verify the endpoint + API key and list the model ids the key can use."""
    from openai import AuthenticationError, OpenAI

    cfg = config()
    if not cfg["base_url"]:
        sys.exit("AGENTLENS_LLM_BASE_URL is empty in .env")
    key = cfg["api_key"]
    key_state = f"set ({len(key)} chars)" if key not in ("", "EMPTY") else "NOT set"
    print(f"Endpoint: {cfg['base_url']}   API key: {key_state}")
    if "integrate.api.nvidia.com" in cfg["base_url"] and not key.startswith("nvapi-"):
        print("WARNING: NVIDIA API catalog keys start with 'nvapi-' and are ~70 chars. "
              "The key in .env does not look like one.")
    client = OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"] or "EMPTY", timeout=30)
    try:
        ids = [m.id for m in client.models.list()]
    except AuthenticationError:
        sys.exit("The endpoint rejected the API key (401). Re-copy the key from the Brev console into .env.")
    except Exception as exc:
        sys.exit(f"Could not reach the endpoint: {exc}\nCheck AGENTLENS_LLM_BASE_URL (it should end in /v1).")
    print("Models available with this key:")
    for model_id in ids:
        print(f"  {model_id}")
    if cfg["model"] not in ids:
        sys.exit(f"Set AGENTLENS_LLM_MODEL in .env to one of the ids above (current: {cfg['model']!r}).")
    print(f"Model {cfg['model']} is listed. Testing the key with a real request...")
    try:
        client.chat.completions.create(model=cfg["model"], max_tokens=1,
                                       messages=[{"role": "user", "content": "ping"}])
    except AuthenticationError as exc:
        sys.exit(f"FAILED: the key was rejected on a real request (401): {exc}\n"
                 "Put the full nvapi-... key from build.nvidia.com into AGENTLENS_LLM_API_KEY in .env.")
    except Exception as exc:
        sys.exit(f"FAILED: the test request errored: {exc}")
    print(f"OK: key accepted and {cfg['model']} answered. The judge is ready.")


if __name__ == "__main__":
    from .reconstruct import build_session
    from .snapshot import trace_hash
    from .store import connect, session_events

    if "--check" in sys.argv:
        check()
        sys.exit(0)
    if not enabled():
        sys.exit("Set AGENTLENS_LLM_BASE_URL and AGENTLENS_LLM_MODEL in .env first.")
    conn = connect()
    sid = sys.argv[1] if len(sys.argv) > 1 else "S008"
    rows = session_events(conn, sid)
    if not rows:
        sys.exit(f"No events for {sid} in agentlens.db. Run scripts/replay.py first.")
    print(json.dumps(judge(build_session(sid, rows), trace_hash(rows), conn)[0], indent=2))
