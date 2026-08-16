"""Pure and stage-contract coverage for final MP4 requested duration."""

import math
import subprocess

import pytest

from shorts_creator.contracts.duration import evaluate_requested_duration_compliance
from shorts_creator.pipeline.orchestrator import _verify_stage_contract


@pytest.mark.parametrize("actual", [27, 28.5, 30])
def test_requested_duration_inclusive_range_passes(actual):
    assert evaluate_requested_duration_compliance(
        actual_video_duration_sec=actual, target_sec=30, min_sec=27, max_sec=30,
    )["status"] == "PASS"


@pytest.mark.parametrize("actual,delta", [(20.88, 6.12), (31, 1)])
def test_requested_duration_outside_range_fails(actual, delta):
    result = evaluate_requested_duration_compliance(
        actual_video_duration_sec=actual, target_sec=30, min_sec=27, max_sec=30,
    )
    assert result["status"] == "FAIL"
    assert result["deltaToRangeSec"] == pytest.approx(delta)


@pytest.mark.parametrize("actual", [True, 0, -1, math.nan, math.inf])
def test_requested_duration_invalid_actual_rejected(actual):
    with pytest.raises(ValueError):
        evaluate_requested_duration_compliance(
            actual_video_duration_sec=actual, target_sec=30, min_sec=27, max_sec=30,
        )


def test_validate_stage_maps_product_duration_failure_to_review(tmp_path):
    (tmp_path / "video.mp4").touch()
    data = {"status": "RENDERED_WITH_WARNINGS", "validation": {"gates": {
        "technicalValidation": "PASS",
        "renderDurationIntegrity": "PASS",
        "requestedDurationCompliance": "FAIL",
        "qualityGate": "FAIL",
    }}}
    ok, status, error = _verify_stage_contract(
        "validate", data, str(tmp_path / "metadata.json"),
        subprocess.CompletedProcess([], 0, "", ""),
    )
    assert not ok and status == "REVIEW_REQUIRED" and error is None
    assert data["status"] == "REVIEW_REQUIRED"
    assert data["reviewReasons"] == ["REQUESTED_DURATION_OUT_OF_RANGE"]


def test_validate_stage_keeps_technical_failure_semantics(tmp_path):
    (tmp_path / "video.mp4").touch()
    ok, status, error = _verify_stage_contract(
        "validate", {"validation": {"gates": {}}}, str(tmp_path / "metadata.json"),
        subprocess.CompletedProcess([], 1, "", "technical failure"),
    )
    assert not ok and status == "VALIDATION_FAILED" and error is None
