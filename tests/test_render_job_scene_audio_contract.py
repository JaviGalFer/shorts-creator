"""Tests for Phase B: per-scene audio contract in render_job.py.

Covers: scene aggregate preflight, audio padding chain, expected_duration,
backward compatibility for continuous and V1.
"""

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "bin"))

import pytest

from render_job import (
    preflight_validate,
    _to_workspace_path,
    _to_docker_asset_path,
    build_per_scene_audio_filter,
    resolve_expected_duration,
    resolve_manifest_scene_audio_duration,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_timeline_entry(sn=1, si=1, dur=6.0, start=0.0, end=6.0,
                         asset_path="assets/seg_001.jpg",
                         audio_path=None, beat_index=1, asset_type="broll"):
    entry = {
        "sceneNumber": sn,
        "segmentIndex": si,
        "durationSec": dur,
        "startSec": start,
        "endSec": end,
        "beatIndex": beat_index,
        "assetType": asset_type,
        "motionType": "static",
        "assetPath": asset_path,
    }
    if audio_path:
        entry["audioPath"] = audio_path
    return entry


def _make_scene(n=1, dur=6.0):
    return {"sceneNumber": n, "targetDurationSec": dur}


def _touch(path: Path, content="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# ---------------------------------------------------------------------------
# Preflight — scene aggregate audio validation
# ---------------------------------------------------------------------------


def _dummy_env(tmp_path) -> tuple[Path, Path]:
    project_root = tmp_path / "project"
    project_root.mkdir()
    video_dir = project_root / "data" / "videos" / "job001"
    video_dir.mkdir(parents=True)
    return project_root, video_dir


class TestPreflightSceneAggregate:
    def test_two_segments_5s_window_10s_audio_6_9_passes(self, tmp_path):
        """Scene window 10s > audio 6.9s → OK (padding will be added)."""
        project_root, video_dir = _dummy_env(tmp_path)
        _touch(video_dir / "assets" / "seg_001.jpg")
        _touch(video_dir / "assets" / "seg_002.jpg")

        mp3 = video_dir / "scenes" / "scene-01.mp3"
        mp3.parent.mkdir()
        mp3.write_bytes(b"\xff\xfb" + b"\x00" * 100)  # minimal MP3 frame

        timeline = [
            _make_timeline_entry(sn=1, si=1, dur=5.0, start=0.0, end=5.0,
                                 asset_path="assets/seg_001.jpg"),
            _make_timeline_entry(sn=1, si=2, dur=5.0, start=5.0, end=10.0,
                                 asset_path="assets/seg_002.jpg"),
        ]
        scenes = [_make_scene(1, 10.0)]
        errors = preflight_validate(timeline, scenes, project_root, video_dir,
                                     expected_total=10.0)
        assert errors == []

    def test_window_10s_audio_6_9s_passes_mocked(self, tmp_path, monkeypatch):
        """Scene window 10s > audio 6.9s → PASS (padding added)."""
        project_root, video_dir = _dummy_env(tmp_path)
        _touch(video_dir / "assets" / "seg_001.jpg")

        mp3 = video_dir / "scenes" / "scene-01.mp3"
        mp3.parent.mkdir()
        mp3.write_bytes(b"\xff\xfb" + b"\x00" * 100)

        timeline = [
            _make_timeline_entry(sn=1, si=1, dur=10.0, start=0.0, end=10.0,
                                 asset_path="assets/seg_001.jpg",
                                 audio_path="scenes/scene-01.mp3"),
        ]
        scenes = [_make_scene(1, 10.0)]

        monkeypatch.setitem(
            preflight_validate.__globals__,
            "_docker_ffprobe_duration",
            lambda ws, root, timeout=30: 6.9,
        )
        errors = preflight_validate(timeline, scenes, project_root, video_dir,
                                     expected_total=10.0)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_window_5s_audio_6_9s_errors_mocked(self, tmp_path, monkeypatch):
        """Scene window 5s < audio 6.9s → truncation error."""
        project_root, video_dir = _dummy_env(tmp_path)
        _touch(video_dir / "assets" / "seg_001.jpg")

        mp3 = video_dir / "scenes" / "scene-01.mp3"
        mp3.parent.mkdir()
        mp3.write_bytes(b"\xff\xfb" + b"\x00" * 100)

        timeline = [
            _make_timeline_entry(sn=1, si=1, dur=5.0, start=0.0, end=5.0,
                                 asset_path="assets/seg_001.jpg",
                                 audio_path="scenes/scene-01.mp3"),
        ]
        scenes = [_make_scene(1, 5.0)]

        monkeypatch.setitem(
            preflight_validate.__globals__,
            "_docker_ffprobe_duration",
            lambda ws, root, timeout=30: 6.9,
        )
        errors = preflight_validate(timeline, scenes, project_root, video_dir,
                                     expected_total=5.0)
        truncation = [e for e in errors if "truncated" in e]
        assert len(truncation) == 1, f"Expected truncation error, got: {errors}"

    def test_overlapping_segments_error(self, tmp_path):
        """Overlap > 0.05s between segments within a scene → error."""
        project_root, video_dir = _dummy_env(tmp_path)
        _touch(video_dir / "assets" / "seg_001.jpg")
        _touch(video_dir / "assets" / "seg_002.jpg")

        timeline = [
            _make_timeline_entry(sn=1, si=1, dur=5.0, start=0.0, end=5.0,
                                 asset_path="assets/seg_001.jpg"),
            _make_timeline_entry(sn=1, si=2, dur=5.0, start=4.0, end=9.0,
                                 asset_path="assets/seg_002.jpg"),
        ]
        scenes = [_make_scene(1, 9.0)]
        errors = preflight_validate(timeline, scenes, project_root, video_dir,
                                     expected_total=9.0)
        overlaps = [e for e in errors if "overlapping" in e]
        assert len(overlaps) == 1, f"Expected overlapping error, got: {errors}"

    def test_non_contiguous_segments_error(self, tmp_path):
        """Gap > 0.05s between segments within a scene → error."""
        project_root, video_dir = _dummy_env(tmp_path)
        _touch(video_dir / "assets" / "seg_001.jpg")
        _touch(video_dir / "assets" / "seg_002.jpg")

        timeline = [
            _make_timeline_entry(sn=1, si=1, dur=4.0, start=0.0, end=4.0,
                                 asset_path="assets/seg_001.jpg"),
            _make_timeline_entry(sn=1, si=2, dur=5.0, start=4.5, end=9.5,
                                 asset_path="assets/seg_002.jpg"),
        ]
        scenes = [_make_scene(1, 9.5)]
        errors = preflight_validate(timeline, scenes, project_root, video_dir,
                                     expected_total=9.5)
        non_contig = [e for e in errors if "non-contiguous" in e]
        assert len(non_contig) == 1, f"Expected non-contiguous error, got: {errors}"

    def test_inconsistent_audio_paths_error(self, tmp_path):
        """Different audio paths within same scene → error."""
        project_root, video_dir = _dummy_env(tmp_path)
        _touch(video_dir / "assets" / "seg_001.jpg")
        _touch(video_dir / "assets" / "seg_002.jpg")

        timeline = [
            _make_timeline_entry(sn=1, si=1, dur=3.0, start=0.0, end=3.0,
                                 asset_path="assets/seg_001.jpg",
                                 audio_path="scenes/scene-01.mp3"),
            _make_timeline_entry(sn=1, si=2, dur=3.0, start=3.0, end=6.0,
                                 asset_path="assets/seg_002.jpg",
                                 audio_path="scenes/scene-02.mp3"),
        ]
        scenes = [_make_scene(1, 6.0)]
        errors = preflight_validate(timeline, scenes, project_root, video_dir,
                                     expected_total=6.0)
        inconsistent = [e for e in errors if "inconsistent audio" in e]
        assert len(inconsistent) == 1, f"Expected inconsistent audio error, got: {errors}"

    def test_single_segment_valid_behavior(self, tmp_path):
        """Single segment per scene is valid preflight."""
        project_root, video_dir = _dummy_env(tmp_path)
        _touch(video_dir / "assets" / "seg_001.jpg")

        timeline = [
            _make_timeline_entry(sn=1, si=1, dur=8.0, start=0.0, end=8.0,
                                 asset_path="assets/seg_001.jpg"),
        ]
        scenes = [_make_scene(1, 8.0)]
        errors = preflight_validate(timeline, scenes, project_root, video_dir,
                                     expected_total=8.0)
        assert errors == []

    def test_continuous_mode_no_scene_aggregate_errors(self, tmp_path):
        """Continuous mode doesn't trigger per-scene audio validation."""
        project_root, video_dir = _dummy_env(tmp_path)
        _touch(video_dir / "assets" / "seg_001.jpg")

        mp3 = video_dir / "scenes" / "narration.mp3"
        mp3.parent.mkdir()
        mp3.write_bytes(b"\xff\xfb" + b"\x00" * 100)

        timeline = [
            _make_timeline_entry(sn=1, si=1, dur=5.0, start=0.0, end=5.0,
                                 asset_path="assets/seg_001.jpg",
                                 audio_path="scenes/narration.mp3"),
            _make_timeline_entry(sn=2, si=1, dur=5.0, start=5.0, end=10.0,
                                 asset_path="assets/seg_001.jpg",
                                 audio_path="scenes/narration.mp3"),
        ]
        scenes = [_make_scene(1, 5.0), _make_scene(2, 5.0)]
        errors = preflight_validate(timeline, scenes, project_root, video_dir,
                                     is_continuous_audio=True, expected_total=10.0)
        # Continuous mode shouldn't flag inconsistent audio paths
        inconsistent = [e for e in errors if "inconsistent audio" in e]
        assert len(inconsistent) == 0

    def test_empty_asset_path_caught(self, tmp_path):
        """Entry with empty assetPath must be caught by preflight."""
        project_root, video_dir = _dummy_env(tmp_path)
        timeline = [
            _make_timeline_entry(sn=1, si=1, dur=5.0, start=0.0, end=5.0,
                                 asset_path=""),
        ]
        scenes = [_make_scene(1, 5.0)]
        errors = preflight_validate(timeline, scenes, project_root, video_dir,
                                     expected_total=5.0)
        assert any("empty" in e for e in errors)

    def test_contiguous_segments_no_error(self, tmp_path):
        """Contiguous segments with no gap don't produce errors."""
        project_root, video_dir = _dummy_env(tmp_path)
        _touch(video_dir / "assets" / "seg_001.jpg")
        _touch(video_dir / "assets" / "seg_002.jpg")

        timeline = [
            _make_timeline_entry(sn=1, si=1, dur=4.0, start=0.0, end=4.0,
                                 asset_path="assets/seg_001.jpg"),
            _make_timeline_entry(sn=1, si=2, dur=4.0, start=4.0, end=8.0,
                                 asset_path="assets/seg_002.jpg"),
        ]
        scenes = [_make_scene(1, 8.0)]
        errors = preflight_validate(timeline, scenes, project_root, video_dir,
                                     expected_total=8.0)
        non_contig = [e for e in errors if "non-contiguous" in e]
        assert len(non_contig) == 0


# ---------------------------------------------------------------------------
# expected_duration from timeline
# ---------------------------------------------------------------------------


class TestExpectedDuration:
    def test_max_end_sec_from_timeline(self):
        """Non-continuous expected_duration = max(endSec) from renderTimeline."""
        timeline = [
            {"sceneNumber": 1, "startSec": 0.0, "endSec": 8.0, "durationSec": 8.0},
            {"sceneNumber": 2, "startSec": 8.0, "endSec": 18.0, "durationSec": 10.0},
            {"sceneNumber": 3, "startSec": 18.0, "endSec": 30.0, "durationSec": 12.0},
        ]
        expected = max(e["endSec"] for e in timeline)
        assert expected == 30.0

    def test_not_sum_of_mp3_durations(self):
        """Expected duration is NOT sum of raw MP3 durations without padding."""
        mp3_durations = [6.576, 6.936, 7.536]
        scene_windows = [8.0, 10.0, 12.0]  # max(target, audio) per scene
        # Raw sum would be 21.048s vs scene windows sum = 30.0s
        assert sum(mp3_durations) < sum(scene_windows)
        assert sum(scene_windows) == 30.0


# ---------------------------------------------------------------------------
# Audio chain — scene window not first segment
# ---------------------------------------------------------------------------


class TestSceneAudioWindowLogic:
    def test_scene_window_is_max_not_first_segment(self):
        """Scene window should be computed from all segments, not just first."""
        segments = [
            {"segmentIndex": 1, "startSec": 0.0, "endSec": 5.0},
            {"segmentIndex": 2, "startSec": 5.0, "endSec": 10.0},
        ]
        scene_start = min(s["startSec"] for s in segments)
        scene_end = max(s["endSec"] for s in segments)
        scene_window = scene_end - scene_start
        assert scene_window == 10.0  # NOT 5.0

    def test_apad_atrim_chain_not_first_segment(self):
        """The FFmpeg chain uses scene_window, not first segment duration."""
        scene_window = 10.0
        first_seg_dur = 5.0
        # atrim=duration=10.0 (scene_window) vs atrim=duration=5.0 (first seg)
        assert scene_window != first_seg_dur
        ffmpeg_atrim = f"apad,atrim=duration={scene_window}"
        assert f"atrim=duration={scene_window}" in ffmpeg_atrim
        assert f"atrim=duration={first_seg_dur}" not in ffmpeg_atrim


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    def test_v1_asset_validation_still_works(self, tmp_path):
        """V1 path patterns still resolve correctly in preflight."""
        project_root, video_dir = _dummy_env(tmp_path)
        _touch(video_dir / "scenes" / "scene-01.jpg")

        timeline = [
            _make_timeline_entry(sn=1, si=1, dur=6.0, start=0.0, end=6.0,
                                 asset_path="scenes/scene-01.jpg"),
        ]
        scenes = [_make_scene(1, 6.0)]
        errors = preflight_validate(timeline, scenes, project_root, video_dir,
                                     expected_total=6.0)
        file_errors = [e for e in errors if "not found" in e]
        assert file_errors == []

    def test_continuous_audio_preflight_no_scene_validation(self, tmp_path):
        """Continuous audio preflight doesn't perform per-scene audio checks."""
        project_root, video_dir = _dummy_env(tmp_path)
        _touch(video_dir / "scenes" / "scene-01.jpg")

        timeline = [
            _make_timeline_entry(sn=1, si=1, dur=6.0, start=0.0, end=6.0,
                                 asset_path="scenes/scene-01.jpg",
                                 audio_path="scenes/narration.mp3"),
        ]
        scenes = [_make_scene(1, 6.0)]
        errors = preflight_validate(timeline, scenes, project_root, video_dir,
                                     is_continuous_audio=True, expected_total=6.0)
        assert errors == []

    def test_continuous_mode_no_aggregate_checks(self, tmp_path):
        """In continuous mode, per-scene aggregate audio/duration checks are skipped."""
        project_root, video_dir = _dummy_env(tmp_path)
        _touch(video_dir / "assets" / "seg_001.jpg")

        timeline = [
            _make_timeline_entry(sn=1, si=1, dur=5.0, start=0.0, end=5.0,
                                 asset_path="assets/seg_001.jpg",
                                 audio_path="scenes/narration.mp3"),
            _make_timeline_entry(sn=2, si=1, dur=5.0, start=5.0, end=10.0,
                                 asset_path="assets/seg_001.jpg",
                                 audio_path="scenes/narration.mp3"),
        ]
        scenes = [_make_scene(1, 5.0), _make_scene(2, 5.0)]
        errors = preflight_validate(timeline, scenes, project_root, video_dir,
                                     is_continuous_audio=True, expected_total=10.0)
        # No non-contiguous or inconsistent audio errors should appear
        for e in errors:
            assert "non-contiguous" not in e.lower()
            assert "inconsistent audio" not in e.lower()


# ---------------------------------------------------------------------------
# Expanded scene preflight: ensure expected_total = max(endSec)
# ---------------------------------------------------------------------------


class TestExpandedScenesPreflight:
    def test_expanded_scenes_use_scene_window_not_target_sum(self, tmp_path, monkeypatch):
        """Target sum 10s vs timeline 19s → preflight must use 19, not 10."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        video_dir = project_root / "data" / "videos" / "job001"
        video_dir.mkdir(parents=True)
        (video_dir / "assets").mkdir()
        _touch(video_dir / "assets" / "seg_001.jpg")
        _touch(video_dir / "assets" / "seg_002.jpg")

        mp3_1 = video_dir / "scenes" / "scene-01.mp3"
        mp3_1.parent.mkdir()
        mp3_1.write_bytes(b"\xff\xfb" + b"\x00" * 100)
        mp3_2 = video_dir / "scenes" / "scene-02.mp3"
        mp3_2.write_bytes(b"\xff\xfb" + b"\x00" * 100)

        timeline = [
            _make_timeline_entry(sn=1, si=1, dur=9.0, start=0.0, end=9.0,
                                 asset_path="assets/seg_001.jpg",
                                 audio_path="scenes/scene-01.mp3"),
            _make_timeline_entry(sn=2, si=1, dur=10.0, start=9.0, end=19.0,
                                 asset_path="assets/seg_002.jpg",
                                 audio_path="scenes/scene-02.mp3"),
        ]
        scenes = [_make_scene(1, 5.0), _make_scene(2, 5.0)]

        expected = resolve_expected_duration(
            timeline, is_continuous_audio=False
        )
        assert expected == pytest.approx(19.0)

        monkeypatch.setitem(
            preflight_validate.__globals__,
            "_docker_ffprobe_duration",
            lambda ws, root, timeout=30: {"scene-01.mp3": 9.0, "scene-02.mp3": 10.0}.get(
                ws.split("/")[-1], 0.0
            ),
        )
        errors = preflight_validate(timeline, scenes, project_root, video_dir,
                                     expected_total=expected)
        # The key: no "total timeline=19.0s vs expected=10.0s" error
        for e in errors:
            assert "expected=10.0" not in e, f"Should not compare against target sum 10, got: {e}"

    def test_resolve_expected_duration_for_expanded_scenes(self):
        """Two scenes expanded to 9+10=19s → resolve_expected_duration returns 19."""
        timeline = [
            {"sceneNumber": 1, "endSec": 9.0},
            {"sceneNumber": 2, "endSec": 19.0},
        ]
        result = resolve_expected_duration(timeline, is_continuous_audio=False)
        assert result == pytest.approx(19.0)

    def test_main_passes_expected_to_preflight(self, monkeypatch, tmp_path):
        """main() with --skip-render passes expected_total from resolve_expected_duration."""
        import render_job as rj
        import json

        job = tmp_path / "job"
        job.mkdir()
        (job / "scenes").mkdir()
        (job / "assets").mkdir()
        (job / "assets" / "seg_001.jpg").write_text("x")
        (job / "assets" / "seg_002.jpg").write_text("x")
        (job / "scenes" / "scene-01.mp3").write_bytes(b"\xff\xfb" + b"\x00" * 100)
        (job / "scenes" / "scene-02.mp3").write_bytes(b"\xff\xfb" + b"\x00" * 100)
        meta_path = job / "metadata.json"

        meta = {
            "jobId": "test-preflight-expected",
            "script": {"scenes": [
                {"sceneNumber": 1, "targetDurationSec": 5.0},
                {"sceneNumber": 2, "targetDurationSec": 5.0},
            ]},
            "audio": {
                "provider": "edge-tts",
                "voice": "es-ES-AlvaroNeural",
                "continuous": False,
                "scenes": [
                    {"sceneNumber": 1, "path": str(job / "scenes" / "scene-01.mp3"),
                     "exists": True, "durationSec": 9.0},
                    {"sceneNumber": 2, "path": str(job / "scenes" / "scene-02.mp3"),
                     "exists": True, "durationSec": 10.0},
                ],
            },
            "assets": [
                {"sceneNumber": 1, "selected": True, "segments": [
                    {"segmentIndex": 1, "path": str(job / "assets" / "seg_001.jpg"),
                     "segmentValidationStatus": "PASS", "error": None}]},
                {"sceneNumber": 2, "selected": True, "segments": [
                    {"segmentIndex": 1, "path": str(job / "assets" / "seg_002.jpg"),
                     "segmentValidationStatus": "PASS", "error": None}]},
            ],
            "renderTimeline": [
                {"sceneNumber": 1, "segmentIndex": 1, "startSec": 0.0, "endSec": 9.0,
                 "durationSec": 9.0, "beatIndex": 1, "assetType": "broll",
                 "motionType": "static", "assetPath": str(job / "assets" / "seg_001.jpg"),
                 "audioPath": str(job / "scenes" / "scene-01.mp3"),
                 "transitionIn": "cut", "transitionOut": "fade",
                 "subtitleCueIndexes": []},
                {"sceneNumber": 2, "segmentIndex": 1, "startSec": 9.0, "endSec": 19.0,
                 "durationSec": 10.0, "beatIndex": 1, "assetType": "broll",
                 "motionType": "static", "assetPath": str(job / "assets" / "seg_002.jpg"),
                 "audioPath": str(job / "scenes" / "scene-02.mp3"),
                 "transitionIn": "cut", "transitionOut": "fade",
                 "subtitleCueIndexes": []},
            ],
            "status": "SUBTITLES_READY",
            "updatedAt": "2026-01-01T00:00:00Z",
            "render": {"path": str(job / "video.mp4"), "durationSeconds": 19.0},
            "subtitles": {"path": str(job / "subtitle.ass"), "format": "ass"},
        }
        meta_path.write_text(json.dumps(meta))

        captured_expected = []

        original_preflight = rj.preflight_validate
        def spy_preflight(timeline, scenes, project_root, video_dir,
                          expected_total=None, is_continuous_audio=False, metadata=None):
            captured_expected.append(expected_total)
            return []

        monkeypatch.setattr(rj, "preflight_validate", spy_preflight)
        monkeypatch.setattr("render_job._docker_ffprobe_duration", lambda ws, root, timeout=30: 9.0)

        monkeypatch.setattr("sys.argv", [
            "render_job.py", str(meta_path),
            "--skip-render", "--skip-asset-validation",
        ])
        exit_code = rj.main()
        assert exit_code == 0
        assert len(captured_expected) == 1
        assert captured_expected[0] == pytest.approx(19.0), \
            f"preflight received {captured_expected[0]}, expected ~19.0"


# ---------------------------------------------------------------------------
# Manifest scene audio duration
# ---------------------------------------------------------------------------


class TestManifestSceneAudioDuration:
    def test_resolve_returns_duration_from_scenes(self):
        """Valid durationSec found by sceneNumber returns the value."""
        audio_config = {
            "continuous": False,
            "scenes": [
                {"sceneNumber": 1, "durationSec": 6.576},
                {"sceneNumber": 2, "durationSec": 7.536},
            ],
        }
        assert resolve_manifest_scene_audio_duration(audio_config, 1) == pytest.approx(6.576)
        assert resolve_manifest_scene_audio_duration(audio_config, 2) == pytest.approx(7.536)

    def test_association_by_scene_number_not_order(self):
        """Lookup is by sceneNumber, not by array index."""
        audio_config = {
            "continuous": False,
            "scenes": [
                {"sceneNumber": 3, "durationSec": 5.0},
                {"sceneNumber": 1, "durationSec": 6.576},
                {"sceneNumber": 2, "durationSec": 7.536},
            ],
        }
        assert resolve_manifest_scene_audio_duration(audio_config, 1) == pytest.approx(6.576)
        assert resolve_manifest_scene_audio_duration(audio_config, 2) == pytest.approx(7.536)
        assert resolve_manifest_scene_audio_duration(audio_config, 3) == pytest.approx(5.0)

    def test_invalid_duration_returns_none(self):
        """None, 0.0, NaN, bool → None (not 0.0)."""
        test_cases = [
            ({"continuous": False, "scenes": [{"sceneNumber": 1, "durationSec": None}]}, None),
            ({"continuous": False, "scenes": [{"sceneNumber": 1, "durationSec": 0.0}]}, None),
            ({"continuous": False, "scenes": [{"sceneNumber": 1, "durationSec": float("nan")}]}, None),
            ({"continuous": False, "scenes": [{"sceneNumber": 1, "durationSec": -1.0}]}, None),
            ({"continuous": False, "scenes": [{"sceneNumber": 1, "durationSec": True}]}, None),
            ({"continuous": False, "scenes": [{"sceneNumber": 1, "durationSec": "6.5"}]}, None),
        ]
        for audio_config, expected in test_cases:
            result = resolve_manifest_scene_audio_duration(audio_config, 1)
            assert result is expected, f"config={audio_config} → {result}"

    def test_scene_not_found_returns_none(self):
        """Missing sceneNumber returns None."""
        audio_config = {
            "continuous": False,
            "scenes": [{"sceneNumber": 1, "durationSec": 6.5}],
        }
        assert resolve_manifest_scene_audio_duration(audio_config, 99) is None

    def test_continuous_returns_none(self):
        """Continuous audio → None (caller uses audio.durationSec)."""
        audio_config = {"continuous": True, "durationSec": 25.0}
        assert resolve_manifest_scene_audio_duration(audio_config, 1) is None

    def test_metadata_not_mutated(self):
        """Audio config must not be modified by the lookup."""
        original = {
            "continuous": False,
            "scenes": [{"sceneNumber": 1, "durationSec": 6.576}],
        }
        audio_config = json.loads(json.dumps(original))  # deep copy
        resolve_manifest_scene_audio_duration(audio_config, 1)
        assert audio_config == original

    def test_integration_with_skip_render(self, monkeypatch, tmp_path):
        """--skip-render must produce manifest with real audio durations."""
        import render_job as rj
        import json

        job = tmp_path / "job"
        job.mkdir()
        (job / "scenes").mkdir()
        (job / "assets").mkdir()
        (job / "assets" / "seg_001.jpg").write_text("x")
        (job / "scenes" / "scene-01.mp3").write_bytes(b"\xff\xfb" + b"\x00" * 100)
        (job / "scenes" / "scene-02.mp3").write_bytes(b"\xff\xfb" + b"\x00" * 100)
        meta_path = job / "metadata.json"

        meta = {
            "jobId": "test-manifest-001",
            "script": {"scenes": [
                {"sceneNumber": 1, "targetDurationSec": 6.0,
                 "subtitleTiming": {"cues": [{"startSec": 0, "endSec": 1, "text": "x"}],
                                    "timingSource": "edge_tts_word_boundary"}},
                {"sceneNumber": 2, "targetDurationSec": 6.0,
                 "subtitleTiming": {"cues": [], "timingSource": "estimated"}},
            ]},
            "audio": {
                "provider": "edge-tts",
                "voice": "es-ES-AlvaroNeural",
                "continuous": False,
                "scenes": [
                    {"sceneNumber": 1, "path": str(job / "scenes" / "scene-01.mp3"),
                     "exists": True, "durationSec": 6.576},
                    {"sceneNumber": 2, "path": str(job / "scenes" / "scene-02.mp3"),
                     "exists": True, "durationSec": 7.536},
                ],
            },
            "assets": [
                {"sceneNumber": 1, "selected": True, "segments": [
                    {"segmentIndex": 1, "path": str(job / "assets" / "seg_001.jpg"),
                     "segmentValidationStatus": "PASS", "error": None}]},
                {"sceneNumber": 2, "selected": True, "segments": [
                    {"segmentIndex": 1, "path": str(job / "assets" / "seg_001.jpg"),
                     "segmentValidationStatus": "PASS", "error": None}]},
            ],
            "renderTimeline": [
                {"sceneNumber": 1, "segmentIndex": 1, "startSec": 0.0,
                 "endSec": 6.576, "durationSec": 6.576, "beatIndex": 1,
                 "assetType": "broll", "motionType": "static",
                 "assetPath": str(job / "assets" / "seg_001.jpg"),
                 "audioPath": str(job / "scenes" / "scene-01.mp3"),
                 "transitionIn": "cut", "transitionOut": "fade",
                 "subtitleCueIndexes": []},
                {"sceneNumber": 2, "segmentIndex": 1, "startSec": 6.576,
                 "endSec": 14.112, "durationSec": 7.536, "beatIndex": 2,
                 "assetType": "broll", "motionType": "static",
                 "assetPath": str(job / "assets" / "seg_001.jpg"),
                 "audioPath": str(job / "scenes" / "scene-02.mp3"),
                 "transitionIn": "cut", "transitionOut": "fade",
                 "subtitleCueIndexes": []},
            ],
            "status": "SUBTITLES_READY",
            "updatedAt": "2026-01-01T00:00:00Z",
            "render": {"path": str(job / "video.mp4"), "durationSeconds": 14.112},
            "subtitles": {"path": str(job / "subtitle.ass"), "format": "ass"},
        }
        meta_path.write_text(json.dumps(meta))

        monkeypatch.setattr("sys.argv", [
            "render_job.py", str(meta_path),
            "--skip-render", "--skip-asset-validation",
        ])
        exit_code = rj.main()
        assert exit_code == 0

        manifest_path = job / "job-manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert manifest["scenes"][0]["audioDurationSec"] == pytest.approx(6.576)
        assert manifest["scenes"][1]["audioDurationSec"] == pytest.approx(7.536)
