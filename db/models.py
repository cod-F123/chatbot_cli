from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from db.db import Base


class ChatSession(Base):
    __tablename__ = "chat_session"

    session_id = Column(Integer, primary_key=True)

    title = Column(String(100), default="New Session")
    messages = relationship("Message", back_populates="session")


class Message(Base):
    __tablename__ = "message"

    message_id = Column(Integer, primary_key=True)

    role = Column(String(4), default="user")

    content = Column(String)

    session_id = Column(ForeignKey("chat_session.session_id"))
    session = relationship("ChatSession", back_populates="messages")
