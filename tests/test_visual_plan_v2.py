"""Tests for VisualPlan v2 canonicalizer and validator.

Run: python3 -m pytest tests/test_visual_plan_v2.py -v
"""

import json
import sys
from pathlib import Path

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))

from visual_plan_v2 import (
    canonicalize_visual_plan_v2,
    validate_visual_plan_v2,
    ALLOWED_VISUAL_INTENTS,
    ALLOWED_ASSET_PREFERENCES,
    ALLOWED_TRANSITIONS,
    ALLOWED_PROVIDERS,
    SCHEMA_VERSION,
    REQUIRED_FIELDS,
)


# ── Fixture helpers ─────────────────────────────────────────────────────────


def _base_fixture(**overrides):
    plan = {
        "_schemaVersion": SCHEMA_VERSION,
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
    plan.update(overrides)
    return plan


def _photosynthesis_plan():
    return {
        "_schemaVersion": SCHEMA_VERSION,
        "visualIntent": "explain",
        "subjects": ["fotosíntesis", "cloroplasto", "hoja"],
        "searchQueries": [
            "photosynthesis diagram",
            "chloroplast structure plant leaf",
        ],
        "assetPreferences": ["diagram", "illustration"],
        "visualSequence": [
            {
                "segmentIndex": 1,
                "assetPreference": "diagram",
                "searchQuery": "photosynthesis diagram plant leaf",
                "durationFraction": 1.0,
                "transition": "cut",
            }
        ],
    }


def _blockchain_plan():
    return {
        "_schemaVersion": SCHEMA_VERSION,
        "visualIntent": "explain",
        "subjects": ["blockchain", "distributed ledger", "transaction"],
        "searchQueries": [
            "blockchain diagram network",
            "how blockchain works distributed ledger",
        ],
        "assetPreferences": ["diagram", "illustration"],
        "visualSequence": [
            {
                "segmentIndex": 1,
                "assetPreference": "diagram",
                "searchQuery": "blockchain distributed ledger diagram",
                "durationFraction": 1.0,
                "transition": "cut",
            }
        ],
    }


def _octopus_plan():
    return {
        "_schemaVersion": SCHEMA_VERSION,
        "visualIntent": "show",
        "subjects": ["octopus", "camouflage", "chromatophore", "cephalopod"],
        "searchQueries": [
            "octopus camouflage ocean reef",
            "cephalopod color change skin",
        ],
        "assetPreferences": ["photograph", "diagram"],
        "location": "ocean",
        "preferredProviders": ["pexels", "wikimedia_commons"],
        "visualSequence": [
            {
                "segmentIndex": 1,
                "assetPreference": "photograph",
                "searchQuery": "octopus camouflaged on ocean reef",
                "durationFraction": 0.6,
                "transition": "fade",
            },
            {
                "segmentIndex": 2,
                "assetPreference": "diagram",
                "searchQuery": "cephalopod chromatophore skin cross section",
                "durationFraction": 0.4,
                "transition": "cut",
            },
        ],
    }


def _french_revolution_plan():
    return {
        "_schemaVersion": SCHEMA_VERSION,
        "visualIntent": "contextualize",
        "subjects": ["Bastilla", "Revolución Francesa", "París"],
        "searchQueries": [
            "Storming of the Bastille 1789 painting",
            "Prise de la Bastille 14 juillet",
        ],
        "assetPreferences": ["archive", "painting"],
        "period": "1789",
        "location": "París",
        "preferredProviders": ["wikimedia_commons"],
        "visualSequence": [
            {
                "segmentIndex": 1,
                "assetPreference": "painting",
                "searchQuery": "Storming of the Bastille July 1789 painting",
                "durationFraction": 0.6,
                "transition": "cut",
            },
            {
                "segmentIndex": 2,
                "assetPreference": "archive",
                "searchQuery": "French Revolution Bastille document 1789",
                "durationFraction": 0.4,
                "transition": "fade",
            },
        ],
    }


def _marie_curie_plan():
    return {
        "_schemaVersion": SCHEMA_VERSION,
        "visualIntent": "show",
        "subjects": ["Marie Curie", "radioactivity", "radium", "polonium"],
        "searchQueries": [
            "Marie Curie portrait photograph",
            "Marie Curie laboratory Paris 1900s",
        ],
        "assetPreferences": ["photograph", "archive"],
        "period": "early 20th century",
        "location": "Paris",
        "preferredProviders": ["wikimedia_commons"],
        "visualSequence": [
            {
                "segmentIndex": 1,
                "assetPreference": "photograph",
                "searchQuery": "Marie Curie portrait photograph Nobel Prize",
                "durationFraction": 0.7,
                "transition": "cut",
            },
            {
                "segmentIndex": 2,
                "assetPreference": "archive",
                "searchQuery": "Marie Curie laboratory Paris 1900",
                "durationFraction": 0.3,
                "transition": "fade",
            },
        ],
    }


def _pomodoro_plan():
    return {
        "_schemaVersion": SCHEMA_VERSION,
        "visualIntent": "explain",
        "subjects": [
            "Pomodoro technique",
            "time management",
            "focus",
            "productivity",
        ],
        "searchQueries": [
            "pomodoro technique diagram timer",
            "time blocking method workflow",
        ],
        "assetPreferences": ["diagram", "illustration", "stock"],
        "visualSequence": [
            {
                "segmentIndex": 1,
                "assetPreference": "diagram",
                "searchQuery": "pomodoro technique 25 minute work flow diagram",
                "durationFraction": 0.5,
                "transition": "cut",
            },
            {
                "segmentIndex": 2,
                "assetPreference": "illustration",
                "searchQuery": "person working focused at desk timer",
                "durationFraction": 0.5,
                "transition": "fade",
            },
        ],
    }


# ── Canonicalization: 6 fixtures ───────────────────────────────────────────


class TestCanonicalizeFixtures:
    def test_photosynthesis_canonicalizes(self):
        result = canonicalize_visual_plan_v2(_photosynthesis_plan())
        assert result["ok"] is True
        assert result["canonicalPlan"] is not None
        plan = result["canonicalPlan"]
        assert plan["_schemaVersion"] == SCHEMA_VERSION
        assert plan["visualIntent"] == "explain"
        assert plan["subjects"] == ["fotosíntesis", "cloroplasto", "hoja"]
        assert plan["period"] is None
        assert plan["location"] is None
        assert plan["allowGeneratedImage"] is False
        assert plan["preferredProviders"] == []
        assert plan["imageGenerationPrompt"] is None
        assert plan["negativePrompt"] is None
        assert len(plan["visualSequence"]) == 1

    def test_photosynthesis_no_legacy_fields_inferred(self):
        result = canonicalize_visual_plan_v2(_photosynthesis_plan())
        plan = result["canonicalPlan"]
        legacy = [
            "editorialRole", "visualTemporalIntent", "strategy",
            "primaryAssetType", "secondaryAssetType",
            "style", "mood", "licenseRequired", "visualImportance",
        ]
        for field in legacy:
            assert field not in plan, f"legacy field '{field}' was inferred"

    def test_blockchain_canonicalizes(self):
        result = canonicalize_visual_plan_v2(_blockchain_plan())
        assert result["ok"] is True
        plan = result["canonicalPlan"]
        assert plan["visualIntent"] == "explain"
        assert plan["subjects"] == ["blockchain", "distributed ledger", "transaction"]
        assert plan["assetPreferences"] == ["diagram", "illustration"]
        assert len(plan["visualSequence"]) == 1

    def test_blockchain_no_legacy_fields_inferred(self):
        result = canonicalize_visual_plan_v2(_blockchain_plan())
        plan = result["canonicalPlan"]
        legacy = [
            "editorialRole", "visualTemporalIntent", "strategy",
            "primaryAssetType", "secondaryAssetType",
        ]
        for field in legacy:
            assert field not in plan, f"legacy field '{field}' was inferred"

    def test_octopus_canonicalizes(self):
        result = canonicalize_visual_plan_v2(_octopus_plan())
        assert result["ok"] is True
        plan = result["canonicalPlan"]
        assert plan["visualIntent"] == "show"
        assert plan["location"] == "ocean"
        assert plan["preferredProviders"] == ["pexels", "wikimedia_commons"]
        assert len(plan["visualSequence"]) == 2
        assert plan["visualSequence"][0]["assetPreference"] == "photograph"
        assert plan["visualSequence"][1]["assetPreference"] == "diagram"

    def test_octopus_no_legacy_fields_inferred(self):
        result = canonicalize_visual_plan_v2(_octopus_plan())
        plan = result["canonicalPlan"]
        legacy = [
            "editorialRole", "visualTemporalIntent", "strategy",
            "primaryAssetType", "secondaryAssetType",
        ]
        for field in legacy:
            assert field not in plan, f"legacy field '{field}' was inferred"

    def test_french_revolution_canonicalizes(self):
        result = canonicalize_visual_plan_v2(_french_revolution_plan())
        assert result["ok"] is True
        plan = result["canonicalPlan"]
        assert plan["visualIntent"] == "contextualize"
        assert plan["period"] == "1789"
        assert plan["location"] == "París"
        assert plan["assetPreferences"] == ["archive", "painting"]
        assert len(plan["visualSequence"]) == 2
        assert plan["visualSequence"][0]["assetPreference"] == "painting"
        assert plan["visualSequence"][1]["assetPreference"] == "archive"

    def test_french_revolution_no_legacy_fields_inferred(self):
        result = canonicalize_visual_plan_v2(_french_revolution_plan())
        plan = result["canonicalPlan"]
        legacy = [
            "editorialRole", "visualTemporalIntent", "strategy",
            "primaryAssetType", "secondaryAssetType",
        ]
        for field in legacy:
            assert field not in plan, f"legacy field '{field}' was inferred"

    def test_marie_curie_canonicalizes(self):
        result = canonicalize_visual_plan_v2(_marie_curie_plan())
        assert result["ok"] is True
        plan = result["canonicalPlan"]
        assert plan["visualIntent"] == "show"
        assert plan["period"] == "early 20th century"
        assert plan["location"] == "Paris"
        assert plan["assetPreferences"] == ["photograph", "archive"]
        assert plan["preferredProviders"] == ["wikimedia_commons"]

    def test_marie_curie_no_legacy_fields_inferred(self):
        result = canonicalize_visual_plan_v2(_marie_curie_plan())
        plan = result["canonicalPlan"]
        legacy = [
            "editorialRole", "visualTemporalIntent", "strategy",
            "primaryAssetType", "secondaryAssetType",
        ]
        for field in legacy:
            assert field not in plan, f"legacy field '{field}' was inferred"

    def test_pomodoro_canonicalizes(self):
        result = canonicalize_visual_plan_v2(_pomodoro_plan())
        assert result["ok"] is True
        plan = result["canonicalPlan"]
        assert plan["visualIntent"] == "explain"
        assert plan["assetPreferences"] == ["diagram", "illustration", "stock"]
        assert len(plan["visualSequence"]) == 2
        assert plan["visualSequence"][0]["assetPreference"] == "diagram"
        assert plan["visualSequence"][1]["assetPreference"] == "illustration"

    def test_pomodoro_no_legacy_fields_inferred(self):
        result = canonicalize_visual_plan_v2(_pomodoro_plan())
        plan = result["canonicalPlan"]
        legacy = [
            "editorialRole", "visualTemporalIntent", "strategy",
            "primaryAssetType", "secondaryAssetType",
        ]
        for field in legacy:
            assert field not in plan, f"legacy field '{field}' was inferred"


# ── Invalid schema/type cases ───────────────────────────────────────────────


class TestInvalidSchema:
    def test_schema_version_string_rejected(self):
        plan = _base_fixture(_schemaVersion="2")
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_FIELD_TYPE:_schemaVersion" in e for e in errors)

    def test_schema_version_1_rejected(self):
        plan = _base_fixture(_schemaVersion=1)
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("UNSUPPORTED_SCHEMA_VERSION" in e for e in errors)

    def test_schema_version_float_rejected(self):
        plan = _base_fixture(_schemaVersion=2.0)
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_FIELD_TYPE:_schemaVersion" in e for e in errors)

    def test_missing_schema_version(self):
        plan = _base_fixture()
        del plan["_schemaVersion"]
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("REQUIRED_FIELD_MISSING:_schemaVersion" in e for e in errors)

    def test_missing_visual_intent(self):
        plan = _base_fixture()
        del plan["visualIntent"]
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("REQUIRED_FIELD_MISSING:visualIntent" in e for e in errors)

    def test_missing_subjects(self):
        plan = _base_fixture()
        del plan["subjects"]
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("REQUIRED_FIELD_MISSING:subjects" in e for e in errors)

    def test_missing_search_queries(self):
        plan = _base_fixture()
        del plan["searchQueries"]
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("REQUIRED_FIELD_MISSING:searchQueries" in e for e in errors)

    def test_missing_asset_preferences(self):
        plan = _base_fixture()
        del plan["assetPreferences"]
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("REQUIRED_FIELD_MISSING:assetPreferences" in e for e in errors)

    def test_missing_visual_sequence(self):
        plan = _base_fixture()
        del plan["visualSequence"]
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("REQUIRED_FIELD_MISSING:visualSequence" in e for e in errors)

    def test_non_dict_input(self):
        result = canonicalize_visual_plan_v2("not a dict")
        assert result["ok"] is False
        assert "INVALID_INPUT" in result["diagnostics"]["errors"][0]["code"]

    def test_non_dict_input_validate(self):
        result = validate_visual_plan_v2([])
        assert result["ok"] is False
        assert "INVALID_INPUT" in result["diagnostics"]["errors"][0]["code"]


class TestInvalidEnums:
    def test_invalid_visual_intent(self):
        plan = _base_fixture(visualIntent="sing")
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_ENUM_VALUE:visualIntent" in e for e in errors)

    def test_invalid_asset_preference(self):
        plan = _base_fixture(assetPreferences=["hovercraft"])
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_ENUM_VALUE:assetPreferences[0]" in e for e in errors)

    def test_invalid_segment_asset_preference(self):
        plan = _base_fixture(
            assetPreferences=["diagram", "hovercraft"],
            visualSequence=[{
                "segmentIndex": 1,
                "assetPreference": "hovercraft",
                "durationFraction": 1.0,
            }],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_ENUM_VALUE:visualSequence[0].assetPreference" in e for e in errors)

    def test_invalid_transition(self):
        plan = _base_fixture(
            visualSequence=[{
                "segmentIndex": 1,
                "assetPreference": "diagram",
                "durationFraction": 1.0,
                "transition": "dissolve",
            }],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_ENUM_VALUE:visualSequence[0].transition" in e for e in errors)


class TestEmptyFields:
    def test_empty_subjects(self):
        plan = _base_fixture(subjects=[])
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("EMPTY_REQUIRED_FIELD:subjects" in e for e in errors)

    def test_empty_search_queries(self):
        plan = _base_fixture(searchQueries=[])
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("EMPTY_REQUIRED_FIELD:searchQueries" in e for e in errors)

    def test_empty_asset_preferences(self):
        plan = _base_fixture(assetPreferences=[])
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("EMPTY_REQUIRED_FIELD:assetPreferences" in e for e in errors)

    def test_empty_visual_sequence(self):
        plan = _base_fixture(visualSequence=[])
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("EMPTY_REQUIRED_FIELD:visualSequence" in e for e in errors)


class TestInvalidTypes:
    def test_subjects_not_list(self):
        plan = _base_fixture(subjects="subject")
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_FIELD_TYPE:subjects" in e for e in errors)

    def test_subjects_contains_non_string(self):
        plan = _base_fixture(subjects=["ok", 123])
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_FIELD_TYPE:subjects[1]" in e for e in errors)

    def test_allow_generated_image_not_bool(self):
        plan = _base_fixture(allowGeneratedImage="yes")
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_FIELD_TYPE:allowGeneratedImage" in e for e in errors)

    def test_search_queries_not_list(self):
        plan = _base_fixture(searchQueries="query")
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_FIELD_TYPE:searchQueries" in e for e in errors)


class TestInvalidSegmentIndex:
    def test_segment_index_not_sequential(self):
        plan = _base_fixture(
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 0.5, "transition": "cut"},
                {"segmentIndex": 3, "assetPreference": "diagram", "durationFraction": 0.5, "transition": "cut"},
            ]
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_SEGMENT_INDEX_SEQUENCE" in e for e in errors)

    def test_segment_index_zero(self):
        plan = _base_fixture(
            visualSequence=[
                {"segmentIndex": 0, "assetPreference": "diagram", "durationFraction": 1.0, "transition": "cut"},
            ]
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_SEGMENT_INDEX:" in e for e in errors)

    def test_duplicate_segment_index(self):
        plan = _base_fixture(
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 0.5, "transition": "cut"},
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 0.5, "transition": "cut"},
            ]
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("DUPLICATE_SEGMENT_INDEX" in e for e in errors)


class TestInvalidDurationFraction:
    def test_duration_sum_not_one(self):
        plan = _base_fixture(
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 0.4, "transition": "cut"},
                {"segmentIndex": 2, "assetPreference": "diagram", "durationFraction": 0.4, "transition": "cut"},
            ]
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("DURATION_FRACTION_SUM_INVALID" in e for e in errors)

    def test_duration_sum_over_one(self):
        plan = _base_fixture(
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 0.8, "transition": "cut"},
                {"segmentIndex": 2, "assetPreference": "diagram", "durationFraction": 0.8, "transition": "cut"},
            ]
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("DURATION_FRACTION_SUM_INVALID" in e for e in errors)

    def test_duration_fraction_zero(self):
        plan = _base_fixture(
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 0, "transition": "cut"},
            ]
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_DURATION_FRACTION:" in e for e in errors)

    def test_duration_fraction_negative(self):
        plan = _base_fixture(
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": -0.5, "transition": "cut"},
            ]
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_DURATION_FRACTION:" in e for e in errors)


# ── Cross-field consistency ─────────────────────────────────────────────────


class TestCrossFieldConsistency:
    def test_segment_preference_not_in_scene_preferences(self):
        plan = _base_fixture(
            assetPreferences=["diagram"],
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "photograph", "durationFraction": 1.0, "transition": "cut"},
            ],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("SEGMENT_PREFERENCE_NOT_ALLOWED" in e for e in errors)

    def test_segment_preference_in_scene_preferences_passes(self):
        plan = _base_fixture(
            assetPreferences=["diagram", "photograph"],
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "photograph", "durationFraction": 1.0, "transition": "cut"},
            ],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is True

    def test_generated_without_flag_fails(self):
        plan = _base_fixture(
            assetPreferences=["generated"],
            allowGeneratedImage=False,
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "generated", "durationFraction": 1.0, "transition": "cut"},
            ],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("GENERATED_ASSET_NOT_ALLOWED" in e for e in errors)

    def test_generated_with_flag_passes(self):
        plan = _base_fixture(
            assetPreferences=["generated"],
            allowGeneratedImage=True,
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "generated", "durationFraction": 1.0, "transition": "cut"},
            ],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is True

    def test_generated_in_segment_only_fails_without_flag(self):
        plan = _base_fixture(
            assetPreferences=["diagram", "generated"],
            allowGeneratedImage=False,
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "generated", "durationFraction": 1.0, "transition": "cut"},
            ],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("GENERATED_ASSET_NOT_ALLOWED" in e for e in errors)

    def test_image_prompt_without_flag_warns(self):
        plan = _base_fixture(
            imageGenerationPrompt="a beautiful landscape",
            allowGeneratedImage=False,
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is True
        warnings = [w["code"] for w in result["diagnostics"]["warnings"]]
        assert any("IMAGE_PROMPT_WITHOUT_GENERATION_FLAG" in w for w in warnings)

    def test_image_prompt_with_generated_preference_no_warning(self):
        plan = _base_fixture(
            assetPreferences=["generated"],
            allowGeneratedImage=True,
            imageGenerationPrompt="a landscape",
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "generated", "durationFraction": 1.0, "transition": "cut"},
            ],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is True
        warnings = [w["code"] for w in result["diagnostics"]["warnings"]]
        assert not any("IMAGE_PROMPT_WITHOUT_GENERATION_FLAG" in w for w in warnings)


# ── Canonicalization transformations ────────────────────────────────────────


class TestCanonicalizationTransformations:
    def test_whitespace_trimming(self):
        plan = _base_fixture(
            subjects=["  fotosíntesis  ", " cloroplasto"],
            searchQueries=["  photosynthesis diagram  "],
            period="  1789  ",
            location="  París  ",
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is True
        c = result["canonicalPlan"]
        assert c["subjects"] == ["fotosíntesis", "cloroplasto"]
        assert c["searchQueries"] == ["photosynthesis diagram"]
        assert c["period"] == "1789"
        assert c["location"] == "París"

    def test_empty_string_to_null(self):
        plan = _base_fixture(period="  ", location="")
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is True
        c = result["canonicalPlan"]
        assert c["period"] is None
        assert c["location"] is None

    def test_enum_lowercasing(self):
        plan = _base_fixture(
            visualIntent="EXPLAIN",
            assetPreferences=["DIAGRAM", "Illustration"],
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "DIAGRAM", "durationFraction": 1.0, "transition": "CUT"},
            ],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is True
        c = result["canonicalPlan"]
        assert c["visualIntent"] == "explain"
        assert c["assetPreferences"] == ["diagram", "illustration"]
        assert c["visualSequence"][0]["assetPreference"] == "diagram"
        assert c["visualSequence"][0]["transition"] == "cut"

    def test_provider_alias_wikimedia(self):
        plan = _base_fixture(preferredProviders=["wikimedia"])
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is True
        c = result["canonicalPlan"]
        assert c["preferredProviders"] == ["wikimedia_commons"]

    def test_duplicate_preferences_removed(self):
        plan = _base_fixture(
            assetPreferences=["diagram", "diagram", "photograph", "diagram"]
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is True
        c = result["canonicalPlan"]
        assert c["assetPreferences"] == ["diagram", "photograph"]

    def test_duplicate_preferences_preserves_first(self):
        plan = _base_fixture(
            assetPreferences=["photograph", "diagram", "photograph"]
        )
        result = canonicalize_visual_plan_v2(plan)
        c = result["canonicalPlan"]
        assert c["assetPreferences"] == ["photograph", "diagram"]

    def test_optional_defaults_applied(self):
        plan = {
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "show",
            "subjects": ["test"],
            "searchQueries": ["test"],
            "assetPreferences": ["photograph"],
            "visualSequence": [
                {"segmentIndex": 1, "assetPreference": "photograph", "durationFraction": 1.0},
            ],
        }
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is True
        c = result["canonicalPlan"]
        assert c["period"] is None
        assert c["location"] is None
        assert c["allowGeneratedImage"] is False
        assert c["preferredProviders"] == []
        assert c["imageGenerationPrompt"] is None
        assert c["negativePrompt"] is None

    def test_unknown_fields_preserved(self):
        plan = _base_fixture()
        plan["futureField"] = "retained"
        plan["anotherExtension"] = 42
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is True
        c = result["canonicalPlan"]
        assert c["futureField"] == "retained"
        assert c["anotherExtension"] == 42
        warnings = [w["code"] for w in result["diagnostics"]["warnings"]]
        assert any("UNKNOWN_FIELD:futureField" in w for w in warnings)
        assert any("UNKNOWN_FIELD:anotherExtension" in w for w in warnings)

    def test_segments_sorted_by_index(self):
        plan = _base_fixture(
            visualSequence=[
                {"segmentIndex": 3, "assetPreference": "diagram", "durationFraction": 0.3, "transition": "cut"},
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 0.4, "transition": "cut"},
                {"segmentIndex": 2, "assetPreference": "diagram", "durationFraction": 0.3, "transition": "cut"},
            ]
        )
        result = canonicalize_visual_plan_v2(plan)
        c = result["canonicalPlan"]
        indices = [s["segmentIndex"] for s in c["visualSequence"]]
        assert indices == [1, 2, 3]

    def test_provider_lowercased(self):
        plan = _base_fixture(preferredProviders=["Pexels", "PIXABAY"])
        result = canonicalize_visual_plan_v2(plan)
        c = result["canonicalPlan"]
        assert c["preferredProviders"] == ["pexels", "pixabay"]

    def test_unrecognized_provider_warns(self):
        plan = _base_fixture(preferredProviders=["unknown_provider"])
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is True
        warnings = [w["code"] for w in result["diagnostics"]["warnings"]]
        assert any("UNRECOGNIZED_PROVIDER" in w for w in warnings)


# ── Validate function ───────────────────────────────────────────────────────


class TestValidateFunction:
    def test_validate_valid_plan(self):
        result = validate_visual_plan_v2(_photosynthesis_plan())
        assert result["ok"] is True
        assert len(result["diagnostics"]["errors"]) == 0

    def test_validate_invalid_plan(self):
        plan = _base_fixture()
        del plan["subjects"]
        result = validate_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("REQUIRED_FIELD_MISSING:subjects" in e for e in errors)

    def test_validate_does_not_canonicalize(self):
        plan = _base_fixture(visualIntent="EXPLAIN")
        result = validate_visual_plan_v2(plan)
        assert result["ok"] is True


# ── All allowed enum values tested ──────────────────────────────────────────


class TestAllEnumValues:
    def test_all_visual_intents_accepted(self):
        for intent in ALLOWED_VISUAL_INTENTS:
            plan = _base_fixture(visualIntent=intent)
            result = canonicalize_visual_plan_v2(plan)
            assert result["ok"] is True, f"visualIntent='{intent}' should be accepted"

    def test_all_asset_preferences_accepted(self):
        for pref in ALLOWED_ASSET_PREFERENCES:
            overrides = {
                "assetPreferences": [pref],
                "visualSequence": [
                    {"segmentIndex": 1, "assetPreference": pref, "durationFraction": 1.0, "transition": "cut"},
                ],
            }
            if pref == "generated":
                overrides["allowGeneratedImage"] = True
            plan = _base_fixture(**overrides)
            result = canonicalize_visual_plan_v2(plan)
            assert result["ok"] is True, (
                f"assetPreference='{pref}' should be accepted: "
                f"{result['diagnostics'].get('errors', [])}"
            )

    def test_all_new_preferences_painting_map_document_accepted(self):
        for pref in ["painting", "map", "document"]:
            assert pref in ALLOWED_ASSET_PREFERENCES, f"'{pref}' should be in allowed asset preferences"
            plan = _base_fixture(
                assetPreferences=[pref],
                visualSequence=[
                    {"segmentIndex": 1, "assetPreference": pref, "durationFraction": 1.0, "transition": "fade"},
                ],
            )
            result = canonicalize_visual_plan_v2(plan)
            assert result["ok"] is True, f"assetPreference='{pref}' should be accepted"

    def test_all_transitions_accepted(self):
        for t in ALLOWED_TRANSITIONS:
            plan = _base_fixture(
                visualSequence=[
                    {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 1.0, "transition": t},
                ],
            )
            result = canonicalize_visual_plan_v2(plan)
            assert result["ok"] is True, f"transition='{t}' should be accepted"

    def test_all_providers_accepted(self):
        for prov in ALLOWED_PROVIDERS:
            plan = _base_fixture(preferredProviders=[prov])
            result = canonicalize_visual_plan_v2(plan)
            assert result["ok"] is True, f"provider='{prov}' should be accepted"


# ── Explicit: no legacy v1 fields inferred across all fixtures ──────────────


LEGACY_V1_FIELDS = [
    "editorialRole",
    "visualTemporalIntent",
    "strategy",
    "primaryAssetType",
    "secondaryAssetType",
    "style",
    "mood",
    "licenseRequired",
    "visualImportance",
]


class TestNoLegacyFieldsInferred:
    def test_photosynthesis_no_legacy(self):
        result = canonicalize_visual_plan_v2(_photosynthesis_plan())
        for field in LEGACY_V1_FIELDS:
            assert field not in result["canonicalPlan"], f"'{field}' inferred for photosynthesis"

    def test_blockchain_no_legacy(self):
        result = canonicalize_visual_plan_v2(_blockchain_plan())
        for field in LEGACY_V1_FIELDS:
            assert field not in result["canonicalPlan"], f"'{field}' inferred for blockchain"

    def test_octopus_no_legacy(self):
        result = canonicalize_visual_plan_v2(_octopus_plan())
        for field in LEGACY_V1_FIELDS:
            assert field not in result["canonicalPlan"], f"'{field}' inferred for octopus"

    def test_french_revolution_no_legacy(self):
        result = canonicalize_visual_plan_v2(_french_revolution_plan())
        for field in LEGACY_V1_FIELDS:
            assert field not in result["canonicalPlan"], f"'{field}' inferred for french_revolution"

    def test_marie_curie_no_legacy(self):
        result = canonicalize_visual_plan_v2(_marie_curie_plan())
        for field in LEGACY_V1_FIELDS:
            assert field not in result["canonicalPlan"], f"'{field}' inferred for marie_curie"

    def test_pomodoro_no_legacy(self):
        result = canonicalize_visual_plan_v2(_pomodoro_plan())
        for field in LEGACY_V1_FIELDS:
            assert field not in result["canonicalPlan"], f"'{field}' inferred for pomodoro"


# ── Field summary in diagnostics ────────────────────────────────────────────


class TestFieldSummary:
    def test_field_summary_present_count(self):
        result = canonicalize_visual_plan_v2(_photosynthesis_plan())
        summary = result["diagnostics"]["fieldSummary"]
        assert summary["present"] >= len(REQUIRED_FIELDS)

    def test_field_summary_has_missing_on_error(self):
        plan = _base_fixture()
        del plan["subjects"]
        result = canonicalize_visual_plan_v2(plan)
        summary = result["diagnostics"]["fieldSummary"]
        assert "subjects" in summary["missing"]

    def test_field_summary_has_unknown(self):
        plan = _base_fixture()
        plan["extraThing"] = "value"
        result = canonicalize_visual_plan_v2(plan)
        summary = result["diagnostics"]["fieldSummary"]
        assert "extraThing" in summary["unknown"]


# ── Case-insensitive cross-field success ─────────────────────────────────────


class TestCaseInsensitiveCrossField:
    def test_uppercase_scene_pref_matches_lowercase_segment(self):
        plan = _base_fixture(
            assetPreferences=["DIAGRAM", "Photograph"],
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 0.5, "transition": "cut"},
                {"segmentIndex": 2, "assetPreference": "photograph", "durationFraction": 0.5, "transition": "cut"},
            ],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is True

    def test_uppercase_generated_flag_true_matches(self):
        plan = _base_fixture(
            assetPreferences=["DIAGRAM", "GENERATED"],
            allowGeneratedImage=True,
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "generated", "durationFraction": 1.0, "transition": "cut"},
            ],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is True


# ── Segment field type validation ────────────────────────────────────────────


class TestSegmentTypeValidation:
    def test_asset_preference_non_string_fails(self):
        plan = _base_fixture(
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": 123, "durationFraction": 1.0, "transition": "cut"},
            ],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_FIELD_TYPE:visualSequence[0].assetPreference" in e for e in errors)

    def test_search_query_non_string_fails(self):
        plan = _base_fixture(
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 1.0, "searchQuery": 123, "transition": "cut"},
            ],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_FIELD_TYPE:visualSequence[0].searchQuery" in e for e in errors)

    def test_transition_non_string_fails(self):
        plan = _base_fixture(
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 1.0, "transition": 123},
            ],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_FIELD_TYPE:visualSequence[0].transition" in e for e in errors)

    def test_segment_index_bool_fails(self):
        plan = _base_fixture(
            visualSequence=[
                {"segmentIndex": True, "assetPreference": "diagram", "durationFraction": 1.0, "transition": "cut"},
            ],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_FIELD_TYPE:visualSequence[0].segmentIndex" in e for e in errors)

    def test_duration_fraction_bool_fails(self):
        plan = _base_fixture(
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": True, "transition": "cut"},
            ],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_FIELD_TYPE:visualSequence[0].durationFraction" in e for e in errors)

    def test_search_query_null_passes(self):
        plan = _base_fixture(
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 1.0, "searchQuery": None, "transition": "cut"},
            ],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is True


# ── Segment field length validation ──────────────────────────────────────────


class TestSegmentLengthValidation:
    def test_asset_preference_too_long_fails(self):
        long_pref = "x" * 101
        plan = _base_fixture(
            assetPreferences=[long_pref],
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": long_pref, "durationFraction": 1.0, "transition": "cut"},
            ],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("FIELD_TOO_LONG:visualSequence[0].assetPreference" in e for e in errors)

    def test_search_query_too_long_fails(self):
        long_query = "x" * 201
        plan = _base_fixture(
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 1.0, "searchQuery": long_query, "transition": "cut"},
            ],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("FIELD_TOO_LONG:visualSequence[0].searchQuery" in e for e in errors)

    def test_transition_too_long_fails(self):
        long_transition = "x" * 21
        plan = _base_fixture(
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 1.0, "transition": long_transition},
            ],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("FIELD_TOO_LONG:visualSequence[0].transition" in e for e in errors)


# ── List-item length limits ──────────────────────────────────────────────────


class TestListItemLengthLimits:
    def test_subject_too_long_fails(self):
        long_subject = "x" * 501
        plan = _base_fixture(subjects=[long_subject])
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("FIELD_TOO_LONG:subjects[0]" in e for e in errors)

    def test_search_query_item_too_long_fails(self):
        long_query = "x" * 201
        plan = _base_fixture(searchQueries=[long_query])
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("FIELD_TOO_LONG:searchQueries[0]" in e for e in errors)

    def test_asset_preference_item_too_long_fails(self):
        long_pref = "x" * 101
        plan = _base_fixture(
            assetPreferences=[long_pref],
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": long_pref, "durationFraction": 1.0, "transition": "cut"},
            ],
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("FIELD_TOO_LONG:assetPreferences[0]" in e for e in errors)

    def test_provider_too_long_fails(self):
        long_provider = "x" * 101
        plan = _base_fixture(preferredProviders=[long_provider])
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("FIELD_TOO_LONG:preferredProviders[0]" in e for e in errors)

    def test_subject_at_limit_passes(self):
        plan = _base_fixture(subjects=["x" * 500])
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is True


# ── Legacy v1 field rejection ────────────────────────────────────────────────


V1_LEGACY_FIELDS = [
    "editorialRole",
    "visualTemporalIntent",
    "strategy",
    "primaryAssetType",
    "secondaryAssetType",
    "style",
    "mood",
    "licenseRequired",
    "visualImportance",
]


class TestLegacyFieldRejection:
    def test_all_legacy_fields_rejected_individually(self):
        for field in V1_LEGACY_FIELDS:
            plan = _base_fixture(**{field: "any_value"})
            result = canonicalize_visual_plan_v2(plan)
            assert result["ok"] is False, f"field '{field}' should be rejected"
            errors = [e["code"] for e in result["diagnostics"]["errors"]]
            assert any(f"LEGACY_FIELD_NOT_ALLOWED:{field}" in e for e in errors), (
                f"expected LEGACY_FIELD_NOT_ALLOWED:{field} in errors: {errors}"
            )

    def test_canonical_plan_null_on_legacy_rejection(self):
        plan = _base_fixture(editorialRole="battle_or_assault")
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        assert result["canonicalPlan"] is None

    def test_ordinary_unknown_field_still_preserved_with_warning(self):
        plan = _base_fixture()
        plan["futureExtension"] = "kept"
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is True
        assert result["canonicalPlan"]["futureExtension"] == "kept"
        warnings = [w["code"] for w in result["diagnostics"]["warnings"]]
        assert any("UNKNOWN_FIELD:futureExtension" in w for w in warnings)

    def test_multiple_legacy_fields_rejected(self):
        plan = _base_fixture(
            editorialRole="context_map",
            strategy="historical_archive",
        )
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert sum("LEGACY_FIELD_NOT_ALLOWED" in e for e in errors) == 2

    def test_legacy_field_not_in_canonical_unknown_count(self):
        plan = _base_fixture()
        plan["editorialRole"] = "test"
        plan["genuineFuture"] = "retained"
        result = canonicalize_visual_plan_v2(plan)
        summary = result["diagnostics"]["fieldSummary"]
        assert "editorialRole" not in summary["unknown"]
        assert "genuineFuture" in summary["unknown"]


# ── Regression: all six fixtures still pass ──────────────────────────────────


class TestRegressionSixFixtures:
    def test_photosynthesis_fixture(self):
        result = canonicalize_visual_plan_v2(_photosynthesis_plan())
        assert result["ok"] is True
        plan = result["canonicalPlan"]
        assert plan["visualIntent"] == "explain"
        for field in V1_LEGACY_FIELDS:
            assert field not in plan

    def test_blockchain_fixture(self):
        result = canonicalize_visual_plan_v2(_blockchain_plan())
        assert result["ok"] is True
        for field in V1_LEGACY_FIELDS:
            assert field not in result["canonicalPlan"]

    def test_octopus_fixture(self):
        result = canonicalize_visual_plan_v2(_octopus_plan())
        assert result["ok"] is True
        for field in V1_LEGACY_FIELDS:
            assert field not in result["canonicalPlan"]

    def test_french_revolution_fixture(self):
        result = canonicalize_visual_plan_v2(_french_revolution_plan())
        assert result["ok"] is True
        for field in V1_LEGACY_FIELDS:
            assert field not in result["canonicalPlan"]

    def test_marie_curie_fixture(self):
        result = canonicalize_visual_plan_v2(_marie_curie_plan())
        assert result["ok"] is True
        for field in V1_LEGACY_FIELDS:
            assert field not in result["canonicalPlan"]

    def test_pomodoro_fixture(self):
        result = canonicalize_visual_plan_v2(_pomodoro_plan())
        assert result["ok"] is True
        for field in V1_LEGACY_FIELDS:
            assert field not in result["canonicalPlan"]
