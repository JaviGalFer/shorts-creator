"""JobExecutor abstraction and in-process LocalJobExecutor.

The executor invokes the canonical ``run_pipeline`` directly in a worker
thread. MVP uses a single active worker (``max_workers=1``) with bounded
admission: one active job plus one queued slot. Further submissions raise
``JobExecutionBusyError`` (job concurrency/admission — NOT HTTP rate
limiting).

The pipeline results are read from the canonical ``metadata.json``; web
``executionState == FINISHED`` maps to ``run_pipeline() == 0`` (a
``REVIEW_REQUIRED``/``ASSETS_PARTIAL`` result is still FINISHED), while a
non-zero return or an uncaught exception maps to FAILED.
"""

from __future__ import annotations

import logging
import threading
import uuid
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from shorts_creator.web.exceptions import JobExecutionBusyError
from shorts_creator.web.repository import WebJob, utcnow_iso

logger = logging.getLogger(__name__)

MAX_ACTIVE = 1
MAX_QUEUED = 1


class JobExecutor(ABC):
    @abstractmethod
    def submit(self, job: WebJob) -> None:
        ...

    @abstractmethod
    def active_count(self) -> int:
        ...

    @abstractmethod
    def shutdown(self) -> None:
        ...


@dataclass
class _QueuedJob:
    job: WebJob


@dataclass
class LocalJobExecutor(JobExecutor):
    """In-process single-active-worker executor with bounded admission.

    ``run_pipeline_fn`` is injectable so tests never invoke the real
    pipeline/LLM. Defaults to the canonical orchestrator.
    """

    videos_root: Any = None
    run_pipeline_fn: Callable[..., int] | None = None
    repo: Any = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _active: WebJob | None = None
    _queued: list[WebJob] = field(default_factory=list)
    _pool: ThreadPoolExecutor | None = None
    _shutdown: bool = False

    def __post_init__(self) -> None:
        if self._pool is None:
            object.__setattr__(self, "_pool", ThreadPoolExecutor(max_workers=MAX_ACTIVE))
        if self.run_pipeline_fn is None:
            from shorts_creator.pipeline.orchestrator import run_pipeline

            object.__setattr__(self, "run_pipeline_fn", run_pipeline)
        # Avoid mutating the frozen default lists across instances.
        object.__setattr__(self, "_queued", [])

    # ── admission ───────────────────────────────────────────────────────

    def submit(self, job: WebJob) -> None:
        with self._lock:
            if self._shutdown:
                raise JobExecutionBusyError(
                    message="Job executor is shutting down."
                )
            if self._active is not None and len(self._queued) >= MAX_QUEUED:
                raise JobExecutionBusyError(
                    message="Job executor is busy (active + queued limit reached)."
                )
            if self._active is None:
                self._active = job
                self._start(job)
            else:
                self._queued.append(job)

    def active_count(self) -> int:
        with self._lock:
            count = 0
            if self._active is not None:
                count += 1
            return count + len(self._queued)

    def _start(self, job: WebJob) -> None:
        if self._pool is None:
            raise JobExecutionBusyError(message="Job executor is not running.")
        self._pool.submit(self._run, job)

    def _run(self, job: WebJob) -> None:
        try:
            self._set_state(job, "RUNNING")
            returncode = self._call_pipeline(job)
            if returncode == 0:
                self._set_state(job, "FINISHED")
            else:
                self._set_state(job, "FAILED", error_code="EXECUTION_FAILED")
        except Exception as exc:  # noqa: BLE001
            logger.warning("job %s pipeline failed: %s", job.job_id, exc)
            self._set_state(job, "FAILED", error_code="EXECUTION_FAILED")
        finally:
            self._complete(job)

    def _call_pipeline(self, job: WebJob) -> int:
        request = job.create_request or {}
        kwargs = _build_pipeline_kwargs(request)
        kwargs["job_id"] = job.job_id
        kwargs["stop_after"] = "validate"
        fn = self.run_pipeline_fn
        return int(fn(**kwargs))

    def _set_state(
        self,
        job: WebJob,
        state: str,
        *,
        error_code: str | None = None,
    ) -> None:
        now = utcnow_iso()
        if state == "RUNNING":
            job.started_at = job.started_at or now
        elif state in ("FINISHED", "FAILED", "INTERRUPTED"):
            job.finished_at = job.finished_at or now
        job.execution_state = state
        if error_code is not None:
            job.error_code = error_code
        if self.repo is not None:
            self.repo.update(job)

    def _complete(self, job: WebJob) -> None:
        with self._lock:
            if self._active is not None and self._active.job_id == job.job_id:
                self._active = None
            if self._queued:
                next_job = self._queued.pop(0)
                self._active = next_job
                # Mark queued->running out of the lock-safe path; _setup_state
                # is cheap and idempotent.
                self._set_state(next_job, "RUNNING")
                if self._pool is not None:
                    self._pool.submit(self._run, next_job)

    def reconcile_stale(self, stale_ids: list[str]) -> None:
        """Mark persisted QUEUED/RUNNING jobs with no live executor as INTERRUPTED."""
        if self.repo is None:
            return
        for job_id in stale_ids:
            try:
                job = self.repo.get(job_id)
            except Exception:  # noqa: BLE001
                continue
            if job.execution_state in ("QUEUED", "RUNNING"):
                self._set_state(job, "INTERRUPTED")

    def shutdown(self) -> None:
        with self._lock:
            self._shutdown = True
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=False)


def _build_pipeline_kwargs(request: dict) -> dict[str, Any]:
    """Map a stored createRequest onto canonical run_pipeline kwargs."""
    kwargs: dict[str, Any] = {"topic": request.get("topic", "")}

    preset = request.get("duration_preset")
    seconds = request.get("duration_seconds")
    if preset is not None:
        kwargs["duration_preset"] = preset
    elif seconds is not None:
        kwargs["duration"] = int(seconds)

    kwargs["tts_provider"] = request.get("tts_provider")
    kwargs["voice"] = request.get("voice")

    visual_mode = request.get("visual_mode")
    if visual_mode is not None:
        kwargs["visual_mode"] = visual_mode.lower().replace("_", "-")

    providers = request.get("asset_providers")
    if providers:
        kwargs["asset_providers"] = ",".join(providers)

    return kwargs