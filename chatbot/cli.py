"""Interactive terminal interface."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Callable

from openai import OpenAIError

from chatbot.config import ConfigError, load_settings
from chatbot.conversation import Conversation
from chatbot.llm import LLMClient

if TYPE_CHECKING:
    from chatbot.repository import Repository


def is_exit_command(text: str) -> bool:
    """``q`` (any case) leaves the current screen."""
    return text.strip().lower() == "q"


class ChatBotApp:
    def __init__(
        self,
        repository: Repository,
        llm,
        summarize_threshold: int,
        input_fn: Callable[[str], str] = input,
        print_fn: Callable[..., None] = print,
    ):
        self._repo = repository
        self._llm = llm
        self._threshold = summarize_threshold
        self._input = input_fn
        self._print = print_fn

    # -- chat screen ---------------------------------------------------------

    def run_chat(self, session_id: int) -> None:
        conversation = Conversation(
            self._repo, self._llm, session_id, self._threshold
        )
        while True:
            try:
                raw = self._input("Ask Something (press 'q' to go back) : ")
            except (EOFError, KeyboardInterrupt):
                self._print()
                return

            text = raw.strip()
            if not text:
                continue
            if is_exit_command(text):
                self._print("Good Bye")
                return

            try:
                # ``text`` keeps the user's original casing.
                conversation.send(
                    text, on_delta=lambda part: self._print(part, end="", flush=True)
                )
            except OpenAIError as exc:
                self._print(f"\nError talking to the model: {exc}")
            except KeyboardInterrupt:
                self._print("\n[interrupted]")
            else:
                self._print()

    # -- menu screen ---------------------------------------------------------

    def _print_sessions(self, sessions) -> None:
        self._print("\nSessions :")
        if not sessions:
            self._print("\t____ Sessions Empty ____")
            return
        for index, chat_session in enumerate(sessions):
            self._print(f"\t[{index}]. {chat_session.title}")

    def run(self) -> None:
        self._print("\n____ ABDOLGHADER ____")
        while True:
            sessions = self._repo.list_sessions()
            self._print("\n[N] Create Session")
            self._print("[E] Exit")
            self._print_sessions(sessions)

            try:
                choice = self._input("\nChoose an option : ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                self._print()
                return

            if choice == "e":
                self._print("Good Luck")
                return
            if choice == "n":
                title = self._input("Enter title (default=New Session) : ")
                self._repo.create_session(title)
                continue
            if choice.isdigit() and int(choice) < len(sessions):
                self.run_chat(sessions[int(choice)].session_id)
                continue

            self._print(f"\n'{choice}' is not a valid option. Please try again.")


def main() -> int:
    # Persistence is wired up here (the composition root) so the app class above
    # only depends on the repository interface, not on SQLAlchemy.
    from chatbot.repository import Repository
    from db.db import create_tables, make_engine, make_session_factory

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    engine = make_engine(settings.database_url)
    create_tables(engine)
    repository = Repository(make_session_factory(engine))

    try:
        llm = LLMClient(settings)
    except OpenAIError as exc:
        print(f"Could not create the API client: {exc}", file=sys.stderr)
        return 1

    ChatBotApp(repository, llm, settings.summarize_threshold).run()
    return 0
