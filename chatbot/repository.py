"""Persistence layer: every database operation lives here."""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import SQLAlchemyError

from db.models import DEFAULT_TITLE, ChatSession, Message


class Repository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    @contextmanager
    def _scope(self):
        """One transaction: commit on success, roll back on error, always close."""
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            raise
        finally:
            session.close()

    def list_sessions(self) -> list[ChatSession]:
        with self._scope() as db:
            return list(
                db.scalars(select(ChatSession).order_by(ChatSession.session_id))
            )

    def create_session(self, title: str = "") -> ChatSession:
        with self._scope() as db:
            chat_session = ChatSession(title=(title or "").strip() or DEFAULT_TITLE)
            db.add(chat_session)
            db.flush()  # assigns session_id
            return chat_session

    def get_messages(self, session_id: int) -> list[dict]:
        """Return the session's messages, oldest first, as ``{role, content}`` dicts."""
        with self._scope() as db:
            rows = db.scalars(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.message_id)
            )
            return [{"role": row.role, "content": row.content} for row in rows]

    def add_message(self, session_id: int, role: str, content: str) -> None:
        with self._scope() as db:
            db.add(Message(session_id=session_id, role=role, content=content))

    def add_tokens(self, session_id: int, amount: int) -> None:
        """Atomically add ``amount`` to the session's cumulative token count."""
        with self._scope() as db:
            db.execute(
                update(ChatSession)
                .where(ChatSession.session_id == session_id)
                .values(total_token=func.coalesce(ChatSession.total_token, 0) + amount)
                .execution_options(synchronize_session=False)
            )

    def replace_with_summary(self, session_id: int, summary: str) -> None:
        """Swap the whole history for a single summary message, in one transaction."""
        with self._scope() as db:
            db.execute(
                delete(Message)
                .where(Message.session_id == session_id)
                .execution_options(synchronize_session=False)
            )
            db.add(Message(session_id=session_id, role="system", content=summary))
