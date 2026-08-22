"""JobService — orchestration of the web job lifecycle.

Single authority for "which jobs the caller can see" (future ownership hook
inserts here) and for translating a validated create request into canonical
``run_pipeline`` invocation via the executor. No raw metadata escapes here.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from shorts_creator.web.dto import JobCreate, JobResponse
from shorts_creator.web.exceptions import (
    ApplicationError,
    InvalidJobIdError,
    InvalidJobRequestError,
    JobExecutionBusyError,
    JobVideoUnavailableError,
)
from shorts_creator.web.executor import JobExecutor
from shorts_creator.web.projection import project_job
from shorts_creator.web.repository import JobRepository, WebJob

_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def validate_uuid4(job_id: str) -> str:
    """Validate an HTTP job id is a version-4 UUID.

    Strict: shape regex plus ``uuid.UUID(...).version == 4``. Raises
    ``InvalidJobIdError`` otherwise.
    """
    if not isinstance(job_id, str) or not _UUID4_RE.match(job_id):
        raise InvalidJobIdError(message="Job id must be a version-4 UUID.")
    try:
        parsed = uuid.UUID(job_id)
    except (ValueError, AttributeError) as exc:
        raise InvalidJobIdError(message="Job id must be a version-4 UUID.") from exc
    if parsed.version != 4:
        raise InvalidJobIdError(message="Job id must be a version-4 UUID.")
    return job_id.lower()


class JobService:
    def __init__(self, repository: JobRepository, executor: JobExecutor):
        self._repository = repository
        self._executor = executor

    # ── create ──────────────────────────────────────────────────────────

    def create_job(self, request: JobCreate) -> JobResponse:
        self._validate_create(request)
        job_id = str(uuid.uuid4())
        try:
            web_job = self._repository.create(job_id, request)
        except ApplicationError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise InvalidJobRequestError(
                message="Could not create job."
            ) from exc

        try:
            self._executor.submit(web_job)
        except JobExecutionBusyError as exc:
            # Clean up the sidecar so a busy rejection leaves no orphan job.
            try:
                self._repository.update(WebJob(
                    job_id=job_id,
                    execution_state="INTERRUPTED",
                    created_at=web_job.created_at,
                ))
            except Exception:  # noqa: BLE001
                pass
            raise

        return self._project(web_job)

    def _validate_create(self, request: JobCreate) -> None:
        if request.duration_preset is not None and request.duration_seconds is not None:
            raise InvalidJobRequestError(
                message="durationPreset and durationSeconds are mutually exclusive."
            )

    # ── read ────────────────────────────────────────────────────────────

    def get_job(self, job_id: str) -> JobResponse:
        job_id = validate_uuid4(job_id)
        web_job = self._repository.get(job_id)
        return self._project(web_job)

    def list_jobs(self) -> list[JobResponse]:
        ids = self._repository.list_web_job_ids()
        responses = []
        for job_id in ids:
            try:
                web_job = self._repository.get(job_id)
                responses.append(self._project(web_job))
            except (JobNotFoundError, ApplicationError):
                continue
        responses.sort(key=lambda r: r.created_at or "", reverse=True)
        return responses

    def get_video_path(self, job_id: str) -> str:
        job_id = validate_uuid4(job_id)
        web_job = self._repository.get(job_id)
        path = self._repository.resolve_video_path(job_id)
        if path is None or not path.is_file():
            raise JobVideoUnavailableError(message="Job video is not available.")
        return str(path)

    # ── internal ────────────────────────────────────────────────────────

    def _project(self, web_job: WebJob) -> JobResponse:
        metadata = self._repository.load_metadata(web_job.job_id)
        video = self._repository.resolve_video_path(web_job.job_id)
        return project_job(
            web_job,
            metadata,
            has_video=video is not None and video.is_file(),
        )

    # expose helpers
    @property
    def repository(self) -> JobRepository:
        return self._repository

    @property
    def executor(self) -> JobExecutor:
        return self._executor