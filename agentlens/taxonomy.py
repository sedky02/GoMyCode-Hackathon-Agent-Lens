"""The outcome vocabulary shared by the rules, the LLM judge, the API and the evaluator."""

OUTCOMES = ("success", "recovered", "failed", "ambiguous")

FAILURE_SEVERITY = {
    "unsupported_success": "high",
    "incomplete_request": "high",
    "wrong_record": "medium",
    "no_progress": "medium",
    "repeated_question": "low",
}
FAILURE_TYPES = frozenset(FAILURE_SEVERITY)
RECOVERY_TYPES = frozenset({"retry_success", "search_refinement", "clarification_success",
                            "corrected_tool_arguments"})
AMBIGUITY_TYPES = frozenset({"multiple_customers", "multiple_orders", "missing_information",
                             "unclear_user_intent"})

SUBTYPE_FIELD = {"failed": "failure_type", "recovered": "recovery_type", "ambiguous": "ambiguity_type"}
