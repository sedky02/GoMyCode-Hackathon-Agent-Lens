"""Combine rule signals into one session outcome."""

from .reconstruct import numbers

RECOVERY_PRIORITY = ["retry_success", "corrected_tool_arguments", "search_refinement", "clarification_success"]


def classify(session, signals):
    """Returns (analysis dict, uncertain flag)."""
    failures = [s for s in signals if s.kind == "failure"]
    ambiguities = [s for s in signals if s.kind == "ambiguity"]
    recoveries = [s for s in signals if s.kind == "recovery"]
    base = {"failure_type": None, "recovery_type": None, "ambiguity_type": None, "source": "rules"}

    if failures:
        best = max(failures, key=lambda s: s.confidence)
        return {**base, "outcome": "failed", "failure_type": best.type, "confidence": best.confidence,
                "reason": best.reason, "evidence_event_ids": best.evidence}, False

    last = session.last_event
    if last is None or last["event_type"] != "agent_message":
        return {**base, "outcome": "ambiguous", "ambiguity_type": "incomplete_trace", "confidence": 0.4,
                "reason": "The trace has no final agent response yet (session still in progress or truncated).",
                "evidence_event_ids": [last["event_id"]] if last else []}, True

    if ambiguities:
        best = ambiguities[0]
        return {**base, "outcome": "ambiguous", "ambiguity_type": best.type, "confidence": best.confidence,
                "reason": best.reason, "evidence_event_ids": best.evidence}, False

    if recoveries:
        best = min(recoveries, key=lambda s: RECOVERY_PRIORITY.index(s.type))
        evidence = best.evidence + [last["event_id"]]
        return {**base, "outcome": "recovered", "recovery_type": best.type, "confidence": best.confidence,
                "reason": best.reason, "evidence_event_ids": evidence}, False

    return _success_or_uncertain(session, base)


def _success_or_uncertain(session, base):
    final = session.final_agent
    supported = numbers(session.user_text())
    for tc in session.tool_calls:
        if tc.ok:
            supported |= numbers(tc.data) | numbers(tc.args)
    unsupported = numbers(final["content"]) - supported
    evidence = [session.user_messages[0]["event_id"]] if session.user_messages else []
    evidence += [i for tc in session.tool_calls for i in tc.ids] + [final["event_id"]]
    if unsupported:
        return {**base, "outcome": "success", "confidence": 0.55,
                "reason": f"No rule fired, but the final answer contains values {sorted(unsupported)} that no "
                          f"successful tool result supports.",
                "evidence_event_ids": evidence}, True
    return {**base, "outcome": "success", "confidence": 0.9,
            "reason": "The agent's final answer is fully supported by successful tool results and no failure, "
                      "recovery or ambiguity pattern was detected.",
            "evidence_event_ids": evidence}, False
