"""Pydantic schemas for the chat and ingest endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

MAX_WORDS_PER_QUERY = 200


class ChatRequest(BaseModel):
    """Incoming chat message from the storefront widget."""

    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str = Field(..., min_length=1, max_length=128)
    is_pro: bool = False
    customer_id: str | None = None

    @field_validator("message")
    @classmethod
    def _enforce_word_limit(cls, value: str) -> str:
        """Cap each query at 200 words (whitespace-delimited)."""
        word_count = len(value.split())
        if word_count > MAX_WORDS_PER_QUERY:
            raise ValueError(
                f"message must be {MAX_WORDS_PER_QUERY} words or fewer "
                f"(received {word_count})"
            )
        return value


class RetrievedChunk(BaseModel):
    """A chunk surfaced by retrieval (for debugging / non-streaming responses)."""

    section: str
    question: str
    text: str
    pro_only: bool
    score: float


class IngestResponse(BaseModel):
    """Result of a knowledge-base re-index."""

    chunks_indexed: int
    pro_only_chunks: int
