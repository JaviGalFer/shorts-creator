"""Offline invariants for the frozen Pexels Photo metadata benchmark."""

from __future__ import annotations

import hashlib
import inspect
import json
import sys
from pathlib import Path

import pytest

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "tools"))

import pexels_photo_selection_benchmark as benchmark  # noqa: E402


def test_module_is_import_safe_and_phase_a_has_no_network_or_ml_dependencies():
    source = inspect.getsource(benchmark)
    for forbidden in ("urllib", "requests", "os.environ", "open_clip", "torch", "transformers"):
        assert forbidden not in source


def test_normalization_is_nfkc_casefold_set_based_and_has_no_aliases():
    assert benchmark.normalized_tokens("ＦＯＯ foo PHOTO and 64-bit") == {"foo", "64", "bit"}
    assert benchmark.normalized_tokens("PlayStation N64") == {"playstation", "n64"}
    assert "nintendo" not in benchmark.normalized_tokens("N64")


def test_a1_exact_lexical_recall_has_frozen_known_score():
    assert benchmark.lexical_recall_score("Castle photograph", "Medieval castle on a hill") == 1.0
    assert benchmark.lexical_recall_score("castle engine photograph", "Castle under clouds") == 0.5
    assert benchmark.lexical_recall_score("photograph", "any photo") == 0.0


def test_a2_bm25_uses_query_local_corpus_and_fixed_positive_signal():
    candidates = [
        {"candidateId": 1, "pexelsQueryRank": 1, "alt": "castle castle stone"},
        {"candidateId": 2, "pexelsQueryRank": 2, "alt": "engine piston"},
    ]
    scores = benchmark.bm25_scores("castle photograph", candidates)
    assert scores[1] > 0
    assert scores[2] == 0


@pytest.mark.parametrize("strategy", [benchmark.RAW, benchmark.LEXICAL_RECALL, benchmark.BM25])
def test_ordering_is_stable_and_ties_keep_raw_order(strategy):
    candidates = [
        {"candidateId": 9, "pexelsQueryRank": 2, "alt": "castle"},
        {"candidateId": 8, "pexelsQueryRank": 1, "alt": "castle"},
    ]
    ordered = benchmark.score_candidates(strategy, "castle photograph", candidates)
    assert [item["pexelsQueryRank"] for item in ordered] == [1, 2]


def test_score_api_cannot_receive_human_labels():
    assert "label" not in inspect.signature(benchmark.score_candidates).parameters
    assert "preference" not in inspect.signature(benchmark.score_candidates).parameters


def test_duplicate_raw_rank_is_rejected():
    with pytest.raises(ValueError, match="DUPLICATE_RAW_RANK"):
        benchmark.score_candidates(
            benchmark.RAW,
            "castle",
            [
                {"candidateId": 1, "pexelsQueryRank": 1, "alt": "castle"},
                {"candidateId": 2, "pexelsQueryRank": 1, "alt": "castle"},
            ],
        )


def test_review_subset_has_exactly_ten_queries_and_persisted_top3():
    queries = benchmark.load_review_queries()
    assert len(queries) == 10
    for query in queries:
        candidates = benchmark.load_photo_candidates(query, limit=3)
        assert [candidate["pexelsQueryRank"] for candidate in candidates] == [1, 2, 3]
        assert len({candidate["candidateId"] for candidate in candidates}) == 3


def test_manifest_is_valid_reproducible_and_not_identity_mapping_for_every_query():
    manifest = benchmark.load_manifest()
    identities = 0
    for entry in manifest["queries"]:
        expected = benchmark.blind_alias_order(
            entry["queryUsed"], benchmark.load_photo_candidates(entry["queryUsed"], limit=3)
        )
        assert [(item["alias"], item["candidateId"], item["pexelsQueryRank"]) for item in entry["candidates"]] == [
            (item["alias"], item["candidateId"], item["pexelsQueryRank"]) for item in expected
        ]
        identities += [item["pexelsQueryRank"] for item in entry["candidates"]] == [1, 2, 3]
    assert identities < len(manifest["queries"])


def _write_fixture(tmp_path: Path, status: str, entries: list[dict]) -> Path:
    path = tmp_path / "preferences.json"
    path.write_text(json.dumps({
        "schemaVersion": 1,
        "status": status,
        "preferences": entries,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _unlabeled_entries() -> list[dict]:
    return [
        {"queryUsed": q, "preferredAliases": [], "allUnusable": None, "notes": ""}
        for q in benchmark.CANONICAL_REVIEW_QUERIES
    ]


def _labeled_entries(overrides: dict | None = None) -> list[dict]:
    entries = [
        {"queryUsed": q, "preferredAliases": [], "allUnusable": True, "notes": ""}
        for q in benchmark.CANONICAL_REVIEW_QUERIES
    ]
    for index, data in (overrides or {}).items():
        entries[index].update(data)
    return entries


def test_valid_unlabeled_fixture_maps_to_awaiting(tmp_path, monkeypatch):
    path = _write_fixture(tmp_path, benchmark.UNLABELED, _unlabeled_entries())
    monkeypatch.chdir(tmp_path)
    assert benchmark.validate_preferences(path)["status"] == benchmark.UNLABELED
    assert benchmark.preferences_status(path) == benchmark.AWAITING_HUMAN_REVIEW


def test_valid_labeled_single_preference_maps_to_ready(tmp_path):
    path = _write_fixture(
        tmp_path, benchmark.LABELED,
        _labeled_entries({0: {"preferredAliases": ["A"], "allUnusable": False}}),
    )
    assert benchmark.validate_preferences(path)["status"] == benchmark.LABELED
    assert benchmark.preferences_status(path) == benchmark.HUMAN_REVIEW_READY


def test_labeled_tie_and_all_unusable_are_valid(tmp_path):
    path = _write_fixture(
        tmp_path, benchmark.LABELED,
        _labeled_entries({
            0: {"preferredAliases": ["A", "B", "C"], "allUnusable": False},
            1: {"preferredAliases": [], "allUnusable": True},
        }),
    )
    assert benchmark.validate_preferences(path)["status"] == benchmark.LABELED


def test_labeled_invalid_alias_rejected(tmp_path):
    path = _write_fixture(
        tmp_path, benchmark.LABELED,
        _labeled_entries({0: {"preferredAliases": ["Q"], "allUnusable": False}}),
    )
    assert benchmark.validate_preferences(path)["status"] == "INVALID"
    with pytest.raises(ValueError):
        benchmark.preferences_status(path)


def test_labeled_duplicate_alias_rejected(tmp_path):
    path = _write_fixture(
        tmp_path, benchmark.LABELED,
        _labeled_entries({0: {"preferredAliases": ["A", "A"], "allUnusable": False}}),
    )
    assert benchmark.validate_preferences(path)["status"] == "INVALID"


def test_labeled_false_without_aliases_rejected(tmp_path):
    path = _write_fixture(
        tmp_path, benchmark.LABELED,
        _labeled_entries({0: {"preferredAliases": [], "allUnusable": False}}),
    )
    assert benchmark.validate_preferences(path)["status"] == "INVALID"


def test_labeled_true_with_aliases_rejected(tmp_path):
    path = _write_fixture(
        tmp_path, benchmark.LABELED,
        _labeled_entries({0: {"preferredAliases": ["A"], "allUnusable": True}}),
    )
    assert benchmark.validate_preferences(path)["status"] == "INVALID"


def test_labeled_null_all_unusable_rejected(tmp_path):
    path = _write_fixture(
        tmp_path, benchmark.LABELED,
        _labeled_entries({0: {"preferredAliases": ["A"], "allUnusable": None}}),
    )
    assert benchmark.validate_preferences(path)["status"] == "INVALID"


def test_labeled_duplicate_query_rejected(tmp_path):
    entries = _unlabeled_entries()
    entries[1]["queryUsed"] = entries[0]["queryUsed"]
    for entry in entries:
        entry["allUnusable"] = True
    path = _write_fixture(tmp_path, benchmark.LABELED, entries)
    assert benchmark.validate_preferences(path)["status"] == "INVALID"


def test_labeled_unknown_query_rejected(tmp_path):
    path = _write_fixture(
        tmp_path, benchmark.LABELED,
        _labeled_entries({0: {"preferredAliases": ["A"], "allUnusable": False, "queryUsed": "bogus query"}}),
    )
    assert benchmark.validate_preferences(path)["status"] == "INVALID"


def test_unknown_status_rejected(tmp_path):
    path = _write_fixture(tmp_path, "BOGUS", _unlabeled_entries())
    assert benchmark.validate_preferences(path)["status"] == "INVALID"


def test_result_schema_accepts_frozen_statuses_with_both_hashes():
    for status in (benchmark.AWAITING_HUMAN_REVIEW, benchmark.HUMAN_REVIEW_READY):
        benchmark.validate_result_schema({
            "status": status,
            "sourceArtifactSha256": "a" * 64,
            "reviewManifestSha256": "b" * 64,
        })
    with pytest.raises(ValueError, match="INVALID_RESULT_STATUS"):
        benchmark.validate_result_schema({"status": "invented", "sourceArtifactSha256": "a"})


def test_result_schema_requires_both_hashes():
    with pytest.raises(ValueError, match="MISSING_REVIEW_MANIFEST_HASH"):
        benchmark.validate_result_schema({
            "status": benchmark.HUMAN_REVIEW_READY,
            "sourceArtifactSha256": "a" * 64,
        })


def test_cli_status_works_outside_repo_cwd(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert benchmark.main(["status"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] in {benchmark.AWAITING_HUMAN_REVIEW, benchmark.HUMAN_REVIEW_READY}
    assert isinstance(out["sourceArtifactSha256"], str) and out["sourceArtifactSha256"]
    assert isinstance(out["reviewManifestSha256"], str) and out["reviewManifestSha256"]


def test_source_hash_is_stable_and_reading_does_not_mutate_source_artifact():
    before = benchmark.PHOTO_SOURCE.read_bytes()
    assert benchmark.source_hash() == hashlib.sha256(before).hexdigest()
    for query in benchmark.load_review_queries():
        benchmark.score_candidates(benchmark.BM25, query, benchmark.load_photo_candidates(query))
    assert benchmark.PHOTO_SOURCE.read_bytes() == before


def test_playstation_raw_top3_is_available_without_evaluating_preference():
    candidates = benchmark.load_photo_candidates("PlayStation Nintendo 64 comparison photograph", limit=3)
    assert [candidate["candidateId"] for candidate in candidates] == [9281228, 9281229, 9281226]


def _synthetic_evaluation_inputs(*, all_unusable_index: int | None = None, tied: bool = False):
    manifest_queries = []
    preferences = []
    scored: dict[str, list[dict]] = {}
    for index, query in enumerate(benchmark.CANONICAL_REVIEW_QUERIES):
        base = 10_000 + index * 10
        manifest_queries.append({
            "queryUsed": query,
            "candidates": [
                {"alias": "A", "candidateId": base + 1, "pexelsQueryRank": 1},
                {"alias": "B", "candidateId": base + 2, "pexelsQueryRank": 2},
                {"alias": "C", "candidateId": base + 3, "pexelsQueryRank": 3},
            ],
        })
        unusable = index == all_unusable_index
        preferences.append({
            "queryUsed": query,
            "preferredAliases": [] if unusable else ["C" if query == "PlayStation Nintendo 64 comparison photograph" else "B"],
            "allUnusable": unusable,
            "notes": "",
        })
        order = [2, 1, 3]
        if query == "PlayStation Nintendo 64 comparison photograph":
            order = [3, 2, 1]
        rank_by_raw = {raw_rank: selector_rank for selector_rank, raw_rank in enumerate(order, start=1)}
        scored[query] = [
            {
                "candidateId": base + raw_rank,
                "pexelsQueryRank": raw_rank,
                "selectorScore": 1.0 if tied and raw_rank in {1, 2} else float(4 - rank_by_raw[raw_rank]),
                "selectorRank": rank_by_raw[raw_rank],
            }
            for raw_rank in (1, 2, 3)
        ]
    return {"queries": manifest_queries}, preferences, scored


def test_evaluation_maps_aliases_and_computes_frozen_metrics():
    manifest, preferences, scored = _synthetic_evaluation_inputs(all_unusable_index=1)
    result = benchmark.evaluate_against_preferences(
        strategy=benchmark.LEXICAL_RECALL,
        scored_candidates=scored,
        manifest=manifest,
        preferences=preferences,
    )
    metrics = result["metrics"]
    assert metrics["top1PreferredRate"] == 1.0
    assert metrics["macroPairwiseAccuracy"] == 1.0
    assert metrics["meanPreferredRank"] == 1.0
    assert metrics["beneficialReorders"] == 9
    assert metrics["harmfulReorders"] == 0
    assert metrics["allUnusable"] == 1
    assert result["queries"][0]["preferredCandidateIds"] == [10_002]
    assert result["queries"][1]["top1Preferred"] is None


def test_human_metrics_use_local_review_window_not_global_selector_rank():
    manifest, preferences, scored = _synthetic_evaluation_inputs()
    query = benchmark.CANONICAL_REVIEW_QUERIES[0]
    # The preferred raw #2 is first within the reviewed top-3, but raw #4..#15
    # are globally ahead. Human metrics must still see reviewWindowRank=1.
    scored[query] = [
        {
            "candidateId": 20_000 + raw_rank,
            "pexelsQueryRank": raw_rank,
            "selectorScore": float(16 - raw_rank),
            "selectorRank": raw_rank - 3,
        }
        for raw_rank in range(4, 16)
    ] + [
        {"candidateId": 20_001, "pexelsQueryRank": 1, "selectorScore": 3.0, "selectorRank": 14},
        {"candidateId": 20_002, "pexelsQueryRank": 2, "selectorScore": 4.0, "selectorRank": 13},
        {"candidateId": 20_003, "pexelsQueryRank": 3, "selectorScore": 2.0, "selectorRank": 15},
    ]
    # Keep the manifest/preference IDs aligned with the synthetic candidates.
    manifest["queries"][0]["candidates"] = [
        {"alias": "A", "candidateId": 20_001, "pexelsQueryRank": 1},
        {"alias": "B", "candidateId": 20_002, "pexelsQueryRank": 2},
        {"alias": "C", "candidateId": 20_003, "pexelsQueryRank": 3},
    ]
    result = benchmark.evaluate_against_preferences(
        strategy=benchmark.LEXICAL_RECALL,
        scored_candidates=scored,
        manifest=manifest,
        preferences=preferences,
    )
    first = result["queries"][0]
    assert result["metrics"]["top1PreferredRate"] == 1.0
    assert first["bestPreferredReviewWindowRank"] == 1
    assert first["pairwiseAccuracy"] == 1.0
    preferred = next(candidate for candidate in first["candidates"] if candidate["candidateId"] == 20_002)
    assert preferred["selectorRank"] == 13
    assert preferred["reviewWindowRank"] == 1


def test_evaluation_records_selector_score_ties_and_playstation_check():
    manifest, preferences, scored = _synthetic_evaluation_inputs(tied=True)
    result = benchmark.evaluate_against_preferences(
        strategy=benchmark.BM25,
        scored_candidates=scored,
        manifest=manifest,
        preferences=preferences,
    )
    assert result["metrics"]["selectorTie"] == 9
    assert result["metrics"]["playstationRank3BeforeRank1"] is True


def _strategy_metrics(**overrides):
    metrics = {
        "top1PreferredRate": 0.4,
        "macroPairwiseAccuracy": 0.4,
        "beneficialReorders": 0,
        "harmfulReorders": 0,
        "playstationRank3BeforeRank1": False,
    }
    metrics.update(overrides)
    return {"metrics": metrics}


def test_verdict_validated_prefers_a1_when_both_alternatives_pass():
    results = {
        benchmark.RAW: _strategy_metrics(),
        benchmark.LEXICAL_RECALL: _strategy_metrics(
            top1PreferredRate=0.7,
            macroPairwiseAccuracy=0.6,
            beneficialReorders=2,
            playstationRank3BeforeRank1=True,
        ),
        benchmark.BM25: _strategy_metrics(
            top1PreferredRate=0.8,
            macroPairwiseAccuracy=0.7,
            beneficialReorders=3,
            playstationRank3BeforeRank1=True,
        ),
    }
    assert benchmark.determine_phase_a_verdict(results, {"sufficient": True}) == (
        "METADATA_SELECTOR_VALIDATED", benchmark.LEXICAL_RECALL, False,
    )


def test_verdict_not_useful_and_insufficient_paths_are_frozen():
    results = {
        benchmark.RAW: _strategy_metrics(),
        benchmark.LEXICAL_RECALL: _strategy_metrics(),
        benchmark.BM25: _strategy_metrics(),
    }
    assert benchmark.determine_phase_a_verdict(results, {"sufficient": True}) == (
        "METADATA_SELECTOR_NOT_USEFUL", None, True,
    )
    assert benchmark.determine_phase_a_verdict(results, {"sufficient": False}) == (
        "METADATA_SELECTION_EVIDENCE_INSUFFICIENT", None, False,
    )


def test_evidence_sufficiency_rejects_triple_ties_as_non_discriminating():
    preferences = [
        {
            "queryUsed": query,
            "preferredAliases": ["A", "B", "C"],
            "allUnusable": False,
            "notes": "",
        }
        for query in benchmark.CANONICAL_REVIEW_QUERIES
    ]
    result = benchmark.evidence_sufficiency(preferences)
    assert result["labeledQueries"] == 10
    assert result["discriminatingQueries"] == 0
    assert result["sufficient"] is False


def test_evaluation_artifact_persists_hashes_deterministically(tmp_path):
    manifest, preferences, scored = _synthetic_evaluation_inputs()
    strategy = benchmark.evaluate_against_preferences(
        strategy=benchmark.RAW,
        scored_candidates=scored,
        manifest=manifest,
        preferences=preferences,
    )
    result = {
        "schemaVersion": 1,
        "status": "METADATA_SELECTION_EVIDENCE_INSUFFICIENT",
        "selectedStrategy": None,
        "sourceArtifactSha256": benchmark.source_hash(),
        "reviewManifestSha256": benchmark.manifest_hash(),
        "humanPreferencesSha256": benchmark.human_preferences_hash(),
        "strategyResults": {benchmark.RAW: strategy},
    }
    path = tmp_path / "phase-a.json"
    benchmark.write_phase_a_result(result, path)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["sourceArtifactSha256"] == benchmark.source_hash()
    assert persisted["reviewManifestSha256"] == benchmark.manifest_hash()
    assert persisted["humanPreferencesSha256"] == benchmark.human_preferences_hash()


def test_sealed_labeled_fixture_is_loadable_for_evaluation():
    preferences = benchmark.load_labeled_preferences()
    assert len(preferences) == 10
    assert {entry["queryUsed"] for entry in preferences} == set(benchmark.CANONICAL_REVIEW_QUERIES)


def test_synthetic_evaluation_is_deterministic():
    manifest, preferences, scored = _synthetic_evaluation_inputs()
    first = benchmark.evaluate_against_preferences(
        strategy=benchmark.LEXICAL_RECALL,
        scored_candidates=scored,
        manifest=manifest,
        preferences=preferences,
    )
    second = benchmark.evaluate_against_preferences(
        strategy=benchmark.LEXICAL_RECALL,
        scored_candidates=scored,
        manifest=manifest,
        preferences=preferences,
    )
    assert first == second
