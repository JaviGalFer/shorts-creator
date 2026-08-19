"""Offline parity evidence for native image candidates and envelope lifecycle."""

from __future__ import annotations

from shorts_creator.assets.candidates import ACCEPTED, EXHAUSTED, select_first_accepted
from shorts_creator.assets.executor import _native_to_candidate_envelope


def _native(provider: str, *, query: str, rank: int | None = None) -> dict:
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
        candidate["providerRank"] = rank
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


def test_wikimedia_adapter_preserves_native_progression_without_inventing_rank():
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


def test_pixabay_adapter_preserves_hit_order_and_provider_ranks():
    natives = [
        _native("pixabay", query="first", rank=1),
        _native("pixabay", query="second", rank=2),
        _native("pixabay", query="third", rank=3),
    ]
    envelopes = [
        _native_to_candidate_envelope(
            native, capability_id="pixabay.image.stock",
            query_texts=["first", "second", "third"], provider_rank=native["providerRank"],
        )
        for native in natives
    ]
    result = _select(envelopes)
    assert result.selected is not None
    assert result.selected.status == ACCEPTED
    assert [envelope.provider_rank for envelope in envelopes] == [1, 2, 3]
    assert [attempt.candidate.query_used for attempt in result.attempts] == ["first", "second", "third"]


def test_exhausted_native_and_envelope_lifecycle_have_same_candidate_order():
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
