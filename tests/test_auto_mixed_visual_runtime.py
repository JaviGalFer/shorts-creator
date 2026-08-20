"""Slice 1 tests for auto-mixed-visual-runtime (offline/mocked). No network."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from shorts_creator.assets.bridge import apply_visual_assets_v2_to_metadata
from shorts_creator.assets.capabilities import PLANNED, get_provider_capability
from shorts_creator.assets.executor import (
    PREFERRED_MEDIA_EXHAUSTED,
    _apply_media_decision_outcome,
    execute_visual_sourcing_plan_v2,
)
from shorts_creator.assets.router import (
    build_visual_sourcing_plan_v2,
    _ordered_media_levels,
)
from shorts_creator.assets.providers.pexels_videos import (
    PexelsVideoSearchResult,
    map_video_response,
    search_pexels_videos,
)
from shorts_creator.contracts.visual import ALLOWED_MEDIA_PREFERENCES, canonicalize_visual_plan_v2
from shorts_creator.contracts.visual_media import (
    AUTO,
    EITHER,
    IMAGE,
    IMAGE_PREFERRED,
    IMAGES_ONLY,
    MIXED,
    VIDEO,
    VIDEO_PREFERRED,
    VIDEOS_ONLY,
    normalize_visual_mode,
)
from shorts_creator.contracts.visual_terms import medium_neutral_query


# ── Prompt / guardia ─────────────────────────────────────────────────────────


def _raw_script(segments, with_media_preference=None):
    vs = []
    for i, seg in enumerate(segments):
        item = {
            "segmentIndex": seg[0],
            "assetPreference": seg[1],
            "durationFraction": 1.0 / len(segments),
            "transition": "cut",
        }
        if with_media_preference is not None:
            item["mediaPreference"] = with_media_preference
        vs.append(item)
    return {
        "_schemaVersion": 2,
        "visualIntent": "show",
        "subjects": ["sujeto"],
        "searchQueries": ["sujeto foto"],
        "assetPreferences": ["photograph"],
        "visualSequence": vs,
    }


def _full_script(raw_plan):
    return {"scenes": [
        {"sceneNumber": 1, "voiceover": "texto con contenido suficiente",
         "targetDurationSec": 6.0, "subtitle": "texto",
         "visualPlan": raw_plan},
    ]}


_SCENE_PLAN = {"minSceneCount": 1, "maxSceneCount": 1, "preferredSceneCount": 1, "targetSceneDurationSec": 6.0}


class TestPromptMediaPreference:
    def test_system_prompt_documents_media_preference_contract(self):
        import shorts_creator.script.generator as gs

        assert "mediaPreference" in gs.SYSTEM_PROMPT_V2
        assert "VIDEO_PREFERRED" in gs.SYSTEM_PROMPT_V2
        assert "IMAGE_PREFERRED" in gs.SYSTEM_PROMPT_V2
        assert "EITHER" in gs.SYSTEM_PROMPT_V2
        # The example JSON must carry mediaPreference on segments
        json_start = gs.SYSTEM_PROMPT_V2.find('"visualSequence": [')
        example = gs.SYSTEM_PROMPT_V2[json_start:json_start + 700]
        assert '"mediaPreference": "VIDEO_PREFERRED"' in example
        assert '"mediaPreference": "IMAGE_PREFERRED"' in example

    def test_auto_mixed_blocks_require_explicit_emission(self):
        import shorts_creator.script.generator as gs

        for mode in ("auto", "mixed"):
            block = gs._build_media_preference_block(mode)
            assert "DEBE" in block
            assert "VIDEO_PREFERRED" in block and "IMAGE_PREFERRED" in block and "EITHER" in block

    def test_hard_modes_keep_policy_as_authority(self):
        import shorts_creator.script.generator as gs

        images = gs._build_media_preference_block("images-only")
        assert "IMAGE_PREFERRED" in images and "autoridad" in images
        videos = gs._build_media_preference_block("videos-only")
        assert "VIDEO_PREFERRED" in videos and "autoridad" in videos

    def test_medium_neutral_query_rule_in_system_prompt(self):
        import shorts_creator.script.generator as gs

        assert "photograph" in gs.SYSTEM_PROMPT_V2
        assert "mediaPreference" in gs.SYSTEM_PROMPT_V2

    def test_missing_media_preference_blocks_under_auto_mixed(self):
        import shorts_creator.script.generator as gs

        raw = {"scenes": [{"sceneNumber": 1, "visualPlan": _raw_script([(1, "photograph"), (2, "photograph")])}]}
        errors = gs._missing_media_preferences(raw)
        assert len(errors) == 2
        assert errors[0]["code"] == "MEDIA_PREFERENCE_MISSING"
        assert "mediaPreference" in errors[0]["path"]

    def test_explicit_presence_is_not_missing(self):
        import shorts_creator.script.generator as gs

        raw = {"scenes": [{"sceneNumber": 1, "visualPlan": _raw_script([(1, "photograph")], "IMAGE_PREFERRED")}]}
        assert gs._missing_media_preferences(raw) == []

    def test_validation_guard_triggers_retry_only_for_auto_mixed(self):
        import shorts_creator.script.generator as gs

        # AUTO/MIXED: raw plan missing mediaPreference -> errors -> retry
        raw = _full_script(_raw_script([(1, "photograph")]))
        _, errors, _ = gs._validate_and_canonicalize_script_v2(
            raw, allow_generated_images=False, scene_plan=_SCENE_PLAN, visual_mode=AUTO,
        )
        assert any(e["code"] == "MEDIA_PREFERENCE_MISSING" for e in errors)
        # explicit all-IMAGE_PREFERRED is valid (case A), NOT a retry cause
        raw2 = _full_script(_raw_script([(1, "photograph")], "IMAGE_PREFERRED"))
        canonical, errors2, _ = gs._validate_and_canonicalize_script_v2(
            raw2, allow_generated_images=False, scene_plan=_SCENE_PLAN, visual_mode=AUTO,
        )
        assert canonical is not None and errors2 == []
        # hard modes: guard disabled (historical behavior preserved)
        raw3 = _full_script(_raw_script([(1, "photograph")]))
        canonical3, errors3, _ = gs._validate_and_canonicalize_script_v2(
            raw3, allow_generated_images=False, scene_plan=_SCENE_PLAN, visual_mode=IMAGES_ONLY,
        )
        assert canonical3 is not None and errors3 == []
        assert canonical3["scenes"][0]["visualPlan"]["visualSequence"][0]["mediaPreference"] == IMAGE_PREFERRED

    def test_retry_instruction_has_corrective_media_block(self):
        import shorts_creator.script.generator as gs

        issues = [{"code": "MEDIA_PREFERENCE_MISSING", "path": "x", "message": "missing"}]
        instruction = gs._build_retry_instruction_v2(
            {}, 0, 1, 5.0, structural_issues=issues, allow_generated_images=False,
        )
        assert "Decisión editorial de medio ausente" in instruction
        assert "AUTO/MIXED" in instruction


# ── Query / queryUsed ────────────────────────────────────────────────────────


class TestMediumNeutralQuery:
    def test_strips_medium_markers_only(self):
        assert medium_neutral_query("emperor penguins photograph") == "emperor penguins"
        assert medium_neutral_query("aurora borealis night sky photo") == "aurora borealis night sky"
        assert medium_neutral_query("fox hunting footage") == "fox hunting"
        assert medium_neutral_query("cool stock photo of waves") == "cool of waves"

    def test_preserves_real_visual_forms(self):
        assert medium_neutral_query("human heart diagram") == "human heart diagram"
        assert medium_neutral_query("map of spain") == "map of spain"
        assert medium_neutral_query("gothic cathedral painting") == "gothic cathedral painting"
        assert medium_neutral_query("vintage document") == "vintage document"

    def test_never_empties_query(self):
        assert medium_neutral_query("photo") == "photo"
        assert medium_neutral_query("stock") == "stock"
        assert medium_neutral_query("") == ""

    def test_non_string_passthrough(self):
        assert medium_neutral_query(None) is None
        assert medium_neutral_query(5) == 5

    def test_pexels_video_uses_effective_query_for_search_and_envelope(self, monkeypatch):
        captured = {}

        def fake_get_json(path, params, api_key=None, timeout=30):
            captured["query"] = params["query"]
            return type("R", (), {"data": {"videos": []}, "telemetry": {}})()

        monkeypatch.setattr(
            "shorts_creator.assets.providers.pexels_videos.get_json", fake_get_json
        )
        result = search_pexels_videos("emperor penguins photograph", api_key="k")
        assert captured["query"] == "emperor penguins"
        assert result.status == "NO_RESULTS"

        mapped = map_video_response(
            {"videos": [
                {"id": 1, "width": 1080, "height": 1920, "duration": 5.0,
                 "url": "https://www.pexels.com/video/penguins-walking-1/",
                 "video_files": [{"id": 11, "width": 1080, "height": 1920, "fps": 30.0,
                                  "file_type": "video/mp4", "link": "https://cdn/x.mp4"}],
                 "tags": ["penguins"], "user": {"id": 1, "name": "a", "url": "u"}},
            ]},
            "emperor penguins",
        )
        assert mapped.candidates[0].envelope.query_used == "emperor penguins"

    def test_router_derives_medium_neutral_subject_queries(self):
        # Form words are kept: diagram suffix is a form, not a medium marker.
        plan = {
            "_schemaVersion": 2, "visualIntent": "show", "subjects": ["emperor penguin"],
            "searchQueries": ["penguin colony"], "assetPreferences": ["diagram"],
            "visualSequence": [{"segmentIndex": 1, "assetPreference": "diagram",
                                "mediaPreference": VIDEO_PREFERRED, "durationFraction": 1.0}],
        }
        routed = _route(plan, {"visualMode": AUTO, "sourceProviders": ["wikimedia_commons"]})
        texts = [q["text"] for q in routed["searchQueries"]]
        assert any("emperor penguin diagram" in t for t in texts)
        # Medium word dropped: photograph suffix is a medium marker and is skipped.
        plan2 = {
            "_schemaVersion": 2, "visualIntent": "show", "subjects": ["emperor penguin"],
            "searchQueries": ["penguin colony"], "assetPreferences": ["photograph"],
            "visualSequence": [{"segmentIndex": 1, "assetPreference": "photograph",
                                "mediaPreference": VIDEO_PREFERRED, "durationFraction": 1.0}],
        }
        routed2 = _route(plan2, {"visualMode": AUTO, "sourceProviders": ["pexels"]})
        texts2 = [q["text"] for q in routed2["searchQueries"]]
        assert all("photograph" not in t for t in texts2)
        assert any("penguin colony" in t for t in texts2)


# ── Router multi-kind + ordering ─────────────────────────────────────────────


def _route(plan, request_visuals, mix_counts=None):
    canonical = canonicalize_visual_plan_v2(plan)["canonicalPlan"]
    return build_visual_sourcing_plan_v2(
        canonical, request_visuals=request_visuals, mix_counts=mix_counts,
    )["sourcingPlan"]["segments"][0]


def _plan(pref="photograph", media="IMAGE_PREFERRED"):
    return {
        "_schemaVersion": 2, "visualIntent": "show", "subjects": ["test"],
        "searchQueries": ["test query"], "assetPreferences": [pref],
        "visualSequence": [{"segmentIndex": 1, "assetPreference": pref,
                            "mediaPreference": media, "durationFraction": 1.0, "transition": "cut"}],
    }


def _kinds(seg):
    return [c.get("mediaKind") for c in seg["providerCandidates"]]


def _providers(seg):
    return [c["provider"] for c in seg["providerCandidates"]]


class TestRouterMediaLevels:
    def test_auto_video_preferred_video_then_image(self):
        seg = _route(_plan(media="VIDEO_PREFERRED"), {
            "visualMode": AUTO, "sourceProviders": ["wikimedia_commons", "pixabay", "pexels"],
        })
        assert _kinds(seg) == [VIDEO, IMAGE, IMAGE, IMAGE]
        assert _providers(seg) == ["pexels", "wikimedia_commons", "pixabay", "pexels"]
        prios = [c["priority"] for c in seg["providerCandidates"]]
        assert prios == [1, 2, 3, 4]

    def test_auto_image_preferred_image_then_video(self):
        seg = _route(_plan(media="IMAGE_PREFERRED"), {
            "visualMode": AUTO, "sourceProviders": ["wikimedia_commons", "pixabay", "pexels"],
        })
        assert _kinds(seg) == [IMAGE, IMAGE, IMAGE, VIDEO]
        assert _providers(seg) == ["wikimedia_commons", "pixabay", "pexels", "pexels"]

    def test_auto_either_is_deterministic(self):
        seg1 = _route(_plan(media="EITHER"), {"visualMode": AUTO, "sourceProviders": ["wikimedia_commons", "pixabay", "pexels"]})
        seg2 = _route(_plan(media="EITHER"), {"visualMode": AUTO, "sourceProviders": ["wikimedia_commons", "pixabay", "pexels"]})
        assert [c["mediaKind"] for c in seg1["providerCandidates"]] == [
            c["mediaKind"] for c in seg2["providerCandidates"]
        ]
        assert _kinds(seg1) == [IMAGE, IMAGE, IMAGE, VIDEO]

    def test_mixed_either_uses_least_used_kind(self):
        for counts, expected in [({"IMAGE": 2, "VIDEO": 1}, VIDEO), ({"IMAGE": 0, "VIDEO": 1}, IMAGE), ({"IMAGE": 1, "VIDEO": 1}, IMAGE)]:
            seg = _route(_plan(media="EITHER"), {"visualMode": MIXED, "sourceProviders": ["wikimedia_commons", "pixabay", "pexels"]}, mix_counts=counts)
            assert seg["mediaDecision"]["resolvedKind"] == expected

    def test_mixed_strong_preference_unaffected_by_counts(self):
        seg = _route(_plan(media="VIDEO_PREFERRED"), {"visualMode": MIXED, "sourceProviders": ["wikimedia_commons", "pixabay", "pexels"]}, mix_counts={"IMAGE": 5, "VIDEO": 0})
        assert seg["mediaDecision"]["resolvedKind"] == VIDEO
        assert _kinds(seg) == [VIDEO, IMAGE, IMAGE, IMAGE]

    def test_images_only_never_has_video_fallback(self):
        seg = _route(_plan(media="VIDEO_PREFERRED"), {"visualMode": IMAGES_ONLY, "sourceProviders": ["wikimedia_commons", "pixabay", "pexels"]})
        assert VIDEO not in _kinds(seg)
        assert seg["mediaDecision"]["resolvedKind"] == IMAGE

    def test_videos_only_never_has_image_fallback(self):
        seg = _route(_plan(media="IMAGE_PREFERRED"), {"visualMode": VIDEOS_ONLY, "sourceProviders": ["wikimedia_commons", "pixabay", "pexels"]})
        assert _kinds(seg) == [VIDEO]
        assert seg["mediaDecision"]["resolvedKind"] == VIDEO

    def test_exact_form_never_gets_video_fallback(self):
        for form in ("diagram", "illustration", "painting"):
            seg = _route(_plan(pref=form, media="VIDEO_PREFERRED"), {"visualMode": AUTO, "sourceProviders": ["wikimedia_commons", "pixabay", "pexels"]})
            assert VIDEO not in _kinds(seg)

    def test_media_decision_and_fallback_kinds_persisted(self):
        seg = _route(_plan(media="VIDEO_PREFERRED"), {"visualMode": AUTO, "sourceProviders": ["wikimedia_commons", "pixabay", "pexels"]})
        decision = seg["mediaDecision"]
        assert decision["visualMode"] == AUTO
        assert decision["editorialPreference"] == VIDEO_PREFERRED
        assert decision["resolvedKind"] == VIDEO
        assert decision["fallbackKinds"] == [IMAGE]
        assert "allowedKinds" in decision and "runtimeAvailableKinds" in decision

    def test_unroutable_preserved(self):
        seg = _route(_plan(), {"visualMode": AUTO, "sourceProviders": ["freeai"]})
        assert seg["routingStatus"] == "UNROUTABLE"
        assert seg["providerCandidates"] == []

    def test_mixed_either_without_counts_falls_back_to_contractual_order(self):
        seg = _route(_plan(media="EITHER"), {"visualMode": MIXED, "sourceProviders": ["wikimedia_commons", "pixabay", "pexels"]})
        assert seg["mediaDecision"]["resolvedKind"] == IMAGE


# ── Executor fallback ────────────────────────────────────────────────────────


def _exec_provider_config(**pexels_overrides):
    cfg = {
        "wikimedia_commons": {"enabled": True, "implemented": True, "requiresApiKey": False},
        "pixabay": {"enabled": True, "implemented": True, "requiresApiKey": True, "apiKeyPresent": True},
        "pexels": {"enabled": True, "implemented": True, "requiresApiKey": True, "apiKeyPresent": True},
    }
    cfg["pexels"].update(pexels_overrides)
    return cfg


def _exec_segment(candidates, resolved_kind):
    return {
        "segmentIndex": 1, "assetPreference": "photograph", "subjects": [], "searchQueries": [],
        "generationPrompts": [], "providerCandidates": candidates, "excludedProviders": [],
        "routingStatus": "ROUTABLE",
        "mediaDecision": {
            "visualMode": AUTO, "editorialPreference": VIDEO_PREFERRED,
            "allowedKinds": [IMAGE, VIDEO], "formSupportedKinds": [IMAGE, VIDEO],
            "runtimeAvailableKinds": [IMAGE, VIDEO], "resolvedKind": resolved_kind,
            "preferenceStatus": "PREFERRED", "degradations": [], "fallbackKinds": [IMAGE],
        },
    }


def _exec_plan(segment):
    return {"schemaVersion": 1, "summary": {}, "segments": [segment]}


def _resolved(provider, media_kind, priority, capability_id):
    return {
        "provider": provider, "mediaKind": media_kind, "priority": priority,
        "queryStrategy": "search", "capabilityId": capability_id,
        "assetPath": "assets/x", "mimeType": "video/mp4" if media_kind == VIDEO else "image/jpeg",
    }


class TestExecutorCrossMediaFallback:
    def test_preferred_video_resolves_without_fallback(self, monkeypatch, tmp_path):
        candidates = [dict(_resolved("pexels", VIDEO, 1, "pexels.video.stock"))]
        plan = _exec_plan(_exec_segment(candidates, VIDEO))

        def fake_resolve(provider, candidate, seg, provider_config, job_dir, warnings,
                         asset_namespace=None, excluded_source_urls=None,
                         excluded_file_urls=None, wikimedia_cache=None,
                         provider_credentials=None):
            assert candidate["capabilityId"] == "pexels.video.stock"
            return {**candidate, "status": "RESOLVED", "searchQueryUsed": "penguins",
                    "semanticAssessment": {"verdict": "RELEVANT"}}

        monkeypatch.setattr("shorts_creator.assets.executor._try_live_resolution", fake_resolve)
        result = execute_visual_sourcing_plan_v2(plan, _exec_provider_config(), dry_run=False, job_dir=str(tmp_path))
        asset = result["resolvedAssets"][0]
        assert asset["mediaKind"] == VIDEO
        assert asset["mediaFallback"] is False
        assert asset["mediaDecision"]["resolvedKind"] == VIDEO

    def test_video_exhausted_image_resolves_with_fallback(self, monkeypatch, tmp_path):
        candidates = [
            dict(_resolved("pexels", VIDEO, 1, "pexels.video.stock")),
            dict(_resolved("wikimedia_commons", IMAGE, 2, "wikimedia_commons.image.stock")),
        ]
        plan = _exec_plan(_exec_segment(candidates, VIDEO))

        def fake_resolve(provider, candidate, seg, provider_config, job_dir, warnings,
                         asset_namespace=None, excluded_source_urls=None,
                         excluded_file_urls=None, wikimedia_cache=None,
                         provider_credentials=None):
            if candidate["mediaKind"] == VIDEO:
                return {"provider": provider, "status": "NO_RESULTS", "mediaKind": VIDEO,
                        "searchQueriesTried": []}
            return {**candidate, "status": "RESOLVED", "searchQueryUsed": "penguins",
                    "semanticAssessment": {"verdict": "RELEVANT"}}

        monkeypatch.setattr("shorts_creator.assets.executor._try_live_resolution", fake_resolve)
        result = execute_visual_sourcing_plan_v2(plan, _exec_provider_config(), dry_run=False, job_dir=str(tmp_path))
        asset = result["resolvedAssets"][0]
        assert asset["mediaKind"] == IMAGE
        assert asset["mediaFallback"] is True
        assert asset["mediaFallbackReason"] == PREFERRED_MEDIA_EXHAUSTED

    def test_unavailable_capability_is_not_exhaustion(self, monkeypatch, tmp_path):
        candidates = [dict(_resolved("pexels", VIDEO, 1, "pexels.video.stock"))]
        plan = _exec_plan(_exec_segment(candidates, VIDEO))
        result = execute_visual_sourcing_plan_v2(
            plan, _exec_provider_config(apiKeyPresent=False), dry_run=False, job_dir=str(tmp_path),
        )
        unresolved = result["unresolvedSegments"][0]
        assert unresolved["status"] == "PROVIDER_UNAVAILABLE"
        assert unresolved["mediaFallback"] is False
        assert unresolved["mediaDecision"]["resolvedKind"] == VIDEO

    def test_hard_modes_cannot_cross_media_fallback(self, monkeypatch, tmp_path):
        # VIDEOS_ONLY: only a VIDEO candidate exists; when it exhausts, no IMAGE
        # candidate is present, so the segment ends unresolved.
        candidates = [dict(_resolved("pexels", VIDEO, 1, "pexels.video.stock"))]
        segment = _exec_segment(candidates, VIDEO)
        segment["mediaDecision"]["visualMode"] = VIDEOS_ONLY
        segment["mediaDecision"]["preferenceStatus"] = "OVERRIDDEN_BY_USER"
        plan = _exec_plan(segment)

        def fake_resolve(provider, candidate, seg, provider_config, job_dir, warnings,
                         asset_namespace=None, excluded_source_urls=None,
                         excluded_file_urls=None, wikimedia_cache=None,
                         provider_credentials=None):
            return {"provider": provider, "status": "NO_RESULTS", "mediaKind": VIDEO, "searchQueriesTried": []}

        monkeypatch.setattr("shorts_creator.assets.executor._try_live_resolution", fake_resolve)
        result = execute_visual_sourcing_plan_v2(plan, _exec_provider_config(), dry_run=False, job_dir=str(tmp_path))
        assert result["resolvedAssets"] == []
        assert result["unresolvedSegments"][0]["status"] == "NO_RESULTS"

    def test_resolved_and_unresolved_preserve_media_decision(self, tmp_path):
        result = {"segmentIndex": 1, "status": "NO_RESULTS", "mediaKind": VIDEO}
        seg = {"segmentIndex": 1, "mediaDecision": {"resolvedKind": VIDEO}}
        _apply_media_decision_outcome(result, seg)
        assert result["mediaDecision"]["resolvedKind"] == VIDEO
        assert result["mediaFallback"] is False
        resolved = {"segmentIndex": 1, "status": "RESOLVED", "mediaKind": IMAGE}
        _apply_media_decision_outcome(resolved, seg)
        assert resolved["mediaFallback"] is True
        assert resolved["mediaFallbackReason"] == PREFERRED_MEDIA_EXHAUSTED


# ── MIXED tracker (fetcher threading) ────────────────────────────────────────


class TestMixTracker:
    def make_fetcher_env(self, monkeypatch, tmp_path):
        import shorts_creator.assets.router as router_mod
        import shorts_creator.assets.executor as executor_mod

        captured = {"route_calls": [], "exec_calls": 0, "exec_mix": None}

        def fake_route(canonical_plan, scene=None, request_visuals=None, mix_counts=None):
            captured["route_calls"].append(dict(mix_counts) if mix_counts else None)
            return {"ok": True, "sourcingPlan": {"schemaVersion": 1, "segments": [], "summary": {}}, "diagnostics": {}}

        def fake_execute(sourcing_plan, provider_config, dry_run=False, job_dir=None,
                         asset_namespace=None, excluded_source_urls=None,
                         excluded_file_urls=None, wikimedia_cache=None,
                         provider_credentials=None):
            captured["exec_calls"] += 1
            # Scene 1 resolves a VIDEO; scene 2 resolves nothing (unresolved IMAGE).
            if captured["exec_calls"] == 1:
                return {"ok": True, "dryRun": False, "resolvedAssets": [
                    {"segmentIndex": 1, "mediaKind": VIDEO, "status": "RESOLVED", "semanticAssessment": {"verdict": "RELEVANT"}},
                ], "unresolvedSegments": [], "dryRunAttempts": [], "diagnostics": {}}
            return {"ok": True, "dryRun": False, "resolvedAssets": [], "unresolvedSegments": [
                {"segmentIndex": 2, "mediaKind": IMAGE, "status": "NO_RESULTS"},
            ], "dryRunAttempts": [], "diagnostics": {}}

        monkeypatch.setattr(router_mod, "build_visual_sourcing_plan_v2", fake_route)
        monkeypatch.setattr(executor_mod, "execute_visual_sourcing_plan_v2", fake_execute)
        return captured

    def test_mix_counts_update_only_on_resolved_and_are_observed_next_scene(self, monkeypatch, tmp_path):
        import shorts_creator.assets.fetcher as fetcher_mod

        captured = self.make_fetcher_env(monkeypatch, tmp_path)
        metadata = {
            "request": {"visuals": {"visualMode": "MIXED", "sourceProviders": ["pexels"]}},
            "script": {"scenes": [
                {"sceneNumber": 1, "visualPlan": {"_schemaVersion": 2, "visualIntent": "show",
                                                  "subjects": ["s"], "searchQueries": ["s"],
                                                  "assetPreferences": ["photograph"],
                                                  "visualSequence": [{"segmentIndex": 1, "assetPreference": "photograph",
                                                                      "mediaPreference": "EITHER", "durationFraction": 1.0}]}},
                {"sceneNumber": 2, "visualPlan": {"_schemaVersion": 2, "visualIntent": "show",
                                                  "subjects": ["s"], "searchQueries": ["s"],
                                                  "assetPreferences": ["photograph"],
                                                  "visualSequence": [{"segmentIndex": 1, "assetPreference": "photograph",
                                                                      "mediaPreference": EITHER, "durationFraction": 1.0}]}},
            ]},
        }
        meta_path = tmp_path / "metadata.json"
        meta_path.write_text(json.dumps(metadata))
        assert fetcher_mod.fetch_assets(metadata_path=meta_path, dry_run=True) == 0
        # Scene 1 routed with initial zero counts; scene 2 sees VIDEO count 1.
        assert captured["route_calls"][0] == {"IMAGE": 0, "VIDEO": 0}
        assert captured["route_calls"][1] == {"IMAGE": 0, "VIDEO": 1}


# ── Bridge ───────────────────────────────────────────────────────────────────


class TestBridgeMediaDecision:
    def _meta(self, scenes):
        return {"script": {"scenes": scenes}}

    def test_resolved_persists_media_decision_and_fallback(self):
        scene = {"sceneNumber": 1, "visualPlan": {"visualSequence": [{"segmentIndex": 1, "durationFraction": 1.0}]}}
        metadata = self._meta([scene])
        decision = {"resolvedKind": VIDEO, "preferenceStatus": "PREFERRED", "fallbackKinds": [IMAGE]}
        result = apply_visual_assets_v2_to_metadata(metadata, {"resolvedAssets": [
            {"segmentIndex": 1, "status": "RESOLVED", "mediaKind": IMAGE, "mediaDecision": decision,
             "mediaFallback": True, "mediaFallbackReason": PREFERRED_MEDIA_EXHAUSTED},
        ], "unresolvedSegments": []})
        seg = result["assets"][0]["segments"][0]
        assert seg["mediaDecision"]["resolvedKind"] == VIDEO
        assert seg["mediaFallback"] is True
        assert seg["mediaFallbackReason"] == PREFERRED_MEDIA_EXHAUSTED

    def test_unresolved_persists_media_decision_without_media_fallback(self):
        scene = {"sceneNumber": 1, "visualPlan": {"visualSequence": [{"segmentIndex": 1, "durationFraction": 1.0}]}}
        metadata = self._meta([scene])
        decision = {"resolvedKind": VIDEO, "preferenceStatus": "EITHER", "fallbackKinds": []}
        result = apply_visual_assets_v2_to_metadata(metadata, {"resolvedAssets": [], "unresolvedSegments": [
            {"segmentIndex": 1, "status": "NO_RESULTS", "mediaKind": VIDEO, "mediaDecision": decision},
        ]})
        seg = result["assets"][0]["segments"][0]
        assert seg["mediaDecision"]["resolvedKind"] == VIDEO
        assert seg["mediaFallback"] is False

    def test_historical_segments_remain_unaffected(self):
        scene = {"sceneNumber": 1, "visualPlan": {"visualSequence": [{"segmentIndex": 1, "durationFraction": 1.0}]}}
        metadata = self._meta([scene])
        result = apply_visual_assets_v2_to_metadata(metadata, {"resolvedAssets": [], "unresolvedSegments": []})
        seg = result["assets"][0]["segments"][0]
        assert seg["mediaDecision"] is None
        assert seg["mediaFallback"] is False
        assert "mediaFallbackReason" not in seg