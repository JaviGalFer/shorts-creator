"""Tests for prepare_job.py asset-completion validation contract."""
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "bin"))

from shorts_creator.rendering.preparer import _validate_asset_completion


def _make_data(scenes, assets, video_dir="/tmp/fake-job"):
    return {
        "script": {"scenes": scenes},
        "assets": assets,
    }


def _scene(n=1, vs=None):
    return {
        "sceneNumber": n,
        "targetDurationSec": 6.0,
        "voiceover": "Test voiceover.",
        "subtitle": "Test",
        "visualPlan": {
            "editorialRole": "context_map",
            "visualSequence": vs or [
                {"segmentIndex": 1, "assetType": "historical_map", "durationFraction": 0.5},
                {"segmentIndex": 2, "assetType": "document", "durationFraction": 0.5},
            ],
        },
    }


def _asset_entry(n=1, selected=True, segments=None):
    return {
        "sceneNumber": n,
        "selected": selected,
        "segments": segments or [
            {"segmentIndex": 1, "path": "/tmp/fake-job/scenes/scene-01-01.jpg",
             "segmentValidationStatus": "PASS", "error": None,
             "assetType": "historical_map"},
            {"segmentIndex": 2, "path": "/tmp/fake-job/scenes/scene-01-02.jpg",
             "segmentValidationStatus": "PASS", "error": None,
             "assetType": "document"},
        ],
    }


class TestAssetCompletionValidation:
    def test_all_valid_passes(self, tmp_path):
        """Fully resolved segments must pass validation."""
        job = tmp_path / "job"
        job.mkdir()
        scenes = job / "scenes"
        scenes.mkdir()
        (scenes / "scene-01-01.jpg").write_text("x" * 1000)
        (scenes / "scene-01-02.jpg").write_text("x" * 1000)

        data = _make_data(
            scenes=[_scene(1)],
            assets=[_asset_entry(1, segments=[
                {"segmentIndex": 1, "path": str(scenes / "scene-01-01.jpg"),
                 "segmentValidationStatus": "PASS", "error": None},
                {"segmentIndex": 2, "path": str(scenes / "scene-01-02.jpg"),
                 "segmentValidationStatus": "PASS", "error": None},
            ])],
        )
        failures = _validate_asset_completion(data, job)
        assert failures == []

    def test_unresolved_segment_error_rejected(self):
        """Segment with error (e.g. ASSET_UNRESOLVED) must be rejected."""
        data = _make_data(
            scenes=[_scene(1)],
            assets=[_asset_entry(1, segments=[
                {"segmentIndex": 1, "path": "/tmp/x.jpg",
                 "segmentValidationStatus": "PASS", "error": None},
                {"segmentIndex": 2, "path": None,
                 "segmentValidationStatus": "REJECTED",
                 "error": "ASSET_UNRESOLVED"},
            ])],
        )
        failures = _validate_asset_completion(data, Path("/tmp/fake-job"))
        assert len(failures) >= 1
        assert any(f["failureCode"] == "SEGMENT_ERROR" for f in failures)

    def test_null_path_rejected(self):
        """Segment with null path must be rejected."""
        data = _make_data(
            scenes=[_scene(1)],
            assets=[_asset_entry(1, segments=[
                {"segmentIndex": 1, "path": "/tmp/x.jpg",
                 "segmentValidationStatus": "PASS", "error": None},
                {"segmentIndex": 2, "path": None,
                 "segmentValidationStatus": "PASS", "error": None},
            ])],
        )
        failures = _validate_asset_completion(data, Path("/tmp/fake-job"))
        assert any(f["failureCode"] == "SEGMENT_PATH_NULL" for f in failures)

    def test_empty_path_rejected(self):
        """Segment with empty string path must be rejected."""
        data = _make_data(
            scenes=[_scene(1)],
            assets=[_asset_entry(1, segments=[
                {"segmentIndex": 1, "path": "/tmp/x.jpg",
                 "segmentValidationStatus": "PASS", "error": None},
                {"segmentIndex": 2, "path": "",
                 "segmentValidationStatus": "PASS", "error": None},
            ])],
        )
        failures = _validate_asset_completion(data, Path("/tmp/fake-job"))
        assert any(f["failureCode"] == "SEGMENT_PATH_NULL" for f in failures)

    def test_file_missing_rejected(self, tmp_path):
        """Segment pointing to non-existent file must be rejected."""
        job = tmp_path / "job"
        job.mkdir()
        data = _make_data(
            scenes=[_scene(1)],
            assets=[_asset_entry(1, segments=[
                {"segmentIndex": 1, "path": "/nonexistent/file.jpg",
                 "segmentValidationStatus": "PASS", "error": None},
            ])],
        )
        # Use video_dir that matches the path prefix so it passes the
        # inside-job check (or use a path inside and don't create the file)
        fake_job = tmp_path / "fake-job"
        fake_job.mkdir()
        (fake_job / "scenes").mkdir()
        data = _make_data(
            scenes=[_scene(1, vs=[
                {"segmentIndex": 1, "assetType": "historical_map", "durationFraction": 0.5},
            ])],
            assets=[{
                "sceneNumber": 1, "selected": True,
                "segments": [
                    {"segmentIndex": 1, "path": str(fake_job / "scenes" / "missing.jpg"),
                     "segmentValidationStatus": "PASS", "error": None},
                ],
            }],
        )
        failures = _validate_asset_completion(data, fake_job)
        assert any(f["failureCode"] == "SEGMENT_FILE_MISSING" for f in failures)

    def test_validation_not_pass_rejected(self):
        """Segment with segmentValidationStatus != PASS must be rejected."""
        data = _make_data(
            scenes=[_scene(1)],
            assets=[_asset_entry(1, segments=[
                {"segmentIndex": 1, "path": "/tmp/x.jpg",
                 "segmentValidationStatus": "REJECTED_FORBIDDEN_TYPE", "error": None},
            ])],
        )
        failures = _validate_asset_completion(data, Path("/tmp/fake-job"))
        assert any(f["failureCode"] == "SEGMENT_VALIDATION_FAILED" for f in failures)

    def test_path_outside_job_rejected(self, tmp_path):
        """Segment path outside job directory must be rejected."""
        data = _make_data(
            scenes=[_scene(1)],
            assets=[_asset_entry(1, segments=[
                {"segmentIndex": 1, "path": "/etc/passwd",
                 "segmentValidationStatus": "PASS", "error": None},
            ])],
        )
        failures = _validate_asset_completion(data, tmp_path / "my-job")
        assert any(f["failureCode"] == "SEGMENT_PATH_OUTSIDE_JOB" for f in failures)

    def test_segment_missing_from_assets(self):
        """visualSequence requests segment index not present in assets."""
        data = _make_data(
            scenes=[_scene(1)],
            assets=[_asset_entry(1, segments=[
                {"segmentIndex": 1, "path": "/tmp/x.jpg",
                 "segmentValidationStatus": "PASS", "error": None},
                # segment 2 missing
            ])],
        )
        failures = _validate_asset_completion(data, Path("/tmp/fake-job"))
        assert any(f["failureCode"] == "SEGMENT_MISSING" for f in failures)

    def test_scene_not_selected_fails(self, tmp_path):
        """Scene with valid segment files but selected=False must fail."""
        job = tmp_path / "job"
        job.mkdir()
        (job / "scenes").mkdir()
        img = job / "scenes" / "scene-01-01.jpg"
        img.write_text("x" * 1000)

        data = _make_data(
            scenes=[_scene(1)],
            assets=[{
                "sceneNumber": 1, "selected": False,
                "segments": [
                    {"segmentIndex": 1, "path": str(img),
                     "segmentValidationStatus": "PASS", "error": None},
                ],
            }],
        )
        failures = _validate_asset_completion(data, job)
        assert any(f["failureCode"] == "SCENE_NOT_SELECTED" for f in failures)

    def test_selected_none_fails_closed(self, tmp_path):
        """Scene with selected=None must fail (fail-closed)."""
        job = tmp_path / "job"
        job.mkdir()
        (job / "scenes").mkdir()
        img = job / "scenes" / "scene-01-01.jpg"
        img.write_text("x" * 1000)

        data = _make_data(
            scenes=[_scene(1)],
            assets=[{
                "sceneNumber": 1, "selected": None,
                "segments": [
                    {"segmentIndex": 1, "path": str(img),
                     "segmentValidationStatus": "PASS", "error": None},
                ],
            }],
        )
        failures = _validate_asset_completion(data, job)
        assert any(f["failureCode"] == "SCENE_NOT_SELECTED" for f in failures)

    def test_selected_omitted_fails_closed(self, tmp_path):
        """Scene with missing selected field must fail (fail-closed)."""
        job = tmp_path / "job"
        job.mkdir()
        (job / "scenes").mkdir()
        img = job / "scenes" / "scene-01-01.jpg"
        img.write_text("x" * 1000)

        data = _make_data(
            scenes=[_scene(1)],
            assets=[{
                "sceneNumber": 1,
                "segments": [
                    {"segmentIndex": 1, "path": str(img),
                     "segmentValidationStatus": "PASS", "error": None},
                ],
            }],
        )
        failures = _validate_asset_completion(data, job)
        assert any(f["failureCode"] == "SCENE_NOT_SELECTED" for f in failures)


# ── Integration tests via main() ────────────────────────────────────────

import sys as _sys


class TestMainAssetGate:
    def test_main_rejects_unresolved_segment(self, monkeypatch, tmp_path):
        """main() with unresolved segment: non-zero exit, ASSET_UNRESOLVED,
        no subtitle/timeline artifacts."""
        import prepare_job as prepare_cli
        import shorts_creator.rendering.preparer as pj
        pj.main = prepare_cli.main

        job = tmp_path / "job"
        job.mkdir()
        (job / "scenes").mkdir()
        img = job / "scenes" / "scene-01-01.jpg"
        img.write_text("x" * 1000)
        meta_path = job / "metadata.json"

        meta = {
            "jobId": "test-001",
            "script": {"scenes": [
                {"sceneNumber": 1, "targetDurationSec": 6.0,
                 "voiceover": "Test.", "subtitle": "Test",
                 "visualPlan": {
                     "editorialRole": "context_map",
                     "visualSequence": [
                         {"segmentIndex": 1, "assetType": "historical_map",
                          "durationFraction": 0.5},
                         {"segmentIndex": 2, "assetType": "document",
                          "durationFraction": 0.5},
                     ],
                 }},
            ]},
            "assets": [{
                "sceneNumber": 1, "selected": True,
                "segments": [
                    {"segmentIndex": 1, "path": str(img),
                     "segmentValidationStatus": "PASS", "error": None},
                    {"segmentIndex": 2, "path": None,
                     "segmentValidationStatus": "REJECTED",
                     "error": "ASSET_UNRESOLVED"},
                ],
            }],
        }
        meta_path.write_text(json.dumps(meta))

        monkeypatch.setattr(_sys, "argv", ["prepare_job.py", str(meta_path)])
        exit_code = pj.main()
        assert exit_code == 1

        result = json.loads(meta_path.read_text())
        assert result["status"] == "ASSET_UNRESOLVED"
        assert result.get("assetFailures")
        assert not (job / "subtitle.ass").exists()
        assert "timeline" not in result
        assert "renderTimeline" not in result

    def test_main_rejects_selected_false(self, monkeypatch, tmp_path):
        """main() with selected=false: non-zero exit, SCENE_NOT_SELECTED."""
        import prepare_job as prepare_cli
        import shorts_creator.rendering.preparer as pj
        pj.main = prepare_cli.main

        job = tmp_path / "job"
        job.mkdir()
        (job / "scenes").mkdir()
        img = job / "scenes" / "scene-01-01.jpg"
        img.write_text("x" * 1000)
        img2 = job / "scenes" / "scene-01-02.jpg"
        img2.write_text("x" * 1000)
        meta_path = job / "metadata.json"

        meta = {
            "jobId": "test-002",
            "script": {"scenes": [
                {"sceneNumber": 1, "targetDurationSec": 6.0,
                 "voiceover": "Test.", "subtitle": "Test",
                 "visualPlan": {
                     "editorialRole": "context_map",
                     "visualSequence": [
                         {"segmentIndex": 1, "assetType": "historical_map",
                          "durationFraction": 0.5},
                         {"segmentIndex": 2, "assetType": "document",
                          "durationFraction": 0.5},
                     ],
                 }},
            ]},
            "assets": [{
                "sceneNumber": 1, "selected": False,
                "segments": [
                    {"segmentIndex": 1, "path": str(img),
                     "segmentValidationStatus": "PASS", "error": None},
                    {"segmentIndex": 2, "path": str(img2),
                     "segmentValidationStatus": "PASS", "error": None},
                ],
            }],
        }
        meta_path.write_text(json.dumps(meta))

        monkeypatch.setattr(_sys, "argv", ["prepare_job.py", str(meta_path)])
        exit_code = pj.main()
        assert exit_code == 1

        result = json.loads(meta_path.read_text())
        assert result["status"] == "ASSET_UNRESOLVED"
        assert any(f["failureCode"] == "SCENE_NOT_SELECTED"
                   for f in result.get("assetFailures", []))
        assert not (job / "subtitle.ass").exists()

    def test_main_cleans_stale_artifacts(self, monkeypatch, tmp_path):
        """Job with pre-existing subtitle.ass/timeline that then fails
        must have stale artifacts cleaned."""
        import prepare_job as prepare_cli
        import shorts_creator.rendering.preparer as pj
        pj.main = prepare_cli.main

        job = tmp_path / "job"
        job.mkdir()
        (job / "scenes").mkdir()
        img = job / "scenes" / "scene-01-01.jpg"
        img.write_text("x" * 1000)
        meta_path = job / "metadata.json"

        # Pre-create stale subtitle and stale timeline in metadata
        stale_sub = job / "subtitle.ass"
        stale_sub.write_text("stale")
        meta = {
            "jobId": "test-003",
            "status": "SUBTITLES_READY",
            "script": {"scenes": [
                {"sceneNumber": 1, "targetDurationSec": 6.0,
                 "voiceover": "Test.", "subtitle": "Test",
                 "visualPlan": {
                     "editorialRole": "context_map",
                     "visualSequence": [
                         {"segmentIndex": 1, "assetType": "historical_map",
                          "durationFraction": 0.5},
                     ],
                 }},
            ]},
            "assets": [{
                "sceneNumber": 1, "selected": True,
                "segments": [
                    {"segmentIndex": 1, "path": None,
                     "segmentValidationStatus": "REJECTED",
                     "error": "ASSET_UNRESOLVED"},
                ],
            }],
            "timeline": ["stale1", "stale2"],
            "renderTimeline": ["stale_rt"],
            "subtitles": {"path": str(stale_sub)},
            "render": {"path": str(job / "video.mp4")},
            "review": {"status": "READY"},
        }
        meta_path.write_text(json.dumps(meta))

        monkeypatch.setattr(_sys, "argv", ["prepare_job.py", str(meta_path)])
        exit_code = pj.main()
        assert exit_code == 1

        result = json.loads(meta_path.read_text())
        assert result["status"] == "ASSET_UNRESOLVED"
        # Stale fields removed
        assert "timeline" not in result
        assert "renderTimeline" not in result
        assert "subtitles" not in result
        assert "render" not in result
        assert "review" not in result
        # subtitle.ass file removed
        assert not stale_sub.exists()

    def test_main_accepts_valid_job(self, monkeypatch, tmp_path):
        """Fully valid job: exit 0, subtitle.ass created, timeline written."""
        import prepare_job as prepare_cli
        import shorts_creator.rendering.preparer as pj
        pj.main = prepare_cli.main

        job = tmp_path / "job"
        job.mkdir()
        (job / "scenes").mkdir()
        img = job / "scenes" / "scene-01-01.jpg"
        img.write_text("x" * 1000)
        mp3 = job / "scenes" / "scene-01.mp3"
        mp3.write_text("x" * 2000)
        meta_path = job / "metadata.json"

        meta = {
            "jobId": "test-004",
            "script": {"scenes": [
                {"sceneNumber": 1, "targetDurationSec": 6.0,
                 "voiceover": "Test voiceover.", "subtitle": "Test",
                 "subtitleTiming": {"cues": []},
                 "visualPlan": {
                     "editorialRole": "context_map",
                     "visualSequence": [
                         {"segmentIndex": 1, "assetType": "historical_map",
                          "durationFraction": 0.5, "transition": "cut",
                          "motionType": "slow_zoom_in"},
                     ],
                 }},
            ]},
            "audio": {
                "provider": "edge-tts",
                "continuous": False,
                "duration_estimated": False,
                "scenes": [
                    {"sceneNumber": 1, "path": str(mp3), "exists": True,
                     "durationSec": 6.0, "durationSource": "ffprobe_local"},
                ],
            },
            "assets": [{
                "sceneNumber": 1, "selected": True,
                "segments": [
                    {"segmentIndex": 1, "path": str(img),
                     "segmentValidationStatus": "PASS", "error": None},
                ],
            }],
        }
        meta_path.write_text(json.dumps(meta))

        monkeypatch.setattr(_sys, "argv", ["prepare_job.py", str(meta_path)])
        exit_code = pj.main()
        assert exit_code == 0

        result = json.loads(meta_path.read_text())
        assert result["status"] == "SUBTITLES_READY"
        assert (job / "subtitle.ass").exists()
        assert "timeline" in result
        assert "renderTimeline" in result
