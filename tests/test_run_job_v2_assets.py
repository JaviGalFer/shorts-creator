"""Tests for v2 assets integration in bin/run_job.py.

Run: python3 -m pytest tests/test_run_job_v2_assets.py -v
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))

import pytest

from shorts_creator.pipeline.orchestrator import (
    _verify_stage_contract,
    build_stage_command,
    STAGE_SCRIPTS,
)
from visual_plan_v2 import SCHEMA_VERSION as V2_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_job_dir():
    with tempfile.TemporaryDirectory() as tmp:
        job_dir = Path(tmp) / "data" / "videos" / "test-2000-01-01-000000"
        job_dir.mkdir(parents=True)
        yield job_dir


def _make_completed_process(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


def _v2_scene(scene_number=1, segment_index=1):
    return {
        "sceneNumber": scene_number,
        "visualPlan": {
            "_schemaVersion": V2_SCHEMA_VERSION,
            "visualIntent": "show",
            "subjects": ["Test Subject"],
            "searchQueries": ["test query"],
            "assetPreferences": ["photograph"],
            "visualSequence": [
                {
                    "segmentIndex": segment_index,
                    "assetPreference": "photograph",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
        },
    }


def _v1_scene(scene_number=1):
    return {
        "sceneNumber": scene_number,
        "visualPlan": {
            "editorialRole": "B-Roll",
            "strategy": "search",
            "searchQueries": ["test v1 query"],
        },
    }


# ---------------------------------------------------------------------------
# build_stage_command — v2 script resolution
# ---------------------------------------------------------------------------

class TestBuildStageCommandV2Only:

    def test_assets_always_uses_v2(self):
        cmd = build_stage_command("assets", "/path/meta.json")
        assert cmd[1].endswith("fetch_images_v2.py")
        assert cmd[2] == "/path/meta.json"

    def test_assets_v2_with_metadata(self):
        v2_meta = {"script": {"scenes": [_v2_scene()]}}
        cmd = build_stage_command("assets", "/path/meta.json", metadata=v2_meta)
        assert cmd[1].endswith("fetch_images_v2.py")
        assert cmd[2] == "/path/meta.json"

    def test_assets_without_metadata(self):
        cmd = build_stage_command("assets", "/path/meta.json", metadata=None)
        assert cmd[1].endswith("fetch_images_v2.py")

    def test_assets_with_v1_metadata(self):
        v1_meta = {"script": {"scenes": [_v1_scene()]}}
        cmd = build_stage_command("assets", "/path/meta.json", metadata=v1_meta)
        assert cmd[1].endswith("fetch_images_v2.py")

    def test_non_assets_stage_unchanged(self):
        for stage in ["audio", "prepare", "render", "validate"]:
            expected_script = STAGE_SCRIPTS[stage]
            v2_meta = {"script": {"scenes": [_v2_scene()]}}
            cmd = build_stage_command(stage, "/path/meta.json", metadata=v2_meta)
            assert cmd[1].endswith(expected_script)


# ---------------------------------------------------------------------------
# v2 assets contract (_verify_stage_contract)
# ---------------------------------------------------------------------------

class TestV2AssetsContract:

    def test_v2_assets_ready_with_images_passes(self, fake_job_dir):
        assets_dir = fake_job_dir / "assets"
        assets_dir.mkdir()
        (assets_dir / "seg_001.jpg").touch()
        meta_path = str(fake_job_dir / "metadata.json")
        data = {
            "status": "ASSETS_READY",
            "script": {"scenes": [_v2_scene()]},
        }
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("assets", data, meta_path, result)
        assert ok is True
        assert status == "ASSETS_READY"
        assert err is None

    def test_v2_assets_ready_no_images_fails(self, fake_job_dir):
        assets_dir = fake_job_dir / "assets"
        assets_dir.mkdir()
        meta_path = str(fake_job_dir / "metadata.json")
        data = {
            "status": "ASSETS_READY",
            "script": {"scenes": [_v2_scene()]},
        }
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("assets", data, meta_path, result)
        assert ok is False
        assert err is not None
        assert "STAGE_OUTPUT_CONTRACT_FAILED" in err

    def test_v2_assets_ready_no_assets_dir_fails(self, fake_job_dir):
        meta_path = str(fake_job_dir / "metadata.json")
        data = {
            "status": "ASSETS_READY",
            "script": {"scenes": [_v2_scene()]},
        }
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("assets", data, meta_path, result)
        assert ok is False
        assert err is not None
        assert "STAGE_OUTPUT_CONTRACT_FAILED" in err

    def test_v2_assets_ready_supports_multiple_extensions(self, fake_job_dir):
        for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4"]:
            assets_dir = fake_job_dir / "assets"
            if assets_dir.exists():
                import shutil
                shutil.rmtree(str(assets_dir))
            assets_dir.mkdir()
            (assets_dir / f"seg_001{ext}").touch()
            meta_path = str(fake_job_dir / "metadata.json")
            data = {
                "status": "ASSETS_READY",
                "script": {"scenes": [_v2_scene()]},
            }
            result = _make_completed_process(0)
            ok, status, err = _verify_stage_contract("assets", data, meta_path, result)
            assert ok is True, f"Failed for extension {ext}"
            assert status == "ASSETS_READY"

    def test_v2_assets_partial_graceful_block(self, fake_job_dir):
        meta_path = str(fake_job_dir / "metadata.json")
        data = {
            "status": "ASSETS_PARTIAL",
            "script": {"scenes": [_v2_scene()]},
        }
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("assets", data, meta_path, result)
        assert ok is False
        assert status == "ASSETS_PARTIAL"
        assert err is None  # graceful block in v2

    def test_v2_asset_unresolved_graceful_block(self, fake_job_dir):
        meta_path = str(fake_job_dir / "metadata.json")
        data = {
            "status": "ASSET_UNRESOLVED",
            "script": {"scenes": [_v2_scene()]},
        }
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("assets", data, meta_path, result)
        assert ok is False
        assert status == "ASSET_UNRESOLVED"
        assert err is None

    def test_v2_review_required_graceful_block(self, fake_job_dir):
        meta_path = str(fake_job_dir / "metadata.json")
        data = {
            "status": "REVIEW_REQUIRED",
            "script": {"scenes": [_v2_scene()]},
        }
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("assets", data, meta_path, result)
        assert ok is False
        assert status == "REVIEW_REQUIRED"
        assert err is None

    def test_v2_unknown_status_fails_contract(self, fake_job_dir):
        meta_path = str(fake_job_dir / "metadata.json")
        data = {
            "status": "ASSETS_FETCHING",
            "script": {"scenes": [_v2_scene()]},
        }
        result = _make_completed_process(0)
        ok, status, err = _verify_stage_contract("assets", data, meta_path, result)
        assert ok is False
        assert err is not None
        assert "STAGE_OUTPUT_CONTRACT_FAILED" in err


# ---------------------------------------------------------------------------
# v2 guard — blocks without --stop-after assets
# ---------------------------------------------------------------------------

class TestV2NoGuardAfterAssets:

    def test_main_v2_assets_with_stop_after_assets_works(self, fake_job_dir):
        meta_path = str(fake_job_dir / "metadata.json")
        script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "SCRIPT_DRAFT"})
        script_meta = {"jobId": "test-1", "status": "SCRIPT_DRAFT", "createdAt": "2000-01-01T00:00:00.000Z",
                        "script": {"scenes": [_v2_scene()]}}
        assets_meta = {"jobId": "test-1", "status": "ASSETS_READY", "createdAt": "2000-01-01T00:00:00.000Z",
                       "script": {"scenes": [_v2_scene()]}}

        assets_dir = fake_job_dir / "assets"
        assets_dir.mkdir()
        (assets_dir / "seg_001.jpg").touch()

        def side_effect(cmd, **kw):
            cmd_str = " ".join(cmd)
            if "generate_script.py" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, stdout=script_output, stderr="")
            if "fetch_images_v2.py" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch("shorts_creator.pipeline.orchestrator.subprocess.run", side_effect=side_effect):
            with patch("shorts_creator.pipeline.orchestrator.load_metadata",
                       side_effect=[dict(script_meta), dict(script_meta),
                                    dict(assets_meta), dict(assets_meta)]):
                with patch("shorts_creator.pipeline.orchestrator.save_metadata"):
                    with patch("shorts_creator.pipeline.orchestrator.os.path.exists", return_value=True):
                        with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "assets"]):
                            rc = __import__("run_job").main()
                            assert rc == 0

    def test_main_v2_assets_without_stop_after_no_longer_blocks(self, fake_job_dir, capsys):
        meta_path = str(fake_job_dir / "metadata.json")
        script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "SCRIPT_DRAFT"})
        script_meta = {"jobId": "test-1", "status": "SCRIPT_DRAFT", "createdAt": "2000-01-01T00:00:00.000Z",
                        "script": {"scenes": [_v2_scene()]}}
        assets_meta = {"jobId": "test-1", "status": "ASSETS_READY", "createdAt": "2000-01-01T00:00:00.000Z",
                       "script": {"scenes": [_v2_scene()]}}
        audio_meta = {"jobId": "test-1", "status": "AUDIO_READY", "createdAt": "2000-01-01T00:00:00.000Z",
                       "script": {"scenes": [_v2_scene()]}}

        assets_dir = fake_job_dir / "assets"
        assets_dir.mkdir()
        (assets_dir / "seg_001.jpg").touch()

        scenes_dir = fake_job_dir / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "narration.mp3").write_text("x" * 1000)

        def side_effect(cmd, **kw):
            cmd_str = " ".join(cmd)
            if "generate_script.py" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, stdout=script_output, stderr="")
            if "fetch_images_v2.py" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            if "generate_audio.py" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch("shorts_creator.pipeline.orchestrator.subprocess.run", side_effect=side_effect):
            with patch("shorts_creator.pipeline.orchestrator.load_metadata",
                       side_effect=[dict(script_meta), dict(script_meta),
                                    dict(assets_meta), dict(assets_meta),
                                    dict(audio_meta), dict(audio_meta)]):
                with patch("shorts_creator.pipeline.orchestrator.save_metadata"):
                    with patch("shorts_creator.pipeline.orchestrator.os.path.exists", return_value=True):
                        with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "audio"]):
                            rc = __import__("run_job").main()
                            assert rc == 0
                            out = capsys.readouterr().out
                            assert "V2_RUNTIME_INTEGRATION_PENDING" not in out
                            assert "audio" in out.lower() or "[audio]" in out

    def test_v2_runtime_pending_guard_removed(self, fake_job_dir, capsys):
        meta_path = str(fake_job_dir / "metadata.json")
        script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "SCRIPT_DRAFT"})
        script_meta = {"jobId": "test-1", "status": "SCRIPT_DRAFT", "createdAt": "2000-01-01T00:00:00.000Z",
                        "script": {"scenes": [_v2_scene()]}}
        assets_meta = {"jobId": "test-1", "status": "ASSETS_READY", "createdAt": "2000-01-01T00:00:00.000Z",
                       "script": {"scenes": [_v2_scene()]}}

        assets_dir = fake_job_dir / "assets"
        assets_dir.mkdir()
        (assets_dir / "seg_001.jpg").touch()

        saved_metas = []

        def mock_save(path, data):
            saved_metas.append(dict(data))

        def side_effect(cmd, **kw):
            cmd_str = " ".join(cmd)
            if "generate_script.py" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, stdout=script_output, stderr="")
            if "fetch_images_v2.py" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch("shorts_creator.pipeline.orchestrator.subprocess.run", side_effect=side_effect):
            with patch("shorts_creator.pipeline.orchestrator.load_metadata",
                       side_effect=[dict(script_meta), dict(script_meta),
                                    dict(assets_meta), dict(assets_meta)]):
                with patch("shorts_creator.pipeline.orchestrator.save_metadata", side_effect=mock_save):
                    with patch("shorts_creator.pipeline.orchestrator.os.path.exists", return_value=True):
                        with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "assets"]):
                            rc = __import__("run_job").main()
                            assert rc == 0

        for meta in saved_metas:
            assert meta.get("status") != "V2_RUNTIME_INTEGRATION_PENDING"


# ---------------------------------------------------------------------------
# Mixed schema fail-fast in main()
# ---------------------------------------------------------------------------

class TestMixedSchemaFailFast:

    def test_main_mixed_schema_returns_1(self, fake_job_dir, capsys):
        meta_path = str(fake_job_dir / "metadata.json")
        script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "SCRIPT_DRAFT"})
        mixed_meta = {
            "jobId": "test-1",
            "status": "SCRIPT_DRAFT",
            "createdAt": "2000-01-01T00:00:00.000Z",
            "script": {
                "scenes": [
                    {"sceneNumber": 1, "visualPlan": {"_schemaVersion": V2_SCHEMA_VERSION}},
                    {"sceneNumber": 2, "visualPlan": {"editorialRole": "B-Roll", "strategy": "search", "searchQueries": ["test"]}},
                ]
            },
        }

        def side_effect(cmd, **kw):
            cmd_str = " ".join(cmd)
            if "generate_script.py" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, stdout=script_output, stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch("shorts_creator.pipeline.orchestrator.subprocess.run", side_effect=side_effect):
            with patch("shorts_creator.pipeline.orchestrator.load_metadata",
                       side_effect=[dict(mixed_meta), dict(mixed_meta)]):
                with patch("shorts_creator.pipeline.orchestrator.save_metadata") as mock_save:
                    with patch("shorts_creator.pipeline.orchestrator.os.path.exists", return_value=True):
                        with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "assets"]):
                            rc = __import__("run_job").main()
                            assert rc == 1
                            out = capsys.readouterr().out
                            assert "MIXED_VISUAL_PLAN_SCHEMA_VERSIONS" in out
                            saved = mock_save.call_args[0][1]
                            assert saved["status"] == "FAILED"
                            assert "MIXED_VISUAL_PLAN_SCHEMA_VERSIONS" in saved["failure"]["error"]

    def test_main_mixed_schema_does_not_run_fetch_images(self, fake_job_dir, capsys):
        meta_path = str(fake_job_dir / "metadata.json")
        script_output = json.dumps({"jobId": "test-1", "path": meta_path, "status": "SCRIPT_DRAFT"})
        mixed_meta = {
            "jobId": "test-1",
            "status": "SCRIPT_DRAFT",
            "createdAt": "2000-01-01T00:00:00.000Z",
            "script": {
                "scenes": [
                    {"sceneNumber": 1, "visualPlan": {"_schemaVersion": V2_SCHEMA_VERSION}},
                    {"sceneNumber": 2, "visualPlan": {"editorialRole": "B-Roll", "strategy": "search"}},
                ]
            },
        }

        call_stages = []

        def side_effect(cmd, **kw):
            cmd_str = " ".join(cmd)
            if "generate_script.py" in cmd_str:
                call_stages.append("script")
                return subprocess.CompletedProcess(cmd, 0, stdout=script_output, stderr="")
            if "fetch_images" in cmd_str:
                call_stages.append("assets")
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch("shorts_creator.pipeline.orchestrator.subprocess.run", side_effect=side_effect):
            with patch("shorts_creator.pipeline.orchestrator.load_metadata",
                       side_effect=[dict(mixed_meta), dict(mixed_meta)]):
                with patch("shorts_creator.pipeline.orchestrator.save_metadata"):
                    with patch("shorts_creator.pipeline.orchestrator.os.path.exists", return_value=True):
                        with patch.object(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "assets"]):
                            rc = __import__("run_job").main()
                            assert rc == 1
                            assert "script" in call_stages
                            assert "assets" not in call_stages


# ---------------------------------------------------------------------------
# Integration: no provider calls, no real jobs
# ---------------------------------------------------------------------------

def test_no_provider_modules_imported_in_run_job():
    run_job_source = (PROJECT / "bin" / "run_job.py").read_text()
    forbidden = [
        "visual_provider_wikimedia_v2",
        "visual_asset_executor_v2",
        "visual_asset_router_v2",
        "visual_asset_bridge_v2",
        "visual_provider_config_v2",
    ]
    for mod in forbidden:
        assert mod not in run_job_source, f"run_job.py should not import {mod}"


# ---------------------------------------------------------------------------
# Regression: non-assets stages still use correct scripts
# ---------------------------------------------------------------------------

def test_non_assets_stages_preserve_scripts():
    assert "assets" not in STAGE_SCRIPTS
    v2_meta = {"script": {"scenes": [_v2_scene()]}}
    for stage, script in STAGE_SCRIPTS.items():
        if stage == "assets":
            continue
        cmd = build_stage_command(stage, "/path/meta.json", metadata=v2_meta)
        assert cmd[1].endswith(script), f"Expected {script} for stage {stage}"
