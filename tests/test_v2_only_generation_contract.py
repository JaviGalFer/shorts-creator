"""Tests for V2-only generation contract (Slice 1).

Run: python3 -m pytest tests/test_v2_only_generation_contract.py -v
"""

import sys
from pathlib import Path

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))

import pytest

from generate_script import main as gs_main
from run_job import build_script_command


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_script_args(topic="Test", duration=None, duration_profile=None,
                       duration_target=None, duration_min=None, duration_max=None,
                       strictness=None, model=None):
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
    return a


# ── Contract 1: generate_script.py defaults to V2 ─────────────────────────────

class TestGenerateScriptDefaultV2:
    """Default resolution is V2 (CLI flag removed)."""

    def test_default_dry_run_uses_v2(self, monkeypatch, capsys):
        """Dry-run without --visual-schema-version outputs schemaVersion=2."""
        monkeypatch.setattr("shorts_creator.script.generator.load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(sys, "argv", [
            "generate_script.py", "--topic", "test",
            "--dry-run", "--model", "gpt-4o-mini",
        ])
        exit_code = gs_main()
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "schemaVersion=2" in out

    def test_removed_visual_schema_flag_is_rejected(self, monkeypatch, capsys):
        """--visual-schema-version flag is rejected because it was removed."""
        monkeypatch.setattr("shorts_creator.script.generator.load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(sys, "argv", [
            "generate_script.py", "--topic", "test",
            "--visual-schema-version", "1",
            "--dry-run", "--model", "gpt-4o-mini",
        ])
        with pytest.raises(SystemExit) as exc_info:
            gs_main()
        assert exc_info.value.code == 2


# ── Contract 2: build_script_command() exposes no visual schema selector ──────

class TestBuildScriptCommandV2:
    """build_script_command no longer adds --visual-schema-version."""

    def test_build_script_command_does_not_add_visual_schema_flag(self):
        """build_script_command does not add --visual-schema-version."""
        args = _make_script_args()
        cmd = build_script_command(args)
        assert "--visual-schema-version" not in cmd

    def test_build_script_command_has_no_visual_schema_selector(self):
        """Command has no V1/V2 selector argument."""
        args = _make_script_args()
        cmd = build_script_command(args)
        assert "--visual-schema-version" not in cmd

    def test_preserves_existing_args_minimal(self):
        """Other existing args are preserved (no V2 flag)."""
        args = _make_script_args(topic="TestTopic")
        cmd = build_script_command(args)
        assert cmd[1].endswith("generate_script.py")
        assert cmd[cmd.index("--topic") + 1] == "TestTopic"
        assert "--visual-schema-version" not in cmd

    def test_preserves_existing_args_all(self):
        """All optional args are preserved (no V2 flag)."""
        args = _make_script_args(
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
        assert "--visual-schema-version" not in cmd

    def test_visual_schema_flag_absent_in_dry_run_command(self):
        """Dry-run command also has no V2 flag."""
        args = _make_script_args(topic="DryRunTest")
        cmd = build_script_command(args)
        assert "--visual-schema-version" not in cmd
