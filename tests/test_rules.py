"""Each detector on a minimal hand-written trace, next to the look-alike trace it must not flag."""

from agentlens.pipeline import analyze_rows
from traces import Trace


def verdict(trace):
    analysis, failures, _live, _judge_failed = analyze_rows(trace.session_id, trace.rows, "rules", None)
    return analysis, failures


def subtype(analysis):
    return analysis["failure_type"] or analysis["recovery_type"] or analysis["ambiguity_type"]


def test_wrong_record_when_the_queried_entity_was_never_requested():
    trace = (Trace().user("How many Samsung TV 43-inch do we have in stock?")
             .tool("get_stock", {"product_name": "Samsung TV 65-inch"},
                   {"product_name": "Samsung TV 65-inch", "stock_quantity": 11})
             .agent("You have 11 Samsung TV 43-inch in stock."))
    analysis, failures = verdict(trace)
    assert (analysis["outcome"], subtype(analysis)) == ("failed", "wrong_record")
    assert failures[0].details["queried"] == "Samsung TV 65-inch"
    assert set(analysis["evidence_event_ids"]) == {1000, 1001, 1002, 1003}


def test_success_when_the_queried_entity_matches_the_request():
    trace = (Trace().user("How many Samsung TV 43-inch do we have in stock?")
             .tool("get_stock", {"product_name": "Samsung TV 43-inch"},
                   {"product_name": "Samsung TV 43-inch", "stock_quantity": 11})
             .agent("You have 11 Samsung TV 43-inch in stock."))
    analysis, failures = verdict(trace)
    assert analysis["outcome"] == "success" and not failures
    assert analysis["confidence"] >= 0.7


def test_unsupported_success_when_every_call_failed_but_the_agent_claims_done():
    trace = (Trace().user("Please update Rania's phone to +216 20 111 222.")
             .tool("update_customer", {"customer_id": "C007", "phone": "+216 20 111 222"},
                   {"error": "Database write conflict, the record could not be saved."}, status="error")
             .agent("Done, Rania's phone number has been updated."))
    analysis, _ = verdict(trace)
    assert (analysis["outcome"], subtype(analysis)) == ("failed", "unsupported_success")


def test_recovered_when_a_transient_error_is_retried_successfully():
    trace = (Trace().user("How many Dell XPS 13 are in stock?")
             .tool("get_stock", {"product_name": "Dell XPS 13"},
                   {"error": "Database connection timed out, please retry."}, status="error")
             .tool("get_stock", {"product_name": "Dell XPS 13"},
                   {"product_name": "Dell XPS 13", "stock_quantity": 4})
             .agent("You have 4 Dell XPS 13 in stock."))
    analysis, failures = verdict(trace)
    assert (analysis["outcome"], subtype(analysis)) == ("recovered", "retry_success")
    assert not failures


def test_recovered_when_rejected_arguments_are_corrected():
    trace = (Trace().user("Order 50 Office Chair for customer C003.")
             .tool("create_order", {"customer_id": "C003", "product": "Office Chair", "quantity": 50},
                   {"error": "Insufficient stock: only 20 available."}, status="error")
             .agent("Only 20 are available. Shall I order 20 instead?")
             .user("Yes, 20 is fine.")
             .tool("create_order", {"customer_id": "C003", "product": "Office Chair", "quantity": 20},
                   {"order_id": "O0101", "status": "confirmed", "delivery_date": "2026-01-05"})
             .agent("Order O0101 for 20 Office Chair has been created."))
    analysis, _ = verdict(trace)
    assert (analysis["outcome"], subtype(analysis)) == ("recovered", "corrected_tool_arguments")


def test_incomplete_request_when_a_claimed_part_came_back_null():
    trace = (Trace().user("Create an order of 3 Laser Printer for C010 and schedule delivery for tomorrow.")
             .tool("create_order", {"customer_id": "C010", "product": "Laser Printer", "quantity": 3},
                   {"order_id": "O0102", "status": "pending_scheduling", "delivery_date": None})
             .agent("Order O0102 has been created and delivery is scheduled for tomorrow."))
    analysis, failures = verdict(trace)
    assert (analysis["outcome"], subtype(analysis)) == ("failed", "incomplete_request")
    assert failures[0].details["field"] == "delivery_date"


def test_no_progress_when_the_same_call_repeats_with_the_same_result():
    matches = {"count": 2, "matches": [{"customer_id": "C1", "name": "Ahmed Ben Ali"},
                                       {"customer_id": "C2", "name": "Ahmed Gharbi"}]}
    trace = Trace().user("Show me Ahmed's latest order.")
    for _ in range(3):
        trace.tool("find_customer", {"query": "Ahmed"}, matches)
    trace.agent("I could not determine which customer you mean.")
    analysis, failures = verdict(trace)
    assert (analysis["outcome"], subtype(analysis)) == ("failed", "no_progress")
    assert failures[0].details["repeats"] == 3


def test_search_refinement_is_a_recovery_not_a_loop():
    trace = (Trace().user("Show me the latest order of Ahmed from Sfax.")
             .tool("find_customer", {"query": "Ahmed"},
                   {"count": 2, "matches": [{"customer_id": "C1", "name": "Ahmed Ben Ali", "city": "Tunis"},
                                            {"customer_id": "C2", "name": "Ahmed Ben Salah", "city": "Sfax"}]})
             .tool("find_customer", {"query": "Ahmed", "city": "Sfax"},
                   {"count": 1, "matches": [{"customer_id": "C2", "name": "Ahmed Ben Salah", "city": "Sfax"}]})
             .agent("Ahmed Ben Salah is customer C2."))
    analysis, failures = verdict(trace)
    assert (analysis["outcome"], subtype(analysis)) == ("recovered", "search_refinement")
    assert not failures


def test_repeated_question_when_the_user_already_gave_the_value():
    trace = (Trace().user("Find the orders of Leila Mansour, her phone is +216 22 333 444.")
             .tool("find_customer", {"query": "Leila Mansour"},
                   {"count": 1, "matches": [{"customer_id": "C9", "name": "Leila Mansour"}]})
             .agent("Could you give me the customer's phone number?")
             .user("I already told you: +216 22 333 444.")
             .agent("Thanks, Leila Mansour is customer C9."))
    analysis, failures = verdict(trace)
    assert (analysis["outcome"], subtype(analysis)) == ("failed", "repeated_question")
    assert failures[0].details["asked_for"] == "phone"


def test_ambiguous_when_a_needed_clarification_is_never_answered():
    trace = (Trace().user("Cancel Mohamed Karray's order.")
             .tool("find_customer", {"query": "Mohamed Karray"},
                   {"count": 2, "matches": [{"customer_id": "C4", "name": "Mohamed Karray", "city": "Tunis"},
                                            {"customer_id": "C5", "name": "Mohamed Karray", "city": "Sfax"}]})
             .agent("I found two customers named Mohamed Karray. Which city, Tunis or Sfax?"))
    analysis, failures = verdict(trace)
    assert (analysis["outcome"], subtype(analysis)) == ("ambiguous", "multiple_customers")
    assert not failures


def test_answered_clarification_is_a_plain_success():
    trace = (Trace().user("Cancel Mohamed Karray's order.")
             .tool("find_customer", {"query": "Mohamed Karray"},
                   {"count": 2, "matches": [{"customer_id": "C4", "name": "Mohamed Karray", "city": "Tunis"},
                                            {"customer_id": "C5", "name": "Mohamed Karray", "city": "Sfax"}]})
             .agent("I found two customers named Mohamed Karray. Which city, Tunis or Sfax?")
             .user("The one in Sfax.")
             .tool("update_order", {"order_id": "O0044", "status": "cancelled"},
                   {"order_id": "O0044", "status": "cancelled"})
             .agent("Order O0044 has been cancelled."))
    analysis, _ = verdict(trace)
    assert analysis["outcome"] == "success"


def test_trace_without_a_final_agent_reply_is_flagged_incomplete():
    trace = (Trace().user("How many Dell XPS 13 are in stock?")
             .call_only("get_stock", {"product_name": "Dell XPS 13"}))
    analysis, _ = verdict(trace)
    assert (analysis["outcome"], subtype(analysis)) == ("ambiguous", "incomplete_trace")
    assert analysis["confidence"] < 0.7
