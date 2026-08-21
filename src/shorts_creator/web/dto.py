"""Web API request/response DTOs — strict allowlists.

Request DTOs accept only product fields (topic, duration, tts provider,
voice, visual mode, asset providers). Response DTOs expose only the
intentionally public projection of a job. All models forbid unknown
fields so a client can never smuggle a path/directory/filename anywhere.

No filesystem paths, raw metadata, env values, secrets, or subprocess
diagnostics are ever represented here.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── JobCreate request ────────────────────────────────────────────────────────


class VisualMode(str, Enum):
    AUTO = "AUTO"
    IMAGES_ONLY = "IMAGES_ONLY"
    VIDEOS_ONLY = "VIDEOS_ONLY"
    MIXED = "MIXED"


class TtsProvider(str, Enum):
    edge_tts = "edge_tts"
    elevenlabs = "elevenlabs"


class JobCreate(BaseModel):
    """Client-submitted create payload. Product fields only."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=500)
    duration_preset: str | None = None
    duration_seconds: int | None = Field(default=None, ge=1, le=300)
    tts_provider: TtsProvider | None = None
    voice: str | None = Field(default=None, max_length=200)
    visual_mode: VisualMode | None = None
    asset_providers: list[str] | None = None

    @field_validator("topic")
    @classmethod
    def _strip_topic(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("topic must not be blank")
        return value

    @field_validator("asset_providers")
    @classmethod
    def _clean_providers(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [p.strip().lower() for p in value if p.strip()]
        if not cleaned:
            raise ValueError("assetProviders must contain at least one provider")
        return cleaned


class JobResponse(BaseModel):
    """Public projection of one job. Allowlist only."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    execution_state: str
    pipeline_status: str | None = None
    current_stage: str | None = None
    last_completed_stage: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    has_video: bool = False
    warnings: list[str] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)


class JobListResponse(BaseModel):
    """Response for GET /api/v1/jobs."""

    model_config = ConfigDict(extra="forbid")

    jobs: list[JobResponse]


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str = "shorts-creator-web"
    status: str = "ok"


class ProviderCapabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    provider: str
    media_kind: str
    source_type: str
    query_strategy: str
    runtime_status: str
    requires_api_key: bool


class DurationPresetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    target_sec: int


class DurationCapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    presets: list[DurationPresetResponse]
    min_sec: int
    max_sec: int
    default: str


class TtsProviderCapabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    default: bool
    available: bool


class VoiceCapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str
    default: str
    elevenlabs_from_env: bool


class CapabilitiesResponse(BaseModel):
    """Derived from canonical runtime enums/contracts; never hardcoded."""

    model_config = ConfigDict(extra="forbid")

    visual_modes: list[str]
    media_preferences: list[str]
    asset_preferences: list[str]
    providers: list[ProviderCapabilityResponse]
    duration: DurationCapabilitiesResponse
    tts_providers: list[TtsProviderCapabilityResponse]
    voices: VoiceCapabilitiesResponse


# Re-export Any for caller convenience in a couple of API helpers.
__all__ = [
    "JobCreate",
    "JobResponse",
    "JobListResponse",
    "HealthResponse",
    "CapabilitiesResponse",
    "ProviderCapabilityResponse",
    "DurationPresetResponse",
    "DurationCapabilitiesResponse",
    "TtsProviderCapabilityResponse",
    "VoiceCapabilitiesResponse",
    "VisualMode",
    "TtsProvider",
    "Any",
]