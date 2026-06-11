"""Embedding helpers wrapping the OpenAI embeddings API."""
from __future__ import annotations

import logging

from app.config import get_settings
from app.dependencies import get_openai_client

logger = logging.getLogger(__name__)


def embed_text(text: str) -> list[float]:
    """Embed a single string, returning its vector."""
    return embed_texts([text])[0]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of strings using the configured embedding model."""
    if not texts:
        return []
    settings = get_settings()
    client = get_openai_client()
    response = client.embeddings.create(model=settings.openai_embed_model, input=texts)
    # Preserve input order.
    return [item.embedding for item in sorted(response.data, key=lambda d: d.index)]
