"""Temporary compatibility facade for the canonical VisualPlan V2 contract."""

from _package_bootstrap import ensure_src_on_path

ensure_src_on_path()

from shorts_creator.contracts.visual import (
    ALLOWED_ASSET_PREFERENCES,
    ALLOWED_PROVIDERS,
    ALLOWED_TRANSITIONS,
    ALLOWED_VISUAL_INTENTS,
    ALL_KNOWN_FIELDS,
    ALL_KNOWN_SEGMENT_FIELDS,
    LEGACY_V1_FIELDS,
    OPTIONAL_DEFAULTS,
    OPTIONAL_SEGMENT_DEFAULTS,
    PROVIDER_ALIASES,
    REQUIRED_FIELDS,
    REQUIRED_SEGMENT_FIELDS,
    SCHEMA_VERSION,
    STRING_FIELD_MAX,
    canonicalize_visual_plan_v2,
    validate_visual_plan_v2,
)

__all__ = [
    "ALLOWED_ASSET_PREFERENCES",
    "ALLOWED_PROVIDERS",
    "ALLOWED_TRANSITIONS",
    "ALLOWED_VISUAL_INTENTS",
    "ALL_KNOWN_FIELDS",
    "ALL_KNOWN_SEGMENT_FIELDS",
    "LEGACY_V1_FIELDS",
    "OPTIONAL_DEFAULTS",
    "OPTIONAL_SEGMENT_DEFAULTS",
    "PROVIDER_ALIASES",
    "REQUIRED_FIELDS",
    "REQUIRED_SEGMENT_FIELDS",
    "SCHEMA_VERSION",
    "STRING_FIELD_MAX",
    "canonicalize_visual_plan_v2",
    "validate_visual_plan_v2",
]
