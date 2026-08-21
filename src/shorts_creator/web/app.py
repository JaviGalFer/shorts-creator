"""FastAPI application factory for the web backend.

Production wiring (repository + executor + service) is built inside the app
lifespan, not at module import, so no worker pool is created without
cleanup. Startup reconciles stale persisted jobs once; shutdown stops the
executor. Tests inject a pre-built service and fully own its lifecycle.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI

from shorts_creator.web import dependencies
from shorts_creator.web.routes import health, jobs, media

API_PREFIX = "/api/v1"


def _make_lifespan(prebuilt_service: Any):
    @asynccontextmanager
    async def _lifespan(app) -> AsyncIterator[None]:
        if prebuilt_service is None:
            repository, executor, service = dependencies.build_service()
            app.state.repository = repository
            app.state.executor = executor
            app.state.service = service
            try:
                stale_ids = repository.list_web_job_ids()
                executor.reconcile_stale(stale_ids)
            except Exception:  # noqa: BLE001
                dependencies.logger.warning("startup reconciliation failed", exc_info=True)
            try:
                yield
            finally:
                executor.shutdown()
        else:
            yield

    return _lifespan


def create_app(*, service: Any = None) -> FastAPI:
    """Build the FastAPI app.

    ``service`` may be injected for tests (in-memory/temp repository and a
    stubbed executor). When omitted, the default production wiring is built
    once, inside the lifespan, and torn down on shutdown.
    """
    app = FastAPI(
        title="shorts-creator-web",
        version="0.1.0",
        lifespan=_make_lifespan(service),
    )
    if service is not None:
        app.state.repository = service.repository
        app.state.executor = service.executor
        app.state.service = service

    dependencies.install_exception_handlers(app)

    app.include_router(health.router, prefix=API_PREFIX, tags=["health"])
    app.include_router(jobs.router, prefix=API_PREFIX, tags=["jobs"])
    app.include_router(media.router, prefix=API_PREFIX, tags=["media"])
    return app


# Uvicorn CLI entrypoint: `uvicorn shorts_creator.web.app:app`.
# No pool/repository is created at import; wiring happens on startup.
app = create_app()