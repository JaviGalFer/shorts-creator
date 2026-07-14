"""Tests for _check_durations() in bin/validate_job.py.

Validates the four-level duration contract:
  1. Scene targetDurationSec
  2. renderTimeline entries
  3. Scene aggregate windows
  4. Total duration
"""

import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))
from validate_job import JobValidator, MAX_TOTAL_DURATION, MAX_SEGMENT_DURATION


def _make_meta_path(tmp_path: Path, metadata: dict) -> Path:
    """Create a metadata.json at a depth such that parents[3] == tmp_path."""
    meta_dir = tmp_path / "a" / "b" / "c"
    meta_dir.mkdir(parents=True)
    meta_path = meta_dir / "metadata.json"
    meta_path.write_text(json.dumps(metadata))
    return meta_path


def _run_duration_check(tmp_path: Path, metadata: dict):
    """Run _check_durations only and return (passed, errors, warnings)."""
    meta_path = _make_meta_path(tmp_path, metadata)
    validator = JobValidator(meta_path, verbose=False)
    ok, msgs = validator._check("durations")
    errors = [msg for sev, msg in msgs if sev == "ERROR"]
    warnings = [msg for sev, msg in msgs if sev == "WARNING"]
    return ok, errors, warnings


def _make_base(**overrides):
    return {
        "jobId": "test-job",
        "script": {
            "scenes": [],
        },
        "audio": {
            "continuous": False,
        },
        **overrides,
    }


# ── Case A: 12s scene with two valid segments ────────────────────────────


def test_scene_12s_two_segments_passes(tmp_path):
    md = _make_base(
        script={
            "scenes": [
                {"sceneNumber": 1, "targetDurationSec": 12},
            ],
        },
        renderTimeline=[
            {"sceneNumber": 1, "startSec": 0, "endSec": 6, "durationSec": 6},
            {"sceneNumber": 1, "startSec": 6, "endSec": 12, "durationSec": 6},
        ],
    )
    ok, errors, warnings = _run_duration_check(tmp_path, md)
    assert ok
    assert len(errors) == 0


# ── Case B: E2E-compatible 3-scene job ────────────────────────────────────


def test_e2e_compatible_3_scene_passes(tmp_path):
    md = _make_base(
        script={
            "scenes": [
                {"sceneNumber": 1, "targetDurationSec": 8},
                {"sceneNumber": 2, "targetDurationSec": 10},
                {"sceneNumber": 3, "targetDurationSec": 12},
            ],
        },
        renderTimeline=[
            {"sceneNumber": 1, "startSec": 0, "endSec": 8, "durationSec": 8},
            {"sceneNumber": 2, "startSec": 8, "endSec": 13, "durationSec": 5},
            {"sceneNumber": 2, "startSec": 13, "endSec": 18, "durationSec": 5},
            {"sceneNumber": 3, "startSec": 18, "endSec": 24, "durationSec": 6},
            {"sceneNumber": 3, "startSec": 24, "endSec": 30, "durationSec": 6},
        ],
    )
    ok, errors, warnings = _run_duration_check(tmp_path, md)
    assert ok
    assert len(errors) == 0


# ── Case C: segment exceeding MAX_SEGMENT_DURATION ────────────────────────


def test_segment_exceeds_max_segment_duration_fails(tmp_path):
    md = _make_base(
        script={
            "scenes": [
                {"sceneNumber": 1, "targetDurationSec": 25},
            ],
        },
        renderTimeline=[
            {"sceneNumber": 1, "startSec": 0, "endSec": 21, "durationSec": 21},
        ],
    )
    ok, errors, warnings = _run_duration_check(tmp_path, md)
    assert not ok
    assert any("max segment" in e for e in errors)


# ── Case D: long scene with valid segments passes ─────────────────────────


def test_long_scene_valid_segments_passes(tmp_path):
    md = _make_base(
        script={
            "scenes": [
                {"sceneNumber": 1, "targetDurationSec": 30},
            ],
        },
        renderTimeline=[
            {"sceneNumber": 1, "startSec": 0, "endSec": 10, "durationSec": 10},
            {"sceneNumber": 1, "startSec": 10, "endSec": 20, "durationSec": 10},
            {"sceneNumber": 1, "startSec": 20, "endSec": 30, "durationSec": 10},
        ],
    )
    ok, errors, warnings = _run_duration_check(tmp_path, md)
    assert ok
    assert len(errors) == 0


# ── Case E: durationSec != end-start ──────────────────────────────────────


def test_duration_mismatch_fails(tmp_path):
    md = _make_base(
        script={
            "scenes": [
                {"sceneNumber": 1, "targetDurationSec": 6},
            ],
        },
        renderTimeline=[
            {"sceneNumber": 1, "startSec": 0, "endSec": 6, "durationSec": 5},
        ],
    )
    ok, errors, warnings = _run_duration_check(tmp_path, md)
    assert not ok
    assert any("!=" in e for e in errors)


# ── Case F: gap between segments ──────────────────────────────────────────


def test_gap_between_segments_fails(tmp_path):
    md = _make_base(
        script={
            "scenes": [
                {"sceneNumber": 1, "targetDurationSec": 11},
            ],
        },
        renderTimeline=[
            {"sceneNumber": 1, "startSec": 0, "endSec": 5, "durationSec": 5},
            {"sceneNumber": 1, "startSec": 6, "endSec": 10, "durationSec": 4},
        ],
    )
    ok, errors, warnings = _run_duration_check(tmp_path, md)
    assert not ok
    assert any("gap" in e for e in errors)


# ── Case G: overlap between segments ──────────────────────────────────────


def test_overlap_between_segments_fails(tmp_path):
    md = _make_base(
        script={
            "scenes": [
                {"sceneNumber": 1, "targetDurationSec": 10},
            ],
        },
        renderTimeline=[
            {"sceneNumber": 1, "startSec": 0, "endSec": 6, "durationSec": 6},
            {"sceneNumber": 1, "startSec": 5, "endSec": 10, "durationSec": 5},
        ],
    )
    ok, errors, warnings = _run_duration_check(tmp_path, md)
    assert not ok
    assert any("overlap" in e for e in errors)


# ── Case H: invalid targetDurationSec values ──────────────────────────────


def test_target_negative_fails(tmp_path):
    md = _make_base(
        script={
            "scenes": [
                {"sceneNumber": 1, "targetDurationSec": -1},
            ],
        },
    )
    ok, errors, _ = _run_duration_check(tmp_path, md)
    assert not ok


def test_target_zero_fails(tmp_path):
    md = _make_base(
        script={
            "scenes": [
                {"sceneNumber": 1, "targetDurationSec": 0},
            ],
        },
    )
    ok, errors, _ = _run_duration_check(tmp_path, md)
    assert not ok


def test_target_bool_fails(tmp_path):
    md = _make_base(
        script={
            "scenes": [
                {"sceneNumber": 1, "targetDurationSec": True},
            ],
        },
    )
    ok, errors, _ = _run_duration_check(tmp_path, md)
    assert not ok


def test_target_nan_fails(tmp_path):
    md = _make_base(
        script={
            "scenes": [
                {"sceneNumber": 1, "targetDurationSec": float("nan")},
            ],
        },
    )
    ok, errors, _ = _run_duration_check(tmp_path, md)
    assert not ok


def test_target_inf_fails(tmp_path):
    md = _make_base(
        script={
            "scenes": [
                {"sceneNumber": 1, "targetDurationSec": float("inf")},
            ],
        },
    )
    ok, errors, _ = _run_duration_check(tmp_path, md)
    assert not ok


def test_target_string_fails(tmp_path):
    md = _make_base(
        script={
            "scenes": [
                {"sceneNumber": 1, "targetDurationSec": "eight"},
            ],
        },
    )
    ok, errors, _ = _run_duration_check(tmp_path, md)
    assert not ok


# ── Case I: legacy metadata without renderTimeline ────────────────────────


def test_legacy_metadata_without_timeline_passes(tmp_path):
    md = _make_base(
        script={
            "scenes": [
                {"sceneNumber": 1, "targetDurationSec": 5},
                {"sceneNumber": 2, "targetDurationSec": 5},
                {"sceneNumber": 3, "targetDurationSec": 5},
            ],
        },
    )
    ok, errors, _ = _run_duration_check(tmp_path, md)
    assert ok
    assert len(errors) == 0


def test_legacy_metadata_exceeds_total_fails(tmp_path):
    md = _make_base(
        script={
            "scenes": [
                {"sceneNumber": 1, "targetDurationSec": MAX_TOTAL_DURATION + 1},
            ],
        },
    )
    ok, errors, _ = _run_duration_check(tmp_path, md)
    assert not ok


# ── Case J: continuous audio compatibility ────────────────────────────────


def test_continuous_audio_passes(tmp_path):
    md = _make_base(
        script={
            "scenes": [
                {"sceneNumber": 1, "targetDurationSec": 30},
            ],
        },
        audio={
            "continuous": True,
            "durationSec": 30,
        },
    )
    ok, errors, _ = _run_duration_check(tmp_path, md)
    assert ok
    assert len(errors) == 0


def test_continuous_audio_zero_duration_fails(tmp_path):
    md = _make_base(
        script={
            "scenes": [
                {"sceneNumber": 1, "targetDurationSec": 10},
            ],
        },
        audio={
            "continuous": True,
            "durationSec": 0,
        },
    )
    ok, errors, _ = _run_duration_check(tmp_path, md)
    assert not ok


# ── Additional: MAX_SEGMENT_DURATION parity with render_job.py ─────────────


def test_max_segment_duration_matches_render_job():
    """Verify that validate_job MAX_SEGMENT_DURATION matches render_job."""
    render_job_mod = None
    for p in sys.path:
        candidate = Path(p) / "render_job.py"
        if candidate.exists():
            spec = __import__("importlib.util", fromlist=["spec_from_file_location"])
            import importlib.util
            spec = importlib.util.spec_from_file_location("render_job", str(candidate))
            render_job_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(render_job_mod)
            break
    if render_job_mod is not None:
        assert MAX_SEGMENT_DURATION == render_job_mod.MAX_SEGMENT_DURATION, (
            f"validate_job MAX_SEGMENT_DURATION ({MAX_SEGMENT_DURATION}) "
            f"!= render_job MAX_SEGMENT_DURATION ({render_job_mod.MAX_SEGMENT_DURATION})"
        )


# ── Additional: targetDurationSec above old 8.0 limit now passes ──────────


def test_scene_target_above_old_max_passes(tmp_path):
    md = _make_base(
        script={
            "scenes": [
                {"sceneNumber": 1, "targetDurationSec": 12},
            ],
        },
        renderTimeline=[
            {"sceneNumber": 1, "startSec": 0, "endSec": 5, "durationSec": 5},
            {"sceneNumber": 1, "startSec": 5, "endSec": 10, "durationSec": 5},
            {"sceneNumber": 1, "startSec": 10, "endSec": 12, "durationSec": 2},
        ],
    )
    ok, errors, _ = _run_duration_check(tmp_path, md)
    assert ok
    assert len(errors) == 0
