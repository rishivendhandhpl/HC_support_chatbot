"""/chat router — streaming SSE chat endpoint."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.schemas.chat import ChatRequest
from app.security.shopify_proxy import extract_customer_id, verify_app_proxy_signature
from app.services.chat_service import stream_chat
from app.services.stores import Store, get_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


def _resolve_access(request: Request, payload: ChatRequest) -> tuple[bool, str | None]:
    """Determine (is_pro, customer_id) securely.

    Production (require_proxy_signature=True): verify the Shopify App Proxy
    signature and derive Pro status from the signed logged_in_customer_id — the
    client body's is_pro/customer_id are ignored and cannot be forged.

    Dev (False): trust the body, for local testing without Shopify.
    """
    settings = get_settings()
    if not settings.require_proxy_signature:
        return payload.is_pro, payload.customer_id

    params: dict[str, str | list[str]] = {}
    for key, value in request.query_params.multi_items():
        existing = params.get(key)
        if existing is None:
            params[key] = value
        elif isinstance(existing, list):
            existing.append(value)
        else:
            params[key] = [existing, value]

    if not verify_app_proxy_signature(params, settings.shopify_app_secret):
        logger.warning("Rejected /chat: invalid Shopify App Proxy signature.")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid signature")

    customer_id = extract_customer_id(params)
    return bool(customer_id), customer_id


@router.post("/chat")
async def chat(
    request: Request, payload: ChatRequest, store: Store = Depends(get_store)
):
    """Stream a grounded, Pro-gated answer back to the widget over SSE."""
    is_pro, customer_id = _resolve_access(request, payload)
    secured = payload.model_copy(update={"is_pro": is_pro, "customer_id": customer_id})
    return EventSourceResponse(stream_chat(store, secured), ping=15000)
