"""Focused tests for the generic post-TTS duration fitting contract (Slice 1).

Covers the pure decision helpers in contracts.duration and the generic
voiceover-only repair prompt/merge in script.generator. No provider, voice or
language is referenced anywhere in the decisions.
"""

import copy
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

import pytest

from shorts_creator.contracts.duration import (
    DEFAULT_FITTING_RATIO_MAX,
    DEFAULT_FITTING_RATIO_MIN,
    distribute_words,
    evaluate_duration_fitting,
)

from shorts_creator.script.generator import (
    _apply_voiceover_repair,
    _build_voiceover_repair_prompt,
)

V2_SCHEMA_VERSION = 2


def _is_v2_valid(script: dict) -> bool:
    from shorts_creator.script.generator import _validate_and_canonicalize_script_v2
    canonical, errs, _ = _validate_and_canonicalize_script_v2(
        script, allow_generated_images=False
    )
    return canonical is not None and not errs


# ── Decision helpers ───────────────────────────────────────────────────────


def test_projected_in_range_is_pass():
    r = evaluate_duration_fitting(
        current_word_count=52,
        projected_duration_sec=28.5,
        target_sec=28,
        min_sec=25,
        max_sec=30,
    )
    assert r["decision"] == "PASS"
    assert r["proposedWords"] == 52
    assert r["deltaToRangeSec"] == 0


def test_short_projected_is_expand():
    r = evaluate_duration_fitting(
        current_word_count=52,
        projected_duration_sec=20.8,
        target_sec=30,
        min_sec=27,
        max_sec=30,
    )
    assert r["decision"] == "EXPAND"
    assert r["proposedWords"] > r["currentWords"]


def test_long_projected_is_compress():
    r = evaluate_duration_fitting(
        current_word_count=52,
        projected_duration_sec=36.0,
        target_sec=30,
        min_sec=27,
        max_sec=30,
    )
    assert r["decision"] == "COMPRESS"
    assert r["proposedWords"] < r["currentWords"]


def test_expand_ratio_capped_at_max():
    r = evaluate_duration_fitting(
        current_word_count=52,
        projected_duration_sec=10.0,
        target_sec=30,
        min_sec=27,
        max_sec=30,
    )
    # Desired 30 / projected 10 = 3.0, capped to policy max 1.50
    assert r["boundedRatio"] == pytest.approx(DEFAULT_FITTING_RATIO_MAX)
    assert r["proposedWords"] == round(52 * DEFAULT_FITTING_RATIO_MAX)
    assert r["rawRatio"] > r["boundedRatio"]


def test_compress_ratio_floored_at_min():
    r = evaluate_duration_fitting(
        current_word_count=52,
        projected_duration_sec=90.0,
        target_sec=30,
        min_sec=27,
        max_sec=30,
    )
    assert r["boundedRatio"] == pytest.approx(DEFAULT_FITTING_RATIO_MIN)
    assert r["proposedWords"] == round(52 * DEFAULT_FITTING_RATIO_MIN)
    assert r["rawRatio"] < r["boundedRatio"]


@pytest.mark.parametrize("bad", [
    None,
    0,
    -1.0,
    float("nan"),
    float("inf"),
    "abc",
])
def test_invalid_projected_duration_rejected(bad):
    with pytest.raises(ValueError):
        evaluate_duration_fitting(
            current_word_count=52,
            projected_duration_sec=bad,
            target_sec=28,
            min_sec=25,
            max_sec=30,
        )


def test_bool_rejected_as_duration():
    with pytest.raises(ValueError):
        evaluate_duration_fitting(
            current_word_count=52,
            projected_duration_sec=True,
            target_sec=28,
            min_sec=25,
            max_sec=30,
        )


def test_invalid_window_rejected():
    with pytest.raises(ValueError):
        evaluate_duration_fitting(
            current_word_count=52,
            projected_duration_sec=28.0,
            target_sec=25,
            min_sec=27,
            max_sec=30,
        )


def test_decision_outputs_full_schema():
    r = evaluate_duration_fitting(
        current_word_count=52,
        projected_duration_sec=30.0,
        target_sec=30,
        min_sec=27,
        max_sec=30,
    )
    for key in ["decision", "currentWords", "proposedWords", "projectedDurationSec",
                "targetSec", "minSec", "maxSec", "rawRatio", "boundedRatio",
                "ratioPolicyMin", "ratioPolicyMax", "deltaToRangeSec"]:
        assert key in r


# ── Per-scene distribution ─────────────────────────────────────────────────


def test_distribute_preserves_total():
    counts = [10, 12, 14, 8, 8]
    target = 60
    got = distribute_words(current_counts=counts, target_total=target)
    assert sum(got) == target
    assert len(got) == len(counts)


def test_distribute_expand():
    counts = [10, 12, 14, 8, 8]
    got = distribute_words(current_counts=counts, target_total=75)
    assert sum(got) == 75
    assert all(g > 0 for g in got)
    # proportionally larger scenes stay larger
    assert got[2] > got[3]


def test_distribute_compress():
    counts = [10, 12, 14, 8, 8]
    got = distribute_words(current_counts=counts, target_total=45)
    assert sum(got) == 45
    assert all(g > 0 for g in got)


def test_distribute_deterministic():
    counts = [10, 12, 14, 8, 8]
    a = distribute_words(current_counts=counts, target_total=60)
    b = distribute_words(current_counts=counts, target_total=60)
    assert a == b


def test_distribute_min_one_word_contract():
    counts = [11, 12, 11, 9, 9]
    got = distribute_words(current_counts=counts, target_total=60, minimum_words_per_scene=7)
    assert sum(got) == 60
    assert all(g >= 7 for g in got)


def test_distribute_min_words_per_scene_enforced():
    counts = [11, 12, 11, 9, 9]
    got = distribute_words(current_counts=counts, target_total=40, minimum_words_per_scene=7)
    assert sum(got) == 40
    assert all(g >= 7 for g in got)


def test_distribute_rejects_target_below_min_total():
    with pytest.raises(ValueError):
        distribute_words(current_counts=[11, 12, 11, 9, 9], target_total=34, minimum_words_per_scene=7)


def test_distribute_rejects_invalid_min_words_per_scene():
    for bad in (0, -1, True, "x"):
        with pytest.raises(ValueError):
            distribute_words(current_counts=[11, 12, 11, 9, 9], target_total=60, minimum_words_per_scene=bad)


# ── Voiceover-only repair prompt / merge ───────────────────────────────────


def _base_script(scene_count=4):
    def _vp():
        return {
            "_schemaVersion": V2_SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["test subject"],
            "searchQueries": ["test query"],
            "assetPreferences": ["diagram"],
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetPreference": "diagram",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
        }

    return {
        "title": "Título",
        "hook": "Gancho",
        "summary": "Resumen",
        "totalTargetDurationSec": 30,
        "scenes": [
            {
                "sceneNumber": i,
                "voiceover": f"voz escena {i}",
                "subtitle": f"subtítulo {i}",
                "targetDurationSec": 7.5,
                "purpose": "context",
                "narrativeFunction": "hook",
                "visualPlan": _vp(),
            }
            for i in range(1, scene_count + 1)
        ],
    }


def _payload(counts):
    return {
        "scenes": [
            {"sceneNumber": i, "voiceover": " ".join(f"nueva{i}" for _ in range(counts[i - 1]))}
            for i in range(1, len(counts) + 1)
        ]
    }


def test_repair_prompt_accepts_direction():
    script = _base_script()
    for direction in ("EXPAND", "COMPRESS"):
        prompt = _build_voiceover_repair_prompt(
            script, direction=direction, current_word_count=52,
            target_total_words=75, scene_word_targets=[15, 15, 15, 15],
        )
        assert f' "direction": "{direction}"' in prompt or f'"direction": "{direction}"' in prompt
        assert '"targetTotalWords": 75' in prompt
        assert "suman el objetivo global" in prompt


def test_repair_prompt_has_no_bootstrap_budget_contract():
    """The post-TTS repair prompt must NOT reimpose the bootstrap 47-52 range."""
    script = _base_script()
    prompt = _build_voiceover_repair_prompt(
        script, direction="EXPAND", current_word_count=52,
        target_total_words=75, scene_word_targets=[15, 15, 15, 15],
    )
    assert "47" not in prompt
    assert "minimumWords" not in prompt
    assert "maximumWords" not in prompt
    assert "entre 47 y 52" not in prompt
    assert "la autoridad final es la duración de voz real medida" in prompt.lower() or \
        "la duración real medida decide" in prompt.lower()


def test_repair_prompt_interpolates_operational_target():
    prompt = _build_voiceover_repair_prompt(
        _base_script(), direction="EXPAND", current_word_count=52,
        target_total_words=75, scene_word_targets=[19, 19, 19, 18],
    )
    assert "objetivo global de 75 palabras" in prompt
    assert "{target_total_words}" not in prompt


def test_generic_repair_system_prompt_and_temperature():
    from shorts_creator.script.generator import (
        COMPRESSION_LLM_TEMPERATURE,
        VOICEOVER_REPAIR_SYSTEM_PROMPT,
        _llm_temperature_for_system_prompt,
    )
    assert "EXPAND" in VOICEOVER_REPAIR_SYSTEM_PROMPT
    assert "COMPRESS" in VOICEOVER_REPAIR_SYSTEM_PROMPT
    assert '"sceneNumber"' in VOICEOVER_REPAIR_SYSTEM_PROMPT
    assert '"voiceover"' in VOICEOVER_REPAIR_SYSTEM_PROMPT
    assert "visualPlan" in VOICEOVER_REPAIR_SYSTEM_PROMPT
    assert _llm_temperature_for_system_prompt(VOICEOVER_REPAIR_SYSTEM_PROMPT) == COMPRESSION_LLM_TEMPERATURE


def test_repair_prompt_rejects_unknown_direction():
    script = _base_script()
    with pytest.raises(ValueError):
        _build_voiceover_repair_prompt(
            script, direction="SIDEWAYS", current_word_count=52,
            target_total_words=75, scene_word_targets=[15, 15, 15, 15],
        )


def test_repair_expand_preserves_structure():
    base = _base_script()
    before = copy.deepcopy(base)
    assert _is_v2_valid(before)
    payload = _payload([15, 15, 15, 15])
    merged, errs = _apply_voiceover_repair(base, payload, expected_scene_numbers=[1, 2, 3, 4])
    assert errs == []
    assert merged is not None
    assert base == before  # input never mutated
    assert _is_v2_valid(merged)
    for i in range(1, 5):
        scene = merged["scenes"][i - 1]
        assert scene["voiceover"].startswith("nueva")
        assert scene["visualPlan"] == before["scenes"][i - 1]["visualPlan"]
        assert scene["purpose"] == "context"
        assert scene["narrativeFunction"] == "hook"
        assert scene["sceneNumber"] == i
    assert merged["title"] == before["title"]


def test_repair_compress_preserves_structure():
    base = _base_script()
    before = copy.deepcopy(base)
    assert _is_v2_valid(before)
    payload = _payload([8, 8, 8, 8])
    merged, errs = _apply_voiceover_repair(base, payload, expected_scene_numbers=[1, 2, 3, 4])
    assert errs == []
    assert merged is not None
    assert _is_v2_valid(merged)
    for i in range(1, 5):
        scene = merged["scenes"][i - 1]
        assert scene["visualPlan"] == before["scenes"][i - 1]["visualPlan"]
        assert scene["purpose"] == "context"
        assert scene["narrativeFunction"] == "hook"
        assert scene["sceneNumber"] == i


def test_repair_keeps_scene_count_and_order():
    base = _base_script(5)
    payload = _payload([10, 10, 10, 10, 10])
    merged, errs = _apply_voiceover_repair(base, payload, expected_scene_numbers=[1, 2, 3, 4, 5])
    assert errs == []
    assert [s["sceneNumber"] for s in merged["scenes"]] == [1, 2, 3, 4, 5]


# ── E2E-like regression (real first run: 52 words, 20.813s projected) ───────


def test_e2e_regression_52_words_20_813s():
    r = evaluate_duration_fitting(
        current_word_count=52,
        projected_duration_sec=20.813,
        target_sec=30,
        min_sec=27,
        max_sec=30,
    )
    assert r["decision"] == "EXPAND"
    assert r["proposedWords"] == 75  # round(52 * min(30/20.813, 1.50))

    counts = [11, 12, 11, 9, 9]
    got = distribute_words(
        current_counts=counts,
        target_total=r["proposedWords"],
        minimum_words_per_scene=7,
    )
    assert sum(got) == r["proposedWords"]
    assert len(got) == 5
    assert all(g >= 7 for g in got)

    prompt = _build_voiceover_repair_prompt(
        _base_script(5), direction="EXPAND", current_word_count=52,
        target_total_words=r["proposedWords"], scene_word_targets=got,
    )
    # No contradictory bootstrap range must survive into the repair prompt.
    assert "47" not in prompt
    assert "minimumWords" not in prompt
    assert "maximumWords" not in prompt
