"""Media route tests: preview (inline) and download of job MP4.

Verifies the routes return the MP4 via FileResponse, never accept client
paths, and expose backend-generated safe presentation names. Range requests
(206) exercise Starlette's built-in handling.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from shorts_creator.web.app import create_app
from shorts_creator.web.dto import JobCreate
from shorts_creator.web.executor import LocalJobExecutor
from shorts_creator.web.repository import FilesystemJobRepository
from shorts_creator.web.service import JobService


def _uid():
    return str(uuid.uuid4())


class _FastPipeline:
    def __call__(self, **kwargs):
        return 0


@pytest.fixture
def client(tmp_path):
    repo = FilesystemJobRepository(tmp_path / "videos")
    executor = LocalJobExecutor(repo=repo, run_pipeline_fn=_FastPipeline())
    service = JobService(repo, executor)
    app = create_app(service=service)
    c = TestClient(app)
    yield c
    c.close()
    executor.shutdown()


def _make_video_job(tmp_path, client, topic="Con video"):
    created = client.post("/api/v1/jobs", json={"topic": topic}).json()
    job_id = created["job_id"]
    # Simulate a rendered video on disk (post-pipeline artifact).
    video = tmp_path / "videos" / job_id / "video.mp4"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 1000)
    return job_id


# ── preview (inline) ────────────────────────────────────────────────────────


def test_get_video_inline(tmp_path, client):
    job_id = _make_video_job(tmp_path, client)
    resp = client.get(f"/api/v1/jobs/{job_id}/video")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("video/mp4")
    # inline: no attachment disposition
    assert "attachment" not in resp.headers.get("content-disposition", "")


def test_get_video_missing_404(tmp_path, client):
    created = client.post("/api/v1/jobs", json={"topic": "Sin video"}).json()
    resp = client.get(f"/api/v1/jobs/{created['job_id']}/video")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "JOB_VIDEO_UNAVAILABLE"


def test_get_video_unknown_job_404(client):
    resp = client.get(f"/api/v1/jobs/{_uid()}/video")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "JOB_NOT_FOUND"


def test_get_video_invalid_uuid_400(client):
    resp = client.get("/api/v1/jobs/bogus/video")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_JOB_ID"


# ── download (attachment) ───────────────────────────────────────────────────


def test_download_attachment(tmp_path, client):
    job_id = _make_video_job(tmp_path, client)
    resp = client.get(f"/api/v1/jobs/{job_id}/download")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("video/mp4")
    disp = resp.headers.get("content-disposition", "")
    assert "attachment" in disp
    # backend-generated safe filename (uuid short), never a client path
    assert disp.rstrip('"').endswith(".mp4")


# ── range (streaming/seek) ─────────────────────────────────────────────────


def test_video_range_supported(tmp_path, client):
    job_id = _make_video_job(tmp_path, client)
    resp = client.get(f"/api/v1/jobs/{job_id}/video", headers={"Range": "bytes=0-99"})
    # Starlette FileResponse supports Range natively (installed 1.6.0).
    # A valid single-range request MUST return 206 with the exact byte
    # window — a 200 fallback would break seek/streaming clients.
    assert resp.status_code == 206
    assert resp.content == b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 88
    assert len(resp.content) == 100
    assert resp.headers["content-range"] == "bytes 0-99/1012"
    assert resp.headers["accept-ranges"] == "bytes"


def test_client_path_never_accepted(client):
    from shorts_creator.web.service import validate_uuid4
    from shorts_creator.web.exceptions import InvalidJobIdError

    # Path-like / invalid inputs are rejected by UUID validation (400) and
    # never reach filesystem access. Multi-segment paths don't even match the
    # route (404). Either way, no file is served.
    for path in ("../etc/passwd", "/abs/path", "a/b"):
        resp = client.get(f"/api/v1/jobs/{path}/video")
        assert resp.status_code in (400, 404)
    # single-segment non-UUID -> 400 via validate_uuid4
    with pytest.raises(InvalidJobIdError):
        validate_uuid4("not-a-uuid")
    resp = client.get("/api/v1/jobs/not-a-uuid/video")
    assert resp.status_code == 400