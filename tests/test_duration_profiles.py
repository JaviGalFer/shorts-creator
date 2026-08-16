"""Canonical target-centered duration resolution tests."""

import pytest

from shorts_creator.contracts.duration import (
    DEFAULT_DURATION_PRESET,
    DURATION_PRESETS,
    calculate_word_budget,
    resolve_requested_duration,
)


def test_default_uses_quick_preset():
    value = resolve_requested_duration()
    assert value["presetId"] == DEFAULT_DURATION_PRESET
    assert (value["targetSec"], value["minSec"], value["maxSec"]) == (30, 27, 33)


@pytest.mark.parametrize("preset,target,tolerance", [
    ("quick_30", 30, 3), ("standard_45", 45, 4), ("deep_60", 60, 5),
])
def test_presets_derive_ranges_from_target_and_tolerance(preset, target, tolerance):
    value = resolve_requested_duration(requested_preset=preset)
    assert DURATION_PRESETS[preset] == {"targetSec": target, "toleranceSec": tolerance}
    assert value["minSec"] == target - tolerance
    assert value["maxSec"] == target + tolerance


def test_legacy_profile_is_an_alias_to_canonical_preset():
    value = resolve_requested_duration(requested_profile="short_25_30")
    assert value["presetId"] == "quick_30"
    assert (value["minSec"], value["maxSec"]) == (27, 33)


def test_custom_uses_half_up_symmetric_tolerance():
    value = resolve_requested_duration(requested_sec=37)
    assert value["source"] == "custom"
    assert (value["toleranceSec"], value["minSec"], value["maxSec"]) == (4, 33, 41)


def test_explicit_range_overrides_have_highest_priority():
    value = resolve_requested_duration(
        requested_preset="quick_30", explicit_target=40, explicit_min=35, explicit_max=45,
    )
    assert (value["targetSec"], value["minSec"], value["maxSec"]) == (40, 35, 45)


@pytest.mark.parametrize("kwargs", [
    {"requested_sec": 19}, {"requested_sec": 61},
    {"requested_sec": 30, "requested_tolerance": 0},
    {"requested_sec": 30, "requested_tolerance": True},
    {"requested_sec": 30, "requested_preset": "quick_30"},
])
def test_invalid_duration_requests_fail(kwargs):
    with pytest.raises(ValueError):
        resolve_requested_duration(**kwargs)


def test_word_budget_consumes_resolved_numbers_only():
    value = resolve_requested_duration(requested_preset="standard_45")
    budget = calculate_word_budget(
        target_sec=value["targetSec"], min_sec=value["minSec"], max_sec=value["maxSec"],
    )
    assert budget["targetSec"] == 45
    assert budget["minSec"] == 41
    assert budget["maxSec"] == 49
