"""KnowledgeChunk model — one row per FAQ Q&A / instruction chunk."""
from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.config import get_settings
from app.models.base import Base, TimestampMixin

_DIM = get_settings().embedding_dim


class KnowledgeChunk(Base, TimestampMixin):
    """A single retrievable chunk of the H&C knowledge base."""

    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(_DIM), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    section: Mapped[str] = mapped_column(String(255), nullable=False)
    question: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    pro_only: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
