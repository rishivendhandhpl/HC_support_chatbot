"""Application exceptions and FastAPI handlers."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base application error."""

    status_code = 500
    detail = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.detail)
        if detail:
            self.detail = detail


class NotFoundError(AppError):
    status_code = 404
    detail = "Resource not found"


class ConflictError(AppError):
    status_code = 409
    detail = "Conflict"


class ServiceError(AppError):
    status_code = 502
    detail = "Upstream service error"


def register_exception_handlers(app: FastAPI) -> None:
    """Attach JSON handlers for AppError subclasses."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        logger.warning("AppError: %s (%s)", exc.detail, exc.status_code)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
