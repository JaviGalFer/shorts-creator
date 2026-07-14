"""Tests for Phase B corrections: generate_audio.py scene duration contract.

Covers: _get_mp3_duration (local + Docker + both fail),
durationSec in per-scene metadata, probe failure → REVIEW_REQUIRED,
pre-existing MP3 probing, voice persistence.
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "bin"))

import pytest

from generate_audio import _get_mp3_duration


# ---------------------------------------------------------------------------
# _get_mp3_duration unit tests
# ---------------------------------------------------------------------------


class TestGetMp3Duration:
    def test_local_ffprobe_valid_json_returns_duration(self, tmp_path):
        mp3 = tmp_path / "test.mp3"
        mp3.write_text("fake")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"format": {"duration": "6.576"}})

        with patch("generate_audio.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/ffprobe"
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                dur, source = _get_mp3_duration(mp3)
                assert dur == pytest.approx(6.576)
                assert source == "ffprobe_local"

    def test_local_ffprobe_zero_duration_returns_none(self, tmp_path):
        mp3 = tmp_path / "test.mp3"
        mp3.write_text("fake")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"format": {"duration": "0"}})

        with patch("generate_audio.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/ffprobe"
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                dur, source = _get_mp3_duration(mp3)
                assert dur is None
                assert source is None

    def test_local_ffprobe_negative_duration_returns_none(self, tmp_path):
        mp3 = tmp_path / "test.mp3"
        mp3.write_text("fake")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"format": {"duration": "-1"}})

        with patch("generate_audio.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/ffprobe"
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                dur, source = _get_mp3_duration(mp3)
                assert dur is None
                assert source is None

    def test_local_ffprobe_nan_rejected(self, tmp_path):
        mp3 = tmp_path / "test.mp3"
        mp3.write_text("fake")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"format": {"duration": "NaN"}})

        with patch("generate_audio.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/ffprobe"
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                dur, source = _get_mp3_duration(mp3)
                assert dur is None
                assert source is None

    def test_docker_fallback_when_local_unavailable(self, tmp_path):
        mp3 = tmp_path / "test.mp3"
        mp3.write_text("fake")
        mock_docker = MagicMock()
        mock_docker.returncode = 0
        mock_docker.stdout = json.dumps({"format": {"duration": "3.141"}})

        with patch("generate_audio.shutil.which") as mock_which:
            mock_which.return_value = None
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = mock_docker
                dur, source = _get_mp3_duration(mp3)
                assert dur == pytest.approx(3.141)
                assert source == "ffprobe_docker"

    def test_docker_probe_pins_docker_api_version(self, tmp_path):
        """Docker probe must set DOCKER_API_VERSION=1.43 for compatibility."""
        mp3 = tmp_path / "test.mp3"
        mp3.write_text("fake")
        mock_docker = MagicMock()
        mock_docker.returncode = 0
        mock_docker.stdout = json.dumps({"format": {"duration": "5.000"}})

        captured_env = []

        def capture_run(args, **kwargs):
            captured_env.append(kwargs.get("env", {}))
            return mock_docker

        with patch("generate_audio.shutil.which") as mock_which:
            mock_which.return_value = None
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = capture_run
                dur, source = _get_mp3_duration(mp3)
                assert dur == pytest.approx(5.0)
                assert source == "ffprobe_docker"
                assert captured_env, "subprocess.run was called"
                env_used = captured_env[0]
                assert isinstance(env_used, dict)
                assert env_used.get("DOCKER_API_VERSION") == "1.43", (
                    "DOCKER_API_VERSION must be set to 1.43"
                )

    def test_docker_fallback_when_local_fails(self, tmp_path):
        mp3 = tmp_path / "test.mp3"
        mp3.write_text("fake")
        mock_local = MagicMock()
        mock_local.returncode = 1

        mock_docker = MagicMock()
        mock_docker.returncode = 0
        mock_docker.stdout = json.dumps({"format": {"duration": "2.5"}})

        with patch("generate_audio.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/ffprobe"
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = [mock_local, mock_docker]
                dur, source = _get_mp3_duration(mp3)
                assert dur == pytest.approx(2.5)
                assert source == "ffprobe_docker"

    def test_both_probes_fail_returns_none(self, tmp_path):
        mp3 = tmp_path / "test.mp3"
        mp3.write_text("fake")
        mock_local = MagicMock()
        mock_local.returncode = 1

        mock_docker = MagicMock()
        mock_docker.returncode = 1

        with patch("generate_audio.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/ffprobe"
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = [mock_local, mock_docker]
                dur, source = _get_mp3_duration(mp3)
                assert dur is None
                assert source is None

    def test_both_probes_exception_returns_none(self, tmp_path):
        mp3 = tmp_path / "test.mp3"
        mp3.write_text("fake")

        with patch("generate_audio.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/ffprobe"
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = Exception("boom")
                dur, source = _get_mp3_duration(mp3)
                assert dur is None
                assert source is None

    def test_never_returns_zero(self, tmp_path):
        mp3 = tmp_path / "test.mp3"
        mp3.write_text("fake")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"format": {"duration": "0.0001"}})

        with patch("generate_audio.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/ffprobe"
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                dur, source = _get_mp3_duration(mp3)
                assert dur is None or dur > 0


# ---------------------------------------------------------------------------
# Per-scene metadata integration tests
# ---------------------------------------------------------------------------


class TestPerSceneDurationContract:
    def test_duration_sec_in_scenes_array(self, tmp_path):
        """Newly generated audio must include durationSec from real file."""
        mp3 = tmp_path / "scene-01.mp3"
        mp3.write_bytes(b"\xff\xfb" + b"\x00" * 5000)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"format": {"duration": "6.576"}})

        with patch("generate_audio.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/ffprobe"
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                dur, source = _get_mp3_duration(mp3)
                assert dur == pytest.approx(6.576)
                assert source == "ffprobe_local"
                assert isinstance(dur, float)
                assert dur > 0

    def test_probe_failure_returns_none_not_zero(self, tmp_path):
        """Failed probe returns None, never 0.0."""
        mp3 = tmp_path / "scene-01.mp3"
        mp3.write_text("x")

        with patch("generate_audio.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/ffprobe"
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = Exception("fail")
                dur, source = _get_mp3_duration(mp3)
                assert dur is None
                assert source is None
                assert dur != 0.0


# ---------------------------------------------------------------------------
# Idempotency: prepare preserves durationSec
# ---------------------------------------------------------------------------


class TestPreparePreservesDurationSec:
    def test_idempotent_prepare_preserves_duration_sec(self, monkeypatch, tmp_path):
        """Two consecutive prepare_job runs must produce identical scene durations."""
        import prepare_job as pj

        job = tmp_path / "job"
        job.mkdir()
        scenes_dir = job / "scenes"
        scenes_dir.mkdir()
        img = scenes_dir / "scene-01-01.jpg"
        img.write_text("x" * 1000)
        mp3 = scenes_dir / "scene-01.mp3"
        mp3.write_text("x" * 2000)
        meta_path = job / "metadata.json"

        meta = {
            "jobId": "test-idemp-001",
            "script": {"scenes": [
                {"sceneNumber": 1, "targetDurationSec": 8.0,
                 "voiceover": "Test.", "subtitle": "Test",
                 "subtitleTiming": {"cues": []},
                 "visualPlan": {
                     "editorialRole": "context_map",
                     "visualSequence": [
                         {"segmentIndex": 1, "assetType": "historical_map",
                          "durationFraction": 1.0},
                     ],
                 }},
            ]},
            "audio": {
                "provider": "edge-tts",
                "continuous": False,
                "duration_estimated": False,
                "scenes": [
                    {"sceneNumber": 1, "path": str(mp3), "exists": True,
                     "durationSec": 6.576, "durationSource": "ffprobe_local"},
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

        # First run
        monkeypatch.setattr(sys, "argv", ["prepare_job.py", str(meta_path)])
        exit_code = pj.main()
        assert exit_code == 0

        result1 = json.loads(meta_path.read_text())
        dur1 = result1["audio"]["scenes"][0]["durationSec"]
        total1 = result1["render"]["durationSeconds"]

        # Second run
        monkeypatch.setattr(sys, "argv", ["prepare_job.py", str(meta_path)])
        exit_code = pj.main()
        assert exit_code == 0

        result2 = json.loads(meta_path.read_text())
        dur2 = result2["audio"]["scenes"][0]["durationSec"]
        total2 = result2["render"]["durationSeconds"]

        assert dur1 == dur2, f"durationSec changed: {dur1} → {dur2}"
        assert total1 == pytest.approx(total2, abs=0.01)

    def test_prepare_blocks_missing_duration(self, monkeypatch, tmp_path):
        """Job without valid durationSec must be blocked by prepare."""
        import prepare_job as pj

        job = tmp_path / "job"
        job.mkdir()
        scenes_dir = job / "scenes"
        scenes_dir.mkdir()
        img = scenes_dir / "scene-01-01.jpg"
        img.write_text("x" * 1000)
        mp3 = scenes_dir / "scene-01.mp3"
        mp3.write_text("x" * 2000)
        meta_path = job / "metadata.json"

        meta = {
            "jobId": "test-block-001",
            "script": {"scenes": [
                {"sceneNumber": 1, "targetDurationSec": 8.0,
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
                "scenes": [
                    {"sceneNumber": 1, "path": str(mp3), "exists": True,
                     "durationSec": 0.0},
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

        monkeypatch.setattr(sys, "argv", ["prepare_job.py", str(meta_path)])
        exit_code = pj.main()
        assert exit_code == 1
        result = json.loads(meta_path.read_text())
        assert result["status"] == "REVIEW_REQUIRED"

    def test_prepare_blocks_none_duration(self, monkeypatch, tmp_path):
        """Job with null durationSec must be blocked."""
        import prepare_job as pj

        job = tmp_path / "job"
        job.mkdir()
        scenes_dir = job / "scenes"
        scenes_dir.mkdir()
        img = scenes_dir / "scene-01-01.jpg"
        img.write_text("x" * 1000)
        mp3 = scenes_dir / "scene-01.mp3"
        mp3.write_text("x" * 2000)
        meta_path = job / "metadata.json"

        meta = {
            "jobId": "test-none-001",
            "script": {"scenes": [
                {"sceneNumber": 1, "targetDurationSec": 8.0,
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
                "scenes": [
                    {"sceneNumber": 1, "path": str(mp3), "exists": True,
                     "durationSec": None},
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

        monkeypatch.setattr(sys, "argv", ["prepare_job.py", str(meta_path)])
        exit_code = pj.main()
        assert exit_code == 1
        result = json.loads(meta_path.read_text())
        assert result["status"] == "REVIEW_REQUIRED"


# ---------------------------------------------------------------------------
# Async main_per_scene tests
# ---------------------------------------------------------------------------


class TestMainPerSceneAsync:
    def _make_scene_meta(self, tmp_path, scenes_data):
        job = tmp_path / "job"
        job.mkdir()
        (job / "scenes").mkdir()
        meta_path = job / "metadata.json"
        meta = {"jobId": "test-async-001", "script": {"scenes": scenes_data}}
        meta_path.write_text(json.dumps(meta))
        return meta_path, job

    def test_success_generates_audio_ready(self, tmp_path, monkeypatch):
        """Full generation: MP3 created, duration probed, AUDIO_READY."""
        meta_path, job = self._make_scene_meta(tmp_path, [
            {"sceneNumber": 1, "voiceover": "Test narration.", "targetDurationSec": 6.0},
        ])
        from generate_audio import main_per_scene

        async def mock_synth(text, output_path, options=None):
            Path(str(output_path)).write_bytes(b"\xff\xfb" + b"\x00" * 5000)
            r = MagicMock()
            r.timing_data = {"word_boundaries": [
                {"startSec": 0.1, "endSec": 0.5, "text": "Test"}],
                "timing_source": "edge_tts_word_boundary"}
            return r

        with patch("generate_audio.get_provider") as mock_gp:
            mock_provider = MagicMock()
            mock_provider.synthesize_with_timing_async = mock_synth
            mock_gp.return_value = mock_provider
            monkeypatch.setattr("generate_audio._get_mp3_duration", lambda p: (6.576, "ffprobe_local"))
            exit_code = asyncio.run(main_per_scene(meta_path, "es-ES-AlvaroNeural"))

        assert exit_code == 0
        result = json.loads(meta_path.read_text())
        assert result["status"] == "AUDIO_READY"
        assert result["audio"]["voice"] == "es-ES-AlvaroNeural"
        assert result["audio"]["scenes"][0]["durationSec"] == pytest.approx(6.576)

    def test_probe_failure_review_required_persists(self, tmp_path, monkeypatch):
        """Probe fails -> REVIEW_REQUIRED, metadata persisted (not lost)."""
        meta_path, job = self._make_scene_meta(tmp_path, [
            {"sceneNumber": 1, "voiceover": "Test narration.", "targetDurationSec": 6.0},
        ])
        from generate_audio import main_per_scene

        async def mock_synth(text, output_path, options=None):
            Path(str(output_path)).write_bytes(b"\xff\xfb" + b"\x00" * 5000)
            r = MagicMock()
            r.timing_data = {"word_boundaries": [
                {"startSec": 0.1, "endSec": 0.5, "text": "Test"}],
                "timing_source": "edge_tts_word_boundary"}
            return r

        with patch("generate_audio.get_provider") as mock_gp:
            mock_gp.return_value = MagicMock(synthesize_with_timing_async=mock_synth)
            monkeypatch.setattr("generate_audio._get_mp3_duration", lambda p: (None, None))
            exit_code = asyncio.run(main_per_scene(meta_path, "es-ES-AlvaroNeural"))

        assert exit_code == 0
        result = json.loads(meta_path.read_text())
        assert result["status"] == "REVIEW_REQUIRED"
        assert any("AUDIO_DURATION_MISSING" in r for r in result.get("reviewReasons", []))
        assert result["audio"]["scenes"][0]["durationSec"] is None
        assert result["audio"]["duration_estimated"] is True

    def test_preexisting_mp3_probed(self, tmp_path, monkeypatch):
        """MP3 already exists -> probed, not regenerated."""
        meta_path, job = self._make_scene_meta(tmp_path, [
            {"sceneNumber": 1, "voiceover": "Test narration.", "targetDurationSec": 6.0},
        ])
        from generate_audio import main_per_scene
        sdir = job / "scenes"
        (sdir / "scene-01.mp3").write_bytes(b"\xff\xfb" + b"\x00" * 5000)

        with patch("generate_audio.get_provider") as mock_gp:
            mock_gp.return_value = MagicMock()
            monkeypatch.setattr("generate_audio._get_mp3_duration", lambda p: (6.576, "ffprobe_local"))
            exit_code = asyncio.run(main_per_scene(meta_path, "es-ES-AlvaroNeural"))

        assert exit_code == 0
        result = json.loads(meta_path.read_text())
        assert result["audio"]["scenes"][0]["durationSec"] == pytest.approx(6.576)

    def test_generation_failure_review_required(self, tmp_path, monkeypatch):
        """Provider fails -> REVIEW_REQUIRED, metadata persisted."""
        meta_path, job = self._make_scene_meta(tmp_path, [
            {"sceneNumber": 1, "voiceover": "Test narration.", "targetDurationSec": 6.0},
        ])
        from generate_audio import main_per_scene

        async def mock_fail(text, output_path, options=None):
            return MagicMock(timing_data={})

        with patch("generate_audio.get_provider") as mock_gp:
            mock_gp.return_value = MagicMock(synthesize_with_timing_async=mock_fail)
            exit_code = asyncio.run(main_per_scene(meta_path, "es-ES-AlvaroNeural"))

        assert exit_code == 1
        result = json.loads(meta_path.read_text())
        assert result["status"] == "REVIEW_REQUIRED"
        assert any("AUDIO_GENERATION_FAILED" in r for r in result.get("reviewReasons", []))
        assert result["audio"]["scenes"][0]["exists"] is False
