"""Tests for Phase 2B: render_job.py v2 assets/ relative path resolution.

Verifies preflight_validate, _to_docker_asset_path, asset_validation.validate_asset_file
all resolve assets/ paths relative to video_dir.

No Docker. No FFmpeg. No real render.

Run: python3 -m pytest tests/test_render_job_v2_assets_paths.py -v
"""

import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "bin"))

import pytest

import asset_validation
from render_job import _to_docker_asset_path, preflight_validate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scene(n=1, dur=6.0):
    return {"sceneNumber": n, "targetDurationSec": dur}


def _make_timeline_entry(sn=1, si=1, dur=6.0, asset_path="assets/seg_001.jpg",
                         start=0, end=6.0):
    return {
        "sceneNumber": sn,
        "segmentIndex": si,
        "durationSec": dur,
        "startSec": start,
        "endSec": end,
        "beatIndex": 0,
        "assetType": "broll",
        "motionType": "static",
        "assetPath": asset_path,
    }


def _touch(path: Path, content="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# ---------------------------------------------------------------------------
# _to_docker_asset_path
# ---------------------------------------------------------------------------


class TestToDockerAssetPath:
    def test_relative_path_assets(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        video_rel = "/workspace/data/videos/job001"
        result = _to_docker_asset_path(project_root, video_rel, "assets/seg_001.jpg")
        assert result == f"{video_rel}/assets/seg_001.jpg"

    def test_relative_path_scenes(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        video_rel = "/workspace/data/videos/job001"
        result = _to_docker_asset_path(project_root, video_rel, "scenes/scene-01.jpg")
        assert result == f"{video_rel}/scenes/scene-01.jpg"

    def test_absolute_path_inside_project_root(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        video_rel = "/workspace/data/videos/job001"
        abs_path = project_root / "data" / "videos" / "job001" / "scenes" / "scene-01.jpg"
        abs_path.parent.mkdir(parents=True)
        abs_path.write_text("x")
        result = _to_docker_asset_path(project_root, video_rel, str(abs_path))
        expected = f"/workspace/{abs_path.relative_to(project_root)}"
        assert result == expected

    def test_absolute_path_outside_project_root_raises(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        video_rel = "/workspace/data/videos/job001"
        with tempfile.TemporaryDirectory() as outside:
            outside_path = Path(outside) / "evil.jpg"
            outside_path.write_text("x")
            with pytest.raises(ValueError):
                _to_docker_asset_path(project_root, video_rel, str(outside_path))

    def test_does_not_fabricate_scenes_pattern(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        video_rel = "/workspace/data/videos/job001"
        result = _to_docker_asset_path(project_root, video_rel, "assets/seg_001.jpg")
        assert "scenes/scene-" not in result
        assert result.endswith("assets/seg_001.jpg")


# ---------------------------------------------------------------------------
# preflight_validate — asset path resolution
# ---------------------------------------------------------------------------


def _dummy_preflight_env(tmp_path) -> tuple[Path, Path, Path]:
    """Create a project_root and video_dir for preflight validation."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    video_dir = project_root / "data" / "videos" / "job001"
    video_dir.mkdir(parents=True)
    return project_root, video_dir, tmp_path


class TestPreflightV2AssetsPaths:
    def test_accepts_assets_relative_path_when_file_exists(self, tmp_path):
        project_root, video_dir, _ = _dummy_preflight_env(tmp_path)
        _touch(video_dir / "assets" / "seg_001.jpg")
        timeline = [_make_timeline_entry(asset_path="assets/seg_001.jpg")]
        scenes = [_make_scene(1, 6.0)]
        errors = preflight_validate(timeline, scenes, project_root, video_dir)
        file_errors = [e for e in errors if "not found" in e]
        assert file_errors == []

    def test_rejects_assets_missing_file(self, tmp_path):
        project_root, video_dir, _ = _dummy_preflight_env(tmp_path)
        (video_dir / "assets").mkdir(parents=True)
        timeline = [_make_timeline_entry(asset_path="assets/missing.jpg")]
        scenes = [_make_scene(1, 6.0)]
        errors = preflight_validate(timeline, scenes, project_root, video_dir)
        file_errors = [e for e in errors if "not found" in e]
        assert len(file_errors) == 1
        assert "assets/missing.jpg" in file_errors[0]

    def test_keeps_scenes_behavior(self, tmp_path):
        project_root, video_dir, _ = _dummy_preflight_env(tmp_path)
        _touch(video_dir / "scenes" / "scene-01.jpg")
        timeline = [_make_timeline_entry(asset_path="scenes/scene-01.jpg")]
        scenes = [_make_scene(1, 6.0)]
        errors = preflight_validate(timeline, scenes, project_root, video_dir)
        file_errors = [e for e in errors if "not found" in e]
        assert file_errors == []

    def test_rejects_scenes_missing_file(self, tmp_path):
        project_root, video_dir, _ = _dummy_preflight_env(tmp_path)
        (video_dir / "scenes").mkdir(parents=True)
        timeline = [_make_timeline_entry(asset_path="scenes/scene-99.jpg")]
        scenes = [_make_scene(1, 6.0)]
        errors = preflight_validate(timeline, scenes, project_root, video_dir)
        file_errors = [e for e in errors if "not found" in e]
        assert len(file_errors) == 1
        assert "scenes/scene-99.jpg" in file_errors[0]

    def test_other_relative_path_resolved_against_video_dir(self, tmp_path):
        project_root, video_dir, _ = _dummy_preflight_env(tmp_path)
        _touch(video_dir / "custom" / "img.png")
        timeline = [_make_timeline_entry(asset_path="custom/img.png")]
        scenes = [_make_scene(1, 6.0)]
        errors = preflight_validate(timeline, scenes, project_root, video_dir)
        file_errors = [e for e in errors if "not found" in e]
        assert file_errors == []

    def test_absolute_path_inside_project_resolved_as_is(self, tmp_path):
        project_root, video_dir, _ = _dummy_preflight_env(tmp_path)
        abs_path = video_dir / "abs_img.jpg"
        _touch(abs_path)
        timeline = [_make_timeline_entry(asset_path=str(abs_path))]
        scenes = [_make_scene(1, 6.0)]
        errors = preflight_validate(timeline, scenes, project_root, video_dir)
        file_errors = [e for e in errors if "not found" in e]
        assert file_errors == []

    def test_absolute_path_outside_project_accepted_if_exists(self, tmp_path):
        project_root, video_dir, _ = _dummy_preflight_env(tmp_path)
        with tempfile.TemporaryDirectory() as outside:
            outside_path = Path(outside) / "ext.jpg"
            outside_path.write_text("x")
            timeline = [_make_timeline_entry(asset_path=str(outside_path))]
            scenes = [_make_scene(1, 6.0)]
            errors = preflight_validate(timeline, scenes, project_root, video_dir)
            file_errors = [e for e in errors if "not found" in e]
            assert file_errors == []

    def test_empty_asset_path_fails_with_empty_message(self, tmp_path):
        project_root, video_dir, _ = _dummy_preflight_env(tmp_path)
        timeline = [_make_timeline_entry(asset_path="")]
        scenes = [_make_scene(1, 6.0)]
        errors = preflight_validate(timeline, scenes, project_root, video_dir)
        assert any("empty" in e for e in errors)


# ---------------------------------------------------------------------------
# asset_validation.validate_asset_file — v2 paths
# ---------------------------------------------------------------------------


class TestAssetValidationV2Paths:
    def test_accepts_assets_relative_with_video_dir(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        video_dir = project_root / "data" / "videos" / "job001"
        video_dir.mkdir(parents=True)
        _touch(video_dir / "assets" / "seg_001.jpg")

        failures = asset_validation.validate_asset_file(
            "assets/seg_001.jpg", project_root, video_dir=video_dir
        )
        file_failures = [f for f in failures if f["rule"] == "file_not_found"]
        assert file_failures == []

    def test_accepts_scenes_relative_with_video_dir(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        video_dir = project_root / "data" / "videos" / "job001"
        video_dir.mkdir(parents=True)
        _touch(video_dir / "scenes" / "scene-01.jpg")

        failures = asset_validation.validate_asset_file(
            "scenes/scene-01.jpg", project_root, video_dir=video_dir
        )
        file_failures = [f for f in failures if f["rule"] == "file_not_found"]
        assert file_failures == []

    def test_rejects_missing_assets_with_video_dir(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        video_dir = project_root / "data" / "videos" / "job001"
        video_dir.mkdir(parents=True)
        (video_dir / "assets").mkdir(parents=True)

        failures = asset_validation.validate_asset_file(
            "assets/missing.jpg", project_root, video_dir=video_dir
        )
        file_failures = [f for f in failures if f["rule"] == "file_not_found"]
        assert len(file_failures) == 1
        assert "assets/missing.jpg" in file_failures[0]["message"]

    def test_falls_back_to_project_root_when_no_video_dir(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        _touch(project_root / "assets" / "seg_001.jpg")

        failures = asset_validation.validate_asset_file(
            "assets/seg_001.jpg", project_root, video_dir=None
        )
        file_failures = [f for f in failures if f["rule"] == "file_not_found"]
        assert file_failures == []

    def test_rejects_non_existent_file_no_video_dir(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()

        failures = asset_validation.validate_asset_file(
            "assets/missing.jpg", project_root, video_dir=None
        )
        file_failures = [f for f in failures if f["rule"] == "file_not_found"]
        assert len(file_failures) == 1
        assert "file not found" in file_failures[0]["message"].lower()

    def test_absolute_path_used_verbatim(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        video_dir = project_root / "data" / "videos" / "job001"
        video_dir.mkdir(parents=True)
        abs_img = project_root / "some" / "absolute.jpg"
        _touch(abs_img)

        failures = asset_validation.validate_asset_file(
            str(abs_img), project_root, video_dir=video_dir
        )
        file_failures = [f for f in failures if f["rule"] == "file_not_found"]
        assert file_failures == []
