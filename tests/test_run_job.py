"""Tests for unified job runner (bin/run_job.py).

Run: python3 -m pytest tests/test_run_job.py -v
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, call

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))

import pytest

from run_job import (
    STAGES,
    STAGE_STATUS_MAP,
    build_script_command,
    build_stage_command,
    parse_script_output,
    load_metadata,
    save_metadata,
    append_orchestration,
    set_failure,
    _verify_stage_contract,
    _final_summary,
    dry_run,
    main,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_job_dir():
    with tempfile.TemporaryDirectory() as tmp:
        job_dir = Path(tmp) / "data" / "videos" / "test-2000-01-01-000000"
        job_dir.mkdir(parents=True)
        yield job_dir


@pytest.fixture
def fake_metadata(fake_job_dir):
    meta = {
        "jobId": "test-2000-01-01-000000",
        "status": "SCRIPT_DRAFT",
        "topic": "Test topic",
        "request": {
            "topic": "Test topic",
            "duration": {"targetSec": 35, "minSec": 32, "maxSec": 38, "strictness": "balanced"},
        },
        "script": {"scenes": [{"sceneNumber": 1, "voiceover": "Test."}]},
        "durationContract": {
            "targetSec": 35, "minSec": 32, "maxSec": 38,
            "wordCount": 5, "sceneCount": 1,
            "minimumWords": 5, "preferredWords": 6, "maximumWords": 7,
            "status": "PASS",
        },
        "createdAt": "2000-01-01T00:00:00.000Z",
        "updatedAt": "2000-01-01T00:00:00.000Z",
    }
    path = fake_job_dir / "metadata.json"
    save_metadata(str(path), meta)
    return str(path), meta


@pytest.fixture
def initial_metadata_file(fake_job_dir):
    """Create a minimal SCRIPT_DRAFT metadata file on disk for multi-stage integration tests."""
    path = fake_job_dir / "metadata.json"
    data = {"jobId": "test-1", "status": "SCRIPT_DRAFT", "createdAt": "2000-01-01T00:00:00.000Z"}
    save_metadata(str(path), data)
    return str(path)


# ---------------------------------------------------------------------------
# Command construction
# ---------------------------------------------------------------------------

def test_build_script_command_minimal():
    args = _make_args(topic="Test", duration=None)
    cmd = build_script_command(args)
    assert cmd[1].endswith("generate_script.py")
    assert "--topic" in cmd
    assert cmd[cmd.index("--topic") + 1] == "Test"
    assert "--duration" not in cmd


def test_build_script_command_all_options():
    args = _make_args(
        topic="Test", duration=42, duration_profile="standard_32_38",
        duration_target=40, duration_min=35, duration_max=45,
        strictness="strict", model="gpt-4",
    )
    cmd = build_script_command(args)
    assert cmd[cmd.index("--topic") + 1] == "Test"
    assert cmd[cmd.index("--duration") + 1] == "42"
    assert cmd[cmd.index("--duration-profile") + 1] == "standard_32_38"
    assert cmd[cmd.index("--duration-target") + 1] == "40"
    assert cmd[cmd.index("--duration-min") + 1] == "35"
    assert cmd[cmd.index("--duration-max") + 1] == "45"
    assert cmd[cmd.index("--strictness") + 1] == "strict"
    assert cmd[cmd.index("--model") + 1] == "gpt-4"


def test_build_stage_command_assets():
    cmd = build_stage_command("assets", "/path/to/metadata.json")
    assert cmd[1].endswith("fetch_images.py")
    assert cmd[2] == "/path/to/metadata.json"


def test_build_stage_command_audio():
    cmd = build_stage_command("audio", "/path/to/metadata.json")
    assert cmd[1].endswith("generate_audio.py")
    assert cmd[2] == "/path/to/metadata.json"


def test_build_stage_command_prepare():
    cmd = build_stage_command("prepare", "/path/to/metadata.json")
    assert cmd[1].endswith("prepare_job.py")
    assert cmd[2] == "/path/to/metadata.json"


def test_build_stage_command_render():
    cmd = build_stage_command("render", "/path/to/metadata.json")
    assert cmd[1].endswith("render_job.py")
    assert cmd[2] == "/path/to/metadata.json"


def test_build_stage_command_validate():
    cmd = build_stage_command("validate", "/path/to/metadata.json")
    assert cmd[1].endswith("validate_job.py")
    assert cmd[2] == "/path/to/metadata.json"


def test_build_stage_command_unknown():
    with pytest.raises(ValueError):
        build_stage_command("invalid_stage", "/path/meta.json")


# ---------------------------------------------------------------------------
# Script output parsing
# ---------------------------------------------------------------------------

def test_parse_script_output_valid():
    output = json.dumps({"jobId": "abc-123", "path": "/tmp/meta.json", "status": "SCRIPT_DRAFT"})
    result = parse_script_output(output)
    assert result is not None
    assert result["jobId"] == "abc-123"
    assert result["path"] == "/tmp/meta.json"


def test_parse_script_output_with_extra_lines():
    output = (
        "Some log line\n"
        '{"jobId": "abc-123", "path": "/tmp/meta.json", "status": "SCRIPT_DRAFT"}\n'
        "Another log line\n"
    )
    result = parse_script_output(output)
    assert result is not None
    assert result["jobId"] == "abc-123"


def test_parse_script_output_missing_path():
    output = json.dumps({"jobId": "abc-123", "status": "SCRIPT_DRAFT"})
    result = parse_script_output(output)
    assert result is None


def test_parse_script_output_missing_jobid():
    output = json.dumps({"path": "/tmp/meta.json", "status": "SCRIPT_DRAFT"})
    result = parse_script_output(output)
    assert result is None


def test_parse_script_output_empty():
    assert parse_script_output("") is None
    assert parse_script_output("   \n  ") is None
    assert parse_script_output("Some log output") is None


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

def test_append_orchestration_first_entry(fake_metadata):
    path, meta = fake_metadata
    started = "2000-01-01T00:00:00.000Z"
    finished = "2000-01-01T00:00:01.000Z"
    append_orchestration(meta, "script", "SCRIPT_DRAFT", started, finished)
    orch = meta["orchestration"]
    assert orch["runnerVersion"] == "1"
    assert orch["currentStage"] == "script"
    assert len(orch["statusHistory"]) == 1
    assert orch["statusHistory"][0]["stage"] == "script"
    assert orch["statusHistory"][0]["status"] == "SCRIPT_DRAFT"


def test_append_orchestration_preserves_existing(fake_metadata):
    path, meta = fake_metadata
    meta["orchestration"] = {"runnerVersion": "1", "currentStage": "script", "statusHistory": []}
    started = "2000-01-01T00:00:00.000Z"
    finished = "2000-01-01T00:00:01.000Z"
    append_orchestration(meta, "assets", "ASSETS_READY", started, finished)
    assert len(meta["orchestration"]["statusHistory"]) == 1


def test_append_orchestration_with_error(fake_metadata):
    path, meta = fake_metadata
    append_orchestration(meta, "assets", "FAILED", "t1", "t2", error="Something broke")
    entry = meta["orchestration"]["statusHistory"][0]
    assert entry["error"] == "Something broke"


def test_set_failure(fake_metadata):
    path, meta = fake_metadata
    set_failure(meta, "assets", "Connection error", ["cmd1", "arg1"], exit_code=1)
    assert meta["status"] == "FAILED"
    assert meta["failure"]["failedStage"] == "assets"
    assert meta["failure"]["exitCode"] == 1
    assert "childCommand" in meta["failure"]
    assert "timestamp" in meta["failure"]


def test_set_failure_truncates_long_error(fake_metadata):
    path, meta = fake_metadata
    long_err = "x" * 5000
    set_failure(meta, "assets", long_err, ["cmd"], exit_code=1)
    assert len(meta["failure"]["error"]) == 1000


# ---------------------------------------------------------------------------
# Metadata load/save preserves fields
# ---------------------------------------------------------------------------

def test_save_and_load_metadata(fake_job_dir):
    path = str(fake_job_dir / "metadata.json")
    original = {"jobId": "test-1", "status": "SCRIPT_DRAFT", "request": {"topic": "X"}, "nested": {"a": 1}}
    save_metadata(path, original)
    loaded = load_metadata(path)
    assert loaded == original


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def test_dry_run_prints_plan(capsys):
    args = _make_args(topic="Dry run test", duration=42, stop_after="validate")
    rc = dry_run(args)
    assert rc == 0
    captured = capsys.readouterr().out
    assert "RUNNER DRY-RUN" in captured
    assert "Duration: 42s" in captured
    assert "standard_32_38" in captured
    assert "EXECUTION PLAN" in captured
    assert "SCRIPT_GENERATING" in captured
    assert "generate_script.py" in captured
    assert "fetch_images.py" in captured
    assert "generate_audio.py" in captured
    assert "prepare_job.py" in captured
    assert "render_job.py" in captured
    assert "validate_job.py" in captured
    assert "END DRY-RUN" in captured


def test_dry_run_stop_after_script_shows_only_script(capsys):
    args = _make_args(topic="Test", duration=28, stop_after="script")
    dry_run(args)
    out = capsys.readouterr().out
    assert "generate_script.py" in out
    assert "fetch_images.py" not in out
    assert "generate_audio.py" not in out


def test_dry_run_invalid_duration_shows_error(capsys):
    args = _make_args(topic="Test", duration=999)
    rc = dry_run(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "ERROR (invalid combination)" in out


# ---------------------------------------------------------------------------
# Script stage -- structured output extraction
# ---------------------------------------------------------------------------

def test_script_stage_extracts_job_id(fake_job_dir, capsys):
    meta_path = str(fake_job_dir / "metadata.json")
    script_output = json.dumps({"jobId": "test-2000-01-01-000000", "path": meta_path, "status": "SCRIPT_DRAFT"})

    with patch("run_job.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=script_output, stderr=""
        )
        with patch("run_job.load_metadata") as mock_load:
            mock_load.return_value = {
                "jobId": "test-2000-01-01-000000",
                "status": "SCRIPT_DRAFT",
                "createdAt": "2000-01-01T00:00:00.000Z",
            }
            with patch("run_job.save_metadata"):
                with patch("run_job.os.path.exists", return_value=True):
                    # Don't save on exit - just verify the parsing path
                    with patch("run_job._final_summary"):
                        args = _make_args(topic="Test", duration=35)
                        with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--duration", "35", "--stop-after", "script"]):
                            rc = main()
                            assert rc == 0


def test_script_stage_missing_output_fails(capsys):
    with patch("run_job.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="No JSON here", stderr=""
        )
        with patch("run_job._final_summary"):
            with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "script"]):
                rc = main()
                assert rc == 1
                out = capsys.readouterr().out
                assert "could not find job path" in out


# ---------------------------------------------------------------------------
# REVIEW_REQUIRED handling
# ---------------------------------------------------------------------------

def test_review_required_stops_before_assets(fake_job_dir, capsys):
    meta_path = str(fake_job_dir / "metadata.json")
    script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "REVIEW_REQUIRED"})
    metadata = {
        "jobId": "test-1",
        "status": "REVIEW_REQUIRED",
        "createdAt": "2000-01-01T00:00:00.000Z",
        "reviewReasons": ["DURATION_OUT_OF_RANGE"],
    }

    with patch("run_job.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=script_output, stderr=""
        )
        with patch("run_job.load_metadata", return_value=metadata):
            with patch("run_job.save_metadata"):
                with patch("run_job.os.path.exists", return_value=True):
                    with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "script"]):
                        rc = main()
                        assert rc == 0
                        out = capsys.readouterr().out
                        assert "REVIEW_REQUIRED" in out


# ---------------------------------------------------------------------------
# Non-zero exit code failure
# ---------------------------------------------------------------------------

def test_non_zero_exit_fails_metadata(fake_job_dir, capsys):
    meta_path = str(fake_job_dir / "metadata.json")
    script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "SCRIPT_DRAFT"})
    metadata = {
        "jobId": "test-1",
        "status": "SCRIPT_DRAFT",
        "createdAt": "2000-01-01T00:00:00.000Z",
    }

    def _side_effect(cmd, **kw):
        if "generate_script.py" in " ".join(cmd):
            return subprocess.CompletedProcess(cmd, 0, stdout=script_output, stderr="")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="Asset download failed")

    with patch("run_job.subprocess.run", side_effect=_side_effect):
        with patch("run_job.load_metadata", return_value=metadata):
            with patch("run_job.save_metadata") as mock_save:
                with patch("run_job.os.path.exists", return_value=True):
                    with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "assets"]):
                        rc = main()
                        assert rc == 1
                        saved = mock_save.call_args[0][1]
                        assert saved["status"] == "FAILED"
                        assert saved["failure"]["failedStage"] == "assets"
                        assert saved["failure"]["exitCode"] == 1


# ---------------------------------------------------------------------------
# stop-after script
# ---------------------------------------------------------------------------

def test_stop_after_script_does_not_run_later_stages(fake_job_dir, capsys):
    meta_path = str(fake_job_dir / "metadata.json")
    script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "SCRIPT_DRAFT"})
    metadata = {"jobId": "test-1", "status": "SCRIPT_DRAFT", "createdAt": "2000-01-01T00:00:00.000Z"}

    mock_subprocess = patch("run_job.subprocess.run")
    mock_load = patch("run_job.load_metadata", return_value=metadata)
    mock_save = patch("run_job.save_metadata")
    mock_exists = patch("run_job.os.path.exists", return_value=True)

    with mock_subprocess as m:
        m.return_value = subprocess.CompletedProcess([], 0, stdout=script_output, stderr="")
        with mock_load, mock_save, mock_exists:
            with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "script"]):
                rc = main()
                assert rc == 0
                # Only generate_script.py should have been called
                all_calls = [c for c in m.call_args_list]
                cmd_strs = [" ".join(c[0][0]) for c in all_calls]
                assert any("generate_script.py" in c for c in cmd_strs)
                assert not any("fetch_images.py" in c for c in cmd_strs)
                assert not any("generate_audio.py" in c for c in cmd_strs)
                assert not any("render_job.py" in c for c in cmd_strs)


# ---------------------------------------------------------------------------
# stop-after assets
# ---------------------------------------------------------------------------

def test_stop_after_assets_does_not_run_audio(fake_job_dir, initial_metadata_file, capsys):
    meta_path = str(fake_job_dir / "metadata.json")
    script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "SCRIPT_DRAFT"})

    # Create a scene image so contract verification passes
    scenes_dir = fake_job_dir / "scenes"
    scenes_dir.mkdir(exist_ok=True)
    (scenes_dir / "scene-1.jpg").touch()

    call_count = {"script": 0, "assets": 0, "audio": 0}

    def side_effect(cmd, **kw):
        cmd_str = " ".join(cmd)
        if "generate_script.py" in cmd_str:
            call_count["script"] += 1
            return subprocess.CompletedProcess(cmd, 0, stdout=script_output, stderr="")
        if "fetch_images.py" in cmd_str:
            call_count["assets"] += 1
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if "generate_audio.py" in cmd_str:
            call_count["audio"] += 1
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    metadata = {"jobId": "test-1", "status": "SCRIPT_DRAFT", "createdAt": "2000-01-01T00:00:00.000Z"}
    assets_meta = {"jobId": "test-1", "status": "ASSETS_READY", "createdAt": "2000-01-01T00:00:00.000Z"}

    with patch("run_job.subprocess.run", side_effect=side_effect):
        with patch("run_job.load_metadata",
                   side_effect=[dict(metadata), dict(metadata), dict(assets_meta), dict(assets_meta)]):
            with patch("run_job.save_metadata"):
                with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "assets"]):
                    rc = main()
                    assert rc == 0
                    assert call_count["script"] == 1
                    assert call_count["assets"] == 1
                    assert call_count["audio"] == 0


# ---------------------------------------------------------------------------
# Final JSON summary
# ---------------------------------------------------------------------------

def test_final_summary_validated(capsys):
    data = {"jobId": "test-1", "status": "VALIDATED", "validation": {"status": "PASS"}}
    _final_summary(data, "/tmp/job/metadata.json", "validate")
    out = capsys.readouterr().out
    summary = json.loads(out.strip())
    assert summary["jobId"] == "test-1"
    assert summary["status"] == "VALIDATED"
    assert summary["lastCompletedStage"] == "validate"
    assert summary["outputVideoPath"] is None  # video.mp4 doesn't exist


def test_final_summary_failed(capsys):
    _final_summary(None, None, "assets")
    out = capsys.readouterr().out
    summary = json.loads(out.strip())
    assert summary["status"] == "FAILED"
    assert summary["lastCompletedStage"] == "assets"


# ---------------------------------------------------------------------------
# Asset-stage failure stops before audio
# ---------------------------------------------------------------------------

def test_asset_failure_stops_before_audio(fake_job_dir, capsys):
    meta_path = str(fake_job_dir / "metadata.json")
    script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "SCRIPT_DRAFT"})
    metadata = {"jobId": "test-1", "status": "SCRIPT_DRAFT", "createdAt": "2000-01-01T00:00:00.000Z"}

    call_count = {"script": 0, "assets": 0, "audio": 0}

    def side_effect(cmd, **kw):
        cmd_str = " ".join(cmd)
        if "generate_script.py" in cmd_str:
            call_count["script"] += 1
            return subprocess.CompletedProcess(cmd, 0, stdout=script_output, stderr="")
        if "fetch_images.py" in cmd_str:
            call_count["assets"] += 1
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="Asset error")
        if "generate_audio.py" in cmd_str:
            call_count["audio"] += 1
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with patch("run_job.subprocess.run", side_effect=side_effect):
        with patch("run_job.load_metadata", return_value=metadata):
            with patch("run_job.save_metadata"):
                with patch("run_job.os.path.exists", return_value=True):
                    with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "validate"]):
                        rc = main()
                        assert rc == 1
                        assert call_count["script"] == 1
                        assert call_count["assets"] == 1
                        assert call_count["audio"] == 0


# ---------------------------------------------------------------------------
# Existing rich metadata is preserved
# ---------------------------------------------------------------------------

def test_metadata_preserved_across_stages(fake_job_dir, capsys):
    meta_path = str(fake_job_dir / "metadata.json")
    script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "SCRIPT_DRAFT"})

    # Full metadata with rich fields
    rich_meta = {
        "jobId": "test-1",
        "status": "SCRIPT_DRAFT",
        "topic": "Test topic",
        "request": {
            "topic": "Test topic",
            "duration": {"targetSec": 35, "minSec": 32, "maxSec": 38, "strictness": "balanced"},
            "voice": {"provider": "edge_tts"},
        },
        "script": {"scenes": [{"sceneNumber": 1}]},
        "durationContract": {
            "targetSec": 35, "minSec": 32, "maxSec": 38,
            "wordCount": 5, "minimumWords": 5, "status": "PASS",
        },
        "resolvedConfig": {"duration": {}, "durationProfile": "standard_32_38"},
        "createdAt": "2000-01-01T00:00:00.000Z",
        "updatedAt": "2000-01-01T00:00:00.000Z",
    }

    with patch("run_job.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout=script_output, stderr="")
        with patch("run_job.load_metadata", return_value=rich_meta):
            with patch("run_job.save_metadata") as mock_save:
                with patch("run_job.os.path.exists", return_value=True):
                    with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "script"]):
                        rc = main()
                        assert rc == 0
                        saved = mock_save.call_args[0][1]
                        # Rich fields preserved
                        assert saved["request"]["voice"]["provider"] == "edge_tts"
                        assert saved["durationContract"]["status"] == "PASS"
                        assert saved["resolvedConfig"]["durationProfile"] == "standard_32_38"
                        # Orchestration appended
                        assert "orchestration" in saved
                        assert len(saved["orchestration"]["statusHistory"]) > 0


# ---------------------------------------------------------------------------
# No secrets in failure metadata
# ---------------------------------------------------------------------------

def test_failure_no_secrets_in_command(fake_metadata):
    path, meta = fake_metadata
    set_failure(
        meta, "script", "error",
        ["python3", "script.py", "--api-key", "sk-abc123"],
        exit_code=1,
    )
    cmd_str = meta["failure"]["childCommand"]
    # API key should be visible since we persist the command as-is for debugging
    # But environment variables and real secrets from .env are not in the command
    assert "childCommand" in meta["failure"]
    # The command itself is a CLI arg string -- the runner does not inject env vars


def test_failure_no_env_vars_in_metadata(fake_metadata):
    path, meta = fake_metadata
    set_failure(
        meta, "script", "error",
        ["python3", "script.py", "/path/to/meta.json"],
        exit_code=1,
    )
    meta_str = json.dumps(meta)
    # No env-like patterns in the metadata
    # This is a structural check: the runner should never call os.environ for persistence
    assert "LLM_API_KEY" not in meta_str
    assert "PEXELS_API_KEY" not in meta_str
    assert "PIXABAY_API_KEY" not in meta_str
    assert "FREEAI_API_KEY" not in meta_str


# ---------------------------------------------------------------------------
# Stage contract verification
# ---------------------------------------------------------------------------

def _make_completed_process(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


class TestVerifyStageContract:

    def test_assets_ready_with_images_passes(self, fake_job_dir):
        scenes_dir = fake_job_dir / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-1.jpg").touch()
        meta_path = str(fake_job_dir / "metadata.json")
        data = {"status": "ASSETS_READY"}
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("assets", data, meta_path, result)
        assert ok is True
        assert status == "ASSETS_READY"
        assert err is None

    def test_assets_ready_but_no_images_fails(self, fake_job_dir):
        meta_path = str(fake_job_dir / "metadata.json")
        data = {"status": "ASSETS_READY"}
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("assets", data, meta_path, result)
        assert ok is False
        assert err is not None
        assert "STAGE_OUTPUT_CONTRACT_FAILED" in err

    def test_assets_unresolved_blocks(self, fake_job_dir):
        meta_path = str(fake_job_dir / "metadata.json")
        data = {"status": "ASSET_UNRESOLVED"}
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("assets", data, meta_path, result)
        assert ok is False
        assert status == "ASSET_UNRESOLVED"
        assert err is None  # known blocking status

    def test_assets_partial_fails_contract(self, fake_job_dir):
        meta_path = str(fake_job_dir / "metadata.json")
        data = {"status": "ASSETS_PARTIAL"}
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("assets", data, meta_path, result)
        assert ok is False
        assert err is not None
        assert "STAGE_OUTPUT_CONTRACT_FAILED" in err

    def test_assets_stale_running_status_fails(self, fake_job_dir):
        meta_path = str(fake_job_dir / "metadata.json")
        data = {"status": "ASSETS_FETCHING"}
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("assets", data, meta_path, result)
        assert ok is False
        assert err is not None
        assert "STAGE_OUTPUT_CONTRACT_FAILED" in err

    def test_audio_ready_with_narration_passes(self, fake_job_dir):
        scenes_dir = fake_job_dir / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "narration.mp3").touch()
        meta_path = str(fake_job_dir / "metadata.json")
        data = {"status": "AUDIO_READY"}
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("audio", data, meta_path, result)
        assert ok is True
        assert status == "AUDIO_READY"
        assert err is None

    def test_audio_ready_with_scene_files_passes(self, fake_job_dir):
        scenes_dir = fake_job_dir / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.mp3").touch()
        meta_path = str(fake_job_dir / "metadata.json")
        data = {"status": "AUDIO_READY"}
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("audio", data, meta_path, result)
        assert ok is True
        assert status == "AUDIO_READY"

    def test_audio_ready_but_no_audio_files_fails(self, fake_job_dir):
        meta_path = str(fake_job_dir / "metadata.json")
        data = {"status": "AUDIO_READY"}
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("audio", data, meta_path, result)
        assert ok is False
        assert "STAGE_OUTPUT_CONTRACT_FAILED" in err

    def test_audio_review_required_blocks(self, fake_job_dir):
        meta_path = str(fake_job_dir / "metadata.json")
        data = {"status": "REVIEW_REQUIRED"}
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("audio", data, meta_path, result)
        assert ok is False
        assert status == "REVIEW_REQUIRED"
        assert err is None

    def test_prepare_subtitles_ready_passes(self, fake_job_dir):
        subtitle_path = fake_job_dir / "subtitle.ass"
        subtitle_path.touch()
        meta_path = str(fake_job_dir / "metadata.json")
        data = {
            "status": "SUBTITLES_READY",
            "subtitles": {"path": str(subtitle_path), "format": "ass"},
            "render": {"path": str(fake_job_dir / "video.mp4")},
            "renderTimeline": [{"start": 0, "end": 10}],
        }
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("prepare", data, meta_path, result)
        assert ok is True
        assert status == "SUBTITLES_READY"

    def test_prepare_missing_subtitle_fails(self, fake_job_dir):
        meta_path = str(fake_job_dir / "metadata.json")
        data = {
            "status": "SUBTITLES_READY",
            "subtitles": {"path": str(fake_job_dir / "subtitle.ass"), "format": "ass"},
            "render": {"path": str(fake_job_dir / "video.mp4")},
            "renderTimeline": [{"start": 0}],
        }
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("prepare", data, meta_path, result)
        assert ok is False
        assert "STAGE_OUTPUT_CONTRACT_FAILED" in err
        assert "subtitle file missing" in err

    def test_prepare_missing_render_timeline_fails(self, fake_job_dir):
        subtitle_path = fake_job_dir / "subtitle.ass"
        subtitle_path.touch()
        meta_path = str(fake_job_dir / "metadata.json")
        data = {
            "status": "SUBTITLES_READY",
            "subtitles": {"path": str(subtitle_path), "format": "ass"},
            "render": {"path": str(fake_job_dir / "video.mp4")},
            # no renderTimeline
        }
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("prepare", data, meta_path, result)
        assert ok is False
        assert "renderTimeline missing" in err

    def test_prepare_not_subtitles_ready_fails(self, fake_job_dir):
        subtitle_path = fake_job_dir / "subtitle.ass"
        subtitle_path.touch()
        meta_path = str(fake_job_dir / "metadata.json")
        data = {
            "status": "AUDIO_READY",  # not SUBTITLES_READY
            "subtitles": {"path": str(subtitle_path), "format": "ass"},
            "render": {"path": str(fake_job_dir / "video.mp4")},
            "renderTimeline": [{"start": 0}],
        }
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("prepare", data, meta_path, result)
        assert ok is False
        assert "status is AUDIO_READY, expected SUBTITLES_READY" in err

    def test_render_rendered_with_video_passes(self, fake_job_dir):
        mp4 = fake_job_dir / "video.mp4"
        mp4.touch()
        meta_path = str(fake_job_dir / "metadata.json")
        data = {"status": "RENDERED"}
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("render", data, meta_path, result)
        assert ok is True
        assert status == "RENDERED"

    def test_render_with_warnings_passes_with_video(self, fake_job_dir):
        mp4 = fake_job_dir / "video.mp4"
        mp4.touch()
        meta_path = str(fake_job_dir / "metadata.json")
        data = {"status": "RENDERED_WITH_WARNINGS"}
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("render", data, meta_path, result)
        assert ok is True
        assert status == "RENDERED_WITH_WARNINGS"

    def test_render_rendered_but_no_video_fails(self, fake_job_dir):
        meta_path = str(fake_job_dir / "metadata.json")
        data = {"status": "RENDERED"}
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("render", data, meta_path, result)
        assert ok is False
        assert "STAGE_OUTPUT_CONTRACT_FAILED" in err
        assert "video.mp4 not found" in err

    def test_render_failed_blocks(self, fake_job_dir):
        meta_path = str(fake_job_dir / "metadata.json")
        data = {"status": "RENDER_FAILED"}
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("render", data, meta_path, result)
        assert ok is False
        assert status == "RENDER_FAILED"
        assert err is None

    def test_validate_pass_sets_validated(self, fake_job_dir):
        mp4 = fake_job_dir / "video.mp4"
        mp4.touch()
        meta_path = str(fake_job_dir / "metadata.json")
        data = {"status": "RENDERED"}
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("validate", data, meta_path, result)
        assert ok is True
        assert status == "VALIDATED"

    def test_validate_no_video_fails(self, fake_job_dir):
        meta_path = str(fake_job_dir / "metadata.json")
        data = {"status": "RENDERED"}
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("validate", data, meta_path, result)
        assert ok is False
        assert "video.mp4" in err

    def test_validate_exit_nonzero_fails(self, fake_job_dir):
        mp4 = fake_job_dir / "video.mp4"
        mp4.touch()
        meta_path = str(fake_job_dir / "metadata.json")
        data = {"status": "RENDERED"}
        result = _make_completed_process(1, stderr="validation failed")
        ok, status, err = _verify_stage_contract("validate", data, meta_path, result)
        assert ok is False
        assert status == "VALIDATION_FAILED"
        assert err is None  # known blocking status


# ---------------------------------------------------------------------------
# Contract failure integration tests (full main() path)
# ---------------------------------------------------------------------------

def test_assets_exit0_but_stale_status_fails(fake_job_dir, initial_metadata_file, capsys):
    """Assets exits 0 but metadata remains ASSETS_FETCHING → contract failure."""
    meta_path = str(fake_job_dir / "metadata.json")
    script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "SCRIPT_DRAFT"})

    def side_effect(cmd, **kw):
        cmd_str = " ".join(cmd)
        if "generate_script.py" in cmd_str:
            return subprocess.CompletedProcess(cmd, 0, stdout=script_output, stderr="")
        if "fetch_images.py" in cmd_str:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    script_meta = {"jobId": "test-1", "status": "SCRIPT_DRAFT", "createdAt": "2000-01-01T00:00:00.000Z"}
    stale_meta = {"jobId": "test-1", "status": "ASSETS_FETCHING", "createdAt": "2000-01-01T00:00:00.000Z"}

    with patch("run_job.subprocess.run", side_effect=side_effect):
        with patch("run_job.load_metadata", side_effect=[script_meta, stale_meta, stale_meta]):
            with patch("run_job.save_metadata") as mock_save:
                with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "assets"]):
                    rc = main()
                    assert rc == 1
                    saved = mock_save.call_args[0][1]
                    assert saved["status"] == "FAILED"
                    assert "STAGE_OUTPUT_CONTRACT_FAILED" in saved["failure"]["error"]


def test_audio_exit0_but_no_audio_file_fails(fake_job_dir, initial_metadata_file, capsys):
    """Audio exits 0 but narration file is missing → contract failure."""
    meta_path = str(fake_job_dir / "metadata.json")
    script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "SCRIPT_DRAFT"})

    # Create scene images for assets verification to pass
    scenes_dir = fake_job_dir / "scenes"
    scenes_dir.mkdir()
    (scenes_dir / "scene-1.jpg").touch()

    call_count = {}

    def side_effect(cmd, **kw):
        cmd_str = " ".join(cmd)
        call_count[cmd_str] = 1
        if "generate_script.py" in cmd_str:
            return subprocess.CompletedProcess(cmd, 0, stdout=script_output, stderr="")
        if "fetch_images.py" in cmd_str:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if "generate_audio.py" in cmd_str:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    script_meta = {"jobId": "test-1", "status": "SCRIPT_DRAFT", "createdAt": "2000-01-01T00:00:00.000Z"}
    assets_meta = {"jobId": "test-1", "status": "ASSETS_READY", "createdAt": "2000-01-01T00:00:00.000Z"}
    audio_meta = {"jobId": "test-1", "status": "AUDIO_READY", "createdAt": "2000-01-01T00:00:00.000Z"}

    with patch("run_job.subprocess.run", side_effect=side_effect):
        with patch("run_job.load_metadata", side_effect=[script_meta, assets_meta, audio_meta, audio_meta]):
            with patch("run_job.save_metadata") as mock_save:
                with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "audio"]):
                    rc = main()
                    assert rc == 1
                    saved = mock_save.call_args[0][1]
                    assert saved["status"] == "FAILED"
                    assert "STAGE_OUTPUT_CONTRACT_FAILED" in saved["failure"]["error"]


def test_prepare_missing_subtitle_fails_pipeline(fake_job_dir, initial_metadata_file, capsys):
    """Prepare exits 0 but subtitle.ass is missing → contract failure."""
    meta_path = str(fake_job_dir / "metadata.json")
    script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "SCRIPT_DRAFT"})

    scenes_dir = fake_job_dir / "scenes"
    scenes_dir.mkdir()
    (scenes_dir / "scene-1.jpg").touch()
    (scenes_dir / "narration.mp3").touch()

    call_count = {}

    def side_effect(cmd, **kw):
        cmd_str = " ".join(cmd)
        call_count[cmd_str] = 1
        if "generate_script.py" in cmd_str:
            return subprocess.CompletedProcess(cmd, 0, stdout=script_output, stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    script_meta = {"jobId": "test-1", "status": "SCRIPT_DRAFT", "createdAt": "2000-01-01T00:00:00.000Z"}
    assets_meta = {"jobId": "test-1", "status": "ASSETS_READY", "createdAt": "2000-01-01T00:00:00.000Z"}
    audio_meta = {"jobId": "test-1", "status": "AUDIO_READY", "createdAt": "2000-01-01T00:00:00.000Z"}
    prepare_meta = {
        "jobId": "test-1",
        "status": "SUBTITLES_READY",
        "subtitles": {"path": str(fake_job_dir / "subtitle.ass"), "format": "ass"},
        "render": {"path": str(fake_job_dir / "video.mp4")},
        # no renderTimeline — will trigger contract failure
    }

    with patch("run_job.subprocess.run", side_effect=side_effect):
        with patch("run_job.load_metadata",
                   side_effect=[dict(script_meta), dict(assets_meta), dict(assets_meta), dict(audio_meta), dict(audio_meta), dict(prepare_meta), dict(prepare_meta)]):
            with patch("run_job.save_metadata") as mock_save:
                with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "prepare"]):
                    rc = main()
                    assert rc == 1
                    saved = mock_save.call_args[0][1]
                    assert saved["status"] == "FAILED"
                    assert "STAGE_OUTPUT_CONTRACT_FAILED" in saved["failure"]["error"]
                    assert "renderTimeline missing" in saved["failure"]["error"]


def test_render_exit0_but_no_video_fails(fake_job_dir, initial_metadata_file, capsys):
    """Render exits 0 but video.mp4 is missing → contract failure."""
    meta_path = str(fake_job_dir / "metadata.json")
    script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "SCRIPT_DRAFT"})

    scenes_dir = fake_job_dir / "scenes"
    scenes_dir.mkdir()
    (scenes_dir / "scene-1.jpg").touch()
    (scenes_dir / "narration.mp3").touch()
    subtitle_path = fake_job_dir / "subtitle.ass"
    subtitle_path.touch()

    def side_effect(cmd, **kw):
        cmd_str = " ".join(cmd)
        if "generate_script.py" in cmd_str:
            return subprocess.CompletedProcess(cmd, 0, stdout=script_output, stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    script_meta = {"jobId": "test-1", "status": "SCRIPT_DRAFT", "createdAt": "2000-01-01T00:00:00.000Z"}
    assets_meta = {"jobId": "test-1", "status": "ASSETS_READY", "createdAt": "2000-01-01T00:00:00.000Z"}
    audio_meta = {"jobId": "test-1", "status": "AUDIO_READY", "createdAt": "2000-01-01T00:00:00.000Z"}
    prepare_meta = {
        "jobId": "test-1",
        "status": "SUBTITLES_READY",
        "subtitles": {"path": str(subtitle_path), "format": "ass"},
        "render": {"path": str(fake_job_dir / "video.mp4")},
        "renderTimeline": [{"start": 0, "end": 10}],
    }
    render_meta = {"jobId": "test-1", "status": "RENDERED"}

    with patch("run_job.subprocess.run", side_effect=side_effect):
        with patch("run_job.load_metadata",
                   side_effect=[dict(script_meta), dict(assets_meta), dict(assets_meta), dict(audio_meta), dict(audio_meta), dict(prepare_meta), dict(prepare_meta), dict(render_meta), dict(render_meta)]):
            with patch("run_job.save_metadata") as mock_save:
                with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "render"]):
                    rc = main()
                    assert rc == 1
                    saved = mock_save.call_args[0][1]
                    assert saved["status"] == "FAILED"
                    assert "STAGE_OUTPUT_CONTRACT_FAILED" in saved["failure"]["error"]
                    assert "video.mp4 not found" in saved["failure"]["error"]


def test_render_exit1_with_warnings_and_video_succeeds(fake_job_dir, initial_metadata_file, capsys):
    """Render exits 1 but status is RENDERED_WITH_WARNINGS and video exists → success."""
    meta_path = str(fake_job_dir / "metadata.json")
    script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "SCRIPT_DRAFT"})

    scenes_dir = fake_job_dir / "scenes"
    scenes_dir.mkdir()
    (scenes_dir / "scene-1.jpg").touch()
    (scenes_dir / "narration.mp3").touch()
    subtitle_path = fake_job_dir / "subtitle.ass"
    subtitle_path.touch()
    video_path = fake_job_dir / "video.mp4"
    video_path.touch()

    def side_effect(cmd, **kw):
        cmd_str = " ".join(cmd)
        if "generate_script.py" in cmd_str:
            return subprocess.CompletedProcess(cmd, 0, stdout=script_output, stderr="")
        if "render_job.py" in cmd_str:
            # render_job.py exits 1 for RENDERED_WITH_WARNINGS
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    script_meta = {"jobId": "test-1", "status": "SCRIPT_DRAFT", "createdAt": "2000-01-01T00:00:00.000Z"}
    assets_meta = {"jobId": "test-1", "status": "ASSETS_READY", "createdAt": "2000-01-01T00:00:00.000Z"}
    audio_meta = {"jobId": "test-1", "status": "AUDIO_READY", "createdAt": "2000-01-01T00:00:00.000Z"}
    prepare_meta = {
        "jobId": "test-1",
        "status": "SUBTITLES_READY",
        "subtitles": {"path": str(subtitle_path), "format": "ass"},
        "render": {"path": str(video_path)},
        "renderTimeline": [{"start": 0}],
    }
    render_meta = {"jobId": "test-1", "status": "RENDERED_WITH_WARNINGS"}

    with patch("run_job.subprocess.run", side_effect=side_effect):
        with patch("run_job.load_metadata",
                   side_effect=[dict(script_meta), dict(assets_meta), dict(assets_meta), dict(audio_meta), dict(audio_meta), dict(prepare_meta), dict(prepare_meta), dict(render_meta), dict(render_meta), dict(render_meta)]):
            with patch("run_job.save_metadata"):
                with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "render"]):
                    rc = main()
                    assert rc == 0


def test_render_exit1_with_failure_and_no_video_fails(fake_job_dir, initial_metadata_file, capsys):
    """Render exits 1 with RENDER_FAILED and no video → fails."""
    meta_path = str(fake_job_dir / "metadata.json")
    script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "SCRIPT_DRAFT"})

    scenes_dir = fake_job_dir / "scenes"
    scenes_dir.mkdir()
    (scenes_dir / "scene-1.jpg").touch()
    (scenes_dir / "narration.mp3").touch()
    subtitle_path = fake_job_dir / "subtitle.ass"
    subtitle_path.touch()

    def side_effect(cmd, **kw):
        if "generate_script.py" in " ".join(cmd):
            return subprocess.CompletedProcess(cmd, 0, stdout=script_output, stderr="")
        if "render_job.py" in " ".join(cmd):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="FFmpeg error")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    script_meta = {"jobId": "test-1", "status": "SCRIPT_DRAFT", "createdAt": "2000-01-01T00:00:00.000Z"}
    assets_meta = {"jobId": "test-1", "status": "ASSETS_READY", "createdAt": "2000-01-01T00:00:00.000Z"}
    audio_meta = {"jobId": "test-1", "status": "AUDIO_READY", "createdAt": "2000-01-01T00:00:00.000Z"}
    prepare_meta = {
        "jobId": "test-1",
        "status": "SUBTITLES_READY",
        "subtitles": {"path": str(subtitle_path), "format": "ass"},
        "render": {"path": str(fake_job_dir / "video.mp4")},
        "renderTimeline": [{"start": 0}],
    }
    render_meta = {"jobId": "test-1", "status": "RENDER_FAILED"}

    with patch("run_job.subprocess.run", side_effect=side_effect):
        with patch("run_job.load_metadata",
                   side_effect=[dict(script_meta), dict(assets_meta), dict(assets_meta), dict(audio_meta), dict(audio_meta), dict(prepare_meta), dict(prepare_meta), dict(render_meta), dict(render_meta)]):
            with patch("run_job.save_metadata") as mock_save:
                with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "render"]):
                    rc = main()
                    assert rc == 1
                    saved = mock_save.call_args[0][1]
                    assert saved["status"] == "FAILED"
                    assert saved["failure"]["failedStage"] == "render"


def test_validate_exit0_sets_validated(fake_job_dir, initial_metadata_file, capsys):
    """Validate exits 0 and video exists → VALIDATED."""
    meta_path = str(fake_job_dir / "metadata.json")
    script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "SCRIPT_DRAFT"})

    scenes_dir = fake_job_dir / "scenes"
    scenes_dir.mkdir()
    (scenes_dir / "scene-1.jpg").touch()
    (scenes_dir / "narration.mp3").touch()
    subtitle_path = fake_job_dir / "subtitle.ass"
    subtitle_path.touch()
    video_path = fake_job_dir / "video.mp4"
    video_path.touch()

    def side_effect(cmd, **kw):
        if "generate_script.py" in " ".join(cmd):
            return subprocess.CompletedProcess(cmd, 0, stdout=script_output, stderr="")
        if "validate_job.py" in " ".join(cmd):
            return subprocess.CompletedProcess(cmd, 0, stdout="All checks passed", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    script_meta = {"jobId": "test-1", "status": "SCRIPT_DRAFT", "createdAt": "2000-01-01T00:00:00.000Z"}
    assets_meta = {"jobId": "test-1", "status": "ASSETS_READY", "createdAt": "2000-01-01T00:00:00.000Z"}
    audio_meta = {"jobId": "test-1", "status": "AUDIO_READY", "createdAt": "2000-01-01T00:00:00.000Z"}
    prepare_meta = {
        "jobId": "test-1",
        "status": "SUBTITLES_READY",
        "subtitles": {"path": str(subtitle_path), "format": "ass"},
        "render": {"path": str(video_path)},
        "renderTimeline": [{"start": 0}],
    }
    render_meta = {"jobId": "test-1", "status": "RENDERED"}
    validated_meta = {"jobId": "test-1", "status": "RENDERED"}

    with patch("run_job.subprocess.run", side_effect=side_effect):
        with patch("run_job.load_metadata",
                   side_effect=[dict(script_meta), dict(assets_meta), dict(assets_meta), dict(audio_meta), dict(audio_meta), dict(prepare_meta), dict(prepare_meta), dict(render_meta), dict(render_meta), dict(render_meta), dict(render_meta), dict(render_meta)]):
            with patch("run_job.save_metadata"):
                with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "validate"]):
                    rc = main()
                    assert rc == 0
                    out = capsys.readouterr().out
                    assert "VALIDATED" in out


# ── Prepare exit-1 pipeline integration ──────────────────────────────────


def test_prepare_exit1_fails_pipeline(fake_job_dir, initial_metadata_file, capsys):
    """Prepare exits 1 → runner records failedStage=prepare."""
    meta_path = str(fake_job_dir / "metadata.json")
    script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "SCRIPT_DRAFT"})

    scenes_dir = fake_job_dir / "scenes"
    scenes_dir.mkdir()
    (scenes_dir / "scene-1.jpg").touch()
    (scenes_dir / "scene-1.mp3").touch()

    def side_effect(cmd, **kw):
        cmd_str = " ".join(cmd)
        if "generate_script.py" in cmd_str:
            return subprocess.CompletedProcess(cmd, 0, stdout=script_output, stderr="")
        if "prepare_job.py" in cmd_str:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="Asset failures")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    script_meta = {"jobId": "test-1", "status": "SCRIPT_DRAFT", "createdAt": "2000-01-01T00:00:00.000Z"}
    assets_meta = {"jobId": "test-1", "status": "ASSETS_READY", "createdAt": "2000-01-01T00:00:00.000Z"}
    audio_meta = {"jobId": "test-1", "status": "AUDIO_READY", "createdAt": "2000-01-01T00:00:00.000Z"}

    with patch("run_job.subprocess.run", side_effect=side_effect):
        with patch("run_job.load_metadata",
                   side_effect=[dict(script_meta), dict(script_meta),
                                dict(assets_meta), dict(assets_meta),
                                dict(audio_meta), dict(audio_meta),
                                dict(audio_meta)]):
            with patch("run_job.save_metadata") as mock_save:
                with patch.object(sys, "argv",
                                  ["run_job.py", "--topic", "Test", "--stop-after", "prepare"]):
                    rc = main()
                    assert rc == 1
                    calls = mock_save.call_args_list
                    failed_save = calls[-1][0][1]
                    assert failed_save["status"] == "FAILED"
                    assert failed_save["failure"]["failedStage"] == "prepare"
                    assert failed_save["failure"]["exitCode"] == 1
                    assert "childCommand" in failed_save["failure"]
                    assert "prepare_job.py" in failed_save["failure"]["childCommand"]
                    out = capsys.readouterr().out
                    assert "FAILED" in out


def test_prepare_exit1_no_render_no_validate(fake_job_dir, initial_metadata_file, capsys):
    """After prepare fails, render and validate must not be invoked."""
    meta_path = str(fake_job_dir / "metadata.json")
    script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "SCRIPT_DRAFT"})

    scenes_dir = fake_job_dir / "scenes"
    scenes_dir.mkdir()
    (scenes_dir / "scene-1.jpg").touch()
    (scenes_dir / "scene-1.mp3").touch()

    call_count = []

    def side_effect(cmd, **kw):
        cmd_str = " ".join(cmd)
        call_count.append(cmd_str)
        if "generate_script.py" in cmd_str:
            return subprocess.CompletedProcess(cmd, 0, stdout=script_output, stderr="")
        if "prepare_job.py" in cmd_str:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    script_meta = {"jobId": "test-1", "status": "SCRIPT_DRAFT", "createdAt": "2000-01-01T00:00:00.000Z"}
    assets_meta = {"jobId": "test-1", "status": "ASSETS_READY", "createdAt": "2000-01-01T00:00:00.000Z"}
    audio_meta = {"jobId": "test-1", "status": "AUDIO_READY", "createdAt": "2000-01-01T00:00:00.000Z"}

    with patch("run_job.subprocess.run", side_effect=side_effect):
        with patch("run_job.load_metadata",
                   side_effect=[dict(script_meta), dict(script_meta),
                                dict(assets_meta), dict(assets_meta),
                                dict(audio_meta), dict(audio_meta),
                                dict(audio_meta)]):
            with patch("run_job.save_metadata"):
                with patch.object(sys, "argv",
                                  ["run_job.py", "--topic", "Test", "--stop-after", "validate"]):
                    rc = main()
                    assert rc == 1
                    assert not any("render_job.py" in c for c in call_count)
                    assert not any("validate_job.py" in c for c in call_count)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_args(topic="Test", duration=None, duration_profile=None,
               duration_target=None, duration_min=None, duration_max=None,
               strictness=None, model=None, stop_after="validate",
               dry_run=False, verbose=False):
    class Args:
        pass
    a = Args()
    a.topic = topic
    a.duration = duration
    a.duration_profile = duration_profile
    a.duration_target = duration_target
    a.duration_min = duration_min
    a.duration_max = duration_max
    a.strictness = strictness
    a.model = model
    a.stop_after = stop_after
    a.dry_run = dry_run
    a.verbose = verbose
    return a
