"""Architecture checks for the migrated audio domain."""

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "bin"))

import generate_audio as cli
from shorts_creator.audio import generator


def test_audio_domain_is_importable():
    assert callable(generator.generate_audio)


def test_cli_delegates_explicit_arguments(monkeypatch):
    received = {}

    async def fake_generate_audio(**kwargs):
        received.update(kwargs)
        return 7

    monkeypatch.setattr(generator, "generate_audio", fake_generate_audio)
    monkeypatch.setattr(sys, "argv", ["generate_audio.py", "metadata.json", "--continuous"])

    assert cli.main() == 7
    assert received["metadata_path"] == "metadata.json"
    assert received["continuous"] is True


def test_bin_adapter_contains_no_audio_runtime():
    source = (PROJECT / "bin" / "generate_audio.py").read_text()
    forbidden = [
        "def _get_mp3_duration",
        "def main_per_scene",
        "def main_continuous",
        "def generate_audio_with_timestamps",
        "AUDIO_DURATION_MISSING",
        "save_metadata(",
    ]
    assert not [token for token in forbidden if token in source]
