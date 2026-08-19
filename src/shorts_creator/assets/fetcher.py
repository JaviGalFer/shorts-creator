"""fetch_images_v2.py — standalone v2 image-fetching CLI stage.

Chains the v2 visual stack:
    visual_plan_v2 → visual_asset_router_v2 → visual_asset_executor_v2
    → visual_asset_bridge_v2

Run:
    python3 bin/fetch_images_v2.py <metadata_path>
    python3 bin/fetch_images_v2.py <metadata_path> --dry-run
    python3 bin/fetch_images_v2.py <metadata_path> --user-agent "my-bot/1.0"
"""

from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

from shorts_creator.assets.bridge import apply_visual_assets_v2_to_metadata
from shorts_creator.assets.provider_credentials import resolve_api_key
from shorts_creator.assets.provider_config import load_provider_config_v2
from shorts_creator.contracts.visual import canonicalize_visual_plan_v2

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _resolve_pixabay_api_key() -> str | None:
    """Resolve PIXABAY_API_KEY from environment or .env file.

    Priority:
        1. os.environ["PIXABAY_API_KEY"]
        2. <project_root>/.env
        3. None

    Empty/whitespace-only values are treated as absent.
    No key values are printed, persisted, or exposed in configs.
    """
    return resolve_api_key("PIXABAY_API_KEY")


def _find_v2_scenes(metadata: dict) -> list[tuple[int, dict, dict]]:
    """Return [(scene_index, scene, visualPlan)] for scenes with v2 plans."""
    scenes = metadata.get("script", {}).get("scenes")
    if not isinstance(scenes, list):
        return []
    result: list[tuple[int, dict, dict]] = []
    for i, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        vp = scene.get("visualPlan")
        if not isinstance(vp, dict):
            continue
        if vp.get("_schemaVersion") != 2:
            continue
        result.append((i, scene, vp))
    return result


def _get_expected_segments(vp: dict) -> list[dict]:
    vs = vp.get("visualSequence")
    if not isinstance(vs, list):
        return []
    return [s for s in vs if isinstance(s, dict)]


def _make_synthetic_unresolved(
    segment: dict,
    status: str,
    reason: str,
    scene_number: int | None = None,
) -> dict:
    seg_index = segment.get("segmentIndex")
    asset_pref = segment.get("assetPreference", "unknown")
    if not isinstance(asset_pref, str):
        asset_pref = "unknown"
    result: dict = {
        "segmentIndex": seg_index,
        "assetPreference": asset_pref,
        "status": status,
        "provider": "v2_pipeline",
        "reason": reason,
    }
    if scene_number is not None:
        result["sceneNumber"] = scene_number
    return result


def _derive_status(metadata: dict) -> str:
    bridge = metadata.get("_visualAssetBridgeV2")
    if not isinstance(bridge, dict):
        return "ASSET_FAILED"
    summary = bridge.get("summary")
    if not isinstance(summary, dict):
        return "ASSET_FAILED"

    segments = summary.get("segments", 0)
    resolved = summary.get("resolved", 0)
    failed = summary.get("failed", 0)

    if segments == 0:
        return "ASSET_FAILED"
    if resolved == segments:
        return "ASSETS_READY"
    if resolved > 0 and failed > 0:
        return "ASSETS_PARTIAL"
    if resolved == 0 and failed > 0:
        return "ASSET_UNRESOLVED"
    return "ASSET_FAILED"


def _exit_code(status: str) -> int:
    if status in ("ASSETS_READY", "ASSETS_PARTIAL"):
        return 0
    return 1


def _atomic_write(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(str(tmp), str(path))
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise


def _print_summary(
    ok: bool,
    status: str,
    metadata_path: str,
    dry_run: bool,
    v2_scenes: int,
    summary: dict | None,
    warnings: list[str],
    errors: list[str],
) -> None:
    output: dict = {
        "ok": ok,
        "status": status,
        "metadataPath": metadata_path,
        "dryRun": dry_run,
        "v2Scenes": v2_scenes,
        "summary": summary,
        "warnings": warnings,
        "errors": errors,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


def _tag_results_with_scene_number(
    resolved: list[dict],
    unresolved: list[dict],
    scene_number: int,
) -> tuple[list[dict], list[dict]]:
    return (
        [dict(r, sceneNumber=scene_number) for r in resolved],
        [dict(u, sceneNumber=scene_number) for u in unresolved],
    )


def _process_scene(
    scene_index: int,
    scene: dict,
    vp: dict,
    provider_config: dict,
    dry_run: bool,
    job_dir: str,
    excluded_source_urls: set[str] | None = None,
    excluded_file_urls: set[str] | None = None,
    wikimedia_cache: dict[str, list] | None = None,
    provider_credentials: dict | None = None,
    request_visuals: dict | None = None,
) -> dict:
    from shorts_creator.assets.executor import execute_visual_sourcing_plan_v2
    from shorts_creator.assets.router import build_visual_sourcing_plan_v2

    expected = _get_expected_segments(vp)
    resolved: list[dict] = []
    unresolved: list[dict] = []

    scene_number = scene.get("sceneNumber")
    if not isinstance(scene_number, int) or isinstance(scene_number, bool) or scene_number <= 0:
        reason = (
            f"sceneNumber '{scene_number}' is not a positive integer; "
            "cannot generate asset namespace"
        )
        for seg in expected:
            unresolved.append(_make_synthetic_unresolved(
                seg, "INVALID_INPUT", reason,
            ))
        return {"resolved": resolved, "unresolved": unresolved}

    asset_namespace = f"scene_{scene_number:03d}"

    # Step a: canonicalize
    canon_result = canonicalize_visual_plan_v2(vp)
    if not canon_result.get("ok") or canon_result.get("canonicalPlan") is None:
        diag = canon_result.get("diagnostics", {})
        errors = diag.get("errors", [])
        reason = "canonicalizer failed"
        if errors:
            reason = f"canonicalizer failed: {errors[0].get('message', 'unknown error')}"
        for seg in expected:
            unresolved.append(_make_synthetic_unresolved(
                seg, "PROVIDER_ERROR", reason, scene_number=scene_number,
            ))
        resolved, unresolved = _tag_results_with_scene_number(
            resolved, unresolved, scene_number,
        )
        return {"resolved": resolved, "unresolved": unresolved}

    canonical_plan = canon_result["canonicalPlan"]

    # Step b: route
    route_result = build_visual_sourcing_plan_v2(
        canonical_plan, request_visuals=request_visuals
    )
    if not route_result.get("ok") or route_result.get("sourcingPlan") is None:
        diag = route_result.get("diagnostics", {})
        errors = diag.get("errors", [])
        reason = "router failed"
        if errors:
            reason = f"router failed: {errors[0].get('message', 'unknown error')}"
        for seg in expected:
            unresolved.append(_make_synthetic_unresolved(
                seg, "PROVIDER_ERROR", reason, scene_number=scene_number,
            ))
        resolved, unresolved = _tag_results_with_scene_number(
            resolved, unresolved, scene_number,
        )
        return {"resolved": resolved, "unresolved": unresolved}

    sourcing_plan = route_result["sourcingPlan"]

    # Step c: execute
    try:
        exec_result = execute_visual_sourcing_plan_v2(
            sourcing_plan=sourcing_plan,
            provider_config=provider_config,
            dry_run=dry_run,
            job_dir=job_dir,
            asset_namespace=asset_namespace,
            excluded_source_urls=excluded_source_urls,
            excluded_file_urls=excluded_file_urls,
            wikimedia_cache=wikimedia_cache,
            provider_credentials=provider_credentials,
        )
    except Exception as exc:
        reason = f"executor failed: {exc}"
        for seg in expected:
            unresolved.append(_make_synthetic_unresolved(
                seg, "PROVIDER_ERROR", reason, scene_number=scene_number,
            ))
        resolved, unresolved = _tag_results_with_scene_number(
            resolved, unresolved, scene_number,
        )
        return {"resolved": resolved, "unresolved": unresolved}

    # Step d: collect resolved/unresolved from executor, tag with sceneNumber
    exec_resolved = exec_result.get("resolvedAssets") or []
    exec_unresolved = exec_result.get("unresolvedSegments") or []
    if not isinstance(exec_resolved, list):
        exec_resolved = []
    if not isinstance(exec_unresolved, list):
        exec_unresolved = []

    resolved.extend(exec_resolved)
    unresolved.extend(exec_unresolved)

    # Ensure every expected segment has a result
    seen_seg_idx: set = set()
    for r in resolved:
        si = r.get("segmentIndex")
        if isinstance(si, int) and not isinstance(si, bool):
            seen_seg_idx.add(si)
    for u in unresolved:
        si = u.get("segmentIndex")
        if isinstance(si, int) and not isinstance(si, bool):
            seen_seg_idx.add(si)

    for seg in expected:
        si = seg.get("segmentIndex")
        if isinstance(si, int) and not isinstance(si, bool) and si not in seen_seg_idx:
            unresolved.append(_make_synthetic_unresolved(
                seg,
                "PROVIDER_UNAVAILABLE",
                "no executor result for expected segment",
                scene_number=scene_number,
            ))

    resolved, unresolved = _tag_results_with_scene_number(
        resolved, unresolved, scene_number,
    )
    return {"resolved": resolved, "unresolved": unresolved}


def fetch_assets(
    *,
    metadata_path: str | Path,
    dry_run: bool = False,
    user_agent: str | None = None,
) -> int:
    """Resolve Visual Assets V2 and persist their metadata atomically."""
    resolved_metadata_path = Path(metadata_path)
    job_dir = resolved_metadata_path.parent

    # 1. Load metadata
    try:
        metadata = json.loads(resolved_metadata_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        _print_summary(
            ok=False,
            status="ASSET_FAILED",
            metadata_path=str(resolved_metadata_path),
            dry_run=dry_run,
            v2_scenes=0,
            summary=None,
            warnings=[],
            errors=[f"failed to load metadata: {exc}"],
        )
        return 1

    # 2. Find v2 scenes
    v2_entries = _find_v2_scenes(metadata)

    request_visuals = metadata.get("request", {}).get("visuals")
    if not isinstance(request_visuals, dict):
        request_visuals = None

    # 3. No v2 plans → ASSET_FAILED
    if not v2_entries:
        metadata["status"] = "ASSET_FAILED"
        try:
            _atomic_write(resolved_metadata_path, metadata)
        except Exception as exc:
            _print_summary(
                ok=False,
                status="ASSET_FAILED",
                metadata_path=str(resolved_metadata_path),
                dry_run=dry_run,
                v2_scenes=0,
                summary=None,
                warnings=[],
                errors=[f"atomic write failed: {exc}"],
            )
            return 1
        _print_summary(
            ok=False,
            status="ASSET_FAILED",
            metadata_path=str(resolved_metadata_path),
            dry_run=dry_run,
            v2_scenes=0,
            summary=None,
            warnings=["no scenes with _schemaVersion == 2"],
            errors=[],
        )
        return 1

    # 4. Build provider config
    wikimedia_live = not dry_run
    pixabay_api_key = _resolve_pixabay_api_key()
    pixabay_key_present = bool(pixabay_api_key)
    pixabay_live = not dry_run
    source_providers = (request_visuals or {}).get("sourceProviders", [])
    pexels_requested = isinstance(source_providers, list) and "pexels" in source_providers
    pexels_api_key = resolve_api_key("PEXELS_API_KEY") if pexels_requested else None

    provider_config = load_provider_config_v2(
        wikimedia_live=wikimedia_live,
        user_agent=user_agent,
        pixabay_live=pixabay_live,
        pixabay_api_key_present=pixabay_key_present,
        pexels_enabled=pexels_requested,
        pexels_api_key_present=bool(pexels_api_key),
        pexels_live=not dry_run,
    )

    provider_credentials: dict | None = None
    if pixabay_key_present:
        provider_credentials = {
            "pixabay": {
                "apiKey": pixabay_api_key,
            },
        }
    if pexels_api_key:
        if provider_credentials is None:
            provider_credentials = {}
        provider_credentials["pexels"] = {"apiKey": pexels_api_key}

    # 5. Validate sceneNumbers are unique
    scene_numbers_seen: set[int] = set()
    for scene_index, scene, vp in v2_entries:
        sn = scene.get("sceneNumber")
        if isinstance(sn, int) and not isinstance(sn, bool) and sn > 0:
            if sn in scene_numbers_seen:
                metadata["status"] = "ASSET_FAILED"
                msg = f"duplicate sceneNumber {sn}; each scene must have a unique positive integer sceneNumber"
                try:
                    _atomic_write(resolved_metadata_path, metadata)
                except Exception:
                    pass
                _print_summary(
                    ok=False,
                    status="ASSET_FAILED",
                    metadata_path=str(resolved_metadata_path),
                    dry_run=dry_run,
                    v2_scenes=len(v2_entries),
                    summary=None,
                    warnings=[],
                    errors=[msg],
                )
                return 1
            scene_numbers_seen.add(sn)

    # 6. Process each v2 scene in order
    combined_resolved: list[dict] = []
    combined_unresolved: list[dict] = []
    scene_warnings: list[str] = []

    excluded_source_urls: set[str] = set()
    excluded_file_urls: set[str] = set()
    wikimedia_cache: dict[str, list] = {}

    for scene_index, scene, vp in v2_entries:
        result = _process_scene(
            scene_index=scene_index,
            scene=scene,
            vp=vp,
            provider_config=provider_config,
            dry_run=dry_run,
            job_dir=str(job_dir),
            excluded_source_urls=excluded_source_urls,
            excluded_file_urls=excluded_file_urls,
            wikimedia_cache=wikimedia_cache,
            provider_credentials=provider_credentials,
            request_visuals=request_visuals,
        )
        combined_resolved.extend(result["resolved"])
        combined_unresolved.extend(result["unresolved"])

    # 7. Apply bridge
    combined_executor_result = {
        "ok": True,
        "dryRun": dry_run,
        "resolvedAssets": combined_resolved,
        "unresolvedSegments": combined_unresolved,
        "dryRunAttempts": [],
        "diagnostics": {
            "errors": [],
            "warnings": [],
            "summary": {},
        },
    }

    updated_metadata = apply_visual_assets_v2_to_metadata(
        metadata, combined_executor_result,
    )

    # 8. Derive status
    status = _derive_status(updated_metadata)
    updated_metadata["status"] = status

    # 9. Atomic write
    try:
        _atomic_write(resolved_metadata_path, updated_metadata)
    except Exception as exc:
        _print_summary(
            ok=False,
            status="ASSET_FAILED",
            metadata_path=str(resolved_metadata_path),
            dry_run=dry_run,
            v2_scenes=len(v2_entries),
            summary=None,
            warnings=scene_warnings,
            errors=[f"atomic write failed: {exc}"],
        )
        return 1

    # 10. Build summary
    bridge_summary = updated_metadata.get("_visualAssetBridgeV2", {}).get("summary")
    if not isinstance(bridge_summary, dict):
        bridge_summary = {"scenes": 0, "segments": 0, "resolved": 0, "failed": 0, "orphaned": 0}

    ok = status in ("ASSETS_READY", "ASSETS_PARTIAL")

    _print_summary(
        ok=ok,
        status=status,
        metadata_path=str(resolved_metadata_path),
        dry_run=dry_run,
        v2_scenes=len(v2_entries),
        summary=bridge_summary,
        warnings=scene_warnings,
        errors=[],
    )

    return _exit_code(status)
