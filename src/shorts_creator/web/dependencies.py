"""Application wiring: singleton construction.

Mutable operational state (repository, executor, service) is built and wired
inside the app lifespan (see ``app._make_lifespan``) rather than at module
import time. Startup runs reconciliation (stale QUEUED/RUNNING ->
INTERRUPTED); shutdown stops the executor. MVP assumes a single Uvicorn
worker while the executor is in-process.
"""

from __future__ import annotations

import logging
from pathlib import Path

from shorts_creator.web.exceptions import (
    ApplicationError,
    to_http_error,
    to_http_internal_error,
)
from shorts_creator.web.repository import FilesystemJobRepository

logger = logging.getLogger(__name__)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def build_service():
    """Build repository + executor + service for the current process."""
    from shorts_creator.web.executor import LocalJobExecutor
    from shorts_creator.web.service import JobService

    root = _project_root()
    videos_root = root / "data" / "videos"

    repository = FilesystemJobRepository(videos_root)
    executor = LocalJobExecutor(repo=repository)
    service = JobService(repository, executor)
    return repository, executor, service


def install_exception_handlers(app) -> None:
    """Register the single centralized error mapping on the app."""

    @app.exception_handler(ApplicationError)
    async def _app_error_handler(request, exc):
        status, body = to_http_error(exc)
        return _json_response(status, body)

    @app.exception_handler(Exception)
    async def _unexpected_handler(request, exc):
        status, body = to_http_internal_error(log_context=request.url.path)
        return _json_response(status, body)


def _json_response(status: int, body: dict):
    from starlette.responses import JSONResponse

    return JSONResponse(status_code=status, content=body)