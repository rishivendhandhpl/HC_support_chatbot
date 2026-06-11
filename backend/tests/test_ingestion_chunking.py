"""Markdown chunking + pro_only classification (no DB / no OpenAI needed)."""
from __future__ import annotations

from app.services.ingestion import parse_markdown


def test_chunks_one_per_question(faq_sample):
    chunks = parse_markdown(faq_sample.read_text(encoding="utf-8"), "HC_FAQ.md")
    questions = [c.question for c in chunks]
    assert "What is H&C?" in questions
    assert "Where can I view your pricing?" in questions
    assert "How do I order online?" in questions
    assert len(chunks) == 3


def test_section_metadata_preserved(faq_sample):
    chunks = parse_markdown(faq_sample.read_text(encoding="utf-8"), "HC_FAQ.md")
    by_q = {c.question: c for c in chunks}
    assert by_q["What is H&C?"].section == "Company & Brand"
    assert by_q["Where can I view your pricing?"].section == "Ordering & Pricing"


def test_pricing_section_flagged_pro_only(faq_sample):
    chunks = parse_markdown(faq_sample.read_text(encoding="utf-8"), "HC_FAQ.md")
    by_q = {c.question: c for c in chunks}
    # Brand info is public.
    assert by_q["What is H&C?"].pro_only is False
    # Ordering & Pricing section is gated.
    assert by_q["Where can I view your pricing?"].pro_only is True
    assert by_q["How do I order online?"].pro_only is True


def test_chunk_text_includes_question_and_answer(faq_sample):
    chunks = parse_markdown(faq_sample.read_text(encoding="utf-8"), "HC_FAQ.md")
    brand = next(c for c in chunks if c.question == "What is H&C?")
    assert "established in 1992" in brand.text
    assert brand.text.startswith("What is H&C?")
