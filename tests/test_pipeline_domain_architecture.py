"""Architecture checks for pipeline and narration trimming ownership."""

import ast
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "bin"))

import run_job as pipeline_cli
import trim_narration_silences as trimming_cli
from shorts_creator.audio import trimming
from shorts_creator.pipeline import orchestrator


def test_pipeline_package_is_importable():
    assert callable(orchestrator.run_pipeline)
    assert orchestrator.STAGES == ["script", "assets", "audio", "prepare", "render", "validate"]


def test_run_job_cli_delegates(monkeypatch):
    received = {}
    monkeypatch.setattr(orchestrator, "run_pipeline", lambda **kwargs: received.update(kwargs) or 7)
    monkeypatch.setattr(sys, "argv", ["run_job.py", "--topic", "Test", "--stop-after", "audio"])
    assert pipeline_cli.main() == 7
    assert received["topic"] == "Test"
    assert received["stop_after"] == "audio"


def test_trimming_cli_delegates(monkeypatch):
    received = {}
    monkeypatch.setattr(trimming, "trim_narration", lambda **kwargs: received.update(kwargs) or 7)
    monkeypatch.setattr(sys, "argv", ["trim_narration_silences.py", "metadata.json", "--dry-run"])
    assert trimming_cli.main() == 7
    assert received["metadata_path"] == "metadata.json"
    assert received["dry_run"] is True


def test_entrypoints_contain_no_runtime_implementation():
    run_source = (PROJECT / "bin" / "run_job.py").read_text()
    trim_source = (PROJECT / "bin" / "trim_narration_silences.py").read_text()
    run_forbidden = [
        "def run_subprocess",
        "def append_orchestration",
        "def _verify_stage_contract",
        "STAGE_STATUS_MAP",
        "REVIEW_BLOCKING_STAGES",
    ]
    trim_forbidden = [
        "def build_trim_command",
        "def compute_trimmed_scene_timings",
        "def adjust_cues_cumulative",
        "subprocess.run",
    ]
    assert not [token for token in run_forbidden if token in run_source]
    assert not [token for token in trim_forbidden if token in trim_source]


def test_package_sources_do_not_import_bin_modules():
    bin_modules = {path.stem for path in (PROJECT / "bin").glob("*.py")}
    violations = []
    for path in (PROJECT / "src" / "shorts_creator").rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".", 1)[0]
                if root in bin_modules:
                    violations.append(f"{path.relative_to(PROJECT)} imports {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in bin_modules:
                        violations.append(f"{path.relative_to(PROJECT)} imports {alias.name}")
    assert violations == []
