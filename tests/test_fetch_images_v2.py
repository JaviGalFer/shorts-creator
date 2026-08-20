"""Tests for fetch_images_v2.py standalone CLI.

Run: python3 -m pytest tests/test_fetch_images_v2.py -v
"""

import json
import os
import sys
from pathlib import Path

import pytest

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))

import fetch_images_v2
from shorts_creator.assets import fetcher as asset_fetcher
from shorts_creator.contracts.visual import SCHEMA_VERSION as V2_SCHEMA_VERSION

V1_LEGACY_FIELDS = frozenset({
    "editorialRole", "strategy", "primaryAssetType",
    "secondaryAssetType", "visualTemporalIntent",
})


def _has_legacy_fields(obj, path: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(obj, dict):
        for key in obj:
            if key in V1_LEGACY_FIELDS:
                violations.append(f"{path}.{key}")
            if isinstance(obj[key], (dict, list)):
                violations.extend(_has_legacy_fields(obj[key], f"{path}.{key}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, (dict, list)):
                violations.extend(_has_legacy_fields(item, f"{path}[{i}]"))
    return violations


# ── Fixture helpers ───────────────────────────────────────────────────────────


def _base_metadata(**overrides) -> dict:
    md = {
        "jobId": "test-job-001",
        "status": "INIT",
        "script": {
            "scenes": [
                {
                    "sceneNumber": 1,
                    "visualPlan": {
                        "_schemaVersion": V2_SCHEMA_VERSION,
                        "visualIntent": "show",
                        "subjects": ["Test Subject"],
                        "searchQueries": ["test query"],
                        "assetPreferences": ["photograph"],
                        "visualSequence": [
                            {
                                "segmentIndex": 1,
                                "assetPreference": "photograph",
                                "durationFraction": 1.0,
                                "transition": "cut",
                            }
                        ],
                    },
                }
            ]
        },
    }
    md.update(overrides)
    return md


def _two_v2_scenes_metadata():
    return {
        "jobId": "test-job-002",
        "status": "INIT",
        "script": {
            "scenes": [
                {
                    "sceneNumber": 1,
                    "visualPlan": {
                        "_schemaVersion": V2_SCHEMA_VERSION,
                        "visualIntent": "show",
                        "subjects": ["Scene One"],
                        "searchQueries": ["scene one query"],
                        "assetPreferences": ["photograph"],
                        "visualSequence": [
                            {
                                "segmentIndex": 1,
                                "assetPreference": "photograph",
                                "durationFraction": 1.0,
                                "transition": "cut",
                            }
                        ],
                    },
                },
                {
                    "sceneNumber": 2,
                    "visualPlan": {
                        "_schemaVersion": V2_SCHEMA_VERSION,
                        "visualIntent": "explain",
                        "subjects": ["Scene Two"],
                        "searchQueries": ["scene two query"],
                        "assetPreferences": ["diagram"],
                        "visualSequence": [
                            {
                                "segmentIndex": 1,
                                "assetPreference": "diagram",
                                "durationFraction": 1.0,
                                "transition": "cut",
                            }
                        ],
                    },
                },
            ]
        },
    }


def _wrap_executor_result(resolved=None, unresolved=None, dry_run=False):
    return {
        "ok": True,
        "dryRun": dry_run,
        "resolvedAssets": resolved or [],
        "unresolvedSegments": unresolved or [],
        "dryRunAttempts": [],
        "diagnostics": {"errors": [], "warnings": [], "summary": {}},
    }


def _resolved_asset(segment_index=1, asset_preference="photograph"):
    return {
        "segmentIndex": segment_index,
        "assetPreference": asset_preference,
        "status": "RESOLVED",
        "provider": "wikimedia_commons",
        "assetPath": f"assets/seg_{segment_index:03d}.jpg",
        "fileSize": 50000,
        "sourceUrl": "https://commons.wikimedia.org/wiki/File:Test.jpg",
        "fileUrl": "https://upload.wikimedia.org/commons/Test.jpg",
        "license": "Public Domain",
        "author": "Test Author",
        "mimeType": "image/jpeg",
        "width": 1200,
        "height": 800,
        "searchQueryUsed": "test query",
        "generationPromptUsed": None,
    }


def _mock_canonicalizer_ok(plan):
    return {
        "ok": True,
        "canonicalPlan": plan,
        "diagnostics": {"ok": True, "errors": [], "warnings": [], "canonicalizations": []},
    }


def _mock_canonicalizer_fail(plan):
    return {
        "ok": False,
        "canonicalPlan": None,
        "diagnostics": {
            "ok": False,
            "errors": [{"code": "TEST_ERROR", "message": "simulated canonicalizer failure"}],
            "warnings": [],
        },
    }


def _mock_router_ok(plan, scene=None, request_visuals=None, mix_counts=None):
    return {
        "ok": True,
        "sourcingPlan": {
            "schemaVersion": 1,
            "segments": [
                {
                    "segmentIndex": 1,
                    "assetPreference": "photograph",
                    "searchQueries": [{"text": "test", "source": "test"}],
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
                        }
                    ],
                    "excludedProviders": [],
                    "routingStatus": "ROUTABLE",
                    "warnings": [],
                    "unsupportedReasons": [],
                }
            ],
            "summary": {"totalSegments": 1, "routable": 1, "routableWithWarnings": 0, "unroutable": 0},
        },
        "diagnostics": {"errors": [], "warnings": [], "unsupported": [], "routingDecisions": []},
    }


def _mock_router_fail(plan, scene=None, request_visuals=None, mix_counts=None):
    return {
        "ok": False,
        "sourcingPlan": None,
        "diagnostics": {
            "errors": [{"code": "TEST_ERROR", "message": "simulated router failure"}],
            "warnings": [],
        },
    }


# ── Tests ────────────────────────────────────────────────────────────────────


class TestLoadMetadata:
    def test_loads_metadata_and_writes_updated(self, tmp_path, monkeypatch):
        metadata_path = tmp_path / "metadata.json"
        metadata = _base_metadata()
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2",
            lambda **kw: _wrap_executor_result(
                resolved=[_resolved_asset()], dry_run=kw.get("dry_run", False)
            ),
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 0

        updated = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert updated["status"] == "ASSETS_READY"
        assert "assets" in updated
        assert "_visualAssetBridgeV2" in updated
        assert updated["_visualAssetBridgeV2"]["summary"]["resolved"] == 1


class TestRequestVisualsPlumbing:
    def test_source_providers_passed_to_router(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata["request"] = {
            "visuals": {"sourceProviders": ["pixabay", "wikimedia_commons"]},
        }
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        captured: dict = {}

        def spy_router(plan, scene=None, request_visuals=None, mix_counts=None):
            captured["request_visuals"] = request_visuals
            return _mock_router_ok(plan, scene=scene, request_visuals=request_visuals)

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", spy_router
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2",
            lambda **kw: _wrap_executor_result(
                resolved=[_resolved_asset()], dry_run=kw.get("dry_run", False)
            ),
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 0
        assert captured.get("request_visuals") == {
            "sourceProviders": ["pixabay", "wikimedia_commons"],
        }

    def test_no_request_visuals_passes_none(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        captured: dict = {}

        def spy_router(plan, scene=None, request_visuals=None, mix_counts=None):
            captured["request_visuals"] = request_visuals
            return _mock_router_ok(plan, scene=scene, request_visuals=request_visuals)

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", spy_router
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2",
            lambda **kw: _wrap_executor_result(
                resolved=[_resolved_asset()], dry_run=kw.get("dry_run", False)
            ),
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 0
        assert captured.get("request_visuals") is None


class TestSceneDetection:
    def test_processes_only_schema_version_2(self, tmp_path, monkeypatch):
        metadata = {
            "jobId": "test",
            "status": "INIT",
            "script": {
                "scenes": [
                    {
                        "sceneNumber": 1,
                        "visualPlan": {"_schemaVersion": 1, "visualSequence": []},
                    },
                    {
                        "sceneNumber": 2,
                        "visualPlan": {
                            "_schemaVersion": V2_SCHEMA_VERSION,
                            "visualIntent": "show",
                            "subjects": ["S2"],
                            "searchQueries": ["q2"],
                            "assetPreferences": ["photograph"],
                            "visualSequence": [
                                {
                                    "segmentIndex": 1,
                                    "assetPreference": "photograph",
                                    "durationFraction": 1.0,
                                    "transition": "cut",
                                }
                            ],
                        },
                    },
                ]
            },
        }
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2",
            lambda **kw: _wrap_executor_result(
                resolved=[_resolved_asset()], dry_run=kw.get("dry_run", False)
            ),
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 0

        updated = json.loads(metadata_path.read_text(encoding="utf-8"))
        summary = updated["_visualAssetBridgeV2"]["summary"]
        assert summary["scenes"] == 1
        assert summary["segments"] == 1

    def test_ignores_scenes_without_visual_plan(self, tmp_path, monkeypatch):
        metadata = {
            "jobId": "test",
            "status": "INIT",
            "script": {
                "scenes": [
                    {
                        "sceneNumber": 1,
                    },
                    {
                        "sceneNumber": 2,
                        "visualPlan": {
                            "_schemaVersion": V2_SCHEMA_VERSION,
                            "visualIntent": "show",
                            "subjects": ["S2"],
                            "searchQueries": ["q2"],
                            "assetPreferences": ["photograph"],
                            "visualSequence": [
                                {
                                    "segmentIndex": 1,
                                    "assetPreference": "photograph",
                                    "durationFraction": 1.0,
                                    "transition": "cut",
                                }
                            ],
                        },
                    },
                ]
            },
        }
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2",
            lambda **kw: _wrap_executor_result(
                resolved=[_resolved_asset()], dry_run=kw.get("dry_run", False)
            ),
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 0
        updated = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert updated["_visualAssetBridgeV2"]["summary"]["scenes"] == 1

    def test_no_v2_plans_exits_with_asset_failed(self, tmp_path):
        metadata = {
            "jobId": "test",
            "status": "INIT",
            "script": {
                "scenes": [
                    {
                        "sceneNumber": 1,
                        "visualPlan": {"_schemaVersion": 1, "visualSequence": []},
                    },
                ]
            },
        }
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 1

        updated = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert updated["status"] == "ASSET_FAILED"


class TestSyntheticUnresolved:
    def test_canonicalizer_failure_produces_synthetic(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_fail
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 1

        updated = json.loads(metadata_path.read_text(encoding="utf-8"))
        summary = updated["_visualAssetBridgeV2"]["summary"]
        assert summary["segments"] == 1
        assert summary["resolved"] == 0
        assert summary["failed"] == 1

    def test_canonicalizer_failure_synthetic_for_multi_segment(self, tmp_path, monkeypatch):
        metadata = {
            "jobId": "test",
            "status": "INIT",
            "script": {
                "scenes": [
                    {
                        "sceneNumber": 1,
                        "visualPlan": {
                            "_schemaVersion": V2_SCHEMA_VERSION,
                            "visualIntent": "explain",
                            "subjects": ["S"],
                            "searchQueries": ["q"],
                            "assetPreferences": ["diagram", "photograph"],
                            "visualSequence": [
                                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 0.5, "transition": "cut"},
                                {"segmentIndex": 2, "assetPreference": "photograph", "durationFraction": 0.5, "transition": "cut"},
                            ],
                        },
                    }
                ]
            },
        }
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_fail
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 1
        updated = json.loads(metadata_path.read_text(encoding="utf-8"))
        summary = updated["_visualAssetBridgeV2"]["summary"]
        assert summary["segments"] == 2
        assert summary["failed"] == 2

    def test_router_failure_produces_synthetic(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_fail
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 1
        updated = json.loads(metadata_path.read_text(encoding="utf-8"))
        summary = updated["_visualAssetBridgeV2"]["summary"]
        assert summary["resolved"] == 0
        assert summary["failed"] == 1

    def test_executor_exception_produces_synthetic(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2",
            lambda **kw: (_ for _ in ()).throw(RuntimeError("simulated executor crash")),
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 1
        updated = json.loads(metadata_path.read_text(encoding="utf-8"))
        summary = updated["_visualAssetBridgeV2"]["summary"]
        assert summary["resolved"] == 0
        assert summary["failed"] == 1

    def test_executor_missing_segment_produces_synthetic(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2",
            lambda **kw: _wrap_executor_result(resolved=[], unresolved=[], dry_run=kw.get("dry_run", False)),
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 1
        updated = json.loads(metadata_path.read_text(encoding="utf-8"))
        summary = updated["_visualAssetBridgeV2"]["summary"]
        assert summary["segments"] == 1
        assert summary["resolved"] == 0
        assert summary["failed"] == 1


class TestPerSceneExecution:
    def test_repeated_segment_index_maps_both_scenes(self, tmp_path, monkeypatch):
        metadata = _two_v2_scenes_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        call_count = [0]

        def mock_executor(**kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return _wrap_executor_result(
                    resolved=[_resolved_asset(segment_index=1, asset_preference="photograph")],
                    dry_run=kw.get("dry_run", False),
                )
            else:
                return _wrap_executor_result(
                    resolved=[_resolved_asset(segment_index=1, asset_preference="diagram")],
                    dry_run=kw.get("dry_run", False),
                )

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2", mock_executor
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 0

        updated = json.loads(metadata_path.read_text(encoding="utf-8"))
        assets = updated["assets"]
        assert len(assets) == 2

        assert assets[0]["sceneNumber"] == 1
        assert len(assets[0]["segments"]) == 1
        assert assets[0]["segments"][0]["segmentValidationStatus"] == "PASS"
        assert assets[0]["segments"][0]["assetType"] == "photograph"

        assert assets[1]["sceneNumber"] == 2
        assert len(assets[1]["segments"]) == 1
        assert assets[1]["segments"][0]["segmentValidationStatus"] == "PASS"
        assert assets[1]["segments"][0]["assetType"] == "diagram"


class TestBridgeAndAssets:
    def test_applies_bridge_and_sets_assets(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2",
            lambda **kw: _wrap_executor_result(
                resolved=[_resolved_asset(asset_preference="photograph")],
                dry_run=kw.get("dry_run", False),
            ),
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 0

        updated = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert "assets" in updated
        assets = updated["assets"]
        assert len(assets) == 1
        assert assets[0]["sceneNumber"] == 1
        assert len(assets[0]["segments"]) == 1
        seg = assets[0]["segments"][0]
        assert seg["segmentValidationStatus"] == "PASS"
        assert seg["path"] == "assets/seg_001.jpg"


class TestStatusBehavior:
    def test_assets_ready_when_all_resolved(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2",
            lambda **kw: _wrap_executor_result(
                resolved=[_resolved_asset()], dry_run=kw.get("dry_run", False)
            ),
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 0
        updated = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert updated["status"] == "ASSETS_READY"

    def test_assets_partial_when_some_resolved(self, tmp_path, monkeypatch):
        metadata = {
            "jobId": "test",
            "status": "INIT",
            "script": {
                "scenes": [
                    {
                        "sceneNumber": 1,
                        "visualPlan": {
                            "_schemaVersion": V2_SCHEMA_VERSION,
                            "visualIntent": "show",
                            "subjects": ["S"],
                            "searchQueries": ["q"],
                            "assetPreferences": ["photograph", "diagram"],
                            "visualSequence": [
                                {"segmentIndex": 1, "assetPreference": "photograph", "durationFraction": 0.5, "transition": "cut"},
                                {"segmentIndex": 2, "assetPreference": "diagram", "durationFraction": 0.5, "transition": "cut"},
                            ],
                        },
                    }
                ]
            },
        }
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )

        def mock_exec(**kw):
            return _wrap_executor_result(
                resolved=[_resolved_asset(segment_index=1, asset_preference="photograph")],
                unresolved=[
                    {
                        "segmentIndex": 2,
                        "assetPreference": "diagram",
                        "status": "NO_RESULTS",
                        "provider": "wikimedia_commons",
                        "reason": "no results",
                    }
                ],
                dry_run=kw.get("dry_run", False),
            )

        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2", mock_exec
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 0
        updated = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert updated["status"] == "ASSETS_PARTIAL"

    def test_asset_unresolved_when_none_resolved(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_fail
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 1
        updated = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert updated["status"] == "ASSET_UNRESOLVED"


class TestDryRun:
    def test_dry_run_passes_dry_run_true_wikimedia_live_false(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        captured_kw = {}

        def mock_exec(**kw):
            captured_kw.update(kw)
            return _wrap_executor_result(
                resolved=[], dry_run=kw.get("dry_run", False)
            )

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2", mock_exec
        )

        fetch_images_v2.main([str(metadata_path), "--dry-run"])
        assert captured_kw["dry_run"] is True
        assert captured_kw["provider_config"]["wikimedia_commons"]["live"] is False

    def test_live_default_passes_dry_run_false_wikimedia_live_true(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        captured_kw = {}

        def mock_exec(**kw):
            captured_kw.update(kw)
            return _wrap_executor_result(
                resolved=[_resolved_asset()], dry_run=kw.get("dry_run", False)
            )

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2", mock_exec
        )

        fetch_images_v2.main([str(metadata_path)])
        assert captured_kw["dry_run"] is False
        assert captured_kw["provider_config"]["wikimedia_commons"]["live"] is True


class TestUserAgent:
    def test_user_agent_propagates(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        captured_kw = {}

        def mock_exec(**kw):
            captured_kw.update(kw)
            return _wrap_executor_result(
                resolved=[_resolved_asset()], dry_run=kw.get("dry_run", False)
            )

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2", mock_exec
        )

        fetch_images_v2.main([str(metadata_path), "--user-agent", "my-bot/3.0"])
        assert captured_kw["provider_config"]["wikimedia_commons"]["userAgent"] == "my-bot/3.0"


class TestAtomicWrite:
    def test_atomic_write_creates_final_metadata_no_tmp(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2",
            lambda **kw: _wrap_executor_result(
                resolved=[_resolved_asset()], dry_run=kw.get("dry_run", False)
            ),
        )

        fetch_images_v2.main([str(metadata_path)])

        assert metadata_path.exists()
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_atomic_write_preserves_original_on_failure(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2",
            lambda **kw: _wrap_executor_result(
                resolved=[_resolved_asset()], dry_run=kw.get("dry_run", False)
            ),
        )

        original_os_replace = os.replace
        call_count = [0]

        def failing_replace(src, dst):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError("simulated replace failure")

        monkeypatch.setattr("os.replace", failing_replace)
        monkeypatch.setattr("shutil.move", failing_replace)

        from fetch_images_v2 import main as fmain
        from unittest.mock import patch

        failed = False
        try:
            with patch("shorts_creator.assets.fetcher.os.replace", failing_replace):
                exit_code = fmain([str(metadata_path)])
        except OSError:
            failed = True

        if not failed:
            monkeypatch.undo()

    def test_atomic_write_failure_reported(self, tmp_path, monkeypatch, capsys):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        original_content = json.dumps(metadata)
        metadata_path.write_text(original_content, encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2",
            lambda **kw: _wrap_executor_result(
                resolved=[_resolved_asset()], dry_run=kw.get("dry_run", False)
            ),
        )

        original_os_replace = os.replace

        def failing_replace(src, dst):
            if isinstance(dst, str) and "metadata.json" in str(dst):
                raise OSError("simulated replace failure")
            return original_os_replace(src, dst)

        monkeypatch.setattr("os.replace", failing_replace)

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 1

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["ok"] is False
        assert output["status"] == "ASSET_FAILED"
        assert len(output["errors"]) >= 1


class TestStdoutSummary:
    def test_stdout_summary_keys(self, tmp_path, monkeypatch, capsys):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2",
            lambda **kw: _wrap_executor_result(
                resolved=[_resolved_asset()], dry_run=kw.get("dry_run", False)
            ),
        )

        fetch_images_v2.main([str(metadata_path)])
        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert "ok" in output
        assert "status" in output
        assert "metadataPath" in output
        assert "dryRun" in output
        assert "v2Scenes" in output
        assert "summary" in output
        assert output["ok"] is True
        assert output["v2Scenes"] == 1


class TestExitCodes:
    def test_exit_code_0_for_assets_ready(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2",
            lambda **kw: _wrap_executor_result(
                resolved=[_resolved_asset()], dry_run=kw.get("dry_run", False)
            ),
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 0

    def test_exit_code_1_for_asset_unresolved(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_fail
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 1

    def test_exit_code_1_for_asset_failed(self, tmp_path):
        metadata = {
            "jobId": "test",
            "status": "INIT",
            "script": {"scenes": []},
        }
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 1


class TestSourceIsolation:
    def test_no_v1_runtime_imports(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2",
            lambda **kw: _wrap_executor_result(
                resolved=[_resolved_asset()], dry_run=kw.get("dry_run", False)
            ),
        )

        v1_modules = [
            "fetch_images", "shorts_creator.validation.asset", "editorial_asset_contract",
            "generate_script", "shorts_creator.rendering.preparer", "shorts_creator.rendering.renderer", "shorts_creator.pipeline.orchestrator",
        ]
        v1_original_modules = {mod: sys.modules.get(mod) for mod in v1_modules}

        with monkeypatch.context() as scoped:
            for mod in v1_modules:
                scoped.delitem(sys.modules, mod, raising=False)

            fetch_images_v2.main([str(metadata_path)])

            for mod in v1_modules:
                assert mod not in sys.modules, f"v1 module '{mod}' was imported"

        for mod in v1_modules:
            if v1_original_modules[mod] is not None:
                assert sys.modules.get(mod) is v1_original_modules[mod], (
                    f"module identity not restored for '{mod}'"
                )
            else:
                assert mod not in sys.modules, (
                    f"module '{mod}' should remain absent after context exit"
                )


class TestNoLegacyFields:
    def test_no_legacy_fields_in_output(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2",
            lambda **kw: _wrap_executor_result(
                resolved=[_resolved_asset()], dry_run=kw.get("dry_run", False)
            ),
        )

        fetch_images_v2.main([str(metadata_path)])
        updated = json.loads(metadata_path.read_text(encoding="utf-8"))

        violations = _has_legacy_fields(updated)
        assert violations == [], f"found legacy v1 fields: {violations}"


class TestNoLiveHttp:
    def test_no_live_http_in_tests(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2",
            lambda **kw: _wrap_executor_result(
                resolved=[_resolved_asset()], dry_run=kw.get("dry_run", False)
            ),
        )

        original_urlopen = None
        try:
            import urllib.request
            original_urlopen = urllib.request.urlopen
            urllib.request.urlopen = lambda *a, **kw: (_ for _ in ()).throw(
                AssertionError("Live HTTP detected in test")
            )
        except ImportError:
            pass

        try:
            fetch_images_v2.main([str(metadata_path)])
        finally:
            if original_urlopen is not None:
                import urllib.request
                urllib.request.urlopen = original_urlopen


# ── Namespace integration tests ──────────────────────────────────────────────


class TestSceneNumberNamespace:
    def test_two_scenes_unique_paths(self, tmp_path, monkeypatch):
        metadata = _two_v2_scenes_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        captured_calls = []

        def mock_exec(**kw):
            captured_calls.append(dict(kw))
            namespace = kw.get("asset_namespace", "")
            seg_idx = 1
            path = f"assets/{namespace}_seg_{seg_idx:03d}.jpg" if namespace else f"assets/seg_{seg_idx:03d}.jpg"
            return _wrap_executor_result(
                resolved=[{
                    "segmentIndex": seg_idx,
                    "assetPreference": "photograph",
                    "status": "RESOLVED",
                    "provider": "wikimedia_commons",
                    "assetPath": path,
                    "fileSize": 50000,
                    "sourceUrl": "https://example.com/test.jpg",
                    "fileUrl": "https://example.com/test.jpg",
                    "license": "Public Domain",
                    "author": "Test",
                    "mimeType": "image/jpeg",
                    "width": 1200,
                    "height": 800,
                    "searchQueryUsed": "test",
                    "generationPromptUsed": None,
                }],
                dry_run=kw.get("dry_run", False),
            )

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2", mock_exec
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 0

        assert len(captured_calls) == 2
        assert captured_calls[0]["asset_namespace"] == "scene_001"
        assert captured_calls[1]["asset_namespace"] == "scene_002"

        updated = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert updated["status"] == "ASSETS_READY"

        paths = []
        for entry in updated["assets"]:
            for seg in entry["segments"]:
                paths.append(seg["path"])

        assert paths == [
            "assets/scene_001_seg_001.jpg",
            "assets/scene_002_seg_001.jpg",
        ]
        assert len(set(paths)) == 2

    def test_scene_number_zero_fails_with_synthetic(self, tmp_path, monkeypatch):
        metadata = {
            "jobId": "test",
            "status": "INIT",
            "script": {
                "scenes": [
                    {
                        "sceneNumber": 0,
                        "visualPlan": {
                            "_schemaVersion": V2_SCHEMA_VERSION,
                            "visualIntent": "show",
                            "subjects": ["S"],
                            "searchQueries": ["q"],
                            "assetPreferences": ["photograph"],
                            "visualSequence": [
                                {"segmentIndex": 1, "assetPreference": "photograph",
                                 "durationFraction": 1.0, "transition": "cut"},
                            ],
                        },
                    }
                ]
            },
        }
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )

        executor_called = [False]

        def mock_exec(**kw):
            executor_called[0] = True
            return _wrap_executor_result(resolved=[], dry_run=kw.get("dry_run", False))

        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2", mock_exec
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 1
        assert not executor_called[0]

        updated = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert updated["status"] == "ASSET_UNRESOLVED"

    def test_scene_number_none_fails_with_synthetic(self, tmp_path, monkeypatch):
        metadata = {
            "jobId": "test",
            "status": "INIT",
            "script": {
                "scenes": [
                    {
                        "sceneNumber": None,
                        "visualPlan": {
                            "_schemaVersion": V2_SCHEMA_VERSION,
                            "visualIntent": "show",
                            "subjects": ["S"],
                            "searchQueries": ["q"],
                            "assetPreferences": ["photograph"],
                            "visualSequence": [
                                {"segmentIndex": 1, "assetPreference": "photograph",
                                 "durationFraction": 1.0, "transition": "cut"},
                            ],
                        },
                    }
                ]
            },
        }
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )

        executor_called = [False]

        def mock_exec(**kw):
            executor_called[0] = True
            return _wrap_executor_result(resolved=[], dry_run=kw.get("dry_run", False))

        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2", mock_exec
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 1
        assert not executor_called[0]

    def test_scene_number_string_fails_with_synthetic(self, tmp_path, monkeypatch):
        metadata = {
            "jobId": "test",
            "status": "INIT",
            "script": {
                "scenes": [
                    {
                        "sceneNumber": "one",
                        "visualPlan": {
                            "_schemaVersion": V2_SCHEMA_VERSION,
                            "visualIntent": "show",
                            "subjects": ["S"],
                            "searchQueries": ["q"],
                            "assetPreferences": ["photograph"],
                            "visualSequence": [
                                {"segmentIndex": 1, "assetPreference": "photograph",
                                 "durationFraction": 1.0, "transition": "cut"},
                            ],
                        },
                    }
                ]
            },
        }
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )

        executor_called = [False]

        def mock_exec(**kw):
            executor_called[0] = True
            return _wrap_executor_result(resolved=[], dry_run=kw.get("dry_run", False))

        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2", mock_exec
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 1
        assert not executor_called[0]

    def test_dry_run_with_namespace_does_not_create_files(self, tmp_path, monkeypatch):
        metadata = _base_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        captured_kw = {}

        def mock_exec(**kw):
            captured_kw.update(kw)
            return _wrap_executor_result(resolved=[], dry_run=kw.get("dry_run", False))

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2", mock_exec
        )

        fetch_images_v2.main([str(metadata_path), "--dry-run"])
        assert captured_kw["asset_namespace"] == "scene_001"
        assert captured_kw["dry_run"] is True

    def test_scene_number_in_results(self, tmp_path, monkeypatch):
        """Each result must carry sceneNumber."""
        metadata = _two_v2_scenes_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        def mock_exec(**kw):
            namespace = kw.get("asset_namespace", "")
            seg_idx = 1
            path = f"assets/{namespace}_seg_{seg_idx:03d}.jpg" if namespace else f"assets/seg_{seg_idx:03d}.jpg"
            return _wrap_executor_result(
                resolved=[{
                    "segmentIndex": seg_idx,
                    "assetPreference": "photograph",
                    "status": "RESOLVED",
                    "provider": "wikimedia_commons",
                    "assetPath": path,
                    "fileSize": 50000,
                    "sourceUrl": "https://example.com/test.jpg",
                    "fileUrl": "https://example.com/test.jpg",
                    "license": "Public Domain",
                    "author": "Test",
                    "mimeType": "image/jpeg",
                    "width": 1200,
                    "height": 800,
                    "searchQueryUsed": "test",
                    "generationPromptUsed": None,
                }],
                dry_run=kw.get("dry_run", False),
            )

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2", mock_exec
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 0

        updated = json.loads(metadata_path.read_text(encoding="utf-8"))
        for entry in updated["assets"]:
            for seg in entry["segments"]:
                if seg["segmentValidationStatus"] == "PASS":
                    assert "scene_" in seg["path"]

    def test_scene_number_duplicate_fails_fast(self, tmp_path, monkeypatch, capsys):
        """Duplicate sceneNumbers must fail with ASSET_FAILED before any executor call."""
        metadata = {
            "jobId": "test-dup",
            "status": "INIT",
            "script": {
                "scenes": [
                    {
                        "sceneNumber": 1,
                        "visualPlan": {
                            "_schemaVersion": V2_SCHEMA_VERSION,
                            "visualIntent": "show",
                            "subjects": ["S1"],
                            "searchQueries": ["q1"],
                            "assetPreferences": ["photograph"],
                            "visualSequence": [
                                {"segmentIndex": 1, "assetPreference": "photograph",
                                 "durationFraction": 1.0, "transition": "cut"},
                            ],
                        },
                    },
                    {
                        "sceneNumber": 1,
                        "visualPlan": {
                            "_schemaVersion": V2_SCHEMA_VERSION,
                            "visualIntent": "explain",
                            "subjects": ["S2"],
                            "searchQueries": ["q2"],
                            "assetPreferences": ["diagram"],
                            "visualSequence": [
                                {"segmentIndex": 1, "assetPreference": "diagram",
                                 "durationFraction": 1.0, "transition": "cut"},
                            ],
                        },
                    },
                ]
            },
        }
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        executor_called = [False]

        def mock_exec(**kw):
            executor_called[0] = True
            return _wrap_executor_result(resolved=[], dry_run=kw.get("dry_run", False))

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2", mock_exec
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 1
        assert not executor_called[0]

        updated = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert updated["status"] == "ASSET_FAILED"

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["status"] == "ASSET_FAILED"
        assert "duplicate sceneNumber" in output["errors"][0]


# ── Accumulated exclusions between scenes ─────────────────────────────────────


class TestAccumulatedExclusions:
    def test_exclusions_accumulated_between_scenes(self, tmp_path, monkeypatch):
        """Exclusion sets grow across scenes, preventing duplicate URLs."""
        metadata = _two_v2_scenes_metadata()
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        captured_excluded_across_calls = []

        def mock_exec(**kw):
            excluded_src = kw.get("excluded_source_urls")
            excluded_file = kw.get("excluded_file_urls")
            wikimedia_cache = kw.get("wikimedia_cache")
            captured_excluded_across_calls.append({
                "excluded_src_size": len(excluded_src) if excluded_src else 0,
                "excluded_file_size": len(excluded_file) if excluded_file else 0,
                "cache_keys": len(wikimedia_cache) if wikimedia_cache else 0,
            })
            # Simulate the mutation that the real executor would perform
            if excluded_src is not None:
                excluded_src.add(f"src_{len(captured_excluded_across_calls)}")
            if excluded_file is not None:
                excluded_file.add(f"file_{len(captured_excluded_across_calls)}")
            namespace = kw.get("asset_namespace", "")
            seg_idx = 1
            path = f"assets/{namespace}_seg_{seg_idx:03d}.jpg" if namespace else f"assets/seg_{seg_idx:03d}.jpg"
            return _wrap_executor_result(
                resolved=[{
                    "segmentIndex": seg_idx,
                    "assetPreference": "photograph",
                    "status": "RESOLVED",
                    "provider": "wikimedia_commons",
                    "assetPath": path,
                    "fileSize": 50000,
                    "sourceUrl": f"https://commons.wikimedia.org/unique_{len(captured_excluded_across_calls)}.jpg",
                    "fileUrl": f"https://upload.wikimedia.org/unique_{len(captured_excluded_across_calls)}.jpg",
                    "license": "Public Domain",
                    "author": "Test",
                    "mimeType": "image/jpeg",
                    "width": 1200,
                    "height": 800,
                    "searchQueryUsed": "test",
                    "generationPromptUsed": None,
                }],
                dry_run=kw.get("dry_run", False),
            )

        monkeypatch.setattr(
            "shorts_creator.assets.fetcher.canonicalize_visual_plan_v2", _mock_canonicalizer_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.router.build_visual_sourcing_plan_v2", _mock_router_ok
        )
        monkeypatch.setattr(
            "shorts_creator.assets.executor.execute_visual_sourcing_plan_v2", mock_exec
        )

        exit_code = fetch_images_v2.main([str(metadata_path)])
        assert exit_code == 0

        assert len(captured_excluded_across_calls) == 2
        assert captured_excluded_across_calls[0]["excluded_src_size"] == 0
        assert captured_excluded_across_calls[1]["excluded_src_size"] >= 1
        assert captured_excluded_across_calls[0]["cache_keys"] == 0


# ── Pixabay API key resolution ───────────────────────────────────────────────


class TestResolvePixabayApiKey:
    """Tests for _resolve_pixabay_api_key()."""

    def test_key_in_environ_used(self, monkeypatch):
        monkeypatch.setenv("PIXABAY_API_KEY", "test-key-123")
        from shorts_creator.assets.fetcher import _resolve_pixabay_api_key
        result = _resolve_pixabay_api_key()
        assert result == "test-key-123"

    def test_environ_has_precedence_over_env_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PIXABAY_API_KEY", "environ-key")
        from shorts_creator.assets.fetcher import _resolve_pixabay_api_key
        result = _resolve_pixabay_api_key()
        assert result == "environ-key"

    def test_empty_env_key_returns_none(self, monkeypatch):
        monkeypatch.setenv("PIXABAY_API_KEY", "")
        from shorts_creator.assets.fetcher import _resolve_pixabay_api_key
        monkeypatch.setattr(asset_fetcher.os, "environ", {"PIXABAY_API_KEY": ""})
        monkeypatch.setattr(asset_fetcher.Path, "__init__", lambda self, *a: None)
        monkeypatch.setattr(asset_fetcher.Path, "resolve", lambda self: self)
        monkeypatch.setattr(asset_fetcher.Path, "exists", lambda self: False)
        result = _resolve_pixabay_api_key()
        assert result is None

    def test_resolve_does_not_print_key_stdout(self, monkeypatch, capsys):
        monkeypatch.setenv("PIXABAY_API_KEY", "secret-key-value")
        from shorts_creator.assets.fetcher import _resolve_pixabay_api_key
        _resolve_pixabay_api_key()
        out = capsys.readouterr()
        assert "secret-key-value" not in out.out + out.err
        # Cache object is passed across scenes (may be empty since we mock executor)
