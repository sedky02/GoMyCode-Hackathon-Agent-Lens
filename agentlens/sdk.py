"""AgentLens SDK: drop-in trace logging for an AI agent.

    client = AgentLensClient("http://localhost:8100")
    client.log_user("S001", "How many Samsung TVs do we have?")
    client.log_tool_call("S001", "get_stock", {"product_name": "Samsung TV"})
    client.log_tool_result("S001", "get_stock", {"stock_quantity": 37}, status="success", latency_ms=210)
    client.log_agent("S001", "You have 37 Samsung TVs.")
    client.flush()
"""

import time
from collections import defaultdict
from datetime import datetime

import httpx


class AgentLensClient:
    def __init__(self, base_url="http://localhost:8100", batch_size=200, timeout=30.0):
        self.base_url = base_url.rstrip("/")
        self.batch_size = batch_size
        self._buffer = []
        self._seq = defaultdict(int)
        self._http = httpx.Client(timeout=timeout)

    def log_event(self, event):
        """Log a fully-specified event (used for replaying existing traces)."""
        self._buffer.append(event)
        self._seq[event["session_id"]] = max(self._seq[event["session_id"]], event["sequence_number"])
        if len(self._buffer) >= self.batch_size:
            self.flush()

    def _log(self, session_id, event_type, role, content, **tool_fields):
        self._seq[session_id] += 1
        self.log_event({
            "session_id": session_id,
            "sequence_number": self._seq[session_id],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event_type": event_type,
            "role": role,
            "content": content,
            **tool_fields,
        })

    def log_user(self, session_id, content):
        self._log(session_id, "user_message", "user", content)

    def log_agent(self, session_id, content):
        self._log(session_id, "agent_message", "assistant", content)

    def log_tool_call(self, session_id, tool_name, arguments):
        self._log(session_id, "tool_call", "assistant", f"Agent invokes {tool_name}",
                  tool_name=tool_name, tool_arguments=arguments)

    def log_tool_result(self, session_id, tool_name, result, status="success", latency_ms=None):
        self._log(session_id, "tool_result", "tool", f"{tool_name} returned",
                  tool_name=tool_name, tool_result=result, tool_status=status, latency_ms=latency_ms)

    def flush(self):
        if not self._buffer:
            return 0
        batch, self._buffer = self._buffer, []
        resp = self._http.post(f"{self.base_url}/v1/events", json={"events": batch})
        resp.raise_for_status()
        return resp.json()["accepted"]

    def analyze(self, wait=True, on_progress=None, poll_seconds=1.0):
        """Start a background analysis run; if wait, poll until it finishes and return the run summary."""
        resp = self._http.post(f"{self.base_url}/v1/analyze")
        resp.raise_for_status()
        if not wait:
            return resp.json()
        while True:
            status = self._http.get(f"{self.base_url}/v1/analyze/status").json()
            if on_progress:
                on_progress(status)
            if not status["running"]:
                if status.get("error"):
                    raise RuntimeError(f"analysis failed: {status['error']}")
                return status["last_run"]
            time.sleep(poll_seconds)
