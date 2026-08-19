"""Focused pure-contract tests for visual media strategy Slice 1."""

from __future__ import annotations

import inspect

import pytest

from shorts_creator.contracts.visual import (
    ALLOWED_MEDIA_PREFERENCES,
    canonicalize_visual_plan_v2,
)
from shorts_creator.contracts.visual_media import (
    AUTO,
    EITHER,
    IMAGE,
    IMAGE_PREFERRED,
    IMAGES_ONLY,
    MEDIA_PREFERENCE_OVERRIDDEN_BY_USER,
    MEDIA_PREFERENCE_UNAVAILABLE,
    MEDIA_PREFERENCE_UNSATISFIABLE_FOR_VISUAL_FORM,
    MIXED,
    VIDEO,
    VIDEO_PREFERRED,
    VIDEOS_ONLY,
    VISUAL_FORM_UNSUPPORTED_FOR_ALLOWED_MEDIA,
    normalize_visual_mode,
    resolve_media_strategy,
)


def _plan(media_preference: str | None = None) -> dict:
    segment = {
        "segmentIndex": 1,
        "assetPreference": "photograph",
        "durationFraction": 1.0,
    }
    if media_preference is not None:
        segment["mediaPreference"] = media_preference
    return {
        "_schemaVersion": 2,
        "visualIntent": "show",
        "subjects": ["test subject"],
        "searchQueries": ["test subject photograph"],
        "assetPreferences": ["photograph"],
        "visualSequence": [segment],
    }


def test_media_preference_enum_is_closed_contract():
    assert ALLOWED_MEDIA_PREFERENCES == {
        IMAGE_PREFERRED, VIDEO_PREFERRED, EITHER,
    }


def test_media_preference_canonicalizes_to_uppercase():
    result = canonicalize_visual_plan_v2(_plan("video_preferred"))
    assert result["ok"] is True
    assert result["canonicalPlan"]["visualSequence"][0]["mediaPreference"] == VIDEO_PREFERRED


def test_legacy_visual_plan_defaults_media_preference_to_image():
    result = canonicalize_visual_plan_v2(_plan())
    assert result["ok"] is True
    assert result["canonicalPlan"]["visualSequence"][0]["mediaPreference"] == IMAGE_PREFERRED


def test_invalid_media_preference_is_rejected():
    result = canonicalize_visual_plan_v2(_plan("ANIMATION_ONLY"))
    assert result["ok"] is False
    assert any(
        error["code"] == "INVALID_ENUM_VALUE:visualSequence[0].mediaPreference"
        for error in result["diagnostics"]["errors"]
    )


def test_provider_hint_remains_unknown_visual_plan_field():
    plan = _plan()
    plan["visualSequence"][0]["providerHint"] = "pexels"
    result = canonicalize_visual_plan_v2(plan)
    assert result["ok"] is True
    assert any(
        warning["code"] == "UNKNOWN_SEGMENT_FIELD:visualSequence[0].providerHint"
        for warning in result["diagnostics"]["warnings"]
    )


@pytest.mark.parametrize(
    ("request_visuals", "expected_mode", "expected_kinds", "mixed_preferred"),
    [
        ({"visualMode": AUTO}, AUTO, (IMAGE, VIDEO), False),
        ({"visualMode": MIXED}, MIXED, (IMAGE, VIDEO), True),
        ({"mode": "images"}, IMAGES_ONLY, (IMAGE,), False),
        ({}, IMAGES_ONLY, (IMAGE,), False),
        (None, IMAGES_ONLY, (IMAGE,), False),
    ],
)
def test_visual_mode_normalization(
    request_visuals, expected_mode, expected_kinds, mixed_preferred
):
    policy = normalize_visual_mode(request_visuals)
    assert policy.visual_mode == expected_mode
    assert policy.allowed_kinds == expected_kinds
    assert policy.mixed_diversity_preferred is mixed_preferred


def test_visual_mode_explicit_images_only_agrees_with_legacy_mode():
    policy = normalize_visual_mode({"mode": "images", "visualMode": "images_only"})
    assert policy.visual_mode == IMAGES_ONLY


def test_visual_mode_conflict_is_explicit():
    with pytest.raises(ValueError, match="VISUAL_MODE_CONFLICT"):
        normalize_visual_mode({"mode": "images", "visualMode": AUTO})


def test_mixed_is_best_effort_not_a_hard_both_kinds_requirement():
    policy = normalize_visual_mode({"visualMode": MIXED})
    decision = resolve_media_strategy(
        policy=policy,
        editorial_preference=IMAGE_PREFERRED,
        form_supported_kinds={IMAGE},
        runtime_available_kinds={IMAGE},
    )
    assert decision.resolved_kind == IMAGE
    assert decision.degradations == ()
    assert decision.unresolved is False


def test_case_a_mixed_photograph_prefers_video_with_image_fallback_allowed():
    decision = resolve_media_strategy(
        policy=normalize_visual_mode({"visualMode": MIXED}),
        editorial_preference=VIDEO_PREFERRED,
        form_supported_kinds={IMAGE, VIDEO},
        runtime_available_kinds={IMAGE, VIDEO},
    )
    assert decision.resolved_kind == VIDEO
    assert decision.allowed_kinds == (IMAGE, VIDEO)
    assert decision.preference_status == "PREFERRED"
    assert decision.degradations == ()


def test_case_b_images_only_overrides_video_preference():
    decision = resolve_media_strategy(
        policy=normalize_visual_mode({"visualMode": IMAGES_ONLY}),
        editorial_preference=VIDEO_PREFERRED,
        form_supported_kinds={IMAGE, VIDEO},
        runtime_available_kinds={IMAGE, VIDEO},
    )
    assert decision.resolved_kind == IMAGE
    assert decision.preference_status == "OVERRIDDEN_BY_USER"
    assert decision.degradations == (MEDIA_PREFERENCE_OVERRIDDEN_BY_USER,)


def test_case_c_video_preference_unsatisfiable_for_diagram_falls_back_to_image():
    decision = resolve_media_strategy(
        policy=normalize_visual_mode({"visualMode": MIXED}),
        editorial_preference=VIDEO_PREFERRED,
        form_supported_kinds={IMAGE},
        runtime_available_kinds={IMAGE, VIDEO},
    )
    assert decision.resolved_kind == IMAGE
    assert decision.preference_status == "FALLBACK_FOR_VISUAL_FORM"
    assert decision.degradations == (
        MEDIA_PREFERENCE_UNSATISFIABLE_FOR_VISUAL_FORM,
    )


def test_case_d_videos_only_diagram_is_unresolved():
    decision = resolve_media_strategy(
        policy=normalize_visual_mode({"visualMode": VIDEOS_ONLY}),
        editorial_preference=VIDEO_PREFERRED,
        form_supported_kinds={IMAGE},
        runtime_available_kinds={IMAGE, VIDEO},
    )
    assert decision.resolved_kind is None
    assert decision.unresolved is True
    assert decision.preference_status == "UNRESOLVED"
    assert decision.degradations == (VISUAL_FORM_UNSUPPORTED_FOR_ALLOWED_MEDIA,)


def test_runtime_unavailable_is_distinct_from_visual_form_mismatch():
    decision = resolve_media_strategy(
        policy=normalize_visual_mode({"visualMode": MIXED}),
        editorial_preference=VIDEO_PREFERRED,
        form_supported_kinds={IMAGE, VIDEO},
        runtime_available_kinds={IMAGE},
    )
    assert decision.resolved_kind == IMAGE
    assert decision.degradations == (MEDIA_PREFERENCE_UNAVAILABLE,)
    assert decision.form_supported_kinds == (IMAGE, VIDEO)
    assert decision.runtime_available_kinds == (IMAGE,)


def test_no_runtime_media_is_explicitly_unresolved():
    decision = resolve_media_strategy(
        policy=normalize_visual_mode({"visualMode": MIXED}),
        editorial_preference=VIDEO_PREFERRED,
        form_supported_kinds={IMAGE, VIDEO},
        runtime_available_kinds=set(),
    )
    assert decision.unresolved is True
    assert decision.degradations == (MEDIA_PREFERENCE_UNAVAILABLE,)


@pytest.mark.parametrize("invalid", [[], "", 0, False])
def test_falsy_non_mapping_visual_inputs_are_rejected(invalid):
    with pytest.raises(ValueError, match="INVALID_REQUEST_VISUALS"):
        normalize_visual_mode(invalid)


@pytest.mark.parametrize(
    ("form_kinds", "runtime_kinds", "error"),
    [({"ANIMATION"}, {IMAGE}, "INVALID_FORM_SUPPORTED_KINDS"),
     ({IMAGE}, {"ANIMATION"}, "INVALID_RUNTIME_AVAILABLE_KINDS")],
)
def test_invalid_media_kinds_are_rejected(form_kinds, runtime_kinds, error):
    with pytest.raises(ValueError, match=error):
        resolve_media_strategy(
            policy=normalize_visual_mode(None),
            editorial_preference=IMAGE_PREFERRED,
            form_supported_kinds=form_kinds,
            runtime_available_kinds=runtime_kinds,
        )


def test_visual_plan_uses_authoritative_media_preference_constant():
    from shorts_creator.contracts import visual
    import shorts_creator.contracts.visual_media as visual_media

    assert visual.ALLOWED_MEDIA_PREFERENCES is visual_media.ALLOWED_MEDIA_PREFERENCES


def test_media_strategy_module_is_import_safe_and_pure():
    import shorts_creator.contracts.visual_media as visual_media

    source = inspect.getsource(visual_media)
    assert "requests" not in source
    assert "urllib" not in source
    assert "os.getenv" not in source
