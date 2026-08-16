"""Tests for shorts_creator.validation.asset v2-neutral metadata support.

Verifies that v2 metadata (marked by _visualAssetBridgeV2) passes asset validation
without requiring v1 legacy fields (editorialRole, etc.), while v1 behavior is preserved.

Run: python3 -m pytest tests/test_asset_validation_v2_neutral_metadata.py -v
"""

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "bin"))

import pytest

import shorts_creator.validation.asset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MIN_SCORE = shorts_creator.validation.asset.MIN_SCORE


def _make_test_image(path: Path, width: int = 1200, height: int = 800) -> None:
    """Create a valid JPEG image with the given dimensions (non-uniform to avoid background detection)."""
    from PIL import Image, ImageDraw
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (width, height), color=(80, 60, 50))
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, width - 50, height - 50], fill=(180, 160, 140))
    draw.rectangle([100, 100, width - 100, height - 100], fill=(200, 190, 170))
    img.save(path, "JPEG")


def _build_v2_metadata(
    job_id: str = "test-v2-001",
    assets: list[dict] | None = None,
    render_timeline: list[dict] | None = None,
    **extra,
) -> dict:
    """Build minimal v2 metadata with _visualAssetBridgeV2 marker."""
    md = {
        "jobId": job_id,
        "topic": "history",
        "script": {"scenes": []},
        "_visualAssetBridgeV2": {
            "summary": {"scenes": 1, "segments": 1, "resolved": 1, "failed": 0, "orphaned": 0},
        },
        "assets": assets or [],
        "renderTimeline": render_timeline or [],
    }
    md.update(extra)
    return md


def _build_v1_metadata(
    job_id: str = "test-v1-001",
    assets: list[dict] | None = None,
    render_timeline: list[dict] | None = None,
    **extra,
) -> dict:
    """Build minimal v1 metadata WITHOUT _visualAssetBridgeV2."""
    md = {
        "jobId": job_id,
        "topic": "history",
        "script": {"scenes": []},
        "assets": assets or [],
        "renderTimeline": render_timeline or [],
    }
    md.update(extra)
    return md


def _v2_segment(**overrides) -> dict:
    """Build a representative v2 neutral segment."""
    seg = {
        "segmentIndex": 1,
        "path": "assets/seg_001.jpg",
        "segmentValidationStatus": "PASS",
        "error": None,
        "assetType": "photograph",
        "assetPreference": "photograph",
        "provider": "wikimedia_commons",
        "sourceUrl": "https://commons.wikimedia.org/wiki/File:Test.jpg",
        "fileUrl": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Test.jpg",
        "license": "Public Domain",
        "author": "Test Author",
        "mimeType": "image/jpeg",
        "width": 1200,
        "height": 800,
        "score": 0.0,
        "scoreReasons": [],
        "queryUsed": "historical test query",
        "generationPromptUsed": None,
    }
    seg.update(overrides)
    return seg


def _v1_segment(**overrides) -> dict:
    """Build a representative v1 segment with editorialRole and searchQuery."""
    seg = {
        "segmentIndex": 1,
        "path": "scenes/scene-01.jpg",
        "segmentValidationStatus": "PASS",
        "error": None,
        "assetType": "historical_photograph",
        "provider": "wikimedia_commons",
        "editorialRole": "portrait",
        "sourceUrl": "https://commons.wikimedia.org/wiki/File:Test.jpg",
        "fileUrl": "https://upload.wikimedia.org/...",
        "license": "Public Domain",
        "author": "Test",
        "width": 1200,
        "height": 800,
        "score": 80,
        "searchQuery": "Napoleon portrait painting",
    }
    seg.update(overrides)
    return seg


def _v2_asset_entry(scene_number: int = 1, selected: bool = True, segments: list[dict] | None = None) -> dict:
    return {
        "sceneNumber": scene_number,
        "selected": selected,
        "segments": segments or [_v2_segment()],
    }


def _v1_asset_entry(scene_number: int = 1, selected: bool = True, segments: list[dict] | None = None) -> dict:
    return {
        "sceneNumber": scene_number,
        "selected": selected,
        "segments": segments or [_v1_segment()],
    }


def _render_entry(asset_path: str = "assets/seg_001.jpg", asset_type: str = "photograph",
                  scene_number: int = 1, segment_index: int = 1) -> dict:
    return {
        "sceneNumber": scene_number,
        "segmentIndex": segment_index,
        "assetPath": asset_path,
        "assetType": asset_type,
        "startSec": 0.0,
        "endSec": 6.0,
        "durationSec": 6.0,
        "beatIndex": 1,
        "transitionIn": "cut",
        "transitionOut": "fade",
        "motionType": "static",
        "overlayText": "",
        "overlayEnabled": False,
        "subtitleCueIndexes": [],
        "audioPath": "",
    }


def _setup_job_dir(base: Path, asset_rel_path: str = "assets/seg_001.jpg",
                   create_file: bool = True) -> tuple[Path, Path]:
    """Create a video_dir with optional asset file. Returns (project_root, video_dir)."""
    project_root = base / "project"
    video_dir = project_root / "data" / "videos" / "job001"
    video_dir.mkdir(parents=True)
    if create_file:
        asset_path = video_dir / asset_rel_path
        _make_test_image(asset_path)
    return project_root, video_dir


# =========================================================================
# V2 TESTS
# =========================================================================


# ---------------------------------------------------------------------------
# Test 1: clean v2 Wikimedia asset -> PASS
# ---------------------------------------------------------------------------

def test_v2_neutral_wikimedia_passes(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path)

    metadata = _build_v2_metadata(
        assets=[_v2_asset_entry()],
        render_timeline=[_render_entry()],
    )

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    failures = result["failures"]

    assert result["status"] == "PASS", f"Expected PASS, got {result['status']}: {failures}"
    assert not any(f["rule"] == "missing_editorialRole" for f in failures)
    assert not any(f["rule"] == "score_below_minimum" for f in failures)
    assert not any(f["rule"] == "no_provenance" for f in failures)
    assert result["summary"]["validAssets"] == 1
    assert result["summary"]["invalidAssets"] == 0


# ---------------------------------------------------------------------------
# Test 2: missing file -> BLOCKED
# ---------------------------------------------------------------------------

def test_v2_missing_file_blocked(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path, create_file=False)

    metadata = _build_v2_metadata(
        assets=[_v2_asset_entry(segments=[_v2_segment(path="assets/missing.jpg")])],
        render_timeline=[_render_entry(asset_path="assets/missing.jpg")],
    )

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    assert result["status"] == "BLOCKED"
    assert any(f["rule"] == "file_not_found" for f in result["failures"])


# ---------------------------------------------------------------------------
# Test 3: missing provider -> BLOCKED
# ---------------------------------------------------------------------------

def test_v2_missing_provider_blocked(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path)

    metadata = _build_v2_metadata(
        assets=[_v2_asset_entry(segments=[_v2_segment(provider="")])],
        render_timeline=[_render_entry()],
    )

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    assert result["status"] == "BLOCKED"
    assert any(f["rule"] == "missing_provider" for f in result["failures"])


# ---------------------------------------------------------------------------
# Test 4: score=0.0 + queryUsed -> no score_below_minimum, no no_provenance
# ---------------------------------------------------------------------------

def test_v2_score_zero_with_query_used_no_failures(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path)

    metadata = _build_v2_metadata(
        assets=[_v2_asset_entry(segments=[_v2_segment(score=0.0, queryUsed="some query")])],
        render_timeline=[_render_entry()],
    )

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    assert not any(f["rule"] == "score_below_minimum" for f in result["failures"])
    assert not any(f["rule"] == "no_provenance" for f in result["failures"])


# ---------------------------------------------------------------------------
# Test 5: score=0.0, no queryUsed, no searchQuery -> no_provenance
# ---------------------------------------------------------------------------

def test_v2_score_zero_no_query_no_provenance(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path)

    metadata = _build_v2_metadata(
        assets=[_v2_asset_entry(segments=[_v2_segment(score=0.0, queryUsed="")])],
        render_timeline=[_render_entry()],
    )
    metadata["assets"][0]["segments"][0].pop("searchQuery", None)
    metadata["assets"][0]["segments"][0]["queryUsed"] = ""

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    assert any(f["rule"] == "no_provenance" for f in result["failures"])
    assert result["status"] == "BLOCKED"


# ---------------------------------------------------------------------------
# Test 6: score=None, no queryUsed -> no_provenance
# ---------------------------------------------------------------------------

def test_v2_score_none_no_query_no_provenance(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path)

    metadata = _build_v2_metadata(
        assets=[_v2_asset_entry(segments=[_v2_segment(score=None, queryUsed="")])],
        render_timeline=[_render_entry()],
    )
    metadata["assets"][0]["segments"][0].pop("searchQuery", None)

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    assert any(f["rule"] == "no_provenance" for f in result["failures"])
    assert result["status"] == "BLOCKED"


# ---------------------------------------------------------------------------
# Test 7: positive score below MIN_SCORE -> score_below_minimum
# ---------------------------------------------------------------------------

def test_v2_positive_score_below_min_raises_score_below_minimum(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path)

    low_score = MIN_SCORE - 1
    metadata = _build_v2_metadata(
        assets=[_v2_asset_entry(segments=[_v2_segment(score=low_score)])],
        render_timeline=[_render_entry()],
    )

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    assert any(f["rule"] == "score_below_minimum" for f in result["failures"])
    assert result["status"] == "REVIEW_REQUIRED"


# ---------------------------------------------------------------------------
# Test 8: negative score -> negative_score, BLOCKED
# ---------------------------------------------------------------------------

def test_v2_negative_score_detected_and_blocked(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path)

    metadata = _build_v2_metadata(
        assets=[_v2_asset_entry(segments=[_v2_segment(score=-5)])],
        render_timeline=[_render_entry()],
    )

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    assert any(f["rule"] == "negative_score" for f in result["failures"])
    assert result["status"] == "BLOCKED"


# ---------------------------------------------------------------------------
# Test 9: Pollinations v2 -> low_confidence_provider, REVIEW_REQUIRED
# ---------------------------------------------------------------------------

def test_v2_pollinations_low_confidence_review_required(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path, asset_rel_path="assets/seg_001.jpg")

    metadata = _build_v2_metadata(
        assets=[_v2_asset_entry(segments=[_v2_segment(provider="pollinations", queryUsed="some prompt",
                                                       sourceUrl="", fileUrl="", license="",
                                                       author="")])],
        render_timeline=[_render_entry()],
    )

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    failures = result["failures"]
    assert any(f["rule"] == "low_confidence_provider" for f in failures)
    assert not any(f["rule"] == "ai_generated_misuse" for f in failures)
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["summary"]["invalidAssets"] == 1
    assert result["summary"]["scenesRequiringManualReview"] == 1


# ---------------------------------------------------------------------------
# Test 10: unresolved v2 segment (segmentValidationStatus=FAIL) -> BLOCKED
# ---------------------------------------------------------------------------

def test_v2_segment_validation_fail_blocks(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path)

    metadata = _build_v2_metadata(
        assets=[_v2_asset_entry(segments=[_v2_segment(
            path="assets/seg_001.jpg",
            segmentValidationStatus="FAIL",
            error="download failed",
        )])],
        render_timeline=[_render_entry()],
    )

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    assert result["status"] == "BLOCKED"
    assert any(f["rule"] == "segment_validation_fail" for f in result["failures"])


# ---------------------------------------------------------------------------
# Test 11: renderabilityStatus FAIL with existing file -> BLOCKED
# ---------------------------------------------------------------------------

def test_v2_renderability_fail_blocks(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path)

    metadata = _build_v2_metadata(
        assets=[_v2_asset_entry(segments=[_v2_segment(
            path="assets/seg_001.jpg",
            renderabilityStatus="FAIL",
            renderabilityReasons=["image is corrupt"],
        )])],
        render_timeline=[_render_entry()],
    )

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    assert result["status"] == "BLOCKED"
    assert any(f["rule"] == "renderability_fail" for f in result["failures"])


# ---------------------------------------------------------------------------
# Test 12: Pexels v2 -> PASS, no low_confidence_provider, no modern rules
# ---------------------------------------------------------------------------

def test_v2_pexels_passes_no_low_confidence(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path)

    metadata = _build_v2_metadata(
        assets=[_v2_asset_entry(segments=[_v2_segment(
            provider="pexels",
            assetType="photograph",
            queryUsed="city street",
        )])],
        render_timeline=[_render_entry(asset_type="photograph")],
    )

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    failures = result["failures"]

    assert result["status"] == "PASS", f"Expected PASS, got {result['status']}: {failures}"
    assert not any(f["rule"] == "low_confidence_provider" for f in failures)
    assert not any(f["rule"] == "modern_asset_hard_role" for f in failures)
    assert not any(f["rule"] == "modern_asset_no_legacy_context" for f in failures)
    assert not any(f["rule"] == "ai_generated_misuse" for f in failures)


# ---------------------------------------------------------------------------
# Test 13: Pixabay v2 -> PASS, no modern rules
# ---------------------------------------------------------------------------

def test_v2_pixabay_passes_no_modern_rules(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path)

    metadata = _build_v2_metadata(
        assets=[_v2_asset_entry(segments=[_v2_segment(
            provider="pixabay",
            assetType="photograph",
            queryUsed="historical building",
        )])],
        render_timeline=[_render_entry(asset_type="photograph")],
    )

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    failures = result["failures"]

    assert result["status"] == "PASS", f"Expected PASS, got {result['status']}: {failures}"
    assert not any(f["rule"] == "low_confidence_provider" for f in failures)
    assert not any(f["rule"] == "modern_asset_hard_role" for f in failures)
    assert not any(f["rule"] == "modern_asset_no_legacy_context" for f in failures)


# ---------------------------------------------------------------------------
# Test 14: v2 perSegment diagnostic exposes queryUsed correctly
# ---------------------------------------------------------------------------

def test_v2_per_segment_query_uses_query_used(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path)

    metadata = _build_v2_metadata(
        assets=[_v2_asset_entry()],
        render_timeline=[_render_entry(asset_type="photograph")],
    )

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    per_seg = result["perSegment"][0]
    assert per_seg["query"] == "historical test query"


# ---------------------------------------------------------------------------
# Test 15: no legacy fields persist in v2 metadata after validation
# ---------------------------------------------------------------------------

def test_v2_no_legacy_fields_added(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path)

    metadata = _build_v2_metadata(
        assets=[_v2_asset_entry()],
        render_timeline=[_render_entry()],
    )

    original_snapshot = json.loads(json.dumps(metadata))

    shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)

    # metadata dict should not have been mutated (no v1 fields injected into assets)
    for entry in metadata.get("assets", []):
        for seg in entry.get("segments", []):
            assert "editorialRole" not in seg, "editorialRole should not exist in v2 metadata after validation"
            assert "strategy" not in seg, "strategy should not exist in v2 metadata after validation"
            assert "primaryAssetType" not in seg, "primaryAssetType should not exist in v2 metadata after validation"
            assert "secondaryAssetType" not in seg, "secondaryAssetType should not exist in v2 metadata after validation"
            assert "visualTemporalIntent" not in seg, "visualTemporalIntent should not exist in v2 metadata after validation"
            assert "searchQuery" not in seg, "searchQuery should not be added to v2 metadata"

    # verify that the original shape is unchanged (deep equality on assets)
    assert metadata["_visualAssetBridgeV2"] == original_snapshot["_visualAssetBridgeV2"]
    for i, entry in enumerate(metadata.get("assets", [])):
        orig_entry = original_snapshot["assets"][i]
        for seg, orig_seg in zip(entry.get("segments", []), orig_entry.get("segments", [])):
            for k in orig_seg:
                assert k in seg, f"Key '{k}' missing from segment after validation"
                assert seg[k] == orig_seg[k], f"Key '{k}' changed: {orig_seg[k]} -> {seg[k]}"


# ---------------------------------------------------------------------------
# Test 16: legacy semantic rules NOT executed for v2
# ---------------------------------------------------------------------------

def test_v2_no_legacy_semantic_rules_executed(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path)

    metadata = _build_v2_metadata(
        assets=[_v2_asset_entry(segments=[_v2_segment(
            provider="pexels",
            assetType="modern_photograph",
            queryUsed="modern city street today",
        )])],
        render_timeline=[_render_entry(asset_type="modern_photograph")],
    )

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    failures = result["failures"]

    # None of these v1 legacy rules should fire for v2 metadata
    assert not any(f["rule"] == "incompatible_asset_type" for f in failures)
    assert not any(f["rule"] == "modern_asset_hard_role" for f in failures)
    assert not any(f["rule"] == "modern_asset_no_legacy_context" for f in failures)
    assert not any(f["rule"] == "missing_border_closure_evidence" for f in failures)
    assert not any(f["rule"] == "reused_asset_no_event_evidence" for f in failures)
    assert not any(f["rule"] == "reuse_civilian_impact_for_distinct_event" for f in failures)
    assert not any(f["rule"] == "reuse_division_subject_for_distinct_event" for f in failures)


# =========================================================================
# V1 REGRESSION TESTS
# =========================================================================


# ---------------------------------------------------------------------------
# Test 17: v1 without marker -> missing_editorialRole still fires
# ---------------------------------------------------------------------------

def test_v1_legacy_editorial_role_still_required(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path, asset_rel_path="scenes/scene-01.jpg")

    metadata = _build_v1_metadata(
        assets=[_v1_asset_entry(segments=[_v1_segment(editorialRole=None)])],
        render_timeline=[_render_entry(asset_path="scenes/scene-01.jpg", asset_type="historical_photograph")],
    )
    metadata["assets"][0]["segments"][0].pop("editorialRole", None)

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    assert any(f["rule"] == "missing_editorialRole" for f in result["failures"])


# ---------------------------------------------------------------------------
# Test 18: v1 score=0.0 triggers score_below_minimum
# ---------------------------------------------------------------------------

def test_v1_legacy_score_zero_triggers_score_below_minimum(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path, asset_rel_path="scenes/scene-01.jpg")

    metadata = _build_v1_metadata(
        assets=[_v1_asset_entry(segments=[_v1_segment(score=0.0, editorialRole="portrait")])],
        render_timeline=[_render_entry(asset_path="scenes/scene-01.jpg", asset_type="historical_photograph")],
    )

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    assert any(f["rule"] == "score_below_minimum" for f in result["failures"])


# ---------------------------------------------------------------------------
# Test 19: v1 searchQuery still works
# ---------------------------------------------------------------------------

def test_v1_legacy_search_query_still_works(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path, asset_rel_path="scenes/scene-01.jpg")

    metadata = _build_v1_metadata(
        assets=[_v1_asset_entry()],
        render_timeline=[_render_entry(asset_path="scenes/scene-01.jpg", asset_type="historical_photograph")],
    )

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    per_seg = result["perSegment"][0]
    assert per_seg["query"] == "Napoleon portrait painting"


# ---------------------------------------------------------------------------
# Test 20: v1 Pollinations -> ai_generated_misuse + low_confidence_provider preserved
# ---------------------------------------------------------------------------

def test_v1_pollinations_ai_misuse_preserved(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path, asset_rel_path="scenes/scene-01.jpg")

    metadata = _build_v1_metadata(
        assets=[_v1_asset_entry(segments=[_v1_segment(
            provider="pollinations",
            score=70,
            editorialRole="portrait",
            searchQuery="some prompt",
            sourceUrl="",
            fileUrl="",
            license="",
            author="",
        )])],
        render_timeline=[_render_entry(asset_path="scenes/scene-01.jpg", asset_type="historical_photograph")],
    )

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    assert any(f["rule"] == "ai_generated_misuse" for f in result["failures"])
    assert any(f["rule"] == "low_confidence_provider" for f in result["failures"])


# ---------------------------------------------------------------------------
# Test 21: v1 Pexels -> low_confidence_provider still fires (v1 behavior)
# ---------------------------------------------------------------------------

def test_v1_pexels_low_confidence_unchanged(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path, asset_rel_path="scenes/scene-01.jpg")

    metadata = _build_v1_metadata(
        assets=[_v1_asset_entry(segments=[_v1_segment(
            provider="pexels",
            editorialRole="legacy",
            searchQuery="some query",
        )])],
        render_timeline=[_render_entry(asset_path="scenes/scene-01.jpg", asset_type="atmospheric_broll")],
    )

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    assert any(f["rule"] == "low_confidence_provider" for f in result["failures"])


# ---------------------------------------------------------------------------
# Test 22: v1 modern asset rules still execute
# ---------------------------------------------------------------------------

def test_v1_modern_asset_rules_executed(tmp_path):
    project_root, video_dir = _setup_job_dir(tmp_path, asset_rel_path="scenes/scene-01.jpg")

    metadata = _build_v1_metadata(
        assets=[_v1_asset_entry(segments=[_v1_segment(
            provider="pexels",
            editorialRole="portrait",
            searchQuery="modern city",
            assetType="atmospheric_broll",
        )])],
        render_timeline=[_render_entry(asset_path="scenes/scene-01.jpg", asset_type="atmospheric_broll")],
        script={"scenes": [{"sceneNumber": 1, "voiceover": "Historical building", "narrativeBeats": []}]},
    )

    result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
    # Pexels + atmospheric_broll triggers _is_modern_asset; editorialRole=portrait not in SOFT_ROLES
    assert any(f["rule"] == "modern_asset_hard_role" for f in result["failures"])


# =========================================================================
# V2 DIMENSION CONTRACT TESTS (Phase A)
# =========================================================================


def _make_image_with_dimensions(path: Path, width: int, height: int) -> None:
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (width, height), color=(100, 80, 60))
    img.save(path, "JPEG")


class TestV2DimensionContract:
    def test_700x435_blocked_in_v2(self, tmp_path):
        project_root, video_dir = _setup_job_dir(tmp_path, create_file=False)
        asset_path = video_dir / "assets" / "seg_001.jpg"
        _make_image_with_dimensions(asset_path, 700, 435)

        metadata = _build_v2_metadata(
            assets=[_v2_asset_entry(segments=[_v2_segment(width=700, height=435)])],
            render_timeline=[_render_entry()],
        )
        result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
        assert result["status"] == "BLOCKED"
        assert any(f["rule"] == "dimensions_too_small" for f in result["failures"])

    def test_720x720_passes_in_v2(self, tmp_path):
        project_root, video_dir = _setup_job_dir(tmp_path, create_file=False)
        asset_path = video_dir / "assets" / "seg_001.jpg"
        _make_image_with_dimensions(asset_path, 720, 720)

        metadata = _build_v2_metadata(
            assets=[_v2_asset_entry(segments=[_v2_segment(width=720, height=720)])],
            render_timeline=[_render_entry()],
        )
        result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
        assert result["status"] == "PASS"

    def test_1200x600_blocked_in_v2(self, tmp_path):
        project_root, video_dir = _setup_job_dir(tmp_path, create_file=False)
        asset_path = video_dir / "assets" / "seg_001.jpg"
        _make_image_with_dimensions(asset_path, 1200, 600)

        metadata = _build_v2_metadata(
            assets=[_v2_asset_entry(segments=[_v2_segment(width=1200, height=600)])],
            render_timeline=[_render_entry()],
        )
        result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
        assert result["status"] == "BLOCKED"
        assert any(f["rule"] == "dimensions_too_small" for f in result["failures"])

    def test_600x1200_blocked_in_v2(self, tmp_path):
        project_root, video_dir = _setup_job_dir(tmp_path, create_file=False)
        asset_path = video_dir / "assets" / "seg_001.jpg"
        _make_image_with_dimensions(asset_path, 600, 1200)

        metadata = _build_v2_metadata(
            assets=[_v2_asset_entry(segments=[_v2_segment(width=600, height=1200)])],
            render_timeline=[_render_entry()],
        )
        result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
        assert result["status"] == "BLOCKED"
        assert any(f["rule"] == "dimensions_too_small" for f in result["failures"])

    def test_721x902_passes_in_v2(self, tmp_path):
        project_root, video_dir = _setup_job_dir(tmp_path, create_file=False)
        asset_path = video_dir / "assets" / "seg_001.jpg"
        _make_image_with_dimensions(asset_path, 721, 902)

        metadata = _build_v2_metadata(
            assets=[_v2_asset_entry(segments=[_v2_segment(width=721, height=902)])],
            render_timeline=[_render_entry()],
        )
        result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
        assert result["status"] == "PASS"


class TestV1DimensionContractPreserved:
    """V1: dimensions_too_small only when BOTH dimensions are below 720."""

    def test_1200x600_passes_in_v1(self, tmp_path):
        """V1 has AND semantics — 1200>=720 so asset passes despite short height."""
        project_root, video_dir = _setup_job_dir(tmp_path, create_file=False)
        asset_path = video_dir / "scenes" / "scene-01.jpg"
        _make_image_with_dimensions(asset_path, 1200, 600)

        metadata = _build_v1_metadata(
            assets=[_v1_asset_entry(segments=[_v1_segment(width=1200, height=600)])],
            render_timeline=[_render_entry(asset_path="scenes/scene-01.jpg",
                                            asset_type="historical_photograph")],
        )
        result = shorts_creator.validation.asset.validate_job_for_render(metadata, project_root, video_dir)
        assert not any(f["rule"] == "dimensions_too_small" for f in result["failures"])
