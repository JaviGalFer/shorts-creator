"""Tests for pure CandidateEnvelope and selection contracts."""

from __future__ import annotations

import math

import pytest

from shorts_creator.assets.candidates import (
    ACCEPTED,
    ADAPTED,
    CandidateAttribution,
    CandidateAttempt,
    CandidateEnvelope,
    CandidateSelectionResult,
    CandidateSemanticMetadata,
    DOWNLOAD_FAILED,
    EXHAUSTED,
    METADATA_REJECTED,
    PIXEL_REJECTED,
    RAW,
    SELECTED,
    select_first_accepted,
    take_top_n,
)
from shorts_creator.contracts.visual_media import IMAGE


def _candidate(**overrides):
    values = {
        "capability_id": "wikimedia_commons.image.stock",
        "provider": "wikimedia_commons",
        "provider_asset_id": None,
        "media_kind": IMAGE,
        "source_type": "STOCK",
        "query_used": "castle photograph",
        "query_variant": RAW,
        "query_index": 0,
        "provider_rank": 1,
        "provider_score": None,
        "semantic_metadata": CandidateSemanticMetadata(
            title="Castle", tags=("castle",), labels=("medieval",),
        ),
        "source_url": "https://example.test/source",
        "preview_url": "https://example.test/preview",
        "acquisition_url": "https://example.test/file.jpg",
        "mime_type": "image/jpeg",
        "width": 1200,
        "height": 800,
        "attribution": CandidateAttribution(author="Author", license="CC BY"),
    }
    values.update(overrides)
    return CandidateEnvelope(**values)


@pytest.mark.parametrize(
    "candidate",
    [
        _candidate(),
        _candidate(provider="pixabay", capability_id="pixabay.image.stock", provider_asset_id="42"),
        _candidate(provider="pexels", capability_id="pexels.photos.stock", provider_asset_id="123", provider_rank=3),
    ],
)
def test_stock_candidate_envelopes_are_valid(candidate):
    assert candidate.source_type == "STOCK"


@pytest.mark.parametrize("source_type", ["GENERATED", "MANUAL"])
def test_generated_and_manual_candidates_need_no_provider_or_capability(source_type):
    candidate = _candidate(
        source_type=source_type,
        provider=None,
        capability_id=None,
        provider_asset_id=None,
        query_variant=None,
    )
    assert candidate.provider is None
    assert candidate.capability_id is None


@pytest.mark.parametrize("overrides", [{"provider": None}, {"capability_id": None}])
def test_stock_candidate_requires_provider_and_capability(overrides):
    with pytest.raises(ValueError, match="STOCK_CANDIDATE_REQUIRES"):
        _candidate(**overrides)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("provider_rank", 0, "INVALID_PROVIDER_RANK"),
        ("provider_rank", -1, "INVALID_PROVIDER_RANK"),
        ("query_index", -1, "INVALID_QUERY_INDEX"),
        ("width", 0, "INVALID_WIDTH"),
        ("height", -1, "INVALID_HEIGHT"),
        ("provider_score", math.nan, "INVALID_PROVIDER_SCORE"),
        ("provider_score", math.inf, "INVALID_PROVIDER_SCORE"),
        ("query_variant", "DERIVED", "INVALID_QUERY_VARIANT"),
    ],
)
def test_candidate_validation(field, value, error):
    with pytest.raises(ValueError, match=error):
        _candidate(**{field: value})


def test_query_variant_is_closed_and_adapted_is_valid():
    assert _candidate(query_variant=ADAPTED).query_variant == ADAPTED


def test_optional_provider_asset_id_is_supported():
    assert _candidate(provider_asset_id=None).provider_asset_id is None


def test_attempt_assessments_are_defensively_immutable():
    assessment = {"nested": {"score": 1}, "items": ["a"]}
    attempt = CandidateAttempt(
        candidate=_candidate(), status=METADATA_REJECTED,
        semantic_assessment=assessment,
    )
    assessment["nested"]["score"] = 2
    with pytest.raises(TypeError):
        attempt.semantic_assessment["nested"] = "changed"
    assert attempt.semantic_assessment["nested"]["score"] == 1


def test_selection_attempts_preserve_order_and_selected_invariant():
    first = CandidateAttempt(candidate=_candidate(provider_rank=1), status=METADATA_REJECTED)
    second = CandidateAttempt(candidate=_candidate(provider_rank=2), status=ACCEPTED)
    result = CandidateSelectionResult(SELECTED, second, [first, second])
    assert result.attempts == (first, second)
    assert result.selected is second


@pytest.mark.parametrize(
    "status, selected, attempts, error",
    [
        (SELECTED, None, (), "INVALID_SELECTED_CANDIDATE"),
        (EXHAUSTED, CandidateAttempt(_candidate(), ACCEPTED), (), "EXHAUSTED_SELECTION"),
        (SELECTED, CandidateAttempt(_candidate(), METADATA_REJECTED), (), "INVALID_SELECTED_CANDIDATE"),
    ],
)
def test_selection_result_invariants(status, selected, attempts, error):
    with pytest.raises(ValueError, match=error):
        CandidateSelectionResult(status, selected, attempts)


def test_exhausted_selection_has_no_selected_candidate():
    result = CandidateSelectionResult(EXHAUSTED, None, ())
    assert result.selected is None


def test_top_n_preserves_discovery_order_without_score_sorting():
    candidates = [
        _candidate(provider_rank=1, provider_score=0.1),
        _candidate(provider_rank=2, provider_score=0.9),
        _candidate(provider_rank=3, provider_score=0.5),
    ]
    assert take_top_n(candidates, 2) == tuple(candidates[:2])


def test_top_n_consumes_only_the_requested_generator_items():
    consumed: list[int] = []

    def source():
        for rank in range(1, 5):
            consumed.append(rank)
            yield _candidate(provider_rank=rank)

    selected = take_top_n(source(), 3)
    assert [candidate.provider_rank for candidate in selected] == [1, 2, 3]
    assert consumed == [1, 2, 3]


@pytest.mark.parametrize("limit", [0, -1, True, "3"])
def test_top_n_rejects_invalid_limit(limit):
    with pytest.raises(ValueError, match="INVALID_CANDIDATE_LIMIT"):
        take_top_n([_candidate()], limit)


def test_candidate_contract_module_is_import_safe():
    import inspect
    import shorts_creator.assets.candidates as candidates

    source = inspect.getsource(candidates)
    assert "urllib" not in source
    assert "requests" not in source
    assert "os.getenv" not in source


def test_lifecycle_rejections_progress_without_unnecessary_downloads():
    candidates = [_candidate(provider_rank=1), _candidate(provider_rank=2), _candidate(provider_rank=3)]
    events: list[str] = []

    def semantic(candidate):
        events.append(f"semantic:{candidate.provider_rank}")
        return {"verdict": "IRRELEVANT" if candidate.provider_rank == 1 else "RELEVANT"}

    def download(candidate):
        events.append(f"download:{candidate.provider_rank}")
        return None if candidate.provider_rank == 2 else "/tmp/third.jpg"

    def fidelity(candidate, path):
        events.append(f"fidelity:{candidate.provider_rank}")
        return True, {"verdict": "ACCEPT"}

    result = select_first_accepted(
        candidates,
        semantic_evaluator=semantic,
        downloader=download,
        visual_fidelity_evaluator=fidelity,
        rejection_cleanup=lambda candidate, path: events.append("cleanup"),
        limit=3,
    )
    assert result.status == SELECTED
    assert [attempt.status for attempt in result.attempts] == [
        METADATA_REJECTED, DOWNLOAD_FAILED, ACCEPTED,
    ]
    assert events == [
        "semantic:1", "semantic:2", "download:2", "semantic:3", "download:3", "fidelity:3",
    ]


def test_lifecycle_pixel_reject_cleans_up_and_exhaustion_preserves_order():
    first = _candidate(provider_rank=1)
    second = _candidate(provider_rank=2)
    cleanup: list[str] = []
    result = select_first_accepted(
        [first, second],
        semantic_evaluator=lambda candidate: {"verdict": "RELEVANT"},
        downloader=lambda candidate: f"/tmp/{candidate.provider_rank}.jpg",
        visual_fidelity_evaluator=lambda candidate, path: (False, {"verdict": "REJECT"}),
        rejection_cleanup=lambda candidate, path: cleanup.append(path),
        limit=2,
    )
    assert result.status == EXHAUSTED
    assert [attempt.status for attempt in result.attempts] == [PIXEL_REJECTED, PIXEL_REJECTED]
    assert cleanup == ["/tmp/1.jpg", "/tmp/2.jpg"]


def test_lifecycle_stops_consuming_after_first_accepted_and_propagates_exceptions():
    consumed: list[int] = []

    def source():
        for rank in range(1, 4):
            consumed.append(rank)
            yield _candidate(provider_rank=rank)

    result = select_first_accepted(
        source(),
        semantic_evaluator=lambda candidate: {"verdict": "RELEVANT"},
        downloader=lambda candidate: "/tmp/one.jpg",
        visual_fidelity_evaluator=lambda candidate, path: (True, {"verdict": "ACCEPT"}),
        rejection_cleanup=lambda candidate, path: None,
        limit=3,
    )
    assert result.status == SELECTED
    assert consumed == [1]

    with pytest.raises(RuntimeError, match="provider failure"):
        select_first_accepted(
            [_candidate()],
            semantic_evaluator=lambda candidate: (_ for _ in ()).throw(RuntimeError("provider failure")),
            downloader=lambda candidate: None,
            visual_fidelity_evaluator=lambda candidate, path: (True, None),
            rejection_cleanup=lambda candidate, path: None,
            limit=1,
        )
