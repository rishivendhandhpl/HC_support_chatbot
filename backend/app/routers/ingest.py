"""/ingest router — re-index the knowledge base."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.schemas.chat import IngestResponse
from app.services.ingestion import ingest
from app.services.stores import Store, get_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse)
async def reindex(store: Store = Depends(get_store)) -> IngestResponse:
    """Re-embed and re-index HC_FAQ.md + HC_SYSTEM_INSTRUCTION.md + companyWiki/."""
    settings = get_settings()
    count, pro_only = ingest(
        store,
        Path(settings.faq_path),
        Path(settings.system_instruction_path),
        Path(settings.wiki_dir),
    )
    return IngestResponse(chunks_indexed=count, pro_only_chunks=pro_only)
