"""Focused tests for the static provider capability registry."""

from __future__ import annotations

import inspect

from shorts_creator.assets.capabilities import (
    AVAILABLE,
    CONDITIONAL_FIT,
    DIRECT,
    IMAGE,
    PLANNED,
    PROVIDER_CAPABILITIES,
    UNSUPPORTED,
    VIDEO,
    get_provider_capability,
)


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


def test_pexels_capabilities_are_planned_not_runtime_claims():
    pexels = [capability for capability in PROVIDER_CAPABILITIES if capability.provider == "pexels"]
    assert {capability.runtime_status for capability in pexels} == {PLANNED}
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


def test_current_available_capabilities_are_image_stock_search_only():
    available = [
        capability
        for capability in PROVIDER_CAPABILITIES
        if capability.runtime_status == AVAILABLE
    ]
    assert {capability.provider for capability in available} == {
        "wikimedia_commons", "pixabay",
    }
    assert {capability.media_kind for capability in available} == {IMAGE}


def test_registry_has_no_dynamic_runtime_or_secret_dependencies():
    import shorts_creator.assets.capabilities as capabilities

    source = inspect.getsource(capabilities)
    assert "os.getenv" not in source
    assert "load_dotenv" not in source
    assert "urllib" not in source
    assert "apiKey" not in source
