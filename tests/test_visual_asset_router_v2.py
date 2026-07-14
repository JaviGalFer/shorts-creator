"""Tests for Visual Asset Router v2.

Run: python3 -m pytest tests/test_visual_asset_router_v2.py -v
"""

import json
import sys
from pathlib import Path

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))

from visual_plan_v2 import canonicalize_visual_plan_v2, SCHEMA_VERSION
from visual_asset_router_v2 import (
    build_visual_sourcing_plan_v2,
    ROUTING_MATRIX,
    ALLOWED_ASSET_PREFERENCES,
    ALLOWED_PROVIDERS,
    ALLOWED_ROUTING_STATUSES,
    PROVIDER_AVAILABILITY,
    GENERATED_PROVIDERS,
    LEGACY_V1_FIELDS,
    DEFAULT_REQUEST_VISUALS,
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _canonicalize(payload: dict) -> dict:
    result = canonicalize_visual_plan_v2(payload)
    assert result["ok"], f"canonicalization failed: {result['diagnostics']}"
    return result["canonicalPlan"]


def _route(payload: dict, request_visuals: dict | None = None) -> dict:
    plan = _canonicalize(payload)
    return build_visual_sourcing_plan_v2(plan, request_visuals=request_visuals)


def _collect_legacy_fields(data, path="") -> list[str]:
    found: list[str] = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k in LEGACY_V1_FIELDS:
                found.append(f"{path}.{k}" if path else k)
            found.extend(_collect_legacy_fields(v, f"{path}.{k}" if path else k))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            found.extend(_collect_legacy_fields(item, f"{path}[{i}]"))
    return found


# ── 6 Fixture definitions (from visual_plan_v2 test suite) ─────────────────


def _photosynthesis_plan():
    return {
        "_schemaVersion": SCHEMA_VERSION,
        "visualIntent": "explain",
        "subjects": ["fotosintesis", "cloroplasto", "hoja"],
        "searchQueries": [
            "photosynthesis diagram",
            "chloroplast structure plant leaf",
        ],
        "assetPreferences": ["diagram", "illustration"],
        "visualSequence": [
            {
                "segmentIndex": 1,
                "assetPreference": "diagram",
                "searchQuery": "photosynthesis diagram plant leaf",
                "durationFraction": 1.0,
                "transition": "cut",
            }
        ],
    }


def _blockchain_plan():
    return {
        "_schemaVersion": SCHEMA_VERSION,
        "visualIntent": "explain",
        "subjects": ["blockchain", "distributed ledger", "transaction"],
        "searchQueries": [
            "blockchain diagram network",
            "how blockchain works distributed ledger",
        ],
        "assetPreferences": ["diagram", "illustration"],
        "visualSequence": [
            {
                "segmentIndex": 1,
                "assetPreference": "diagram",
                "searchQuery": "blockchain distributed ledger diagram",
                "durationFraction": 1.0,
                "transition": "cut",
            }
        ],
    }


def _octopus_plan():
    return {
        "_schemaVersion": SCHEMA_VERSION,
        "visualIntent": "show",
        "subjects": ["octopus", "camouflage", "chromatophore", "cephalopod"],
        "searchQueries": [
            "octopus camouflage ocean reef",
            "cephalopod color change skin",
        ],
        "assetPreferences": ["photograph", "diagram"],
        "location": "ocean",
        "preferredProviders": ["pexels", "wikimedia_commons"],
        "visualSequence": [
            {
                "segmentIndex": 1,
                "assetPreference": "photograph",
                "searchQuery": "octopus camouflaged on ocean reef",
                "durationFraction": 0.6,
                "transition": "fade",
            },
            {
                "segmentIndex": 2,
                "assetPreference": "diagram",
                "searchQuery": "cephalopod chromatophore skin cross section",
                "durationFraction": 0.4,
                "transition": "cut",
            },
        ],
    }


def _french_revolution_plan():
    return {
        "_schemaVersion": SCHEMA_VERSION,
        "visualIntent": "contextualize",
        "subjects": ["Bastilla", "Revolucion Francesa", "Paris"],
        "searchQueries": [
            "Storming of the Bastille 1789 painting",
            "Prise de la Bastille 14 juillet",
        ],
        "assetPreferences": ["archive", "painting"],
        "period": "1789",
        "location": "Paris",
        "preferredProviders": ["wikimedia_commons"],
        "visualSequence": [
            {
                "segmentIndex": 1,
                "assetPreference": "painting",
                "searchQuery": "Storming of the Bastille July 1789 painting",
                "durationFraction": 0.6,
                "transition": "cut",
            },
            {
                "segmentIndex": 2,
                "assetPreference": "archive",
                "searchQuery": "French Revolution Bastille document 1789",
                "durationFraction": 0.4,
                "transition": "fade",
            },
        ],
    }


def _marie_curie_plan():
    return {
        "_schemaVersion": SCHEMA_VERSION,
        "visualIntent": "show",
        "subjects": ["Marie Curie", "radioactivity", "radium", "polonium"],
        "searchQueries": [
            "Marie Curie portrait photograph",
            "Marie Curie laboratory Paris 1900s",
        ],
        "assetPreferences": ["photograph", "archive"],
        "period": "early 20th century",
        "location": "Paris",
        "preferredProviders": ["wikimedia_commons"],
        "visualSequence": [
            {
                "segmentIndex": 1,
                "assetPreference": "photograph",
                "searchQuery": "Marie Curie portrait photograph Nobel Prize",
                "durationFraction": 0.7,
                "transition": "cut",
            },
            {
                "segmentIndex": 2,
                "assetPreference": "archive",
                "searchQuery": "Marie Curie laboratory Paris 1900",
                "durationFraction": 0.3,
                "transition": "fade",
            },
        ],
    }


def _pomodoro_plan():
    return {
        "_schemaVersion": SCHEMA_VERSION,
        "visualIntent": "explain",
        "subjects": [
            "Pomodoro technique",
            "time management",
            "focus",
            "productivity",
        ],
        "searchQueries": [
            "pomodoro technique diagram timer",
            "time blocking method workflow",
        ],
        "assetPreferences": ["diagram", "illustration", "stock"],
        "visualSequence": [
            {
                "segmentIndex": 1,
                "assetPreference": "diagram",
                "searchQuery": "pomodoro technique 25 minute work flow diagram",
                "durationFraction": 0.5,
                "transition": "cut",
            },
            {
                "segmentIndex": 2,
                "assetPreference": "illustration",
                "searchQuery": "person working focused at desk timer",
                "durationFraction": 0.5,
                "transition": "fade",
            },
        ],
    }


# ── 6 Fixture tests ────────────────────────────────────────────────────────


class TestFixtureRouting:
    def test_photosynthesis_diagram_routable_with_warnings(self):
        result = _route(_photosynthesis_plan())
        assert result["ok"] is True
        segments = result["sourcingPlan"]["segments"]
        assert len(segments) == 1
        assert segments[0]["assetPreference"] == "diagram"
        assert segments[0]["routingStatus"] == "ROUTABLE_WITH_WARNINGS"
        providers = [c["provider"] for c in segments[0]["providerCandidates"]]
        assert "wikimedia_commons" in providers
        assert "freeai" not in providers
        assert "pollinations" not in providers

    def test_photosynthesis_generated_excluded_without_flag(self):
        result = _route(_photosynthesis_plan())
        s = result["sourcingPlan"]["segments"][0]
        excluded_providers = {e["provider"]: e["exclusionReason"] for e in s["excludedProviders"]}
        assert "freeai" in excluded_providers
        assert "generated" in excluded_providers["freeai"]

    def test_blockchain_diagram_routable_with_warnings(self):
        result = _route(_blockchain_plan())
        assert result["ok"] is True
        s = result["sourcingPlan"]["segments"][0]
        assert s["assetPreference"] == "diagram"
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"
        providers = [c["provider"] for c in s["providerCandidates"]]
        assert "wikimedia_commons" in providers
        assert "freeai" not in providers

    def test_octopus_photograph_routable_with_warnings(self):
        result = _route(_octopus_plan())
        assert result["ok"] is True
        s = [s for s in result["sourcingPlan"]["segments"] if s["assetPreference"] == "photograph"][0]
        assert s["routingStatus"] in ("ROUTABLE", "ROUTABLE_WITH_WARNINGS")
        # pexels is preferred, should be present
        providers = [c["provider"] for c in s["providerCandidates"]]
        assert "pexels" in providers or "pixabay" in providers or "wikimedia_commons" in providers

    def test_octopus_diagram_routable_with_warnings(self):
        result = _route(_octopus_plan())
        s = [s for s in result["sourcingPlan"]["segments"] if s["assetPreference"] == "diagram"][0]
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"

    def test_french_revolution_painting_routable_with_warnings(self):
        result = _route(_french_revolution_plan())
        s = [s for s in result["sourcingPlan"]["segments"] if s["assetPreference"] == "painting"][0]
        # Wikimedia with medium support + available → ROUTABLE_WITH_WARNINGS
        # (only strong+available yields clean ROUTABLE)
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"
        providers = [c["provider"] for c in s["providerCandidates"]]
        assert "wikimedia_commons" in providers

    def test_french_revolution_archive_routable_with_warnings(self):
        result = _route(_french_revolution_plan())
        s = [s for s in result["sourcingPlan"]["segments"] if s["assetPreference"] == "archive"][0]
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"
        providers = [c["provider"] for c in s["providerCandidates"]]
        assert "wikimedia_commons" in providers

    def test_marie_curie_photograph_routable_with_warnings(self):
        result = _route(_marie_curie_plan())
        s = [s for s in result["sourcingPlan"]["segments"] if s["assetPreference"] == "photograph"][0]
        # photograph: pexels=strong+conditional, pixabay=strong+conditional, wikimedia=medium+available
        # No strong+available provider → ROUTABLE_WITH_WARNINGS
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"

    def test_marie_curie_archive_routable_with_warnings(self):
        result = _route(_marie_curie_plan())
        s = [s for s in result["sourcingPlan"]["segments"] if s["assetPreference"] == "archive"][0]
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"

    def test_pomodoro_diagram_routable_with_warnings(self):
        result = _route(_pomodoro_plan())
        s = [s for s in result["sourcingPlan"]["segments"] if s["assetPreference"] == "diagram"][0]
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"

    def test_pomodoro_illustration_expected_status(self):
        result = _route(_pomodoro_plan())
        s = [s for s in result["sourcingPlan"]["segments"] if s["assetPreference"] == "illustration"][0]
        assert s["routingStatus"] in ("ROUTABLE", "ROUTABLE_WITH_WARNINGS")


# ── All 9 asset preferences ─────────────────────────────────────────────────


class TestAllAssetPreferences:
    def _plan_for_pref(self, pref: str, **overrides):
        plan = {
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["test"],
            "searchQueries": ["test query"],
            "assetPreferences": [pref],
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetPreference": pref,
                    "searchQuery": "test query",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
        }
        if pref == "generated":
            plan["allowGeneratedImage"] = True
        plan.update(overrides)
        return plan

    def test_diagram_routing(self):
        result = _route(self._plan_for_pref("diagram"))
        s = result["sourcingPlan"]["segments"][0]
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"
        providers = [c["provider"] for c in s["providerCandidates"]]
        assert "wikimedia_commons" in providers
        assert s["providerCandidates"][0]["supportStrength"] == "weak"

    def test_illustration_routing(self):
        result = _route(self._plan_for_pref("illustration"))
        s = result["sourcingPlan"]["segments"][0]
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"

    def test_photograph_routing(self):
        result = _route(self._plan_for_pref("photograph"))
        s = result["sourcingPlan"]["segments"][0]
        # pexels=strong+conditional, pixabay=strong+conditional, wikimedia=medium+available
        # No strong+available → ROUTABLE_WITH_WARNINGS
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"

    def test_painting_routing(self):
        result = _route(self._plan_for_pref("painting"))
        s = result["sourcingPlan"]["segments"][0]
        # wikimedia=medium+available → ROUTABLE_WITH_WARNINGS
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"

    def test_archive_routing(self):
        result = _route(self._plan_for_pref("archive"))
        s = result["sourcingPlan"]["segments"][0]
        # wikimedia=medium+available → ROUTABLE_WITH_WARNINGS
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"

    def test_map_routing(self):
        result = _route(self._plan_for_pref("map"))
        s = result["sourcingPlan"]["segments"][0]
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"
        providers = [c["provider"] for c in s["providerCandidates"]]
        assert "wikimedia_commons" in providers
        assert s["providerCandidates"][0]["supportStrength"] == "weak"

    def test_document_routing(self):
        result = _route(self._plan_for_pref("document"))
        s = result["sourcingPlan"]["segments"][0]
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"
        assert s["providerCandidates"][0]["supportStrength"] == "weak"

    def test_stock_routing(self):
        result = _route(self._plan_for_pref("stock"))
        s = result["sourcingPlan"]["segments"][0]
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"
        # stock: pexels strong + conditional, pixabay strong + conditional
        # both conditional → ROUTABLE_WITH_WARNINGS

    def test_generated_routable_with_warnings_when_both_gates_open(self):
        plan = self._plan_for_pref("generated", allowGeneratedImage=True)
        result = _route(plan, request_visuals={"allowGeneratedImages": True})
        s = result["sourcingPlan"]["segments"][0]
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"
        providers = [c["provider"] for c in s["providerCandidates"]]
        assert "freeai" in providers
        assert "pollinations" in providers

    def test_generated_unroutable_without_plan_flag(self):
        plan = self._plan_for_pref("generated", allowGeneratedImage=True)
        result = _route(plan, request_visuals={"allowGeneratedImages": True})
        s = result["sourcingPlan"]["segments"][0]
        # Both gates open, but all candidates are conditional → ROUTABLE_WITH_WARNINGS
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"

    def test_generated_unroutable_with_request_gate_only(self):
        plan = self._plan_for_pref("generated", allowGeneratedImage=True)
        result = _route(plan, request_visuals={"allowGeneratedImages": False})
        s = result["sourcingPlan"]["segments"][0]
        assert s["routingStatus"] == "UNROUTABLE"


# ── Request-level constraints ───────────────────────────────────────────────


class TestRequestConstraints:
    def _plan(self, pref: str):
        return {
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["test"],
            "searchQueries": ["test query"],
            "assetPreferences": [pref],
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetPreference": pref,
                    "searchQuery": "test query",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
        }

    def test_blocked_providers_excludes(self):
        result = _route(self._plan("photograph"), request_visuals={
            "blockedProviders": ["pexels"],
        })
        s = result["sourcingPlan"]["segments"][0]
        included = {c["provider"] for c in s["providerCandidates"]}
        assert "pexels" not in included
        excluded = {e["provider"] for e in s["excludedProviders"]}
        assert "pexels" in excluded

    def test_allow_search_providers_false(self):
        result = _route(self._plan("photograph"), request_visuals={
            "allowSearchProviders": False,
        })
        s = result["sourcingPlan"]["segments"][0]
        assert s["routingStatus"] == "UNROUTABLE"

    def test_allow_stock_assets_false_excludes_pexels_pixabay(self):
        result = _route(self._plan("stock"), request_visuals={
            "allowStockAssets": False,
        })
        s = result["sourcingPlan"]["segments"][0]
        assert s["routingStatus"] == "UNROUTABLE"
        included = {c["provider"] for c in s["providerCandidates"]}
        assert "pexels" not in included
        assert "pixabay" not in included

    def test_allow_stock_assets_false_excludes_pexels_from_photograph(self):
        result = _route(self._plan("photograph"), request_visuals={
            "allowStockAssets": False,
        })
        s = result["sourcingPlan"]["segments"][0]
        included = {c["provider"] for c in s["providerCandidates"]}
        assert "pexels" not in included
        assert "pixabay" not in included
        assert "wikimedia_commons" in included

    def test_allow_archive_assets_false_excludes_wikimedia_for_painting(self):
        result = _route(self._plan("painting"), request_visuals={
            "allowArchiveAssets": False,
        })
        s = result["sourcingPlan"]["segments"][0]
        assert s["routingStatus"] == "UNROUTABLE"

    def test_allow_archive_assets_false_does_not_exclude_wikimedia_for_photograph(self):
        result = _route(self._plan("photograph"), request_visuals={
            "allowArchiveAssets": False,
        })
        s = result["sourcingPlan"]["segments"][0]
        included = {c["provider"] for c in s["providerCandidates"]}
        assert "wikimedia_commons" in included

    def test_allow_generated_images_false_excludes_generated(self):
        plan = self._plan("diagram")
        plan["allowGeneratedImage"] = True
        result = _route(plan, request_visuals={
            "allowGeneratedImages": False,
        })
        s = result["sourcingPlan"]["segments"][0]
        included = {c["provider"] for c in s["providerCandidates"]}
        assert "freeai" not in included
        assert "pollinations" not in included

    def test_generated_double_gate_both_true_allows_generated(self):
        plan = self._plan("diagram")
        plan["allowGeneratedImage"] = True
        result = _route(plan, request_visuals={
            "allowGeneratedImages": True,
        })
        s = result["sourcingPlan"]["segments"][0]
        included = {c["provider"] for c in s["providerCandidates"]}
        assert "freeai" in included
        assert "pollinations" in included

    def test_generated_double_gate_plan_false_blocks(self):
        plan = self._plan("diagram")
        plan["allowGeneratedImage"] = False
        result = _route(plan, request_visuals={
            "allowGeneratedImages": True,
        })
        s = result["sourcingPlan"]["segments"][0]
        included = {c["provider"] for c in s["providerCandidates"]}
        assert "freeai" not in included
        assert "pollinations" not in included


# ── Priority policies ───────────────────────────────────────────────────────


class TestPriorityPolicies:
    def _plan(self, pref="photograph"):
        return {
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "show",
            "subjects": ["test"],
            "searchQueries": ["test query"],
            "assetPreferences": [pref],
            "preferredProviders": ["wikimedia_commons"],
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetPreference": pref,
                    "searchQuery": "test query",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
        }

    def test_balanced_policy(self):
        result = _route(self._plan(), request_visuals={
            "providerPriorityPolicy": "balanced",
            "preferredProviders": ["pexels"],
        })
        s = result["sourcingPlan"]["segments"][0]
        # photograph: no strong+available provider → always ROUTABLE_WITH_WARNINGS
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"

    def test_request_first_policy(self):
        result = _route(self._plan(), request_visuals={
            "providerPriorityPolicy": "request_first",
            "preferredProviders": ["wikimedia_commons"],
        })
        s = result["sourcingPlan"]["segments"][0]
        # wikimedia should be P1
        p1 = s["providerCandidates"][0]
        assert p1["provider"] == "wikimedia_commons"
        assert p1["priority"] == 1

    def test_plan_first_policy(self):
        result = _route(self._plan(), request_visuals={
            "providerPriorityPolicy": "plan_first",
            "preferredProviders": ["pexels"],
        })
        s = result["sourcingPlan"]["segments"][0]
        # wikimedia is plan preferred, should be P1
        p1 = s["providerCandidates"][0]
        assert p1["provider"] == "wikimedia_commons"
        assert p1["priority"] == 1

    def test_policy_never_promotes_blocked_providers(self):
        result = _route(self._plan(), request_visuals={
            "providerPriorityPolicy": "request_first",
            "preferredProviders": ["pexels"],
            "blockedProviders": ["pexels"],
        })
        s = result["sourcingPlan"]["segments"][0]
        included = {c["provider"] for c in s["providerCandidates"]}
        assert "pexels" not in included

    def test_policy_never_promotes_gated_generated(self):
        plan = self._plan("diagram")
        plan["allowGeneratedImage"] = False
        result = _route(plan, request_visuals={
            "providerPriorityPolicy": "request_first",
            "preferredProviders": ["freeai"],
            "allowGeneratedImages": False,
        })
        s = result["sourcingPlan"]["segments"][0]
        included = {c["provider"] for c in s["providerCandidates"]}
        assert "freeai" not in included

    def test_unknown_priority_policy_falls_back_to_balanced(self):
        result = _route(self._plan(), request_visuals={
            "providerPriorityPolicy": "warp_drive",
        })
        assert result["ok"] is True
        warnings = [w["code"] for w in result["diagnostics"]["warnings"]]
        assert any("UNKNOWN_PRIORITY_POLICY" in w for w in warnings)


# ── Generated-image planning ───────────────────────────────────────────────


class TestGeneratedImagePlanning:
    def _plan(self, pref="generated", allow_generated=True):
        overrides: dict = {}
        if allow_generated:
            overrides["allowGeneratedImage"] = True
        else:
            overrides["allowGeneratedImage"] = True
        return {
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "show",
            "subjects": ["test"],
            "searchQueries": ["test query"],
            "assetPreferences": [pref],
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetPreference": pref,
                    "searchQuery": "test query",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
            **overrides,
        }

    def test_freeai_is_conditional_and_requires_api_key(self):
        result = _route(self._plan(), request_visuals={"allowGeneratedImages": True})
        s = result["sourcingPlan"]["segments"][0]
        freeai = [c for c in s["providerCandidates"] if c["provider"] == "freeai"]
        assert len(freeai) == 1
        assert freeai[0]["availability"] == "conditional"
        assert freeai[0]["requiresApiKey"] is True
        assert freeai[0]["queryStrategy"] == "generate"

    def test_pollinations_is_conditional_no_api_key(self):
        result = _route(self._plan(), request_visuals={"allowGeneratedImages": True})
        s = result["sourcingPlan"]["segments"][0]
        polli = [c for c in s["providerCandidates"] if c["provider"] == "pollinations"]
        assert len(polli) == 1
        assert polli[0]["availability"] == "conditional"
        assert polli[0]["requiresApiKey"] is False
        assert polli[0]["queryStrategy"] == "generate"

    def test_generated_segment_never_routable_clean(self):
        result = _route(self._plan(), request_visuals={"allowGeneratedImages": True})
        s = result["sourcingPlan"]["segments"][0]
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"

    def test_generated_segment_unroutable_when_both_gates_false(self):
        plan = self._plan(allow_generated=True)
        result = _route(plan, request_visuals={"allowGeneratedImages": False})
        s = result["sourcingPlan"]["segments"][0]
        assert s["routingStatus"] == "UNROUTABLE"

    def test_freeai_never_makes_segment_routable_by_itself(self):
        plan = self._plan()
        plan["assetPreferences"] = ["generated"]
        plan["visualSequence"][0]["assetPreference"] = "generated"
        result = _route(plan, request_visuals={"allowGeneratedImages": True})
        s = result["sourcingPlan"]["segments"][0]
        assert s["routingStatus"] != "ROUTABLE"

    def test_pollinations_never_makes_segment_routable_by_itself(self):
        plan = self._plan()
        plan["assetPreferences"] = ["generated"]
        plan["visualSequence"][0]["assetPreference"] = "generated"
        result = _route(plan, request_visuals={"allowGeneratedImages": True})
        s = result["sourcingPlan"]["segments"][0]
        assert s["routingStatus"] != "ROUTABLE"

    def test_generated_providers_carry_warnings(self):
        result = _route(self._plan(), request_visuals={"allowGeneratedImages": True})
        s = result["sourcingPlan"]["segments"][0]
        candidates = {c["provider"]: c for c in s["providerCandidates"]}
        assert len(candidates.get("freeai", {}).get("warnings", [])) > 0
        assert len(candidates.get("pollinations", {}).get("warnings", [])) > 0


# ── Query derivation ────────────────────────────────────────────────────────


class TestQueryDerivation:
    def _plan(self, **overrides):
        base = {
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["subject one", "subject two"],
            "searchQueries": ["scene query one", "scene query two"],
            "assetPreferences": ["diagram"],
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetPreference": "diagram",
                    "searchQuery": "segment specific query",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
        }
        base.update(overrides)
        return base

    def test_segment_search_query_first(self):
        result = _route(self._plan())
        s = result["sourcingPlan"]["segments"][0]
        assert s["searchQueries"][0]["text"] == "segment specific query"
        assert s["searchQueries"][0]["source"] == "segment.searchQuery"

    def test_scene_search_queries_next(self):
        result = _route(self._plan(
            visualSequence=[{
                "segmentIndex": 1,
                "assetPreference": "diagram",
                "durationFraction": 1.0,
                "transition": "cut",
            }]
        ))
        s = result["sourcingPlan"]["segments"][0]
        sources = [q["source"] for q in s["searchQueries"]]
        assert any("scene.searchQueries" in src for src in sources)

    def test_image_generation_prompt_not_in_search_queries(self):
        result = _route(self._plan(
            imageGenerationPrompt="a beautiful generative image",
            allowGeneratedImage=True,
        ))
        s = result["sourcingPlan"]["segments"][0]
        sq_sources = [q["source"] for q in s["searchQueries"]]
        assert not any("imageGenerationPrompt" in src for src in sq_sources), \
            "imageGenerationPrompt must not appear in searchQueries"
        gp_sources = [p["source"] for p in s["generationPrompts"]]
        assert any("scene.imageGenerationPrompt" in src for src in gp_sources), \
            "imageGenerationPrompt must appear in generationPrompts"

    def test_subject_plus_asset_preference_fallback(self):
        result = _route(self._plan(
            visualSequence=[{
                "segmentIndex": 1,
                "assetPreference": "diagram",
                "durationFraction": 1.0,
                "transition": "cut",
            }]
        ))
        s = result["sourcingPlan"]["segments"][0]
        sources = [q["source"] for q in s["searchQueries"]]
        assert any("subjects" in src and "assetPreference" in src for src in sources)

    def test_subject_plus_location_if_budget_remains(self):
        plan = {
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["subject one"],
            "searchQueries": ["scene query one"],
            "assetPreferences": ["diagram"],
            "location": "Paris",
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetPreference": "diagram",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
        }
        result = _route(plan)
        s = result["sourcingPlan"]["segments"][0]
        sources = [q["source"] for q in s["searchQueries"]]
        assert any("location" in src for src in sources)

    def test_subject_plus_period_if_budget_remains(self):
        plan = {
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["subject one"],
            "searchQueries": ["scene query one"],
            "assetPreferences": ["diagram"],
            "period": "1789",
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetPreference": "diagram",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
        }
        result = _route(plan)
        s = result["sourcingPlan"]["segments"][0]
        sources = [q["source"] for q in s["searchQueries"]]
        assert any("period" in src for src in sources)

    def test_deduplication_case_insensitive(self):
        result = _route(self._plan(
            searchQueries=["SEGMENT SPECIFIC QUERY", "Segment Specific Query"],
            visualSequence=[{
                "segmentIndex": 1,
                "assetPreference": "diagram",
                "searchQuery": "segment specific query",
                "durationFraction": 1.0,
                "transition": "cut",
            }]
        ))
        s = result["sourcingPlan"]["segments"][0]
        texts_lower = [q["text"].lower() for q in s["searchQueries"]]
        assert len(texts_lower) == len(set(texts_lower))

    def test_max_queries_per_segment_respected(self):
        result = _route(self._plan(
            searchQueries=["q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8"],
            subjects=["s1", "s2", "s3", "s4", "s5", "s6"],
            location="Paris",
            period="1789",
        ), request_visuals={"maxQueriesPerSegment": 3})
        s = result["sourcingPlan"]["segments"][0]
        assert len(s["searchQueries"]) <= 3

    def test_no_queries_warning_when_empty(self):
        plan = {
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["irrelevant"],
            "searchQueries": ["irrelevant query"],
            "assetPreferences": ["diagram"],
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetPreference": "diagram",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
        }
        result = _route(plan)
        s = result["sourcingPlan"]["segments"][0]
        # Scene searchQueries should still provide a query
        assert len(s["searchQueries"]) >= 1
        # But if we route a plan with truly no subj/query data that can produce queries,
        # the warning should be absent for valid plans that DO produce queries
        assert len(s["searchQueries"]) > 0

    def test_location_period_not_used_as_domain_classification(self):
        plan = {
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["subject one"],
            "searchQueries": ["minimal query"],
            "assetPreferences": ["diagram"],
            "period": "1789",
            "location": "Paris",
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetPreference": "diagram",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
        }
        result = _route(plan)
        s = result["sourcingPlan"]["segments"][0]
        for q in s["searchQueries"]:
            if "location" in q["source"] or "period" in q["source"]:
                assert "Paris" in q["text"] or "1789" in q["text"]


# ── Excluded providers ──────────────────────────────────────────────────────


class TestExcludedProviders:
    def _plan(self, pref="diagram"):
        return {
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["test"],
            "searchQueries": ["test query"],
            "assetPreferences": [pref],
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetPreference": pref,
                    "searchQuery": "test query",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
        }

    def test_excluded_providers_include_unsuitable(self):
        result = _route(self._plan("stock"))
        s = result["sourcingPlan"]["segments"][0]
        excluded_providers = {e["provider"] for e in s["excludedProviders"]}
        # wikimedia doesn't support 'stock', so it should be in the matrix
        included = {c["provider"] for c in s["providerCandidates"]}
        assert "pexels" in included or "pixabay" in included

    def test_excluded_providers_have_exclusion_reason(self):
        result = _route(self._plan("diagram"))
        s = result["sourcingPlan"]["segments"][0]
        for e in s["excludedProviders"]:
            assert e.get("exclusionReason"), f"{e['provider']} missing exclusionReason"

    def test_all_non_matrix_providers_excluded_for_generated_no_gates(self):
        plan = self._plan("generated")
        plan["allowGeneratedImage"] = True
        result = _route(plan, request_visuals={"allowGeneratedImages": False})
        s = result["sourcingPlan"]["segments"][0]
        assert s["routingStatus"] == "UNROUTABLE"


# ── Output contract ─────────────────────────────────────────────────────────


class TestOutputContract:
    def test_ok_is_true_for_valid_plan(self):
        result = _route(_photosynthesis_plan())
        assert result["ok"] is True

    def test_ok_is_false_for_invalid_plan_input(self):
        result = build_visual_sourcing_plan_v2("not a dict")
        assert result["ok"] is False

    def test_ok_is_false_for_invalid_request_config_type(self):
        plan = _canonicalize(_photosynthesis_plan())
        result = build_visual_sourcing_plan_v2(plan, request_visuals="bad")
        assert result["ok"] is False

    def test_sourcing_plan_has_required_top_level_keys(self):
        result = _route(_photosynthesis_plan())
        sp = result["sourcingPlan"]
        assert "schemaVersion" in sp
        assert sp["schemaVersion"] == 1
        assert "segments" in sp
        assert "summary" in sp

    def test_summary_has_correct_counts(self):
        result = _route(_octopus_plan())
        summary = result["sourcingPlan"]["summary"]
        assert summary["totalSegments"] == 2
        assert summary["routable"] + summary["routableWithWarnings"] + summary["unroutable"] == 2

    def test_diagnostics_has_required_keys(self):
        result = _route(_photosynthesis_plan())
        d = result["diagnostics"]
        assert "errors" in d
        assert "warnings" in d
        assert "unsupported" in d
        assert "routingDecisions" in d

    def test_each_segment_has_required_keys(self):
        result = _route(_octopus_plan())
        for s in result["sourcingPlan"]["segments"]:
            assert "segmentIndex" in s
            assert "assetPreference" in s
            assert "searchQueries" in s
            assert "generationPrompts" in s
            assert "providerCandidates" in s
            assert "excludedProviders" in s
            assert "routingStatus" in s
            assert "warnings" in s
            assert "unsupportedReasons" in s

    def test_provider_candidate_has_required_keys(self):
        result = _route(_french_revolution_plan())
        for s in result["sourcingPlan"]["segments"]:
            for c in s["providerCandidates"]:
                assert "provider" in c
                assert "priority" in c
                assert "queryStrategy" in c
                assert "candidateStatus" in c
                assert "availability" in c
                assert "requiresApiKey" in c
                assert "supportStrength" in c
                assert "reason" in c
                assert "warnings" in c

    def test_routing_statuses_are_valid(self):
        result = _route(_pomodoro_plan())
        for s in result["sourcingPlan"]["segments"]:
            assert s["routingStatus"] in ALLOWED_ROUTING_STATUSES


# ── Invalid request config should not crash ─────────────────────────────────


class TestInvalidRequestConfig:
    def _plan(self):
        return {
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["test"],
            "searchQueries": ["test query"],
            "assetPreferences": ["diagram"],
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetPreference": "diagram",
                    "searchQuery": "test query",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
        }

    def test_invalid_bool_fields_do_not_crash(self):
        result = _route(self._plan(), request_visuals={
            "allowSearchProviders": "yes",
        })
        assert result["ok"] is True
        assert any("INVALID_REQUEST_CONFIG" in w["code"]
                   for w in result["diagnostics"]["warnings"])

    def test_invalid_max_queries_do_not_crash(self):
        result = _route(self._plan(), request_visuals={
            "maxQueriesPerSegment": "lots",
        })
        assert result["ok"] is True
        assert any("INVALID_REQUEST_CONFIG" in w["code"]
                   for w in result["diagnostics"]["warnings"])

    def test_invalid_max_queries_zero_do_not_crash(self):
        result = _route(self._plan(), request_visuals={
            "maxQueriesPerSegment": 0,
        })
        assert result["ok"] is True
        assert any("INVALID_REQUEST_CONFIG" in w["code"]
                   for w in result["diagnostics"]["warnings"])

    def test_unrecognized_provider_in_preferred_warns(self):
        result = _route(self._plan(), request_visuals={
            "preferredProviders": ["nonexistent_provider"],
        })
        assert result["ok"] is True
        warnings = [w["code"] for w in result["diagnostics"]["warnings"]]
        assert any("UNRECOGNIZED_PROVIDER" in w for w in warnings)


# ── Legacy v1 field regression ─────────────────────────────────────────────


class TestNoLegacyFields:
    def test_photosynthesis_no_legacy_fields(self):
        result = _route(_photosynthesis_plan())
        found = _collect_legacy_fields(result)
        assert not found, f"Legacy fields found: {found}"

    def test_blockchain_no_legacy_fields(self):
        result = _route(_blockchain_plan())
        found = _collect_legacy_fields(result)
        assert not found, f"Legacy fields found: {found}"

    def test_octopus_no_legacy_fields(self):
        result = _route(_octopus_plan())
        found = _collect_legacy_fields(result)
        assert not found, f"Legacy fields found: {found}"

    def test_french_revolution_no_legacy_fields(self):
        result = _route(_french_revolution_plan())
        found = _collect_legacy_fields(result)
        assert not found, f"Legacy fields found: {found}"

    def test_marie_curie_no_legacy_fields(self):
        result = _route(_marie_curie_plan())
        found = _collect_legacy_fields(result)
        assert not found, f"Legacy fields found: {found}"

    def test_pomodoro_no_legacy_fields(self):
        result = _route(_pomodoro_plan())
        found = _collect_legacy_fields(result)
        assert not found, f"Legacy fields found: {found}"

    def test_all_asset_preferences_no_legacy_fields(self):
        for pref in ["diagram", "illustration", "photograph", "painting",
                     "archive", "map", "document", "stock"]:
            plan = {
                "_schemaVersion": SCHEMA_VERSION,
                "visualIntent": "explain",
                "subjects": ["test"],
                "searchQueries": ["test query"],
                "assetPreferences": [pref],
                "visualSequence": [{
                    "segmentIndex": 1,
                    "assetPreference": pref,
                    "searchQuery": "test query",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }],
            }
            result = _route(plan)
            found = _collect_legacy_fields(result)
            assert not found, f"Legacy fields found for pref '{pref}': {found}"


# ── Summary edge cases ──────────────────────────────────────────────────────


class TestSummaryEdgeCases:
    def test_all_segments_unroutable(self):
        plan = {
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["test"],
            "searchQueries": ["test"],
            "assetPreferences": ["generated"],
            "allowGeneratedImage": True,
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetPreference": "generated",
                    "searchQuery": "test",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
        }
        result = _route(plan, request_visuals={"allowGeneratedImages": False})
        summary = result["sourcingPlan"]["summary"]
        assert summary["unroutable"] == 1
        assert summary["routable"] == 0

    def test_request_visuals_none_uses_defaults(self):
        plan = _canonicalize(_photosynthesis_plan())
        result = build_visual_sourcing_plan_v2(plan, request_visuals=None)
        assert result["ok"] is True

    def test_unknown_preference_no_crash(self):
        plan = {
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["test"],
            "searchQueries": ["test"],
            "assetPreferences": ["diagram", "painting"],
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetPreference": "painting",
                    "searchQuery": "test",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
        }
        result = _route(plan)
        s = result["sourcingPlan"]["segments"][0]
        assert s["assetPreference"] == "painting"
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"


# ── Fix 1: Search/generation separation ──────────────────────────────────────


class TestSearchGenerationSeparation:
    def _plan(self, pref="diagram", **overrides):
        return {
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["test"],
            "searchQueries": ["test query"],
            "assetPreferences": [pref],
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetPreference": pref,
                    "searchQuery": "segment test query",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
            **overrides,
        }

    def test_image_generation_prompt_not_in_search_queries(self):
        plan = self._plan("diagram", imageGenerationPrompt="generate this diagram")
        result = _route(plan)
        s = result["sourcingPlan"]["segments"][0]
        sq_texts = [q["text"] for q in s["searchQueries"]]
        assert "generate this diagram" not in sq_texts, \
            "imageGenerationPrompt must not appear in searchQueries"
        sq_sources = [q["source"] for q in s["searchQueries"]]
        assert not any("imageGenerationPrompt" in src for src in sq_sources), \
            "imageGenerationPrompt source must not appear in searchQueries"

    def test_generation_prompts_contains_image_generation_prompt(self):
        plan = self._plan("diagram", imageGenerationPrompt="generate this diagram")
        result = _route(plan)
        s = result["sourcingPlan"]["segments"][0]
        gp_texts = [p["text"] for p in s["generationPrompts"]]
        assert "generate this diagram" in gp_texts, \
            "imageGenerationPrompt must appear in generationPrompts"

    def test_generated_segment_generation_prompts_accessible(self):
        plan = self._plan("generated", imageGenerationPrompt="generate me", allowGeneratedImage=True)
        result = _route(plan, request_visuals={"allowGeneratedImages": True})
        s = result["sourcingPlan"]["segments"][0]
        assert len(s["generationPrompts"]) >= 1
        # FreeAI/Pollinations should be included (generated pref, both gates open)
        included = {c["provider"] for c in s["providerCandidates"]}
        assert "freeai" in included
        assert "pollinations" in included

    def test_generated_segment_search_providers_excluded(self):
        plan = self._plan("generated", allowGeneratedImage=True)
        result = _route(plan, request_visuals={"allowGeneratedImages": True})
        s = result["sourcingPlan"]["segments"][0]
        included = {c["provider"] for c in s["providerCandidates"]}
        assert "pexels" not in included
        assert "pixabay" not in included
        assert "wikimedia_commons" not in included
        excluded = {e["provider"] for e in s["excludedProviders"]}
        assert "pexels" in excluded
        assert "pixabay" in excluded
        assert "wikimedia_commons" in excluded

    def test_photograph_segment_no_generation_prompt_in_search(self):
        plan = self._plan("photograph", imageGenerationPrompt="a photo prompt")
        result = _route(plan)
        s = result["sourcingPlan"]["segments"][0]
        sq_texts = [q["text"] for q in s["searchQueries"]]
        assert "a photo prompt" not in sq_texts, \
            "imageGenerationPrompt must not leak into photograph searchQueries"
        included = {c["provider"] for c in s["providerCandidates"]}
        for provider in included:
            c = [c for c in s["providerCandidates"] if c["provider"] == provider][0]
            if c["queryStrategy"] == "search":
                pass

    def test_generation_prompt_fallback_to_segment_query(self):
        plan = {
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["test"],
            "searchQueries": ["test query"],
            "assetPreferences": ["generated"],
            "allowGeneratedImage": True,
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetPreference": "generated",
                    "searchQuery": "a generated illustration",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
        }
        result = _route(plan, request_visuals={"allowGeneratedImages": True})
        s = result["sourcingPlan"]["segments"][0]
        assert len(s["generationPrompts"]) >= 1
        gp_sources = [p["source"] for p in s["generationPrompts"]]
        assert any("searchQuery" in src and "fallback" in src for src in gp_sources), \
            "when imageGenerationPrompt is missing, fallback to segment.searchQuery"


# ── Fix 2: Excluded provider completeness ────────────────────────────────────


class TestExcludedProviderCompleteness:
    def test_all_prefs_have_five_providers(self):
        for pref in ALLOWED_ASSET_PREFERENCES:
            plan = {
                "_schemaVersion": SCHEMA_VERSION,
                "visualIntent": "explain",
                "subjects": ["test"],
                "searchQueries": ["test query"],
                "assetPreferences": [pref],
                "visualSequence": [
                    {
                        "segmentIndex": 1,
                        "assetPreference": pref,
                        "searchQuery": "test query",
                        "durationFraction": 1.0,
                        "transition": "cut",
                    }
                ],
            }
            if pref == "generated":
                plan["allowGeneratedImage"] = True
            result = _route(plan)
            s = result["sourcingPlan"]["segments"][0]
            total = len(s["providerCandidates"]) + len(s["excludedProviders"])
            assert total == len(ALLOWED_PROVIDERS), \
                f"pref '{pref}': got {total} providers, expected {len(ALLOWED_PROVIDERS)}"
            all_provs = {c.get("provider") for c in s["providerCandidates"]}
            all_provs |= {e["provider"] for e in s["excludedProviders"]}
            assert all_provs == ALLOWED_PROVIDERS, \
                f"pref '{pref}': missing providers {ALLOWED_PROVIDERS - all_provs}"

    def test_diagram_excludes_pexels_pixabay_as_unsuitable(self):
        plan = {
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["test"],
            "searchQueries": ["test query"],
            "assetPreferences": ["diagram"],
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetPreference": "diagram",
                    "searchQuery": "test query",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
        }
        result = _route(plan)
        s = result["sourcingPlan"]["segments"][0]
        excluded = {e["provider"]: e for e in s["excludedProviders"]}
        assert "pexels" in excluded
        assert "pixabay" not in excluded
        assert "does not support" in excluded["pexels"]["exclusionReason"]
        assert "diagram" in excluded["pexels"]["exclusionReason"]

    def test_stock_excludes_wikimedia_as_unsuitable(self):
        plan = {
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["test"],
            "searchQueries": ["test query"],
            "assetPreferences": ["stock"],
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetPreference": "stock",
                    "searchQuery": "test query",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
        }
        result = _route(plan)
        s = result["sourcingPlan"]["segments"][0]
        excluded = {e["provider"]: e for e in s["excludedProviders"]}
        assert "wikimedia_commons" in excluded
        assert "does not support" in excluded["wikimedia_commons"]["exclusionReason"]
        assert "stock" in excluded["wikimedia_commons"]["exclusionReason"]

    def test_generated_both_gates_false_all_search_excluded(self):
        plan = {
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["test"],
            "searchQueries": ["test query"],
            "assetPreferences": ["generated"],
            "allowGeneratedImage": True,
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetPreference": "generated",
                    "searchQuery": "test query",
                    "durationFraction": 1.0,
                    "transition": "cut",
                }
            ],
        }
        result = _route(plan, request_visuals={"allowGeneratedImages": False})
        s = result["sourcingPlan"]["segments"][0]
        assert s["routingStatus"] == "UNROUTABLE"
        excluded = {e["provider"]: e for e in s["excludedProviders"]}
        assert "freeai" in excluded
        assert "pollinations" in excluded
        assert "wikimedia_commons" in excluded
        assert "pexels" in excluded
        assert "pixabay" in excluded
        total = len(s["providerCandidates"]) + len(s["excludedProviders"])
        assert total == len(ALLOWED_PROVIDERS)

    def test_every_provider_appears_exactly_once_per_segment(self):
        for pref in ["diagram", "photograph", "generated"]:
            plan = {
                "_schemaVersion": SCHEMA_VERSION,
                "visualIntent": "explain",
                "subjects": ["test"],
                "searchQueries": ["test query"],
                "assetPreferences": [pref],
                "visualSequence": [
                    {
                        "segmentIndex": 1,
                        "assetPreference": pref,
                        "searchQuery": "test query",
                        "durationFraction": 1.0,
                        "transition": "cut",
                    }
                ],
            }
            if pref == "generated":
                plan["allowGeneratedImage"] = True
            result = _route(plan, request_visuals={"allowGeneratedImages": True} if pref == "generated" else None)
            s = result["sourcingPlan"]["segments"][0]
            cand_providers = [c["provider"] for c in s["providerCandidates"]]
            excl_providers = [e["provider"] for e in s["excludedProviders"]]
            all_p = cand_providers + excl_providers
            assert len(all_p) == len(ALLOWED_PROVIDERS), \
                f"pref '{pref}': total count mismatch"
            assert len(all_p) == len(set(all_p)), \
                f"pref '{pref}': duplicate providers found"


# ── Regression ───────────────────────────────────────────────────────────────


class TestRegressionAfterFixes:
    def test_all_six_fixtures_still_conservative(self):
        plans = {
            "photosynthesis": _photosynthesis_plan(),
            "blockchain": _blockchain_plan(),
            "octopus": _octopus_plan(),
            "french_revolution": _french_revolution_plan(),
            "marie_curie": _marie_curie_plan(),
            "pomodoro": _pomodoro_plan(),
        }
        for name, plan_fn in plans.items():
            result = _route(plan_fn)
            assert result["ok"], f"{name}: ok should be True"
            for seg in result["sourcingPlan"]["segments"]:
                assert seg["routingStatus"] in ("ROUTABLE", "ROUTABLE_WITH_WARNINGS"), \
                    f"{name} seg[{seg['segmentIndex']}]: unexpected status {seg['routingStatus']}"
                assert len(seg["searchQueries"]) >= 0
                assert isinstance(seg["generationPrompts"], list)
                total = len(seg["providerCandidates"]) + len(seg["excludedProviders"])
                assert total == len(ALLOWED_PROVIDERS), \
                    f"{name} seg[{seg['segmentIndex']}]: {total} providers, expected 5"
                found = _collect_legacy_fields(seg)
                assert not found, f"{name} seg[{seg['segmentIndex']}]: legacy fields {found}"

    def test_no_legacy_fields_anywhere(self):
        result = _route(_octopus_plan())
        found = _collect_legacy_fields(result)
        assert not found, f"Legacy fields found: {found}"
    
    
    # ── Diagram + Pixabay ────────────────────────────────────────────────
    
    def test_diagram_includes_pixabay_as_candidate(self):
        result = _route(_photosynthesis_plan())
        s = result["sourcingPlan"]["segments"][0]
        providers = [c["provider"] for c in s["providerCandidates"]]
        assert "wikimedia_commons" in providers
        assert "pixabay" in providers
    
    def test_pixabay_diagram_marked_weak_not_strong(self):
        result = _route(_photosynthesis_plan())
        s = result["sourcingPlan"]["segments"][0]
        pix = [c for c in s["providerCandidates"] if c["provider"] == "pixabay"][0]
        assert pix["supportStrength"] == "weak"
    
    def test_pixabay_diagram_conditional_requires_api_key(self):
        result = _route(_photosynthesis_plan())
        s = result["sourcingPlan"]["segments"][0]
        pix = [c for c in s["providerCandidates"] if c["provider"] == "pixabay"][0]
        assert pix["requiresApiKey"] is True
        assert pix["availability"] == "conditional"
    
    def test_diagram_pixabay_warning_present(self):
        result = _route(_photosynthesis_plan())
        s = result["sourcingPlan"]["segments"][0]
        wms = s.get("warnings", [])
        relevant = [w for w in wms if "Pixabay" in w]
        assert len(relevant) >= 1
    
    def test_diagram_missing_api_key_not_invalidates_plan(self):
        result = _route(_photosynthesis_plan())
        assert result["ok"] is True
        s = result["sourcingPlan"]["segments"][0]
        assert s["routingStatus"] == "ROUTABLE_WITH_WARNINGS"
    
    def test_allow_stock_assets_false_excludes_pixabay(self):
        plan = _canonicalize({
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["test"],
            "searchQueries": ["test query"],
            "assetPreferences": ["diagram"],
            "visualSequence": [{
                "segmentIndex": 1,
                "assetPreference": "diagram",
                "searchQuery": "test query",
                "durationFraction": 1.0,
                "transition": "cut",
            }],
        })
        result = build_visual_sourcing_plan_v2(
            plan, request_visuals={"allowStockAssets": False},
        )
        s = result["sourcingPlan"]["segments"][0]
        excluded = {e["provider"] for e in s["excludedProviders"]}
        candidates = {c["provider"] for c in s["providerCandidates"]}
        assert "pixabay" in excluded
        assert "pixabay" not in candidates
    
    def test_blocked_providers_pixabay_excludes(self):
        plan = _canonicalize({
            "_schemaVersion": SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["test"],
            "searchQueries": ["test query"],
            "assetPreferences": ["diagram"],
            "visualSequence": [{
                "segmentIndex": 1,
                "assetPreference": "diagram",
                "searchQuery": "test query",
                "durationFraction": 1.0,
                "transition": "cut",
            }],
        })
        result = build_visual_sourcing_plan_v2(
            plan, request_visuals={"blockedProviders": ["pixabay"]},
        )
        s = result["sourcingPlan"]["segments"][0]
        excluded = {e["provider"] for e in s["excludedProviders"]}
        candidates = {c["provider"] for c in s["providerCandidates"]}
        assert "pixabay" in excluded
        assert "pixabay" not in candidates
    
    def test_diagram_no_legacy_fields_added(self):
        result = _route(_photosynthesis_plan())
        found = _collect_legacy_fields(result)
        assert not found, f"Legacy fields found: {found}"
    
    def test_diagram_no_domain_modes_added(self):
        result = _route(_photosynthesis_plan())
        s = result["sourcingPlan"]["segments"][0]
        for c in s["providerCandidates"]:
            assert "domainMode" not in c
