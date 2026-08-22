"""Preview / download MP4 routes.

Both resolve the canonical ``data/videos/<uuid>/video.mp4`` internally from
the validated job identity; never accept a path/filename from the client.
Download sends a safe backend-generated presentation filename.
"""

from __future__ import annotations

import uuid as _uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse

from shorts_creator.web.exceptions import (
    JobNotFoundError,
    JobVideoUnavailableError,
)
from shorts_creator.web.service import JobService

router = APIRouter()


def _service(request: Request) -> JobService:
    return request.app.state.service


@router.get("/jobs/{job_id}/video")
def get_video(job_id: str, service: JobService = Depends(_service)) -> FileResponse:
    return _file_response_for(job_id, service, attachment=False)


@router.get("/jobs/{job_id}/download")
def download_video(job_id: str, service: JobService = Depends(_service)) -> FileResponse:
    return _file_response_for(job_id, service, attachment=True)


def _file_response_for(job_id: str, service: JobService, *, attachment: bool) -> FileResponse:
    try:
        path = service.get_video_path(job_id)
    except JobNotFoundError:
        raise
    except JobVideoUnavailableError:
        raise
    # service.get_video_path raises JobVideoUnavailableError for no video;
    # missing web-job -> JobNotFoundError. Both surface sanely.
    vid = _uuid.UUID(job_id)
    short = str(vid)[:8]
    headers = {}
    if attachment:
        headers["Content-Disposition"] = f'attachment; filename="video-{short}.mp4"'
    return FileResponse(
        path=path,
        media_type="video/mp4",
        headers=headers,
    )