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


def _clean_heading(text: str) -> str:
    """Strip markdown emphasis / stray punctuation from a heading for metadata."""
    return text.strip().strip("*").strip().strip("#").strip()


def parse_wiki_markdown(content: str, source_file: str) -> list[ParsedChunk]:
    """Chunk a long-form wiki doc: one chunk per `#`/`##` topic heading.

    Unlike the FAQ (one chunk per `###` Q&A), the wiki docs use `#`/`##` for the
    document title and major topics and `###` for sub-points. We chunk at the
    topic level so each chunk keeps its full context, and fold `###` sub-points
    into the topic body. The document title (first heading) becomes the chunk
    ``section`` so citations read "<doc topic> — <file>".
    """
    chunks: list[ParsedChunk] = []
    title: str | None = None
    current_heading: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current_heading is None:
            return
        body = "\n".join(buffer).strip()
        if not body:
            return  # heading with no content of its own — skip
        section = title or source_file
        full_text = f"{current_heading}\n{body}".strip()
        chunks.append(
            ParsedChunk(
                section=section,
                question=current_heading,
                text=full_text,
                pro_only=_is_pro_only(section, full_text),
                source_file=source_file,
            )
        )

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        # Topic boundary = H1 or H2 (but NOT H3+, which stay inline as body).
        if line.startswith("# ") or line.startswith("## "):
            flush()
            current_heading = _clean_heading(line.lstrip("#").strip())
            if title is None:
                title = current_heading
            buffer = []
        else:
            if current_heading is not None:
                buffer.append(line)
    flush()
    return chunks


def parse_wiki_dir(
    wiki_dir: Path, *, skip: set[Path] | None = None
) -> list[ParsedChunk]:
    """Scan a directory for *.md files and parse each into topic chunks.

    Files are processed in a stable, sorted order and de-duplicated by resolved
    path so no document is indexed twice. ``skip`` excludes specific files
    (e.g. the FAQ / instruction) should they ever live under the wiki dir.
    """
    chunks: list[ParsedChunk] = []
    if not wiki_dir.exists():
        logger.warning("Wiki directory not found: %s", wiki_dir)
        return chunks

    skip_resolved = {p.resolve() for p in (skip or set())}
    seen: set[Path] = set()
    for md_path in sorted(wiki_dir.glob("*.md")):
        resolved = md_path.resolve()
        if resolved in skip_resolved or resolved in seen:
            continue  # avoid duplicate indexing
        seen.add(resolved)
        doc_chunks = parse_wiki_markdown(
            md_path.read_text(encoding="utf-8"), md_path.name
        )
        if not doc_chunks:
            logger.warning("No chunks parsed from wiki doc: %s", md_path.name)
        chunks += doc_chunks
    logger.info("Parsed %d wiki chunks from %d files.", len(chunks), len(seen))
    return chunks


def parse_files(
    faq_path: Path, instruction_path: Path, wiki_dir: Path | None = None
) -> list[ParsedChunk]:
    """Parse the FAQ, system instruction, and (optionally) the wiki dir."""
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
    if wiki_dir is not None:
        chunks += parse_wiki_dir(
            wiki_dir, skip={faq_path, instruction_path}
        )
    return chunks


def ingest(
    store: Store,
    faq_path: Path,
    instruction_path: Path,
    wiki_dir: Path | None = None,
) -> tuple[int, int]:
    """Re-index the knowledge base. Returns (chunks_indexed, pro_only_count).

    Idempotent: parses the FAQ, system instruction, and every wiki doc, then
    clears existing chunks and re-embeds/inserts them in a single atomic
    ``replace_chunks`` call. Combining all sources into one replace means
    re-running never produces duplicates and the wiki never wipes the FAQ.
    Works against any storage backend (pgvector or in-memory).
    """
    parsed = parse_files(faq_path, instruction_path, wiki_dir)
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
