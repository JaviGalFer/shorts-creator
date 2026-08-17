"""Focused tests for the visual-query specificity guard and the shared
lexical vocabulary move (script-visual-specificity, Slice 1).

Run: python3 -m pytest tests/test_visual_specificity.py -v
"""

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "bin"))

import pytest

from shorts_creator.contracts import visual_terms
from shorts_creator.contracts.visual_specificity import (
    VALID,
    VAGUE,
    assess_query_specificity,
    assess_visual_plan_specificity,
)
from shorts_creator.assets import semantic


# ── Must reject: clearly vague/editorial queries ────────────────────────────


@pytest.mark.parametrize("query", [
    "popular culture",
    "future of YouTube",
    "viral YouTube video screenshot",
    "famous early YouTubers photo",
    "future of the youtube",
])
def test_vague_queries_rejected(query):
    assessment = assess_query_specificity(query)
    assert assessment["verdict"] == VAGUE, f"expected VAGUE for '{query}': {assessment}"
    assert assessment["ok"] is False
    assert isinstance(assessment["reason"], str) and assessment["reason"]


def test_all_weak_query_rejected():
    assessment = assess_query_specificity("famous popular viral culture")
    assert assessment["verdict"] == VAGUE
    assert assessment["anchorTerms"] == []


def test_filler_only_query_rejected():
    assessment = assess_query_specificity("photo image illustration")
    assert assessment["verdict"] == VAGUE
    assert assessment["anchorTerms"] == []


def test_stopwords_cannot_rescue_a_vague_query():
    assert assess_query_specificity("the future of the youtube")["verdict"] == VAGUE
    assert assess_query_specificity("the popular culture")["verdict"] == VAGUE
    assert assess_query_specificity("this and that about the future")["verdict"] == VAGUE


def test_empty_and_non_string_rejected():
    assert assess_query_specificity("")["verdict"] == VAGUE
    assert assess_query_specificity(None)["verdict"] == VAGUE
    assert assess_query_specificity(42)["verdict"] == VAGUE


# ── Must accept: concrete / retrievable queries ─────────────────────────────


@pytest.mark.parametrize("query", [
    "Smosh",
    "Minecraft",
    "Chernobyl",
    "aurora borealis solar particles photograph",
    "test query",
    "early YouTube vlogs image",
])
def test_concrete_queries_accepted(query):
    assessment = assess_query_specificity(query)
    assert assessment["verdict"] == VALID, f"expected VALID for '{query}': {assessment}"
    assert assessment["ok"] is True
    assert assessment["anchorTerms"], f"expected anchors for '{query}'"


@pytest.mark.parametrize("query", [
    "Jenna Marbles early YouTube video screenshot",
    "YouTube logo photograph",
    "YouTube interface screenshot",
    "viral content YouTube screenshot",
    "YouTube logo history diagram",
])
def test_calibrated_queries_now_valid(query):
    # Runtime calibration (Slice 3A): concrete subjects padded with neutral
    # descriptors or bounded weak context remain VALID under the new rule.
    assessment = assess_query_specificity(query)
    assert assessment["verdict"] == VALID, f"expected VALID for '{query}': {assessment}"
    assert assessment["ok"] is True
    assert len(assessment["anchorTerms"]) >= 1


def test_single_concrete_entity_remains_valid():
    for entity in ("Smosh", "Minecraft", "Chernobyl", "Turing", "Fuji"):
        assessment = assess_query_specificity(entity)
        assert assessment["verdict"] == VALID, entity
        assert assessment["anchorTerms"] == [entity.lower()]


def test_diagnostics_shape():
    assessment = assess_query_specificity("aurora borealis famous popular culture")
    assert set(assessment) >= {
        "ok", "verdict", "reason", "contentTerms", "weakTerms", "anchorTerms",
    }
    assert assessment["verdict"] == VAGUE
    assert "aurora" in assessment["contentTerms"]
    assert "famous" in assessment["weakTerms"]
    assert "popular" in assessment["weakTerms"]
    assert "aurora" in assessment["anchorTerms"]
    assert "famous" not in assessment["anchorTerms"]


# ── Vocabulary move parity: semantic.py re-exports the shared terms ─────────


def test_semantic_reexports_moved_vocabulary():
    assert semantic.GENERIC_FILLER is visual_terms.GENERIC_FILLER
    assert semantic.WEAK_SUPPORT_TERMS is visual_terms.WEAK_SUPPORT_TERMS
    assert semantic.tokenize is visual_terms.tokenize


def test_tokenize_behavior_unchanged_after_move():
    samples = [
        "Aurora Borealis photo",
        "Photosynthesis diagram plant leaf",
        "octopus camouflaged on ocean reef",
        "Storming of the Bastille 1789 painting",
    ]
    for sample in samples:
        assert semantic.tokenize(sample) == visual_terms.tokenize(sample)


@pytest.mark.parametrize("word", ["image", "photo", "stock", "wallpaper", "jpeg"])
def test_generic_filler_excluded_by_tokenize(word):
    assert word not in visual_terms.tokenize(word)


def test_stopwords_are_guard_only_not_filler():
    assert "the" in visual_terms.tokenize("the future of YouTube")
    assert "the" in visual_terms.STOPWORDS
    assert "of" in visual_terms.STOPWORDS
    assert "the" not in semantic.WEAK_SUPPORT_TERMS
    assert "the" not in semantic.GENERIC_FILLER
    assert "the" not in visual_terms.SPECIFICITY_WEAK_TERMS


def test_specificity_weak_terms_is_a_subset_of_semantic_weak():
    assert visual_terms.SPECIFICITY_WEAK_TERMS <= semantic.WEAK_SUPPORT_TERMS
    assert semantic.WEAK_SUPPORT_TERMS != visual_terms.SPECIFICITY_WEAK_TERMS


@pytest.mark.parametrize("word", [
    "logo", "interface", "formation", "first", "current", "latest", "modern",
    "new", "old",
])
def test_neutral_descriptors_not_specificity_weak(word):
    # Calibration (Slice 3A): these neutral descriptors must NOT count as
    # specificity-weak, even though several remain semantic weak terms.
    assert word not in visual_terms.SPECIFICITY_WEAK_TERMS


# ── Plan-level assessment ───────────────────────────────────────────────────


def test_plan_level_mixed_queries():
    plan = {
        "_schemaVersion": 2,
        "searchQueries": ["popular culture", "aurora borealis particles"],
        "visualSequence": [
            {"segmentIndex": 1, "searchQuery": "viral YouTube screenshot"},
            {"segmentIndex": 2, "searchQuery": None},
            {"segmentIndex": 3, "searchQuery": "Chernobyl"},
        ],
    }
    result = assess_visual_plan_specificity(plan)
    assert result["ok"] is False
    codes = {e["code"] for e in result["errors"]}
    assert codes == {
        "QUERY_NOT_SPECIFIC",
        "SEGMENT_QUERY_NOT_SPECIFIC",
    }
    paths = {e["path"] for e in result["errors"]}
    assert "searchQueries[0]" in paths
    assert "visualSequence[0].searchQuery" in paths


def test_plan_level_all_valid():
    plan = {
        "_schemaVersion": 2,
        "searchQueries": ["Smosh", "aurora borealis particles"],
        "visualSequence": [
            {"segmentIndex": 1, "searchQuery": "Minecraft"},
            {"segmentIndex": 2, "searchQuery": None},
        ],
    }
    result = assess_visual_plan_specificity(plan)
    assert result["ok"] is True
    assert result["errors"] == []
    assert len(result["checks"]) == 3


def test_plan_level_invalid_input():
    assert assess_visual_plan_specificity(None)["ok"] is False
    assert assess_visual_plan_specificity("not a dict")["ok"] is False