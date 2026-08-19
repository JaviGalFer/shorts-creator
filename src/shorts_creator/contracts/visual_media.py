"""Pure media-strategy contracts for VisualPlan V2.

This module resolves user media policy and editorial preference only. It does
not query providers, inspect runtime availability, or route production assets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

IMAGE = "IMAGE"
VIDEO = "VIDEO"

AUTO = "AUTO"
IMAGES_ONLY = "IMAGES_ONLY"
VIDEOS_ONLY = "VIDEOS_ONLY"
MIXED = "MIXED"
ALLOWED_VISUAL_MODES: frozenset[str] = frozenset({
    AUTO, IMAGES_ONLY, VIDEOS_ONLY, MIXED,
})

IMAGE_PREFERRED = "IMAGE_PREFERRED"
VIDEO_PREFERRED = "VIDEO_PREFERRED"
EITHER = "EITHER"
ALLOWED_MEDIA_PREFERENCES: frozenset[str] = frozenset({
    IMAGE_PREFERRED, VIDEO_PREFERRED, EITHER,
})

MEDIA_PREFERENCE_OVERRIDDEN_BY_USER = "MEDIA_PREFERENCE_OVERRIDDEN_BY_USER"
MEDIA_PREFERENCE_UNAVAILABLE = "MEDIA_PREFERENCE_UNAVAILABLE"
MEDIA_PREFERENCE_UNSATISFIABLE_FOR_VISUAL_FORM = (
    "MEDIA_PREFERENCE_UNSATISFIABLE_FOR_VISUAL_FORM"
)
VISUAL_FORM_UNSUPPORTED_FOR_ALLOWED_MEDIA = (
    "VISUAL_FORM_UNSUPPORTED_FOR_ALLOWED_MEDIA"
)


@dataclass(frozen=True)
class VisualModePolicy:
    """Normalized request-level media restriction."""

    visual_mode: str
    allowed_kinds: tuple[str, ...]
    mixed_diversity_preferred: bool


@dataclass(frozen=True)
class MediaStrategyDecision:
    """Pure, auditable media decision for one visual segment."""

    visual_mode: str
    editorial_preference: str
    allowed_kinds: tuple[str, ...]
    resolved_kind: str | None
    preference_status: str
    degradations: tuple[str, ...]

    @property
    def unresolved(self) -> bool:
        return self.resolved_kind is None


def _canonical_enum(value: Any, *, allowed: frozenset[str], field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"INVALID_{field}: expected string")
    canonical = value.strip().upper()
    if canonical not in allowed:
        raise ValueError(f"INVALID_{field}: {value!r}")
    return canonical


def normalize_visual_mode(request_visuals: Mapping[str, Any] | None) -> VisualModePolicy:
    """Return the compatible effective media policy without mutating input.

    Historical jobs used ``mode: images``. Its absence, and absence of the new
    ``visualMode``, intentionally preserve the image-only contract.
    """
    visuals = request_visuals or {}
    if not isinstance(visuals, Mapping):
        raise ValueError("INVALID_REQUEST_VISUALS: expected mapping")

    raw_mode = visuals.get("mode")
    raw_visual_mode = visuals.get("visualMode")
    legacy_mode = None
    if raw_mode is not None:
        if not isinstance(raw_mode, str) or raw_mode.strip().lower() != "images":
            raise ValueError(f"INVALID_LEGACY_VISUAL_MODE: {raw_mode!r}")
        legacy_mode = IMAGES_ONLY

    explicit = None
    if raw_visual_mode is not None:
        explicit = _canonical_enum(
            raw_visual_mode, allowed=ALLOWED_VISUAL_MODES, field="VISUAL_MODE"
        )
    if explicit is not None and legacy_mode is not None and explicit != legacy_mode:
        raise ValueError(
            "VISUAL_MODE_CONFLICT: request.visuals.mode='images' conflicts with "
            f"request.visuals.visualMode={explicit!r}"
        )

    visual_mode = explicit or legacy_mode or IMAGES_ONLY
    if visual_mode == IMAGES_ONLY:
        allowed_kinds = (IMAGE,)
    elif visual_mode == VIDEOS_ONLY:
        allowed_kinds = (VIDEO,)
    else:
        allowed_kinds = (IMAGE, VIDEO)
    return VisualModePolicy(
        visual_mode=visual_mode,
        allowed_kinds=allowed_kinds,
        mixed_diversity_preferred=visual_mode == MIXED,
    )


def resolve_media_strategy(
    *,
    policy: VisualModePolicy,
    editorial_preference: str | None,
    supported_kinds: frozenset[str] | set[str] | tuple[str, ...],
) -> MediaStrategyDecision:
    """Resolve policy and editorial preference against form-supported media.

    ``supported_kinds`` is a pure capability/form input. A future router will
    derive it by intersecting registered provider capabilities, fit policy, and
    runtime availability. The resolver deliberately does not perform that I/O.
    """
    preference = (
        IMAGE_PREFERRED
        if editorial_preference is None
        else _canonical_enum(
            editorial_preference,
            allowed=ALLOWED_MEDIA_PREFERENCES,
            field="MEDIA_PREFERENCE",
        )
    )
    supported = frozenset(supported_kinds)
    invalid_kinds = supported - {IMAGE, VIDEO}
    if invalid_kinds:
        raise ValueError(f"INVALID_SUPPORTED_MEDIA_KINDS: {sorted(invalid_kinds)}")

    eligible = tuple(kind for kind in policy.allowed_kinds if kind in supported)
    if not eligible:
        return MediaStrategyDecision(
            visual_mode=policy.visual_mode,
            editorial_preference=preference,
            allowed_kinds=policy.allowed_kinds,
            resolved_kind=None,
            preference_status="UNRESOLVED",
            degradations=(VISUAL_FORM_UNSUPPORTED_FOR_ALLOWED_MEDIA,),
        )

    preferred_kind = {
        IMAGE_PREFERRED: IMAGE,
        VIDEO_PREFERRED: VIDEO,
    }.get(preference)
    if preferred_kind is None:
        return MediaStrategyDecision(
            visual_mode=policy.visual_mode,
            editorial_preference=preference,
            allowed_kinds=policy.allowed_kinds,
            resolved_kind=eligible[0],
            preference_status="EITHER",
            degradations=(),
        )
    if preferred_kind in eligible:
        return MediaStrategyDecision(
            visual_mode=policy.visual_mode,
            editorial_preference=preference,
            allowed_kinds=policy.allowed_kinds,
            resolved_kind=preferred_kind,
            preference_status="PREFERRED",
            degradations=(),
        )

    resolved_kind = eligible[0]
    if preferred_kind not in policy.allowed_kinds:
        degradation = MEDIA_PREFERENCE_OVERRIDDEN_BY_USER
        status = "OVERRIDDEN_BY_USER"
    elif preferred_kind not in supported:
        degradation = MEDIA_PREFERENCE_UNSATISFIABLE_FOR_VISUAL_FORM
        status = "FALLBACK_FOR_VISUAL_FORM"
    else:
        degradation = MEDIA_PREFERENCE_UNAVAILABLE
        status = "FALLBACK_UNAVAILABLE"
    return MediaStrategyDecision(
        visual_mode=policy.visual_mode,
        editorial_preference=preference,
        allowed_kinds=policy.allowed_kinds,
        resolved_kind=resolved_kind,
        preference_status=status,
        degradations=(degradation,),
    )
