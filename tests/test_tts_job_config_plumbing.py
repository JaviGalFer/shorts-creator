"""Focused tests for TTS job-config plumbing (run_job -> orchestrator -> script/audio).

Run: python3 -m pytest tests/test_tts_job_config_plumbing.py -v
"""

import sys
from pathlib import Path
from unittest.mock import patch

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))

import pytest

from shorts_creator.audio.generator import (
    resolve_audio_job_config,
    resolve_audio_regeneration_config,
    get_audio_defaults,
)
from shorts_creator.pipeline.orchestrator import (
    build_script_command,
    build_stage_command,
    build_audio_regeneration_command,
    _resolve_audio_config,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_args(**overrides):
    from tests.test_run_job import _make_args
    return _make_args(**overrides)


def _script_cmd(**overrides):
    return build_script_command(_make_args(**overrides))


def _cmd_flags(cmd):
    """Return {flag: value} pairs present in a command list."""
    flags = {}
    i = 0
    while i < len(cmd):
        if cmd[i].startswith("--"):
            flags[cmd[i]] = cmd[i + 1] if i + 1 < len(cmd) else None
        i += 1
    return flags


# ---------------------------------------------------------------------------
# Defaults (test 1) & explicit propagation (tests 2-6)
# ---------------------------------------------------------------------------

def test_defaults_resolve_edge_provider_voice_timing():
    config = resolve_audio_job_config()
    assert config["tts_provider"] == "edge_tts"
    assert config["voice"] == "es-ES-AlvaroNeural"
    assert config["subtitle_timing_provider"] == "auto"


def test_script_command_carries_default_audio_flags():
    flags = _cmd_flags(_script_cmd(tts_provider=None, voice=None))
    assert flags.get("--tts-provider") == "edge_tts"
    assert flags.get("--voice") == "es-ES-AlvaroNeural"
    assert flags.get("--subtitle-timing-provider") == "auto"


def test_explicit_elevenlabs_and_voice_propagate_to_script_command():
    flags = _cmd_flags(_script_cmd(
        tts_provider="elevenlabs", voice="Xb7hH8MSUJpSbSDYk0k2",
    ))
    assert flags.get("--tts-provider") == "elevenlabs"
    assert flags.get("--voice") == "Xb7hH8MSUJpSbSDYk0k2"


def test_explicit_voice_wins_over_env():
    with patch("shorts_creator.audio.generator._read_runtime_env") as mock_env:
        mock_env.side_effect = lambda key, default=None: {
            "TTS_PROVIDER": "edge_tts",
            "TTS_VOICE": "es-ES-RaulNeural",
            "ELEVENLABS_VOICE_ID": "env-voice",
            "SUBTITLE_TIMING_PROVIDER": "auto",
        }.get(key, default)
        config = resolve_audio_job_config(tts_provider="edge_tts", voice="explicit-voice")
    assert config["voice"] == "explicit-voice"


def test_elevenlabs_without_voice_falls_back_to_env_voice():
    with patch("shorts_creator.audio.generator._read_runtime_env") as mock_env:
        mock_env.side_effect = lambda key, default=None: {
            "TTS_PROVIDER": "edge_tts",
            "ELEVENLABS_VOICE_ID": "env-eleven-voice",
            "SUBTITLE_TIMING_PROVIDER": "auto",
        }.get(key, default)
        config = resolve_audio_job_config(tts_provider="elevenlabs", voice=None)
    assert config["voice"] == "env-eleven-voice"


def test_initial_audio_stage_command_carries_resolved_flags():
    args = _make_args(
        tts_provider="elevenlabs", voice="Xb7hH8MSUJpSbSDYk0k2",
    )
    cmd = build_stage_command(
        "audio", "/path/to/metadata.json",
        audio_config=getattr(args, "audio_config", None),
    )
    flags = _cmd_flags(cmd)
    assert flags.get("--tts-provider") == "elevenlabs"
    assert flags.get("--voice") == "Xb7hH8MSUJpSbSDYk0k2"
    assert flags.get("--subtitle-timing-provider") == "auto"


# ---------------------------------------------------------------------------
# Non-audio stages do not carry audio flags (test 7)
# ---------------------------------------------------------------------------

def test_non_audio_stages_have_no_audio_flags():
    args = _make_args(tts_provider="elevenlabs", voice="Xb7hH8MSUJpSbSDYk0k2")
    for stage in ("assets", "prepare", "render", "validate"):
        cmd = build_stage_command(
            stage, "/path/to/metadata.json",
            audio_config=getattr(args, "audio_config", None),
        )
        assert "--tts-provider" not in cmd, stage
        assert "--voice" not in cmd, stage
        assert "--subtitle-timing-provider" not in cmd, stage


# ---------------------------------------------------------------------------
# Regeneration preserves provider/voice (tests 8-9)
# ---------------------------------------------------------------------------

def test_regeneration_command_preserves_resolved_config():
    metadata = {
        "request": {
            "voice": {"provider": "elevenlabs", "voiceId": "Xb7hH8MSUJpSbSDYk0k2"},
            "subtitles": {"timingProvider": "elevenlabs_normalized_alignment"},
        },
    }
    regen = resolve_audio_regeneration_config(metadata)
    assert regen["tts_provider"] == "elevenlabs"
    assert regen["voice"] == "Xb7hH8MSUJpSbSDYk0k2"
    assert regen["subtitle_timing_provider"] == "elevenlabs_normalized_alignment"

    cmd = build_audio_regeneration_command("/path/metadata.json", metadata)
    flags = _cmd_flags(cmd)
    assert flags.get("--tts-provider") == "elevenlabs"
    assert flags.get("--voice") == "Xb7hH8MSUJpSbSDYk0k2"


def test_regeneration_preserves_edge_default_when_request_lacks_voice():
    defaults = get_audio_defaults()
    metadata = {"request": {"voice": {}, "subtitles": {}}}
    regen = resolve_audio_regeneration_config(metadata)
    assert regen["tts_provider"] == defaults["tts_provider"]
    assert regen["voice"] == defaults["voice"]
    assert regen["subtitle_timing_provider"] == defaults["subtitle_timing_provider"]


# ---------------------------------------------------------------------------
# request/audio/resolvedConfig invariant (11) & secrets (12)
# ---------------------------------------------------------------------------

def test_resolved_config_stays_consistent_across_stages():
    config = resolve_audio_job_config(
        tts_provider="elevenlabs", voice="Xb7hH8MSUJpSbSDYk0k2",
    )
    persisted_request = {
        "voice": {"provider": config["tts_provider"], "voiceId": config["voice"]},
        "subtitles": {"timingProvider": config["subtitle_timing_provider"]},
    }
    regen = resolve_audio_regeneration_config({"request": persisted_request})
    assert regen["tts_provider"] == config["tts_provider"]
    assert regen["voice"] == config["voice"]
    assert regen["subtitle_timing_provider"] == config["subtitle_timing_provider"]


def test_no_api_key_in_commands_or_request():
    args = _make_args(tts_provider="elevenlabs", voice="Xb7hH8MSUJpSbSDYk0k2")
    cmd = build_script_command(args)
    joined = " ".join(cmd)
    assert "ELEVENLABS_API_KEY" not in joined
    assert "sk_" not in joined
    cmd = _cmd_flags(cmd)
    assert "ELEVENLABS_API_KEY" not in cmd
    assert "--api-key" not in cmd
    audio = " ".join(build_stage_command(
        "audio", "/p/meta.json",
        audio_config=getattr(args, "audio_config", None),
    ))
    assert "ELEVENLABS_API_KEY" not in audio
    assert "sk_" not in audio


def test_dry_run_shows_provider_and_voice_no_secrets(capsys):
    from shorts_creator.pipeline.orchestrator import dry_run
    args = _make_args(
        topic="Arcoíris", duration=30, stop_after="audio",
        tts_provider="elevenlabs", voice="Xb7hH8MSUJpSbSDYk0k2",
    )
    dry_run(args)
    out = capsys.readouterr().out
    assert "--tts-provider elevenlabs" in out
    assert "--voice Xb7hH8MSUJpSbSDYk0k2" in out
    assert "--subtitle-timing-provider auto" in out
    assert "ELEVENLABS_API_KEY" not in out
    assert "sk_" not in out