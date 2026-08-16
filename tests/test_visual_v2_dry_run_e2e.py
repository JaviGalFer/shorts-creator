"""End-to-end dry-run validation for the v2 visual stack.

Exercises the full chain:
    VisualPlan v2 canonicalizer → Visual Asset Router v2
    → Visual Asset Executor v2 dry-run

Run: python3 -m pytest tests/test_visual_v2_dry_run_e2e.py -v
"""

import sys
from pathlib import Path

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))

from shorts_creator.contracts.visual import canonicalize_visual_plan_v2, SCHEMA_VERSION
from shorts_creator.assets.router import build_visual_sourcing_plan_v2, LEGACY_V1_FIELDS
from shorts_creator.assets.executor import execute_visual_sourcing_plan_v2

LEGACY_FIELD_NAMES = frozenset({
    "editorialRole", "visualTemporalIntent", "strategy",
    "primaryAssetType", "secondaryAssetType", "style",
    "mood", "licenseRequired", "visualImportance",
})


# ── Provider config fixtures ────────────────────────────────────────────────


def _config_a_none_implemented():
    return {
        "wikimedia_commons": {"enabled": True, "implemented": False, "requiresApiKey": False},
        "pexels": {"enabled": True, "implemented": False, "requiresApiKey": True, "apiKeyPresent": False},
        "pixabay": {"enabled": True, "implemented": False, "requiresApiKey": True, "apiKeyPresent": False},
        "freeai": {"enabled": True, "implemented": False, "requiresApiKey": True, "apiKeyPresent": False},
        "pollinations": {"enabled": True, "implemented": False, "requiresApiKey": False},
    }


def _config_b_wikimedia_available():
    return {
        "wikimedia_commons": {"enabled": True, "implemented": True, "requiresApiKey": False},
        "pexels": {"enabled": True, "implemented": False, "requiresApiKey": True, "apiKeyPresent": False},
        "pixabay": {"enabled": True, "implemented": False, "requiresApiKey": True, "apiKeyPresent": False},
        "freeai": {"enabled": True, "implemented": False, "requiresApiKey": True, "apiKeyPresent": False},
        "pollinations": {"enabled": True, "implemented": False, "requiresApiKey": False},
    }


def _config_c_generated_available():
    return {
        "wikimedia_commons": {"enabled": False, "implemented": True, "requiresApiKey": False},
        "pexels": {"enabled": False, "implemented": True, "requiresApiKey": True, "apiKeyPresent": True},
        "pixabay": {"enabled": False, "implemented": True, "requiresApiKey": True, "apiKeyPresent": True},
        "freeai": {"enabled": True, "implemented": True, "requiresApiKey": True, "apiKeyPresent": True},
        "pollinations": {"enabled": True, "implemented": True, "requiresApiKey": False},
    }


# ── VisualPlan v2 fixtures ──────────────────────────────────────────────────


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


def _generated_plan():
    return {
        "_schemaVersion": SCHEMA_VERSION,
        "visualIntent": "show",
        "subjects": ["abstract landscape", "dreamscape", "surreal"],
        "searchQueries": ["abstract geometric landscape"],
        "assetPreferences": ["generated"],
        "allowGeneratedImage": True,
        "imageGenerationPrompt": "a surreal abstract geometric landscape with vibrant colors",
        "visualSequence": [
            {
                "segmentIndex": 1,
                "assetPreference": "generated",
                "searchQuery": "abstract geometric landscape",
                "durationFraction": 1.0,
                "transition": "cut",
            }
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


# ── Helpers ─────────────────────────────────────────────────────────────────


def _run_pipeline(raw_plan, provider_config, request_visuals=None):
    canon_result = canonicalize_visual_plan_v2(raw_plan)
    assert canon_result["ok"], f"canonicalize failed: {canon_result['diagnostics']}"
    canon = canon_result["canonicalPlan"]

    router_result = build_visual_sourcing_plan_v2(canon, request_visuals=request_visuals)
    assert router_result["ok"], f"router failed: {router_result['diagnostics']}"
    sp = router_result["sourcingPlan"]

    exec_result = execute_visual_sourcing_plan_v2(
        sp, provider_config, request_visuals=request_visuals, dry_run=True,
    )
    return canon_result, router_result, exec_result


def _collect_legacy_fields(data, path=""):
    found = []
    if isinstance(data, dict):
        for k, v in data.items():
            key = k.lstrip("_") if isinstance(k, str) else str(k)
            if key in LEGACY_FIELD_NAMES or k in LEGACY_FIELD_NAMES:
                found.append(f"{path}.{k}" if path else k)
            found.extend(_collect_legacy_fields(v, f"{path}.{k}" if path else k))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            found.extend(_collect_legacy_fields(item, f"{path}[{i}]"))
    return found


# ── Config A: none implemented ──────────────────────────────────────────────


class TestConfigANoneImplemented:
    """All providers not implemented → all segments provider-unavailable."""

    def test_photosynthesis_config_a(self):
        canon, router, exec_ = _run_pipeline(
            _photosynthesis_plan(), _config_a_none_implemented(),
        )
        assert canon["ok"] and router["ok"] and exec_["ok"]
        assert exec_["dryRun"] is True
        assert exec_["resolvedAssets"] == []
        assert exec_["dryRunAttempts"] == []
        unres = exec_["unresolvedSegments"]
        assert len(unres) == 1
        assert unres[0]["status"] == "PROVIDER_UNAVAILABLE"

    def test_octopus_config_a(self):
        _, _, exec_ = _run_pipeline(
            _octopus_plan(), _config_a_none_implemented(),
        )
        assert exec_["ok"]
        assert exec_["dryRunAttempts"] == []
        assert exec_["resolvedAssets"] == []
        unres = exec_["unresolvedSegments"]
        assert len(unres) == 2
        for u in unres:
            assert u["status"] == "PROVIDER_UNAVAILABLE"

    def test_generated_config_a_no_gates(self):
        canon, router, exec_ = _run_pipeline(
            _generated_plan(), _config_a_none_implemented(),
            request_visuals={"allowGeneratedImages": True},
        )
        assert canon["ok"] and router["ok"] and exec_["ok"]
        assert exec_["dryRunAttempts"] == []
        assert exec_["resolvedAssets"] == []

    def test_pomodoro_config_a(self):
        _, _, exec_ = _run_pipeline(
            _pomodoro_plan(), _config_a_none_implemented(),
        )
        assert exec_["ok"]
        assert exec_["dryRunAttempts"] == []
        unres = exec_["unresolvedSegments"]
        assert len(unres) == 2
        for u in unres:
            assert u["status"] == "PROVIDER_UNAVAILABLE"

    def test_french_revolution_config_a(self):
        _, _, exec_ = _run_pipeline(
            _french_revolution_plan(), _config_a_none_implemented(),
        )
        assert exec_["ok"]
        assert exec_["dryRunAttempts"] == []
        unres = exec_["unresolvedSegments"]
        assert len(unres) == 2
        for u in unres:
            assert u["status"] == "PROVIDER_UNAVAILABLE"


# ── Config B: wikimedia simulated available ─────────────────────────────────


class TestConfigBWikimediaAvailable:
    """Wikimedia implemented=true → segments routed to wikimedia get
    SKIPPED_DRY_RUN."""

    def test_photosynthesis_wikimedia(self):
        _, _, exec_ = _run_pipeline(
            _photosynthesis_plan(), _config_b_wikimedia_available(),
        )
        assert exec_["ok"]
        assert len(exec_["dryRunAttempts"]) == 1
        attempt = exec_["dryRunAttempts"][0]
        assert attempt["status"] == "SKIPPED_DRY_RUN"
        assert attempt["selectedProvider"] == "wikimedia_commons"
        assert attempt["selectedInputType"] == "searchQueries"
        assert len(attempt["selectedInputs"]) >= 1
        assert exec_["resolvedAssets"] == []

    def test_octopus_wikimedia(self):
        _, _, exec_ = _run_pipeline(
            _octopus_plan(), _config_b_wikimedia_available(),
        )
        assert exec_["ok"]
        attempts = exec_["dryRunAttempts"]
        unres = exec_["unresolvedSegments"]
        for a in attempts:
            assert a["status"] == "SKIPPED_DRY_RUN"
            assert a["selectedInputType"] == "searchQueries"
        assert exec_["resolvedAssets"] == []
        assert len(attempts) + len(unres) == 2

    def test_french_revolution_wikimedia(self):
        _, _, exec_ = _run_pipeline(
            _french_revolution_plan(), _config_b_wikimedia_available(),
        )
        assert exec_["ok"]
        attempts = exec_["dryRunAttempts"]
        unres = exec_["unresolvedSegments"]
        for a in attempts:
            assert a["status"] == "SKIPPED_DRY_RUN"
            assert a["selectedProvider"] == "wikimedia_commons"
            assert a["selectedInputType"] == "searchQueries"
        assert exec_["resolvedAssets"] == []
        assert len(attempts) + len(unres) == 2

    def test_pomodoro_wikimedia(self):
        _, router, exec_ = _run_pipeline(
            _pomodoro_plan(), _config_b_wikimedia_available(),
        )
        assert exec_["ok"]
        attempts = exec_["dryRunAttempts"]
        for a in attempts:
            assert a["status"] == "SKIPPED_DRY_RUN"
            assert a["selectedInputType"] == "searchQueries"
        assert exec_["resolvedAssets"] == []

    def test_generated_no_gates_blocked_with_wikimedia(self):
        _, router, exec_ = _run_pipeline(
            _generated_plan(), _config_b_wikimedia_available(),
            request_visuals={"allowGeneratedImages": False},
        )
        assert exec_["ok"]
        for seg in router["sourcingPlan"]["segments"]:
            if seg["assetPreference"] == "generated":
                assert seg["routingStatus"] == "UNROUTABLE"
        unres = exec_["unresolvedSegments"]
        assert len(unres) >= 1
        for u in unres:
            if u["assetPreference"] == "generated":
                assert u["status"] == "UNRESOLVED"


# ── Config C: generated provider simulated available ────────────────────────


class TestConfigCGeneratedAvailable:
    """Generated providers available; search providers disabled."""

    def test_generated_plan_config_c(self):
        _, router, exec_ = _run_pipeline(
            _generated_plan(), _config_c_generated_available(),
            request_visuals={"allowGeneratedImages": True},
        )
        assert exec_["ok"]

        for seg in router["sourcingPlan"]["segments"]:
            candidates = {c["provider"] for c in seg["providerCandidates"]}
            assert "freeai" in candidates or "pollinations" in candidates

        attempts = exec_["dryRunAttempts"]
        assert len(attempts) >= 1
        for a in attempts:
            assert a["status"] == "SKIPPED_DRY_RUN"
            assert a["selectedInputType"] == "generationPrompts"
            assert len(a["selectedInputs"]) >= 1
            assert a["selectedProvider"] in ("freeai", "pollinations")
        assert exec_["resolvedAssets"] == []

    def test_photosynthesis_blocks_generated_no_flag(self):
        _, router, exec_ = _run_pipeline(
            _photosynthesis_plan(), _config_c_generated_available(),
            request_visuals={"allowGeneratedImages": True},
        )
        assert exec_["ok"]
        for seg in router["sourcingPlan"]["segments"]:
            if seg["assetPreference"] == "diagram":
                included = {c["provider"] for c in seg["providerCandidates"]}
                assert "freeai" not in included
                assert "pollinations" not in included

    def test_generated_without_request_gate_blocked_config_c(self):
        _, router, exec_ = _run_pipeline(
            _generated_plan(), _config_c_generated_available(),
            request_visuals={"allowGeneratedImages": False},
        )
        assert exec_["ok"]
        for seg in router["sourcingPlan"]["segments"]:
            if seg["assetPreference"] == "generated":
                assert seg["routingStatus"] == "UNROUTABLE"


# ── Legacy field regression ─────────────────────────────────────────────────


class TestE2ENoLegacyFields:
    """Recursive check that no v1 legacy fields appear anywhere in the
    canonicalizer, router or executor outputs."""

    FIXTURES = [
        ("photosynthesis", _photosynthesis_plan()),
        ("octopus", _octopus_plan()),
        ("generated", _generated_plan()),
        ("pomodoro", _pomodoro_plan()),
        ("french_revolution", _french_revolution_plan()),
    ]

    def test_canonicalizer_no_legacy(self):
        for name, raw in self.FIXTURES:
            result = canonicalize_visual_plan_v2(raw)
            assert result["ok"], f"{name}: canonicalize failed"
            found = _collect_legacy_fields(result)
            assert not found, f"{name}: legacy fields in canonicalizer: {found}"

    def test_router_no_legacy(self):
        for name, raw in self.FIXTURES:
            canon_result = canonicalize_visual_plan_v2(raw)
            assert canon_result["ok"], f"{name}: canonicalize failed"
            router_result = build_visual_sourcing_plan_v2(
                canon_result["canonicalPlan"],
                request_visuals={"allowGeneratedImages": True},
            )
            assert router_result["ok"], f"{name}: router failed"
            found = _collect_legacy_fields(router_result)
            assert not found, f"{name}: legacy fields in router: {found}"

    def test_executor_no_legacy_config_b(self):
        for name, raw in self.FIXTURES:
            _, _, exec_ = _run_pipeline(
                raw, _config_b_wikimedia_available(),
            )
            found = _collect_legacy_fields(exec_)
            assert not found, f"{name}: legacy fields in executor (config B): {found}"

    def test_executor_no_legacy_config_c(self):
        raw = _generated_plan()
        _, _, exec_ = _run_pipeline(
            raw, _config_c_generated_available(),
            request_visuals={"allowGeneratedImages": True},
        )
        found = _collect_legacy_fields(exec_)
        assert not found, f"generated: legacy fields in executor (config C): {found}"


# ── Pipeline invariant checks ───────────────────────────────────────────────


class TestPipelineInvariants:
    """Every pipeline stage returns consistent invariants."""

    FIXTURES = [
        ("photosynthesis", _photosynthesis_plan(), "diagram"),
        ("octopus", _octopus_plan(), "photograph"),
        ("pomodoro", _pomodoro_plan(), "diagram"),
        ("french_revolution", _french_revolution_plan(), "painting"),
    ]

    def test_segment_count_preserved(self):
        for name, raw, _ in self.FIXTURES:
            canon_result = canonicalize_visual_plan_v2(raw)
            assert canon_result["ok"], f"{name}: canonicalize failed"
            canon = canon_result["canonicalPlan"]
            seq_len = len(canon["visualSequence"])

            router_result = build_visual_sourcing_plan_v2(canon)
            assert router_result["ok"], f"{name}: router failed"
            sp = router_result["sourcingPlan"]

            exec_result = execute_visual_sourcing_plan_v2(
                sp, _config_b_wikimedia_available(), dry_run=True,
            )
            assert exec_result["ok"], f"{name}: executor failed"

            seg_count = len(sp["segments"])
            assert seg_count == seq_len, f"{name}: segment count mismatch"
            summary = exec_result["diagnostics"]["summary"]
            achieved = summary["dryRunAttempts"] + summary["unresolved"] + summary["providerUnavailable"]
            assert achieved == seg_count, (
                f"{name}: executor covered {achieved}/{seg_count} segments"
            )

    def test_router_uses_search_queries_and_generation_prompts(self):
        for name, raw, _ in self.FIXTURES:
            canon_result = canonicalize_visual_plan_v2(raw)
            assert canon_result["ok"], f"{name}: canonicalize failed"
            router_result = build_visual_sourcing_plan_v2(
                canon_result["canonicalPlan"],
            )
            assert router_result["ok"], f"{name}: router failed"
            for seg in router_result["sourcingPlan"]["segments"]:
                assert "searchQueries" in seg
                assert "generationPrompts" in seg
                assert "providerCandidates" in seg
                assert "excludedProviders" in seg
                assert isinstance(seg["searchQueries"], list)
                assert isinstance(seg["generationPrompts"], list)

    def test_executor_input_types_match_strategy(self):
        for name, raw, _ in self.FIXTURES:
            _, _, exec_ = _run_pipeline(
                raw, _config_b_wikimedia_available(),
            )
            for attempt in exec_["dryRunAttempts"]:
                qs = attempt["queryStrategy"]
                sit = attempt["selectedInputType"]
                if qs == "search":
                    assert sit == "searchQueries", (
                        f"{name}: search strategy got {sit}"
                    )
                elif qs == "generate":
                    assert sit == "generationPrompts", (
                        f"{name}: generate strategy got {sit}"
                    )

    def test_generated_input_type_in_config_c(self):
        _, _, exec_ = _run_pipeline(
            _generated_plan(), _config_c_generated_available(),
            request_visuals={"allowGeneratedImages": True},
        )
        for attempt in exec_["dryRunAttempts"]:
            assert attempt["selectedInputType"] == "generationPrompts"
            assert len(attempt["selectedInputs"]) >= 1


# ── V2 stack source-level isolation ──────────────────────────────────────────


RUNTIME_MODULES = frozenset({
    "fetch_images", "shorts_creator.validation.asset", "editorial_asset_contract",
    "generate_script", "shorts_creator.rendering.preparer", "shorts_creator.rendering.renderer", "shorts_creator.pipeline.orchestrator",
})

V2_MODULES = [
    ("visual", PROJECT / "src" / "shorts_creator" / "contracts" / "visual.py"),
    ("router", PROJECT / "src" / "shorts_creator" / "assets" / "router.py"),
    ("executor", PROJECT / "src" / "shorts_creator" / "assets" / "executor.py"),
    ("wikimedia", PROJECT / "src" / "shorts_creator" / "assets" / "providers" / "wikimedia.py"),
]


class TestV2StackSourceIsolation:
    """Verify v2 module source files do not import runtime pipeline modules."""

    def test_v2_modules_no_runtime_imports(self):
        for name, path in V2_MODULES:
            source = path.read_text()
            lines = source.split("\n")
            for lineno, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                for mod in RUNTIME_MODULES:
                    import_word = f"import {mod}"
                    from_word = f"from {mod}"
                    if import_word in stripped or from_word in stripped:
                        raise AssertionError(
                            f"{name}:{lineno}: imports runtime module '{mod}'"
                        )
