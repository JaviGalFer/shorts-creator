"""Focused tests for tools/genericity_matrix.py.

Synthetic fixtures only. Does not depend on live data/videos jobs and makes no
network/LLM/provider calls.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = str(_PROJECT_ROOT / "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from genericity_matrix import (  # noqa: E402
    build_job_metrics,
    format_table,
)


def _scene(
    scene_number: int,
    *,
    prefs=(),
    segment_search_query=None,
) -> dict:
    vp = {
        "_schemaVersion": 2,
        "visualIntent": "explain",
        "subjects": ["aurora borealis"],
        "searchQueries": ["aurora borealis solar particles photograph"],
        "assetPreferences": list(prefs) or ["photograph"],
        "visualSequence": [
            {
                "segmentIndex": 1,
                "assetPreference": "photograph",
                "durationFraction": 1.0,
                "searchQuery": segment_search_query,
            }
        ],
    }
    return {
        "sceneNumber": scene_number,
        "visualPlan": vp,
        "voiceover": "Una aurora boreal se forma cuando partículas solares chocan con la atmósfera.",
    }


def _base_metadata(**overrides) -> dict:
    md = {
        "jobId": "test-000000-000000",
        "status": "SCRIPT_DRAFT",
        "topic": "Cómo se forma una aurora boreal",
        "requestedTopic": "Cómo se forma una aurora boreal",
        "request": {
            "duration": {"targetSec": 30, "minSec": 27, "maxSec": 33},
            "visuals": {"sourceProviders": ["wikimedia_commons", "pixabay"]},
        },
        "durationContract": {"status": "PASS"},
        "script": {
            "scenes": [_scene(1)],
        },
    }
    md.update(overrides)
    return md


def _resolved_segment(
    *,
    scene_number=1,
    provider="wikimedia_commons",
    query_used="aurora borealis solar particles photograph",
    semantic=True,
) -> dict:
    seg = {
        "segmentIndex": 1,
        "path": "assets/scene_001_seg_001.jpg",
        "segmentValidationStatus": "PASS",
        "error": None,
        "assetType": "photograph",
        "assetPreference": "photograph",
        "provider": provider,
        "queryUsed": query_used,
        "sourceUrl": "https://example.org/aurora.jpg",
    }
    if semantic:
        seg["semanticAssessment"] = {
            "verdict": "RELEVANT",
            "matchedAnchors": ["aurora", "borealis", "solar"],
            "anchorTerms": ["aurora", "borealis", "particles"],
        }
    return seg


def _unresolved_segment(*, executor_status="NO_RESULTS", reason="no candidate passed") -> dict:
    return {
        "segmentIndex": 1,
        "path": None,
        "segmentValidationStatus": "FAIL",
        "error": reason,
        "assetType": "photograph",
        "assetPreference": "photograph",
        "provider": "wikimedia_commons",
        "_executorStatus": executor_status,
        "_reason": reason,
        "_searchQueriesTried": ["aurora borealis photograph"],
    }


def _metadata_with_assets(segments) -> dict:
    md = _base_metadata()
    md["status"] = "ASSETS_PARTIAL"
    md["assets"] = [{"sceneNumber": 1, "selected": True, "segments": segments}]
    md["_visualAssetBridgeV2"] = {
        "summary": {
            "scenes": 1,
            "segments": len(segments),
            "resolved": sum(1 for s in segments if s["segmentValidationStatus"] == "PASS"),
            "failed": sum(1 for s in segments if s["segmentValidationStatus"] != "PASS"),
            "orphaned": 0,
        }
    }
    return md


def test_valid_extraction_job_and_visual_plan() -> None:
    md = _base_metadata()
    metrics = build_job_metrics(md)

    job = metrics["job"]
    assert job["jobId"] == "test-000000-000000"
    assert job["topic"] == "Cómo se forma una aurora boreal"
    assert job["status"] == "SCRIPT_DRAFT"
    assert job["sceneCount"] == 1
    assert job["bootstrapDurationContractStatus"] == "PASS"

    vp = metrics["visualPlan"]
    assert vp["totalSceneSearchQueries"] == 1
    assert vp["totalSegmentSearchQueries"] == 0  # segment searchQuery is None
    assert vp["totalQueriesAssessed"] == 1
    assert vp["specificityValid"] == 1
    assert vp["specificityVague"] == 0
    assert vp["totalSegments"] == 1
    assert vp["assetPreferencesDistribution"] == {
        "plan:photograph": 1,
        "segment:photograph": 1,
    }

    a = metrics["assets"]
    assert a["hasAssetsField"] is False
    assert a["resolved"] == 0
    assert a["unresolvedOrFailed"] == 0
    assert a["resolutionRatio"] is None
    assert a["persistedAssetSegments"] == 0
    assert a["expectedVisualSegments"] == 1
    assert a["assetSegmentCoverage"] == 0.0
    assert a["resolvedDetails"] == []


def test_assest_partial_resolved_plus_unresolved_mix() -> None:
    segments = [
        _resolved_segment(),
        _unresolved_segment(executor_status="NO_RESULTS", reason="no candidate passed"),
        _unresolved_segment(executor_status="DOWNLOAD_FAILED", reason="download failed"),
    ]
    md = _metadata_with_assets(segments)
    a = build_job_metrics(md)["assets"]

    assert a["resolved"] == 1
    assert a["unresolvedOrFailed"] == 2
    assert a["resolutionRatio"] == 0.3333
    assert a["providerDistribution"] == {"wikimedia_commons": 1}
    assert a["queryUsedForResolved"] == ["aurora borealis solar particles photograph"]
    assert a["semanticVerdictCounts"] == {"RELEVANT": 1}
    assert a["executorStatusCounts"] == {"NO_RESULTS": 1, "DOWNLOAD_FAILED": 1}
    assert len(a["unresolvedReasons"]) == 2

    assert len(a["resolvedDetails"]) == 1
    detail = a["resolvedDetails"][0]
    assert detail["sceneNumber"] == 1
    assert detail["segmentIndex"] == 1
    assert detail["assetPreference"] == "photograph"
    assert detail["provider"] == "wikimedia_commons"
    assert detail["queryUsed"] == "aurora borealis solar particles photograph"
    assert detail["path"] == "assets/scene_001_seg_001.jpg"
    assert detail["sourceUrl"] == "https://example.org/aurora.jpg"
    assert detail["semanticAssessment"]["verdict"] == "RELEVANT"
    assert detail["semanticAssessment"]["anchorTerms"] == ["aurora", "borealis", "particles"]
    assert detail["semanticAssessment"]["matchedAnchors"] == ["aurora", "borealis", "solar"]

    # 3 persisted segments against 1 expected visual-sequence segment (this
    # synthetic scene has 1 planned segment); coverage = persisted / expected.
    assert a["persistedAssetSegments"] == 3
    assert a["expectedVisualSegments"] == 1
    assert a["assetSegmentCoverage"] == 3.0


def test_missing_optional_semantic_assessment() -> None:
    segments = [_resolved_segment(semantic=False), _resolved_segment(semantic=False)]
    md = _metadata_with_assets(segments)
    a = build_job_metrics(md)["assets"]

    assert a["resolved"] == 2
    assert a["semanticAssessments"] == []
    assert a["semanticVerdictCounts"] == {}
    assert all(
        d["semanticAssessment"]["verdict"] is None
        and d["semanticAssessment"]["anchorTerms"] is None
        for d in a["resolvedDetails"]
    )


def test_no_assets() -> None:
    md = _base_metadata()
    md["assets"] = []
    a = build_job_metrics(md)["assets"]

    assert a["hasAssetsField"] is True
    assert a["resolved"] == 0
    assert a["unresolvedOrFailed"] == 0
    assert a["resolutionRatio"] is None
    assert a["persistedAssetSegments"] == 0
    assert a["assetSegmentCoverage"] == 0.0


def test_bootstrap_fail_is_telemetry_not_failure() -> None:
    md = _base_metadata()
    md["durationContract"]["status"] = "FAIL"
    metrics = build_job_metrics(md)

    # The status is surfaced only as a telemetry field; the harness exposes no
    # genericity failure / classification derived from it (contract A).
    assert metrics["job"]["bootstrapDurationContractStatus"] == "FAIL"
    assert "failure" not in metrics
    assert not any("fail" in k.lower() for k in metrics["job"].keys())


def test_input_metadata_not_mutated() -> None:
    md = _metadata_with_assets([_resolved_segment(), _unresolved_segment()])
    snapshot = copy.deepcopy(md)
    build_job_metrics(md)
    assert md == snapshot


def test_format_table_renders() -> None:
    rows = [{"path": "x.json", **build_job_metrics(_metadata_with_assets([_resolved_segment()]))}]
    text = format_table(rows)
    assert "test-000000-000000" in text
    assert "ASSETS_PARTIAL" in text
