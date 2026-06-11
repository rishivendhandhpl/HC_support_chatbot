"""Chat orchestration: retrieve, assemble prompt, stream, persist history."""
from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from app.config import get_settings
from app.dependencies import get_openai_client, get_pst_now
from app.schemas.chat import ChatRequest
from app.services.embeddings import embed_text
from app.services.prompt import build_messages
from app.services.stores import Store

logger = logging.getLogger(__name__)


def stream_chat(store: Store, req: ChatRequest) -> Iterator[Any]:
    """Yield answer tokens for EventSourceResponse (which adds SSE framing).

    Yields plain token strings, then a final ``{"event": "done"}`` sentinel.
    Honors the server-side Pro gate via ``store.search(is_pro=...)`` and the
    prompt access directive. Never logs message content with PII — only ids.
    """
    settings = get_settings()
    logger.info(
        "chat session=%s is_pro=%s customer=%s",
        req.session_id,
        req.is_pro,
        req.customer_id or "-",
    )

    query_vec = embed_text(req.message)
    chunks = store.search(query_vec, is_pro=req.is_pro, k=settings.retrieval_top_k)
    history = store.get_history(req.session_id)
    messages = build_messages(
        req.message, chunks, is_pro=req.is_pro, now_pst=get_pst_now(), history=history
    )

    store.add_turn(req.session_id, "user", req.message, req.is_pro, req.customer_id)

    client = get_openai_client()
    collected: list[str] = []
    stream = client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,  # type: ignore[arg-type]
        temperature=0.2,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        if delta:
            collected.append(delta)
            yield delta  # EventSourceResponse wraps this as `data: <delta>`

    answer = "".join(collected)
    store.add_turn(req.session_id, "assistant", answer, req.is_pro, req.customer_id)
    yield {"event": "done", "data": "[DONE]"}
