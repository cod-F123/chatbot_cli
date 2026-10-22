from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from db.db import Base

DEFAULT_TITLE = "New Session"


class ChatSession(Base):
    __tablename__ = "chat_session"

    session_id = Column(Integer, primary_key=True)

    title = Column(String(100), default=DEFAULT_TITLE)

    # Cumulative tokens reported by the API for this session (informational).
    total_token = Column(Integer, default=0)

    messages = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.message_id",
    )


class Message(Base):
    __tablename__ = "message"

    message_id = Column(Integer, primary_key=True)

    # "system", "user" and "assistant" do not fit in String(4); SQLite ignores
    # the length but stricter databases (PostgreSQL, MySQL) would reject it.
    role = Column(String(20), default="user")

    content = Column(String)

    session_id = Column(ForeignKey("chat_session.session_id"))
    session = relationship("ChatSession", back_populates="messages")
