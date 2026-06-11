"""Shared FastAPI dependencies and helpers."""
from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from openai import OpenAI

from app.config import get_settings
from app.database import get_db  # re-exported for convenience

__all__ = ["get_db", "get_openai_client", "get_pst_now"]

_PST = ZoneInfo("America/Los_Angeles")


@lru_cache
def get_openai_client() -> OpenAI:
    """Return a cached OpenAI client (reads OPENAI_API_KEY from settings/env)."""
    settings = get_settings()
    return OpenAI(api_key=settings.openai_api_key or None)


def get_pst_now() -> datetime:
    """Current time in America/Los_Angeles — used for the 1 PM PST ship cutoff."""
    return datetime.now(tz=_PST)
