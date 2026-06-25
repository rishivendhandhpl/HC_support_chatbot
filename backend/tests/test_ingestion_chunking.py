"""Markdown chunking + pro_only classification (no DB / no OpenAI needed)."""
from __future__ import annotations

from app.services.ingestion import parse_markdown, parse_wiki_dir, parse_wiki_markdown


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


# --------------------------------------------------------------------------- #
# Wiki docs: chunk per #/## topic heading, ### folded inline.                 #
# --------------------------------------------------------------------------- #
_WIKI_DOC = (
    "# Hair Textures - Complete Guide\n"
    "_verified by Elizabeth_\n\n"
    "# Natural Wave\n"
    "Classic S-shaped wave patterns.\n"
    "### Available In\n"
    "*   Both finishes: Premium AND Layered\n"
    "### Best For\n"
    "*   Brand transitions\n\n"
    "## Curly Hair Care\n"
    "Highest maintenance texture.\n"
)

# Mirrors HC Introduction.md: only `#` headings, NO `###` at all. The FAQ
# parser would produce zero chunks for this; the wiki parser must not.
_INTRO_DOC = (
    "# Introduction\n\n"
    "# Welcome to Hair School\n"
    "This guide is an orientation program for new team members.\n\n"
    "# Who Should Use This Document\n"
    "New team members and the customer service team.\n"
)


def test_wiki_chunks_per_topic_heading():
    chunks = parse_wiki_markdown(_WIKI_DOC, "Hair Textures - Complete Guide.md")
    questions = [c.question for c in chunks]
    # H1 and H2 headings become topic chunks...
    assert "Natural Wave" in questions
    assert "Curly Hair Care" in questions
    # ...but H3 sub-points are folded into the parent topic, not their own chunk.
    assert "Available In" not in questions
    assert "Best For" not in questions


def test_wiki_h3_folded_into_topic_body():
    chunks = parse_wiki_markdown(_WIKI_DOC, "Hair Textures - Complete Guide.md")
    natural = next(c for c in chunks if c.question == "Natural Wave")
    # The whole topic, including its ### sub-points, lives in one chunk.
    assert "Available In" in natural.text
    assert "Premium AND Layered" in natural.text
    assert "Best For" in natural.text


def test_wiki_section_is_document_title():
    chunks = parse_wiki_markdown(_WIKI_DOC, "Hair Textures - Complete Guide.md")
    # Document title (first heading) is preserved as the section for citations.
    assert all(c.section == "Hair Textures - Complete Guide" for c in chunks)
    assert all(c.source_file == "Hair Textures - Complete Guide.md" for c in chunks)


def test_wiki_h1_only_doc_still_chunks():
    # Regression: a doc with only `#` headings (like HC Introduction.md) must
    # NOT be silently dropped the way the FAQ parser would drop it.
    chunks = parse_wiki_markdown(_INTRO_DOC, "HC Introduction.md")
    questions = [c.question for c in chunks]
    assert "Welcome to Hair School" in questions
    assert "Who Should Use This Document" in questions
    assert len(chunks) >= 2


def test_wiki_heading_emphasis_stripped():
    chunks = parse_wiki_markdown(
        "# **Bold Title**\nbody\n# **Bold Topic**\nmore body\n", "x.md"
    )
    assert chunks[0].section == "Bold Title"
    assert any(c.question == "Bold Topic" for c in chunks)


def test_wiki_dir_dedup_and_skip(tmp_path):
    (tmp_path / "a.md").write_text("# A\nbody a\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# B\nbody b\n", encoding="utf-8")
    faq = tmp_path / "HC_FAQ.md"
    faq.write_text("## S\n### Q\nignored\n", encoding="utf-8")

    chunks = parse_wiki_dir(tmp_path, skip={faq})
    sources = {c.source_file for c in chunks}
    # FAQ skipped; both real wiki docs indexed exactly once.
    assert sources == {"a.md", "b.md"}


def test_wiki_dir_missing_returns_empty(tmp_path):
    assert parse_wiki_dir(tmp_path / "does_not_exist") == []
