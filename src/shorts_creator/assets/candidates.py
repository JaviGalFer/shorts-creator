"""Pure candidate contracts used before a visual asset is selected."""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from shorts_creator.assets.capabilities import SOURCE_TYPES
from shorts_creator.contracts.visual_media import MEDIA_KINDS

RAW = "RAW"
ADAPTED = "ADAPTED"
QUERY_VARIANTS: frozenset[str] = frozenset({RAW, ADAPTED})

METADATA_REJECTED = "METADATA_REJECTED"
DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
PIXEL_REJECTED = "PIXEL_REJECTED"
ACCEPTED = "ACCEPTED"
CANDIDATE_ATTEMPT_STATUSES: frozenset[str] = frozenset({
    METADATA_REJECTED, DOWNLOAD_FAILED, PIXEL_REJECTED, ACCEPTED,
})

SELECTED = "SELECTED"
EXHAUSTED = "EXHAUSTED"
SELECTION_RESULT_STATUSES: frozenset[str] = frozenset({SELECTED, EXHAUSTED})


def _optional_string(value: str | None, field: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise ValueError(f"INVALID_{field}: expected string or None")
    return value


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze_value(item) for item in value)
    return value


def _freeze_assessment(value: Mapping[str, Any] | None, field: str) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError(f"INVALID_{field}: expected mapping or None")
    return _freeze_value(value)


@dataclass(frozen=True)
class CandidateSemanticMetadata:
    title: str | None = None
    description: str | None = None
    tags: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()
    asset_type: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", _optional_string(self.title, "TITLE"))
        object.__setattr__(self, "description", _optional_string(self.description, "DESCRIPTION"))
        object.__setattr__(self, "asset_type", _optional_string(self.asset_type, "ASSET_TYPE"))
        for field in ("tags", "labels"):
            values = getattr(self, field)
            if not isinstance(values, (list, tuple)) or any(not isinstance(v, str) for v in values):
                raise ValueError(f"INVALID_{field.upper()}: expected strings")
            object.__setattr__(self, field, tuple(values))


@dataclass(frozen=True)
class CandidateAttribution:
    author: str | None = None
    license: str | None = None
    license_url: str | None = None

    def __post_init__(self) -> None:
        for field in ("author", "license", "license_url"):
            object.__setattr__(self, field, _optional_string(getattr(self, field), field.upper()))


@dataclass(frozen=True)
class CandidateEnvelope:
    capability_id: str | None
    provider: str | None
    provider_asset_id: str | None
    media_kind: str
    source_type: str
    query_used: str | None
    query_variant: str | None
    query_index: int | None
    provider_rank: int | None
    provider_score: float | None
    semantic_metadata: CandidateSemanticMetadata
    source_url: str | None
    preview_url: str | None
    acquisition_url: str | None
    mime_type: str | None
    width: int | None
    height: int | None
    attribution: CandidateAttribution

    def __post_init__(self) -> None:
        if self.media_kind not in MEDIA_KINDS:
            raise ValueError(f"INVALID_MEDIA_KIND: {self.media_kind!r}")
        if self.source_type not in SOURCE_TYPES:
            raise ValueError(f"INVALID_SOURCE_TYPE: {self.source_type!r}")
        if self.source_type == "STOCK":
            if not self.provider or not self.capability_id:
                raise ValueError("STOCK_CANDIDATE_REQUIRES_PROVIDER_AND_CAPABILITY")
        if self.query_variant is not None and self.query_variant not in QUERY_VARIANTS:
            raise ValueError(f"INVALID_QUERY_VARIANT: {self.query_variant!r}")
        if self.query_index is not None and (
            isinstance(self.query_index, bool) or not isinstance(self.query_index, int) or self.query_index < 0
        ):
            raise ValueError("INVALID_QUERY_INDEX")
        if self.provider_rank is not None and (
            isinstance(self.provider_rank, bool) or not isinstance(self.provider_rank, int) or self.provider_rank <= 0
        ):
            raise ValueError("INVALID_PROVIDER_RANK")
        if self.provider_score is not None and (
            isinstance(self.provider_score, bool)
            or not isinstance(self.provider_score, (int, float))
            or not math.isfinite(self.provider_score)
        ):
            raise ValueError("INVALID_PROVIDER_SCORE")
        for field in ("width", "height"):
            value = getattr(self, field)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value <= 0
            ):
                raise ValueError(f"INVALID_{field.upper()}")
        for field in (
            "capability_id", "provider", "provider_asset_id", "query_used",
            "source_url", "preview_url", "acquisition_url", "mime_type",
        ):
            object.__setattr__(self, field, _optional_string(getattr(self, field), field.upper()))
        if not isinstance(self.semantic_metadata, CandidateSemanticMetadata):
            raise ValueError("INVALID_SEMANTIC_METADATA")
        if not isinstance(self.attribution, CandidateAttribution):
            raise ValueError("INVALID_ATTRIBUTION")


@dataclass(frozen=True)
class CandidateAttempt:
    candidate: CandidateEnvelope
    status: str
    semantic_assessment: Mapping[str, Any] | None = None
    visual_fidelity_assessment: Mapping[str, Any] | None = None
    local_path: str | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, CandidateEnvelope):
            raise ValueError("INVALID_CANDIDATE")
        if self.status not in CANDIDATE_ATTEMPT_STATUSES:
            raise ValueError(f"INVALID_CANDIDATE_ATTEMPT_STATUS: {self.status!r}")
        object.__setattr__(
            self, "semantic_assessment", _freeze_assessment(self.semantic_assessment, "SEMANTIC_ASSESSMENT")
        )
        object.__setattr__(
            self, "visual_fidelity_assessment", _freeze_assessment(
                self.visual_fidelity_assessment, "VISUAL_FIDELITY_ASSESSMENT"
            )
        )
        object.__setattr__(self, "local_path", _optional_string(self.local_path, "LOCAL_PATH"))
        object.__setattr__(self, "error_code", _optional_string(self.error_code, "ERROR_CODE"))


@dataclass(frozen=True)
class CandidateSelectionResult:
    status: str
    selected: CandidateAttempt | None
    attempts: tuple[CandidateAttempt, ...]

    def __post_init__(self) -> None:
        if self.status not in SELECTION_RESULT_STATUSES:
            raise ValueError(f"INVALID_SELECTION_RESULT_STATUS: {self.status!r}")
        if not isinstance(self.attempts, (list, tuple)) or any(
            not isinstance(attempt, CandidateAttempt) for attempt in self.attempts
        ):
            raise ValueError("INVALID_CANDIDATE_ATTEMPTS")
        attempts = tuple(self.attempts)
        object.__setattr__(self, "attempts", attempts)
        if self.status == SELECTED:
            if self.selected is None or self.selected.status != ACCEPTED or self.selected not in attempts:
                raise ValueError("INVALID_SELECTED_CANDIDATE")
        elif self.selected is not None:
            raise ValueError("EXHAUSTED_SELECTION_MUST_NOT_HAVE_SELECTED_CANDIDATE")


def take_top_n(
    candidates: Sequence[CandidateEnvelope],
    limit: int,
) -> tuple[CandidateEnvelope, ...]:
    """Return the first N candidates in discovery order without re-ranking."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("INVALID_CANDIDATE_LIMIT")
    if any(not isinstance(candidate, CandidateEnvelope) for candidate in candidates):
        raise ValueError("INVALID_CANDIDATE_ENVELOPE")
    return tuple(candidates[:limit])
