"""Deterministic detectors. Each looks at session structure (arguments vs. the user's words,
results vs. the agent's claims, how the run ends) and returns Signals."""

import re
from dataclasses import dataclass, field

from .reconstruct import TOKEN, contains, is_question, norm, numbers

KEY_ARGS = ("product_name", "query", "customer_name", "product")
TRANSIENT_ERROR = re.compile(r"timeout|timed out|temporar|unavailable|please retry|connection", re.I)
SUCCESS_CLAIM = re.compile(
    r"\b(done|has been (updated|created|cancel+ed|saved|scheduled)|updated to|will be delivered"
    r"|(you|we) (currently )?have \d+|\d+ units)\b", re.I)
PHONE = re.compile(r"\+?\d[\d\- ]{7,}\d")
ORDER_ID = re.compile(r"\b[Oo]\d{3,}\b")
STOP = {
    "you", "we", "have", "the", "of", "in", "do", "how", "many", "units", "unit", "stock", "currently", "a",
    "an", "is", "are", "our", "for", "to", "available", "right", "now", "can", "check", "level", "what", "s",
    "current", "inventory", "i", "need", "know", "there", "there's", "it", "on", "and", "your",
}


@dataclass
class Signal:
    kind: str                 # failure | recovery | ambiguity
    type: str
    confidence: float
    reason: str
    evidence: list
    severity: str | None = None
    tool: str | None = None
    details: dict = field(default_factory=dict)
    signature: str = ""


def common_phrase(a, b):
    """Longest shared word sequence between two texts, trimmed of filler words."""
    ta, tb = TOKEN.findall(a or ""), TOKEN.findall(b or "")
    la, lb = [t.lower() for t in ta], [t.lower() for t in tb]
    best_len, best = 0, None
    for i in range(len(la)):
        for j in range(len(lb)):
            k = 0
            while i + k < len(la) and j + k < len(lb) and la[i + k] == lb[j + k]:
                k += 1
            if not k:
                continue
            seg = ta[i:i + k]
            while seg and seg[0].lower() in STOP:
                seg = seg[1:]
            while seg and seg[-1].lower() in STOP:
                seg = seg[:-1]
            if len(seg) > best_len:
                best_len, best = len(seg), " ".join(seg)
    return best


def clause(text, stem):
    for part in re.split(r"[,.;!?]| and ", text or ""):
        if stem in part.lower():
            return part.strip()
    return None


def detect_no_progress(s):
    signals, run = [], []
    for tc in s.tool_calls:
        if (run and tc.ok and run[-1].ok and tc.call_key() == run[-1].call_key()
                and tc.result_key() == run[-1].result_key()
                and not s.users_between(run[-1].seq, tc.seq)):
            run.append(tc)
        else:
            if len(run) >= 3:
                signals.append(_no_progress_signal(s, run))
            run = [tc]
    if len(run) >= 3:
        signals.append(_no_progress_signal(s, run))
    return signals


def _no_progress_signal(s, run):
    first = run[0]
    evidence = [i for tc in run for i in tc.ids]
    after = [a for a in s.agent_messages if a["sequence_number"] > run[-1].seq]
    if after:
        evidence.append(after[0]["event_id"])
    return Signal(
        "failure", "no_progress", 0.9,
        f"{first.name} was called {len(run)} times with identical arguments {first.args} and returned the "
        f"identical result every time; the agent never refined the query or asked the user to clarify.",
        evidence, severity="medium", tool=first.name,
        details={"tool": first.name, "arguments": first.args, "repeats": len(run),
                 "result_count": first.count},
        signature=f"no_progress | tool={first.name} | identical call repeated with identical result "
                  f"| no refinement or clarification",
    )


def detect_unsupported_success(s):
    final = s.final_agent
    if not final or not SUCCESS_CLAIM.search(final["content"]):
        return []
    before = s.calls_before(final["sequence_number"])
    if not before:
        return []
    last = before[-1]
    same_tool = [tc for tc in before if tc.name == last.name]
    if last.ok or any(tc.ok for tc in same_tool):
        return []
    evidence = [i for tc in same_tool for i in tc.ids] + [final["event_id"]]
    return [Signal(
        "failure", "unsupported_success", 0.95,
        f"Every {last.name} call failed (last error: '{last.error}'), yet the agent's final message claims "
        f"success: \"{final['content']}\"",
        evidence, severity="high", tool=last.name,
        details={"requested": s.user_messages[0]["content"] if s.user_messages else None,
                 "tool": last.name, "tool_status": "error", "returned": last.error,
                 "claimed": final["content"]},
        signature=f"unsupported_success | tool={last.name} | tool returned an error | agent claimed success",
    )]


def detect_wrong_record(s):
    final = s.final_agent
    if not final:
        return []
    signals = []
    for tc in s.calls_before(final["sequence_number"]):
        if not tc.ok:
            continue
        for arg in KEY_ARGS:
            value = tc.args.get(arg)
            if not isinstance(value, str):
                continue
            earlier_results = " ".join(str(prev.data) for prev in s.calls_before(tc.seq))
            if contains(s.user_text(tc.seq), value) or contains(earlier_results, value):
                continue
            if contains(final["content"], value):
                continue
            value_nums = numbers(tc.data) & numbers(final["content"])
            if not value_nums:
                continue
            requested_msg = s.user_messages[0] if s.user_messages else None
            requested = common_phrase(requested_msg["content"], final["content"]) if requested_msg else None
            returned = tc.data.get("product_name") or tc.data.get("name") or value
            evidence = ([requested_msg["event_id"]] if requested_msg else []) + tc.ids + [final["event_id"]]
            signals.append(Signal(
                "failure", "wrong_record", 0.92,
                f"The user asked about '{requested}' but {tc.name} was called with {arg}='{value}' "
                f"(never mentioned by the user). The agent then reported that record's value as if it "
                f"belonged to '{requested}'.",
                evidence, severity="medium", tool=tc.name,
                details={"requested": requested, "queried": value, "returned": returned,
                         "claimed": requested, "claimed_value": sorted(value_nums)[0]},
                signature=f"wrong_record | tool={tc.name} | key argument not grounded in the user request "
                          f"| answer attributed the tool value to the requested entity",
            ))
    return signals


def detect_incomplete_request(s):
    final = s.final_agent
    if not final:
        return []
    signals = []
    for tc in s.calls_before(final["sequence_number"]):
        if not tc.ok:
            continue
        for key, value in tc.data.items():
            if value is not None:
                continue
            stem = key.split("_")[0][:7]
            user_text = s.user_text(final["sequence_number"])
            if stem not in norm(final["content"]) or stem not in norm(user_text):
                continue
            user_msg = next((u for u in s.user_messages if stem in norm(u["content"])), None)
            evidence = ([user_msg["event_id"]] if user_msg else []) + tc.ids + [final["event_id"]]
            signals.append(Signal(
                "failure", "incomplete_request", 0.9,
                f"The user asked for '{clause(user_text, stem)}'. {tc.name} returned {key}=null "
                f"(status: {tc.data.get('status')}), so that part was never done, but the agent claimed: "
                f"\"{clause(final['content'], stem)}\".",
                evidence, severity="high", tool=tc.name,
                details={"requested": clause(user_text, stem), "field": key, "returned": None,
                         "status": tc.data.get("status"), "claimed": clause(final["content"], stem)},
                signature=f"incomplete_request | tool={tc.name} | result field {key} missing "
                          f"| agent claimed that part of the request was done",
            ))
    return signals


def detect_repeated_question(s):
    names = {m["name"] for tc in s.tool_calls if tc.ok for m in tc.data.get("matches", []) if "name" in m}
    signals = []
    for q in s.agent_messages:
        if not is_question(q):
            continue
        text = q["content"].lower()
        slots = [slot for slot, pat in (("name", r"\bname\b"), ("phone", r"phone"),
                                        ("order", r"order (number|id)")) if re.search(pat, text)]
        if not slots:
            continue
        prior_users = [u for u in s.user_messages if u["sequence_number"] < q["sequence_number"]]
        last_user_seq = prior_users[-1]["sequence_number"] if prior_users else 0
        disambiguating = any(tc.count and tc.count > 1 for tc in s.tool_calls
                             if last_user_seq < tc.seq < q["sequence_number"])
        if disambiguating:
            continue
        for slot in slots:
            for u in prior_users:
                value = None
                if slot == "name":
                    value = next((n for n in names if contains(u["content"], n)), None)
                elif slot == "phone":
                    m = PHONE.search(u["content"])
                    value = m.group(0) if m else None
                elif slot == "order":
                    m = ORDER_ID.search(u["content"])
                    value = m.group(0) if m else None
                if value:
                    reply = next((r for r in s.user_messages if r["sequence_number"] > q["sequence_number"]), None)
                    evidence = [u["event_id"], q["event_id"]] + ([reply["event_id"]] if reply else [])
                    signals.append(Signal(
                        "failure", "repeated_question", 0.9,
                        f"The agent asked for the customer's {slot}, but the user had already provided it "
                        f"('{value}') in an earlier message.",
                        evidence, severity="low", tool=None,
                        details={"asked_for": slot, "already_provided": value, "asked": q["content"]},
                        signature=f"repeated_question | slot={slot} | agent asked for information the user "
                                  f"already provided",
                    ))
                    return signals
    return signals


def detect_ambiguous_ending(s):
    last = s.last_event
    if not is_question(last):
        return []
    prior_calls = s.calls_before(last["sequence_number"])
    ambiguous_call = next((tc for tc in reversed(prior_calls) if tc.ok and tc.count and tc.count > 1), None)
    if ambiguous_call:
        kind = {"find_customer": "multiple_customers", "find_order": "multiple_orders"}.get(
            ambiguous_call.name, "multiple_matches")
        evidence = [s.user_messages[0]["event_id"]] + ambiguous_call.ids + [last["event_id"]]
        reason = (f"{ambiguous_call.name} returned {ambiguous_call.count} matches, the agent correctly asked "
                  f"which one the user meant, and the user never answered.")
    else:
        kind = ("missing_information" if re.search(r"\b(order|customer|invoice|id|number)\b", last["content"], re.I)
                else "unclear_user_intent")
        evidence = [u["event_id"] for u in s.user_messages] + [last["event_id"]]
        reason = ("The request lacked information needed to act, the agent asked for it instead of "
                  "guessing, and the user never answered.")
    return [Signal("ambiguity", kind, 0.85, reason, evidence)]


def detect_retries(s):
    signals = []
    for i, tc in enumerate(s.tool_calls):
        if tc.ok or tc.result is None:
            continue
        later_ok = next((t for t in s.tool_calls[i + 1:] if t.name == tc.name and t.ok), None)
        if not later_ok:
            continue
        transient = bool(TRANSIENT_ERROR.search(tc.error))
        kind = "retry_success" if transient else "corrected_tool_arguments"
        how = ("retried after a transient error" if transient
               else f"changed the arguments from {tc.args} to {later_ok.args}")
        signals.append(Signal(
            "recovery", kind, 0.9,
            f"{tc.name} failed ('{tc.error}'); the agent {how} and the next call succeeded.",
            tc.ids + later_ok.ids, tool=tc.name,
        ))
        break
    return signals


def detect_search_refinement(s):
    for prev, nxt in zip(s.tool_calls, s.tool_calls[1:]):
        if (prev.name == nxt.name and prev.ok and nxt.ok and prev.count and prev.count > 1
                and nxt.count == 1 and not s.users_between(prev.seq, nxt.seq)):
            return [Signal(
                "recovery", "search_refinement", 0.9,
                f"{prev.name}({prev.args}) returned {prev.count} matches; the agent refined it to "
                f"{nxt.args} using context the user had already given, and reached a unique match.",
                prev.ids + nxt.ids, tool=prev.name,
            )]
    return []


def detect_clarification_rounds(s):
    answered = [q for q in s.agent_messages if is_question(q) and any(
        u["sequence_number"] > q["sequence_number"] for u in s.user_messages)]
    if len(answered) < 2:
        return []
    evidence = []
    for q in answered:
        evidence.append(q["event_id"])
        reply = next(u for u in s.user_messages if u["sequence_number"] > q["sequence_number"])
        evidence.append(reply["event_id"])
    return [Signal(
        "recovery", "clarification_success", 0.85,
        f"The agent needed {len(answered)} clarification rounds: the first answer did not resolve the "
        f"ambiguity, the agent recognized that, asked again, and then completed the request.",
        sorted(set(evidence)),
    )]


ALL_RULES = [
    detect_no_progress, detect_unsupported_success, detect_wrong_record, detect_incomplete_request,
    detect_repeated_question, detect_ambiguous_ending, detect_retries, detect_search_refinement,
    detect_clarification_rounds,
]


def run_rules(session):
    return [sig for rule in ALL_RULES for sig in rule(session)]
