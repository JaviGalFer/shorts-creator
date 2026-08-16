"""Architecture checks for the migrated script domain."""

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "bin"))

import generate_script as cli
from shorts_creator.script import generator


def test_script_domain_is_importable():
    assert callable(generator.generate_script)
    assert generator.MAX_SCRIPT_ATTEMPTS == 3


def test_cli_delegates_explicit_arguments(monkeypatch):
    received = {}

    def fake_generate_script(**kwargs):
        received.update(kwargs)
        return 7

    monkeypatch.setattr(generator, "generate_script", fake_generate_script)
    monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test", "--duration", "30"])

    assert cli.main() == 7
    assert received["topic"] == "Test"
    assert received["duration"] == 30


def test_bin_adapter_contains_no_generation_implementation():
    source = (PROJECT / "bin" / "generate_script.py").read_text()
    forbidden = [
        "SYSTEM_PROMPT_V2",
        "def call_llm",
        "def _validate_and_canonicalize_script_v2",
        "MAX_SCRIPT_ATTEMPTS",
        "save_metadata(",
    ]
    assert not [token for token in forbidden if token in source]
