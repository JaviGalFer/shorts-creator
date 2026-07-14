"""Tests for Phase 2A: prepare_job.py asset path resolution.

Verifies _resolve_asset_path resolves relative paths against video_dir,
rejects path traversal, and preserves original path strings in timelines.

Run: python3 -m pytest tests/test_prepare_job_v2_assets_paths.py -v
"""

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "bin"))

import pytest

from prepare_job import (
    _resolve_asset_path,
    _validate_asset_completion,
    build_timeline,
    build_render_timeline,
)


# ---------------------------------------------------------------------------
# _resolve_asset_path unit tests
# ---------------------------------------------------------------------------


class TestResolveAssetPath:
    def test_relative_assets_seg_returns_inside_video_dir(self, tmp_path):
        video_dir = tmp_path / "job"
        video_dir.mkdir()
        asset_dir = video_dir / "assets"
        asset_dir.mkdir()
        (asset_dir / "seg_001.jpg").write_text("x")
        result = _resolve_asset_path(video_dir, "assets/seg_001.jpg")
        assert result == (video_dir / "assets" / "seg_001.jpg").resolve()

    def test_relative_scenes_path_returns_inside_video_dir(self, tmp_path):
        video_dir = tmp_path / "job"
        video_dir.mkdir()
        scenes_dir = video_dir / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.jpg").write_text("x")
        result = _resolve_asset_path(video_dir, "scenes/scene-01.jpg")
        assert result == (video_dir / "scenes" / "scene-01.jpg").resolve()

    def test_path_traversal_returns_none(self, tmp_path):
        video_dir = tmp_path / "job"
        video_dir.mkdir()
        result = _resolve_asset_path(video_dir, "../evil.jpg")
        assert result is None

    def test_absolute_path_outside_returns_none(self, tmp_path):
        video_dir = tmp_path / "job"
        video_dir.mkdir()
        result = _resolve_asset_path(video_dir, "/etc/passwd")
        assert result is None

    def test_absolute_path_inside_accepted(self, tmp_path):
        video_dir = tmp_path / "job"
        video_dir.mkdir()
        asset_dir = video_dir / "assets"
        asset_dir.mkdir(parents=True)
        abs_path = (asset_dir / "a.jpg").resolve()
        abs_path.write_text("x")
        result = _resolve_asset_path(video_dir, str(abs_path))
        assert result == abs_path

    def test_empty_string_returns_none(self, tmp_path):
        result = _resolve_asset_path(tmp_path, "")
        assert result is None

    def test_none_returns_none(self, tmp_path):
        result = _resolve_asset_path(tmp_path, None)
        assert result is None

    def test_whitespace_only_returns_none(self, tmp_path):
        result = _resolve_asset_path(tmp_path, "   ")
        assert result is None

    def test_path_with_dots_still_inside_accepted(self, tmp_path):
        video_dir = tmp_path / "job"
        video_dir.mkdir()
        sub = video_dir / "sub"
        sub.mkdir()
        (sub / "target.jpg").write_text("x")
        result = _resolve_asset_path(video_dir, "sub/../sub/target.jpg")
        assert result is not None
        assert result == (sub / "target.jpg").resolve()

    def test_path_resolves_into_parent_via_dots_rejected(self, tmp_path):
        video_dir = tmp_path / "job" / "deep"
        video_dir.mkdir(parents=True)
        result = _resolve_asset_path(video_dir, "../../evil.jpg")
        assert result is None


# ---------------------------------------------------------------------------
# _validate_asset_completion tests with v2-style relative paths
# ---------------------------------------------------------------------------


def _make_data(scenes, assets):
    return {"script": {"scenes": scenes}, "assets": assets}


def _scene(n=1, vs=None):
    return {
        "sceneNumber": n,
        "targetDurationSec": 6.0,
        "voiceover": "Test voiceover.",
        "subtitle": "Test",
        "visualPlan": {
            "editorialRole": "context_map",
            "visualSequence": vs or [
                {"segmentIndex": 1, "assetType": "historical_map"},
            ],
        },
    }


class TestValidateAssetV2Paths:
    def test_v2_assets_relative_passes_when_file_exists(self, tmp_path):
        video_dir = tmp_path / "job"
        video_dir.mkdir()
        asset_dir = video_dir / "assets"
        asset_dir.mkdir()
        (asset_dir / "seg_001.jpg").write_text("x" * 1000)

        data = _make_data(
            scenes=[_scene(1)],
            assets=[{
                "sceneNumber": 1, "selected": True,
                "segments": [
                    {"segmentIndex": 1, "path": "assets/seg_001.jpg",
                     "segmentValidationStatus": "PASS", "error": None},
                ],
            }],
        )
        failures = _validate_asset_completion(data, video_dir)
        assert failures == []

    def test_v1_scenes_relative_passes_when_file_exists(self, tmp_path):
        video_dir = tmp_path / "job"
        video_dir.mkdir()
        scenes_dir = video_dir / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.jpg").write_text("x" * 1000)

        data = _make_data(
            scenes=[_scene(1)],
            assets=[{
                "sceneNumber": 1, "selected": True,
                "segments": [
                    {"segmentIndex": 1, "path": "scenes/scene-01.jpg",
                     "segmentValidationStatus": "PASS", "error": None},
                ],
            }],
        )
        failures = _validate_asset_completion(data, video_dir)
        assert failures == []

    def test_assets_missing_file_fails(self, tmp_path):
        video_dir = tmp_path / "job"
        video_dir.mkdir()
        asset_dir = video_dir / "assets"
        asset_dir.mkdir()
        # file not created

        data = _make_data(
            scenes=[_scene(1)],
            assets=[{
                "sceneNumber": 1, "selected": True,
                "segments": [
                    {"segmentIndex": 1, "path": "assets/missing.jpg",
                     "segmentValidationStatus": "PASS", "error": None},
                ],
            }],
        )
        failures = _validate_asset_completion(data, video_dir)
        assert any(f["failureCode"] == "SEGMENT_FILE_MISSING" for f in failures)

    def test_path_traversal_fails_path_outside_job(self, tmp_path):
        video_dir = tmp_path / "job"
        video_dir.mkdir()

        data = _make_data(
            scenes=[_scene(1)],
            assets=[{
                "sceneNumber": 1, "selected": True,
                "segments": [
                    {"segmentIndex": 1, "path": "../evil.jpg",
                     "segmentValidationStatus": "PASS", "error": None},
                ],
            }],
        )
        failures = _validate_asset_completion(data, video_dir)
        assert any(f["failureCode"] == "SEGMENT_PATH_OUTSIDE_JOB" for f in failures)

    def test_empty_path_fails_path_null(self, tmp_path):
        video_dir = tmp_path / "job"
        video_dir.mkdir()

        data = _make_data(
            scenes=[_scene(1)],
            assets=[{
                "sceneNumber": 1, "selected": True,
                "segments": [
                    {"segmentIndex": 1, "path": "",
                     "segmentValidationStatus": "PASS", "error": None},
                ],
            }],
        )
        failures = _validate_asset_completion(data, video_dir)
        assert any(f["failureCode"] == "SEGMENT_PATH_NULL" for f in failures)

    def test_none_path_fails_path_null(self, tmp_path):
        video_dir = tmp_path / "job"
        video_dir.mkdir()

        data = _make_data(
            scenes=[_scene(1)],
            assets=[{
                "sceneNumber": 1, "selected": True,
                "segments": [
                    {"segmentIndex": 1, "path": None,
                     "segmentValidationStatus": "PASS", "error": None},
                ],
            }],
        )
        failures = _validate_asset_completion(data, video_dir)
        assert any(f["failureCode"] == "SEGMENT_PATH_NULL" for f in failures)

    def test_validation_status_fail_still_fails(self, tmp_path):
        video_dir = tmp_path / "job"
        video_dir.mkdir()

        data = _make_data(
            scenes=[_scene(1)],
            assets=[{
                "sceneNumber": 1, "selected": True,
                "segments": [
                    {"segmentIndex": 1, "path": "assets/seg_001.jpg",
                     "segmentValidationStatus": "FAIL", "error": None},
                ],
            }],
        )
        failures = _validate_asset_completion(data, video_dir)
        assert any(f["failureCode"] == "SEGMENT_VALIDATION_FAILED" for f in failures)

    def test_selected_false_still_fails(self, tmp_path):
        video_dir = tmp_path / "job"
        video_dir.mkdir()
        asset_dir = video_dir / "assets"
        asset_dir.mkdir()
        (asset_dir / "seg_001.jpg").write_text("x")

        data = _make_data(
            scenes=[_scene(1)],
            assets=[{
                "sceneNumber": 1, "selected": False,
                "segments": [
                    {"segmentIndex": 1, "path": "assets/seg_001.jpg",
                     "segmentValidationStatus": "PASS", "error": None},
                ],
            }],
        )
        failures = _validate_asset_completion(data, video_dir)
        assert any(f["failureCode"] == "SCENE_NOT_SELECTED" for f in failures)

    def test_segment_error_still_fails(self, tmp_path):
        video_dir = tmp_path / "job"
        video_dir.mkdir()

        data = _make_data(
            scenes=[_scene(1)],
            assets=[{
                "sceneNumber": 1, "selected": True,
                "segments": [
                    {"segmentIndex": 1, "path": "assets/seg_001.jpg",
                     "segmentValidationStatus": "PASS",
                     "error": "SOME_ERROR"},
                ],
            }],
        )
        failures = _validate_asset_completion(data, video_dir)
        assert any(f["failureCode"] == "SEGMENT_ERROR" for f in failures)


# ---------------------------------------------------------------------------
# Timeline preservation tests
# ---------------------------------------------------------------------------


class TestTimelinePreservesRelativePaths:
    def test_build_timeline_preserves_relative_image_path(self, tmp_path):
        video_dir = tmp_path / "job"
        video_dir.mkdir()
        scenes_dir = video_dir / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.mp3").write_text("audio")

        scenes = [{"sceneNumber": 1, "targetDurationSec": 6.0}]
        assets = [{
            "sceneNumber": 1,
            "segments": [
                {"segmentIndex": 1, "path": "assets/seg_001.jpg",
                 "durationSec": 6.0, "transition": "cut", "assetType": "broll"},
            ],
        }]
        timeline = build_timeline(scenes, assets, video_dir, scenes_dir)
        assert timeline[0]["imagePath"] == "assets/seg_001.jpg"

    def test_build_render_timeline_preserves_relative_asset_path(self, tmp_path):
        video_dir = tmp_path / "job"
        video_dir.mkdir()
        scenes_dir = video_dir / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.mp3").write_text("audio")

        scenes = [{
            "sceneNumber": 1, "targetDurationSec": 6.0,
            "subtitleTiming": {"cues": []},
        }]
        assets = [{
            "sceneNumber": 1,
            "segments": [
                {"segmentIndex": 1, "path": "assets/seg_001.jpg",
                 "durationFraction": 1.0},
            ],
        }]
        rt = build_render_timeline(scenes, assets, scenes_dir, scene_audio_durations={1: 5.65})
        assert rt[0]["assetPath"] == "assets/seg_001.jpg"


# ---------------------------------------------------------------------------
# Integration test via main()
# ---------------------------------------------------------------------------


class TestMainV2AssetsPaths:
    def test_main_accepts_v2_assets_relative_paths(self, monkeypatch, tmp_path):
        import prepare_job as pj

        job = tmp_path / "job"
        job.mkdir()
        scenes_dir = job / "scenes"
        scenes_dir.mkdir()
        asset_dir = job / "assets"
        asset_dir.mkdir()

        (asset_dir / "seg_001.jpg").write_text("x" * 1000)
        (scenes_dir / "scene-01.mp3").write_text("x" * 2000)
        meta_path = job / "metadata.json"

        meta = {
            "jobId": "test-v2-assets",
            "script": {"scenes": [
                {"sceneNumber": 1, "targetDurationSec": 6.0,
                 "voiceover": "Test.", "subtitle": "Test",
                 "subtitleTiming": {"cues": []},
                 "visualPlan": {
                     "editorialRole": "context_map",
                     "visualSequence": [
                         {"segmentIndex": 1, "assetType": "historical_map"},
                     ],
                 }},
            ]},
            "audio": {
                "provider": "edge-tts",
                "continuous": False,
                "duration_estimated": False,
                "scenes": [
                    {"sceneNumber": 1, "path": str(scenes_dir / "scene-01.mp3"),
                     "exists": True, "durationSec": 6.0, "durationSource": "ffprobe_local"},
                ],
            },
            "assets": [{
                "sceneNumber": 1, "selected": True,
                "segments": [
                    {"segmentIndex": 1, "path": "assets/seg_001.jpg",
                     "segmentValidationStatus": "PASS", "error": None,
                     "transition": "cut"},
                ],
            }],
        }
        meta_path.write_text(json.dumps(meta))

        monkeypatch.setattr(sys, "argv", ["prepare_job.py", str(meta_path)])
        exit_code = pj.main()
        assert exit_code == 0

        result = json.loads(meta_path.read_text())
        assert result["status"] == "SUBTITLES_READY"
        assert (job / "subtitle.ass").exists()
        assert "timeline" in result
        assert "renderTimeline" in result
        # imagePath preserved as relative
        assert result["timeline"][0]["imagePath"] == "assets/seg_001.jpg"
        # assetPath preserved as relative
        assert result["renderTimeline"][0]["assetPath"] == "assets/seg_001.jpg"

    def test_main_rejects_missing_v2_assets(self, monkeypatch, tmp_path):
        import prepare_job as pj

        job = tmp_path / "job"
        job.mkdir()
        scenes_dir = job / "scenes"
        scenes_dir.mkdir()
        # no assets/ directory created

        (scenes_dir / "scene-01.mp3").write_text("x" * 2000)
        meta_path = job / "metadata.json"

        meta = {
            "jobId": "test-v2-missing",
            "script": {"scenes": [
                {"sceneNumber": 1, "targetDurationSec": 6.0,
                 "voiceover": "Test.", "subtitle": "Test",
                 "visualPlan": {
                     "editorialRole": "context_map",
                     "visualSequence": [
                         {"segmentIndex": 1, "assetType": "historical_map"},
                     ],
                 }},
            ]},
            "assets": [{
                "sceneNumber": 1, "selected": True,
                "segments": [
                    {"segmentIndex": 1, "path": "assets/missing.jpg",
                     "segmentValidationStatus": "PASS", "error": None},
                ],
            }],
        }
        meta_path.write_text(json.dumps(meta))

        monkeypatch.setattr(sys, "argv", ["prepare_job.py", str(meta_path)])
        exit_code = pj.main()
        assert exit_code == 1

        result = json.loads(meta_path.read_text())
        assert result["status"] == "ASSET_UNRESOLVED"
        assert any(f["failureCode"] == "SEGMENT_FILE_MISSING"
                   for f in result.get("assetFailures", []))
