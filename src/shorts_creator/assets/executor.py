"""Visual Asset Executor v2 — dry-run and live sourcing plan executor.

Consumes the sourcing plan from ``build_visual_sourcing_plan_v2`` and
produces an execution plan.  In dry-run mode evaluates provider
availability and returns what would be attempted.  In live mode
executes Wikimedia Commons searches and downloads (other providers
remain not implemented).

No imports from v1 runtime pipeline modules.  Stdlib only.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from shorts_creator.assets.semantic import (
    RELEVANT,
    assess_candidate,
)

# ── Constants ────────────────────────────────────────────────────────────────

ALLOWED_AVAILABILITY_STATUSES: frozenset[str] = frozenset({
    "AVAILABLE", "DISABLED_BY_REQUEST", "NOT_IMPLEMENTED",
    "MISSING_API_KEY", "UNKNOWN_PROVIDER",
})

ALLOWED_EXECUTOR_STATUSES: frozenset[str] = frozenset({
    "SKIPPED_DRY_RUN", "PROVIDER_UNAVAILABLE", "UNRESOLVED",
    "LIVE_EXECUTION_NOT_IMPLEMENTED", "INVALID_INPUT",
    "RESOLVED", "NO_RESULTS", "DOWNLOAD_FAILED", "PROVIDER_ERROR",
})

LEGACY_V1_FIELDS: frozenset[str] = frozenset({
    "editorialRole", "visualTemporalIntent", "strategy",
    "primaryAssetType", "secondaryAssetType", "style",
    "mood", "licenseRequired", "visualImportance",
})

SECRET_FIELD_NAMES: frozenset[str] = frozenset({
    "api_key", "apiKey", "token", "secret",
})

REQUIRED_SOURCING_PLAN_KEYS: frozenset[str] = frozenset({
    "schemaVersion", "segments", "summary",
})

REQUIRED_SEGMENT_KEYS: frozenset[str] = frozenset({
    "segmentIndex", "assetPreference", "searchQueries",
    "generationPrompts", "providerCandidates", "excludedProviders",
    "routingStatus",
})

# ── Diagnostics helpers ──────────────────────────────────────────────────────


def _err(code: str, message: str, path: str = "") -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _warn(code: str, message: str, path: str = "") -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


# ── Input validation ─────────────────────────────────────────────────────────


def _validate_sourcing_plan(sp: Any) -> list[dict]:
    errors: list[dict] = []
    if not isinstance(sp, dict):
        errors.append(_err("INVALID_INPUT", "sourcing_plan must be a dict", ""))
        return errors
    for key in REQUIRED_SOURCING_PLAN_KEYS:
        if key not in sp:
            errors.append(_err(
                f"MISSING_SOURCING_PLAN_KEY:{key}",
                f"'{key}' is required in sourcing_plan",
                key,
            ))
    if "segments" in sp and not isinstance(sp["segments"], list):
        errors.append(_err(
            "INVALID_FIELD_TYPE:segments",
            "segments must be a list",
            "segments",
        ))
    return errors


def _validate_provider_config(config: Any, warnings: list[dict]) -> dict:
    if not isinstance(config, dict):
        warnings.append(_warn(
            "INVALID_PROVIDER_CONFIG",
            "provider_config must be a dict",
            "",
        ))
        return {}
    for provider, cfg in config.items():
        if not isinstance(cfg, dict):
            continue
        for key in cfg:
            if key in SECRET_FIELD_NAMES:
                warnings.append(_warn(
                    "SECRET_FIELD_IGNORED",
                    f"provider '{provider}': field '{key}' is a secret-like "
                    "field and was ignored",
                    f"provider_config.{provider}.{key}",
                ))
    return config


# ── Provider availability ────────────────────────────────────────────────────


def _evaluate_provider_availability(
    provider: str,
    config: dict,
) -> str:
    if not isinstance(config, dict):
        return "UNKNOWN_PROVIDER"
    if provider not in config:
        return "UNKNOWN_PROVIDER"
    provider_cfg = config.get(provider)
    if not isinstance(provider_cfg, dict):
        return "UNKNOWN_PROVIDER"
    if provider_cfg.get("enabled") is False:
        return "DISABLED_BY_REQUEST"
    if provider_cfg.get("implemented") is False:
        return "NOT_IMPLEMENTED"
    if (
        provider_cfg.get("requiresApiKey") is True
        and provider_cfg.get("apiKeyPresent") is not True
    ):
        return "MISSING_API_KEY"
    return "AVAILABLE"


def _availability_reason(availability: str, provider: str) -> str:
    reasons: dict[str, str] = {
        "AVAILABLE": "first available provider candidate",
        "NOT_IMPLEMENTED": f"provider '{provider}' is not implemented yet",
        "MISSING_API_KEY": f"provider '{provider}' requires an API key but none is configured",
        "DISABLED_BY_REQUEST": f"provider '{provider}' is disabled by request",
        "UNKNOWN_PROVIDER": f"provider '{provider}' is unknown in provider_config",
    }
    return reasons.get(availability, f"unknown availability status '{availability}'")


# ── Query / prompt dispatch ──────────────────────────────────────────────────


def _dispatch_inputs(
    candidate: dict,
    segment: dict,
) -> tuple[str, list]:
    query_strategy = candidate.get("queryStrategy", "search")
    if query_strategy == "generate":
        prompts = segment.get("generationPrompts")
        if isinstance(prompts, list):
            return "generationPrompts", list(prompts)
        return "generationPrompts", []
    else:
        queries = segment.get("searchQueries")
        if isinstance(queries, list):
            return "searchQueries", list(queries)
        return "searchQueries", []


# ── Live mode helpers ────────────────────────────────────────────────────────

_MIME_TO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _extension_from_mime(mime_type: str) -> str:
    return _MIME_TO_EXT.get(mime_type.lower(), ".bin")


def _extension_from_url(file_url: str) -> str:
    try:
        path = file_url.split("?")[0]
        name = path.rsplit("/", 1)[-1]
        if "." in name:
            ext = "." + name.rsplit(".", 1)[-1].lower()
            if 2 <= len(ext) <= 6:
                return ext
    except Exception:
        pass
    return ".bin"


def _determine_extension(candidate: dict) -> str:
    mime = (candidate.get("mimeType") or "").lower()
    if mime:
        ext = _extension_from_mime(mime)
        if ext != ".bin":
            return ext
    file_url = candidate.get("fileUrl", "")
    return _extension_from_url(file_url)


_NAMESPACE_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_asset_namespace(namespace: str) -> str | None:
    if not namespace or not isinstance(namespace, str):
        return "asset_namespace must be a non-empty string"
    if not _NAMESPACE_RE.match(namespace):
        return (
            f"asset_namespace '{namespace}' contains invalid characters; "
            "only ASCII letters, digits, hyphen and underscore are allowed"
        )
    return None


def _compute_asset_paths(
    job_dir: str,
    segment_index: int,
    candidate: dict,
    asset_namespace: str | None = None,
) -> tuple[str, Path]:
    ext = _determine_extension(candidate)
    if asset_namespace:
        filename = f"{asset_namespace}_seg_{segment_index:03d}{ext}"
    else:
        filename = f"seg_{segment_index:03d}{ext}"
    relative = f"assets/{filename}"
    absolute = Path(job_dir) / relative
    return relative, absolute


def _extract_query_texts(queries: list) -> list[str]:
    texts: list[str] = []
    for q in queries:
        if isinstance(q, str):
            t = q.strip()
            if t:
                texts.append(t)
        elif isinstance(q, dict):
            t = (q.get("text") or "").strip()
            if t:
                texts.append(t)
    return texts


# ── Diagnostics builder ──────────────────────────────────────────────────────


def _build_empty_diagnostics(
    job_dir: str | None = None,
    request_visuals_provided: bool = False,
) -> dict[str, Any]:
    return {
        "errors": [],
        "warnings": [],
        "providerAvailability": {},
        "jobDir": job_dir,
        "requestVisualsProvided": request_visuals_provided,
        "summary": {
            "totalSegments": 0,
            "dryRunAttempts": 0,
            "resolved": 0,
            "unresolved": 0,
            "providerUnavailable": 0,
            "noResults": 0,
            "downloadFailed": 0,
            "providerError": 0,
        },
    }


# ── Public API ───────────────────────────────────────────────────────────────


def execute_visual_sourcing_plan_v2(
    sourcing_plan: dict,
    provider_config: dict,
    request_visuals: dict | None = None,
    dry_run: bool = True,
    job_dir: str | None = None,
    asset_namespace: str | None = None,
    excluded_source_urls: set[str] | None = None,
    excluded_file_urls: set[str] | None = None,
    wikimedia_cache: dict[str, list] | None = None,
    provider_credentials: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Execute a v2 visual sourcing plan.

    Consumes the ``sourcingPlan`` from ``build_visual_sourcing_plan_v2``,
    evaluates provider availability, and returns resolved assets (live)
    or what would be attempted (dry-run).

    Live execution is implemented for ``wikimedia_commons`` only.
    All other providers return ``PROVIDER_UNAVAILABLE`` in live mode.

    Args:
        sourcing_plan: The ``sourcingPlan`` dict from
            ``build_visual_sourcing_plan_v2``.
        provider_config: Dict mapping provider names to their config, e.g.
            ``{"wikimedia_commons": {"enabled": true, "implemented": true,
            "requiresApiKey": false, "live": true}}``.
        request_visuals: Optional request-level config (stored for
            traceability only; not re-applied).
        dry_run: If ``True`` (default), returns dry-run attempt plan.
            If ``False``, attempts live Wikimedia resolution.
        job_dir: Job directory path for asset downloads (required in
            live mode).
        asset_namespace: Optional namespace prefix for asset filenames.
            When ``None`` (default), filenames use format
            ``assets/seg_NNN.ext``.  When set, filenames use format
            ``assets/{namespace}_seg_NNN.ext``.  Only ASCII letters,
            digits, hyphen and underscore are allowed.

    Returns:
        ``{ok, dryRun, resolvedAssets, unresolvedSegments,
           dryRunAttempts, diagnostics}``
    """
    diagnostics = _build_empty_diagnostics(
        job_dir,
        request_visuals is not None,
    )
    errors: list[dict] = diagnostics["errors"]
    warnings: list[dict] = diagnostics["warnings"]
    provider_availability: dict[str, str] = diagnostics["providerAvailability"]

    if asset_namespace is not None:
        ns_error = _validate_asset_namespace(asset_namespace)
        if ns_error is not None:
            errors.append(_err(
                "INVALID_INPUT:asset_namespace",
                ns_error,
                "asset_namespace",
            ))
            return {
                "ok": False,
                "dryRun": False,
                "resolvedAssets": [],
                "unresolvedSegments": [],
                "dryRunAttempts": [],
                "diagnostics": diagnostics,
            }

    # ── Live mode: require job_dir ───────────────────────────────────────
    if not dry_run and not job_dir:
        errors.append(_err(
            "JOB_DIR_REQUIRED_FOR_LIVE_EXECUTION",
            "job_dir is required when dry_run=False",
            "",
        ))
        return {
            "ok": False,
            "dryRun": False,
            "resolvedAssets": [],
            "unresolvedSegments": [],
            "dryRunAttempts": [],
            "diagnostics": diagnostics,
        }

    # ── Validate and sanitize provider config ─────────────────────────────
    provider_config = _validate_provider_config(provider_config, warnings)

    # Compute full provider availability map
    all_providers = sorted(
        {k for k in provider_config if isinstance(provider_config.get(k), dict)}
    )
    for provider in all_providers:
        provider_availability[provider] = _evaluate_provider_availability(
            provider, provider_config
        )
    if isinstance(sourcing_plan, dict):
        for seg in sourcing_plan.get("segments", []) or []:
            if not isinstance(seg, dict):
                continue
            for cand in seg.get("providerCandidates", []) or []:
                if not isinstance(cand, dict):
                    continue
                p = cand.get("provider", "")
                if p and p not in provider_availability:
                    provider_availability[p] = _evaluate_provider_availability(
                        p, provider_config
                    )

    # ── Validate sourcing plan shape ──────────────────────────────────────
    sp_errors = _validate_sourcing_plan(sourcing_plan)
    errors.extend(sp_errors)
    if sp_errors:
        return {
            "ok": False,
            "dryRun": dry_run,
            "resolvedAssets": [],
            "unresolvedSegments": [],
            "dryRunAttempts": [],
            "diagnostics": diagnostics,
        }

    segments = sourcing_plan.get("segments")
    if not isinstance(segments, list):
        segments = []

    diagnostics["summary"]["totalSegments"] = len(segments)

    unresolved_segments: list[dict] = []
    dry_run_attempts: list[dict] = []
    resolved_assets: list[dict] = []

    for idx, seg in enumerate(segments):
        if not isinstance(seg, dict):
            warnings.append(_warn(
                f"INVALID_SEGMENT:segments[{idx}]",
                f"segment at index {idx} is not a dict, skipping",
                f"segments[{idx}]",
            ))
            continue

        missing_keys = [k for k in REQUIRED_SEGMENT_KEYS if k not in seg]
        if missing_keys:
            for mk in missing_keys:
                errors.append(_err(
                    f"MISSING_SEGMENT_KEY:{idx}.{mk}",
                    f"segment at index {idx} missing key '{mk}'",
                    f"segments[{idx}].{mk}",
                ))
            continue

        segment_idx = seg.get("segmentIndex")
        asset_pref = seg.get("assetPreference", "")
        routing_status = seg.get("routingStatus", "")

        # ── Router UNROUTABLE → executor UNRESOLVED ────────────────────
        if routing_status == "UNROUTABLE":
            unresolved_segments.append({
                "segmentIndex": segment_idx,
                "assetPreference": asset_pref,
                "status": "UNRESOLVED",
                "reason": "Router marked segment as UNROUTABLE",
                "unsupportedReasons": list(
                    seg.get("unsupportedReasons", []) or []
                ),
            })
            diagnostics["summary"]["unresolved"] += 1
            continue

        candidates = seg.get("providerCandidates")
        if not isinstance(candidates, list):
            candidates = []

        if not candidates:
            unresolved_segments.append({
                "segmentIndex": segment_idx,
                "assetPreference": asset_pref,
                "status": "PROVIDER_UNAVAILABLE",
                "reason": "no provider candidates",
                "attemptedProviders": [],
            })
            diagnostics["summary"]["providerUnavailable"] += 1
            continue

        attempted: list[dict] = []
        selected_provider: str | None = None
        selected_candidate: dict | None = None

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue

            provider = candidate.get("provider", "")
            if not provider or "priority" not in candidate:
                continue

            candidate_status = candidate.get("candidateStatus", "")
            if candidate_status == "excluded":
                continue

            avail = _evaluate_provider_availability(provider, provider_config)
            entry: dict[str, Any] = {
                "provider": provider,
                "availability": avail,
                "wouldAttempt": avail == "AVAILABLE",
                "reason": _availability_reason(avail, provider),
            }
            attempted.append(entry)

            if selected_provider is None and avail == "AVAILABLE":
                selected_provider = provider
                selected_candidate = candidate

        # ── Dry-run path ─────────────────────────────────────────────────
        if dry_run:
            if selected_provider is not None and selected_candidate is not None:
                input_type, inputs = _dispatch_inputs(selected_candidate, seg)
                dry_run_attempts.append({
                    "segmentIndex": segment_idx,
                    "assetPreference": asset_pref,
                    "status": "SKIPPED_DRY_RUN",
                    "selectedProvider": selected_provider,
                    "queryStrategy": selected_candidate.get("queryStrategy", "search"),
                    "selectedInputType": input_type,
                    "selectedInputs": inputs,
                    "providerAvailability": "AVAILABLE",
                    "attemptedProviders": attempted,
                })
                diagnostics["summary"]["dryRunAttempts"] += 1
            else:
                unresolved_segments.append({
                    "segmentIndex": segment_idx,
                    "assetPreference": asset_pref,
                    "status": "PROVIDER_UNAVAILABLE",
                    "reason": (
                        "all provider candidates unavailable"
                        if attempted
                        else "no provider candidates remain after filtering"
                    ),
                    "attemptedProviders": attempted,
                })
                diagnostics["summary"]["providerUnavailable"] += 1
            continue

        # ── Live path: multi-provider failover ────────────────────────────
        provider_attempts: list[dict] = []
        resolved_result: dict | None = None
        resolved_strategy: str = ""
        last_non_terminal: dict | None = None

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue

            provider = candidate.get("provider", "")
            if not provider or "priority" not in candidate:
                continue

            candidate_status = candidate.get("candidateStatus", "")
            if candidate_status == "excluded":
                continue

            avail = _evaluate_provider_availability(provider, provider_config)

            if avail in ("NOT_IMPLEMENTED", "MISSING_API_KEY",
                         "DISABLED_BY_REQUEST", "UNKNOWN_PROVIDER"):
                provider_attempts.append({
                    "provider": provider,
                    "status": (
                        "PROVIDER_UNAVAILABLE" if avail != "MISSING_API_KEY"
                        else "MISSING_API_KEY"
                    ),
                    "reason": _availability_reason(avail, provider),
                })
                continue

            provider_result = _try_live_resolution(
                provider,
                candidate,
                seg,
                provider_config,
                str(job_dir),
                warnings,
                asset_namespace,
                excluded_source_urls=excluded_source_urls,
                excluded_file_urls=excluded_file_urls,
                wikimedia_cache=wikimedia_cache,
                provider_credentials=provider_credentials,
            )

            status = provider_result.get("status", "")
            reason = provider_result.get("reason", "")

            provider_attempts.append({
                "provider": provider,
                "status": status,
                "reason": reason,
            })

            if status == "INVALID_INPUT":
                unresolved_segments.append(provider_result)
                _increment_live_unresolved(provider_result, diagnostics)
                break

            if status == "RESOLVED":
                resolved_result = provider_result
                resolved_strategy = candidate.get("queryStrategy", "")
                break

            if status in ("PROVIDER_ERROR",):
                last_non_terminal = provider_result
                continue

            if status in ("NO_RESULTS", "DOWNLOAD_FAILED"):
                last_non_terminal = provider_result
                continue

            last_non_terminal = provider_result
            continue

        if resolved_result is not None:
            resolved_result["providerAttempts"] = provider_attempts
            if _search_semantic_ok(resolved_result, resolved_strategy):
                resolved_assets.append(resolved_result)
                diagnostics["summary"]["resolved"] += 1
            else:
                # Generic postcondition: a search-strategy RESOLVED result must
                # carry a RELEVANT semantic assessment. Never let it resolve.
                warnings.append(_warn(
                    "SEMANTIC_POSTCONDITION:RESOLVED",
                    f"segment {segment_idx} provider {resolved_result.get('provider', '')} "
                    "returned RESOLVED without a RELEVANT semanticAssessment",
                    "",
                ))
                unresolved_segments.append({
                    "segmentIndex": segment_idx,
                    "assetPreference": asset_pref,
                    "status": "PROVIDER_ERROR",
                    "provider": resolved_result.get("provider", ""),
                    "searchQueriesTried": resolved_result.get("searchQueriesTried", []),
                    "reason": "SEMANTIC POSTCONDITION VIOLATION: RESOLVED without RELEVANT semanticAssessment",
                    "providerAttempts": provider_attempts,
                })
                diagnostics["summary"]["providerError"] += 1
        else:
            if last_non_terminal is not None:
                last_non_terminal["providerAttempts"] = provider_attempts
                unresolved_segments.append(last_non_terminal)
                _increment_live_unresolved(last_non_terminal, diagnostics)
            else:
                unresolved_segments.append({
                    "segmentIndex": segment_idx,
                    "assetPreference": asset_pref,
                    "status": "PROVIDER_UNAVAILABLE",
                    "reason": (
                        "all provider candidates unavailable"
                        if attempted
                        else "no provider candidates remain after filtering"
                    ),
                    "attemptedProviders": attempted,
                    "providerAttempts": provider_attempts,
                })
                diagnostics["summary"]["providerUnavailable"] += 1

    return {
        "ok": len(errors) == 0,
        "dryRun": dry_run,
        "resolvedAssets": resolved_assets,
        "unresolvedSegments": unresolved_segments,
        "dryRunAttempts": dry_run_attempts,
        "diagnostics": diagnostics,
    }


def _search_semantic_ok(resolved: dict, strategy: str) -> bool:
    """Postcondition for search-strategy providers.

    A RESOLVED result from a search-strategy provider must carry a
    ``semanticAssessment`` whose ``verdict`` is ``RELEVANT``; otherwise the
    result is rejected and must never enter ``resolvedAssets``.  Generation
    (prompt) strategies legitimately carry no token-overlap assessment and are
    allowed through.  Provider-name agnostic: only the candidate's
    ``queryStrategy`` is consulted.
    """
    if strategy != "search":
        return True
    sem = resolved.get("semanticAssessment") or {}
    return sem.get("verdict") == RELEVANT


def _evaluate_semantic(segment: dict, candidate: dict) -> dict:
    """Score a candidate's semantic relevance to the segment expected intent.

    Expected intent = candidate's queryUsed (primary) + scene subjects.
    Returns the semantic assessment dict; the gate skips non-RELEVANT.
    """
    expected = {
        "query": candidate.get("queryUsed", "") or "",
        "subjects": segment.get("subjects") or [],
    }
    return assess_candidate(expected, candidate)


def _try_live_resolution(
    provider: str,
    candidate: dict,
    segment: dict,
    provider_config: dict,
    job_dir: str,
    warnings: list[dict],
    asset_namespace: str | None = None,
    excluded_source_urls: set[str] | None = None,
    excluded_file_urls: set[str] | None = None,
    wikimedia_cache: dict[str, list] | None = None,
    provider_credentials: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    if provider == "wikimedia_commons":
        return _resolve_wikimedia(
            candidate, segment, provider_config, job_dir, warnings,
            asset_namespace, excluded_source_urls, excluded_file_urls,
            wikimedia_cache,
        )

    if provider == "pixabay":
        return _resolve_pixabay(
            candidate, segment, job_dir, warnings,
            asset_namespace, excluded_source_urls, excluded_file_urls,
            provider_credentials,
        )

    segment_idx = segment.get("segmentIndex")
    asset_pref = segment.get("assetPreference", "")
    return {
        "segmentIndex": segment_idx,
        "assetPreference": asset_pref,
        "status": "PROVIDER_UNAVAILABLE",
        "reason": (
            f"live execution not implemented for provider '{provider}'; "
            "only wikimedia_commons and pixabay are supported"
        ),
    }


def _resolve_wikimedia(
    candidate: dict,
    segment: dict,
    provider_config: dict,
    job_dir: str,
    warnings: list[dict],
    asset_namespace: str | None = None,
    excluded_source_urls: set[str] | None = None,
    excluded_file_urls: set[str] | None = None,
    wikimedia_cache: dict[str, list] | None = None,
) -> dict[str, Any]:
    segment_idx = segment.get("segmentIndex")
    asset_pref = segment.get("assetPreference", "")

    wikimedia_cfg = provider_config.get("wikimedia_commons", {}) or {}
    if not isinstance(wikimedia_cfg, dict):
        wikimedia_cfg = {}
    live_enabled = wikimedia_cfg.get("live")
    if live_enabled is not True:
        return {
            "segmentIndex": segment_idx,
            "assetPreference": asset_pref,
            "status": "PROVIDER_UNAVAILABLE",
            "reason": (
                "wikimedia_commons provider is not marked live=true "
                "in provider_config"
            ),
        }

    user_agent = wikimedia_cfg.get("userAgent", None)

    _, queries = _dispatch_inputs(candidate, segment)
    query_texts = _extract_query_texts(queries)

    _MAX_DOWNLOAD_ATTEMPTS = 20

    try:
        from shorts_creator.assets.providers.wikimedia import (
            resolve_wikimedia_candidate_v2,
            download_wikimedia_asset_v2,
            WikimediaRateLimitedError,
        )

        download_errors: list[dict] = []
        semantic_rejections: list[dict] = []
        any_candidate_found = False

        for _attempt_idx in range(_MAX_DOWNLOAD_ATTEMPTS):
            resolved = resolve_wikimedia_candidate_v2(
                query_texts,
                user_agent=user_agent,
                excluded_source_urls=excluded_source_urls,
                excluded_file_urls=excluded_file_urls,
                cache=wikimedia_cache,
            )

            if resolved is None:
                break

            any_candidate_found = True

            if excluded_source_urls is not None:
                excluded_source_urls.add(resolved.get("sourceUrl", ""))
            if excluded_file_urls is not None:
                excluded_file_urls.add(resolved.get("fileUrl", ""))

            # ── Semantic gate: before download, skip irrelevant/unscorable ──
            semantic = _evaluate_semantic(segment, resolved)
            if semantic.get("verdict") != RELEVANT:
                semantic_rejections.append(semantic)
                continue

            relative_path, absolute_path = _compute_asset_paths(
                job_dir, segment_idx, resolved, asset_namespace,
            )

            dl_result = download_wikimedia_asset_v2(
                resolved,
                absolute_path,
                user_agent=user_agent,
            )

            if dl_result["ok"]:
                query_used = resolved.get("queryUsed", "")
                if not query_used and query_texts:
                    query_used = query_texts[0]
                return {
                    "segmentIndex": segment_idx,
                    "assetPreference": asset_pref,
                    "status": "RESOLVED",
                    "provider": "wikimedia_commons",
                    "assetPath": relative_path,
                    "fileSize": dl_result["size"],
                    "sourceUrl": resolved.get("sourceUrl", ""),
                    "fileUrl": resolved.get("fileUrl", ""),
                    "license": resolved.get("license", "unknown"),
                    "author": resolved.get("author", "Unknown"),
                    "mimeType": dl_result.get("mimeType")
                                or resolved.get("mimeType", ""),
                    "width": resolved.get("width", 0),
                    "height": resolved.get("height", 0),
                    "searchQueryUsed": query_used,
                    "generationPromptUsed": None,
                    "semanticAssessment": semantic,
                }

            if absolute_path.exists():
                absolute_path.unlink(missing_ok=True)

            download_errors.append({
                "sourceUrl": resolved.get("sourceUrl", ""),
                "fileUrl": resolved.get("fileUrl", ""),
                "error": dl_result.get("error", "download failed"),
            })

        if download_errors:
            return {
                "segmentIndex": segment_idx,
                "assetPreference": asset_pref,
                "status": "DOWNLOAD_FAILED",
                "provider": "wikimedia_commons",
                "searchQueriesTried": query_texts,
                "reason": "all download attempts failed",
                "downloadAttempts": len(download_errors),
                "downloadErrors": download_errors,
            }

        return {
            "segmentIndex": segment_idx,
            "assetPreference": asset_pref,
            "status": "NO_RESULTS",
            "provider": "wikimedia_commons",
            "searchQueriesTried": query_texts,
            "reason": "no candidate passed minimum filters",
            "semanticRejections": semantic_rejections,
        }

    except WikimediaRateLimitedError:
        return {
            "segmentIndex": segment_idx,
            "assetPreference": asset_pref,
            "status": "PROVIDER_ERROR",
            "provider": "wikimedia_commons",
            "searchQueriesTried": query_texts,
            "reason": "RATE_LIMITED",
        }

    except Exception as exc:
        warnings.append(_warn(
            "PROVIDER_ERROR:wikimedia_commons",
            f"Wikimedia provider error: {exc}",
            "",
        ))
        return {
            "segmentIndex": segment_idx,
            "assetPreference": asset_pref,
            "status": "PROVIDER_ERROR",
            "provider": "wikimedia_commons",
            "searchQueriesTried": query_texts,
            "reason": f"provider error: {exc}",
        }


def _resolve_pixabay(
    candidate: dict,
    segment: dict,
    job_dir: str,
    warnings: list[dict],
    asset_namespace: str | None = None,
    excluded_source_urls: set[str] | None = None,
    excluded_file_urls: set[str] | None = None,
    provider_credentials: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    segment_idx = segment.get("segmentIndex")
    asset_pref = segment.get("assetPreference", "")

    creds = provider_credentials or {}
    pixabay_creds = creds.get("pixabay", {}) or {}
    api_key = pixabay_creds.get("apiKey", "")

    if not api_key or not isinstance(api_key, str) or not api_key.strip():
        return {
            "segmentIndex": segment_idx,
            "assetPreference": asset_pref,
            "status": "MISSING_API_KEY",
            "provider": "pixabay",
            "reason": "PIXABAY_API_KEY not configured in provider_credentials",
        }

    _, queries = _dispatch_inputs(candidate, segment)
    query_texts = _extract_query_texts(queries)

    try:
        from shorts_creator.assets.providers.pixabay import (
            resolve_pixabay_candidates_v2,
            download_pixabay_asset_v2,
        )

        from pathlib import Path as _Path

        cache_dir = _Path("data/cache/pixabay-v2")

        candidates = resolve_pixabay_candidates_v2(
            query_texts,
            api_key=api_key,
            asset_preference=asset_pref,
            excluded_source_urls=excluded_source_urls,
            excluded_file_urls=excluded_file_urls,
            cache_dir=cache_dir,
            cache_ttl_sec=86400,
        )

        if not candidates:
            return {
                "segmentIndex": segment_idx,
                "assetPreference": asset_pref,
                "status": "NO_RESULTS",
                "provider": "pixabay",
                "searchQueriesTried": query_texts,
                "reason": "Pixabay returned no valid candidates",
            }

        _MAX_DOWNLOAD_ATTEMPTS = 20
        download_errors: list[dict] = []
        semantic_rejections: list[dict] = []

        for attempt in range(min(_MAX_DOWNLOAD_ATTEMPTS, len(candidates))):
            pix_candidate = candidates[attempt]

            if excluded_source_urls is not None:
                excluded_source_urls.add(pix_candidate.get("sourceUrl", ""))
            if excluded_file_urls is not None:
                excluded_file_urls.add(pix_candidate.get("fileUrl", ""))

            # ── Semantic gate: before download, skip irrelevant/unscorable ──
            semantic = _evaluate_semantic(segment, pix_candidate)
            if semantic.get("verdict") != RELEVANT:
                semantic_rejections.append(semantic)
                continue

            relative_path, absolute_path = _compute_asset_paths(
                job_dir, segment_idx, pix_candidate, asset_namespace,
            )

            dl_result = download_pixabay_asset_v2(
                pix_candidate,
                absolute_path,
            )

            if dl_result["ok"]:
                query_used = pix_candidate.get("queryUsed", "")
                if not query_used and query_texts:
                    query_used = query_texts[0]
                return {
                    "segmentIndex": segment_idx,
                    "assetPreference": asset_pref,
                    "status": "RESOLVED",
                    "provider": "pixabay",
                    "assetPath": relative_path,
                    "fileSize": dl_result["size"],
                    "sourceUrl": pix_candidate.get("sourceUrl", ""),
                    "fileUrl": pix_candidate.get("fileUrl", ""),
                    "license": pix_candidate.get("license", "Pixabay Content License"),
                    "author": pix_candidate.get("author", "Unknown"),
                    "mimeType": dl_result.get("mimeType") or "",
                    "width": dl_result.get("actualWidth",
                                          pix_candidate.get("width", 0)),
                    "height": dl_result.get("actualHeight",
                                           pix_candidate.get("height", 0)),
                    "searchQueryUsed": query_used,
                    "generationPromptUsed": None,
                    "tags": pix_candidate.get("tags", ""),
                    "pixabayId": pix_candidate.get("pixabayId"),
                    "semanticAssessment": semantic,
                }

            if absolute_path.exists():
                absolute_path.unlink(missing_ok=True)

            download_errors.append({
                "sourceUrl": pix_candidate.get("sourceUrl", ""),
                "fileUrl": pix_candidate.get("fileUrl", ""),
                "error": dl_result.get("error", "download failed"),
            })

        if download_errors:
            return {
                "segmentIndex": segment_idx,
                "assetPreference": asset_pref,
                "status": "DOWNLOAD_FAILED",
                "provider": "pixabay",
                "searchQueriesTried": query_texts,
                "reason": "all Pixabay download attempts failed",
                "downloadAttempts": len(download_errors),
                "downloadErrors": download_errors,
            }

        return {
            "segmentIndex": segment_idx,
            "assetPreference": asset_pref,
            "status": "NO_RESULTS",
            "provider": "pixabay",
            "searchQueriesTried": query_texts,
            "reason": "no Pixabay candidate downloaded successfully",
            "semanticRejections": semantic_rejections,
        }

    except ValueError as exc:
        return {
            "segmentIndex": segment_idx,
            "assetPreference": asset_pref,
            "status": "MISSING_API_KEY",
            "provider": "pixabay",
            "reason": str(exc),
        }

    except Exception as exc:
        error_msg = str(exc)
        if "401" in error_msg or "403" in error_msg or "AUTH" in error_msg.upper():
            reason = "AUTH_ERROR"
        elif "429" in error_msg:
            reason = "RATE_LIMITED"
        elif "timeout" in error_msg.lower() or "Network" in error_msg:
            reason = "NETWORK_ERROR"
        else:
            reason = f"provider error: {exc}"

        warnings.append(_warn(
            "PROVIDER_ERROR:pixabay",
            f"Pixabay provider error: {exc}",
            "",
        ))
        return {
            "segmentIndex": segment_idx,
            "assetPreference": asset_pref,
            "status": "PROVIDER_ERROR",
            "provider": "pixabay",
            "searchQueriesTried": query_texts,
            "reason": reason,
        }


def _increment_live_unresolved(
    result: dict,
    diagnostics: dict,
) -> None:
    status = result.get("status", "")
    summary = diagnostics["summary"]
    if status == "NO_RESULTS":
        summary["noResults"] += 1
    elif status == "DOWNLOAD_FAILED":
        summary["downloadFailed"] += 1
    elif status == "PROVIDER_ERROR":
        summary["providerError"] += 1
    elif status == "PROVIDER_UNAVAILABLE":
        summary["providerUnavailable"] += 1
    else:
        summary["unresolved"] += 1
