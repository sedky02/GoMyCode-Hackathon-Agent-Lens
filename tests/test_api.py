from concurrent.futures import ThreadPoolExecutor

import httpx


def test_read_endpoints_survive_concurrent_requests(live_server):
    with ThreadPoolExecutor(8) as pool:
        codes = list(pool.map(lambda _: httpx.get(f"{live_server}/v1/overview").status_code, range(40)))
    assert codes == [200] * 40


VALID_EVENT = {"session_id": "T1", "sequence_number": 1, "timestamp": "2026-01-01 00:00:00",
               "event_type": "user_message", "role": "user", "content": "hi"}


def test_ingest_accepts_sdk_and_dataset_shapes(client, dataset_events):
    tool_call = {**VALID_EVENT, "sequence_number": 2, "event_type": "tool_call", "tool_name": "get_stock",
                 "tool_arguments": {"product_name": "Desk"}}
    assert client.post("/v1/events", json={"events": dataset_events[:50]}).json() == {"accepted": 50}
    assert client.post("/v1/events", json={"events": [VALID_EVENT, tool_call]}).json() == {"accepted": 2}
    stored = client.get("/v1/sessions/T1").json()["events"]
    assert stored[1]["tool_arguments"] == {"product_name": "Desk"}


def test_ingest_ignores_duplicate_event_ids(client, dataset_events):
    client.post("/v1/events", json={"events": dataset_events[:10]})
    assert client.post("/v1/events", json={"events": dataset_events[:10]}).json() == {"accepted": 0}


def test_ingest_rejects_malformed_events(client):
    bad_events = [
        {k: v for k, v in VALID_EVENT.items() if k != "session_id"},
        {**VALID_EVENT, "sequence_number": "abc"},
        {**VALID_EVENT, "timestamp": 123},
        {**VALID_EVENT, "event_type": "banana"},
        {**VALID_EVENT, "event_type": "tool_call", "tool_arguments_json": "{not json"},
    ]
    for event in bad_events:
        assert client.post("/v1/events", json={"events": [event]}).status_code == 422, event
    assert client.get("/v1/overview").json()["totals"]["events"] == 0


def test_unknown_ids_and_filters_are_client_errors(client):
    assert client.get("/v1/sessions/NOPE").status_code == 404
    assert client.get("/v1/issues/999").status_code == 404
    assert client.get("/v1/sessions", params={"outcome": "bogus"}).status_code == 422
    assert client.post("/v1/demo/waves/3").status_code == 404
