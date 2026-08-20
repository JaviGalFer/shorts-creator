"""Job CRUD / polling routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from shorts_creator.web.dto import (
    JobCreate,
    JobListResponse,
    JobResponse,
)
from shorts_creator.web.service import JobService

router = APIRouter()


def _service(request: Request) -> JobService:
    return request.app.state.service


@router.post("/jobs", response_model=JobResponse, status_code=202)
def create_job(payload: JobCreate, service: JobService = Depends(_service)) -> JobResponse:
    return service.create_job(payload)


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(service: JobService = Depends(_service)) -> JobListResponse:
    return JobListResponse(jobs=service.list_jobs())


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, service: JobService = Depends(_service)) -> JobResponse:
    return service.get_job(job_id)