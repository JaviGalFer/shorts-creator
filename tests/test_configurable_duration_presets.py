import pytest

from shorts_creator.contracts.duration import (
    evaluate_duration_fitting,
    evaluate_requested_duration_compliance,
    resolve_requested_duration,
)


@pytest.mark.parametrize("preset,target,minimum,maximum", [
    ("quick_30", 30, 27, 33), ("standard_45", 45, 41, 49), ("deep_60", 60, 55, 65),
])
def test_presets_resolve_symmetric_ranges(preset, target, minimum, maximum):
    value = resolve_requested_duration(requested_preset=preset)
    assert (value["targetSec"], value["minSec"], value["maxSec"]) == (target, minimum, maximum)
    assert value["source"] == "preset" and value["presetId"] == preset


def test_custom_duration_and_tolerance_are_symmetric():
    automatic = resolve_requested_duration(requested_sec=37)
    explicit = resolve_requested_duration(requested_sec=37, requested_tolerance=2)
    assert (automatic["minSec"], automatic["maxSec"], automatic["toleranceSec"]) == (33, 41, 4)
    assert (explicit["minSec"], explicit["maxSec"], explicit["toleranceSec"]) == (35, 39, 2)


def test_custom_30_no_longer_clamps_to_legacy_profile():
    value = resolve_requested_duration(requested_sec=30)
    assert (value["targetSec"], value["minSec"], value["maxSec"], value["toleranceSec"]) == (30, 27, 33, 3)
    assert value["source"] == "custom"


def test_preset_tolerance_override_and_ambiguity_errors():
    value = resolve_requested_duration(requested_preset="quick_30", requested_tolerance=2)
    assert (value["targetSec"], value["minSec"], value["maxSec"]) == (30, 28, 32)
    with pytest.raises(ValueError, match="cannot be used together"):
        resolve_requested_duration(requested_sec=30, requested_preset="quick_30")
    for bad in (0, -1, True, "2"):
        with pytest.raises(ValueError):
            resolve_requested_duration(requested_sec=30, requested_tolerance=bad)


def test_e2e_30_587_is_in_range_for_fitting_and_final_mp4():
    fitting = evaluate_duration_fitting(
        current_word_count=70, projected_duration_sec=30.587,
        target_sec=30, min_sec=27, max_sec=33,
    )
    final = evaluate_requested_duration_compliance(
        actual_video_duration_sec=30.587, target_sec=30, min_sec=27, max_sec=33,
    )
    assert fitting["decision"] == "PASS"
    assert final["status"] == "PASS"
