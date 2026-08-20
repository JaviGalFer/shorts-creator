"""Health and capabilities routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from shorts_creator.web.capabilities import build_capabilities
from shorts_creator.web.dto import CapabilitiesResponse, HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities() -> CapabilitiesResponse:
    return build_capabilities()