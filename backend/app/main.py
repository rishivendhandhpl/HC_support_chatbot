"""FastAPI application entrypoint for the H&C AI Virtual Stylist backend."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.config import get_settings
from app.exceptions import register_exception_handlers
from app.routers import chat, ingest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_min}/minute"])


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    errors = settings.validate_runtime()
    if errors:
        for message in errors:
            logger.error("Configuration error: %s", message)
        raise RuntimeError(
            "Refusing to start with invalid configuration: " + "; ".join(errors)
        )
    logger.info(
        "H&C backend started. model=%s embed=%s store=%s origins=%s proxy_verify=%s",
        settings.openai_model,
        settings.openai_embed_model,
        settings.store_backend,
        settings.allowed_origins_list,
        settings.require_proxy_signature,
    )
    yield


app = FastAPI(title="H&C AI Virtual Stylist", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)  # enforces default per-IP rate limits

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(chat.router)
app.include_router(ingest.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
