"""Pydantic schemas for the chat and ingest endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat message from the storefront widget."""

    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str = Field(..., min_length=1, max_length=128)
    is_pro: bool = False
    customer_id: str | None = None


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
