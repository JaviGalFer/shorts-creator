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


def test_distribute_min_one_word():
    counts = [1, 1, 8]
    got = distribute_words(current_counts=counts, target_total=3)
    assert sum(got) == 3
    assert all(g >= 1 for g in got)


# ── Voiceover-only repair prompt / merge ───────────────────────────────────


def _base_script(scene_count=4):
    return {
        "title": "Título",
        "scenes": [
            {
                "sceneNumber": i,
                "voiceover": f"voz escena {i}",
                "subtitle": f"subtítulo {i}",
                "purpose": "context",
                "narrativeFunction": "hook",
                "visualPlan": {
                    "_schemaVersion": 2,
                    "editorialRole": "context_map",
                    "visualSequence": [{"segmentIndex": 1, "assetType": "map"}],
                },
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
            target_total_words=60, minimum_words=47, maximum_words=65,
            scene_word_targets=[12, 12, 12, 12],
        )
        assert f' "direction": "{direction}"' in prompt or f'"direction": "{direction}"' in prompt
        assert '"targetTotalWords": 60' in prompt
        assert "suman el objetivo global" in prompt


def test_repair_prompt_rejects_unknown_direction():
    script = _base_script()
    with pytest.raises(ValueError):
        _build_voiceover_repair_prompt(
            script, direction="SIDEWAYS", current_word_count=52,
            target_total_words=60, minimum_words=47, maximum_words=65,
            scene_word_targets=[12, 12, 12, 12],
        )


def test_repair_expand_preserves_structure():
    base = _base_script()
    before = copy.deepcopy(base)
    payload = _payload([15, 15, 15, 15])
    merged, errs = _apply_voiceover_repair(base, payload, expected_scene_numbers=[1, 2, 3, 4])
    assert errs == []
    assert merged is not None
    assert base == before  # input never mutated
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
    payload = _payload([8, 8, 8, 8])
    merged, errs = _apply_voiceover_repair(base, payload, expected_scene_numbers=[1, 2, 3, 4])
    assert errs == []
    assert merged is not None
    for i in range(1, 5):
        scene = merged["scenes"][i - 1]
        assert scene["visualPlan"] == before["scenes"][i - 1]["visualPlan"]
        assert scene["sceneNumber"] == i


def test_repair_keeps_scene_count_and_order():
    base = _base_script(5)
    payload = _payload([10, 10, 10, 10, 10])
    merged, errs = _apply_voiceover_repair(base, payload, expected_scene_numbers=[1, 2, 3, 4, 5])
    assert errs == []
    assert [s["sceneNumber"] for s in merged["scenes"]] == [1, 2, 3, 4, 5]