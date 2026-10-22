"""Test doubles shared by the test modules."""

from __future__ import annotations

from types import SimpleNamespace

from chatbot.llm import ChatResult


class FakeRepository:
    """In-memory stand-in for ``chatbot.repository.Repository``."""

    def __init__(self):
        self.sessions = {}
        self.messages = {}
        self.tokens = {}
        self._next_id = 1

    def list_sessions(self):
        return [SimpleNamespace(session_id=sid, title=title) for sid, title in self.sessions.items()]

    def create_session(self, title=""):
        sid = self._next_id
        self._next_id += 1
        self.sessions[sid] = title
        self.messages[sid] = []
        self.tokens[sid] = 0
        return SimpleNamespace(session_id=sid, title=title)

    def get_messages(self, session_id):
        return [dict(m) for m in self.messages.get(session_id, [])]

    def add_message(self, session_id, role, content):
        self.messages.setdefault(session_id, []).append({"role": role, "content": content})

    def add_tokens(self, session_id, amount):
        self.tokens[session_id] = self.tokens.get(session_id, 0) + amount

    def replace_with_summary(self, session_id, summary):
        self.messages[session_id] = [{"role": "system", "content": summary}]


class FakeLLM:
    """Scripted LLM: pops one ``(text, total_tokens)`` pair per ``stream_chat`` call."""

    def __init__(self, replies, summary="a short summary", summarize_error=None):
        self.replies = list(replies)
        self.summary = summary
        self.summarize_error = summarize_error
        self.chat_calls = []  # snapshot of the messages sent on each call
        self.summarize_calls = []

    def stream_chat(self, messages, on_delta=None):
        self.chat_calls.append([dict(m) for m in messages])
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        text, tokens = reply
        if on_delta and text:
            on_delta(text)
        return ChatResult(text=text, total_tokens=tokens)

    def summarize(self, messages):
        self.summarize_calls.append([dict(m) for m in messages])
        if self.summarize_error:
            raise self.summarize_error
        return self.summary
