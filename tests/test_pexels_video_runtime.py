"""Mocked Slice 1 tests for Pexels Video asset runtime. No network."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import urllib.error
from unittest.mock import patch

from shorts_creator.assets.bridge import apply_visual_assets_v2_to_metadata
from shorts_creator.assets.capabilities import PLANNED, get_provider_capability
from shorts_creator.assets.executor import _apply_visual_fidelity_gate, _resolve_pexels_videos, _search_semantic_ok, execute_visual_sourcing_plan_v2
from shorts_creator.assets.providers.pexels_videos import (
    PexelsVideoSearchResult,
    descriptive_video_slug,
    download_pexels_video,
    map_video_response,
)
from shorts_creator.assets.router import build_visual_sourcing_plan_v2
from shorts_creator.contracts.visual_media import VIDEO


def _file(file_id: int, width: int = 1080, height: int = 1920, **overrides) -> dict:
    value = {"id": file_id, "quality": "hd", "file_type": "video/mp4", "width": width, "height": height, "fps": 30.0, "link": f"https://cdn.test/{file_id}.mp4"}
    value.update(overrides)
    return value


def _video(video_id: int = 1, **overrides) -> dict:
    value = {
        "id": video_id, "width": 1080, "height": 1920,
        "url": "https://www.pexels.com/video/water-crashing-over-the-rocks-1093662/",
        "image": "https://images.test/preview.jpg", "duration": 12.5,
        "tags": ["water", "rocks"], "user": {"id": 7, "name": "Ada", "url": "https://www.pexels.com/@ada"},
        "video_files": [_file(11)], "video_pictures": [],
    }
    value.update(overrides)
    return value


def _planned_video_capability(capability_id: str):
    capability = get_provider_capability(capability_id)
    if capability and capability_id == "pexels.video.stock":
        return replace(capability, runtime_status=PLANNED)
    return capability


def _plan(mode: str, preference: str = "VIDEO_PREFERRED", form: str = "photograph") -> dict:
    return {
        "visualSequence": [{"segmentIndex": 1, "assetPreference": form, "mediaPreference": preference, "searchQuery": "water rocks photograph"}],
        "searchQueries": ["water rocks photograph"], "subjects": [],
    }


def test_video_adapter_maps_raw_order_slug_tags_and_provenance():
    result = map_video_response({"videos": [_video(9)]}, "water rocks photograph")
    candidate = result.candidates[0]
    assert candidate.pexels_query_rank == 1
    assert candidate.envelope.media_kind == VIDEO
    assert candidate.envelope.semantic_metadata.title == "water crashing over the rocks"
    assert candidate.envelope.semantic_metadata.tags == ("water", "rocks")
    assert candidate.source_duration_sec == 12.5
    assert candidate.fps == 30.0
    assert candidate.envelope.attribution.author == "Ada"


def test_numeric_only_slug_has_no_semantic_evidence():
    assert descriptive_video_slug("https://www.pexels.com/video/2499611/") is None


def test_video_file_selection_prefers_smallest_sufficient_then_720_fallback():
    high = map_video_response({"videos": [_video(video_files=[_file(1, 2160, 3840), _file(2, 1080, 1920)])]}, "water rocks")
    assert high.candidates[0].pexels_video_file_id == "2"
    fallback = map_video_response({"videos": [_video(video_files=[_file(1, 720, 1280), _file(2, 900, 1600)])]}, "water rocks")
    assert fallback.candidates[0].pexels_video_file_id == "1"


def test_video_file_selection_rejects_hls_landscape_and_sub720():
    payload = {"videos": [_video(video_files=[
        _file(1, 1080, 1920, file_type="application/x-mpegURL", link="https://cdn.test/a.m3u8"),
        _file(2, 1920, 1080), _file(3, 540, 960),
    ])]}
    try:
        map_video_response(payload, "water rocks")
        assert False, "expected malformed response"
    except Exception as exc:
        assert getattr(exc, "code", None) == "MALFORMED_RESPONSE"


def test_router_routes_video_when_available():
    routed = build_visual_sourcing_plan_v2(_plan("videos-only"), request_visuals={"sourceProviders": ["pexels"], "visualMode": "VIDEOS_ONLY"})
    candidate = routed["sourcingPlan"]["segments"][0]["providerCandidates"][0]
    assert candidate["capabilityId"] == "pexels.video.stock"
    assert candidate["mediaKind"] == VIDEO
    images = build_visual_sourcing_plan_v2(_plan("images-only"), request_visuals={"sourceProviders": ["pexels"], "visualMode": "IMAGES_ONLY"})
    assert images["sourcingPlan"]["segments"][0]["providerCandidates"][0]["capabilityId"] == "pexels.photos.stock"


def test_router_keeps_video_unroutable_when_planned(monkeypatch):
    monkeypatch.setattr("shorts_creator.assets.router.get_provider_capability", _planned_video_capability)
    routed = build_visual_sourcing_plan_v2(_plan("videos-only"), request_visuals={"sourceProviders": ["pexels"], "visualMode": "VIDEOS_ONLY"})
    assert routed["sourcingPlan"]["segments"][0]["routingStatus"] == "UNROUTABLE"


def test_videos_only_exact_form_is_unroutable():
    routed = build_visual_sourcing_plan_v2(_plan("videos-only", form="diagram"), request_visuals={"sourceProviders": ["pexels"], "visualMode": "VIDEOS_ONLY"})
    assert routed["sourcingPlan"]["segments"][0]["routingStatus"] == "UNROUTABLE"


def test_video_lifecycle_allows_only_anchored_unscorable_and_persists_metadata(tmp_path):
    result = map_video_response({"videos": [_video(url="https://www.pexels.com/video/2499611/", tags=[])]}, "water rocks photograph")
    search = PexelsVideoSearchResult("OK", result.candidates, {"x-ratelimit-remaining": "9"})
    with patch("shorts_creator.assets.providers.pexels_videos.search_pexels_videos", return_value=search), patch(
        "shorts_creator.assets.providers.pexels_videos.download_pexels_video",
        side_effect=lambda envelope, path: (path.parent.mkdir(parents=True, exist_ok=True), path.write_bytes(b"mp4"), {"ok": True, "size": 3, "mimeType": "video/mp4"})[-1],
    ):
        resolved = _resolve_pexels_videos(
            {"capabilityId": "pexels.video.stock", "queryStrategy": "search"},
            {"segmentIndex": 1, "assetPreference": "photograph", "subjects": [], "searchQueries": [{"text": "water rocks photograph"}]},
            {}, str(tmp_path), [], provider_credentials={"pexels": {"apiKey": "secret"}},
        )
    assert resolved["status"] == "RESOLVED"
    assert resolved["semanticAssessment"]["verdict"] == "UNSCORABLE"
    assert resolved["semanticDegradation"] == "PROVIDER_METADATA_INSUFFICIENT"
    assert resolved["visualFidelityAssessment"]["status"] == "NOT_APPLICABLE"
    assert _search_semantic_ok(resolved, "search") is True
    metadata = {"script": {"scenes": [{"sceneNumber": 1, "visualPlan": {"visualSequence": [{"segmentIndex": 1}]}}]}}
    segment = apply_visual_assets_v2_to_metadata(metadata, {"resolvedAssets": [dict(resolved, sceneNumber=1)], "unresolvedSegments": []})["assets"][0]["segments"][0]
    assert segment["mediaKind"] == VIDEO and segment["sourceDurationSec"] == 12.5 and segment["fps"] == 30.0


def test_image_postcondition_stays_strict_for_unscorable():
    assert _search_semantic_ok({"mediaKind": "IMAGE", "semanticAssessment": {"verdict": "UNSCORABLE"}, "semanticDegradation": "PROVIDER_METADATA_INSUFFICIENT"}, "search") is False


def test_video_pixel_gate_never_calls_openclip(monkeypatch, tmp_path):
    monkeypatch.setattr("shorts_creator.assets.executor.score_visual_fidelity", lambda *_args: (_ for _ in ()).throw(AssertionError("must not score video")))
    allowed, assessment = _apply_visual_fidelity_gate(tmp_path / "asset.mp4", "water rocks", [], media_kind=VIDEO)
    assert allowed is True
    assert assessment["reasonCode"] == "UNSUPPORTED_MEDIA_KIND"


def test_executor_dispatches_pexels_by_capability(monkeypatch, tmp_path):
    plan = {"schemaVersion": 1, "summary": {}, "segments": [{
        "segmentIndex": 1, "assetPreference": "photograph", "subjects": [],
        "searchQueries": [{"text": "water rocks"}], "generationPrompts": [],
        "providerCandidates": [{"provider": "pexels", "priority": 1, "queryStrategy": "search", "capabilityId": "pexels.video.stock", "mediaKind": VIDEO}],
        "excludedProviders": [], "routingStatus": "ROUTABLE",
    }]}
    monkeypatch.setattr("shorts_creator.assets.executor._resolve_pexels_videos", lambda *_args, **_kwargs: {
        "segmentIndex": 1, "assetPreference": "photograph", "status": "RESOLVED", "provider": "pexels", "mediaKind": VIDEO,
        "semanticAssessment": {"verdict": "RELEVANT"},
    })
    result = execute_visual_sourcing_plan_v2(plan, {"pexels": {"enabled": True, "implemented": True, "requiresApiKey": True, "apiKeyPresent": True}}, dry_run=False, job_dir=str(tmp_path))
    assert result["resolvedAssets"][0]["mediaKind"] == VIDEO


def _video_candidate_envelope():
    return map_video_response({"videos": [_video(url="https://www.pexels.com/video/water-crashing-over-the-rocks-1093662/")]}, "water rocks").candidates[0].envelope


def _fake_response(content_type="video/mp4", body=b"mp4"):
    class _Resp:
        def __init__(self):
            self.headers = {"Content-Type": content_type}
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n=-1):
            if n == -1:
                return self._body
            data = self._body
            self._body = b""
            return data

    return _Resp()


def test_downloader_sends_user_agent(tmp_path):
    captured = {}

    def _urlopen(request, timeout=None):
        captured["ua"] = request.get_header("User-agent") or request.get_header("User-Agent")
        return _fake_response(body=b"mp4")

    with patch("shorts_creator.assets.providers.pexels_videos.urllib.request.urlopen", side_effect=_urlopen):
        result = download_pexels_video(_video_candidate_envelope(), tmp_path / "a.mp4")
    assert result["ok"] is True
    assert captured["ua"] == "shorts-creator/1.0"


def test_downloader_rejects_non_mp4_mime(tmp_path):
    with patch("shorts_creator.assets.providers.pexels_videos.urllib.request.urlopen", return_value=_fake_response("image/jpeg")):
        result = download_pexels_video(_video_candidate_envelope(), tmp_path / "a.mp4")
    assert result["error"] == "VIDEO_MIME_MISMATCH"
    assert not (tmp_path / "a.mp4").exists()


def test_downloader_handles_403(tmp_path):
    def _raise(*a, **k):
        raise urllib.error.HTTPError("https://x", 403, "Forbidden", {}, None)

    with patch("shorts_creator.assets.providers.pexels_videos.urllib.request.urlopen", side_effect=_raise):
        result = download_pexels_video(_video_candidate_envelope(), tmp_path / "a.mp4")
    assert result["error"] == "VIDEO_ACCESS_DENIED"
    assert not (tmp_path / "a.mp4").exists()


# ── Fix 1: selected-only cross-scene reservation ─────────────────────────────


def _dl_ok():
    return lambda envelope, path: (path.parent.mkdir(parents=True, exist_ok=True), path.write_bytes(b"mp4"), {"ok": True, "size": 3, "mimeType": "video/mp4"})[-1]


def _resolve_videos(excluded_source, excluded_file, videos, query_texts, download=None):
    search = PexelsVideoSearchResult("OK", tuple(map_video_response({"videos": videos}, query_texts[0]).candidates), {})
    with patch("shorts_creator.assets.providers.pexels_videos.search_pexels_videos", return_value=search), patch(
        "shorts_creator.assets.providers.pexels_videos.download_pexels_video",
        side_effect=download if download is not None else _dl_ok(),
    ):
        return _resolve_pexels_videos(
            {"capabilityId": "pexels.video.stock", "queryStrategy": "search"},
            {"segmentIndex": 1, "assetPreference": "photograph", "subjects": [], "searchQueries": [{"text": q} for q in query_texts]},
            {}, str(Path("/tmp/resv-test")), [], excluded_source_urls=excluded_source, excluded_file_urls=excluded_file,
            provider_credentials={"pexels": {"apiKey": "secret"}},
        )


def test_rejected_video_candidate_does_not_poison_global_sets(tmp_path):
    excluded_source, excluded_file = set(), set()
    resolved = _resolve_videos(excluded_source, excluded_file, [_video(url="https://www.pexels.com/video/unrelated-footage-123/", tags=[])], ["water rocks photograph"])
    assert resolved["status"] == "NO_RESULTS"
    assert excluded_source == set()
    assert excluded_file == set()


def test_download_failed_video_candidate_does_not_poison_global_sets(tmp_path):
    excluded_source, excluded_file = set(), set()
    resolved = _resolve_videos(excluded_source, excluded_file, [_video(url="https://www.pexels.com/video/water-rocks-456/", tags=[])], ["water rocks photograph"], download=lambda envelope, path: {"ok": False, "error": "VIDEO_DOWNLOAD_FAILED"})
    assert resolved["status"] == "DOWNLOAD_FAILED"
    assert excluded_source == set()
    assert excluded_file == set()


def test_selected_video_candidate_enters_global_sets(tmp_path):
    excluded_source, excluded_file = set(), set()
    resolved = _resolve_videos(excluded_source, excluded_file, [_video(url="https://www.pexels.com/video/water-rocks-456/", tags=[])], ["water rocks photograph"])
    assert resolved["status"] == "RESOLVED"
    assert resolved["sourceUrl"] in excluded_source
    assert resolved["fileUrl"] in excluded_file


def test_selected_video_candidate_skipped_by_later_resolver(tmp_path):
    excluded_source, excluded_file = set(), set()
    videos = [_video(1, url="https://www.pexels.com/video/water-rocks-456/", tags=[])]
    first = _resolve_videos(excluded_source, excluded_file, videos, ["water rocks photograph"])
    assert first["status"] == "RESOLVED"
    second = _resolve_videos(excluded_source, excluded_file, videos, ["water rocks photograph"])
    assert second["status"] == "NO_RESULTS"


def test_local_repeated_video_candidate_evaluated_once(tmp_path):
    import shorts_creator.assets.executor as ex

    videos = [_video(1, url="https://www.pexels.com/video/water-rocks-456/", tags=[])]
    search = PexelsVideoSearchResult("OK", tuple(map_video_response({"videos": videos}, "water rocks photograph").candidates), {})
    calls = []
    orig = ex._evaluate_semantic

    def spy(segment, candidate):
        calls.append(candidate.get("queryUsed"))
        return orig(segment, candidate)

    with patch("shorts_creator.assets.providers.pexels_videos.search_pexels_videos", side_effect=lambda q, api_key=None, timeout=30: search), patch(
        "shorts_creator.assets.executor._evaluate_semantic", side_effect=spy), patch(
        "shorts_creator.assets.providers.pexels_videos.download_pexels_video", side_effect=_dl_ok(),
    ):
        resolved = _resolve_pexels_videos(
            {"capabilityId": "pexels.video.stock", "queryStrategy": "search"},
            {"segmentIndex": 1, "assetPreference": "photograph", "subjects": [], "searchQueries": [{"text": "water rocks photograph"}, {"text": "water rocks closeup"}]},
            {}, str(tmp_path), [], provider_credentials={"pexels": {"apiKey": "secret"}},
        )
    assert resolved["status"] == "RESOLVED"
    assert len(calls) == 1


# ── Fix 2: VIDEO sparse-metadata partial-match policy ────────────────────────


def test_video_sparse_partial_match_degraded_accept(tmp_path):
    excluded_source, excluded_file = set(), set()
    resolved = _resolve_videos(
        excluded_source, excluded_file,
        [_video(url="https://www.pexels.com/video/aerial-view-of-turquoise-ocean-waters-123/", tags=[])],
        ["tropical ocean landscape"],
    )
    assert resolved["status"] == "RESOLVED"
    assessment = resolved["semanticAssessment"]
    assert assessment["verdict"] == "IRRELEVANT"
    assert resolved["semanticDegradation"] == "PROVIDER_METADATA_PARTIAL_MATCH"
    assert assessment["matchedAnchors"]
    assert "allowSemanticDegradation" not in assessment
    assert "allowUnscorable" not in assessment


def test_video_sparse_zero_matched_anchors_rejected(tmp_path):
    excluded_source, excluded_file = set(), set()
    resolved = _resolve_videos(
        excluded_source, excluded_file,
        [_video(url="https://www.pexels.com/video/completely-unrelated-footage-999/", tags=[])],
        ["tropical ocean landscape"],
    )
    assert resolved["status"] == "NO_RESULTS"
    assert excluded_source == set()
    assert excluded_file == set()


def test_video_rich_metadata_mismatch_rejected(tmp_path):
    excluded_source, excluded_file = set(), set()
    resolved = _resolve_videos(
        excluded_source, excluded_file,
        [_video(url="https://www.pexels.com/video/mountain-forest-777/", tags=["mountain", "forest"])],
        ["tropical ocean landscape"],
    )
    assert resolved["status"] == "NO_RESULTS"


def test_video_partial_match_postcondition_allowed():
    ok = _search_semantic_ok({
        "mediaKind": VIDEO,
        "semanticAssessment": {"verdict": "IRRELEVANT", "matchedAnchors": ["ocean"]},
        "semanticDegradation": "PROVIDER_METADATA_PARTIAL_MATCH",
    }, "search")
    assert ok is True


def test_video_partial_match_without_anchors_rejected():
    ok = _search_semantic_ok({
        "mediaKind": VIDEO,
        "semanticAssessment": {"verdict": "IRRELEVANT", "matchedAnchors": []},
        "semanticDegradation": "PROVIDER_METADATA_PARTIAL_MATCH",
    }, "search")
    assert ok is False


def test_image_partial_match_flag_rejected():
    ok = _search_semantic_ok({
        "mediaKind": "IMAGE",
        "semanticAssessment": {"verdict": "IRRELEVANT", "matchedAnchors": ["ocean"]},
        "semanticDegradation": "PROVIDER_METADATA_PARTIAL_MATCH",
    }, "search")
    assert ok is False
