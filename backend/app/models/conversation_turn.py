"""ConversationTurn model — chat history keyed by session_id."""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ConversationTurn(Base, TimestampMixin):
    """A single user or assistant message within a chat session."""

    __tablename__ = "conversation_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # 'user' | 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_pro: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
