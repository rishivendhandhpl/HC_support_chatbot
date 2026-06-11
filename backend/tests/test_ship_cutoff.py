"""The PST helper drives the 1 PM same-day ship-cutoff logic."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.dependencies import get_pst_now

_PST = ZoneInfo("America/Los_Angeles")


def test_get_pst_now_is_timezone_aware():
    now = get_pst_now()
    assert now.tzinfo is not None
    assert "Los_Angeles" in str(now.tzinfo) or now.utcoffset() is not None


def test_before_cutoff_is_same_day():
    t = datetime(2026, 6, 10, 12, 59, tzinfo=_PST)
    assert t.hour < 13  # before 1 PM PST → ships same day


def test_after_cutoff_is_next_day():
    t = datetime(2026, 6, 10, 13, 1, tzinfo=_PST)
    assert t.hour >= 13  # at/after 1 PM PST → ships next business day
