"""Visual Asset Router v2 — pure sourcing plan builder.

Receives a canonical v2 VisualPlan, applies provider routing heuristics,
query derivation, and request-level constraints, and returns a structured
sourcing plan.

No I/O, no HTTP, no provider SDK calls, no file access, no environment reads.
Generated-image providers are planned as routing candidates only.
Actual image generation belongs to a future executor/downloader module.
"""

from __future__ import annotations

from typing import Any

# ── Schema constants ────────────────────────────────────────────────────────

SOURCING_PLAN_SCHEMA_VERSION = 1

ALLOWED_ASSET_PREFERENCES: frozenset[str] = frozenset({
    "diagram", "illustration", "photograph", "painting",
    "archive", "map", "document", "stock", "generated",
})

ALLOWED_PROVIDERS: frozenset[str] = frozenset({
    "wikimedia_commons", "pexels", "pixabay", "freeai", "pollinations",
})

ALLOWED_PRIORITY_POLICIES: frozenset[str] = frozenset({
    "balanced", "request_first", "plan_first",
})

ALLOWED_CANDIDATE_STATUSES: frozenset[str] = frozenset({
    "included", "conditional", "excluded",
})

ALLOWED_AVAILABILITIES: frozenset[str] = frozenset({
    "available", "conditional", "blocked", "unknown",
})

ALLOWED_SUPPORT_STRENGTHS: frozenset[str] = frozenset({
    "strong", "medium", "weak", "conditional",
})

ALLOWED_ROUTING_STATUSES: frozenset[str] = frozenset({
    "ROUTABLE", "ROUTABLE_WITH_WARNINGS", "UNROUTABLE",
})

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

# ── Provider metadata ───────────────────────────────────────────────────────

PROVIDER_AVAILABILITY: dict[str, str] = {
    "wikimedia_commons": "available",
    "pexels": "conditional",
    "pixabay": "conditional",
    "freeai": "conditional",
    "pollinations": "conditional",
}

PROVIDER_REQUIRES_API_KEY: dict[str, bool] = {
    "wikimedia_commons": False,
    "pexels": True,
    "pixabay": True,
    "freeai": True,
    "pollinations": False,
}

PROVIDER_QUERY_STRATEGY: dict[str, str] = {
    "wikimedia_commons": "search",
    "pexels": "search",
    "pixabay": "search",
    "freeai": "generate",
    "pollinations": "generate",
}

PROVIDER_WARNINGS: dict[str, list[str]] = {
    "freeai": [
        "actual generation requires future executor module and API key",
        "FreeAI validation status is PENDIENTE_DE_VALIDAR per integrations.md",
    ],
    "pollinations": [
        "actual generation requires future executor module",
        "quality is known to be low per integrations.md",
        "rate-limit uncertainty — 429 responses observed",
    ],
}

# ── Routing matrix ──────────────────────────────────────────────────────────

# Structure: assetPreference → [(provider, supportStrength), ...]
# Order defines priority within "balanced" policy before boosts.
ROUTING_MATRIX: dict[str, list[tuple[str, str]]] = {
    "photograph": [
        ("pexels", "strong"),
        ("pixabay", "strong"),
        ("wikimedia_commons", "medium"),
    ],
    "stock": [
        ("pexels", "strong"),
        ("pixabay", "strong"),
    ],
    "archive": [
        ("wikimedia_commons", "medium"),
    ],
    "map": [
        ("wikimedia_commons", "weak"),
    ],
    "document": [
        ("wikimedia_commons", "weak"),
    ],
    "painting": [
        ("wikimedia_commons", "medium"),
    ],
    "diagram": [
        ("wikimedia_commons", "weak"),
        ("freeai", "conditional"),
        ("pollinations", "conditional"),
    ],
    "illustration": [
        ("pixabay", "medium"),
        ("pexels", "medium"),
        ("wikimedia_commons", "weak"),
        ("freeai", "conditional"),
        ("pollinations", "conditional"),
    ],
    "generated": [
        ("freeai", "conditional"),
        ("pollinations", "conditional"),
    ],
}

MATRIX_WARNINGS: dict[str, dict[str, list[str]]] = {
    "photograph": {
        "wikimedia_commons": [
            "Wikimedia photograph results are archival/historical, not modern stock photography",
        ],
    },
    "archive": {
        "wikimedia_commons": [
            "archive support on Wikimedia varies by topic — no fallback provider available",
        ],
    },
    "map": {
        "wikimedia_commons": [
            "map support on Wikimedia is topic-dependent and not guaranteed",
        ],
    },
    "document": {
        "wikimedia_commons": [
            "document support on Wikimedia is topic-dependent and not guaranteed",
        ],
    },
    "painting": {
        "wikimedia_commons": [
            "painting support on Wikimedia varies by topic — well-known subjects more likely to have artworks",
        ],
    },
    "diagram": {
        "wikimedia_commons": [
            "diagram support on Wikimedia is topic-dependent and not guaranteed",
        ],
    },
    "illustration": {
        "wikimedia_commons": [
            "Wikimedia illustration support is weak and topic-dependent",
        ],
    },
    "generated": {
        "freeai": [
            "FreeAI generation requires future executor module and API key",
        ],
        "pollinations": [
            "Pollinations generation requires future executor module; quality is low",
        ],
    },
}

GENERATED_PROVIDERS: frozenset[str] = frozenset({"freeai", "pollinations"})

# ── Default request config ──────────────────────────────────────────────────

DEFAULT_REQUEST_VISUALS: dict[str, Any] = {
    "allowSearchProviders": True,
    "allowStockAssets": True,
    "allowArchiveAssets": True,
    "allowGeneratedImages": False,
    "preferredProviders": [],
    "blockedProviders": [],
    "maxQueriesPerSegment": 4,
    "providerPriorityPolicy": "balanced",
}

# ── Diagnostics helpers ─────────────────────────────────────────────────────


def _err(code: str, message: str, path: str = "") -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _warn(code: str, message: str, path: str = "") -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


# ── Request config validation ───────────────────────────────────────────────


def _validate_request_config(
    config: dict, errors: list[dict], warnings: list[dict]
) -> dict:
    canonical: dict[str, Any] = dict(DEFAULT_REQUEST_VISUALS)
    if not config:
        return canonical

    bool_fields = [
        "allowSearchProviders", "allowStockAssets",
        "allowArchiveAssets", "allowGeneratedImages",
    ]
    for field in bool_fields:
        if field in config:
            val = config[field]
            if not isinstance(val, bool):
                warnings.append(_warn(
                    f"INVALID_REQUEST_CONFIG:{field}",
                    f"expected bool, got {type(val).__name__}; using default ({canonical[field]})",
                    f"request_visuals.{field}",
                ))
            else:
                canonical[field] = val

    if "preferredProviders" in config:
        val = config["preferredProviders"]
        if isinstance(val, list):
            clean: list[str] = []
            for i, p in enumerate(val):
                if isinstance(p, str):
                    p_clean = p.strip().lower()
                    if p_clean in ALLOWED_PROVIDERS:
                        clean.append(p_clean)
                    else:
                        warnings.append(_warn(
                            f"UNRECOGNIZED_PROVIDER:request_visuals.preferredProviders[{i}]",
                            f"provider '{p}' not recognized",
                            f"request_visuals.preferredProviders[{i}]",
                        ))
            canonical["preferredProviders"] = clean
        else:
            warnings.append(_warn(
                "INVALID_REQUEST_CONFIG:preferredProviders",
                f"expected list, got {type(val).__name__}; using default ({canonical['preferredProviders']})",
                "request_visuals.preferredProviders",
            ))

    if "blockedProviders" in config:
        val = config["blockedProviders"]
        if isinstance(val, list):
            clean: list[str] = []
            for i, p in enumerate(val):
                if isinstance(p, str):
                    p_clean = p.strip().lower()
                    if p_clean in ALLOWED_PROVIDERS:
                        clean.append(p_clean)
                    else:
                        warnings.append(_warn(
                            f"UNRECOGNIZED_PROVIDER:request_visuals.blockedProviders[{i}]",
                            f"provider '{p}' not recognized",
                            f"request_visuals.blockedProviders[{i}]",
                        ))
            canonical["blockedProviders"] = clean
        else:
            warnings.append(_warn(
                "INVALID_REQUEST_CONFIG:blockedProviders",
                f"expected list, got {type(val).__name__}; using default ({canonical['blockedProviders']})",
                "request_visuals.blockedProviders",
            ))

    if "maxQueriesPerSegment" in config:
        val = config["maxQueriesPerSegment"]
        if isinstance(val, int) and not isinstance(val, bool):
            if val < 1:
                warnings.append(_warn(
                    "INVALID_REQUEST_CONFIG:maxQueriesPerSegment",
                    f"expected >= 1, got {val}; using default ({canonical['maxQueriesPerSegment']})",
                    "request_visuals.maxQueriesPerSegment",
                ))
            else:
                canonical["maxQueriesPerSegment"] = val
        else:
            warnings.append(_warn(
                "INVALID_REQUEST_CONFIG:maxQueriesPerSegment",
                f"expected int, got {type(val).__name__}; using default ({canonical['maxQueriesPerSegment']})",
                "request_visuals.maxQueriesPerSegment",
            ))

    if "providerPriorityPolicy" in config:
        val = config["providerPriorityPolicy"]
        if isinstance(val, str):
            clean = val.strip().lower()
            if clean in ALLOWED_PRIORITY_POLICIES:
                canonical["providerPriorityPolicy"] = clean
            else:
                warnings.append(_warn(
                    "UNKNOWN_PRIORITY_POLICY",
                    f"got '{val}', allowed: {sorted(ALLOWED_PRIORITY_POLICIES)}; using default 'balanced'",
                    "request_visuals.providerPriorityPolicy",
                ))
        else:
            warnings.append(_warn(
                "INVALID_REQUEST_CONFIG:providerPriorityPolicy",
                f"expected str, got {type(val).__name__}; using default 'balanced'",
                "request_visuals.providerPriorityPolicy",
            ))

    return canonical


# ── Query derivation ────────────────────────────────────────────────────────


def _derive_search_queries(
    canonical_plan: dict,
    segment: dict,
    asset_preference: str,
    max_queries: int,
    warnings: list[dict],
) -> list[dict[str, str]]:
    """Derive search queries only.  imageGenerationPrompt is excluded."""
    queries: list[dict[str, str]] = []
    seen: set[str] = set()

    def _add(text: str, source: str) -> None:
        if len(queries) >= max_queries:
            return
        trimmed = text.strip()[:200]
        if not trimmed:
            return
        key = trimmed.lower()
        if key in seen:
            return
        seen.add(key)
        queries.append({"text": trimmed, "source": source})

    sq = segment.get("searchQuery")
    if sq is not None and isinstance(sq, str) and sq.strip():
        _add(sq, "segment.searchQuery")

    scene_queries = canonical_plan.get("searchQueries") or []
    if isinstance(scene_queries, list):
        for i, q in enumerate(scene_queries):
            if isinstance(q, str) and q.strip():
                _add(q, f"scene.searchQueries[{i}]")

    subjects = canonical_plan.get("subjects") or []
    if isinstance(subjects, list):
        for i, subj in enumerate(subjects):
            if not isinstance(subj, str) or not subj.strip():
                continue
            _add(f"{subj.strip()} {asset_preference}", f"subjects[{i}] + assetPreference")

    location = canonical_plan.get("location")
    if location and isinstance(location, str) and location.strip() and isinstance(subjects, list):
        for i, subj in enumerate(subjects):
            if not isinstance(subj, str) or not subj.strip():
                continue
            _add(f"{subj.strip()} {location.strip()}", f"subjects[{i}] + location")

    period = canonical_plan.get("period")
    if period and isinstance(period, str) and period.strip() and isinstance(subjects, list):
        for i, subj in enumerate(subjects):
            if not isinstance(subj, str) or not subj.strip():
                continue
            _add(f"{subj.strip()} {period.strip()}", f"subjects[{i}] + period")

    if not queries:
        warnings.append(_warn(
            "NO_SEARCH_QUERIES_DERIVED",
            f"segment has no searchQuery and no scene-level queries; subjects/period/location also insufficient",
            "",
        ))

    return queries


def _derive_generation_prompts(
    canonical_plan: dict,
    segment: dict,
    warnings: list[dict],
) -> list[dict[str, str]]:
    """Derive generation prompts.  Only meaningful for generated providers."""
    prompts: list[dict[str, str]] = []
    seen: set[str] = set()

    def _add(text: str, source: str) -> None:
        trimmed = text.strip()[:500]
        if not trimmed:
            return
        key = trimmed.lower()
        if key in seen:
            return
        seen.add(key)
        prompts.append({"text": trimmed, "source": source})

    igp = canonical_plan.get("imageGenerationPrompt")
    if igp is not None and isinstance(igp, str) and igp.strip():
        _add(igp, "scene.imageGenerationPrompt")

    if not prompts:
        sg = segment.get("searchQuery")
        if sg is not None and isinstance(sg, str) and sg.strip():
            _add(sg, "segment.searchQuery (fallback)")
        else:
            scene_queries = canonical_plan.get("searchQueries") or []
            if isinstance(scene_queries, list) and scene_queries:
                first = scene_queries[0]
                if isinstance(first, str) and first.strip():
                    _add(first, "scene.searchQueries[0] (fallback)")

    if not prompts:
        warnings.append(_warn(
            "NO_GENERATION_PROMPT_DERIVED",
            "no imageGenerationPrompt in plan and no fallback search query; "
            "generated providers will have no prompt",
            "",
        ))

    return prompts


# ── Provider candidate builder ──────────────────────────────────────────────


def _make_candidate(
    provider: str,
    priority: int,
    support_strength: str,
    reason: str,
    candidate_status: str = "included",
    availability: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    av = availability or PROVIDER_AVAILABILITY.get(provider, "unknown")
    return {
        "provider": provider,
        "priority": priority,
        "queryStrategy": PROVIDER_QUERY_STRATEGY.get(provider, "search"),
        "candidateStatus": candidate_status,
        "availability": av,
        "requiresApiKey": PROVIDER_REQUIRES_API_KEY.get(provider, False),
        "supportStrength": support_strength,
        "reason": reason,
        "exclusionReason": None if candidate_status == "included" else reason,
        "warnings": warnings or [],
    }


def _make_excluded(
    provider: str,
    exclusion_reason: str,
    availability: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    av = availability or PROVIDER_AVAILABILITY.get(provider, "unknown")
    return {
        "provider": provider,
        "candidateStatus": "excluded",
        "availability": av,
        "exclusionReason": exclusion_reason,
        "warnings": warnings or [],
    }


def _is_generated_provider(provider: str) -> bool:
    return provider in GENERATED_PROVIDERS


def _generation_gates_open(
    canonical_plan: dict, request_visuals: dict
) -> tuple[bool, str | None]:
    plan_gate = canonical_plan.get("allowGeneratedImage", False)
    request_gate = request_visuals.get("allowGeneratedImages", False)

    if not plan_gate:
        return False, "generated images blocked: canonical_plan.allowGeneratedImage=false"
    if not request_gate:
        return False, "generated images blocked: request_visuals.allowGeneratedImages=false"
    return True, None


def _is_archive_only_pref(asset_preference: str) -> bool:
    return asset_preference in ("archive", "painting", "map", "document")


# ── Routing engine ──────────────────────────────────────────────────────────


def _route_segment(
    canonical_plan: dict,
    segment: dict,
    request_visuals: dict,
    seg_warnings: list[dict],
    routing_decisions: list[str],
) -> dict[str, Any]:
    asset_pref = segment.get("assetPreference", "")
    if not isinstance(asset_pref, str) or not asset_pref:
        return {
            "segmentIndex": segment.get("segmentIndex", 0),
            "assetPreference": "",
            "searchQueries": [],
            "generationPrompts": [],
            "providerCandidates": [],
            "excludedProviders": [],
            "routingStatus": "UNROUTABLE",
            "warnings": [],
            "unsupportedReasons": ["empty or missing assetPreference"],
        }

    segment_idx = segment.get("segmentIndex", 0)

    # ── Query derivation ─────────────────────────────────────────────────
    search_queries = _derive_search_queries(
        canonical_plan, segment, asset_pref,
        request_visuals.get("maxQueriesPerSegment", 4),
        seg_warnings,
    )
    generation_prompts = _derive_generation_prompts(
        canonical_plan, segment, seg_warnings,
    )

    # ── Get matrix row ───────────────────────────────────────────────────
    matrix_row = ROUTING_MATRIX.get(asset_pref)
    matrix_providers: set[str] = set()
    if matrix_row:
        matrix_providers = {p for p, _ in matrix_row}

    if not matrix_row:
        return {
            "segmentIndex": segment_idx,
            "assetPreference": asset_pref,
            "searchQueries": search_queries,
            "generationPrompts": generation_prompts,
            "providerCandidates": [],
            "excludedProviders": [
                _make_excluded(
                    p,
                    f"assetPreference '{asset_pref}' not in v2 routing matrix",
                    availability="unknown",
                )
                for p in ALLOWED_PROVIDERS
            ],
            "routingStatus": "UNROUTABLE",
            "warnings": [],
            "unsupportedReasons": [f"assetPreference '{asset_pref}' not in routing matrix"],
        }

    # ── Build initial candidate list ─────────────────────────────────────
    candidates: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for priority_rank, (provider, support_strength) in enumerate(matrix_row, start=1):
        reason = f"{asset_pref} preference — {provider} {support_strength} support"
        pw = list(MATRIX_WARNINGS.get(asset_pref, {}).get(provider, []))

        c = _make_candidate(
            provider=provider,
            priority=priority_rank,
            support_strength=support_strength,
            reason=reason,
            candidate_status="included",
            warnings=pw,
        )
        candidates.append(c)

    # Add providers NOT in the matrix row as excluded (complete audit)
    for provider in sorted(ALLOWED_PROVIDERS):
        if provider not in matrix_providers:
            excluded.append(_make_excluded(
                provider,
                f"provider does not support assetPreference='{asset_pref}' in v2 routing matrix",
            ))

    # ── Apply constraints in order ───────────────────────────────────────

    # 1. blockedProviders
    blocked = set(request_visuals.get("blockedProviders") or [])
    for c in candidates[:]:
        if c["provider"] in blocked:
            candidates.remove(c)
            excluded.append(_make_excluded(
                c["provider"],
                f"blocked by request_visuals.blockedProviders",
                availability="blocked",
            ))
            routing_decisions.append(
                f"segment[{segment_idx}] {asset_pref}: {c['provider']} excluded (blocked)"
            )

    # 2. allowSearchProviders
    if not request_visuals.get("allowSearchProviders", True):
        for c in candidates[:]:
            if PROVIDER_QUERY_STRATEGY.get(c["provider"]) == "search":
                candidates.remove(c)
                excluded.append(_make_excluded(
                    c["provider"],
                    "search providers disabled: request_visuals.allowSearchProviders=false",
                ))
                routing_decisions.append(
                    f"segment[{segment_idx}] {asset_pref}: {c['provider']} excluded (search disabled)"
                )

    # 3. allowStockAssets
    if not request_visuals.get("allowStockAssets", True):
        for c in candidates[:]:
            if c["provider"] in ("pexels", "pixabay"):
                candidates.remove(c)
                excluded.append(_make_excluded(
                    c["provider"],
                    "stock assets disabled: request_visuals.allowStockAssets=false",
                ))
                routing_decisions.append(
                    f"segment[{segment_idx}] {asset_pref}: {c['provider']} excluded (stock disabled)"
                )

    # 4. allowArchiveAssets (only for archive/painting/map/document)
    if not request_visuals.get("allowArchiveAssets", True) and _is_archive_only_pref(asset_pref):
        for c in candidates[:]:
            if c["provider"] == "wikimedia_commons":
                candidates.remove(c)
                excluded.append(_make_excluded(
                    c["provider"],
                    f"archive assets disabled for '{asset_pref}': request_visuals.allowArchiveAssets=false",
                ))
                routing_decisions.append(
                    f"segment[{segment_idx}] {asset_pref}: {c['provider']} excluded (archive disabled for {asset_pref})"
                )

    # 5. generated double gate
    gen_ok, gen_block_reason = _generation_gates_open(canonical_plan, request_visuals)
    if not gen_ok:
        for c in candidates[:]:
            if _is_generated_provider(c["provider"]):
                candidates.remove(c)
                excluded.append(_make_excluded(
                    c["provider"],
                    gen_block_reason or "generated images blocked",
                ))
                routing_decisions.append(
                    f"segment[{segment_idx}] {asset_pref}: {c['provider']} excluded (generated blocked)"
                )
    else:
        for c in candidates:
            if _is_generated_provider(c["provider"]):
                c["warnings"] = list(c.get("warnings") or [])
                pw = PROVIDER_WARNINGS.get(c["provider"], [])
                for w in pw:
                    if w not in c["warnings"]:
                        c["warnings"].append(w)

    # ── Priority policy ordering ──────────────────────────────────────────
    policy = request_visuals.get("providerPriorityPolicy", "balanced")
    candidates = _apply_priority_policy(
        candidates, canonical_plan, request_visuals, policy, asset_pref
    )

    # ── Compute routing status ───────────────────────────────────────────
    status = _compute_routing_status(candidates, asset_pref, segment_idx)
    segment_warnings: list[str] = []

    if not search_queries:
        segment_warnings.append("no search queries derived for this segment")
    for c in candidates:
        if c.get("warnings"):
            for w in c["warnings"]:
                if w not in segment_warnings:
                    segment_warnings.append(f"{c['provider']}: {w}")

    return {
        "segmentIndex": segment_idx,
        "assetPreference": asset_pref,
        "searchQueries": search_queries,
        "generationPrompts": generation_prompts,
        "providerCandidates": candidates,
        "excludedProviders": excluded,
        "routingStatus": status,
        "warnings": segment_warnings,
        "unsupportedReasons": [],
    }


def _apply_priority_policy(
    candidates: list[dict[str, Any]],
    canonical_plan: dict,
    request_visuals: dict,
    policy: str,
    asset_pref: str,
) -> list[dict[str, Any]]:
    if not candidates:
        return candidates

    plan_prefs: set[str] = set()
    pp = canonical_plan.get("preferredProviders") or []
    if isinstance(pp, list):
        plan_prefs = {p for p in pp if isinstance(p, str)}

    req_prefs: set[str] = set()
    rp = request_visuals.get("preferredProviders") or []
    if isinstance(rp, list):
        req_prefs = {p for p in rp if isinstance(p, str)}

    def _boost_eligible(c: dict[str, Any]) -> int:
        boost = 0
        if policy == "request_first":
            if c["provider"] in req_prefs:
                boost -= 200
            elif c["provider"] in plan_prefs:
                boost -= 50
        elif policy == "plan_first":
            if c["provider"] in plan_prefs:
                boost -= 200
            elif c["provider"] in req_prefs:
                boost -= 50
        else:  # balanced
            if c["provider"] in plan_prefs:
                boost -= 50
            if c["provider"] in req_prefs:
                boost -= 50

        strength_rank = {"strong": 0, "medium": 100, "weak": 200, "conditional": 300}
        boost += strength_rank.get(c.get("supportStrength", "weak"), 200)

        return boost

    candidates.sort(key=_boost_eligible)

    for i, c in enumerate(candidates):
        c["priority"] = i + 1

    return candidates


def _compute_routing_status(
    candidates: list[dict[str, Any]],
    asset_pref: str,
    segment_idx: int,
) -> str:
    if not candidates:
        return "UNROUTABLE"

    has_strong_available = any(
        c.get("supportStrength") == "strong"
        and c.get("availability") == "available"
        for c in candidates
    )

    if has_strong_available:
        return "ROUTABLE"

    if candidates:
        return "ROUTABLE_WITH_WARNINGS"

    return "UNROUTABLE"


# ── Public API ──────────────────────────────────────────────────────────────


def build_visual_sourcing_plan_v2(
    canonical_plan: dict,
    scene: dict | None = None,
    request_visuals: dict | None = None,
) -> dict[str, Any]:
    """Build a visual sourcing plan from a canonicalized v2 VisualPlan.

    Args:
        canonical_plan: Canonicalized VisualPlan v2 (from
                        ``canonicalize_visual_plan_v2``).
        scene: Optional scene dict (reserved for future use; currently unused).
        request_visuals: Optional request-level visual configuration dict.

    Returns:
        ``{ok, sourcingPlan, diagnostics}``
    """
    diagnostics: dict[str, Any] = {
        "errors": [],
        "warnings": [],
        "unsupported": [],
        "routingDecisions": [],
    }
    errors: list[dict] = diagnostics["errors"]
    d_warnings: list[dict] = diagnostics["warnings"]
    routing_decisions: list[str] = diagnostics["routingDecisions"]

    if not isinstance(canonical_plan, dict):
        diagnostics["ok"] = False
        errors.append(_err(
            "INVALID_INPUT", "canonical_plan must be a dict", ""
        ))
        return {"ok": False, "sourcingPlan": None, "diagnostics": diagnostics}

    req_config = DEFAULT_REQUEST_VISUALS
    if request_visuals is not None:
        if not isinstance(request_visuals, dict):
            errors.append(_err(
                "INVALID_REQUEST_CONFIG",
                "request_visuals must be a dict or None",
                "",
            ))
            return {"ok": False, "sourcingPlan": None, "diagnostics": diagnostics}
        req_config = _validate_request_config(request_visuals, errors, d_warnings)

    # ── Only fail for truly invalid input shapes, not config warnings ────

    # ── Check for legacy v1 fields (defensive) ───────────────────────────
    for field in LEGACY_V1_FIELDS:
        if field in canonical_plan:
            errors.append(_err(
                f"LEGACY_FIELD_NOT_ALLOWED_IN_ROUTER:{field}",
                f"v1 legacy field '{field}' must not appear in router input",
                field,
            ))

    if errors:
        diagnostics["ok"] = False
        return {"ok": False, "sourcingPlan": None, "diagnostics": diagnostics}

    # ── Route each segment ───────────────────────────────────────────────
    visual_sequence = canonical_plan.get("visualSequence") or []
    if not isinstance(visual_sequence, list):
        visual_sequence = []

    segments: list[dict[str, Any]] = []
    seg_warnings: list[dict] = []

    for i, seg in enumerate(visual_sequence):
        if not isinstance(seg, dict):
            d_warnings.append(_warn(
                f"INVALID_SEGMENT:{i}",
                f"visualSequence[{i}] is not a dict, skipping",
                f"visualSequence[{i}]",
            ))
            continue
        routed = _route_segment(
            canonical_plan, seg, req_config, seg_warnings, routing_decisions
        )
        segments.append(routed)

    # ── Compute summary ──────────────────────────────────────────────────
    total = len(segments)
    routable = sum(1 for s in segments if s["routingStatus"] == "ROUTABLE")
    routable_with_warnings = sum(1 for s in segments if s["routingStatus"] == "ROUTABLE_WITH_WARNINGS")
    unroutable = sum(1 for s in segments if s["routingStatus"] == "UNROUTABLE")

    d_warnings.extend(seg_warnings)

    sourcing_plan = {
        "schemaVersion": SOURCING_PLAN_SCHEMA_VERSION,
        "segments": segments,
        "summary": {
            "totalSegments": total,
            "routable": routable,
            "routableWithWarnings": routable_with_warnings,
            "unroutable": unroutable,
        },
    }

    diagnostics["ok"] = True

    return {
        "ok": True,
        "sourcingPlan": sourcing_plan,
        "diagnostics": diagnostics,
    }
