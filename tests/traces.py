"""Tiny builder for hand-written traces in the same row shape the store returns."""

import json


class Trace:
    def __init__(self, session_id="T001", first_event_id=1000):
        self.session_id = session_id
        self.rows = []
        self._next_id = first_event_id

    def _add(self, event_type, role, content, **fields):
        row = {"event_id": self._next_id, "session_id": self.session_id, "sequence_number": len(self.rows) + 1,
               "timestamp": f"2026-01-01 10:00:{len(self.rows):02d}", "event_type": event_type, "role": role,
               "content": content, "tool_name": None, "tool_arguments_json": None, "tool_result_json": None,
               "tool_status": None, "latency_ms": None, **fields}
        self.rows.append(row)
        self._next_id += 1
        return self

    def user(self, text):
        return self._add("user_message", "user", text)

    def agent(self, text):
        return self._add("agent_message", "assistant", text)

    def tool(self, name, arguments, result, status="success"):
        self._add("tool_call", "assistant", f"Agent invokes {name}", tool_name=name,
                  tool_arguments_json=json.dumps(arguments))
        return self._add("tool_result", "tool", f"{name} returned", tool_name=name,
                         tool_result_json=json.dumps(result), tool_status=status, latency_ms=120)

    def call_only(self, name, arguments):
        return self._add("tool_call", "assistant", f"Agent invokes {name}", tool_name=name,
                         tool_arguments_json=json.dumps(arguments))
