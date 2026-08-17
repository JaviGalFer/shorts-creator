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
    assert SEMANTIC_METHOD == "deterministic_anchor_coverage_v2"


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


# ── Replay regression: real Pixabay candidates from local cache ─────────────

# These are the eleven selected Pixabay hits from
# los-semantic-regression-20260817-200642.  Tags are copied verbatim from the
# local Pixabay cache entries identified by each pixabayId.
_REPLAY_FALSE_POSITIVES = (
    ("7647805", "YouTube logo image",
     "volkswagen, automobile, antique car, beetle, vw, car wallpapers, vw beetle, vehicle, dare, emblem, logo, vw logo, car, transport, traffic"),
    ("7718193", "early YouTube interface screenshot",
     "bellflower, campanula, bud, purple flower, grow, sprout, early spring, early bloomer, bud, bud, bud, bud, bud, sprout"),
    ("6055943", "famous early YouTubers photo",
     "plant, plum blossom, sunbeams, nature, early spring, japan"),
    ("7487173", "early YouTube vlogs image",
     "dawn, ocean, nature, sky, sunrise, sunset, landscape, early morning"),
    ("7510927", "early YouTube tutorials image",
     "city, buildings, sunrise, skyline, water, twilight, nature, cityscape, early morning, quiet"),
    ("5059830", "viral YouTube video screenshot",
     "online, meeting, virtual, skype, zoom, video, conference, videoconference, webinar, remote, working, work, from, home, computer, businesswoman, pointing, couch, laptop, blue computer, blue home, blue laptop, blue work, blue video, blue meeting, blue online, blue videos, blue zoom, blue conference, blue couch, video, webinar, webinar, webinar, webinar, webinar"),
    ("2673038", "YouTube comments section screenshot",
     "kiwi, fruit, half, cross section, seeds, kiwi seeds, green, fresh, ripe, organic, food, delicious, eat, healthy, cut out, close up, kiwi, kiwi, kiwi, kiwi, kiwi"),
    ("5355845", "YouTube influencers popular culture image",
     "cancel, social, company, culture, break up, pull back, support, media, crime, community, youtube, shame, resignation, video, influencer, movie star, cancel, cancel, cancel, cancel, cancel, youtube, youtube, shame, resignation, resignation, influencer"),
    ("4685942", "future of YouTube screenshot",
     "lyon, flower background, flower, pink, nature, flora, petal, purple, bokeh, flower wallpaper, beautiful flowers, screenshot"),
    ("5527726", "current popular YouTubers photo",
     "coastal, village, sea, cliffs, steep, tower house, colorful, nature, wharf, path, popular, tourist, destination"),
    ("998990", "social media subscribe follow image",
     "media, social media, apps, social network, facebook, symbols, digital, twitter, network, social networking, icon, communication, www, internet, networking, button, social, social media, social media, social media, social media, social media"),
)


def test_cached_replay_candidates_require_query_anchor_coverage():
    for pixabay_id, query, tags in _REPLAY_FALSE_POSITIVES:
        result = assess_candidate(
            _expected(query),
            {"provider": "pixabay", "pixabayId": pixabay_id, "tags": tags},
        )
        assert result["verdict"] == IRRELEVANT, pixabay_id
        assert result["score"] == 0, pixabay_id
        assert result["anchorTerms"], pixabay_id
        assert "anchorCoverage" in result
        assert "weakMatches" in result


def test_subjects_cannot_rescue_missing_query_anchor():
    result = assess_candidate(
        _expected(
            "YouTube logo image",
            ["YouTube logo", "pantalla de ordenador", "primeros videos"],
        ),
        {
            "provider": "pixabay",
            "pixabayId": "7647805",
            "tags": _REPLAY_FALSE_POSITIVES[0][2],
        },
    )
    assert result["verdict"] == IRRELEVANT
    assert result["matchedAnchors"] == []
    assert result["weakMatches"] == ["logo"]


def test_subjects_cannot_replace_an_anchorless_query():
    result = assess_candidate(
        _expected("early screenshot", ["YouTube comments"]),
        {"provider": "pixabay", "tags": "youtube, comments, screenshot"},
    )
    assert result["verdict"] == UNSCORABLE
    assert result["anchorTerms"] == []
    assert result["weakMatches"] == ["screenshot"]


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
