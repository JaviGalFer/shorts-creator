"""Architecture checks for rendering and validation ownership."""

import ast
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "bin"))

import prepare_job as prepare_cli
import render_job as render_cli
import validate_job as validate_cli
from shorts_creator.rendering import preparer, renderer
from shorts_creator.validation import job


def test_rendering_and_validation_packages_are_importable():
    assert callable(preparer.prepare_job)
    assert callable(renderer.render_job)
    assert callable(job.validate_job)


def test_prepare_cli_delegates(monkeypatch):
    received = {}
    monkeypatch.setattr(preparer, "prepare_job", lambda **kwargs: received.update(kwargs) or 7)
    monkeypatch.setattr(sys, "argv", ["prepare_job.py", "metadata.json"])
    assert prepare_cli.main() == 7
    assert received["metadata_path"] == "metadata.json"


def test_render_cli_delegates(monkeypatch):
    received = {}
    monkeypatch.setattr(renderer, "render_job", lambda **kwargs: received.update(kwargs) or 7)
    monkeypatch.setattr(sys, "argv", ["render_job.py", "metadata.json", "--skip-render"])
    assert render_cli.main() == 7
    assert received["skip_render"] is True


def test_validate_cli_delegates(monkeypatch):
    received = {}
    monkeypatch.setattr(job, "validate_job", lambda **kwargs: received.update(kwargs) or 7)
    monkeypatch.setattr(sys, "argv", ["validate_job.py", "metadata.json", "--json"])
    assert validate_cli.main() == 7
    assert received["json_output"] is True


def test_internal_modules_are_absent_from_bin():
    removed = [
        "asset_validation.py",
        "audio_validation.py",
        "coverage_validation.py",
        "pacing_validation.py",
        "subtitle_normalize.py",
        "subtitle_validation_context.py",
        "visual_normalize.py",
        "whisper_subtitles.py",
    ]
    assert not [name for name in removed if (PROJECT / "bin" / name).exists()]


def test_entrypoints_contain_no_runtime_implementation():
    forbidden = {
        "prepare_job.py": ["def build_timeline", "def generate_ass_from_cues"],
        "render_job.py": ["def preflight_validate", "def build_motion_filter", "ffmpeg_args"],
        "validate_job.py": ["class JobValidator", "def update_manifest_gates"],
    }
    for filename, tokens in forbidden.items():
        source = (PROJECT / "bin" / filename).read_text()
        assert not [token for token in tokens if token in source]


def test_package_sources_do_not_import_bin_runtime_modules():
    legacy_modules = [
        "prepare_job",
        "render_job",
        "validate_job",
        "asset_validation",
        "audio_validation",
        "coverage_validation",
        "pacing_validation",
        "subtitle_normalize",
        "subtitle_validation_context",
        "visual_normalize",
        "whisper_subtitles",
    ]
    violations = []
    for path in (PROJECT / "src" / "shorts_creator").rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in legacy_modules:
                violations.append(f"{path.relative_to(PROJECT)} imports {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in legacy_modules:
                        violations.append(f"{path.relative_to(PROJECT)} imports {alias.name}")
    assert violations == []
