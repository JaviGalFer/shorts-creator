"""LocalJobExecutor lifecycle, admission and reconciliation tests."""

import threading
import time
import uuid

import pytest

from shorts_creator.web.dto import JobCreate
from shorts_creator.web.exceptions import JobExecutionBusyError
from shorts_creator.web.executor import LocalJobExecutor, MAX_ACTIVE, MAX_QUEUED
from shorts_creator.web.repository import FilesystemJobRepository


def _uid():
    return str(uuid.uuid4())


# ── lifecycle / wite ─────────────────────────────────────────────────────────


def test_lifespan_wires_production_and_shuts_down(tmp_path, monkeypatch):
    """create_app() (no injected service) must build inside lifespan: reconcile
    once on startup, shutdown the executor on exit, and create no pool at import.
    """
    from fastapi.testclient import TestClient

    from shorts_creator.web import dependencies
    from shorts_creator.web.app import create_app
    from shorts_creator.web.service import JobService

    # Point production wiring at a temp videos root (no touched data/).
    tmp_videos = tmp_path / "videos"
    tmp_videos.mkdir()

    built = {"count": 0}
    executor_box = {}

    real_build = dependencies.build_service

    def fake_build():
        built["count"] += 1
        repo = FilesystemJobRepository(tmp_videos)
        ex = _RecordingExecutor(repo)
        executor_box["ex"] = ex
        return repo, ex, JobService(repo, ex)

    monkeypatch.setattr(dependencies, "build_service", fake_build)

    app = create_app()
    assert built["count"] == 0  # not built at import time
    with TestClient(app) as c:
        assert built["count"] == 1  # built once inside lifespan startup
        assert executor_box["ex"].calls_reconcile == 1  # reconcile once at startup
        c.get("/api/v1/health")
    assert executor_box["ex"].calls_shutdown == 1  # executor.shutdown() on lifespan exit


def test_lifespan_shuts_down_executor_on_exception(tmp_path, monkeypatch):
    """executor.shutdown() must run even if an exception propagates through the
    lifespan body, via try/finally around the yield.
    """
    import asyncio
    from types import SimpleNamespace

    from shorts_creator.web import dependencies
    from shorts_creator.web.app import _make_lifespan
    from shorts_creator.web.service import JobService

    tmp_videos = tmp_path / "videos"
    tmp_videos.mkdir()

    executor_box = {}

    def fake_build():
        repo = FilesystemJobRepository(tmp_videos)
        ex = _RecordingExecutor(repo)
        executor_box["ex"] = ex
        return repo, ex, JobService(repo, ex)

    monkeypatch.setattr(dependencies, "build_service", fake_build)

    lifespan = _make_lifespan(None)
    app = SimpleNamespace(state=SimpleNamespace())

    async def drive():
        try:
            async with lifespan(app):  # startup: build + reconcile
                raise RuntimeError("boom in request flow")
        except RuntimeError:
            pass  # expected: body raised; teardown (finally) must still run
        return executor_box["ex"]

    ex = asyncio.run(drive())
    assert ex.calls_reconcile == 1
    assert ex.calls_shutdown == 1  # finally ensured shutdown despite the runtime error


class _RecordingExecutor(LocalJobExecutor):
    def __init__(self, repo=None):
        self.calls_reconcile = 0
        self.calls_shutdown = 0
        super().__init__(repo=repo)

    def reconcile_stale(self, stale_ids):
        self.calls_reconcile += 1
        return super().reconcile_stale(stale_ids)

    def shutdown(self):
        self.calls_shutdown += 1
        return super().shutdown()


def test_job_dir_rejects_path_separators(tmp_path):
    from shorts_creator.web.exceptions import InvalidJobIdError

    repo = FilesystemJobRepository(tmp_path / "videos")
    for bad in ("../escape", "a/b", "a\\b", "/abs"):
        with pytest.raises(InvalidJobIdError):
            repo._job_dir(bad)


def test_videos_root_missing_lists_empty(tmp_path):
    repo = FilesystemJobRepository(tmp_path / "videos")
    assert repo.list_web_job_ids() == []