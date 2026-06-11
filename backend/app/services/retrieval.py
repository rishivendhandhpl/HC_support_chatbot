"""Retrieval result type shared by all storage backends."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Retrieved:
    """A retrieved chunk plus its cosine distance (lower = closer)."""

    section: str
    question: str
    text: str
    pro_only: bool
    distance: float
