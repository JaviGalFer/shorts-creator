"""FastAPI application factory for the web backend.

Production wiring (repository + executor + service) is built inside the app
lifespan, not at module import, so no worker pool is created without
cleanup. Startup reconciles stale persisted jobs once; shutdown stops the
executor. Tests inject a pre-built service and fully own its lifecycle.

Angular production build is served from ``web/frontend/dist/frontend/browser/``.
A catch-all route provides SPA fallback for frontend routes only;
``/api/v1/...`` paths are never intercepted. Static assets (.js, .css, .ico, etc.)
are served directly from the browser build root.
"""

from __future__ import annotations

import os
import pathlib
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from shorts_creator.web import dependencies
from shorts_creator.web.routes import health, jobs, media

API_PREFIX = "/api/v1"

# Environment variable driving the production Angular build root inside Docker.
# Resolution precedence (highest first): explicit ``frontend_dist`` argument >
# ``SHORTS_FRONTEND_DIST`` env > development/source-layout default.
FRONTEND_DIST_ENV = "SHORTS_FRONTEND_DIST"
_SOURCE_LAYOUT_FRONTEND_DIST = pathlib.Path(__file__).parent.parent.parent.parent.joinpath(
    "web", "frontend", "dist", "frontend", "browser"
)


def _resolve_frontend_dist(explicit: Optional[pathlib.Path]) -> pathlib.Path:
    """Return the configured frontend browser-build directory.

    ``explicit`` wins (tests inject a temporary dir). Otherwise fall back to the
    ``SHORTS_FRONTEND_DIST`` environment variable (set by Docker), then to the
    development/source-layout default.
    """
    if explicit is not None:
        return explicit
    env = os.environ.get(FRONTEND_DIST_ENV)
    if env:
        return pathlib.Path(env)
    return _SOURCE_LAYOUT_FRONTEND_DIST


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


def create_app(*, service: Any = None, frontend_dist: Optional[pathlib.Path] = None) -> FastAPI:
    """Build the FastAPI app.

    ``service`` may be injected for tests (in-memory/temp repository and a
    stubbed executor). When omitted, the default production wiring is built
    once, inside the lifespan, and torn down on shutdown.

    ``frontend_dist`` may be injected to configure the Angular browser build
    directory. When omitted, resolution falls back to ``SHORTS_FRONTEND_DIST``
    and then the package layout. Tests can supply a temporary directory.
    """
    _frontend_dist = _resolve_frontend_dist(frontend_dist)

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

    @app.get("/{full_path:path}")
    async def spa_fallback(request: Request, full_path: str) -> FileResponse:
        """Serve Angular production build for SPA routing.

        Priority:
        1. If the requested path maps to a real file under ``frontend_dist``,
           serve that file (covers .js, .css, .ico, assets, etc.).
        2. If no real static file exists and the path is a frontend route
           (not starting with ``/api``), serve ``index.html``.
        3. Anything beginning with ``/api`` must never fall back to Angular.
           Paths that escape the frontend build root also return 404.
        """
        # Strip leading slash for consistent checking
        path_to_check = full_path.lstrip("/")

        # 3. API namespace — never fall back; also block escaped paths
        if path_to_check == "api" or path_to_check.startswith("api/") or path_to_check.startswith("../"):
            raise HTTPException(status_code=404)

        # 1. Try to serve real static file from frontend_dist
        static_path = _frontend_dist.joinpath(path_to_check).resolve()
        # Security: ensure resolved path is still under frontend_dist
        try:
            static_path.relative_to(_frontend_dist.resolve())
        except ValueError:
            # Path escapes the frontend build root — never serve, return 404
            raise HTTPException(status_code=404)

        if static_path.is_file():
            return FileResponse(static_path)

        # 2. SPA fallback — serve index.html for frontend routes
        # Only fall back for paths that don't escape the build root
        if not path_to_check.startswith("api/"):
            index_path = _frontend_dist.joinpath("index.html").resolve()
            if index_path.is_file():
                return FileResponse(index_path)

        # Should not reach here, but fallback clearly
        raise HTTPException(status_code=404, detail="Angular app not built")

    return app


# Uvicorn CLI entrypoint: `uvicorn shorts_creator.web.app:app`.
# No pool/repository is created at import; wiring happens on startup.
app = create_app()