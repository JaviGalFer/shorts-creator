"""Visual Asset Bridge v2 — pure mapping from executor output to pipeline metadata.

Maps the output of ``execute_visual_sourcing_plan_v2`` into the
``metadata["assets"]`` shape expected by ``prepare_job.py``.

No I/O, no provider calls, no file checks, no runtime pipeline imports.
Deterministic.  Does not mutate input.  Stdlib only.
"""

from __future__ import annotations

import copy
from typing import Any

V2_LEGACY_FIELDS: frozenset[str] = frozenset({
    "editorialRole",
    "strategy",
    "primaryAssetType",
    "secondaryAssetType",
    "visualTemporalIntent",
})

RESOLVED_STATUS = "RESOLVED"

UNRESOLVED_STATUSES: frozenset[str] = frozenset({
    "UNRESOLVED",
    "NO_RESULTS",
    "DOWNLOAD_FAILED",
    "PROVIDER_ERROR",
    "PROVIDER_UNAVAILABLE",
})


# ── Internal helpers ─────────────────────────────────────────────────────────


def _scene_number(scene: dict, index: int) -> int:
    sn = scene.get("sceneNumber")
    if isinstance(sn, int) and not isinstance(sn, bool):
        return sn
    return index + 1


def _get_visual_sequence(scene: dict) -> list[dict]:
    vp = scene.get("visualPlan")
    if not isinstance(vp, dict):
        return []
    vs = vp.get("visualSequence")
    if not isinstance(vs, list):
        return []
    return [s for s in vs if isinstance(s, dict)]


def _build_segment_index(
    scenes: list[dict],
) -> dict[int, dict[int, dict]]:
    scene_index: dict[int, dict[int, dict]] = {}
    for i, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        sn = _scene_number(scene, i)
        vs = _get_visual_sequence(scene)
        seg_map: dict[int, dict] = {}
        for seg in vs:
            si = seg.get("segmentIndex")
            if isinstance(si, int) and not isinstance(si, bool):
                seg_map[si] = seg
        if seg_map:
            scene_index[sn] = seg_map
    return scene_index


def _build_match_queue(
    scene_index: dict[int, dict[int, dict]],
) -> list[tuple[int, int]]:
    queue: list[tuple[int, int]] = []
    for sn in sorted(scene_index.keys()):
        for si in sorted(scene_index[sn].keys()):
            queue.append((sn, si))
    return queue


def _get_explicit_slot(
    scene_index: dict[int, dict[int, dict]],
    claimed: set[tuple[int, int]],
    sn: int,
    si: int,
) -> tuple[tuple[int, int] | None, str | None]:
    """Resolve an explicit (sceneNumber, segmentIndex) pair.

    Returns ((sn, si), None) if valid and unclaimed, or (None, reason).
    """
    if sn not in scene_index:
        return None, f"sceneNumber {sn} not found in metadata scenes"
    if si not in scene_index.get(sn, {}):
        return None, f"segmentIndex {si} not found in scene {sn}"
    if (sn, si) in claimed:
        return None, (
            f"segment (sceneNumber={sn}, segmentIndex={si}) "
            "already claimed by another result"
        )
    return (sn, si), None


def _claim_segment(
    match_queue: list[tuple[int, int]],
    segment_index: int,
    claimed: set[tuple[int, int]],
) -> tuple[int, int] | None:
    """Fallback: claim first matching (sn, si) in match_queue by segmentIndex."""
    for entry in match_queue:
        sn, si = entry
        if si == segment_index and entry not in claimed:
            return entry
    return None


def _map_resolved_asset(
    asset: dict,
    vs_entry: dict,
) -> dict:
    segment: dict[str, Any] = {
        "segmentIndex": asset.get("segmentIndex"),
        "path": asset.get("assetPath"),
        "segmentValidationStatus": "PASS",
        "error": None,
        "assetType": asset.get("assetPreference", ""),
        "assetPreference": asset.get("assetPreference", ""),
        "provider": asset.get("provider", ""),
        "sourceUrl": asset.get("sourceUrl", ""),
        "fileUrl": asset.get("fileUrl", ""),
        "license": asset.get("license", ""),
        "author": asset.get("author", ""),
        "mimeType": asset.get("mimeType", ""),
        "mediaKind": asset.get("mediaKind", "IMAGE"),
        "width": asset.get("width"),
        "height": asset.get("height"),
        "sourceDurationSec": asset.get("sourceDurationSec"),
        "fps": asset.get("fps"),
        "score": asset.get("score", 0.0),
        "scoreReasons": list(asset.get("scoreReasons", []) or []),
        "queryUsed": asset.get("searchQueryUsed", ""),
        "generationPromptUsed": asset.get("generationPromptUsed"),
        "semanticAssessment": asset.get("semanticAssessment"),
        "semanticDegradation": asset.get("semanticDegradation"),
        "visualFidelityAssessment": asset.get("visualFidelityAssessment"),
        "durationFraction": vs_entry.get("durationFraction", 1.0),
        "transition": vs_entry.get("transition", "cut"),
        "mediaDecision": copy.deepcopy(asset["mediaDecision"]) if "mediaDecision" in asset else None,
        "mediaFallback": asset.get("mediaFallback", False),
    }

    for k in V2_LEGACY_FIELDS:
        segment.pop(k, None)

    if "mediaFallbackReason" in asset:
        segment["mediaFallbackReason"] = asset["mediaFallbackReason"]

    # Provider-specific provenance is additive so historical provider shapes
    # remain unchanged while future attribution/UI can consume primitives.
    for key in (
        "capabilityId", "providerAssetId", "pexelsPhotoId", "pexelsVideoId",
        "pexelsVideoFileId", "authorUrl",
        "queryIndex", "pexelsQueryRank", "providerRank", "selectorIdentity",
        "selectorScore", "pexelsRateLimitTelemetry",
    ):
        if key in asset:
            segment[key] = copy.deepcopy(asset[key])

    return segment


def _map_unresolved_segment(
    unresolved: dict,
    vs_entry: dict | None,
) -> dict:
    status = unresolved.get("status", "UNRESOLVED")
    error = unresolved.get("reason") or status

    segment: dict[str, Any] = {
        "segmentIndex": unresolved.get("segmentIndex"),
        "path": None,
        "segmentValidationStatus": "FAIL",
        "error": error,
        "assetType": unresolved.get("assetPreference", ""),
        "assetPreference": unresolved.get("assetPreference", ""),
        "provider": unresolved.get("provider", ""),
        "sourceUrl": "",
        "fileUrl": "",
        "license": "",
        "author": "",
        "mimeType": "",
        "mediaKind": unresolved.get("mediaKind", "IMAGE"),
        "capabilityId": unresolved.get("capabilityId"),
        "width": None,
        "height": None,
        "score": 0.0,
        "scoreReasons": [],
        "queryUsed": "",
        "generationPromptUsed": None,
        "durationFraction": (
            vs_entry.get("durationFraction", 1.0) if vs_entry else 1.0
        ),
        "transition": (
            vs_entry.get("transition", "cut") if vs_entry else "cut"
        ),
        "_executorStatus": status,
        "_reason": unresolved.get("reason", ""),
        "_searchQueriesTried": list(
            unresolved.get("searchQueriesTried", []) or []
        ),
        "_visualFidelityRejections": list(
            unresolved.get("visualFidelityRejections", []) or []
        ),
        "_attemptedProviders": list(
            unresolved.get("providerAttempts",
            unresolved.get("attemptedProviders", [])) or []
        ),
        "mediaDecision": copy.deepcopy(unresolved["mediaDecision"]) if "mediaDecision" in unresolved else None,
        "mediaFallback": unresolved.get("mediaFallback", False),
    }

    for k in V2_LEGACY_FIELDS:
        segment.pop(k, None)

    if "mediaFallbackReason" in unresolved:
        segment["mediaFallbackReason"] = unresolved["mediaFallbackReason"]

    return segment


def _ensure_no_v1_fields(obj: Any, path: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(obj, dict):
        for key in obj:
            if key in V2_LEGACY_FIELDS:
                violations.append(f"{path}.{key}")
            if isinstance(obj[key], (dict, list)):
                violations.extend(
                    _ensure_no_v1_fields(obj[key], f"{path}.{key}")
                )
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, (dict, list)):
                violations.extend(
                    _ensure_no_v1_fields(item, f"{path}[{i}]")
                )
    return violations


# ── Public API ───────────────────────────────────────────────────────────────


def apply_visual_assets_v2_to_metadata(
    metadata: dict,
    executor_result: dict,
    *,
    asset_base_dir: str = "assets",
) -> dict:
    """Map v2 executor output into the pipeline ``assets`` metadata shape.

    Returns a *new* dict.  The original *metadata* is never mutated.
    """
    result = copy.deepcopy(metadata)

    scenes: list[dict] = []
    raw_scenes = result.get("script", {}).get("scenes")
    if isinstance(raw_scenes, list):
        scenes = [s for s in raw_scenes if isinstance(s, dict)]

    resolved = executor_result.get("resolvedAssets")
    unresolved = executor_result.get("unresolvedSegments")
    if not isinstance(resolved, list):
        resolved = []
    if not isinstance(unresolved, list):
        unresolved = []

    scene_index = _build_segment_index(scenes)
    match_queue = _build_match_queue(scene_index)
    claimed: set[tuple[int, int]] = set()

    scene_assets: dict[int, dict[str, Any]] = {}
    for sn in scene_index:
        scene_assets[sn] = {
            "sceneNumber": sn,
            "selected": False,
            "segments": [],
        }
    for i, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        sn = _scene_number(scene, i)
        if sn not in scene_assets:
            scene_assets[sn] = {
                "sceneNumber": sn,
                "selected": False,
                "segments": [],
            }

    orphaned_results: list[dict] = []
    total_segments = 0
    resolved_count = 0
    failed_count = 0

    for asset in resolved:
        sn_explicit = asset.get("sceneNumber")
        si = asset.get("segmentIndex")

        claimed_entry = None

        if (
            isinstance(sn_explicit, int)
            and not isinstance(sn_explicit, bool)
            and isinstance(si, int)
            and not isinstance(si, bool)
        ):
            slot, orphan_reason = _get_explicit_slot(
                scene_index, claimed, sn_explicit, si,
            )
            if slot is not None:
                claimed_entry = slot
            else:
                orphaned_results.append({
                    "type": "resolved",
                    "sceneNumber": sn_explicit,
                    "segmentIndex": si,
                    "reason": orphan_reason,
                    "result": asset,
                })
                continue

        if claimed_entry is None:
            if not isinstance(si, int) or isinstance(si, bool):
                orphaned_results.append({
                    "type": "resolved",
                    "segmentIndex": si,
                    "reason": "invalid segmentIndex type",
                    "result": asset,
                })
                continue
            claimed_entry = _claim_segment(match_queue, si, claimed)
            if claimed_entry is None:
                orphaned_results.append({
                    "type": "resolved",
                    "segmentIndex": si,
                    "reason": "no matching visualSequence segment found",
                    "result": asset,
                })
                continue

        sn, _ = claimed_entry
        claimed.add(claimed_entry)
        vs_entry = scene_index[sn][si]

        seg = _map_resolved_asset(asset, vs_entry)
        scene_assets[sn]["segments"].append(seg)
        scene_assets[sn]["selected"] = True
        total_segments += 1
        resolved_count += 1

    for unresolved_item in unresolved:
        sn_explicit = unresolved_item.get("sceneNumber")
        si = unresolved_item.get("segmentIndex")

        claimed_entry = None

        if (
            isinstance(sn_explicit, int)
            and not isinstance(sn_explicit, bool)
            and isinstance(si, int)
            and not isinstance(si, bool)
        ):
            slot, orphan_reason = _get_explicit_slot(
                scene_index, claimed, sn_explicit, si,
            )
            if slot is not None:
                claimed_entry = slot
            else:
                orphaned_results.append({
                    "type": "unresolved",
                    "sceneNumber": sn_explicit,
                    "segmentIndex": si,
                    "reason": orphan_reason,
                    "result": unresolved_item,
                })
                continue

        if claimed_entry is None:
            if not isinstance(si, int) or isinstance(si, bool):
                orphaned_results.append({
                    "type": "unresolved",
                    "segmentIndex": si,
                    "reason": "invalid segmentIndex type",
                    "result": unresolved_item,
                })
                continue
            claimed_entry = _claim_segment(match_queue, si, claimed)
            if claimed_entry is None:
                orphaned_results.append({
                    "type": "unresolved",
                    "segmentIndex": si,
                    "reason": "no matching visualSequence segment found",
                    "result": unresolved_item,
                })
                continue

        sn, _ = claimed_entry
        claimed.add(claimed_entry)
        vs_entry = scene_index[sn][si]

        seg = _map_unresolved_segment(unresolved_item, vs_entry)
        scene_assets[sn]["segments"].append(seg)
        total_segments += 1
        failed_count += 1

    for sn, entry in scene_assets.items():
        seg_indices = {s["segmentIndex"] for s in entry["segments"]}
        for si in sorted(scene_index.get(sn, {}).keys()):
            if si not in seg_indices:
                missing = {
                    "segmentIndex": si,
                    "path": None,
                    "segmentValidationStatus": "FAIL",
                    "error": "no executor result for this segment",
                    "assetType": "",
                    "assetPreference": "",
                    "provider": "",
                    "sourceUrl": "",
                    "fileUrl": "",
                    "license": "",
                    "author": "",
                    "mimeType": "",
                    "mediaKind": "IMAGE",
                    "width": None,
                    "height": None,
                    "score": 0.0,
                    "scoreReasons": [],
                    "queryUsed": "",
                    "generationPromptUsed": None,
                    "mediaDecision": None,
                    "mediaFallback": False,
                    "durationFraction": scene_index[sn][si].get(
                        "durationFraction", 1.0
                    ),
                    "transition": scene_index[sn][si].get(
                        "transition", "cut"
                    ),
                }
                for k in V2_LEGACY_FIELDS:
                    missing.pop(k, None)
                scene_assets[sn]["segments"].append(missing)
                total_segments += 1
                failed_count += 1

    assets_array: list[dict] = []
    for sn in sorted(scene_assets.keys()):
        entry = scene_assets[sn]
        entry["segments"].sort(
            key=lambda s: (
                s.get("segmentIndex")
                if isinstance(s.get("segmentIndex"), int)
                else 0
            )
        )
        assets_array.append(entry)

    result["assets"] = assets_array
    result["_visualAssetBridgeV2"] = {
        "summary": {
            "scenes": len(scene_index),
            "segments": total_segments,
            "resolved": resolved_count,
            "failed": failed_count,
            "orphaned": len(orphaned_results),
        },
        "orphanedResults": orphaned_results,
    }

    return result
