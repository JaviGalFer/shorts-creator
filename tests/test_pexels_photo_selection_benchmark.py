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
