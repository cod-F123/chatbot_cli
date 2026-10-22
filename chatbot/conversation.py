"""Conversation logic: keeps the message history, talks to the LLM, summarizes."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from chatbot.prompts import SUMMARY_PREFIX, SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class Conversation:
    """One chat session.

    ``messages`` is what gets sent to the model: the base system prompt (never
    stored in the database) followed by the stored history.
    """

    def __init__(
        self,
        repository,
        llm,
        session_id: int,
        summarize_threshold: int,
        system_prompt: str = SYSTEM_PROMPT,
    ):
        self._repo = repository
        self._llm = llm
        self.session_id = session_id
        self._threshold = summarize_threshold
        self.messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            *repository.get_messages(session_id),
        ]
        # Size of the context at the last request (prompt + reply). Summarization
        # is triggered by this, not by the cumulative count.
        self.context_tokens = 0

    def send(
        self, text: str, on_delta: Optional[Callable[[str], None]] = None
    ) -> str:
        """Send ``text`` to the model and return the full reply."""
        self._remember("user", text)

        result = self._llm.stream_chat(self.messages, on_delta)

        if result.text:
            self._remember("assistant", result.text)
        self._repo.add_tokens(self.session_id, result.total_tokens)
        self.context_tokens = result.total_tokens

        self._maybe_summarize()
        return result.text

    def _remember(self, role: str, content: str) -> None:
        # Database first, so memory never claims something that was not saved.
        self._repo.add_message(self.session_id, role, content)
        self.messages.append({"role": role, "content": content})

    def _maybe_summarize(self) -> bool:
        if self.context_tokens < self._threshold:
            return False

        history = self.messages[1:]  # everything except the base system prompt
        try:
            summary = self._llm.summarize(history)
        except Exception:  # the reply was already delivered; try again next turn
            logger.warning("Summarization failed; keeping full history", exc_info=True)
            return False
        if not summary.strip():
            return False

        content = SUMMARY_PREFIX + summary.strip()
        self._repo.replace_with_summary(self.session_id, content)
        self.messages = [self.messages[0], {"role": "system", "content": content}]
        self.context_tokens = 0
        return True
