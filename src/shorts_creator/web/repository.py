"""JobRepository abstraction and filesystem-backed implementation.

Only Web-managed jobs (directories containing a ``web-job.json`` sidecar)
are visible to the web API. This intentionally hides historical CLI and
evaluation jobs under ``data/videos/``.

``metadata.json`` remains canonical pipeline-owned state; ``web-job.json``
is the minimal Web execution lifecycle sidecar and is written atomically.
"""

from __future__ import annotations

import json
import os
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from shorts_creator.web.dto import JobCreate
from shorts_creator.web.exceptions import (
    InternalStorageError,
    InvalidJobIdError,
    JobNotFoundError,
)

WEB_JOB_FILE = "web-job.json"
_VIDEO_FILE = "video.mp4"

TERMINAL_EXECUTION_STATES = frozenset({"FINISHED", "FAILED", "INTERRUPTED"})


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


@dataclass
class WebJob:
    """In-memory representation of the web execution sidecar."""

    job_id: str
    execution_state: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error_code: str | None = None
    create_request: dict | None = None

    def to_dict(self) -> dict:
        return {
            "jobId": self.job_id,
            "executionState": self.execution_state,
            "createdAt": self.created_at,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "errorCode": self.error_code,
            "createRequest": self.create_request,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WebJob":
        return cls(
            job_id=str(data.get("jobId", "")),
            execution_state=str(data.get("executionState", "QUEUED")),
            created_at=str(data.get("createdAt") or utcnow_iso()),
            started_at=data.get("startedAt"),
            finished_at=data.get("finishedAt"),
            error_code=data.get("errorCode"),
            create_request=data.get("createRequest"),
        )


def atomic_write_json(path: Path, data: dict) -> None:
    """Write a JSON file atomically via temp file + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except OSError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


class JobRepository(ABC):
    @abstractmethod
    def create(self, job_id: str, request: JobCreate) -> WebJob:
        ...

    @abstractmethod
    def get(self, job_id: str) -> WebJob:
        ...

    @abstractmethod
    def update(self, job: WebJob) -> WebJob:
        ...

    @abstractmethod
    def list_web_job_ids(self) -> list[str]:
        ...

    @abstractmethod
    def load_metadata(self, job_id: str) -> dict:
        ...

    @abstractmethod
    def resolve_video_path(self, job_id: str) -> Path | None:
        ...


class FilesystemJobRepository(JobRepository):
    """Web execution state persisted as per-job ``web-job.json`` sidecars."""

    def __init__(self, videos_root: Path):
        self._videos_root = videos_root

    # ── path helpers ────────────────────────────────────────────────────

    def _job_dir(self, job_id: str) -> Path:
        if not job_id:
            raise InvalidJobIdError(message="job id is empty")
        if "/" in job_id or "\\" in job_id or ".." in job_id:
            raise InvalidJobIdError(message="job id must not contain path separators")
        return self._videos_root / job_id

    def _sidecar_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / WEB_JOB_FILE

    def _is_web_job_dir(self, dir_path: Path) -> bool:
        try:
            return (dir_path / WEB_JOB_FILE).is_file()
        except OSError:
            return False

    # ── CRUD ────────────────────────────────────────────────────────────

    def create(self, job_id: str, request: JobCreate) -> WebJob:
        try:
            job = WebJob(
                job_id=job_id,
                execution_state="QUEUED",
                created_at=utcnow_iso(),
                create_request=request.model_dump(
                    exclude_none=True, exclude={"topic": False}
                ),
            )
            path = self._sidecar_path(job_id)
            atomic_write_json(path, job.to_dict())
            return job
        except OSError as exc:
            raise InternalStorageError(message="Could not write job.") from exc

    def get(self, job_id: str) -> WebJob:
        path = self._sidecar_path(job_id)
        if not path.is_file():
            raise JobNotFoundError(message="Job not found.")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InternalStorageError(message="Job metadata is unreadable.") from exc
        if not isinstance(data, dict) or data.get("jobId") != job_id:
            raise JobNotFoundError(message="Job not found.")
        return WebJob.from_dict(data)

    def update(self, job: WebJob) -> WebJob:
        try:
            atomic_write_json(self._sidecar_path(job.job_id), job.to_dict())
        except OSError as exc:
            raise InternalStorageError(message="Could not update job.") from exc
        return job

    def list_web_job_ids(self) -> list[str]:
        if not self._videos_root.is_dir():
            return []
        ids = []
        try:
            for child in self._videos_root.iterdir():
                if not child.is_dir():
                    continue
                if self._is_web_job_dir(child):
                    ids.append(child.name)
        except OSError:
            raise InternalStorageError(message="Could not list jobs.") from None
        return sorted(ids)

    def load_metadata(self, job_id: str) -> dict:
        path = self._job_dir(job_id) / "metadata.json"
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def resolve_video_path(self, job_id: str) -> Path | None:
        path = self._job_dir(job_id) / _VIDEO_FILE
        return path if path.is_file() else None