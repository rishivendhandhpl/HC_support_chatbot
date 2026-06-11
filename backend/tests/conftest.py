"""Shared pytest fixtures."""
from __future__ import annotations

import os

import pytest

# Ensure settings never require a real key during tests.
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql://hc:hc@localhost:5432/hc_chatbot")


@pytest.fixture
def faq_sample(tmp_path):
    """A small two-section markdown file for chunking tests."""
    content = (
        "# FAQ\n\n"
        "## Company & Brand\n\n"
        "### What is H&C?\n"
        "Hair & Compounds was established in 1992.\n\n"
        "## Ordering & Pricing\n\n"
        "### Where can I view your pricing?\n"
        "To see prices you must create an account.\n\n"
        "### How do I order online?\n"
        "Apply for a Pro-Access Account first.\n"
    )
    path = tmp_path / "HC_FAQ.md"
    path.write_text(content, encoding="utf-8")
    return path
