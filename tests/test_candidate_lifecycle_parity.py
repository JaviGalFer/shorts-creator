"""Candidate lifecycle adapter invariants without legacy equivalence claims."""

from __future__ import annotations

from shorts_creator.assets.candidates import ACCEPTED, EXHAUSTED, select_first_accepted
from shorts_creator.assets.executor import _native_to_candidate_envelope


def _native(provider: str, *, query: str) -> dict:
    candidate = {
        "provider": provider,
        "title": f"{query} candidate",
        "sourceUrl": f"https://example.test/{provider}/source",
        "fileUrl": f"https://example.test/{provider}/file.jpg",
        "license": "Test License",
        "author": "Test Author",
        "width": 1200,
        "height": 800,
        "mimeType": "image/jpeg",
        "queryUsed": query,
        "tags": query,
    }
    if provider == "pixabay":
        candidate["pixabayId"] = 42
    return candidate


def _select(envelopes):
    return select_first_accepted(
        envelopes,
        semantic_evaluator=lambda candidate: {
            "verdict": "IRRELEVANT" if candidate.query_used == "first" else "RELEVANT"
        },
        downloader=lambda candidate: None if candidate.query_used == "second" else "/tmp/final.jpg",
        visual_fidelity_evaluator=lambda candidate, path: (True, {"verdict": "ACCEPT"}),
        rejection_cleanup=lambda candidate, path: None,
        limit=20,
    )


def test_wikimedia_adapter_keeps_rank_undeclared():
    natives = [
        _native("wikimedia_commons", query="first"),
        _native("wikimedia_commons", query="second"),
        _native("wikimedia_commons", query="third"),
    ]
    envelopes = [
        _native_to_candidate_envelope(
            native, capability_id="wikimedia_commons.image.stock",
            query_texts=["first", "second", "third"], provider_rank=None,
        )
        for native in natives
    ]
    result = _select(envelopes)
    assert [attempt.candidate.query_used for attempt in result.attempts] == ["first", "second", "third"]
    assert result.selected is not None
    assert result.selected.candidate.query_used == "third"
    assert all(envelope.provider_rank is None for envelope in envelopes)


def test_pixabay_adapter_uses_final_discovery_stream_rank():
    natives = [
        _native("pixabay", query="first"),
        _native("pixabay", query="second"),
        _native("pixabay", query="third"),
    ]
    envelopes = [
        _native_to_candidate_envelope(
            native, capability_id="pixabay.image.stock",
            query_texts=["first", "second", "third"], provider_rank=index,
        )
        for index, native in enumerate(natives, start=1)
    ]
    result = _select(envelopes)
    assert result.selected is not None
    assert result.selected.status == ACCEPTED
    assert [envelope.provider_rank for envelope in envelopes] == [1, 2, 3]
    assert [attempt.candidate.query_used for attempt in result.attempts] == ["first", "second", "third"]


def test_pixabay_illustration_vector_final_stream_rank_is_unique():
    # The provider has already filtered/deduplicated its illustration and vector
    # sub-searches. Candidate rank is only the final stream position.
    final_pool = [
        _native("pixabay", query="illustration-a"),
        _native("pixabay", query="illustration-b"),
        _native("pixabay", query="vector-c"),
        _native("pixabay", query="vector-d"),
    ]
    envelopes = [
        _native_to_candidate_envelope(
            native,
            capability_id="pixabay.image.stock",
            query_texts=[native["queryUsed"] for native in final_pool],
            provider_rank=index,
        )
        for index, native in enumerate(final_pool, start=1)
    ]
    assert [envelope.provider_rank for envelope in envelopes] == [1, 2, 3, 4]


def test_exhausted_adapter_lifecycle_preserves_candidate_order():
    natives = [_native("wikimedia_commons", query="first"), _native("wikimedia_commons", query="second")]
    envelopes = [
        _native_to_candidate_envelope(
            native, capability_id="wikimedia_commons.image.stock",
            query_texts=["first", "second"], provider_rank=None,
        )
        for native in natives
    ]
    result = select_first_accepted(
        envelopes,
        semantic_evaluator=lambda candidate: {"verdict": "IRRELEVANT"},
        downloader=lambda candidate: "/tmp/never.jpg",
        visual_fidelity_evaluator=lambda candidate, path: (True, None),
        rejection_cleanup=lambda candidate, path: None,
        limit=20,
    )
    assert result.status == EXHAUSTED
    assert [attempt.candidate.query_used for attempt in result.attempts] == ["first", "second"]
