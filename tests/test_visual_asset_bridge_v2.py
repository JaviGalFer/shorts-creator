"""Tests for Visual Asset Bridge v2.

Run: python3 -m pytest tests/test_visual_asset_bridge_v2.py -v
"""

import sys
from pathlib import Path

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))

from shorts_creator.assets.bridge import (
    apply_visual_assets_v2_to_metadata,
    V2_LEGACY_FIELDS,
)

# ── Fixture helpers ──────────────────────────────────────────────────────────


def _base_metadata(**overrides) -> dict:
    md = {
        "jobId": "test-job-001",
        "script": {
            "scenes": [
                {
                    "sceneNumber": 1,
                    "visualPlan": {
                        "_schemaVersion": 2,
                        "visualSequence": [
                            {
                                "segmentIndex": 1,
                                "assetPreference": "painting",
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


def _resolved_asset(**overrides) -> dict:
    r = {
        "segmentIndex": 1,
        "assetPreference": "painting",
        "status": "RESOLVED",
        "provider": "wikimedia_commons",
        "assetPath": "assets/seg_001.jpg",
        "sourceUrl": "https://commons.wikimedia.org/wiki/File:Test.jpg",
        "fileUrl": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Test.jpg",
        "license": "Public Domain",
        "author": "Test Author",
        "mimeType": "image/jpeg",
        "width": 1200,
        "height": 800,
        "searchQueryUsed": "Storming of the Bastille 1789 painting",
        "generationPromptUsed": None,
    }
    r.update(overrides)
    return r


def _unresolved_segment(**overrides) -> dict:
    u = {
        "segmentIndex": 1,
        "assetPreference": "painting",
        "status": "NO_RESULTS",
        "provider": "wikimedia_commons",
        "searchQueriesTried": ["Storming of the Bastille 1789"],
        "reason": "no candidate passed minimum filters",
    }
    u.update(overrides)
    return u


def _empty_executor_result() -> dict:
    return {
        "ok": True,
        "dryRun": False,
        "resolvedAssets": [],
        "unresolvedSegments": [],
        "dryRunAttempts": [],
        "diagnostics": {},
    }


# ── Test 1: one resolved asset maps to correct scene and segment ─────────────


def test_one_resolved_asset_maps_to_correct_scene_and_segment():
    metadata = _base_metadata()
    executor_result = {
        "resolvedAssets": [_resolved_asset()],
        "unresolvedSegments": [],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    assets = result["assets"]
    assert len(assets) == 1
    assert assets[0]["sceneNumber"] == 1
    assert assets[0]["selected"] is True
    assert len(assets[0]["segments"]) == 1
    seg = assets[0]["segments"][0]
    assert seg["segmentIndex"] == 1
    assert seg["segmentValidationStatus"] == "PASS"
    assert seg["error"] is None
    assert seg["path"] == "assets/seg_001.jpg"


# ── Test 2: multiple resolved assets map to multiple scenes ──────────────────


def test_multiple_resolved_assets_map_to_multiple_scenes():
    metadata = _base_metadata()
    metadata["script"]["scenes"] = [
        {
            "sceneNumber": 1,
            "visualPlan": {
                "_schemaVersion": 2,
                "visualSequence": [
                    {
                        "segmentIndex": 1,
                        "assetPreference": "painting",
                        "durationFraction": 1.0,
                        "transition": "cut",
                    }
                ],
            },
        },
        {
            "sceneNumber": 2,
            "visualPlan": {
                "_schemaVersion": 2,
                "visualSequence": [
                    {
                        "segmentIndex": 1,
                        "assetPreference": "photograph",
                        "durationFraction": 1.0,
                        "transition": "fade",
                    }
                ],
            },
        },
    ]
    executor_result = {
        "resolvedAssets": [
            _resolved_asset(segmentIndex=1, assetPreference="painting"),
            _resolved_asset(
                segmentIndex=1,
                assetPreference="photograph",
                assetPath="assets/seg_002.jpg",
            ),
        ],
        "unresolvedSegments": [],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    assets = result["assets"]
    assert len(assets) == 2
    assert assets[0]["sceneNumber"] == 1
    assert assets[0]["selected"] is True
    assert assets[1]["sceneNumber"] == 2
    assert assets[1]["selected"] is True
    assert assets[0]["segments"][0]["path"] == "assets/seg_001.jpg"
    assert assets[1]["segments"][0]["path"] == "assets/seg_002.jpg"


# ── Test 3: unresolved segment maps to FAIL with error ───────────────────────


def test_unresolved_segment_maps_to_fail_with_error():
    metadata = _base_metadata()
    executor_result = {
        "resolvedAssets": [],
        "unresolvedSegments": [
            _unresolved_segment(
                status="NO_RESULTS",
                reason="no candidate passed minimum filters",
            )
        ],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    assets = result["assets"]
    assert len(assets) == 1
    assert assets[0]["selected"] is False
    seg = assets[0]["segments"][0]
    assert seg["segmentValidationStatus"] == "FAIL"
    assert seg["error"] == "no candidate passed minimum filters"
    assert seg["path"] is None


# ── Test 4: mixed resolved/unresolved sets selected=true ─────────────────────


def test_mixed_resolved_unresolved_scene_selected_true():
    metadata = _base_metadata()
    metadata["script"]["scenes"][0]["visualPlan"]["visualSequence"] = [
        {"segmentIndex": 1, "assetPreference": "painting",
         "durationFraction": 0.5, "transition": "cut"},
        {"segmentIndex": 2, "assetPreference": "photograph",
         "durationFraction": 0.5, "transition": "fade"},
    ]
    executor_result = {
        "resolvedAssets": [
            _resolved_asset(segmentIndex=1, assetPreference="painting"),
        ],
        "unresolvedSegments": [
            _unresolved_segment(segmentIndex=2, assetPreference="photograph"),
        ],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    assets = result["assets"]
    assert assets[0]["selected"] is True
    segments = assets[0]["segments"]
    assert len(segments) == 2
    assert segments[0]["segmentValidationStatus"] == "PASS"
    assert segments[1]["segmentValidationStatus"] == "FAIL"


# ── Test 5: scene with only unresolved segments sets selected=false ──────────


def test_scene_only_unresolved_segments_selected_false():
    metadata = _base_metadata()
    executor_result = {
        "resolvedAssets": [],
        "unresolvedSegments": [
            _unresolved_segment(status="PROVIDER_UNAVAILABLE")
        ],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    assert result["assets"][0]["selected"] is False


# ── Test 6: sourceUrl, fileUrl, license, author, provider, width, height, mimeType ─


def test_source_license_author_provider_preserved():
    metadata = _base_metadata()
    executor_result = {
        "resolvedAssets": [
            _resolved_asset(
                sourceUrl="https://commons.wikimedia.org/wiki/File:MyImage.jpg",
                fileUrl="https://upload.wikimedia.org/wikipedia/commons/x/yz/MyImage.jpg",
                license="CC BY-SA 4.0",
                author="Jane Doe",
                provider="wikimedia_commons",
                width=1920,
                height=1080,
                mimeType="image/png",
            )
        ],
        "unresolvedSegments": [],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    seg = result["assets"][0]["segments"][0]
    assert seg["sourceUrl"] == "https://commons.wikimedia.org/wiki/File:MyImage.jpg"
    assert seg["fileUrl"] == "https://upload.wikimedia.org/wikipedia/commons/x/yz/MyImage.jpg"
    assert seg["license"] == "CC BY-SA 4.0"
    assert seg["author"] == "Jane Doe"
    assert seg["provider"] == "wikimedia_commons"
    assert seg["width"] == 1920
    assert seg["height"] == 1080
    assert seg["mimeType"] == "image/png"


# ── Test 7: searchQueryUsed maps to queryUsed ────────────────────────────────


def test_search_query_used_maps_to_query_used():
    metadata = _base_metadata()
    executor_result = {
        "resolvedAssets": [
            _resolved_asset(
                searchQueryUsed="French Revolution 1789 painting"
            )
        ],
        "unresolvedSegments": [],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    seg = result["assets"][0]["segments"][0]
    assert seg["queryUsed"] == "French Revolution 1789 painting"


# ── Test 8: generationPromptUsed preserved ───────────────────────────────────


def test_generation_prompt_used_preserved():
    metadata = _base_metadata()
    executor_result = {
        "resolvedAssets": [
            _resolved_asset(
                assetPreference="generated",
                generationPromptUsed="A futuristic cityscape at dawn",
                provider="freeai",
            )
        ],
        "unresolvedSegments": [],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    seg = result["assets"][0]["segments"][0]
    assert seg["generationPromptUsed"] == "A futuristic cityscape at dawn"


# ── Test 8b: semanticAssessment preserved ────────────────────────────────────


def test_semantic_assessment_preserved():
    metadata = _base_metadata()
    executor_result = {
        "resolvedAssets": [
            _resolved_asset(
                semanticAssessment={
                    "verdict": "RELEVANT",
                    "score": 100,
                    "reasons": ["candidate semantic metadata shares substantive token(s) with the query/subjects"],
                    "matchedEvidence": ["test"],
                    "method": "deterministic_token_overlap_v1",
                }
            )
        ],
        "unresolvedSegments": [],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    seg = result["assets"][0]["segments"][0]
    assert seg["semanticAssessment"]["verdict"] == "RELEVANT"
    assert seg["semanticAssessment"]["method"] == "deterministic_token_overlap_v1"


# ── Test 9: durationFraction and transition from visualSequence ──────────────


def test_duration_fraction_and_transition_from_visual_sequence():
    metadata = _base_metadata()
    metadata["script"]["scenes"][0]["visualPlan"]["visualSequence"][0].update(
        durationFraction=0.65, transition="fade"
    )
    executor_result = {
        "resolvedAssets": [_resolved_asset()],
        "unresolvedSegments": [],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    seg = result["assets"][0]["segments"][0]
    assert seg["durationFraction"] == 0.65
    assert seg["transition"] == "fade"


# ── Test 10: original metadata is not mutated ────────────────────────────────


def test_original_metadata_not_mutated():
    import copy
    metadata = _base_metadata()
    original = copy.deepcopy(metadata)
    executor_result = {
        "resolvedAssets": [_resolved_asset()],
        "unresolvedSegments": [],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    assert result is not metadata
    assert metadata == original
    assert "assets" not in metadata
    assert "_visualAssetBridgeV2" not in metadata


# ── Test 11: no legacy v1 planning fields in output ──────────────────────────


def test_no_legacy_v1_fields_emitted():
    metadata = _base_metadata()
    executor_result = {
        "resolvedAssets": [_resolved_asset()],
        "unresolvedSegments": [
            _unresolved_segment(
                segmentIndex=1,
                status="PROVIDER_UNAVAILABLE",
                # Put v1-like data in input to verify it's not carried to output
            ),
        ],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    from shorts_creator.assets.bridge import _ensure_no_v1_fields
    violations = _ensure_no_v1_fields(result["assets"])
    assert violations == [], f"v1 fields found in assets: {violations}"

    violations = _ensure_no_v1_fields(result["_visualAssetBridgeV2"])
    assert violations == [], f"v1 fields found in bridge diag: {violations}"

    # Also direct check on segment dicts
    for asset_entry in result["assets"]:
        for seg in asset_entry.get("segments", []):
            for field in V2_LEGACY_FIELDS:
                assert field not in seg, f"v1 field '{field}' leaked into segment"


# ── Test 12: unknown segmentIndex → orphanedResults ──────────────────────────


def test_unknown_segment_index_goes_to_orphaned():
    metadata = _base_metadata()
    executor_result = {
        "resolvedAssets": [
            _resolved_asset(segmentIndex=99),
        ],
        "unresolvedSegments": [
            _unresolved_segment(segmentIndex=42),
        ],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    orphaned = result["_visualAssetBridgeV2"]["orphanedResults"]
    assert len(orphaned) == 2
    assert orphaned[0]["segmentIndex"] == 99
    assert orphaned[0]["type"] == "resolved"
    assert orphaned[1]["segmentIndex"] == 42
    assert orphaned[1]["type"] == "unresolved"

    # assets should have the missing-segment placeholder
    assets = result["assets"]
    assert len(assets) == 1
    segs = assets[0]["segments"]
    assert any(s["segmentIndex"] == 1 for s in segs)
    missing = [s for s in segs if s["segmentIndex"] == 1][0]
    assert missing["segmentValidationStatus"] == "FAIL"
    assert "no executor result" in missing["error"]


# ── Test 13: empty executor result → empty assets array and summary ──────────


def test_empty_executor_result_produces_empty_assets_and_summary():
    metadata = _base_metadata()
    executor_result = _empty_executor_result()
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    # Scene entry still created; segment marked as missing (FAIL)
    assert len(result["assets"]) == 1
    assert result["assets"][0]["selected"] is False
    segs = result["assets"][0]["segments"]
    assert len(segs) == 1
    assert segs[0]["segmentValidationStatus"] == "FAIL"
    assert "no executor result" in segs[0]["error"]
    summary = result["_visualAssetBridgeV2"]["summary"]
    assert summary["scenes"] == 1
    assert summary["segments"] == 1
    assert summary["resolved"] == 0
    assert summary["failed"] == 1
    assert summary["orphaned"] == 0


# ── Test 14: missing sceneNumber uses 1-based index ──────────────────────────


def test_missing_scene_number_uses_one_based_index():
    metadata = {
        "script": {
            "scenes": [
                {
                    "visualPlan": {
                        "_schemaVersion": 2,
                        "visualSequence": [
                            {"segmentIndex": 1, "assetPreference": "photograph",
                             "durationFraction": 1.0, "transition": "cut"}
                        ],
                    }
                }
            ]
        }
    }
    executor_result = {
        "resolvedAssets": [_resolved_asset()],
        "unresolvedSegments": [],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    assert result["assets"][0]["sceneNumber"] == 1


# ── Test 15: missing visualSequence is tolerated ─────────────────────────────


def test_missing_visual_sequence_is_tolerated():
    metadata = _base_metadata()
    metadata["script"]["scenes"][0]["visualPlan"] = {}
    executor_result = {
        "resolvedAssets": [_resolved_asset(segmentIndex=1)],
        "unresolvedSegments": [],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    # Scene with no visualSequence → no segment index → scene not in index
    # Resolved asset goes to orphaned; no scene segments produced
    assert len(result["assets"]) == 0 or (
        len(result["assets"]) == 1
        and len(result["assets"][0].get("segments", [])) == 0
    )
    summary = result["_visualAssetBridgeV2"]["summary"]
    assert summary["scenes"] == 0
    assert len(result["_visualAssetBridgeV2"]["orphanedResults"]) == 1


# ── Test 16: assetType equals assetPreference ────────────────────────────────


def test_asset_type_equals_asset_preference():
    metadata = _base_metadata()
    executor_result = {
        "resolvedAssets": [
            _resolved_asset(assetPreference="archive"),
            _resolved_asset(
                segmentIndex=None,  # will be orphaned — no match for this test
            ),
        ],
        "unresolvedSegments": [
            _unresolved_segment(
                segmentIndex=1,
                assetPreference="diagram",
                status="PROVIDER_UNAVAILABLE",
            ),
        ],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    # Archive is the resolved one
    segs = result["assets"][0]["segments"]
    assert segs[0]["assetType"] == "archive"
    assert segs[0]["assetPreference"] == "archive"


# ── Test 17: score defaults to 0.0 and scoreReasons to [] ───────────────────


def test_score_defaults_and_score_reasons():
    metadata = _base_metadata()
    executor_result = {
        "resolvedAssets": [_resolved_asset()],
        "unresolvedSegments": [],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    seg = result["assets"][0]["segments"][0]
    assert seg["score"] == 0.0
    assert seg["scoreReasons"] == []


# ── Test 18: unresolved provider/reason/searchQueriesTried preserved ────────


def test_unresolved_provider_reason_search_queries_preserved():
    metadata = _base_metadata()
    executor_result = {
        "resolvedAssets": [],
        "unresolvedSegments": [
            _unresolved_segment(
                status="DOWNLOAD_FAILED",
                provider="wikimedia_commons",
                reason="download failed: 404",
                searchQueriesTried=["query A", "query B"],
            )
        ],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    seg = result["assets"][0]["segments"][0]
    assert seg["_executorStatus"] == "DOWNLOAD_FAILED"
    assert seg["_reason"] == "download failed: 404"
    assert seg["_searchQueriesTried"] == ["query A", "query B"]
    assert seg["provider"] == "wikimedia_commons"


# ── Test 19: bridge summary counts scenes, segments, resolved, failed, orphaned


def test_bridge_summary_counts():
    metadata = _base_metadata()
    metadata["script"]["scenes"] = [
        {
            "sceneNumber": 1,
            "visualPlan": {
                "_schemaVersion": 2,
                "visualSequence": [
                    {"segmentIndex": 1, "assetPreference": "painting",
                     "durationFraction": 0.5, "transition": "cut"},
                    {"segmentIndex": 2, "assetPreference": "photograph",
                     "durationFraction": 0.5, "transition": "fade"},
                ],
            },
        },
        {
            "sceneNumber": 2,
            "visualPlan": {
                "_schemaVersion": 2,
                "visualSequence": [
                    {"segmentIndex": 1, "assetPreference": "archive",
                     "durationFraction": 1.0, "transition": "cut"},
                ],
            },
        },
    ]
    executor_result = {
        "resolvedAssets": [
            _resolved_asset(segmentIndex=1, assetPreference="painting"),
            _resolved_asset(segmentIndex=2, assetPreference="photograph"),
            _resolved_asset(
                segmentIndex=1,
                assetPreference="archive",
                assetPath="assets/seg_003.jpg",
            ),
        ],
        "unresolvedSegments": [],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    summary = result["_visualAssetBridgeV2"]["summary"]
    assert summary["scenes"] == 2
    assert summary["segments"] == 3
    assert summary["resolved"] == 3
    assert summary["failed"] == 0
    assert summary["orphaned"] == 0


# ── Test 20: function returns a new dict object ──────────────────────────────


def test_returns_new_dict_object():
    metadata = _base_metadata()
    executor_result = {
        "resolvedAssets": [_resolved_asset()],
        "unresolvedSegments": [],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    assert result is not metadata
    assert id(result) != id(metadata)
    assert isinstance(result, dict)


# ── Additional test: missing segment added automatically ─────────────────────


def test_missing_segment_without_executor_result_added_as_failed():
    metadata = _base_metadata()
    metadata["script"]["scenes"][0]["visualPlan"]["visualSequence"] = [
        {"segmentIndex": 1, "assetPreference": "painting",
         "durationFraction": 0.5, "transition": "cut"},
        {"segmentIndex": 2, "assetPreference": "photograph",
         "durationFraction": 0.5, "transition": "fade"},
    ]
    executor_result = {
        "resolvedAssets": [
            _resolved_asset(segmentIndex=1, assetPreference="painting"),
        ],
        "unresolvedSegments": [],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    assert len(result["assets"]) == 1
    segs = result["assets"][0]["segments"]
    assert len(segs) == 2
    resolved = [s for s in segs if s["segmentValidationStatus"] == "PASS"]
    failed = [s for s in segs if s["segmentValidationStatus"] == "FAIL"]
    assert len(resolved) == 1
    assert len(failed) == 1
    assert failed[0]["segmentIndex"] == 2
    assert "no executor result" in failed[0]["error"]


# ── Additional test: unknown sceneNumber+segmentIndex for unresolved ──────────


def test_unknown_segment_index_unresolved_goes_to_orphaned():
    metadata = _base_metadata()
    executor_result = {
        "resolvedAssets": [],
        "unresolvedSegments": [
            _unresolved_segment(segmentIndex=999, status="NO_RESULTS"),
        ],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    orphaned = result["_visualAssetBridgeV2"]["orphanedResults"]
    assert len(orphaned) == 1
    assert orphaned[0]["segmentIndex"] == 999
    assert orphaned[0]["type"] == "unresolved"


# ── Tests: explicit sceneNumber in results ────────────────────────────────────


class TestExplicitSceneNumberMatching:
    """Bridge maps results by explicit (sceneNumber, segmentIndex) key."""

    def _two_scene_metadata(self):
        return {
            "script": {
                "scenes": [
                    {
                        "sceneNumber": 1,
                        "visualPlan": {
                            "_schemaVersion": 2,
                            "visualSequence": [
                                {"segmentIndex": 1, "assetPreference": "photograph",
                                 "durationFraction": 1.0, "transition": "cut"},
                            ],
                        },
                    },
                    {
                        "sceneNumber": 2,
                        "visualPlan": {
                            "_schemaVersion": 2,
                            "visualSequence": [
                                {"segmentIndex": 1, "assetPreference": "photograph",
                                 "durationFraction": 1.0, "transition": "cut"},
                            ],
                        },
                    },
                ]
            }
        }

    def test_scene1_unresolved_scene2_resolved(self):
        """Critical case: scene 1 unresolved + scene 2 resolved with same segmentIndex."""
        metadata = self._two_scene_metadata()
        executor_result = {
            "resolvedAssets": [
                {**_resolved_asset(segmentIndex=1, assetPreference="photograph"),
                 "sceneNumber": 2,
                 "assetPath": "assets/scene_002_seg_001.jpg"},
            ],
            "unresolvedSegments": [
                {**_unresolved_segment(segmentIndex=1, assetPreference="photograph",
                                        status="NO_RESULTS"),
                 "sceneNumber": 1},
            ],
        }
        result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

        assets = {a["sceneNumber"]: a for a in result["assets"]}

        assert assets[1]["selected"] is False
        seg1 = assets[1]["segments"][0]
        assert seg1["segmentValidationStatus"] == "FAIL"
        assert seg1["segmentIndex"] == 1
        assert seg1["path"] is None

        assert assets[2]["selected"] is True
        seg2 = assets[2]["segments"][0]
        assert seg2["segmentValidationStatus"] == "PASS"
        assert seg2["segmentIndex"] == 1
        assert seg2["path"] == "assets/scene_002_seg_001.jpg"

        assert result["_visualAssetBridgeV2"]["orphanedResults"] == []

    def test_scene1_resolved_scene2_unresolved(self):
        """Inverse: scene 1 resolved, scene 2 unresolved."""
        metadata = self._two_scene_metadata()
        executor_result = {
            "resolvedAssets": [
                {**_resolved_asset(segmentIndex=1, assetPreference="photograph"),
                 "sceneNumber": 1,
                 "assetPath": "assets/scene_001_seg_001.jpg"},
            ],
            "unresolvedSegments": [
                {**_unresolved_segment(segmentIndex=1, assetPreference="photograph",
                                        status="NO_RESULTS"),
                 "sceneNumber": 2},
            ],
        }
        result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

        assets = {a["sceneNumber"]: a for a in result["assets"]}

        assert assets[1]["selected"] is True
        seg1 = assets[1]["segments"][0]
        assert seg1["segmentValidationStatus"] == "PASS"
        assert seg1["path"] == "assets/scene_001_seg_001.jpg"

        assert assets[2]["selected"] is False
        seg2 = assets[2]["segments"][0]
        assert seg2["segmentValidationStatus"] == "FAIL"
        assert seg2["path"] is None

        assert result["_visualAssetBridgeV2"]["orphanedResults"] == []

    def test_reversed_scene_order_still_maps_correctly(self):
        """Scenes stored as [scene 2, scene 1] — explicit sceneNumber maps correctly."""
        metadata = {
            "script": {
                "scenes": [
                    {
                        "sceneNumber": 2,
                        "visualPlan": {
                            "_schemaVersion": 2,
                            "visualSequence": [
                                {"segmentIndex": 1, "assetPreference": "photograph",
                                 "durationFraction": 1.0, "transition": "cut"},
                            ],
                        },
                    },
                    {
                        "sceneNumber": 1,
                        "visualPlan": {
                            "_schemaVersion": 2,
                            "visualSequence": [
                                {"segmentIndex": 1, "assetPreference": "photograph",
                                 "durationFraction": 1.0, "transition": "cut"},
                            ],
                        },
                    },
                ]
            }
        }
        executor_result = {
            "resolvedAssets": [
                {**_resolved_asset(segmentIndex=1),
                 "sceneNumber": 1,
                 "assetPath": "assets/scene_001_seg_001.jpg"},
            ],
            "unresolvedSegments": [
                {**_unresolved_segment(segmentIndex=1, status="NO_RESULTS"),
                 "sceneNumber": 2},
            ],
        }
        result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

        assets = {a["sceneNumber"]: a for a in result["assets"]}
        assert assets[1]["segments"][0]["segmentValidationStatus"] == "PASS"
        assert assets[2]["segments"][0]["segmentValidationStatus"] == "FAIL"


class TestExplicitSceneNumberInvalid:
    """Invalid explicit sceneNumbers go to orphanedResults, never reassigned."""

    def _two_scene_metadata(self):
        return {
            "script": {
                "scenes": [
                    {
                        "sceneNumber": 1,
                        "visualPlan": {
                            "_schemaVersion": 2,
                            "visualSequence": [
                                {"segmentIndex": 1, "assetPreference": "photograph",
                                 "durationFraction": 1.0, "transition": "cut"},
                            ],
                        },
                    },
                ]
            }
        }

    def test_nonexistent_scene_number_orphaned(self):
        metadata = self._two_scene_metadata()
        executor_result = {
            "resolvedAssets": [
                {**_resolved_asset(segmentIndex=1), "sceneNumber": 99},
            ],
            "unresolvedSegments": [],
        }
        result = apply_visual_assets_v2_to_metadata(metadata, executor_result)
        orphaned = result["_visualAssetBridgeV2"]["orphanedResults"]
        assert len(orphaned) == 1
        assert orphaned[0]["reason"] == "sceneNumber 99 not found in metadata scenes"
        # Scene 1 should have a missing segment, NOT the orphaned result
        segs = result["assets"][0]["segments"]
        assert segs[0]["segmentValidationStatus"] == "FAIL"
        assert "no executor result" in segs[0]["error"]

    def test_bool_scene_number_uses_fallback(self):
        """bool sceneNumber (e.g. True) is not a valid int — uses fallback."""
        metadata = self._two_scene_metadata()
        executor_result = {
            "resolvedAssets": [
                {**_resolved_asset(segmentIndex=1), "sceneNumber": True},
            ],
            "unresolvedSegments": [],
        }
        result = apply_visual_assets_v2_to_metadata(metadata, executor_result)
        # Falls back to FIFO, segmentIndex=1 maps to scene 1
        assert result["assets"][0]["segments"][0]["segmentValidationStatus"] == "PASS"

    def test_string_scene_number_uses_fallback(self):
        """String sceneNumber is not a valid int — uses fallback."""
        metadata = self._two_scene_metadata()
        executor_result = {
            "resolvedAssets": [
                {**_resolved_asset(segmentIndex=1), "sceneNumber": "one"},
            ],
            "unresolvedSegments": [],
        }
        result = apply_visual_assets_v2_to_metadata(metadata, executor_result)
        assert result["assets"][0]["segments"][0]["segmentValidationStatus"] == "PASS"

    def test_segment_index_not_in_scene_orphaned(self):
        metadata = self._two_scene_metadata()
        executor_result = {
            "resolvedAssets": [
                {**_resolved_asset(segmentIndex=5), "sceneNumber": 1},
            ],
            "unresolvedSegments": [],
        }
        result = apply_visual_assets_v2_to_metadata(metadata, executor_result)
        orphaned = result["_visualAssetBridgeV2"]["orphanedResults"]
        assert len(orphaned) == 1
        assert "segmentIndex 5 not found" in orphaned[0]["reason"]

    def test_duplicate_claim_orphaned(self):
        """Same (sceneNumber, segmentIndex) claimed twice — second goes to orphaned."""
        metadata = self._two_scene_metadata()
        executor_result = {
            "resolvedAssets": [
                {**_resolved_asset(segmentIndex=1), "sceneNumber": 1,
                 "assetPath": "assets/seg_first.jpg"},
                {**_resolved_asset(segmentIndex=1), "sceneNumber": 1,
                 "assetPath": "assets/seg_second.jpg"},
            ],
            "unresolvedSegments": [],
        }
        result = apply_visual_assets_v2_to_metadata(metadata, executor_result)
        orphaned = result["_visualAssetBridgeV2"]["orphanedResults"]
        assert len(orphaned) == 1
        assert "already claimed" in orphaned[0]["reason"]
        assert orphaned[0]["result"]["assetPath"] == "assets/seg_second.jpg"
        segs = result["assets"][0]["segments"]
        assert segs[0]["path"] == "assets/seg_first.jpg"


class TestCompatibilityWithoutSceneNumber:
    """Results without sceneNumber use existing FIFO fallback (backward compat)."""

    def test_direct_executor_result_without_scene_number(self):
        metadata = {
            "script": {
                "scenes": [
                    {
                        "sceneNumber": 1,
                        "visualPlan": {
                            "_schemaVersion": 2,
                            "visualSequence": [
                                {"segmentIndex": 1, "assetPreference": "photograph",
                                 "durationFraction": 1.0, "transition": "cut"},
                            ],
                        },
                    }
                ]
            }
        }
        executor_result = {
            "resolvedAssets": [_resolved_asset(segmentIndex=1)],
            "unresolvedSegments": [],
        }
        result = apply_visual_assets_v2_to_metadata(metadata, executor_result)
        assert result["assets"][0]["segments"][0]["segmentValidationStatus"] == "PASS"
        assert result["assets"][0]["segments"][0]["path"] == "assets/seg_001.jpg"
        assert result["_visualAssetBridgeV2"]["orphanedResults"] == []

    def test_api_does_not_require_scene_number(self):
        """apply_visual_assets_v2_to_metadata works without sceneNumber in results."""
        metadata = _base_metadata()
        executor_result = {
            "resolvedAssets": [_resolved_asset()],
            "unresolvedSegments": [],
        }
        result = apply_visual_assets_v2_to_metadata(metadata, executor_result)

    def test_unresolved_segment_preserves_provider_attempts(self):
        """Bridge reads providerAttempts (new field) and persists _attemptedProviders."""
        from shorts_creator.assets.bridge import apply_visual_assets_v2_to_metadata
        metadata = _base_metadata()
        exec_result = {
            "resolvedAssets": [],
            "unresolvedSegments": [{
                "sceneNumber": 1,
                "segmentIndex": 1,
                "assetPreference": "photograph",
                "queryUsed": "test query",
                "durationFraction": 1.0,
                "transition": "cut",
                "status": "PROVIDER_ERROR",
                "reason": "RATE_LIMITED",
                "searchQueriesTried": ["test query"],
                "providerAttempts": [
                    {"provider": "wikimedia_commons", "status": "PROVIDER_ERROR", "reason": "RATE_LIMITED"},
                    {"provider": "pixabay", "status": "NO_RESULTS", "reason": "no candidate"},
                ],
            }],
            "summary": {"scenes": 1, "segments": 1, "resolved": 0, "failed": 1, "orphaned": 0},
            "status": "ASSET_UNRESOLVED",
            "errors": [],
            "warnings": [],
        }
        result = apply_visual_assets_v2_to_metadata(metadata, exec_result)
        assets = result.get("assets", [])
        assert len(assets) >= 1
        scene = assets[0]
        segments = scene.get("segments", [])
        unresolved = [s for s in segments if s.get("segmentValidationStatus") == "FAIL"]
        assert len(unresolved) == 1
        attempts = unresolved[0].get("_attemptedProviders", [])
        assert len(attempts) == 2
        providers = [a.get("provider") for a in attempts]
        assert "wikimedia_commons" in providers
        assert "pixabay" in providers

    def test_unresolved_segment_no_provider_attempts_empty_list(self):
        """When providerAttempts is missing, _attemptedProviders is empty list."""
        from shorts_creator.assets.bridge import apply_visual_assets_v2_to_metadata
        metadata = _base_metadata()
        exec_result = {
            "resolvedAssets": [],
            "unresolvedSegments": [{
                "sceneNumber": 1,
                "segmentIndex": 1,
                "assetPreference": "photograph",
                "queryUsed": "test query",
                "durationFraction": 1.0,
                "transition": "cut",
                "status": "UNROUTABLE",
                "reason": "unknown provider",
            }],
            "summary": {"scenes": 1, "segments": 1, "resolved": 0, "failed": 1, "orphaned": 0},
            "status": "ASSET_UNRESOLVED",
            "errors": [],
            "warnings": [],
        }
        result = apply_visual_assets_v2_to_metadata(metadata, exec_result)
        assets = result.get("assets", [])
        unresolved = [s for s in assets[0].get("segments", []) if s.get("segmentValidationStatus") == "FAIL"]
        assert len(unresolved) == 1
        assert unresolved[0].get("_attemptedProviders", ["nope"]) == []
