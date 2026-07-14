"""Tests for Visual Asset Executor v2 — dry-run and live.

Run: python3 -m pytest tests/test_visual_asset_executor_v2.py -v
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))

from visual_asset_executor_v2 import (
    execute_visual_sourcing_plan_v2,
    _evaluate_provider_availability,
    _dispatch_inputs,
    _build_empty_diagnostics,
    _compute_asset_paths,
    _extension_from_mime,
    _extension_from_url,
    _determine_extension,
    _extract_query_texts,
    _validate_asset_namespace,
    ALLOWED_AVAILABILITY_STATUSES,
    ALLOWED_EXECUTOR_STATUSES,
    LEGACY_V1_FIELDS,
)

# ── Helpers ─────────────────────────────────────────────────────────────────


def _default_provider_config(**overrides) -> dict:
    cfg = {
        "wikimedia_commons": {
            "enabled": True, "implemented": False, "requiresApiKey": False,
        },
        "pexels": {
            "enabled": True, "implemented": False, "requiresApiKey": True,
            "apiKeyPresent": False,
        },
        "pixabay": {
            "enabled": True, "implemented": False, "requiresApiKey": True,
            "apiKeyPresent": False,
        },
        "freeai": {
            "enabled": True, "implemented": False, "requiresApiKey": True,
            "apiKeyPresent": False,
        },
        "pollinations": {
            "enabled": True, "implemented": False, "requiresApiKey": False,
        },
    }
    for provider, settings in overrides.items():
        if provider in cfg:
            cfg[provider].update(settings)
    return cfg


def _mock_candidate(provider="wikimedia_commons", priority=1, queryStrategy="search",
                    candidateStatus="included", availability="available",
                    requiresApiKey=False, supportStrength="weak"):
    return {
        "provider": provider,
        "priority": priority,
        "queryStrategy": queryStrategy,
        "candidateStatus": candidateStatus,
        "availability": availability,
        "requiresApiKey": requiresApiKey,
        "supportStrength": supportStrength,
        "reason": f"{provider} — {supportStrength} support",
        "exclusionReason": None,
        "warnings": [],
    }


def _mock_excluded(provider="pexels", reason="does not support"):
    return {
        "provider": provider,
        "candidateStatus": "excluded",
        "availability": "conditional",
        "exclusionReason": reason,
        "warnings": [],
    }


def _mock_segment(segmentIndex=1, assetPreference="diagram",
                  routingStatus="ROUTABLE_WITH_WARNINGS",
                  providerCandidates=None, searchQueries=None,
                  generationPrompts=None, excludedProviders=None,
                  unsupportedReasons=None):
    return {
        "segmentIndex": segmentIndex,
        "assetPreference": assetPreference,
        "searchQueries": searchQueries or [],
        "generationPrompts": generationPrompts or [],
        "providerCandidates": providerCandidates or [],
        "excludedProviders": excludedProviders or [],
        "routingStatus": routingStatus,
        "warnings": [],
        "unsupportedReasons": unsupportedReasons or [],
    }


def _mock_sourcing_plan(segments=None):
    return {
        "schemaVersion": 1,
        "segments": segments or [],
        "summary": {
            "totalSegments": len(segments or []),
            "routable": 0,
            "routableWithWarnings": len(segments or []),
            "unroutable": 0,
        },
    }


def _collect_legacy_fields(data, path=""):
    found = []
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(k, str):
                canonical = k.lstrip("_")
            else:
                canonical = str(k)
            if canonical in LEGACY_V1_FIELDS or k in LEGACY_V1_FIELDS:
                found.append(f"{path}.{k}" if path else k)
            found.extend(_collect_legacy_fields(v, f"{path}.{k}" if path else k))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            found.extend(_collect_legacy_fields(item, f"{path}[{i}]"))
    return found


# ── Input / output contract ─────────────────────────────────────────────────


class TestInputOutputContract:
    def test_valid_sourcing_plan_returns_ok_true(self):
        plan = _mock_sourcing_plan([
            _mock_segment(
                providerCandidates=[_mock_candidate()],
            ),
        ])
        result = execute_visual_sourcing_plan_v2(
            plan, _default_provider_config(),
        )
        assert result["ok"] is True
        assert result["dryRun"] is True

    def test_non_dict_sourcing_plan_returns_ok_false(self):
        result = execute_visual_sourcing_plan_v2(
            "not a dict", _default_provider_config(),
        )
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_INPUT" in e for e in errors)

    def test_missing_sourcing_plan_keys_returns_ok_false(self):
        plan = {"segments": []}
        result = execute_visual_sourcing_plan_v2(
            plan, _default_provider_config(),
        )
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("MISSING_SOURCING_PLAN_KEY:schemaVersion" in e for e in errors)
        assert any("MISSING_SOURCING_PLAN_KEY:summary" in e for e in errors)

    def test_dry_run_true_is_default(self):
        result = execute_visual_sourcing_plan_v2(
            _mock_sourcing_plan(), _default_provider_config(),
        )
        assert result["dryRun"] is True

    def test_resolved_assets_always_empty_in_dry_run(self):
        result = execute_visual_sourcing_plan_v2(
            _mock_sourcing_plan([
                _mock_segment(
                    providerCandidates=[_mock_candidate()],
                ),
            ]),
            _default_provider_config(),
        )
        assert result["resolvedAssets"] == []

    def test_summary_counts_are_correct(self):
        plan = _mock_sourcing_plan([
            _mock_segment(
                segmentIndex=1,
                providerCandidates=[_mock_candidate(provider="wikimedia_commons")],
            ),
            _mock_segment(
                segmentIndex=2,
                routingStatus="UNROUTABLE",
            ),
            _mock_segment(
                segmentIndex=3,
                providerCandidates=[],
            ),
        ])
        result = execute_visual_sourcing_plan_v2(
            plan,
            _default_provider_config(
                wikimedia_commons={"implemented": True},
            ),
        )
        summary = result["diagnostics"]["summary"]
        assert summary["totalSegments"] == 3
        assert summary["dryRunAttempts"] == 1
        assert summary["resolved"] == 0
        assert summary["unresolved"] == 1
        assert summary["providerUnavailable"] == 1

    def test_job_dir_stored_in_diagnostics(self):
        result = execute_visual_sourcing_plan_v2(
            _mock_sourcing_plan(), _default_provider_config(),
            job_dir="/tmp/test-job",
        )
        assert result["diagnostics"]["jobDir"] == "/tmp/test-job"

    def test_request_visuals_provided_tracked(self):
        result = execute_visual_sourcing_plan_v2(
            _mock_sourcing_plan(), _default_provider_config(),
            request_visuals={"allowGeneratedImages": True},
        )
        assert result["diagnostics"]["requestVisualsProvided"] is True

    def test_request_visuals_not_provided_false(self):
        result = execute_visual_sourcing_plan_v2(
            _mock_sourcing_plan(), _default_provider_config(),
        )
        assert result["diagnostics"]["requestVisualsProvided"] is False


# ── Provider availability (unit-level) ──────────────────────────────────────


class TestProviderAvailabilityUnit:
    def test_enabled_false_is_disabled_by_request(self):
        avail = _evaluate_provider_availability("pexels", {
            "pexels": {"enabled": False, "implemented": True,
                       "requiresApiKey": True, "apiKeyPresent": True},
        })
        assert avail == "DISABLED_BY_REQUEST"

    def test_implemented_false_is_not_implemented(self):
        avail = _evaluate_provider_availability("pexels", {
            "pexels": {"enabled": True, "implemented": False,
                       "requiresApiKey": True, "apiKeyPresent": True},
        })
        assert avail == "NOT_IMPLEMENTED"

    def test_requires_key_true_key_missing_is_missing_api_key(self):
        avail = _evaluate_provider_availability("pexels", {
            "pexels": {"enabled": True, "implemented": True,
                       "requiresApiKey": True, "apiKeyPresent": False},
        })
        assert avail == "MISSING_API_KEY"

    def test_missing_provider_is_unknown_provider(self):
        avail = _evaluate_provider_availability("nonexistent", {
            "pexels": {"enabled": True, "implemented": True,
                       "requiresApiKey": False},
        })
        assert avail == "UNKNOWN_PROVIDER"

    def test_implemented_true_no_key_needed_is_available(self):
        avail = _evaluate_provider_availability("wikimedia_commons", {
            "wikimedia_commons": {"enabled": True, "implemented": True,
                                  "requiresApiKey": False},
        })
        assert avail == "AVAILABLE"

    def test_implemented_true_key_present_is_available(self):
        avail = _evaluate_provider_availability("pexels", {
            "pexels": {"enabled": True, "implemented": True,
                       "requiresApiKey": True, "apiKeyPresent": True},
        })
        assert avail == "AVAILABLE"

    def test_non_dict_config_is_unknown_provider(self):
        avail = _evaluate_provider_availability("pexels", "not a dict")
        assert avail == "UNKNOWN_PROVIDER"


# ── SECRET_FIELD_IGNORED ────────────────────────────────────────────────────


class TestSecretFieldIgnored:
    def test_api_key_field_ignored_with_warning(self):
        cfg = {
            "pexels": {
                "enabled": True, "implemented": False,
                "requiresApiKey": True, "apiKeyPresent": False,
                "api_key": "some-real-key",
            },
        }
        result = execute_visual_sourcing_plan_v2(
            _mock_sourcing_plan([_mock_segment(
                providerCandidates=[_mock_candidate(provider="pexels")],
            )]),
            cfg,
        )
        warnings = [w["code"] for w in result["diagnostics"]["warnings"]]
        assert any("SECRET_FIELD_IGNORED" in w for w in warnings)

    def test_camelcase_api_key_ignored(self):
        cfg = {
            "pexels": {
                "enabled": True, "implemented": False,
                "requiresApiKey": True, "apiKeyPresent": False,
                "apiKey": "some-key",
            },
        }
        result = execute_visual_sourcing_plan_v2(
            _mock_sourcing_plan(), cfg,
        )
        warnings = [w["code"] for w in result["diagnostics"]["warnings"]]
        assert any("SECRET_FIELD_IGNORED" in w for w in warnings)

    def test_token_field_ignored(self):
        cfg = {
            "pexels": {
                "enabled": True, "implemented": False,
                "requiresApiKey": True, "apiKeyPresent": False,
                "token": "some-token",
            },
        }
        result = execute_visual_sourcing_plan_v2(
            _mock_sourcing_plan(), cfg,
        )
        warnings = [w["code"] for w in result["diagnostics"]["warnings"]]
        assert any("SECRET_FIELD_IGNORED" in w for w in warnings)

    def test_secret_field_ignored(self):
        cfg = {
            "pexels": {
                "enabled": True, "implemented": False,
                "requiresApiKey": True, "apiKeyPresent": False,
                "secret": "some-secret",
            },
        }
        result = execute_visual_sourcing_plan_v2(
            _mock_sourcing_plan(), cfg,
        )
        warnings = [w["code"] for w in result["diagnostics"]["warnings"]]
        assert any("SECRET_FIELD_IGNORED" in w for w in warnings)


# ── Candidate priority ──────────────────────────────────────────────────────


class TestCandidatePriority:
    def _config(self):
        return {
            "wikimedia_commons": {
                "enabled": True, "implemented": True, "requiresApiKey": False,
            },
            "pexels": {
                "enabled": True, "implemented": True,
                "requiresApiKey": True, "apiKeyPresent": True,
            },
        }

    def test_respects_candidate_priority_order(self):
        plan = _mock_sourcing_plan([_mock_segment(
            providerCandidates=[
                _mock_candidate(provider="pexels", priority=1),
                _mock_candidate(provider="wikimedia_commons", priority=2),
            ],
        )])
        result = execute_visual_sourcing_plan_v2(plan, self._config())
        attempt = result["dryRunAttempts"][0]
        assert attempt["selectedProvider"] == "pexels"

    def test_skips_unavailable_selects_first_available(self):
        plan = _mock_sourcing_plan([_mock_segment(
            providerCandidates=[
                _mock_candidate(provider="pexels", priority=1),
                _mock_candidate(provider="wikimedia_commons", priority=2),
            ],
        )])
        result = execute_visual_sourcing_plan_v2(
            plan,
            _default_provider_config(
                wikimedia_commons={"implemented": True},
            ),
        )
        attempt = result["dryRunAttempts"][0]
        assert attempt["selectedProvider"] == "wikimedia_commons"

    def test_does_not_attempt_excluded_providers(self):
        plan = _mock_sourcing_plan([_mock_segment(
            providerCandidates=[
                _mock_candidate(provider="pexels", priority=1,
                                candidateStatus="excluded"),
                _mock_candidate(provider="wikimedia_commons", priority=2),
            ],
            excludedProviders=[
                _mock_excluded(provider="pexels",
                               reason="does not support in v2 routing matrix"),
            ],
        )])
        result = execute_visual_sourcing_plan_v2(
            plan,
            _default_provider_config(
                wikimedia_commons={"implemented": True},
            ),
        )
        attempt = result["dryRunAttempts"][0]
        assert attempt["selectedProvider"] == "wikimedia_commons"


# ── Query/prompt separation ─────────────────────────────────────────────────


class TestQueryPromptSeparation:
    def _config_available(self):
        return {
            "wikimedia_commons": {
                "enabled": True, "implemented": True, "requiresApiKey": False,
            },
            "freeai": {
                "enabled": True, "implemented": True,
                "requiresApiKey": True, "apiKeyPresent": True,
            },
        }

    def test_search_provider_receives_search_queries(self):
        plan = _mock_sourcing_plan([_mock_segment(
            assetPreference="diagram",
            searchQueries=[
                {"text": "photosynthesis diagram", "source": "segment.searchQuery"},
            ],
            generationPrompts=[
                {"text": "generate this diagram", "source": "scene.imageGenerationPrompt"},
            ],
            providerCandidates=[
                _mock_candidate(provider="wikimedia_commons", priority=1,
                                queryStrategy="search"),
            ],
        )])
        result = execute_visual_sourcing_plan_v2(plan, self._config_available())
        attempt = result["dryRunAttempts"][0]
        assert attempt["selectedInputType"] == "searchQueries"
        texts = [q.get("text", q) if isinstance(q, dict) else q
                 for q in attempt["selectedInputs"]]
        assert "photosynthesis diagram" in texts

    def test_generated_provider_receives_generation_prompts(self):
        plan = _mock_sourcing_plan([_mock_segment(
            assetPreference="diagram",
            searchQueries=[
                {"text": "photosynthesis diagram", "source": "segment.searchQuery"},
            ],
            generationPrompts=[
                {"text": "generate this diagram", "source": "scene.imageGenerationPrompt"},
            ],
            providerCandidates=[
                _mock_candidate(provider="freeai", priority=1,
                                queryStrategy="generate"),
            ],
        )])
        result = execute_visual_sourcing_plan_v2(plan, self._config_available())
        attempt = result["dryRunAttempts"][0]
        assert attempt["selectedInputType"] == "generationPrompts"
        texts = [q.get("text", q) if isinstance(q, dict) else q
                 for q in attempt["selectedInputs"]]
        assert "generate this diagram" in texts

    def test_generation_prompts_not_used_for_search_providers(self):
        plan = _mock_sourcing_plan([_mock_segment(
            assetPreference="diagram",
            searchQueries=[
                {"text": "photosynthesis", "source": "segment.searchQuery"},
            ],
            generationPrompts=[
                {"text": "generate me", "source": "scene.imageGenerationPrompt"},
            ],
            providerCandidates=[
                _mock_candidate(provider="wikimedia_commons", priority=1,
                                queryStrategy="search"),
            ],
        )])
        result = execute_visual_sourcing_plan_v2(plan, self._config_available())
        attempt = result["dryRunAttempts"][0]
        assert attempt["selectedInputType"] == "searchQueries"
        texts = [q.get("text", q) if isinstance(q, dict) else q
                 for q in attempt["selectedInputs"]]
        assert "generate me" not in texts

    def test_search_queries_not_used_as_input_when_gen_prompts_exist(self):
        plan = _mock_sourcing_plan([_mock_segment(
            assetPreference="generated",
            searchQueries=[
                {"text": "a search query", "source": "segment.searchQuery"},
            ],
            generationPrompts=[
                {"text": "a generation prompt", "source": "scene.imageGenerationPrompt"},
            ],
            providerCandidates=[
                _mock_candidate(provider="freeai", priority=1,
                                queryStrategy="generate"),
            ],
        )])
        result = execute_visual_sourcing_plan_v2(plan, self._config_available())
        attempt = result["dryRunAttempts"][0]
        assert attempt["selectedInputType"] == "generationPrompts"


# ── Segment behavior ────────────────────────────────────────────────────────


class TestSegmentBehavior:
    def _available_wikimedia_config(self):
        return {"wikimedia_commons": {
            "enabled": True, "implemented": True, "requiresApiKey": False,
        }}

    def test_routable_with_available_provider_gets_skipped_dry_run(self):
        plan = _mock_sourcing_plan([_mock_segment(
            routingStatus="ROUTABLE_WITH_WARNINGS",
            providerCandidates=[
                _mock_candidate(provider="wikimedia_commons", priority=1),
            ],
        )])
        result = execute_visual_sourcing_plan_v2(
            plan,
            {"wikimedia_commons": {
                "enabled": True, "implemented": True, "requiresApiKey": False,
            }},
        )
        assert len(result["dryRunAttempts"]) == 1
        assert result["dryRunAttempts"][0]["status"] == "SKIPPED_DRY_RUN"

    def test_all_providers_unavailable_gets_provider_unavailable(self):
        plan = _mock_sourcing_plan([_mock_segment(
            routingStatus="ROUTABLE_WITH_WARNINGS",
            providerCandidates=[
                _mock_candidate(provider="pexels", priority=1),
                _mock_candidate(provider="pixabay", priority=2),
            ],
        )])
        result = execute_visual_sourcing_plan_v2(
            plan, _default_provider_config(),
        )
        assert len(result["dryRunAttempts"]) == 0
        assert len(result["unresolvedSegments"]) == 1
        assert result["unresolvedSegments"][0]["status"] == "PROVIDER_UNAVAILABLE"

    def test_unroutable_segment_gets_unresolved(self):
        plan = _mock_sourcing_plan([_mock_segment(
            routingStatus="UNROUTABLE",
            unsupportedReasons=["assetPreference 'unknown' not in routing matrix"],
        )])
        result = execute_visual_sourcing_plan_v2(
            plan, _default_provider_config(),
        )
        assert len(result["unresolvedSegments"]) == 1
        assert result["unresolvedSegments"][0]["status"] == "UNRESOLVED"
        assert result["unresolvedSegments"][0]["reason"] == (
            "Router marked segment as UNROUTABLE"
        )


# ── Live mode guard ─────────────────────────────────────────────────────────


class TestLiveModeGuard:
    def test_dry_run_false_without_job_dir_returns_error(self):
        result = execute_visual_sourcing_plan_v2(
            _mock_sourcing_plan(), _default_provider_config(),
            dry_run=False,
        )
        assert result["ok"] is False
        assert result["dryRun"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("JOB_DIR_REQUIRED_FOR_LIVE_EXECUTION" in e for e in errors)


# ── Legacy v1 field regression ──────────────────────────────────────────────


class TestNoLegacyFields:
    def test_output_contains_no_legacy_v1_fields(self):
        plan = _mock_sourcing_plan([
            _mock_segment(
                segmentIndex=1,
                assetPreference="diagram",
                routingStatus="ROUTABLE_WITH_WARNINGS",
                searchQueries=[
                    {"text": "photosynthesis diagram", "source": "segment.searchQuery"},
                ],
                providerCandidates=[
                    _mock_candidate(provider="wikimedia_commons", priority=1),
                ],
            ),
            _mock_segment(
                segmentIndex=2,
                routingStatus="UNROUTABLE",
                unsupportedReasons=["no matrix entry"],
            ),
        ])
        result = execute_visual_sourcing_plan_v2(
            plan, _default_provider_config(),
        )
        found = _collect_legacy_fields(result)
        assert not found, f"Legacy v1 fields found in output: {found}"


# ── Complete provider availability map ──────────────────────────────────────


class TestProviderAvailabilityMap:
    def test_diagnostics_has_provider_availability_map(self):
        result = execute_visual_sourcing_plan_v2(
            _mock_sourcing_plan(), _default_provider_config(),
        )
        avail = result["diagnostics"]["providerAvailability"]
        assert isinstance(avail, dict)
        assert "wikimedia_commons" in avail
        assert "pexels" in avail
        assert avail["wikimedia_commons"] == "NOT_IMPLEMENTED"
        assert avail["pexels"] == "NOT_IMPLEMENTED"

    def test_provider_from_candidates_not_in_config_added_to_map(self):
        plan = _mock_sourcing_plan([_mock_segment(
            providerCandidates=[
                _mock_candidate(provider="wikimedia_commons", priority=1),
            ],
        )])
        cfg = {}  # empty config — no providers configured
        result = execute_visual_sourcing_plan_v2(plan, cfg)
        avail = result["diagnostics"]["providerAvailability"]
        assert "wikimedia_commons" in avail
        assert avail["wikimedia_commons"] == "UNKNOWN_PROVIDER"


# ── Multiple segments with mixed statuses ────────────────────────────────────


class TestMultipleSegments:
    def test_mixed_segments_produce_correct_outputs(self):
        plan = _mock_sourcing_plan([
            _mock_segment(
                segmentIndex=1, assetPreference="photograph",
                routingStatus="ROUTABLE_WITH_WARNINGS",
                searchQueries=[{"text": "octopus photo", "source": "segment.searchQuery"}],
                providerCandidates=[
                    _mock_candidate(provider="pexels", priority=1),
                    _mock_candidate(provider="wikimedia_commons", priority=2),
                ],
            ),
            _mock_segment(
                segmentIndex=2, assetPreference="generated",
                routingStatus="UNROUTABLE",
                unsupportedReasons=["generated blocked by gates"],
            ),
            _mock_segment(
                segmentIndex=3, assetPreference="diagram",
                routingStatus="ROUTABLE_WITH_WARNINGS",
                providerCandidates=[
                    _mock_candidate(provider="pexels", priority=1),
                ],
            ),
        ])
        result = execute_visual_sourcing_plan_v2(
            plan,
            _default_provider_config(
                wikimedia_commons={"implemented": True},
            ),
        )
        assert result["ok"] is True

        attempts = result["dryRunAttempts"]
        unresolved = result["unresolvedSegments"]

        assert len(attempts) == 1
        assert attempts[0]["segmentIndex"] == 1

        assert len(unresolved) == 2
        statuses = {u["segmentIndex"]: u["status"] for u in unresolved}
        assert statuses[2] == "UNRESOLVED"
        assert statuses[3] == "PROVIDER_UNAVAILABLE"

        summary = result["diagnostics"]["summary"]
        assert summary["totalSegments"] == 3
        assert summary["dryRunAttempts"] == 1
        assert summary["unresolved"] == 1
        assert summary["providerUnavailable"] == 1
        assert summary["resolved"] == 0


# ── Invalid segment shapes ──────────────────────────────────────────────────


class TestInvalidSegmentShapes:
    def test_non_dict_segment_produces_warning(self):
        plan = _mock_sourcing_plan(["not_a_dict"])
        result = execute_visual_sourcing_plan_v2(
            plan, _default_provider_config(),
        )
        warnings = [w["code"] for w in result["diagnostics"]["warnings"]]
        assert any("INVALID_SEGMENT" in w for w in warnings)

    def test_segment_missing_keys_produces_errors(self):
        plan = _mock_sourcing_plan([
            {"segmentIndex": 1},
        ])
        result = execute_visual_sourcing_plan_v2(
            plan, _default_provider_config(),
        )
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("MISSING_SEGMENT_KEY" in e for e in errors)


# ── Dispatch inputs unit ────────────────────────────────────────────────────


class TestDispatchInputsUnit:
    def test_search_strategy_returns_search_queries(self):
        candidate = {"queryStrategy": "search"}
        segment = {
            "searchQueries": [{"text": "q", "source": "s"}],
            "generationPrompts": [{"text": "p", "source": "s"}],
        }
        input_type, inputs = _dispatch_inputs(candidate, segment)
        assert input_type == "searchQueries"
        assert len(inputs) == 1
        assert inputs[0]["text"] == "q"

    def test_generate_strategy_returns_generation_prompts(self):
        candidate = {"queryStrategy": "generate"}
        segment = {
            "searchQueries": [{"text": "q", "source": "s"}],
            "generationPrompts": [{"text": "p", "source": "s"}],
        }
        input_type, inputs = _dispatch_inputs(candidate, segment)
        assert input_type == "generationPrompts"
        assert len(inputs) == 1
        assert inputs[0]["text"] == "p"

    def test_default_strategy_is_search(self):
        candidate = {}
        segment = {"searchQueries": [{"text": "q", "source": "s"}]}
        input_type, inputs = _dispatch_inputs(candidate, segment)
        assert input_type == "searchQueries"

    def test_generate_strategy_handles_missing_generation_prompts(self):
        candidate = {"queryStrategy": "generate"}
        segment = {}
        input_type, inputs = _dispatch_inputs(candidate, segment)
        assert input_type == "generationPrompts"
        assert inputs == []


# ── Empty diagnostics builder ───────────────────────────────────────────────


class TestDiagnosticsBuilder:
    def test_empty_diagnostics_structure(self):
        diag = _build_empty_diagnostics()
        assert "errors" in diag
        assert "warnings" in diag
        assert "providerAvailability" in diag
        assert "jobDir" in diag
        assert "requestVisualsProvided" in diag
        assert "summary" in diag
        summary = diag["summary"]
        assert         summary["totalSegments"] == 0
        assert summary["dryRunAttempts"] == 0
        assert summary["resolved"] == 0
        assert summary["unresolved"] == 0
        assert summary["providerUnavailable"] == 0
        assert summary["noResults"] == 0
        assert summary["downloadFailed"] == 0
        assert summary["providerError"] == 0

    def test_empty_diagnostics_job_dir(self):
        diag = _build_empty_diagnostics(job_dir="/some/dir")
        assert diag["jobDir"] == "/some/dir"

    def test_empty_diagnostics_request_visuals(self):
        diag = _build_empty_diagnostics(request_visuals_provided=True)
        assert diag["requestVisualsProvided"] is True


# ── Extension and path helpers ───────────────────────────────────────────────


class TestExtensionHelpers:
    def test_mime_to_ext_jpeg(self):
        assert _extension_from_mime("image/jpeg") == ".jpg"

    def test_mime_to_ext_png(self):
        assert _extension_from_mime("image/png") == ".png"

    def test_mime_to_ext_webp(self):
        assert _extension_from_mime("image/webp") == ".webp"

    def test_mime_to_ext_gif(self):
        assert _extension_from_mime("image/gif") == ".gif"

    def test_mime_to_ext_unknown(self):
        assert _extension_from_mime("image/bmp") == ".bin"

    def test_url_extension(self):
        assert _extension_from_url("https://example.com/image.png") == ".png"

    def test_url_extension_jpg(self):
        assert _extension_from_url("https://example.com/photo.jpg?w=200") == ".jpg"

    def test_url_no_extension(self):
        assert _extension_from_url("https://example.com/image") == ".bin"

    def test_determine_extension_from_mime(self):
        ext = _determine_extension({"mimeType": "image/jpeg", "fileUrl": ""})
        assert ext == ".jpg"

    def test_determine_extension_from_url_fallback(self):
        ext = _determine_extension({"mimeType": "image/bmp", "fileUrl": "https://x.com/img.png"})
        assert ext == ".png"

    def test_path_computation(self):
        rel, abs_path = _compute_asset_paths(
            "/tmp/job", 1,
            {"mimeType": "image/jpeg", "fileUrl": ""},
        )
        assert rel == "assets/seg_001.jpg"
        assert str(abs_path) == "/tmp/job/assets/seg_001.jpg"

    def test_path_computation_multi_digit(self):
        rel, abs_path = _compute_asset_paths(
            "/tmp/job", 42,
            {"mimeType": "image/png", "fileUrl": ""},
        )
        assert rel == "assets/seg_042.png"

    def test_extract_query_texts_strings(self):
        texts = _extract_query_texts(["hello", "world"])
        assert texts == ["hello", "world"]

    def test_extract_query_texts_dicts(self):
        texts = _extract_query_texts([
            {"text": "hello"},
            {"text": "world"},
        ])
        assert texts == ["hello", "world"]

    def test_extract_query_texts_mixed(self):
        texts = _extract_query_texts([
            "plain",
            {"text": "from dict"},
            "",
            {"other": "ignored"},
        ])
        assert texts == ["plain", "from dict"]


# ── Live mode: Wikimedia ─────────────────────────────────────────────────────


class TestLiveModeWikimedia:
    def _live_wikimedia_config(self):
        return {
            "wikimedia_commons": {
                "enabled": True, "implemented": True,
                "requiresApiKey": False, "live": True,
            },
        }

    def _mock_candidate(self):
        return {
            "provider": "wikimedia_commons",
            "title": "Test Image",
            "sourceUrl": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Test.jpg",
            "fileUrl": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Test.jpg",
            "thumbnailUrl": "",
            "license": "Public Domain",
            "author": "Test Author",
            "width": 1200,
            "height": 800,
            "mimeType": "image/jpeg",
            "queryUsed": "test query",
            "score": 0.0,
        }

    def _mock_download_ok(self):
        return {"ok": True, "path": "/tmp/job/assets/seg_001.jpg",
                "size": 50000, "mimeType": "image/jpeg", "error": None}

    def _mock_download_fail(self):
        return {"ok": False, "path": "/tmp/job/assets/seg_001.jpg",
                "size": 0, "mimeType": None, "error": "download failed"}

    def _mock_segment_wikimedia(self):
        return {
            "segmentIndex": 1,
            "assetPreference": "painting",
            "searchQueries": [{"text": "test query", "source": "segment.searchQuery"}],
            "generationPrompts": [],
            "providerCandidates": [
                {
                    "provider": "wikimedia_commons",
                    "priority": 1,
                    "queryStrategy": "search",
                    "candidateStatus": "included",
                    "availability": "available",
                    "requiresApiKey": False,
                    "supportStrength": "medium",
                    "reason": "painting — medium support",
                    "exclusionReason": None,
                    "warnings": [],
                },
            ],
            "excludedProviders": [],
            "routingStatus": "ROUTABLE_WITH_WARNINGS",
            "warnings": [],
            "unsupportedReasons": [],
        }

    def _mock_sourcing_plan(self, segments):
        return {
            "schemaVersion": 1,
            "segments": segments,
            "summary": {
                "totalSegments": len(segments),
                "routable": 0,
                "routableWithWarnings": len(segments),
                "unroutable": 0,
            },
        }

    # ── Positive tests ───────────────────────────────────────────────────

    def test_live_wikimedia_resolves(self, tmp_path):
        plan = self._mock_sourcing_plan([self._mock_segment_wikimedia()])
        with patch(
            "visual_provider_wikimedia_v2.resolve_wikimedia_candidate_v2",
            return_value=self._mock_candidate(),
        ), patch(
            "visual_provider_wikimedia_v2.download_wikimedia_asset_v2",
            return_value=self._mock_download_ok(),
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
            )
        assert result["ok"] is True
        assert result["dryRun"] is False
        assert len(result["resolvedAssets"]) == 1
        ra = result["resolvedAssets"][0]
        assert ra["status"] == "RESOLVED"
        assert ra["provider"] == "wikimedia_commons"
        assert ra["segmentIndex"] == 1
        assert ra["assetPreference"] == "painting"
        assert ra["assetPath"] == "assets/seg_001.jpg"
        assert ra["fileSize"] == 50000
        assert ra["license"] == "Public Domain"
        assert ra["author"] == "Test Author"
        assert ra["width"] == 1200
        assert ra["height"] == 800
        assert ra["searchQueryUsed"] == "test query"
        assert ra["generationPromptUsed"] is None
        assert len(result["unresolvedSegments"]) == 0
        assert len(result["dryRunAttempts"]) == 0

        summary = result["diagnostics"]["summary"]
        assert summary["resolved"] == 1
        assert summary["totalSegments"] == 1
        assert summary["dryRunAttempts"] == 0

    def test_live_wikimedia_asset_path_under_job_dir(self, tmp_path):
        plan = self._mock_sourcing_plan([self._mock_segment_wikimedia()])
        with patch(
            "visual_provider_wikimedia_v2.resolve_wikimedia_candidate_v2",
            return_value=self._mock_candidate(),
        ), patch(
            "visual_provider_wikimedia_v2.download_wikimedia_asset_v2",
            return_value=self._mock_download_ok(),
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
            )
        ra = result["resolvedAssets"][0]
        expected = f"assets/seg_001.jpg"
        assert ra["assetPath"] == expected

    def test_live_wikimedia_no_results(self, tmp_path):
        plan = self._mock_sourcing_plan([self._mock_segment_wikimedia()])
        with patch(
            "visual_provider_wikimedia_v2.resolve_wikimedia_candidate_v2",
            return_value=None,
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
            )
        assert result["ok"] is True
        assert len(result["resolvedAssets"]) == 0
        assert len(result["unresolvedSegments"]) == 1
        us = result["unresolvedSegments"][0]
        assert us["status"] == "NO_RESULTS"
        assert us["provider"] == "wikimedia_commons"
        assert "no candidate" in us["reason"]
        assert "searchQueriesTried" in us
        assert "test query" in us["searchQueriesTried"]

        summary = result["diagnostics"]["summary"]
        assert summary["noResults"] == 1

    def test_live_wikimedia_download_failed(self, tmp_path):
        plan = self._mock_sourcing_plan([self._mock_segment_wikimedia()])
        call_count = [0]

        def mock_resolve(queries, user_agent=None, excluded_source_urls=None,
                         excluded_file_urls=None, cache=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return self._mock_candidate()
            return None

        with patch(
            "visual_provider_wikimedia_v2.resolve_wikimedia_candidate_v2",
            side_effect=mock_resolve,
        ), patch(
            "visual_provider_wikimedia_v2.download_wikimedia_asset_v2",
            return_value=self._mock_download_fail(),
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
            )
        assert len(result["resolvedAssets"]) == 0
        assert len(result["unresolvedSegments"]) == 1
        us = result["unresolvedSegments"][0]
        assert us["status"] == "DOWNLOAD_FAILED"
        assert us["downloadAttempts"] == 1
        assert len(us["downloadErrors"]) == 1
        assert us["downloadErrors"][0]["error"] == "download failed"

        summary = result["diagnostics"]["summary"]
        assert summary["downloadFailed"] == 1

    def test_live_wikimedia_provider_error(self, tmp_path):
        plan = self._mock_sourcing_plan([self._mock_segment_wikimedia()])
        with patch(
            "visual_provider_wikimedia_v2.resolve_wikimedia_candidate_v2",
            side_effect=RuntimeError("connection timeout"),
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
            )
        assert len(result["resolvedAssets"]) == 0
        assert len(result["unresolvedSegments"]) == 1
        us = result["unresolvedSegments"][0]
        assert us["status"] == "PROVIDER_ERROR"
        assert "connection timeout" in us["reason"]

        summary = result["diagnostics"]["summary"]
        assert summary["providerError"] == 1

    # ── Non-Wikimedia providers in live mode ─────────────────────────────

    def test_non_wikimedia_provider_unavailable_live(self, tmp_path):
        plan = self._mock_sourcing_plan([{
            "segmentIndex": 1,
            "assetPreference": "photograph",
            "searchQueries": [{"text": "test", "source": "s"}],
            "generationPrompts": [],
            "providerCandidates": [
                {
                    "provider": "pexels",
                    "priority": 1,
                    "queryStrategy": "search",
                    "candidateStatus": "included",
                    "availability": "conditional",
                    "requiresApiKey": True,
                    "supportStrength": "strong",
                    "reason": "photograph — strong support",
                    "exclusionReason": None,
                    "warnings": [],
                },
            ],
            "excludedProviders": [],
            "routingStatus": "ROUTABLE",
            "warnings": [],
            "unsupportedReasons": [],
        }])
        pexels_config = {
            "wikimedia_commons": {
                "enabled": True, "implemented": False, "requiresApiKey": False,
            },
            "pexels": {
                "enabled": True, "implemented": True,
                "requiresApiKey": True, "apiKeyPresent": True,
                "live": False,
            },
        }
        result = execute_visual_sourcing_plan_v2(
            plan, pexels_config,
            dry_run=False, job_dir=str(tmp_path),
        )
        assert len(result["resolvedAssets"]) == 0
        assert len(result["unresolvedSegments"]) == 1
        us = result["unresolvedSegments"][0]
        assert us["status"] == "PROVIDER_UNAVAILABLE"
        assert "not implemented" in us["reason"].lower()

    # ── job_dir validation ───────────────────────────────────────────────

    def test_dry_run_false_no_job_dir_returns_error(self):
        plan = self._mock_sourcing_plan([self._mock_segment_wikimedia()])
        result = execute_visual_sourcing_plan_v2(
            plan, self._live_wikimedia_config(),
            dry_run=False, job_dir=None,
        )
        assert result["ok"] is False
        assert result["dryRun"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("JOB_DIR_REQUIRED_FOR_LIVE_EXECUTION" in e for e in errors)

    # ── dry_run=True behavior preserved ──────────────────────────────────

    def test_dry_run_true_still_works(self):
        plan = self._mock_sourcing_plan([self._mock_segment_wikimedia()])
        result = execute_visual_sourcing_plan_v2(
            plan, self._live_wikimedia_config(),
            dry_run=True,
        )
        assert result["ok"] is True
        assert result["dryRun"] is True
        assert result["resolvedAssets"] == []
        assert len(result["dryRunAttempts"]) == 1
        assert result["dryRunAttempts"][0]["status"] == "SKIPPED_DRY_RUN"

    # ── Legacy field regression ──────────────────────────────────────────

    def test_no_legacy_fields_in_live_output(self, tmp_path):
        plan = self._mock_sourcing_plan([self._mock_segment_wikimedia()])
        with patch(
            "visual_provider_wikimedia_v2.resolve_wikimedia_candidate_v2",
            return_value=self._mock_candidate(),
        ), patch(
            "visual_provider_wikimedia_v2.download_wikimedia_asset_v2",
            return_value=self._mock_download_ok(),
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
            )
        found = _collect_legacy_fields(result)
        assert not found, f"Legacy v1 fields found in live output: {found}"

    # ── Wikimedia not marked live ────────────────────────────────────────

    def test_wikimedia_not_live_returns_unavailable(self, tmp_path):
        plan = self._mock_sourcing_plan([self._mock_segment_wikimedia()])
        config_no_live = {
            "wikimedia_commons": {
                "enabled": True, "implemented": True,
                "requiresApiKey": False, "live": False,
            },
        }
        result = execute_visual_sourcing_plan_v2(
            plan, config_no_live,
            dry_run=False, job_dir=str(tmp_path),
        )
        assert len(result["resolvedAssets"]) == 0
        assert len(result["unresolvedSegments"]) == 1
        us = result["unresolvedSegments"][0]
        assert us["status"] == "PROVIDER_UNAVAILABLE"
        assert "not marked live" in us["reason"].lower()


# ── Namespace validation ────────────────────────────────────────────────────


class TestNamespaceValidation:
    def test_valid_simple_namespace(self):
        assert _validate_asset_namespace("scene_001") is None

    def test_valid_alphanumeric(self):
        assert _validate_asset_namespace("abc123") is None

    def test_valid_hyphen(self):
        assert _validate_asset_namespace("my-namespace") is None

    def test_reject_empty(self):
        assert _validate_asset_namespace("") is not None

    def test_reject_slash(self):
        assert _validate_asset_namespace("scene/001") is not None

    def test_reject_backslash(self):
        assert _validate_asset_namespace("scene\\001") is not None

    def test_reject_dotdot(self):
        assert _validate_asset_namespace("../evil") is not None

    def test_reject_spaces(self):
        assert _validate_asset_namespace("scene 001") is not None

    def test_reject_absolute_path(self):
        assert _validate_asset_namespace("/etc/passwd") is not None

    def test_reject_non_string(self):
        assert _validate_asset_namespace(123) is not None


# ── Namespace in executor public API ─────────────────────────────────────────


class TestNamespaceInExecutor:
    def _live_wikimedia_config(self):
        return {
            "wikimedia_commons": {
                "enabled": True, "implemented": True,
                "requiresApiKey": False, "live": True,
            },
        }

    def _mock_candidate(self):
        return {
            "provider": "wikimedia_commons",
            "title": "Test Image",
            "sourceUrl": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Test.jpg",
            "fileUrl": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Test.jpg",
            "thumbnailUrl": "",
            "license": "Public Domain",
            "author": "Test Author",
            "width": 1200,
            "height": 900,
            "mimeType": "image/jpeg",
            "queryUsed": "test query",
            "score": 0.0,
        }

    def _mock_download_ok(self):
        return {"ok": True, "path": "/tmp/job/assets/seg_001.jpg",
                "size": 50000, "mimeType": "image/jpeg", "error": None}

    def _mock_segment(self):
        return {
            "segmentIndex": 1,
            "assetPreference": "photograph",
            "searchQueries": [{"text": "test", "source": "s"}],
            "generationPrompts": [],
            "providerCandidates": [
                {
                    "provider": "wikimedia_commons",
                    "priority": 1,
                    "queryStrategy": "search",
                    "candidateStatus": "included",
                    "availability": "available",
                    "requiresApiKey": False,
                    "supportStrength": "medium",
                    "reason": "test",
                    "warnings": [],
                },
            ],
            "excludedProviders": [],
            "routingStatus": "ROUTABLE_WITH_WARNINGS",
            "warnings": [],
            "unsupportedReasons": [],
        }

    def _mock_sourcing_plan(self, segments):
        return {
            "schemaVersion": 1,
            "segments": segments,
            "summary": {
                "totalSegments": len(segments),
                "routable": 0,
                "routableWithWarnings": len(segments),
                "unroutable": 0,
            },
        }

    def test_without_namespace_default_path(self, tmp_path):
        plan = self._mock_sourcing_plan([self._mock_segment()])
        with patch(
            "visual_provider_wikimedia_v2.resolve_wikimedia_candidate_v2",
            return_value=self._mock_candidate(),
        ), patch(
            "visual_provider_wikimedia_v2.download_wikimedia_asset_v2",
            return_value=self._mock_download_ok(),
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
            )
        ra = result["resolvedAssets"][0]
        assert ra["assetPath"] == "assets/seg_001.jpg"

    def test_namespace_scene_001(self, tmp_path):
        plan = self._mock_sourcing_plan([self._mock_segment()])
        with patch(
            "visual_provider_wikimedia_v2.resolve_wikimedia_candidate_v2",
            return_value=self._mock_candidate(),
        ), patch(
            "visual_provider_wikimedia_v2.download_wikimedia_asset_v2",
            return_value=self._mock_download_ok(),
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
                asset_namespace="scene_001",
            )
        ra = result["resolvedAssets"][0]
        assert ra["assetPath"] == "assets/scene_001_seg_001.jpg"

    def test_namespace_scene_002(self, tmp_path):
        plan = self._mock_sourcing_plan([self._mock_segment()])
        with patch(
            "visual_provider_wikimedia_v2.resolve_wikimedia_candidate_v2",
            return_value=self._mock_candidate(),
        ), patch(
            "visual_provider_wikimedia_v2.download_wikimedia_asset_v2",
            return_value=self._mock_download_ok(),
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
                asset_namespace="scene_002",
            )
        ra = result["resolvedAssets"][0]
        assert ra["assetPath"] == "assets/scene_002_seg_001.jpg"

    def test_two_scenes_with_same_segment_index_different_paths(self, tmp_path):
        cfg = self._live_wikimedia_config()
        candidate = self._mock_candidate()

        plan1 = self._mock_sourcing_plan([self._mock_segment()])
        with patch(
            "visual_provider_wikimedia_v2.resolve_wikimedia_candidate_v2",
            return_value=candidate,
        ), patch(
            "visual_provider_wikimedia_v2.download_wikimedia_asset_v2",
            return_value=self._mock_download_ok(),
        ):
            result1 = execute_visual_sourcing_plan_v2(
                plan1, cfg,
                dry_run=False, job_dir=str(tmp_path),
                asset_namespace="scene_001",
            )

        plan2 = self._mock_sourcing_plan([{
            **self._mock_segment(),
            "segmentIndex": 1,
        }])
        with patch(
            "visual_provider_wikimedia_v2.resolve_wikimedia_candidate_v2",
            return_value=candidate,
        ), patch(
            "visual_provider_wikimedia_v2.download_wikimedia_asset_v2",
            return_value=self._mock_download_ok(),
        ):
            result2 = execute_visual_sourcing_plan_v2(
                plan2, cfg,
                dry_run=False, job_dir=str(tmp_path),
                asset_namespace="scene_002",
            )

        p1 = result1["resolvedAssets"][0]["assetPath"]
        p2 = result2["resolvedAssets"][0]["assetPath"]
        assert p1 != p2
        assert p1 == "assets/scene_001_seg_001.jpg"
        assert p2 == "assets/scene_002_seg_001.jpg"

    def test_invalid_namespace_rejected(self):
        plan = self._mock_sourcing_plan([self._mock_segment()])
        result = execute_visual_sourcing_plan_v2(
            plan, self._live_wikimedia_config(),
            dry_run=False, job_dir="/tmp",
            asset_namespace="../evil",
        )
        assert result["ok"] is False
        errors = [e["code"] for e in result["diagnostics"]["errors"]]
        assert any("INVALID_INPUT:asset_namespace" in e for e in errors)

    def test_namespace_with_backslash_rejected(self):
        plan = self._mock_sourcing_plan([self._mock_segment()])
        result = execute_visual_sourcing_plan_v2(
            plan, self._live_wikimedia_config(),
            dry_run=False, job_dir="/tmp",
            asset_namespace="scene\\001",
        )
        assert result["ok"] is False

    def test_namespace_with_spaces_rejected(self):
        plan = self._mock_sourcing_plan([self._mock_segment()])
        result = execute_visual_sourcing_plan_v2(
            plan, self._live_wikimedia_config(),
            dry_run=False, job_dir="/tmp",
            asset_namespace="scene 001",
        )
        assert result["ok"] is False

    def test_extension_preserved_with_namespace(self, tmp_path):
        for mime, expected_ext in [
            ("image/jpeg", "scene_001_seg_001.jpg"),
            ("image/png", "scene_001_seg_001.png"),
            ("image/webp", "scene_001_seg_001.webp"),
            ("image/gif", "scene_001_seg_001.gif"),
        ]:
            candidate = {**self._mock_candidate(), "mimeType": mime}
            plan = self._mock_sourcing_plan([self._mock_segment()])
            with patch(
                "visual_provider_wikimedia_v2.resolve_wikimedia_candidate_v2",
                return_value=candidate,
            ), patch(
                "visual_provider_wikimedia_v2.download_wikimedia_asset_v2",
                return_value=self._mock_download_ok(),
            ):
                result = execute_visual_sourcing_plan_v2(
                    plan, self._live_wikimedia_config(),
                    dry_run=False, job_dir=str(tmp_path),
                    asset_namespace="scene_001",
                )
            ra = result["resolvedAssets"][0]
            assert ra["assetPath"] == f"assets/{expected_ext}"

    def test_legacy_call_without_namespace_still_works(self):
        result = execute_visual_sourcing_plan_v2(
            _mock_sourcing_plan([
                _mock_segment(
                    providerCandidates=[_mock_candidate(provider="wikimedia_commons")],
                ),
            ]),
            _default_provider_config(
                wikimedia_commons={"implemented": True},
            ),
        )
        assert result["ok"] is True
        assert result["dryRun"] is True

    def test_dry_run_with_namespace_does_not_create_files(self, tmp_path):
        cfg = _default_provider_config(
            wikimedia_commons={"implemented": True},
        )
        plan = _mock_sourcing_plan([
            _mock_segment(
                providerCandidates=[_mock_candidate(provider="wikimedia_commons")],
            ),
        ])
        result = execute_visual_sourcing_plan_v2(
            plan, cfg,
            dry_run=True,
            asset_namespace="scene_001",
        )
        assert result["dryRun"] is True
        assert result["resolvedAssets"] == []


# ── Rate-limited propagation in executor ──────────────────────────────────────


class TestRateLimitedInExecutor:
    def _live_wikimedia_config(self):
        return {
            "wikimedia_commons": {
                "enabled": True, "implemented": True,
                "requiresApiKey": False, "live": True,
            },
        }

    def _mock_segment(self):
        return {
            "segmentIndex": 1,
            "assetPreference": "photograph",
            "searchQueries": [{"text": "test", "source": "s"}],
            "generationPrompts": [],
            "providerCandidates": [
                {
                    "provider": "wikimedia_commons",
                    "priority": 1,
                    "queryStrategy": "search",
                    "candidateStatus": "included",
                    "availability": "available",
                    "requiresApiKey": False,
                    "supportStrength": "medium",
                    "reason": "test",
                    "warnings": [],
                },
            ],
            "excludedProviders": [],
            "routingStatus": "ROUTABLE_WITH_WARNINGS",
            "warnings": [],
            "unsupportedReasons": [],
        }

    def test_rate_limited_propagates_provider_error(self, tmp_path):
        from visual_provider_wikimedia_v2 import WikimediaRateLimitedError

        plan = {
            "schemaVersion": 1,
            "segments": [self._mock_segment()],
            "summary": {"totalSegments": 1, "routable": 0, "routableWithWarnings": 1, "unroutable": 0},
        }
        with patch(
            "visual_provider_wikimedia_v2.resolve_wikimedia_candidate_v2",
            side_effect=WikimediaRateLimitedError("429 exhausted"),
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
            )
        assert len(result["resolvedAssets"]) == 0
        assert len(result["unresolvedSegments"]) == 1
        us = result["unresolvedSegments"][0]
        assert us["status"] == "PROVIDER_ERROR"
        assert us["reason"] == "RATE_LIMITED"
        assert result["diagnostics"]["summary"]["providerError"] == 1

    def test_no_results_preserved_for_empty_candidates(self, tmp_path):
        plan = {
            "schemaVersion": 1,
            "segments": [self._mock_segment()],
            "summary": {"totalSegments": 1, "routable": 0, "routableWithWarnings": 1, "unroutable": 0},
        }
        with patch(
            "visual_provider_wikimedia_v2.resolve_wikimedia_candidate_v2",
            return_value=None,
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
            )
        assert len(result["resolvedAssets"]) == 0
        assert len(result["unresolvedSegments"]) == 1
        us = result["unresolvedSegments"][0]
        assert us["status"] == "NO_RESULTS"
        assert result["diagnostics"]["summary"]["noResults"] == 1


# ── Exclusion propagation between scenes in executor ──────────────────────────


class TestExclusionInExecutor:
    def _live_wikimedia_config(self):
        return {
            "wikimedia_commons": {
                "enabled": True, "implemented": True,
                "requiresApiKey": False, "live": True,
            },
        }

    def _mock_candidate(self):
        return {
            "provider": "wikimedia_commons",
            "title": "Test Image",
            "sourceUrl": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Test.jpg",
            "fileUrl": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Test.jpg",
            "thumbnailUrl": "",
            "license": "Public Domain",
            "author": "Test Author",
            "width": 1200,
            "height": 800,
            "mimeType": "image/jpeg",
            "queryUsed": "test query",
            "score": 0.0,
        }

    def _mock_download_ok(self):
        return {"ok": True, "path": "/tmp/job/assets/seg_001.jpg",
                "size": 50000, "mimeType": "image/jpeg", "error": None}

    def _mock_segment(self, segment_index=1):
        return {
            "segmentIndex": segment_index,
            "assetPreference": "photograph",
            "searchQueries": [{"text": "test", "source": "s"}],
            "generationPrompts": [],
            "providerCandidates": [
                {
                    "provider": "wikimedia_commons",
                    "priority": 1,
                    "queryStrategy": "search",
                    "candidateStatus": "included",
                    "availability": "available",
                    "requiresApiKey": False,
                    "supportStrength": "medium",
                    "reason": "test",
                    "warnings": [],
                },
            ],
            "excludedProviders": [],
            "routingStatus": "ROUTABLE_WITH_WARNINGS",
            "warnings": [],
            "unsupportedReasons": [],
        }

    def test_second_segment_receives_excluded_urls_from_first(self, tmp_path):
        """When executor receives exclusion sets, resolver sees accumulated state."""
        plan = {
            "schemaVersion": 1,
            "segments": [self._mock_segment(1), self._mock_segment(2)],
            "summary": {"totalSegments": 2, "routable": 0, "routableWithWarnings": 2, "unroutable": 0},
        }

        excluded_src: set[str] = set()
        excluded_file: set[str] = set()

        captured_calls = []

        def mock_resolve(queries, user_agent=None, excluded_source_urls=None,
                         excluded_file_urls=None, **kwargs):
            captured_calls.append({
                "excluded_src": set(excluded_source_urls) if excluded_source_urls else set(),
            })
            return self._mock_candidate()

        with patch(
            "visual_provider_wikimedia_v2.resolve_wikimedia_candidate_v2",
            side_effect=mock_resolve,
        ), patch(
            "visual_provider_wikimedia_v2.download_wikimedia_asset_v2",
            return_value=self._mock_download_ok(),
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
                excluded_source_urls=excluded_src,
                excluded_file_urls=excluded_file,
            )

        assert len(result["resolvedAssets"]) == 2
        assert len(captured_calls) == 2
        assert len(captured_calls[1]["excluded_src"]) >= 1


# ── Multi-provider failover ──────────────────────────────────────────────────


class TestMultiProviderFailover:
    def _live_wikimedia_config(self):
        return {
            "wikimedia_commons": {
                "enabled": True, "implemented": True,
                "requiresApiKey": False, "live": True,
            },
            "pixabay": {
                "enabled": True, "implemented": True,
                "requiresApiKey": True, "apiKeyPresent": True, "live": True,
            },
        }

    def _wikimedia_candidate(self):
        return {
            "provider": "wikimedia_commons",
            "title": "Test",
            "sourceUrl": "https://commons.wikimedia.org/wiki/File:Test.jpg",
            "fileUrl": "https://upload.wikimedia.org/wikipedia/commons/test.jpg",
            "license": "Public Domain",
            "author": "Test",
            "width": 1200,
            "height": 800,
            "mimeType": "image/jpeg",
            "queryUsed": "test",
            "score": 0.0,
        }

    def _pixabay_candidate(self):
        return {
            "provider": "pixabay",
            "sourceUrl": "https://pixabay.com/photos/test/",
            "fileUrl": "https://pixabay.com/get/test.jpg",
            "width": 1280,
            "height": 720,
            "author": "Test",
            "license": "Pixabay Content License",
            "queryUsed": "test",
        }

    def _download_ok(self):
        return {"ok": True, "path": "/tmp/job/assets/seg_001.jpg",
                "size": 50000, "mimeType": "image/jpeg", "error": None,
                "actualWidth": 1280, "actualHeight": 720}

    def _segment_diagram_wikimedia_pixabay(self):
        return {
            "segmentIndex": 1,
            "assetPreference": "diagram",
            "searchQueries": [{"text": "test", "source": "s"}],
            "generationPrompts": [],
            "providerCandidates": [
                {
                    "provider": "wikimedia_commons",
                    "priority": 1,
                    "queryStrategy": "search",
                    "candidateStatus": "included",
                    "availability": "available",
                    "requiresApiKey": False,
                    "supportStrength": "weak",
                    "reason": "diagram — weak support",
                    "warnings": [],
                },
                {
                    "provider": "pixabay",
                    "priority": 2,
                    "queryStrategy": "search",
                    "candidateStatus": "included",
                    "availability": "conditional",
                    "requiresApiKey": True,
                    "supportStrength": "weak",
                    "reason": "diagram — weak support",
                    "warnings": [],
                },
            ],
            "excludedProviders": [],
            "routingStatus": "ROUTABLE_WITH_WARNINGS",
            "warnings": [],
            "unsupportedReasons": [],
        }

    def _sourcing_plan(self, segment):
        return {
            "schemaVersion": 1,
            "segments": [segment],
            "summary": {
                "totalSegments": 1,
                "routable": 0,
                "routableWithWarnings": 1,
                "unroutable": 0,
            },
        }

    def test_wikimedia_resolved_pixabay_not_called(self, tmp_path):
        plan = self._sourcing_plan(self._segment_diagram_wikimedia_pixabay())
        pixabay_called = [False]

        def mock_pixabay(candidate, segment, job_dir, warnings,
                         asset_namespace=None, excluded_source_urls=None,
                         excluded_file_urls=None, provider_credentials=None):
            pixabay_called[0] = True
            return {"status": "PROVIDER_ERROR", "reason": "should not be called"}

        with patch(
            "visual_asset_executor_v2._resolve_wikimedia",
            return_value={
                "segmentIndex": 1, "assetPreference": "diagram",
                "status": "RESOLVED", "provider": "wikimedia_commons",
                "assetPath": "assets/seg_001.jpg", "fileSize": 50000,
                "sourceUrl": "", "fileUrl": "",
                "license": "CC", "author": "A",
                "mimeType": "image/jpeg", "width": 800, "height": 800,
                "searchQueryUsed": "test", "generationPromptUsed": None,
            },
        ), patch(
            "visual_asset_executor_v2._resolve_pixabay", wraps=mock_pixabay,
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
                provider_credentials={"pixabay": {"apiKey": "KEY"}},
            )
        assert result["ok"] is True
        assert len(result["resolvedAssets"]) == 1
        assert result["resolvedAssets"][0]["provider"] == "wikimedia_commons"
        assert pixabay_called[0] is False

    def test_wikimedia_rate_limited_pixabay_resolved(self, tmp_path):
        plan = self._sourcing_plan(self._segment_diagram_wikimedia_pixabay())
        with patch(
            "visual_asset_executor_v2._resolve_wikimedia",
            return_value={
                "segmentIndex": 1, "assetPreference": "diagram",
                "status": "PROVIDER_ERROR", "provider": "wikimedia_commons",
                "searchQueriesTried": ["test"], "reason": "RATE_LIMITED",
            },
        ), patch(
            "visual_asset_executor_v2._resolve_pixabay",
            return_value={
                "segmentIndex": 1, "assetPreference": "diagram",
                "status": "RESOLVED", "provider": "pixabay",
                "assetPath": "assets/seg_001.jpg", "fileSize": 50000,
                "sourceUrl": "https://pixabay.com/photos/test/",
                "fileUrl": "https://pixabay.com/get/test.jpg",
                "license": "Pixabay Content License", "author": "Test",
                "mimeType": "image/jpeg", "width": 1280, "height": 720,
                "searchQueryUsed": "test", "generationPromptUsed": None,
            },
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
                provider_credentials={"pixabay": {"apiKey": "KEY"}},
            )
        assert result["ok"] is True
        assert len(result["resolvedAssets"]) == 1
        assert result["resolvedAssets"][0]["provider"] == "pixabay"
        assert "providerAttempts" in result["resolvedAssets"][0]
        attempts = result["resolvedAssets"][0]["providerAttempts"]
        assert len(attempts) == 2
        assert attempts[0]["provider"] == "wikimedia_commons"
        assert attempts[0]["status"] == "PROVIDER_ERROR"
        assert attempts[1]["provider"] == "pixabay"
        assert attempts[1]["status"] == "RESOLVED"

    def test_wikimedia_no_results_pixabay_resolved(self, tmp_path):
        plan = self._sourcing_plan(self._segment_diagram_wikimedia_pixabay())
        with patch(
            "visual_asset_executor_v2._resolve_wikimedia",
            return_value={
                "segmentIndex": 1, "assetPreference": "diagram",
                "status": "NO_RESULTS", "provider": "wikimedia_commons",
                "searchQueriesTried": ["test"], "reason": "no candidates",
            },
        ), patch(
            "visual_asset_executor_v2._resolve_pixabay",
            return_value={
                "segmentIndex": 1, "assetPreference": "diagram",
                "status": "RESOLVED", "provider": "pixabay",
                "assetPath": "assets/seg_001.jpg", "fileSize": 50000,
                "sourceUrl": "", "fileUrl": "",
                "license": "Pixabay Content License", "author": "Test",
                "mimeType": "image/jpeg", "width": 1280, "height": 720,
                "searchQueryUsed": "test", "generationPromptUsed": None,
            },
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
                provider_credentials={"pixabay": {"apiKey": "KEY"}},
            )
        assert len(result["resolvedAssets"]) == 1
        assert result["resolvedAssets"][0]["provider"] == "pixabay"

    def test_wikimedia_download_failed_pixabay_resolved(self, tmp_path):
        plan = self._sourcing_plan(self._segment_diagram_wikimedia_pixabay())
        with patch(
            "visual_asset_executor_v2._resolve_wikimedia",
            return_value={
                "segmentIndex": 1, "assetPreference": "diagram",
                "status": "DOWNLOAD_FAILED", "provider": "wikimedia_commons",
                "searchQueriesTried": ["test"], "reason": "download errors",
            },
        ), patch(
            "visual_asset_executor_v2._resolve_pixabay",
            return_value={
                "segmentIndex": 1, "assetPreference": "diagram",
                "status": "RESOLVED", "provider": "pixabay",
                "assetPath": "assets/seg_001.jpg", "fileSize": 50000,
                "sourceUrl": "", "fileUrl": "",
                "license": "Pixabay Content License", "author": "Test",
                "mimeType": "image/jpeg", "width": 1280, "height": 720,
                "searchQueryUsed": "test", "generationPromptUsed": None,
            },
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
                provider_credentials={"pixabay": {"apiKey": "KEY"}},
            )
        assert len(result["resolvedAssets"]) == 1
        assert result["resolvedAssets"][0]["provider"] == "pixabay"

    def test_both_no_results_unresolved(self, tmp_path):
        plan = self._sourcing_plan(self._segment_diagram_wikimedia_pixabay())
        with patch(
            "visual_asset_executor_v2._resolve_wikimedia",
            return_value={
                "segmentIndex": 1, "assetPreference": "diagram",
                "status": "NO_RESULTS", "provider": "wikimedia_commons",
                "searchQueriesTried": ["test"], "reason": "no candidates",
            },
        ), patch(
            "visual_asset_executor_v2._resolve_pixabay",
            return_value={
                "segmentIndex": 1, "assetPreference": "diagram",
                "status": "NO_RESULTS", "provider": "pixabay",
                "searchQueriesTried": ["test"], "reason": "no hits",
            },
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
                provider_credentials={"pixabay": {"apiKey": "KEY"}},
            )
        assert len(result["resolvedAssets"]) == 0
        assert len(result["unresolvedSegments"]) == 1
        us = result["unresolvedSegments"][0]
        assert us["status"] == "NO_RESULTS"
        assert "providerAttempts" in us
        assert len(us["providerAttempts"]) == 2

    def test_pixabay_without_api_key_skipped(self, tmp_path):
        plan = self._sourcing_plan(self._segment_diagram_wikimedia_pixabay())
        with patch(
            "visual_asset_executor_v2._resolve_wikimedia",
            return_value={
                "segmentIndex": 1, "assetPreference": "diagram",
                "status": "RESOLVED", "provider": "wikimedia_commons",
                "assetPath": "assets/seg_001.jpg", "fileSize": 50000,
                "sourceUrl": "", "fileUrl": "",
                "license": "CC", "author": "A",
                "mimeType": "image/jpeg", "width": 800, "height": 800,
                "searchQueryUsed": "test", "generationPromptUsed": None,
            },
        ):
            config_no_pixabay_key = {
                "wikimedia_commons": {
                    "enabled": True, "implemented": True,
                    "requiresApiKey": False, "live": True,
                },
                "pixabay": {
                    "enabled": True, "implemented": True,
                    "requiresApiKey": True, "apiKeyPresent": False, "live": True,
                },
            }
            result = execute_visual_sourcing_plan_v2(
                plan, config_no_pixabay_key,
                dry_run=False, job_dir=str(tmp_path),
                provider_credentials=None,
            )
        assert len(result["resolvedAssets"]) == 1
        assert result["resolvedAssets"][0]["provider"] == "wikimedia_commons"

    def test_provider_attempts_in_order(self, tmp_path):
        plan = self._sourcing_plan(self._segment_diagram_wikimedia_pixabay())
        with patch(
            "visual_asset_executor_v2._resolve_wikimedia",
            return_value={
                "segmentIndex": 1, "assetPreference": "diagram",
                "status": "PROVIDER_ERROR", "provider": "wikimedia_commons",
                "searchQueriesTried": ["test"], "reason": "RATE_LIMITED",
            },
        ), patch(
            "visual_asset_executor_v2._resolve_pixabay",
            return_value={
                "segmentIndex": 1, "assetPreference": "diagram",
                "status": "RESOLVED", "provider": "pixabay",
                "assetPath": "assets/seg_001.jpg", "fileSize": 50000,
                "sourceUrl": "", "fileUrl": "",
                "license": "Pixabay", "author": "T",
                "mimeType": "image/jpeg", "width": 900, "height": 900,
                "searchQueryUsed": "test", "generationPromptUsed": None,
            },
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
                provider_credentials={"pixabay": {"apiKey": "KEY"}},
            )
        attempts = result["resolvedAssets"][0]["providerAttempts"]
        assert attempts[0]["provider"] == "wikimedia_commons"
        assert attempts[1]["provider"] == "pixabay"

    def test_no_credentials_in_output(self, tmp_path):
        plan = self._sourcing_plan(self._segment_diagram_wikimedia_pixabay())
        with patch(
            "visual_asset_executor_v2._resolve_wikimedia",
            return_value={
                "segmentIndex": 1, "assetPreference": "diagram",
                "status": "PROVIDER_ERROR", "provider": "wikimedia_commons",
                "searchQueriesTried": ["test"], "reason": "RATE_LIMITED",
            },
        ), patch(
            "visual_asset_executor_v2._resolve_pixabay",
            return_value={
                "segmentIndex": 1, "assetPreference": "diagram",
                "status": "RESOLVED", "provider": "pixabay",
                "assetPath": "assets/seg_001.jpg", "fileSize": 50000,
                "sourceUrl": "", "fileUrl": "",
                "license": "Pixabay", "author": "T",
                "mimeType": "image/jpeg", "width": 900, "height": 900,
                "searchQueryUsed": "test", "generationPromptUsed": None,
            },
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
                provider_credentials={"pixabay": {"apiKey": "secret-key-123"}},
            )
        result_json = json.dumps(result)
        assert "secret-key-123" not in result_json

    def test_dry_run_preserves_candidates_list(self):
        plan = self._sourcing_plan(self._segment_diagram_wikimedia_pixabay())
        result = execute_visual_sourcing_plan_v2(
            plan, self._live_wikimedia_config(),
            dry_run=True,
            provider_credentials={"pixabay": {"apiKey": "KEY"}},
        )
        dry = result["dryRunAttempts"][0]
        assert dry["selectedProvider"] == "wikimedia_commons"
        assert dry["status"] == "SKIPPED_DRY_RUN"

    def test_wikimedia_only_no_regression(self, tmp_path):
        plan = self._sourcing_plan({
            "segmentIndex": 1,
            "assetPreference": "diagram",
            "searchQueries": [{"text": "test", "source": "s"}],
            "generationPrompts": [],
            "providerCandidates": [
                {
                    "provider": "wikimedia_commons",
                    "priority": 1,
                    "queryStrategy": "search",
                    "candidateStatus": "included",
                    "availability": "available",
                    "requiresApiKey": False,
                    "supportStrength": "weak",
                    "reason": "diagram — weak support",
                    "warnings": [],
                },
            ],
            "excludedProviders": [],
            "routingStatus": "ROUTABLE_WITH_WARNINGS",
            "warnings": [],
            "unsupportedReasons": [],
        })
        with patch(
            "visual_asset_executor_v2._resolve_wikimedia",
            return_value={
                "segmentIndex": 1, "assetPreference": "diagram",
                "status": "RESOLVED", "provider": "wikimedia_commons",
                "assetPath": "assets/seg_001.jpg", "fileSize": 50000,
                "sourceUrl": "", "fileUrl": "",
                "license": "CC", "author": "A",
                "mimeType": "image/jpeg", "width": 800, "height": 800,
                "searchQueryUsed": "test", "generationPromptUsed": None,
            },
        ):
            result = execute_visual_sourcing_plan_v2(
                plan, self._live_wikimedia_config(),
                dry_run=False, job_dir=str(tmp_path),
            )
        assert len(result["resolvedAssets"]) == 1
        assert result["resolvedAssets"][0]["provider"] == "wikimedia_commons"
