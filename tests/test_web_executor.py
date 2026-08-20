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


def _make_request(**overrides):
    data = {"topic": "Tema", "visual_mode": "AUTO", "asset_providers": ["wikimedia_commons"]}
    data.update(overrides)
    return JobCreate(**data)


def _repo(tmp_path):
    return FilesystemJobRepository(tmp_path / "videos")


def _dummy_run_pipeline(**kwargs):
    return 0


class _Gated:
    """A run_pipeline stub that blocks until released, recording calls."""

    def __init__(self, rc=0):
        self.rc = rc
        self.calls = []
        self._started = threading.Event()
        self._release = threading.Event()

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        self._started.set()
        self._release.wait(timeout=5.0)
        return self.rc

    def wait_started(self, timeout=2.0):
        assert self._started.wait(timeout)

    def release(self):
        self._release.set()


def _wait_for_terminal(repo, job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = repo.get(job_id).execution_state
        if state in ("FINISHED", "FAILED", "INTERRUPTED"):
            return state
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not reach terminal state (got {repo.get(job_id).execution_state})")


# ── Happy path ──────────────────────────────────────────────────────────────


def test_success_marks_finished(tmp_path):
    repo = _repo(tmp_path)
    ex = LocalJobExecutor(repo=repo, run_pipeline_fn=_dummy_run_pipeline)
    job = repo.create(_uid(), _make_request())
    ex.submit(job)
    assert _wait_for_terminal(repo, job.job_id) == "FINISHED"
    ex.shutdown()


def test_run_receives_mapped_kwargs(tmp_path):
    repo = _repo(tmp_path)
    gated = _Gated()
    ex = LocalJobExecutor(repo=repo, run_pipeline_fn=gated)
    job = repo.create(_uid(), _make_request(visual_mode="VIDEOS_ONLY", asset_providers=["pexels"]))

    ex.submit(job)
    gated.wait_started()
    gated.release()
    _wait_for_terminal(repo, job.job_id)
    assert gated.calls
    first = gated.calls[0]
    assert first["job_id"] == job.job_id
    assert first["visual_mode"] == "videos-only"
    assert first["asset_providers"] == "pexels"
    ex.shutdown()


def test_failure_marks_failed(tmp_path):
    repo = _repo(tmp_path)

    def failing(**kwargs):
        return 1

    ex = LocalJobExecutor(repo=repo, run_pipeline_fn=failing)
    job = repo.create(_uid(), _make_request())
    ex.submit(job)
    assert _wait_for_terminal(repo, job.job_id) == "FAILED"
    ex.shutdown()


def test_exception_marks_failed(tmp_path):
    repo = _repo(tmp_path)

    def raising(**kwargs):
        raise RuntimeError("boom")

    ex = LocalJobExecutor(repo=repo, run_pipeline_fn=raising)
    job = repo.create(_uid(), _make_request())
    ex.submit(job)
    assert _wait_for_terminal(repo, job.job_id) == "FAILED"
    assert repo.get(job.job_id).error_code == "EXECUTION_FAILED"
    ex.shutdown()


# ── Admission / limits ──────────────────────────────────────────────────────


def test_busy_when_queue_full(tmp_path):
    repo = _repo(tmp_path)
    gated = _Gated()
    ex = LocalJobExecutor(repo=repo, run_pipeline_fn=gated)
    # Fill max_active (1) — must actually start to hold the slot.
    first = repo.create(_uid(), _make_request())
    ex.submit(first)
    gated.wait_started()
    # Fill max_queued (1)
    queued = repo.create(_uid(), _make_request())
    ex.submit(queued)
    # Next must be busy
    extra = repo.create(_uid(), _make_request())
    with pytest.raises(JobExecutionBusyError):
        ex.submit(extra)
    gated.release()
    ex.shutdown()


def test_limits_are_positive():
    assert MAX_ACTIVE >= 1
    assert MAX_QUEUED == 1


# ── Reconciliation ──────────────────────────────────────────────────────────


def test_reconcile_stale_marks_interrupted(tmp_path):
    repo = _repo(tmp_path)
    ex = LocalJobExecutor(repo=repo, run_pipeline_fn=_dummy_run_pipeline)
    stale_ids = []
    for state in ("QUEUED", "RUNNING"):
        jid = _uid()
        job = repo.create(jid, _make_request())
        job.execution_state = state
        repo.update(job)
        stale_ids.append(jid)
    ex.reconcile_stale(stale_ids)
    for jid in stale_ids:
        assert repo.get(jid).execution_state == "INTERRUPTED"
    ex.shutdown()


def test_reconcile_preserves_finished(tmp_path):
    repo = _repo(tmp_path)
    ex = LocalJobExecutor(repo=repo, run_pipeline_fn=_dummy_run_pipeline)
    jid = _uid()
    job = repo.create(jid, _make_request())
    job.execution_state = "FINISHED"
    repo.update(job)
    ex.reconcile_stale([jid])
    assert repo.get(jid).execution_state == "FINISHED"
    ex.shutdown()


def test_executor_uses_single_worker():
    assert MAX_ACTIVE == 1


def test_default_run_pipeline_is_orchestrator():
    ex = LocalJobExecutor(videos_root=None)
    assert ex.run_pipeline_fn.__module__ == "shorts_creator.pipeline.orchestrator"
    ex.shutdown()