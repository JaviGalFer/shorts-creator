"""VisualPlan v2 canonicalizer and validator.

Accepts neutral v2 visual plans, validates field types and cross-field
consistency, canonicalizes values, and returns structured diagnostics.

No I/O, no provider calls, no pipeline imports.
Never infers legacy v1 fields (editorialRole, strategy, etc.).
"""

from __future__ import annotations

from typing import Any

# ── Schema constants ────────────────────────────────────────────────────────

SCHEMA_VERSION = 2

ALLOWED_VISUAL_INTENTS: frozenset[str] = frozenset({
    "explain", "show", "compare", "contextualize", "immerse", "emphasize",
})

ALLOWED_ASSET_PREFERENCES: frozenset[str] = frozenset({
    "diagram", "illustration", "photograph", "painting",
    "archive", "map", "document", "stock", "generated",
})

ALLOWED_MEDIA_PREFERENCES: frozenset[str] = frozenset({
    "IMAGE_PREFERRED", "VIDEO_PREFERRED", "EITHER",
})

ALLOWED_TRANSITIONS: frozenset[str] = frozenset({"cut", "fade"})

ALLOWED_PROVIDERS: frozenset[str] = frozenset({
    "wikimedia_commons", "pexels", "pixabay", "freeai", "pollinations",
})

PROVIDER_ALIASES: dict[str, str] = {
    "wikimedia": "wikimedia_commons",
    "wikimediacommons": "wikimedia_commons",
}

REQUIRED_FIELDS: list[str] = [
    "_schemaVersion",
    "visualIntent",
    "subjects",
    "searchQueries",
    "assetPreferences",
    "visualSequence",
]

OPTIONAL_DEFAULTS: dict[str, Any] = {
    "period": None,
    "location": None,
    "allowGeneratedImage": False,
    "preferredProviders": [],
    "imageGenerationPrompt": None,
    "negativePrompt": None,
}

ALL_KNOWN_FIELDS: set[str] = set(REQUIRED_FIELDS) | set(OPTIONAL_DEFAULTS.keys())

LEGACY_V1_FIELDS: frozenset[str] = frozenset({
    "editorialRole",
    "visualTemporalIntent",
    "strategy",
    "primaryAssetType",
    "secondaryAssetType",
    "style",
    "mood",
    "licenseRequired",
    "visualImportance",
})

REQUIRED_SEGMENT_FIELDS: list[str] = [
    "segmentIndex",
    "assetPreference",
    "durationFraction",
]

OPTIONAL_SEGMENT_DEFAULTS: dict[str, Any] = {
    "searchQuery": None,
    "transition": "cut",
    "mediaPreference": "IMAGE_PREFERRED",
}

ALL_KNOWN_SEGMENT_FIELDS: set[str] = (
    set(REQUIRED_SEGMENT_FIELDS) | set(OPTIONAL_SEGMENT_DEFAULTS.keys())
)

STRING_FIELD_MAX: dict[str, int] = {
    "visualIntent": 100,
    "subjects": 500,
    "searchQueries": 200,
    "assetPreferences": 100,
    "period": 200,
    "location": 200,
    "preferredProviders": 100,
    "imageGenerationPrompt": 500,
    "negativePrompt": 200,
    "assetPreference": 100,
    "mediaPreference": 30,
    "searchQuery": 200,
    "transition": 20,
}

# ── Validation helpers ──────────────────────────────────────────────────────


def _err(code: str, message: str, path: str = "") -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _warn(code: str, message: str, path: str = "") -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _validate_type(value: Any, expected: type, path: str) -> list[dict]:
    if not isinstance(value, expected):
        return [_err(f"INVALID_FIELD_TYPE:{path}", f"expected {expected.__name__}, got {type(value).__name__}", path)]
    return []


def _validate_string_field(value: Any, path: str) -> list[dict]:
    errors: list[dict] = []
    if not isinstance(value, str):
        errors.append(_err(f"INVALID_FIELD_TYPE:{path}", f"expected str, got {type(value).__name__}", path))
        return errors
    max_len = 200
    for prefix, limit in STRING_FIELD_MAX.items():
        if path.startswith(prefix):
            max_len = limit
            break
    if len(value) > max_len:
        errors.append(_err(f"FIELD_TOO_LONG:{path}", f"max {max_len} chars, got {len(value)}", path))
    return errors


def _validate_required_present(plan: dict) -> list[dict]:
    errors: list[dict] = []
    for field in REQUIRED_FIELDS:
        if field not in plan:
            errors.append(_err(f"REQUIRED_FIELD_MISSING:{field}", f"'{field}' is required", field))
    return errors


def _validate_schema_version(value: Any) -> list[dict]:
    errors: list[dict] = []
    if not isinstance(value, int):
        errors.append(_err(
            f"INVALID_FIELD_TYPE:_schemaVersion",
            f"expected int, got {type(value).__name__}",
            "_schemaVersion",
        ))
        return errors
    if isinstance(value, bool):
        errors.append(_err(
            f"INVALID_FIELD_TYPE:_schemaVersion",
            f"expected int, got bool",
            "_schemaVersion",
        ))
        return errors
    if value != SCHEMA_VERSION:
        errors.append(_err(
            f"UNSUPPORTED_SCHEMA_VERSION:_schemaVersion",
            f"expected {SCHEMA_VERSION}, got {value}",
            "_schemaVersion",
        ))
    return errors


def _collect_field_errors(plan: dict) -> tuple[list[dict], list[dict], set[str]]:
    errors: list[dict] = []
    warnings: list[dict] = []
    unknown: set[str] = set()

    for key in plan:
        if key in LEGACY_V1_FIELDS:
            errors.append(_err(
                f"LEGACY_FIELD_NOT_ALLOWED:{key}",
                f"v1 legacy field '{key}' is not allowed in v2 plans",
                key,
            ))
        elif key not in ALL_KNOWN_FIELDS:
            unknown.add(key)
            warnings.append(_warn(f"UNKNOWN_FIELD:{key}", f"field '{key}' is not in the v2 schema", key))

    return errors, warnings, unknown


def _validate_plan_types(plan: dict, errors: list[dict], warnings: list[dict]) -> None:
    required_type_checks = [
        ("_schemaVersion", _validate_schema_version),
    ]

    for field, validator in required_type_checks:
        if field in plan:
            errors.extend(validator(plan[field]))

    string_fields = [
        "visualIntent", "period", "location",
        "imageGenerationPrompt", "negativePrompt",
    ]
    for field in string_fields:
        if field in plan and plan[field] is not None:
            errors.extend(_validate_string_field(plan[field], field))

    list_fields = ["subjects", "searchQueries", "assetPreferences", "preferredProviders"]
    for field in list_fields:
        if field in plan:
            errors.extend(_validate_type(plan[field], list, field))
            val = plan[field]
            if isinstance(val, list):
                max_len = STRING_FIELD_MAX.get(field, 200)
                for i, item in enumerate(val):
                    if not isinstance(item, str):
                        errors.append(_err(
                            f"INVALID_FIELD_TYPE:{field}[{i}]",
                            f"expected str, got {type(item).__name__}",
                            f"{field}[{i}]",
                        ))
                    elif len(item) > max_len:
                        errors.append(_err(
                            f"FIELD_TOO_LONG:{field}[{i}]",
                            f"max {max_len} chars, got {len(item)}",
                            f"{field}[{i}]",
                        ))

    if "allowGeneratedImage" in plan:
        val = plan["allowGeneratedImage"]
        if not isinstance(val, bool):
            errors.append(_err(
                f"INVALID_FIELD_TYPE:allowGeneratedImage",
                f"expected bool, got {type(val).__name__}",
                "allowGeneratedImage",
            ))

    if "visualSequence" in plan:
        errors.extend(_validate_type(plan["visualSequence"], list, "visualSequence"))
        vs = plan.get("visualSequence")
        if isinstance(vs, list):
            _validate_visual_sequence(vs, errors, warnings)


def _validate_visual_sequence(
    segments: list, errors: list[dict], warnings: list[dict]
) -> None:
    seen_indices: set[int] = set()

    for i, seg in enumerate(segments):
        path_prefix = f"visualSequence[{i}]"

        if not isinstance(seg, dict):
            errors.append(_err(
                f"INVALID_FIELD_TYPE:{path_prefix}",
                f"expected object, got {type(seg).__name__}",
                path_prefix,
            ))
            continue

        for rfield in REQUIRED_SEGMENT_FIELDS:
            if rfield not in seg:
                errors.append(_err(
                    f"REQUIRED_FIELD_MISSING:{path_prefix}.{rfield}",
                    f"'{rfield}' is required in segment {i}",
                    f"{path_prefix}.{rfield}",
                ))

        if "segmentIndex" in seg:
            si = seg["segmentIndex"]
            if isinstance(si, int) and not isinstance(si, bool):
                if si < 1:
                    errors.append(_err(
                        f"INVALID_SEGMENT_INDEX:{path_prefix}.segmentIndex",
                        f"segmentIndex must be >= 1, got {si}",
                        f"{path_prefix}.segmentIndex",
                    ))
                elif si in seen_indices:
                    errors.append(_err(
                        f"DUPLICATE_SEGMENT_INDEX:{path_prefix}.segmentIndex",
                        f"segmentIndex {si} appears more than once",
                        f"{path_prefix}.segmentIndex",
                    ))
                else:
                    seen_indices.add(si)
            else:
                errors.append(_err(
                    f"INVALID_FIELD_TYPE:{path_prefix}.segmentIndex",
                    f"expected int, got {type(si).__name__}",
                    f"{path_prefix}.segmentIndex",
                ))

        if "durationFraction" in seg:
            df = seg["durationFraction"]
            if isinstance(df, (int, float)) and not isinstance(df, bool):
                if df <= 0 or df > 1:
                    errors.append(_err(
                        f"INVALID_DURATION_FRACTION:{path_prefix}.durationFraction",
                        f"durationFraction must be > 0 and <= 1, got {df}",
                        f"{path_prefix}.durationFraction",
                    ))
            else:
                errors.append(_err(
                    f"INVALID_FIELD_TYPE:{path_prefix}.durationFraction",
                    f"expected float, got {type(df).__name__}",
                    f"{path_prefix}.durationFraction",
                ))

        for field in ("assetPreference", "mediaPreference"):
            if field not in seg:
                continue
            ap = seg[field]
            if not isinstance(ap, str):
                errors.append(_err(
                    f"INVALID_FIELD_TYPE:{path_prefix}.{field}",
                    f"expected str, got {type(ap).__name__}",
                    f"{path_prefix}.{field}",
                ))
            elif len(ap) > STRING_FIELD_MAX[field]:
                errors.append(_err(
                    f"FIELD_TOO_LONG:{path_prefix}.{field}",
                    f"max {STRING_FIELD_MAX[field]} chars, got {len(ap)}",
                    f"{path_prefix}.{field}",
                ))

        if "searchQuery" in seg and seg["searchQuery"] is not None:
            sq = seg["searchQuery"]
            if not isinstance(sq, str):
                errors.append(_err(
                    f"INVALID_FIELD_TYPE:{path_prefix}.searchQuery",
                    f"expected str or null, got {type(sq).__name__}",
                    f"{path_prefix}.searchQuery",
                ))
            elif len(sq) > STRING_FIELD_MAX["searchQuery"]:
                errors.append(_err(
                    f"FIELD_TOO_LONG:{path_prefix}.searchQuery",
                    f"max {STRING_FIELD_MAX['searchQuery']} chars, got {len(sq)}",
                    f"{path_prefix}.searchQuery",
                ))

        if "transition" in seg:
            tr = seg["transition"]
            if not isinstance(tr, str):
                errors.append(_err(
                    f"INVALID_FIELD_TYPE:{path_prefix}.transition",
                    f"expected str, got {type(tr).__name__}",
                    f"{path_prefix}.transition",
                ))
            elif len(tr) > STRING_FIELD_MAX["transition"]:
                errors.append(_err(
                    f"FIELD_TOO_LONG:{path_prefix}.transition",
                    f"max {STRING_FIELD_MAX['transition']} chars, got {len(tr)}",
                    f"{path_prefix}.transition",
                ))

        for uf in seg:
            if uf not in ALL_KNOWN_SEGMENT_FIELDS:
                warnings.append(_warn(
                    f"UNKNOWN_SEGMENT_FIELD:{path_prefix}.{uf}",
                    f"field '{uf}' is not in the v2 segment schema",
                    f"{path_prefix}.{uf}",
                ))

    if not any(
        isinstance(e, dict) and e.get("code", "").startswith("INVALID_FIELD_TYPE:")
        for e in errors
        if "segmentIndex" in (e.get("path") or "")
    ):
        expected_indices = set(range(1, len(segments) + 1))
        if seen_indices and seen_indices != expected_indices:
            errors.append(_err(
                "INVALID_SEGMENT_INDEX_SEQUENCE:visualSequence",
                f"expected segmentIndex 1..{len(segments)}, got {sorted(seen_indices)}",
                "visualSequence",
            ))

    if not any(
        isinstance(e, dict) and e.get("code", "").startswith("INVALID_FIELD_TYPE:")
        for e in errors
        if "durationFraction" in (e.get("path") or "")
    ):
        valid = True
        total = 0.0
        for seg in segments:
            if isinstance(seg, dict):
                df = seg.get("durationFraction")
                if isinstance(df, (int, float)) and not isinstance(df, bool):
                    total += float(df)
                else:
                    valid = False
                    break
        if valid and segments:
            if abs(total - 1.0) > 0.01:
                errors.append(_err(
                    "DURATION_FRACTION_SUM_INVALID:visualSequence",
                    f"sum of durationFraction must be 1.0, got {total:.3f}",
                    "visualSequence",
                ))


def _validate_enums(plan: dict, errors: list[dict], warnings: list[dict]) -> None:
    if "visualIntent" in plan and isinstance(plan["visualIntent"], str):
        if plan["visualIntent"].strip().lower() not in ALLOWED_VISUAL_INTENTS:
            errors.append(_err(
                f"INVALID_ENUM_VALUE:visualIntent",
                f"got '{plan['visualIntent']}', allowed: {sorted(ALLOWED_VISUAL_INTENTS)}",
                "visualIntent",
            ))

    for field in ["assetPreferences"]:
        if field in plan and isinstance(plan[field], list):
            for i, val in enumerate(plan[field]):
                if isinstance(val, str) and val.strip().lower() not in ALLOWED_ASSET_PREFERENCES:
                    errors.append(_err(
                        f"INVALID_ENUM_VALUE:{field}[{i}]",
                        f"got '{val}', allowed: {sorted(ALLOWED_ASSET_PREFERENCES)}",
                        f"{field}[{i}]",
                    ))

    if "preferredProviders" in plan and isinstance(plan["preferredProviders"], list):
        canonical_allowed = set(PROVIDER_ALIASES.keys()) | set(ALLOWED_PROVIDERS)
        for i, val in enumerate(plan["preferredProviders"]):
            if isinstance(val, str):
                clean = val.strip().lower()
                if clean not in canonical_allowed:
                    warnings.append(_warn(
                        f"UNRECOGNIZED_PROVIDER:preferredProviders[{i}]",
                        f"provider '{val}' not recognized",
                        f"preferredProviders[{i}]",
                    ))

    if "visualSequence" in plan and isinstance(plan["visualSequence"], list):
        for i, seg in enumerate(plan["visualSequence"]):
            if not isinstance(seg, dict):
                continue
            path_prefix = f"visualSequence[{i}]"
            if "assetPreference" in seg and isinstance(seg["assetPreference"], str):
                if seg["assetPreference"].strip().lower() not in ALLOWED_ASSET_PREFERENCES:
                    errors.append(_err(
                        f"INVALID_ENUM_VALUE:{path_prefix}.assetPreference",
                        f"got '{seg['assetPreference']}', allowed: {sorted(ALLOWED_ASSET_PREFERENCES)}",
                        f"{path_prefix}.assetPreference",
                    ))
            if "mediaPreference" in seg and isinstance(seg["mediaPreference"], str):
                if seg["mediaPreference"].strip().upper() not in ALLOWED_MEDIA_PREFERENCES:
                    errors.append(_err(
                        f"INVALID_ENUM_VALUE:{path_prefix}.mediaPreference",
                        f"got '{seg['mediaPreference']}', allowed: {sorted(ALLOWED_MEDIA_PREFERENCES)}",
                        f"{path_prefix}.mediaPreference",
                    ))
            if "transition" in seg and isinstance(seg["transition"], str):
                if seg["transition"].strip().lower() not in ALLOWED_TRANSITIONS:
                    errors.append(_err(
                        f"INVALID_ENUM_VALUE:{path_prefix}.transition",
                        f"got '{seg['transition']}', allowed: {sorted(ALLOWED_TRANSITIONS)}",
                        f"{path_prefix}.transition",
                    ))


def _validate_cross_field(plan: dict, errors: list[dict], warnings: list[dict]) -> None:
    scene_prefs: list[str] = []
    if "assetPreferences" in plan and isinstance(plan["assetPreferences"], list):
        scene_prefs = [
            v.strip().lower()
            for v in plan["assetPreferences"]
            if isinstance(v, str)
        ]

    if "visualSequence" in plan and isinstance(plan["visualSequence"], list):
        for i, seg in enumerate(plan["visualSequence"]):
            if not isinstance(seg, dict):
                continue
            seg_pref = seg.get("assetPreference")
            if isinstance(seg_pref, str) and scene_prefs:
                seg_norm = seg_pref.strip().lower()
                if seg_norm not in scene_prefs:
                    errors.append(_err(
                        f"SEGMENT_PREFERENCE_NOT_ALLOWED:visualSequence[{i}].assetPreference",
                        f"'{seg_pref}' not in scene assetPreferences ({plan['assetPreferences']})",
                        f"visualSequence[{i}].assetPreference",
                    ))

    has_generated = False
    if scene_prefs and "generated" in scene_prefs:
        has_generated = True
    if "visualSequence" in plan and isinstance(plan["visualSequence"], list):
        for seg in plan["visualSequence"]:
            if isinstance(seg, dict) and isinstance(seg.get("assetPreference"), str):
                if seg["assetPreference"].strip().lower() == "generated":
                    has_generated = True
                    break

    if has_generated:
        if not plan.get("allowGeneratedImage", False):
            errors.append(_err(
                "GENERATED_ASSET_NOT_ALLOWED",
                "assetPreferences includes 'generated' but allowGeneratedImage is false or missing",
                "",
            ))

    if "imageGenerationPrompt" in plan:
        igp = plan["imageGenerationPrompt"]
        if igp is not None and isinstance(igp, str) and igp.strip():
            agi = plan.get("allowGeneratedImage", False)
            if not agi and not has_generated:
                warnings.append(_warn(
                    "IMAGE_PROMPT_WITHOUT_GENERATION_FLAG",
                    "imageGenerationPrompt is set but allowGeneratedImage is false and no 'generated' preference is used",
                    "imageGenerationPrompt",
                ))


def _validate_required_not_empty(plan: dict, errors: list[dict]) -> None:
    for field in ["subjects", "searchQueries", "assetPreferences"]:
        if field in plan and isinstance(plan[field], list):
            if len(plan[field]) == 0:
                errors.append(_err(
                    f"EMPTY_REQUIRED_FIELD:{field}",
                    f"'{field}' must not be empty",
                    field,
                ))
    if "visualSequence" in plan and isinstance(plan["visualSequence"], list):
        if len(plan["visualSequence"]) == 0:
            errors.append(_err(
                "EMPTY_REQUIRED_FIELD:visualSequence",
                "visualSequence must not be empty",
                "visualSequence",
            ))


# ── Canonicalization helpers ────────────────────────────────────────────────


def _canonicalize_enum(value: str) -> str:
    return value.strip().lower()


def _canonicalize_provider(value: str) -> tuple[str, str | None]:
    clean = value.strip().lower()
    canonical = PROVIDER_ALIASES.get(clean, clean)
    warning = None
    if canonical not in ALLOWED_PROVIDERS:
        warning = f"provider '{value}' not recognized, kept as-is"
    return canonical, warning


def _canonicalize_plan(plan: dict, diagnostics: dict) -> dict:
    canonicalizations: list[str] = []

    canonical: dict[str, Any] = {}

    canonical["_schemaVersion"] = plan["_schemaVersion"]

    vi = _canonicalize_enum(plan["visualIntent"])
    if vi != plan["visualIntent"]:
        canonicalizations.append(f"visualIntent canonicalized '{plan['visualIntent']}' → '{vi}'")
    canonical["visualIntent"] = vi

    for field in ["subjects", "searchQueries"]:
        raw = plan[field]
        cleaned = [s.strip() for s in raw]
        if cleaned != raw:
            canonicalizations.append(f"{field} whitespace trimmed")
        canonical[field] = cleaned

    raw_prefs = plan["assetPreferences"]
    cleaned_prefs = [_canonicalize_enum(p) for p in raw_prefs]
    canonicalizations.append("assetPreferences enum values lowercased")
    seen_prefs: set[str] = set()
    deduped_prefs: list[str] = []
    for p in cleaned_prefs:
        if p not in seen_prefs:
            seen_prefs.add(p)
            deduped_prefs.append(p)
    if len(deduped_prefs) != len(cleaned_prefs):
        canonicalizations.append("assetPreferences duplicates removed (preserving first occurrence)")
    canonical["assetPreferences"] = deduped_prefs

    for field, default in [
        ("period", None),
        ("location", None),
        ("imageGenerationPrompt", None),
        ("negativePrompt", None),
    ]:
        raw = plan.get(field)
        if raw is None:
            canonical[field] = None
        elif isinstance(raw, str):
            trimmed = raw.strip()
            if not trimmed:
                canonical[field] = None
                if raw != "":
                    canonicalizations.append(f"{field} empty string normalized to null")
            else:
                canonical[field] = trimmed
                if trimmed != raw:
                    canonicalizations.append(f"{field} whitespace trimmed")
        else:
            canonical[field] = raw

    agi = plan.get("allowGeneratedImage")
    canonical["allowGeneratedImage"] = agi if agi is not None else OPTIONAL_DEFAULTS["allowGeneratedImage"]

    raw_providers = plan.get("preferredProviders")
    if raw_providers is None or not isinstance(raw_providers, list):
        canonical["preferredProviders"] = []
        if raw_providers is None:
            canonicalizations.append("preferredProviders default applied ([])")
    else:
        canon_provs: list[str] = []
        for p in raw_providers:
            if isinstance(p, str):
                c, _ = _canonicalize_provider(p)
                canon_provs.append(c)
            else:
                canon_provs.append(p)
        if canon_provs != raw_providers:
            canonicalizations.append("preferredProviders normalized")
        canonical["preferredProviders"] = canon_provs

    raw_vs = plan["visualSequence"]
    canon_vs: list[dict] = []
    for seg in raw_vs:
        if not isinstance(seg, dict):
            canon_vs.append(seg)
            continue
        cs: dict[str, Any] = {}
        for k, v in seg.items():
            cs[k] = v
        if "assetPreference" in cs and isinstance(cs["assetPreference"], str):
            clean = _canonicalize_enum(cs["assetPreference"])
            if clean != cs["assetPreference"]:
                canonicalizations.append(f"visualSequence assetPreference '{cs['assetPreference']}' → '{clean}'")
            cs["assetPreference"] = clean
        raw_media_preference = cs.get("mediaPreference")
        if raw_media_preference is None:
            cs["mediaPreference"] = OPTIONAL_SEGMENT_DEFAULTS["mediaPreference"]
            canonicalizations.append(
                "visualSequence mediaPreference default applied (IMAGE_PREFERRED)"
            )
        elif isinstance(raw_media_preference, str):
            clean = raw_media_preference.strip().upper()
            if clean != raw_media_preference:
                canonicalizations.append(
                    f"visualSequence mediaPreference '{raw_media_preference}' → '{clean}'"
                )
            cs["mediaPreference"] = clean
        if "transition" in cs and isinstance(cs["transition"], str):
            clean = _canonicalize_enum(cs["transition"])
            if clean != cs["transition"]:
                canonicalizations.append(f"visualSequence transition '{cs['transition']}' → '{clean}'")
            cs["transition"] = clean
        if "transition" not in cs:
            cs["transition"] = "cut"
        if "searchQuery" in cs and isinstance(cs["searchQuery"], str):
            trimmed = cs["searchQuery"].strip()
            if not trimmed:
                cs["searchQuery"] = None
            elif trimmed != cs["searchQuery"]:
                canonicalizations.append("visualSequence searchQuery whitespace trimmed")
                cs["searchQuery"] = trimmed
        if "searchQuery" not in cs:
            cs["searchQuery"] = None
        canon_vs.append(cs)

    try:
        canon_vs.sort(key=lambda s: s.get("segmentIndex", 0) if isinstance(s, dict) else 0)
    except Exception:
        pass
    canonical["visualSequence"] = canon_vs

    for key in plan:
        if key not in ALL_KNOWN_FIELDS and key not in LEGACY_V1_FIELDS:
            canonical[key] = plan[key]

    diagnostics["canonicalizations"] = canonicalizations
    return canonical


# ── Public API ──────────────────────────────────────────────────────────────


def canonicalize_visual_plan_v2(
    plan: dict, scene: dict | None = None
) -> dict[str, Any]:
    """Accept a v2 visual plan, validate and canonicalize it.

    Returns ``{ok, canonicalPlan, diagnostics}``.
    """
    diagnostics: dict[str, Any] = {
        "ok": True,
        "errors": [],
        "warnings": [],
        "canonicalizations": [],
        "fieldSummary": {
            "totalExpected": len(ALL_KNOWN_FIELDS),
            "present": 0,
            "missing": [],
            "unknown": [],
        },
    }

    if not isinstance(plan, dict):
        diagnostics["ok"] = False
        diagnostics["errors"].append(_err(
            "INVALID_INPUT", "plan must be a dict", ""
        ))
        return {"ok": False, "canonicalPlan": None, "diagnostics": diagnostics}

    errors: list[dict] = diagnostics["errors"]
    warnings: list[dict] = diagnostics["warnings"]

    errs, warns, unknown = _collect_field_errors(plan)
    errors.extend(errs)
    warnings.extend(warns)

    errors.extend(_validate_required_present(plan))

    if errors:
        diagnostics["ok"] = False
        diagnostics["fieldSummary"]["unknown"] = sorted(unknown)
        present = [k for k in ALL_KNOWN_FIELDS if k in plan]
        diagnostics["fieldSummary"]["present"] = len(present)
        diagnostics["fieldSummary"]["missing"] = sorted(set(REQUIRED_FIELDS) - set(plan.keys()))
        return {"ok": False, "canonicalPlan": None, "diagnostics": diagnostics}

    _validate_plan_types(plan, errors, warnings)

    _validate_required_not_empty(plan, errors)

    _validate_enums(plan, errors, warnings)

    _validate_cross_field(plan, errors, warnings)

    present = [k for k in ALL_KNOWN_FIELDS if k in plan]
    diagnostics["fieldSummary"]["present"] = len(present)
    diagnostics["fieldSummary"]["missing"] = sorted(set(REQUIRED_FIELDS) - set(plan.keys()))
    diagnostics["fieldSummary"]["unknown"] = sorted(unknown)

    if errors:
        diagnostics["ok"] = False
        return {"ok": False, "canonicalPlan": None, "diagnostics": diagnostics}

    canonical = _canonicalize_plan(plan, diagnostics)
    diagnostics["ok"] = True

    return {"ok": True, "canonicalPlan": canonical, "diagnostics": diagnostics}


def validate_visual_plan_v2(
    plan: dict, scene: dict | None = None
) -> dict[str, Any]:
    """Validate a v2 visual plan. Does not canonicalize.

    Returns ``{ok, diagnostics}``.
    """
    diagnostics: dict[str, Any] = {
        "ok": True,
        "errors": [],
        "warnings": [],
        "fieldSummary": {
            "totalExpected": len(ALL_KNOWN_FIELDS),
            "present": 0,
            "missing": [],
            "unknown": [],
        },
    }

    if not isinstance(plan, dict):
        diagnostics["ok"] = False
        diagnostics["errors"].append(_err(
            "INVALID_INPUT", "plan must be a dict", ""
        ))
        return {"ok": False, "diagnostics": diagnostics}

    errors: list[dict] = diagnostics["errors"]
    warnings: list[dict] = diagnostics["warnings"]

    errs, warns, unknown = _collect_field_errors(plan)
    errors.extend(errs)
    warnings.extend(warns)

    errors.extend(_validate_required_present(plan))

    _validate_plan_types(plan, errors, warnings)
    _validate_required_not_empty(plan, errors)
    _validate_enums(plan, errors, warnings)
    _validate_cross_field(plan, errors, warnings)

    present = [k for k in ALL_KNOWN_FIELDS if k in plan]
    diagnostics["fieldSummary"]["present"] = len(present)
    diagnostics["fieldSummary"]["missing"] = sorted(set(REQUIRED_FIELDS) - set(plan.keys()))
    diagnostics["fieldSummary"]["unknown"] = sorted(unknown)

    if errors:
        diagnostics["ok"] = False

    return {"ok": diagnostics["ok"], "diagnostics": diagnostics}
