"""Tests for provider-agnostic semantic relevance (asset-semantic-relevance, Slice 1)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path("/home/javi/projects/shorts-creator") / "bin"))

from shorts_creator.assets.semantic import (
    RELEVANT,
    IRRELEVANT,
    UNSCORABLE,
    SEMANTIC_METHOD,
    GENERIC_FILLER,
    CONTRACT_KEYS,
    PROVIDER_ADAPTERS,
    to_semantic_candidate,
    tokenize,
    score_semantic_relevance,
    assess_candidate,
)


def _expected(query="", subjects=None):
    return {"query": query, "subjects": subjects or []}


def test_constants():
    assert RELEVANT == "RELEVANT"
    assert IRRELEVANT == "IRRELEVANT"
    assert UNSCORABLE == "UNSCORABLE"
    assert SEMANTIC_METHOD == "deterministic_token_overlap_v1"


# ── Positive controls: truly relevant metadata scores RELEVANT ─────────────


def test_youtube_relevant():
    cand = to_semantic_candidate({
        "provider": "wikimedia_commons",
        "title": "YouTube video studio overview",
        "description": "recording room with camera and lights",
    })
    result = score_semantic_relevance(_expected("YouTube"), cand)
    assert result["verdict"] == RELEVANT
    assert result["score"] is not None and result["score"] >= 60
    assert "youtube" in result["matchedEvidence"]


def test_rainbow_relevant():
    cand = to_semantic_candidate({
        "provider": "pixabay",
        "tags": "rainbow, sky, clouds, weather",
    })
    result = score_semantic_relevance(_expected("rainbow"), cand)
    assert result["verdict"] == RELEVANT
    assert "rainbow" in result["matchedEvidence"]


def test_rainbow_formation_full_query_relevant():
    cand = to_semantic_candidate({
        "provider": "pixabay",
        "tags": "rainbow, arch, after rain, sky",
    })
    result = score_semantic_relevance(_expected("rainbow formation illustration"), cand)
    assert result["verdict"] == RELEVANT
    assert "rainbow" in result["matchedEvidence"]


def test_youtube_logo_full_query_relevant():
    cand = to_semantic_candidate({
        "provider": "wikimedia_commons",
        "title": "YouTube logo on a dark background",
        "description": "youtube brand emblem",
    })
    result = score_semantic_relevance(_expected("YouTube logo image"), cand)
    assert result["verdict"] == RELEVANT
    assert "youtube" in result["matchedEvidence"]


def test_prism_relevant():
    cand = to_semantic_candidate({
        "provider": "wikimedia_commons",
        "title": "Triangular prism refracting light",
        "description": "glass prism spectrum",
    })
    result = score_semantic_relevance(_expected("prism"), cand)
    assert result["verdict"] == RELEVANT


# ── Regression negatives: unrelated evidence → IRRELEVANT ──────────────────


def test_volkswagen_irrelevant_for_youtube_logo_image():
    cand = to_semantic_candidate({
        "provider": "wikimedia_commons",
        "title": "Volkswagen Beetle parked on a street",
        "description": "classic german car",
    })
    result = score_semantic_relevance(_expected("YouTube logo image"), cand)
    assert result["verdict"] == IRRELEVANT
    assert result["score"] == 0
    assert result["matchedEvidence"] == []


def test_kiwi_irrelevant_for_youtube_comments_screenshot():
    cand = to_semantic_candidate({
        "provider": "pixabay",
        "tags": "kiwi, fruit, healthy, food",
    })
    result = score_semantic_relevance(_expected("YouTube comments section screenshot"), cand)
    assert result["verdict"] == IRRELEVANT


def test_flower_irrelevant_for_famous_early_youtubers():
    cand = to_semantic_candidate({
        "provider": "wikimedia_commons",
        "title": "Pink plum blossom flowers",
        "description": "garden flower petals in bloom",
    })
    result = score_semantic_relevance(_expected("famous early YouTubers photo"), cand)
    assert result["verdict"] == IRRELEVANT


def test_pride_irrelevant_for_rainbow_formation_illustration():
    cand = to_semantic_candidate({
        "provider": "pixabay",
        "tags": "pride, flag, community, event",
    })
    result = score_semantic_relevance(_expected("rainbow formation illustration"), cand)
    assert result["verdict"] == IRRELEVANT


# ── UNSCORABLE: missing substantive evidence on either side ────────────────


def test_unscorable_no_candidate_evidence():
    cand = to_semantic_candidate({
        "provider": "wikimedia_commons",
        "title": "Image",
    })
    result = score_semantic_relevance(_expected("YouTube"), cand)
    assert result["verdict"] == UNSCORABLE
    assert result["score"] is None


def test_unscorable_no_expected_intent():
    cand = to_semantic_candidate({
        "provider": "wikimedia_commons",
        "title": "Volkswagen Beetle",
    })
    result = score_semantic_relevance(_expected(""), cand)
    assert result["verdict"] == UNSCORABLE


def test_unscorable_when_both_empty():
    result = score_semantic_relevance(_expected(""), to_semantic_candidate({}))
    assert result["verdict"] == UNSCORABLE


# ── Normalization / adapters ───────────────────────────────────────────────


def test_to_semantic_candidate_pixabay_tags_normalized_to_list():
    sem = to_semantic_candidate({
        "provider": "pixabay",
        "tags": "rainbow, sky, clouds",
    })
    assert "rainbow" in sem["tags"]
    assert "sky" in sem["tags"]
    assert isinstance(sem["tags"], list)


def test_to_semantic_candidate_wikimedia_labels_from_filename():
    sem = to_semantic_candidate({
        "provider": "wikimedia_commons",
        "title": "Rainbow arch",
        "fileUrl": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Rainbow_arch.jpg",
    })
    combined = [s for s in sem["labels"]]
    assert any("rainbow" in s.lower() for s in combined)


def test_provider_adapters_no_unknown_provider_crash():
    sem = to_semantic_candidate({"provider": "some_future_provider", "title": "A thing", "description": "desc"})
    assert sem["provider"] == "some_future_provider"


def test_to_semantic_candidate_non_dict():
    sem = to_semantic_candidate("not a dict")
    assert not sem["title"]
    assert sem["tags"] == []


def test_tokenize_removes_generic_filler():
    tokens = tokenize("free high quality stock photo of a rainbow")
    assert "rainbow" in tokens
    assert "photo" not in tokens
    assert "stock" not in tokens
    assert "free" not in tokens


def test_contract_keys_shape():
    sem = to_semantic_candidate({})
    assert set(CONTRACT_KEYS) == set(sem.keys())


def test_assess_candidate_one_shot_endpoint():
    result = assess_candidate(
        _expected("YouTube"),
        {"provider": "wikimedia_commons", "title": "YouTube studio setup"},
    )
    assert result["verdict"] == RELEVANT
    assert result["method"] == SEMANTIC_METHOD