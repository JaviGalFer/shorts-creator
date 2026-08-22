"""Slice 1/2: Web-managed job repository tests.

The FilesystemJobRepository must: recognize only Web-managed jobs
(a web-job.json sidecar), write web-job.json atomically, handle malformed
job files safely, resolve the canonical video, and expose no path traversal.
"""

import json
import os
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from shorts_creator.web.dto import JobCreate
from shorts_creator.web.exceptions import JobNotFoundError
from shorts_creator.web.repository import FilesystemJobRepository


def _uid() -> str:
    return str(uuid.uuid4())


def _make_request(**overrides):
    data = {
        "topic": "Tema",
        "visual_mode": "AUTO",
        "asset_providers": ["wikimedia_commons"],
    }
    data.update(overrides)
    return JobCreate(**data)


def _repo(tmp_path) -> FilesystemJobRepository:
    return FilesystemJobRepository(tmp_path / "videos")


def _write_sidecar(dir_path: Path, job_id: str, state="QUEUED"):
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "web-job.json").write_text(
        json.dumps(
            {"jobId": job_id, "executionState": state, "createdAt": "2026-08-20T00:00:00.000Z"}
        )
    )


# ── Web-managed only ────────────────────────────────────────────────────────


def test_list_only_recognizes_web_managed_jobs(tmp_path):
    repo = _repo(tmp_path)
    web_id = _uid()
    _write_sidecar(tmp_path / "videos" / web_id, web_id)
    # Historical CLI job: directory without web-job.json must be hidden.
    (tmp_path / "videos" / "legacy-cli-job").mkdir(parents=True)
    (tmp_path / "videos" / "legacy-cli-job" / "metadata.json").write_text("{}")
    # A loose file (not a dir) must be ignored.
    (tmp_path / "videos" / "somefile.json").write_text("{}")

    assert repo.list_web_job_ids() == [web_id]


# ── Atomic write ────────────────────────────────────────────────────────────


def test_create_writes_atomic_web_job(tmp_path):
    repo = _repo(tmp_path)
    job_id = _uid()
    created = repo.create(job_id, _make_request())
    assert created.execution_state == "QUEUED"
    path = tmp_path / "videos" / job_id / "web-job.json"
    assert path.is_file()
    data = json.loads(path.read_text())
    assert data["jobId"] == job_id
    assert data["executionState"] == "QUEUED"
    # No temp leftovers after atomic replace.
    leftovers = [p.name for p in path.parent.iterdir() if p.name.startswith(".tmp-")]
    assert leftovers == []


def test_update_preserves_fields(tmp_path):
    repo = _repo(tmp_path)
    job_id = _uid()
    job = repo.create(job_id, _make_request())
    job.execution_state = "RUNNING"
    repo.update(job)
    loaded = repo.get(job_id)
    assert loaded.execution_state == "RUNNING"
    assert loaded.job_id == job_id


# ── Malformed job files ─────────────────────────────────────────────────────


def test_get_missing_sidecar_raises_not_found(tmp_path):
    repo = _repo(tmp_path)
    with pytest.raises(JobNotFoundError):
        repo.get(_uid())


def test_get_malformed_sidecar_raises_storage_error(tmp_path):
    repo = _repo(tmp_path)
    job_id = _uid()
    d = tmp_path / "videos" / job_id
    d.mkdir(parents=True)
    (d / "web-job.json").write_text("{ not json")
    from shorts_creator.web.exceptions import InternalStorageError

    with pytest.raises(InternalStorageError):
        repo.get(job_id)


def test_list_skips_malformed_sidecar_without_crashing(tmp_path):
    repo = _repo(tmp_path)
    good = _uid()
    bad = _uid()
    _write_sidecar(tmp_path / "videos" / good, good)
    (tmp_path / "videos" / bad).mkdir(parents=True)
    (tmp_path / "videos" / bad / "web-job.json").write_text("{ broken")
    ids = repo.list_web_job_ids()
    assert good in ids
    assert bad in ids  # recognized as web-managed; get() will surface storage error


# ── Video resolution ────────────────────────────────────────────────────────


def test_resolve_video_returns_path_when_present(tmp_path):
    repo = _repo(tmp_path)
    job_id = _uid()
    _write_sidecar(tmp_path / "videos" / job_id, job_id)
    (tmp_path / "videos" / job_id / "video.mp4").write_bytes(b"data")
    path = repo.resolve_video_path(job_id)
    assert path is not None and path.is_file()


def test_resolve_video_returns_none_when_missing(tmp_path):
    repo = _repo(tmp_path)
    job_id = _uid()
    _write_sidecar(tmp_path / "videos" / job_id, job_id)
    assert repo.resolve_video_path(job_id) is None


# ── Path traversal surface ─────────────────────────────────────────────────


def test_job_dir_rejects_path_separators(tmp_path):
    repo = _repo(tmp_path)
    from shorts_creator.web.exceptions import InvalidJobIdError

    for bad in ("../escape", "a/b", "a\\b", "/abs"):
        with pytest.raises(InvalidJobIdError):
            repo._job_dir(bad)


def test_load_metadata_returns_empty_for_missing(tmp_path):
    repo = _repo(tmp_path)
    job_id = _uid()
    _write_sidecar(tmp_path / "videos" / job_id, job_id)
    assert repo.load_metadata(job_id) == {}


def test_load_metadata_returns_dict(tmp_path):
    repo = _repo(tmp_path)
    job_id = _uid()
    d = tmp_path / "videos" / job_id
    _write_sidecar(d, job_id)
    (d / "metadata.json").write_text(json.dumps({"jobId": job_id, "status": "VALIDATED"}))
    assert repo.load_metadata(job_id)["status"] == "VALIDATED"