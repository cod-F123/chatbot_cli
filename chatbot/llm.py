"""Thin wrapper around an OpenAI-compatible chat completions API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from chatbot.config import Settings
from chatbot.prompts import SUMMARIZE_PROMPT

CHAT_TEMPERATURE = 0.7
SUMMARY_TEMPERATURE = 0.3


@dataclass
class ChatResult:
    text: str
    total_tokens: int


def estimate_tokens(messages: list[dict], reply: str = "") -> int:
    """Rough token estimate (about 4 characters per token).

    Only used when the provider does not report usage while streaming.
    """
    chars = sum(len(m.get("content") or "") for m in messages) + len(reply)
    return max(1, chars // 4)


class LLMClient:
    def __init__(self, settings: Settings, client: Optional[Any] = None):
        self._settings = settings
        if client is None:
            # Imported lazily so this module (and its tests) work without the SDK.
            from openai import OpenAI

            client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)
        self._client = client

    def stream_chat(
        self,
        messages: list[dict],
        on_delta: Optional[Callable[[str], None]] = None,
    ) -> ChatResult:
        """Stream a reply, calling ``on_delta`` with each text fragment."""
        extra = {}
        if self._settings.include_stream_usage:
            extra["stream_options"] = {"include_usage": True}

        stream = self._client.chat.completions.create(
            model=self._settings.chat_model,
            messages=messages,
            temperature=CHAT_TEMPERATURE,
            stream=True,
            **extra,
        )

        parts: list[str] = []
        total_tokens: Optional[int] = None
        for chunk in stream:
            usage = getattr(chunk, "usage", None)
            if usage is not None and getattr(usage, "total_tokens", None):
                total_tokens = usage.total_tokens
            # The final usage chunk has an empty ``choices`` list.
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                parts.append(delta)
                if on_delta is not None:
                    on_delta(delta)

        text = "".join(parts)
        if total_tokens is None:
            total_tokens = estimate_tokens(messages, text)
        return ChatResult(text=text, total_tokens=total_tokens)

    def summarize(self, messages: list[dict]) -> str:
        """Ask the summarization model to condense ``messages``."""
        response = self._client.chat.completions.create(
            model=self._settings.summarize_model,
            messages=[{"role": "system", "content": SUMMARIZE_PROMPT}, *messages],
            temperature=SUMMARY_TEMPERATURE,
        )
        return response.choices[0].message.content or ""
