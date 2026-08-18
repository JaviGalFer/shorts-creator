"""Offline tests for the compositional benchmark tool and the fresh holdout.

No torch / transformers / open_clip / network calls / production runtime
imports are allowed here. The holdout fixture must stay untouched by the
calibration set and the tool must stay import-safe without any ML stack.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = str(_ROOT / "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from visual_fidelity_benchmark import (  # noqa: E402
    ACCEPT,
    REJECT,
    human_label_to_verdict,
    load_labels,
    validate_labels,
)

_FIXTURES = _ROOT / "tests/fixtures/asset_visual_fidelity"
CALIBRATION = _FIXTURES / "labels.json"
HOLDOUT = _FIXTURES / "holdout_labels.json"

BLIP_THRESHOLD = 0.015839167404919863  # locked from calibration; NOT tunable


def _read(path: Path) -> Path:
    assert path.is_file(), f"missing file: {path}"
    return path


def test_holdout_fixture_is_valid_and_counts_match():
    entries = _read(HOLDOUT)
    summary = validate_labels(load_labels(entries))
    assert summary["total"] == 20
    assert summary["clearlyRelevant"] == 3
    assert summary["coarseButUsable"] == 10
    assert summary["falsePositiveOrUnusable"] == 7
    assert summary["accept"] == 13
    assert summary["reject"] == 7
    assert summary["duplicateKeys"] == 0
    assert summary["emptyQueryUsed"] == 0


def test_holdout_is_disjoint_from_calibration():
    calib_paths = {e["assetPath"] for e in load_labels(_read(CALIBRATION))}
    holdout_paths = {e["assetPath"] for e in load_labels(_read(HOLDOUT))}
    assert calib_paths.isdisjoint(holdout_paths)
    assert len(holdout_paths) == 20


def test_holdout_labels_map_to_13_accept_7_reject():
    entries = load_labels(_read(HOLDOUT))
    accept = sum(1 for e in entries if human_label_to_verdict(e["humanLabel"]) == ACCEPT)
    reject = sum(1 for e in entries if human_label_to_verdict(e["humanLabel"]) == REJECT)
    assert accept == 13
    assert reject == 7


def test_holdout_assets_exist_on_disk():
    entries = load_labels(_read(HOLDOUT))
    for entry in entries:
        assert (_ROOT / entry["assetPath"]).is_file(), entry["assetPath"]


def test_holdout_rejects_roleplay_cases_binary_shape():
    # The 5 critical false-positive cases documented in the change must all be
    # labeled REJECT in the fixture (the pixel models must prove useful on them).
    entries = load_labels(_read(HOLDOUT))
    critical_scenes = {
        "cmo-2026-08-18-210827": {(1, 2)},  # motor 2T vs query 4T
        "cmo-2026-08-18-211151": {(1, 1), (3, 1), (4, 2)},  # castle cases
        "qu-2026-08-18-211511": {(1, 2)},  # blockchain art vs data center
    }
    for entry in entries:
        key = (entry["sceneNumber"], entry["segmentIndex"])
        if entry["jobId"] in critical_scenes and key in critical_scenes[entry["jobId"]]:
            assert human_label_to_verdict(entry["humanLabel"]) == REJECT, (
                f"{entry['jobId']} scene {key} is a critical rejection case"
            )


def test_tool_module_has_no_top_level_ml_imports():
    source = _read(_ROOT / "tools/visual_fidelity_compositional_benchmark.py").read_text(
        encoding="utf-8"
    )
    for forbidden in ("import torch", "import open_clip", "from transformers"):
        assert forbidden not in source.split("\n\n")[0], f"top-level {forbidden}"


def test_tool_source_has_no_production_runtime_imports():
    source = _read(_ROOT / "tools/visual_fidelity_compositional_benchmark.py").read_text(
        encoding="utf-8"
    )
    assert "shorts_creator" not in source
    assert "from src" not in source
    assert "import src" not in source
    assert "from bin" not in source
    assert "import bin" not in source
    assert "visual_fidelity.py" not in source


def test_cli_help_is_offline_and_import_safe():
    result = subprocess.run(
        [sys.executable, str(_ROOT / "tools/visual_fidelity_compositional_benchmark.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    assert "--model" in result.stdout
    assert "--device" in result.stdout
    assert "blip_itm_base" in result.stdout
    assert "openclip_vit_b32" in result.stdout
    assert "evaluation-only" in result.stdout.lower()


def test_holdout_blip_threshold_locked_is_not_in_fixture():
    # The calibration threshold must never be encoded inside the fixtures.
    for fixture in (CALIBRATION, HOLDOUT):
        raw = json.loads(fixture.read_text(encoding="utf-8"))
        dumped = json.dumps(raw)
        assert str(BLIP_THRESHOLD) not in dumped