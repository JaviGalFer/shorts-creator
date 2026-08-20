"""HTTP-level tests for the Job API (POST /jobs, GET /jobs).

Uses the test transport via a real FilesystemJobRepository pointed at a
temp dir and an injectable fake ``run_pipeline`` so no pipeline/LLM runs.
"""

import threading
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from shorts_creator.web.app import create_app
from shorts_creator.web.dto import JobCreate
from shorts_creator.web.executor import LocalJobExecutor, MAX_QUEUED
from shorts_creator.web.repository import FilesystemJobRepository
from shorts_creator.web.service import JobService


def _uid():
    return str(uuid.uuid4())


class _FakePipeline:
    """Blocks to keep a job RUNNING; releases on demand."""

    def __init__(self, rc=0):
        self.rc = rc
        self.calls = []
        self._release = threading.Event()

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        self._release.wait(timeout=10.0)
        return self.rc

    def release(self):
        self._release.set()


@pytest.fixture
def client(tmp_path):
    repo = FilesystemJobRepository(tmp_path / "videos")
    pipeline = _FakePipeline()
    executor = LocalJobExecutor(repo=repo, run_pipeline_fn=pipeline)
    service = JobService(repo, executor)
    app = create_app(service=service)
    app.state._pipeline = pipeline
    c = TestClient(app)
    yield c
    pipeline.release()
    c.close()
    executor.shutdown()


# ── POST /jobs ─────────────────────────────────────────────────────────────


def test_create_job_returns_accepted(client):
    resp = client.post("/api/v1/jobs", json={"topic": "Volcanes"})
    assert resp.status_code == 202
    body = resp.json()
    assert body["execution_state"] == "QUEUED" or body["execution_state"] == "RUNNING"
    assert uuid.UUID(body["job_id"]).version == 4
    assert body["pipeline_status"] is None


def test_create_job_rejects_members_names(client):
    resp = client.post(
        "/api/v1/jobs",
        json={
            "topic": "Tema",
            "duration_preset": "quick_30",
            "duration_seconds": 30,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_JOB_REQUEST"


def test_extraneous_field_rejected(client):
    resp = client.post("/api/v1/jobs", json={"topic": "T", "bogus": 1})
    assert resp.status_code == 422  # pydantic extra=forbid


def test_missing_topic_rejected(client):
    resp = client.post("/api/v1/jobs", json={})
    assert resp.status_code == 422


def test_list_jobs_empty(client):
    resp = client.get("/api/v1/jobs")
    assert resp.status_code == 200
    assert resp.json()["jobs"] == []


def test_list_jobs_lists_created(client):
    first = client.post("/api/v1/jobs", json={"topic": "Uno"}).json()
    second = client.post("/api/v1/jobs", json={"topic": "Dos"}).json()
    jobs = client.get("/api/v1/jobs").json()["jobs"]
    ids = {j["job_id"] for j in jobs}
    assert {first["job_id"], second["job_id"]} <= ids


def test_get_job_detail(client):
    created = client.post("/api/v1/jobs", json={"topic": "Detalle"}).json()
    job_id = created["job_id"]
    resp = client.get(f"/api/v1/jobs/{job_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == job_id
    assert body["execution_state"] in ("QUEUED", "RUNNING")


def test_get_unknown_job_404(client):
    resp = client.get(f"/api/v1/jobs/{_uid()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "JOB_NOT_FOUND"


def test_get_invalid_uuid_400(client):
    resp = client.get("/api/v1/jobs/not-a-uuid")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_JOB_ID"


def test_executor_busy_returns_409(client):
    # release handle from app state
    pipeline = client.app.state._pipeline
    first = client.post("/api/v1/jobs", json={"topic": "hold"}).json()
    # run it to RUNNING (single-works) then queue
    for _ in range(MAX_QUEUED):
        client.post("/api/v1/jobs", json={"topic": f"q{_}"})
    resp = client.post("/api/v1/jobs", json={"topic": "overflow"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "JOB_EXECUTION_BUSY"