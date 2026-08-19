"""Focused tests for the static provider capability registry."""

from __future__ import annotations

import inspect

from shorts_creator.assets.capabilities import (
    AVAILABLE,
    CONDITIONAL_FIT,
    DIRECT,
    IMAGE,
    PROVIDER_CAPABILITIES,
    UNSUPPORTED,
    UNDECLARED,
    VIDEO,
    get_provider_capability,
    get_visual_form_fit,
)
from shorts_creator.contracts.visual_media import MEDIA_KINDS


def test_capability_ids_are_unique():
    ids = [capability.capability_id for capability in PROVIDER_CAPABILITIES]
    assert len(ids) == len(set(ids))


def test_pexels_photo_and_video_are_separate_capabilities():
    photos = get_provider_capability("pexels.photos.stock")
    video = get_provider_capability("pexels.video.stock")
    assert photos is not None
    assert video is not None
    assert photos.media_kind == IMAGE
    assert video.media_kind == VIDEO
    assert photos.capability_id != video.capability_id


def test_pexels_photos_and_video_are_runtime_available():
    pexels = [capability for capability in PROVIDER_CAPABILITIES if capability.provider == "pexels"]
    assert {capability.capability_id: capability.runtime_status for capability in pexels} == {
        "pexels.photos.stock": AVAILABLE,
        "pexels.video.stock": AVAILABLE,
    }
    assert {capability.evidence_version for capability in pexels} == {
        "pexels-provider-fit-benchmark"
    }


def test_pexels_form_fit_preserves_benchmark_semantics():
    photos = get_provider_capability("pexels.photos.stock")
    video = get_provider_capability("pexels.video.stock")
    assert photos is not None
    assert video is not None
    assert photos.visual_form_fit["photograph"] == DIRECT
    assert video.visual_form_fit["photograph"] == CONDITIONAL_FIT
    for form in ("diagram", "infographic", "illustration", "painting"):
        assert photos.visual_form_fit[form] == UNSUPPORTED
        assert video.visual_form_fit[form] == UNSUPPORTED


def test_current_available_capabilities_cover_image_and_video_stock_search():
    available = [
        capability
        for capability in PROVIDER_CAPABILITIES
        if capability.runtime_status == AVAILABLE
    ]
    assert {capability.provider for capability in available} == {
        "wikimedia_commons", "pixabay", "pexels",
    }
    assert {capability.media_kind for capability in available} == {IMAGE, VIDEO}


def test_missing_visual_form_fit_is_undeclared_not_unsupported():
    wikimedia = get_provider_capability("wikimedia_commons.image.stock")
    assert wikimedia is not None
    assert get_visual_form_fit(wikimedia, "photograph") == UNDECLARED
    assert UNDECLARED != UNSUPPORTED


def test_available_legacy_capabilities_are_not_excluded_by_empty_fit_maps():
    available = [
        capability for capability in PROVIDER_CAPABILITIES
        if capability.runtime_status == AVAILABLE
    ]
    legacy = [
        capability for capability in available
        if capability.provider in {"wikimedia_commons", "pixabay"}
    ]
    assert all(get_visual_form_fit(capability, "diagram") == UNDECLARED for capability in legacy)


def test_visual_form_fit_mapping_is_immutable():
    pexels = get_provider_capability("pexels.photos.stock")
    assert pexels is not None
    try:
        pexels.visual_form_fit["photograph"] = UNSUPPORTED
    except TypeError:
        pass
    else:
        raise AssertionError("visual_form_fit must not be mutable")


def test_capabilities_use_authoritative_media_kind_constants():
    import shorts_creator.assets.capabilities as capabilities

    assert capabilities.IMAGE == IMAGE
    assert capabilities.VIDEO == VIDEO
    assert capabilities.MEDIA_KINDS is MEDIA_KINDS


def test_registry_has_no_dynamic_runtime_or_secret_dependencies():
    import shorts_creator.assets.capabilities as capabilities

    source = inspect.getsource(capabilities)
    assert "os.getenv" not in source
    assert "load_dotenv" not in source
    assert "urllib" not in source
    assert "apiKey" not in source
