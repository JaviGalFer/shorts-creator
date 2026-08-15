"""Tests for duration profile system.

Run: python3 -m pytest tests/test_duration_profiles.py -v
"""

import argparse
import sys
from pathlib import Path

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))

import pytest

from duration_profiles import (
    DURATION_PROFILES,
    DEFAULT_PROFILE,
    resolve_duration_config,
    resolve_requested_duration,
    calculate_word_budget,
)
from shorts_creator.contracts import duration as canonical_duration


def test_canonical_duration_contract_matches_legacy_facade():
    assert canonical_duration.DURATION_PROFILES is DURATION_PROFILES
    assert canonical_duration.DEFAULT_PROFILE is DEFAULT_PROFILE
    assert canonical_duration.resolve_duration_config is resolve_duration_config
    assert canonical_duration.resolve_requested_duration is resolve_requested_duration
    assert canonical_duration.calculate_word_budget is calculate_word_budget


def test_legacy_duration_facade_retains_cli_adapter():
    parser = argparse.ArgumentParser()
    from duration_profiles import add_duration_profile_args

    add_duration_profile_args(parser)
    assert parser.parse_args(["--duration", "42"]).duration == 42


def test_default_resolves_to_short_25_30():
    name, config = resolve_duration_config()
    assert name == "short_25_30"
    assert config["targetSec"] == 28
    assert config["minSec"] == 25
    assert config["maxSec"] == 30
    assert config["strictness"] == "balanced"


def test_standard_profile():
    name, config = resolve_duration_config(profile_name="standard_32_38")
    assert name == "standard_32_38"
    assert config["targetSec"] == 35
    assert config["minSec"] == 32
    assert config["maxSec"] == 38


def test_extended_profile():
    name, config = resolve_duration_config(profile_name="extended_50_60")
    assert name == "extended_50_60"
    assert config["targetSec"] == 55
    assert config["minSec"] == 50
    assert config["maxSec"] == 60


def test_explicit_target_overrides_profile():
    name, config = resolve_duration_config(
        profile_name="short_25_30", target=30
    )
    assert config["targetSec"] == 30
    assert config["minSec"] == 25  # unchanged
    assert config["maxSec"] == 30  # unchanged


def test_all_explicit_overrides():
    name, config = resolve_duration_config(
        profile_name="short_25_30",
        target=40,
        min_sec=35,
        max_sec=45,
        strictness="relaxed",
    )
    assert config["targetSec"] == 40
    assert config["minSec"] == 35
    assert config["maxSec"] == 45
    assert config["strictness"] == "relaxed"
    # profile name is still the one passed
    assert name == "short_25_30"


def test_unknown_profile_falls_back_to_default():
    name, config = resolve_duration_config(profile_name="nonexistent")
    assert name == DEFAULT_PROFILE
    assert config["targetSec"] == DURATION_PROFILES[DEFAULT_PROFILE]["targetSec"]


def test_partial_override_keeps_profile_values():
    name, config = resolve_duration_config(
        profile_name="standard_32_38", min_sec=30
    )
    assert config["targetSec"] == 35  # from profile
    assert config["minSec"] == 30  # overridden
    assert config["maxSec"] == 38  # from profile


# ── Word budget tests ───────────────────────────────────────────────────


def assert_budget_fields(budget):
    assert "minimumWords" in budget
    assert "preferredWords" in budget
    assert "maximumWords" in budget
    assert "sceneCount" in budget
    assert "pauseSec" in budget
    assert budget["minimumWords"] >= 0
    assert budget["preferredWords"] >= budget["minimumWords"]
    assert budget["maximumWords"] >= budget["preferredWords"]


def test_word_budget_short_profile():
    """28s target, 5 scenes, WPM 110, 350ms pauses."""
    b = calculate_word_budget(target_sec=28, min_sec=25, max_sec=30, scene_count=5)
    assert_budget_fields(b)
    assert b["sceneCount"] == 5
    assert b["pauseSec"] == 1.4
    # Spoken time available: 25-1.4=23.6 → ceil(23.6/60*110)=44
    assert b["minimumWords"] == 44
    # 28-1.4=26.6 → round(26.6/60*110)=49
    assert b["preferredWords"] == 49
    # 30-1.4=28.6 → floor(28.6/60*110)=52
    assert b["maximumWords"] == 52


def test_word_budget_standard_profile():
    """35s target, 5 scenes."""
    b = calculate_word_budget(target_sec=35, min_sec=32, max_sec=38, scene_count=5)
    assert_budget_fields(b)
    assert b["sceneCount"] == 5
    assert b["pauseSec"] == 1.4
    # 32-1.4=30.6 → ceil(30.6/60*110)=57
    assert b["minimumWords"] == 57
    # 35-1.4=33.6 → round(33.6/60*110)=62
    assert b["preferredWords"] == 62
    # 38-1.4=36.6 → floor(36.6/60*110)=67
    assert b["maximumWords"] == 67


def test_word_budget_extended_profile():
    """55s target, 6 scenes."""
    b = calculate_word_budget(target_sec=55, min_sec=50, max_sec=60, scene_count=6)
    assert_budget_fields(b)
    assert b["sceneCount"] == 6
    # 5 transitions × 350ms = 1.75s
    assert b["pauseSec"] == 1.75
    # 50-1.75=48.25 → ceil(48.25/60*110)=89
    assert b["minimumWords"] == 89
    # 55-1.75=53.25 → round(53.25/60*110)=98
    assert b["preferredWords"] == 98
    # 60-1.75=58.25 → floor(58.25/60*110)=106
    assert b["maximumWords"] == 106


def test_word_budget_explicit_values():
    """Custom values unrelated to any named profile."""
    b = calculate_word_budget(
        target_sec=42, min_sec=38, max_sec=48, scene_count=4, spoken_words_per_minute=130,
    )
    assert_budget_fields(b)
    assert b["sceneCount"] == 4
    # 3 transitions × 350ms = 1.05s
    assert b["pauseSec"] == 1.05
    # 38-1.05=36.95 → ceil(36.95/60*130)=81
    assert b["minimumWords"] == 81
    # 42-1.05=40.95 → round(40.95/60*130)=89
    assert b["preferredWords"] == 89
    # 48-1.05=46.95 → floor(46.95/60*130)=101
    assert b["maximumWords"] == 101


def test_word_budget_40_seconds_6_scenes():
    """40s target, 6 scenes — dynamic calculation."""
    b = calculate_word_budget(target_sec=40, min_sec=35, max_sec=45, scene_count=6)
    assert_budget_fields(b)
    assert b["sceneCount"] == 6
    assert b["pauseSec"] == 1.75
    # 35-1.75=33.25 → ceil(33.25/60*110)=61
    assert b["minimumWords"] == 61
    # 40-1.75=38.25 → round(38.25/60*110)=70
    assert b["preferredWords"] == 70
    # 45-1.75=43.25 → floor(43.25/60*110)=79
    assert b["maximumWords"] == 79


def test_word_budget_provisional_not_hardcoded():
    """Engine must work for any scene count, not just 5."""
    for n_scenes in [1, 2, 3, 4, 5, 6, 7, 8]:
        b = calculate_word_budget(target_sec=28, min_sec=25, max_sec=30, scene_count=n_scenes)
        assert_budget_fields(b)
        assert b["sceneCount"] == n_scenes


def test_word_budget_works_with_explicit_overrides():
    """Explicit --duration-target/min/max must override profile-derived values."""
    b = calculate_word_budget(
        target_sec=45, min_sec=40, max_sec=50, scene_count=5,
    )
    assert_budget_fields(b)
    # ceil((40-1.4)/60*110) = ceil(38.6/60*110) = ceil(70.77) = 71
    assert b["minimumWords"] == 71
    # floor((50-1.4)/60*110) = floor(48.6/60*110) = floor(89.1) = 89
    assert b["maximumWords"] == 89


def test_word_budget_zero_pause_single_scene():
    """Single scene → zero pause, budget = raw duration."""
    b = calculate_word_budget(target_sec=28, min_sec=25, max_sec=30, scene_count=1)
    assert b["pauseSec"] == 0.0
    assert b["minimumWords"] == 46  # ceil(25/60*110)
    assert b["preferredWords"] == 51  # round(28/60*110)
    assert b["maximumWords"] == 55  # floor(30/60*110)


def test_word_budget_classify_below_minimum():
    """54-word script for standard_32_38 with 5 scenes → below minimum."""
    b = calculate_word_budget(target_sec=35, min_sec=32, max_sec=38, scene_count=5)
    assert b["minimumWords"] == 57
    assert 54 < b["minimumWords"]


def test_word_budget_classify_in_range():
    """62-word script for standard_32_38 with 5 scenes → in range."""
    b = calculate_word_budget(target_sec=35, min_sec=32, max_sec=38, scene_count=5)
    assert b["minimumWords"] <= 62 <= b["maximumWords"]


def test_word_budget_generate_script_uses_budget():
    """Verify generate_script's _build_duration_prompt_instruction_v2 uses budget."""
    from generate_script import _build_duration_prompt_instruction_v2 as _build_duration_prompt_instruction
    budget = calculate_word_budget(target_sec=35, min_sec=32, max_sec=38, scene_count=5)
    instruction = _build_duration_prompt_instruction(budget, "balanced")
    assert "57" in instruction
    assert "62" in instruction
    assert "67" in instruction
    assert "32-38" in instruction or "32" in instruction


def test_word_budget_retry_instruction_contains_correction():
    """Retry instruction must include actual word count, missing words, budgets."""
    from generate_script import _build_retry_instruction_v2 as _build_retry_instruction
    budget = calculate_word_budget(target_sec=35, min_sec=32, max_sec=38, scene_count=5)
    instruction = _build_retry_instruction(budget, actual_word_count=54, actual_scene_count=5, estimated_dur=30.9, structural_issues=[], allow_generated_images=False)
    assert "54" in instruction
    assert "57" in instruction
    assert "62" in instruction
    assert "67" in instruction
    assert "30.9" in instruction or "30" in instruction
    assert "3" in instruction or "expansion" in instruction.lower()


# ── Prompt-contract consistency tests ──────────────────────────────────


def test_system_prompt_no_fixed_duration():
    """SYSTEM_PROMPT must not contain fixed '25-30' duration range."""
    from generate_script import SYSTEM_PROMPT_V2 as SYSTEM_PROMPT
    assert "25-30" not in SYSTEM_PROMPT, "SYSTEM_PROMPT must not hardcode duration range"
    assert "<30s" not in SYSTEM_PROMPT, "SYSTEM_PROMPT must not reference under-30 limit"


def test_system_prompt_no_fixed_word_count():
    """SYSTEM_PROMPT must not contain fixed '45-55' word range."""
    from generate_script import SYSTEM_PROMPT_V2 as SYSTEM_PROMPT
    assert "45-55" not in SYSTEM_PROMPT, "SYSTEM_PROMPT must not hardcode word count"


def test_standard_profile_prompt_has_dynamic_budget():
    """standard_32_38 dry-run prompt must include 32-38 range and 57-67 word budget."""
    from generate_script import _build_duration_prompt_instruction_v2 as _build_duration_prompt_instruction
    budget = calculate_word_budget(target_sec=35, min_sec=32, max_sec=38, scene_count=5)
    inst = _build_duration_prompt_instruction(budget, "balanced")
    assert "32" in inst and "38" in inst, "standard_32_38 prompt must contain min/max duration"
    assert "57" in inst and "67" in inst, "standard_32_38 prompt must contain word budget"
    assert "62" in inst, "standard_32_38 prompt must contain preferred words"


def test_extended_profile_prompt_has_dynamic_budget():
    """extended_50_60 dry-run prompt must include 50-60 range and its own word budget."""
    from generate_script import _build_duration_prompt_instruction_v2 as _build_duration_prompt_instruction
    budget = calculate_word_budget(target_sec=55, min_sec=50, max_sec=60, scene_count=6)
    inst = _build_duration_prompt_instruction(budget, "balanced")
    assert "50" in inst and "60" in inst, "extended_50_60 prompt must contain min/max duration"
    assert str(budget["minimumWords"]) in inst, "extended_50_60 prompt must contain minimum words"
    assert str(budget["maximumWords"]) in inst, "extended_50_60 prompt must contain maximum words"
    assert str(budget["preferredWords"]) in inst, "extended_50_60 prompt must contain preferred words"


def test_short_profile_prompt_has_correct_range():
    """short_25_30 prompt must still include its own 25-30 range and word budget."""
    from generate_script import _build_duration_prompt_instruction_v2 as _build_duration_prompt_instruction
    budget = calculate_word_budget(target_sec=28, min_sec=25, max_sec=30, scene_count=5)
    inst = _build_duration_prompt_instruction(budget, "balanced")
    assert "25" in inst and "30" in inst, "short_25_30 prompt must contain min/max duration"
    assert str(budget["minimumWords"]) in inst, "short_25_30 prompt must contain minimum words"
    assert str(budget["maximumWords"]) in inst, "short_25_30 prompt must contain maximum words"


def test_prompt_has_no_fixed_under_30_reference():
    """Dynamic prompt must not fall back to hardcoded under-30 constraints."""
    from generate_script import _build_duration_prompt_instruction_v2 as _build_duration_prompt_instruction
    budget = calculate_word_budget(target_sec=35, min_sec=32, max_sec=38, scene_count=5)
    inst = _build_duration_prompt_instruction(budget, "balanced")
    assert "<30s" not in inst
    assert "25-30" not in inst
    assert "45-55" not in inst


# ── Approximate duration resolution tests (Phase 22) ──────────────────


def test_duration_28_resolves_short_profile():
    """--duration 28 resolves to short_25_30, target=28, constrained to 25-30."""
    r = resolve_requested_duration(requested_sec=28)
    assert r["profile_name"] == "short_25_30"
    assert r["targetSec"] == 28
    assert r["minSec"] == 25  # 28-3=25, clamped to profile min
    assert r["maxSec"] == 30  # 28+3=31, clamped to profile max


def test_duration_35_resolves_standard_profile():
    """--duration 35 resolves to standard_32_38, target=35, min=32, max=38."""
    r = resolve_requested_duration(requested_sec=35)
    assert r["profile_name"] == "standard_32_38"
    assert r["targetSec"] == 35
    assert r["minSec"] == 32  # 35-4=31, clamped to profile min=32
    assert r["maxSec"] == 38  # 35+4=39, clamped to profile max=38


def test_duration_42_resolves_standard_profile():
    """--duration 42 resolves to standard_32_38, target=42, min=38, max=46."""
    r = resolve_requested_duration(requested_sec=42)
    assert r["profile_name"] == "standard_32_38"
    assert r["targetSec"] == 42
    # tolerance = clamp(round(42*0.10), 2, 5) = clamp(4.2, 2, 5) = 4
    assert r["minSec"] == 38  # 42-4=38
    assert r["maxSec"] == 46  # 42+4=46


def test_duration_55_resolves_extended_profile():
    """--duration 55 resolves to extended_50_60, target=55, min=50, max=60."""
    r = resolve_requested_duration(requested_sec=55)
    assert r["profile_name"] == "extended_50_60"
    assert r["targetSec"] == 55
    # tolerance = clamp(round(55*0.10), 2, 5) = clamp(6, 2, 5) = 5
    assert r["minSec"] == 50  # 55-5=50
    assert r["maxSec"] == 60  # 55+5=60


def test_duration_20_and_60_boundaries():
    """Boundary values 20 and 60 must resolve without error."""
    r20 = resolve_requested_duration(requested_sec=20)
    assert r20["profile_name"] == "short_25_30"
    assert r20["targetSec"] == 20

    r60 = resolve_requested_duration(requested_sec=60)
    assert r60["profile_name"] == "extended_50_60"
    assert r60["targetSec"] == 60


def test_duration_19_and_61_fail():
    """Values below 20 or above 60 must raise ValueError."""
    with pytest.raises(ValueError, match="below the minimum"):
        resolve_requested_duration(requested_sec=19)
    with pytest.raises(ValueError, match="exceeds the maximum"):
        resolve_requested_duration(requested_sec=61)


def test_explicit_profile_incompatible_duration_fails():
    """--duration-profile short_25_30 --duration 42 must fail (target exceeds constrained max)."""
    with pytest.raises(ValueError, match="must not exceed maximum"):
        resolve_requested_duration(requested_sec=42, requested_profile="short_25_30")


def test_explicit_overrides_highest_priority():
    """Explicit --duration-target/min/max override everything."""
    r = resolve_requested_duration(
        requested_sec=42,
        explicit_target=50,
        explicit_min=45,
        explicit_max=55,
    )
    assert r["targetSec"] == 50
    assert r["minSec"] == 45
    assert r["maxSec"] == 55


def test_invalid_numeric_combination_fails():
    """min > target must raise ValueError."""
    with pytest.raises(ValueError, match="minSec.*>.*targetSec"):
        resolve_requested_duration(explicit_target=30, explicit_min=35)


def test_legacy_no_args_defaults_to_short():
    """No duration arguments must default to short_25_30."""
    r = resolve_requested_duration()
    assert r["profile_name"] == "short_25_30"
    assert r["targetSec"] == 28
    assert r["minSec"] == 25
    assert r["maxSec"] == 30
    assert r["requestedSec"] is None


def test_word_budget_uses_resolved_values():
    """Word budget for --duration 42 must use resolved values, not static profile defaults."""
    r = resolve_requested_duration(requested_sec=42)
    b = calculate_word_budget(
        target_sec=r["targetSec"],
        min_sec=r["minSec"],
        max_sec=r["maxSec"],
        scene_count=5,
    )
    # standard_32_38 static default would be 57-62-67
    # For 42s: min=38, max=46
    # pauseSec = 1.4
    # minW = ceil((38-1.4)/60*110) = ceil(36.6/60*110) = ceil(67.1) = 68
    # prefW = round((42-1.4)/60*110) = round(40.6/60*110) = round(74.43) = 74
    # maxW = floor((46-1.4)/60*110) = floor(44.6/60*110) = floor(81.77) = 81
    assert b["minimumWords"] == 68
    assert b["preferredWords"] == 74
    assert b["maximumWords"] == 81
