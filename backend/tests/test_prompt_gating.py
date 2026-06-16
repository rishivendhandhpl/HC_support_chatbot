"""Prompt assembly enforces the Pro/anonymous access directive."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.prompt import build_user_content
from app.services.retrieval import Retrieved

_NOW = datetime(2026, 6, 10, 10, 0, tzinfo=ZoneInfo("America/Los_Angeles"))


def _chunk() -> Retrieved:
    return Retrieved(
        section="Shipping & Insurance",
        question="How long does it take to receive hair?",
        text="Orders before 1 PM PST ship same day.",
        pro_only=False,
        distance=0.1,
    )


def test_anonymous_directive_blocks_pricing():
    content = build_user_content("show me prices", [_chunk()], is_pro=False, now_pst=_NOW)
    assert "ANONYMOUS" in content
    assert "Do NOT share pricing" in content
    assert "pages/create-an-account" in content


def test_pro_directive_allows_pricing():
    content = build_user_content("show me prices", [_chunk()], is_pro=True, now_pst=_NOW)
    assert "PRO (logged-in" in content
    assert "pricing guidance" in content


def test_pst_time_injected():
    content = build_user_content("when ship?", [_chunk()], is_pro=True, now_pst=_NOW)
    assert "CURRENT PST TIME" in content
    assert "01:00 PM" in content or "1 PM PST" in content


def test_context_included():
    content = build_user_content("when ship?", [_chunk()], is_pro=True, now_pst=_NOW)
    assert "same day" in content
    assert "USER QUESTION:" in content
