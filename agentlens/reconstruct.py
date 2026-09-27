"""Turn a flat list of trace events into one chronological agent run."""

import json
import re
from dataclasses import dataclass

from .store import parse_event

TOKEN = re.compile(r"[A-Za-z0-9][\w\-+]*")
NUM = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class ToolCall:
    call: dict
    result: dict | None = None

    @property
    def name(self):
        return self.call["tool_name"]

    @property
    def args(self):
        return self.call.get("tool_arguments") or {}

    @property
    def data(self):
        return (self.result or {}).get("tool_result") or {}

    @property
    def ok(self):
        return self.result is not None and self.result.get("tool_status") == "success"

    @property
    def error(self):
        return "" if self.ok else str(self.data.get("error", ""))

    @property
    def seq(self):
        return self.call["sequence_number"]

    @property
    def ids(self):
        return [self.call["event_id"]] + ([self.result["event_id"]] if self.result else [])

    @property
    def count(self):
        c = self.data.get("count")
        return c if isinstance(c, int) else None

    def call_key(self):
        return self.name, json.dumps(self.args, sort_keys=True)

    def result_key(self):
        return json.dumps(self.data, sort_keys=True)


@dataclass
class Session:
    session_id: str
    events: list
    tool_calls: list

    def of_type(self, event_type):
        return [e for e in self.events if e["event_type"] == event_type]

    @property
    def user_messages(self):
        return self.of_type("user_message")

    @property
    def agent_messages(self):
        return self.of_type("agent_message")

    @property
    def final_agent(self):
        msgs = self.agent_messages
        return msgs[-1] if msgs else None

    @property
    def last_event(self):
        return self.events[-1] if self.events else None

    def user_text(self, before_seq=None):
        return " ".join(u["content"] for u in self.user_messages
                        if before_seq is None or u["sequence_number"] < before_seq)

    def users_between(self, after_seq, before_seq):
        return [u for u in self.user_messages if after_seq < u["sequence_number"] < before_seq]

    def calls_before(self, seq):
        return [tc for tc in self.tool_calls if tc.seq < seq]


def build_session(session_id, rows):
    events = [parse_event(r) for r in rows]
    events.sort(key=lambda e: e["sequence_number"])
    tool_calls = []
    for e in events:
        if e["event_type"] == "tool_call":
            tool_calls.append(ToolCall(e))
        elif e["event_type"] == "tool_result":
            for tc in reversed(tool_calls):
                if tc.result is None and tc.name == e["tool_name"]:
                    tc.result = e
                    break
    return Session(session_id, events, tool_calls)


def norm(text):
    return " ".join(t.lower() for t in TOKEN.findall(text or ""))


def contains(haystack, needle):
    n = norm(needle)
    return bool(n) and f" {n} " in f" {norm(haystack)} "


def numbers(obj):
    """Every number appearing anywhere in obj (including inside strings like 'O0061' or '2026-09-28')."""
    found = set()
    if isinstance(obj, bool) or obj is None:
        return found
    if isinstance(obj, (int, float)):
        found.add(round(float(obj), 2))
    elif isinstance(obj, str):
        found.update(round(float(n), 2) for n in NUM.findall(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            found |= numbers(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            found |= numbers(v)
    return found


def is_question(event):
    return event is not None and event["event_type"] == "agent_message" and "?" in (event.get("content") or "")
