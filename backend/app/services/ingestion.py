"""Knowledge-base ingestion: parse markdown, chunk per Q&A, embed, upsert.

The FAQ is chunked one chunk per `###` question (heading kept as the
`section` metadata). The system instruction is chunked per `###` subsection so
its policy details are retrievable too. Pricing / ordering / account chunks are
flagged ``pro_only=True`` so retrieval can withhold them from anonymous users.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from app.services.embeddings import embed_texts
from app.services.stores import ChunkRecord, Store

logger = logging.getLogger(__name__)

# Sections (## headings) whose content is gated to logged-in Pro members.
_PRO_ONLY_SECTIONS = {
    "accounts & access",
    "ordering & pricing",
    "orders & payments",
}

# Keyword fallback so a pricing/quote answer in any section is still gated.
_PRO_ONLY_KEYWORDS = re.compile(
    r"\b(price|pricing|prices|quote|checkout|place an order|deep[- ]?link)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedChunk:
    """An un-embedded knowledge chunk parsed from a markdown file."""

    section: str
    question: str
    text: str
    pro_only: bool
    source_file: str


def _is_pro_only(section: str, body: str) -> bool:
    if section.strip().lower() in _PRO_ONLY_SECTIONS:
        return True
    return bool(_PRO_ONLY_KEYWORDS.search(body))


def parse_markdown(content: str, source_file: str) -> list[ParsedChunk]:
    """Split markdown into chunks: one per `###` question under each `##` section."""
    chunks: list[ParsedChunk] = []
    current_section = source_file
    current_question: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current_question is None:
            return
        body = "\n".join(buffer).strip()
        if not body and not current_question:
            return
        full_text = f"{current_question}\n{body}".strip()
        chunks.append(
            ParsedChunk(
                section=current_section,
                question=current_question,
                text=full_text,
                pro_only=_is_pro_only(current_section, full_text),
                source_file=source_file,
            )
        )

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## ") and not line.startswith("### "):
            flush()
            current_question = None
            buffer = []
            current_section = line[3:].strip()
        elif line.startswith("### "):
            flush()
            current_question = line[4:].strip()
            buffer = []
        else:
            if current_question is not None:
                buffer.append(line)
    flush()
    return chunks


def parse_files(faq_path: Path, instruction_path: Path) -> list[ParsedChunk]:
    """Parse both knowledge-base files into chunks."""
    chunks: list[ParsedChunk] = []
    if faq_path.exists():
        chunks += parse_markdown(faq_path.read_text(encoding="utf-8"), faq_path.name)
    else:
        logger.warning("FAQ file not found: %s", faq_path)
    if instruction_path.exists():
        chunks += parse_markdown(
            instruction_path.read_text(encoding="utf-8"), instruction_path.name
        )
    else:
        logger.warning("System instruction file not found: %s", instruction_path)
    return chunks


def ingest(store: Store, faq_path: Path, instruction_path: Path) -> tuple[int, int]:
    """Re-index the knowledge base. Returns (chunks_indexed, pro_only_count).

    Idempotent: clears existing chunks then re-embeds and inserts. Works against
    any storage backend (pgvector or in-memory).
    """
    parsed = parse_files(faq_path, instruction_path)
    if not parsed:
        logger.warning("No chunks parsed; aborting ingest.")
        return 0, 0

    embeddings = embed_texts([c.text for c in parsed])
    records = [
        ChunkRecord(
            text=chunk.text,
            section=chunk.section,
            question=chunk.question,
            pro_only=chunk.pro_only,
            source_file=chunk.source_file,
            embedding=vector,
        )
        for chunk, vector in zip(parsed, embeddings, strict=True)
    ]
    store.replace_chunks(records)

    pro_only = sum(1 for c in parsed if c.pro_only)
    logger.info("Ingested %d chunks (%d pro_only).", len(records), pro_only)
    return len(records), pro_only
