"""Mocked Slice 2 integration tests for Pexels Photos runtime wiring."""

from __future__ import annotations

from pathlib import Path
import sys
from unittest.mock import patch

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))

from shorts_creator.assets.bridge import apply_visual_assets_v2_to_metadata
from shorts_creator.assets.executor import _resolve_pexels_photos, execute_visual_sourcing_plan_v2
from shorts_creator.assets.providers.pexels import AUTH_ERROR, PexelsClientError, RATE_LIMITED
from shorts_creator.assets.providers.pexels_photos import map_photo_response, order_candidates_bm25
from shorts_creator.assets.router import build_visual_sourcing_plan_v2


def _photo(photo_id: int, alt: str = "castle stone photograph") -> dict:
    return {
        "id": photo_id, "width": 1800, "height": 2400,
        "url": f"https://www.pexels.com/photo/{photo_id}/",
        "photographer": "Ada", "photographer_url": "https://www.pexels.com/@ada",
        "photographer_id": 7, "alt": alt,
        "src": {
            "original": f"https://images.pexels.test/{photo_id}.jpg",
            "large2x": f"https://images.pexels.test/{photo_id}-large.jpg",
        },
    }


def _result(query: str, *photos: dict):
    return type("Result", (), {
        "status": "OK",
        "candidates": order_candidates_bm25(query, map_photo_response({"photos": list(photos)}, query).candidates),
        "telemetry": {"x-ratelimit-remaining": "99"},
    })()


def _segment(queries=None):
    return {
        "segmentIndex": 1, "assetPreference": "photograph", "subjects": [],
        "searchQueries": [{"text": text, "source": "segment.searchQuery"} for text in (queries or ["castle photograph"])],
    }


def _candidate():
    return {"provider": "pexels", "priority": 1, "queryStrategy": "search"}


def _download(candidate, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"image")
    return {"ok": True, "size": 5, "mimeType": "image/jpeg", "actualWidth": 1800, "actualHeight": 2400}


def _plan(asset_preference: str, source_providers=None):
    visuals = {} if source_providers is None else {"sourceProviders": source_providers}
    return build_visual_sourcing_plan_v2({
        "visualSequence": [{"segmentIndex": 1, "assetPreference": asset_preference, "searchQuery": "castle photograph"}],
        "searchQueries": ["castle photograph"], "subjects": [],
    }, request_visuals=visuals)


def test_router_requires_explicit_opt_in_and_preserves_order():
    omitted = _plan("photograph")["sourcingPlan"]["segments"][0]
    assert "pexels" not in [item["provider"] for item in omitted["providerCandidates"]]
    explicit = _plan("photograph", ["pexels", "wikimedia_commons", "pixabay"])["sourcingPlan"]["segments"][0]
    assert [item["provider"] for item in explicit["providerCandidates"]] == ["pexels", "wikimedia_commons", "pixabay"]
    reversed_order = _plan("photograph", ["wikimedia_commons", "pexels"])["sourcingPlan"]["segments"][0]
    assert [item["provider"] for item in reversed_order["providerCandidates"]] == ["wikimedia_commons", "pexels"]


def test_router_excludes_pexels_for_non_photographic_forms():
    for form in ("diagram", "infographic", "illustration", "painting"):
        segment = _plan(form, ["pexels", "wikimedia_commons"])["sourcingPlan"]["segments"][0]
        assert "pexels" not in [item["provider"] for item in segment["providerCandidates"]]
        excluded = {item["provider"]: item["exclusionReason"] for item in segment["excludedProviders"]}
        assert "pexels" in excluded


def test_pexels_lifecycle_progresses_through_all_gates(tmp_path):
    query = "castle photograph"
    search_result = _result(query, _photo(1), _photo(2), _photo(3), _photo(4))
    seen = []

    def semantic(_segment, native):
        photo_id = native["pexelsPhotoId"]
        seen.append(("semantic", photo_id))
        return {"verdict": "IRRELEVANT" if photo_id == "1" else "RELEVANT"}

    def download(native, path):
        photo_id = native["pexelsPhotoId"]
        seen.append(("download", photo_id))
        if photo_id == "2":
            return {"ok": False, "error": "failed"}
        return _download(native, path)

    def fidelity(path, _query, _warnings):
        photo_id = path.stem.split("_")[-1] if "_" in path.stem else "3"
        seen.append(("pixel", photo_id))
        return (len([event for event in seen if event[0] == "pixel"]) > 1, {"status": "SCORED", "verdict": "REJECT"})

    with patch("shorts_creator.assets.providers.pexels_photos.search_pexels_photos", return_value=search_result), patch(
        "shorts_creator.assets.providers.pixabay.download_pixabay_asset_v2", side_effect=download,
    ), patch("shorts_creator.assets.executor._evaluate_semantic", side_effect=semantic), patch(
        "shorts_creator.assets.executor._apply_visual_fidelity_gate", side_effect=fidelity,
    ):
        result = _resolve_pexels_photos(_candidate(), _segment(), {}, str(tmp_path), [], provider_credentials={"pexels": {"apiKey": "secret"}})
    assert result["status"] == "RESOLVED"
    assert result["pexelsPhotoId"] == "4"
    assert result["providerRank"] == 4
    assert result["pexelsQueryRank"] == 4
    assert result["selectorIdentity"] == "PROVISIONAL_BM25"
    assert (tmp_path / "assets" / "seg_001.jpg").exists()  # final accepted replacement


def test_pexels_multi_query_ranks_are_raw_local_and_stream_global(tmp_path):
    first = _result("first castle", _photo(1, "unrelated"), _photo(2, "unrelated two"))
    second = _result("second castle", _photo(3, "second castle"), _photo(4, "second castle wall"))
    with patch("shorts_creator.assets.providers.pexels_photos.search_pexels_photos", side_effect=[first, second]), patch(
        "shorts_creator.assets.executor._evaluate_semantic",
        side_effect=lambda _segment, native: {"verdict": "RELEVANT" if native["queryUsed"] == "second castle" else "IRRELEVANT"},
    ), patch("shorts_creator.assets.providers.pixabay.download_pixabay_asset_v2", side_effect=_download), patch(
        "shorts_creator.assets.executor._apply_visual_fidelity_gate", return_value=(True, {"status": "DISABLED", "verdict": "BYPASS"}),
    ):
        result = _resolve_pexels_photos(_candidate(), _segment(["first castle", "second castle"]), {}, str(tmp_path), [], provider_credentials={"pexels": {"apiKey": "secret"}})
    assert result["status"] == "RESOLVED"
    assert result["queryIndex"] == 1
    assert result["pexelsQueryRank"] == 1
    assert result["providerRank"] == 3


def test_pexels_no_results_and_provider_errors_allow_explicit_fallback(tmp_path):
    plan = {
        "schemaVersion": 1,
        "segments": [{**_segment(), "generationPrompts": [], "providerCandidates": [
            _candidate(), {"provider": "wikimedia_commons", "priority": 2, "queryStrategy": "search"},
        ], "excludedProviders": [], "routingStatus": "ROUTABLE"}],
        "summary": {},
    }
    config = {
        "pexels": {"enabled": True, "implemented": True, "requiresApiKey": True, "apiKeyPresent": True},
        "wikimedia_commons": {"enabled": True, "implemented": True, "requiresApiKey": False, "live": True},
    }
    fallback = {"segmentIndex": 1, "assetPreference": "photograph", "status": "RESOLVED", "provider": "wikimedia_commons", "semanticAssessment": {"verdict": "RELEVANT"}}
    with patch("shorts_creator.assets.executor._resolve_pexels_photos", return_value={
        "segmentIndex": 1, "assetPreference": "photograph", "status": "NO_RESULTS", "provider": "pexels", "reason": "NO_RESULTS",
    }), patch("shorts_creator.assets.executor._resolve_wikimedia", return_value=fallback):
        result = execute_visual_sourcing_plan_v2(plan, config, dry_run=False, job_dir=str(tmp_path), provider_credentials={"pexels": {"apiKey": "secret"}})
    assert result["resolvedAssets"][0]["provider"] == "wikimedia_commons"
    assert [item["provider"] for item in result["resolvedAssets"][0]["providerAttempts"]] == ["pexels", "wikimedia_commons"]


def test_pexels_auth_rate_and_missing_key_are_safe(tmp_path):
    for error, code in ((PexelsClientError(AUTH_ERROR, "auth"), AUTH_ERROR), (PexelsClientError(RATE_LIMITED, "rate"), RATE_LIMITED)):
        with patch("shorts_creator.assets.providers.pexels_photos.search_pexels_photos", side_effect=error):
            result = _resolve_pexels_photos(_candidate(), _segment(), {}, str(tmp_path), [], provider_credentials={"pexels": {"apiKey": "secret"}})
        assert result["status"] == "PROVIDER_ERROR"
        assert result["reason"] == code
        assert "secret" not in repr(result)
    missing = _resolve_pexels_photos(_candidate(), _segment(), {}, str(tmp_path), [], provider_credentials={})
    assert missing["status"] == "MISSING_API_KEY"
    assert "secret" not in repr(missing)


def test_bridge_persists_pexels_primitives_without_changing_existing_shape():
    metadata = {"script": {"scenes": [{"sceneNumber": 1, "visualPlan": {"visualSequence": [{"segmentIndex": 1}]}}]}}
    resolved = {
        "sceneNumber": 1, "segmentIndex": 1, "assetPreference": "photograph", "provider": "pexels",
        "assetPath": "assets/one.jpg", "sourceUrl": "https://www.pexels.com/photo/1/", "fileUrl": "https://images.test/1.jpg",
        "author": "Ada", "authorUrl": "https://www.pexels.com/@ada", "mimeType": "image/jpeg", "width": 1, "height": 1,
        "searchQueryUsed": "castle", "capabilityId": "pexels.photos.stock", "providerAssetId": "1", "pexelsPhotoId": "1",
        "queryIndex": 0, "pexelsQueryRank": 2, "providerRank": 1, "selectorIdentity": "PROVISIONAL_BM25", "selectorScore": 0.5,
        "pexelsRateLimitTelemetry": {"x-ratelimit-remaining": "99"},
    }
    segment = apply_visual_assets_v2_to_metadata(metadata, {"resolvedAssets": [resolved], "unresolvedSegments": []})["assets"][0]["segments"][0]
    assert segment["authorUrl"] == "https://www.pexels.com/@ada"
    assert segment["pexelsQueryRank"] == 2
    assert segment["providerRank"] == 1
    assert segment["selectorIdentity"] == "PROVISIONAL_BM25"
    assert "secret" not in repr(segment)
