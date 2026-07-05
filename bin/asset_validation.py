#!/usr/bin/env python3
"""Asset validation for render quality gate. Ensures no placeholder/invalid asset reaches final MP4."""

import json
import re
from pathlib import Path
from typing import Any

MIN_ASSET_WIDTH = 720
MIN_ASSET_HEIGHT = 720
MIN_SCORE = 30

PLACEHOLDER_KEYWORDS = ["placeholder", "fallback", "no_image", "debug", "test_pattern"]

EDITORIAL_ROLE_COMPATIBILITY = {
    "context_map": ["historical_map", "map", "document", "illustration"],
    "battle_action": ["historical_photograph", "historical_art_or_document", "atmospheric_broll", "illustration"],
    "battle_or_assault": ["historical_photograph", "historical_art_or_document"],
    "border_closure_construction": ["historical_photograph", "historical_art_or_document"],
    "portrait": ["historical_photograph", "historical_art_or_document", "painting"],
    "aftermath": ["historical_photograph", "atmospheric_broll", "historical_art_or_document"],
    "document_or_date": ["document", "newspaper", "historical_map"],
    "civilian_impact": ["historical_photograph", "historical_art_or_document"],
    "consequence_or_legacy": ["historical_photograph", "historical_art_or_document", "reuse_previous_valid_asset"],
    "legacy": ["atmospheric_broll", "modern_photograph", "historical_photograph"],
    "abstract": ["atmospheric_broll", "generated_reconstruction", "illustration"],
    "unknown": None,
}

THEME_CONSTRAINTS: dict[str, dict] = {
    "La caída de Constantinopla": {
        "period": "Imperio Bizantino, 1453",
        "location": "Constantinopla",
        "entities": ["Imperio Bizantino", "Sultan Mehmed II", "Constantinopla"],
        "negativeKeywords": ["modern", "contemporary", "gun", "tank", "skyscraper", "21st", "futuristic", "selfie", "smartphone", "car"],
        "allowedAssetTypes": ["historical_map", "historical_photograph", "historical_art_or_document", "atmospheric_broll", "illustration", "map", "document", "painting"],
    }
}

LOW_CONFIDENCE_PROVIDERS = {"pollinations", "pexels"}

PLACEHOLDER_PROVIDER_PATTERNS = [re.compile(r, re.IGNORECASE) for r in [
    r"^placeholder$", r"^debug$", r"^test$", r"^fallback$", r"^pillow$",
]]


def _get_segment_asset(render_entry: dict, assets: list[dict]) -> dict | None:
    sn = render_entry.get("sceneNumber")
    si = render_entry.get("segmentIndex")
    for a in assets:
        if a.get("sceneNumber") == sn:
            for seg in a.get("segments", []):
                if seg.get("segmentIndex") == si:
                    return seg
    return None


def validate_asset_file(asset_path: str, project_root: Path, video_dir: Path | None = None) -> list[dict]:
    failures = []
    p = Path(asset_path)
    if not p.is_absolute():
        if video_dir is not None and str(asset_path).startswith("scenes/"):
            p = video_dir / asset_path
        else:
            p = project_root / asset_path
    if not p.exists():
        failures.append({"rule": "file_not_found", "message": f"Asset file not found: {asset_path}"})
        return failures
    try:
        from PIL import Image, ImageStat
        with Image.open(p) as img:
            w, h = img.size
            if w < MIN_ASSET_WIDTH and h < MIN_ASSET_HEIGHT:
                failures.append({
                    "rule": "dimensions_too_small",
                    "message": f"Asset {w}x{h} — both dimensions below min {MIN_ASSET_WIDTH}x{MIN_ASSET_HEIGHT}: {asset_path}"
                })
            stat = ImageStat.Stat(img)
            stddev = stat.stddev
            if stddev and all(s < 15 for s in stddev):
                mean = stat.mean
                if mean and all(80 < m < 200 for m in mean[:3]):
                    failures.append({
                        "rule": "uniform_background",
                        "message": f"Asset appears to be uniform gray background (stddev<15, mean~{mean[:3]}): {asset_path}"
                    })
    except Exception as e:
        failures.append({"rule": "not_decodable", "message": f"Asset cannot be decoded: {asset_path} ({e})"})
    return failures


def detect_placeholder_content(render_entry: dict, segment_asset: dict | None, asset_path: str) -> list[dict]:
    failures = []
    if segment_asset is None:
        failures.append({"rule": "no_asset_metadata", "message": f"No asset metadata for scene {render_entry.get('sceneNumber')} segment {render_entry.get('segmentIndex')}"})
        return failures

    provider = segment_asset.get("provider")
    if not provider:
        failures.append({"rule": "missing_provider", "message": f"No provider for scene {render_entry.get('sceneNumber')} segment {render_entry.get('segmentIndex')}"})
    else:
        for pattern in PLACEHOLDER_PROVIDER_PATTERNS:
            if pattern.search(str(provider)):
                failures.append({"rule": "placeholder_provider", "message": f"Provider '{provider}' is a placeholder/test provider"})
                break

    for kw in PLACEHOLDER_KEYWORDS:
        if kw.lower() in Path(asset_path).stem.lower():
            failures.append({"rule": "placeholder_filename", "message": f"Filename contains placeholder keyword '{kw}': {asset_path}"})
            break

    score = segment_asset.get("score")
    if score is not None and score < 0:
        failures.append({"rule": "negative_score", "message": f"Asset score {score} < 0 indicates rejection or fallback"})

    query = segment_asset.get("searchQuery")
    if score is None and query is None:
        failures.append({"rule": "no_provenance", "message": f"No score or query — asset has no provenance"})

    return failures


def validate_metadata_completeness(segment_asset: dict | None, render_entry: dict) -> list[dict]:
    failures = []
    if segment_asset is None:
        failures.append({"rule": "no_metadata", "message": "No metadata found"})
        return failures

    required_fields = {
        "provider": "No provider registered",
        "score": "No score registered",
        "assetType": "No assetType registered",
        "editorialRole": "No editorialRole registered",
    }
    for field, msg in required_fields.items():
        val = segment_asset.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            failures.append({"rule": f"missing_{field}", "message": msg})

    score = segment_asset.get("score")
    if score is not None and score < MIN_SCORE:
        failures.append({"rule": "score_below_minimum", "message": f"Score {score} < minimum {MIN_SCORE}"})

    source_url = segment_asset.get("sourceUrl")
    editorial_role = segment_asset.get("editorialRole")
    if editorial_role in ("context_map", "battle_action", "portrait") and not source_url:
        failures.append({"rule": "missing_source_url", "message": f"No sourceUrl for editorialRole={editorial_role}"})

    return failures


def check_editorial_coherence(render_entry: dict, segment_asset: dict | None, topic: str) -> list[dict]:
    failures = []
    if segment_asset is None:
        return failures

    asset_type = render_entry.get("assetType") or segment_asset.get("assetType", "")
    editorial_role = segment_asset.get("editorialRole", "unknown")

    allowed = EDITORIAL_ROLE_COMPATIBILITY.get(editorial_role)
    if allowed is not None and asset_type not in allowed:
        failures.append({
            "rule": "incompatible_asset_type",
            "message": f"assetType={asset_type} not compatible with editorialRole={editorial_role} (allowed: {allowed})"
        })

    constraints = THEME_CONSTRAINTS.get(topic)
    if constraints:
        if asset_type not in constraints.get("allowedAssetTypes", []):
            failures.append({
                "rule": "forbidden_asset_type",
                "message": f"assetType={asset_type} not allowed for theme '{topic}'"
            })
        query = (segment_asset.get("searchQuery") or "").lower()
        source_url = (segment_asset.get("sourceUrl") or "").lower()
        for nk in constraints.get("negativeKeywords", []):
            if nk.lower() in query or nk.lower() in source_url:
                failures.append({
                    "rule": "negative_keyword_match",
                    "message": f"Query/sourceUrl contains negative keyword '{nk}' for theme '{topic}'"
                })

    return failures


def check_provider_allowed(segment_asset: dict | None) -> list[dict]:
    failures = []
    if segment_asset is None:
        return failures
    provider = (segment_asset.get("provider") or "").lower()
    if provider in LOW_CONFIDENCE_PROVIDERS:
        failures.append({
            "rule": "low_confidence_provider",
            "message": f"Provider '{provider}' is low confidence (score may be unreliable)"
        })
    editorial_role = segment_asset.get("editorialRole", "")
    asset_type = segment_asset.get("assetType", "")
    if provider == "pollinations" and editorial_role not in ("abstract", "legacy"):
        failures.append({
            "rule": "ai_generated_misuse",
            "message": f"generated_reconstruction used for editorialRole={editorial_role} (only allowed for abstract/legacy)"
        })
    return failures


LEGACY_KEYWORDS = {
    "hoy", "hoy en día", "actual", "actualmente", "hoy día",
    "Estambul", "estambul", "moderno", "moderna", "legado", "consecuencia",
    "contemporáneo", "contemporánea", "presente", "hoy,",
    "en la actualidad", "a día de hoy", "todavía", "aún",
    "today", "present", "modern", "legacy", "istanbul",
}

SOFT_ROLES = {"consequence_or_legacy", "legacy"}

MODERN_PROVIDERS = {"pexels", "pixabay"}

MODERN_ASSET_TYPES = {"atmospheric_broll", "modern_photograph", "broll"}

MODERN_QUERY_KEYWORDS = [
    "istanbul", "estambul", "modern", "today", "present", "city",
    "street", "building", "contemporary", "skyline", "current",
]


def _is_modern_asset(segment: dict) -> bool:
    provider = (segment.get("provider") or "").lower()
    if provider in MODERN_PROVIDERS:
        return True
    asset_type = (segment.get("assetType") or "").lower()
    if asset_type in MODERN_ASSET_TYPES:
        return True
    query = (segment.get("searchQuery") or "").lower()
    for kw in MODERN_QUERY_KEYWORDS:
        if kw in query:
            return True
    return False


def _is_modern_street(segment: dict) -> bool:
    query = (segment.get("searchQuery") or "").lower()
    street_keywords = {"street", "calle", "avenida", "building", "edificio",
                       "skyline", "cityscape", "urban", "urbano", "plaza"}
    for kw in street_keywords:
        if kw in query:
            return True
    return False


def check_role_evidence(segment: dict, editorial_role: str) -> list[dict]:
    """Validate role-specific semantic evidence requirements (Fase 19)."""
    failures = []
    se = segment.get("semanticEvidence") or {}
    if editorial_role == "border_closure_construction":
        border_ev = se.get("borderClosureSubjectEvidence", [])
        if not border_ev:
            failures.append({
                "rule": "missing_border_closure_evidence",
                "message": f"border_closure_construction requires non-empty borderClosureSubjectEvidence, got {border_ev}",
            })
    if editorial_role == "consequence_or_legacy":
        # For event_depiction scenes, require depicted-date or fall/opening subject evidence.
        depicted = se.get("sourceDepictedDateEvidence", [])
        fall_open = se.get("fallOpeningSubjectEvidence", [])
        # Heuristic: validation only fails when neither is present AND the
        # scene's narration mentions an event year (handled by fetch_images hard
        # rule). For validation, we warn if both are empty for reused assets.
        if segment.get("reuseReason") == "reuse_previous_valid_asset" and not depicted and not fall_open:
            failures.append({
                "rule": "reused_asset_no_event_evidence",
                "message": "Reused asset for event_depiction lacks sourceDepictedDateEvidence and fallOpeningSubjectEvidence",
            })
    return failures


def check_reuse_compatibility(segment: dict, scene: dict) -> list[dict]:
    """Reject reuse where originalSceneNumber/role differs materially from target event."""
    failures = []
    if segment.get("reuseReason") != "reuse_previous_valid_asset":
        return failures
    orig_role = segment.get("originalEditorialRole") or segment.get("editorialRole", "")
    se = segment.get("semanticEvidence") or {}
    depicted = set(se.get("sourceDepictedDateEvidence", []))
    division_subj = se.get("divisionSubjectEvidence", [])
    fall_open = se.get("fallOpeningSubjectEvidence", [])
    # Extract target event year from scene voiceover
    target_years: set[str] = set()
    vo = (scene.get("voiceover") or "")
    for tok in vo.split():
        c = tok.strip(".,;:!?()[]{}'\"")
        if c.isdigit() and len(c) == 4:
            target_years.add(c)
    if target_years and depicted and not target_years.intersection(depicted):
        if orig_role == "civilian_impact":
            failures.append({
                "rule": "reuse_civilian_impact_for_distinct_event",
                "message": (f"Reused civilian_impact asset (depicted {sorted(depicted)}) "
                            f"cannot depict target event {sorted(target_years)}"),
            })
        if division_subj and not fall_open:
            failures.append({
                "rule": "reuse_division_subject_for_distinct_event",
                "message": (f"Reused division/family subject (divisionSubjectEvidence={division_subj[:2]}) "
                            f"incompatible with target event {sorted(target_years)}"),
            })
    return failures


def check_modern_asset_context(segment: dict, beat_text: str, editorial_role: str) -> list[dict]:
    if not _is_modern_asset(segment):
        return []
    if editorial_role not in SOFT_ROLES:
        return [{
            "rule": "modern_asset_hard_role",
            "message": f"Modern asset (provider={segment.get('provider')}) "
                       f"used in editorialRole='{editorial_role}' — only allowed in {SOFT_ROLES}"
        }]
    text_lower = beat_text.lower()
    has_legacy = any(kw in text_lower for kw in LEGACY_KEYWORDS)
    if not has_legacy:
        return [{
            "rule": "modern_asset_no_legacy_context",
            "message": f"Modern asset in {editorial_role} without legacy keywords in beat text"
        }]
    if _is_modern_street(segment) and "estambul" not in text_lower and "istanbul" not in text_lower:
        return [{
            "rule": "modern_asset_missing_city_context",
            "message": "Modern street/building asset without 'Estambul' in beat text"
        }]
    return []


def validate_job_for_render(metadata: dict, project_root: Path, video_dir: Path | None = None) -> dict:
    render_timeline = metadata.get("renderTimeline", [])
    assets = metadata.get("assets", [])
    topic = metadata.get("topic", "")
    scenes_list = metadata.get("script", {}).get("scenes", [])
    scene_by_num = {s["sceneNumber"]: s for s in scenes_list}
    if video_dir is None:
        video_dir = project_root / "data" / "videos" / metadata.get("jobId", "")
    failures = []
    per_segment = []

    for entry in render_timeline:
        sn = entry.get("sceneNumber")
        si = entry.get("segmentIndex")
        asset_path = entry.get("assetPath", "")
        seg_asset = _get_segment_asset(entry, assets)

        seg_result = {
            "sceneNumber": sn,
            "segmentIndex": si,
            "valid": True,
            "provider": seg_asset.get("provider") if seg_asset else None,
            "assetType": entry.get("assetType"),
            "editorialRole": seg_asset.get("editorialRole") if seg_asset else None,
            "score": seg_asset.get("score") if seg_asset else None,
            "query": seg_asset.get("searchQuery") if seg_asset else None,
            "failures": [],
        }

        file_issues = validate_asset_file(asset_path, project_root, video_dir)
        placeholder_issues = detect_placeholder_content(entry, seg_asset, asset_path)
        metadata_issues = validate_metadata_completeness(seg_asset, entry)
        coherence_issues = check_editorial_coherence(entry, seg_asset, topic)
        provider_issues = check_provider_allowed(seg_asset)

        # Renderability status check (from fetch_images pre-check)
        renderability_status = (seg_asset or {}).get("renderabilityStatus")
        renderability_issues = []
        if renderability_status == "FAIL":
            reasons = (seg_asset or {}).get("renderabilityReasons", [])
            renderability_issues.append({"rule": "renderability_fail", "message": f"Asset marked as unrenderable: {reasons}"})

        scene_data = scene_by_num.get(sn, {})
        beat_text = " ".join(
            b.get("text", "") for b in scene_data.get("narrativeBeats", [])
        ).strip() or scene_data.get("voiceover", "") or ""
        editorial_role = (seg_asset.get("editorialRole") if seg_asset else
                          entry.get("assetType", ""))
        # Role evidence / reuse compatibility checks (Fase 19)
        role_evidence_issues = check_role_evidence(seg_asset or {}, editorial_role)
        scene_data_for_reuse = scene_by_num.get(sn, {})
        reuse_issues = check_reuse_compatibility(seg_asset or {}, scene_data_for_reuse)

        modern_issues = check_modern_asset_context(
            seg_asset or {}, beat_text, editorial_role
        )

        all_issues = (file_issues + placeholder_issues + metadata_issues
                       + coherence_issues + provider_issues + modern_issues + renderability_issues
                       + role_evidence_issues + reuse_issues)
        seg_result["failures"] = all_issues
        if all_issues:
            seg_result["valid"] = False
            failures.extend(all_issues)

        per_segment.append(seg_result)

    has_placeholder = any(f["rule"] in ("placeholder_provider", "placeholder_filename", "no_asset_metadata", "missing_provider", "no_provenance", "file_not_found", "not_decodable") for f in failures)
    has_file_invalid = any(f["rule"] in ("file_not_found", "not_decodable", "dimensions_too_small") for f in failures)
    metadata_fail_count = sum(1 for f in failures if f["rule"].startswith("missing_"))
    has_editorial_fail = any(f["rule"] in ("incompatible_asset_type", "forbidden_asset_type", "negative_keyword_match") for f in failures)
    has_modern_fail = any(f["rule"].startswith("modern_asset_") for f in failures)
    score_below = any(f["rule"] == "score_below_minimum" for f in failures)

    if has_placeholder or has_file_invalid:
        status = "BLOCKED"
    elif has_modern_fail:
        status = "BLOCKED"
    elif metadata_fail_count >= 2 or has_editorial_fail:
        status = "BLOCKED"
    elif any(f["rule"] in ("missing_border_closure_evidence",
                           "reuse_civilian_impact_for_distinct_event",
                           "reuse_division_subject_for_distinct_event")
             for f in failures):
        status = "BLOCKED"
    elif any(f["rule"] == "reused_asset_no_event_evidence" for f in failures):
        status = "REVIEW_REQUIRED"
    elif metadata_fail_count == 1:
        status = "REVIEW_REQUIRED"
    elif score_below:
        status = "REVIEW_REQUIRED"
    else:
        status = "PASS"

    valid_count = sum(1 for s in per_segment if s["valid"])
    invalid_count = sum(1 for s in per_segment if not s["valid"])
    placeholder_count = sum(1 for s in per_segment if any(f["rule"] in ("placeholder_provider", "placeholder_filename", "no_asset_metadata", "missing_provider", "no_provenance") for f in s["failures"]))
    archive_count = sum(1 for s in per_segment if s.get("provider") in ("wikimedia_commons", "wikimedia"))
    broll_count = sum(1 for s in per_segment if s.get("provider") in ("pexels", "pixabay", "freeai"))
    ai_count = sum(1 for s in per_segment if s.get("provider") == "pollinations")
    manual_review = sum(1 for s in per_segment if any(f["rule"] in ("low_confidence_provider", "score_below_minimum", "negative_score") for f in s["failures"]))

    result = {
        "status": status,
        "failures": failures[:50],
        "perSegment": per_segment,
        "summary": {
            "totalSegments": len(render_timeline),
            "validAssets": valid_count,
            "invalidAssets": invalid_count,
            "placeholdersDetected": placeholder_count,
            "renderBlocked": status == "BLOCKED",
            "assetsFromArchive": archive_count,
            "assetsFromBroll": broll_count,
            "assetsFromAI": ai_count,
            "scenesRequiringManualReview": manual_review,
        }
    }
    return result


if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1]).resolve()
    project_root = path.parents[3]
    video_dir = path.parent
    metadata = json.loads(path.read_text())
    result = validate_job_for_render(metadata, project_root, video_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
