"""Focused tests for tools/visual_fidelity_benchmark.py (Slice 1).

Pure offline logic tests. Uses the canonical 38-asset labels fixture plus
synthetic scores/verdicts. Never touches data/videos assets and never imports
ML/network modules.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = str(_PROJECT_ROOT / "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from visual_fidelity_benchmark import (  # noqa: E402
    ACCEPT,
    ACCEPTABLE_LABELS,
    ALLOWED_LABELS,
    REJECT,
    REJECTED_LABELS,
    _select_best_point,
    evaluate_scores,
    evaluate_verdicts,
    human_label_to_verdict,
    load_labels,
    select_threshold,
    threshold_sweep,
    validate_labels,
)

FIXTURE = Path(__file__).parent / "fixtures" / "asset_visual_fidelity" / "labels.json"


def _canonical() -> list[dict]:
    return load_labels(FIXTURE)


def _canonical_scores(*, good_score: float, bad_score: float) -> dict[str, float]:
    """Synthetic perfect-ish scores: good assets high, bad assets low."""
    scores: dict[str, float] = {}
    for entry in _canonical():
        verdict = human_label_to_verdict(entry["humanLabel"])
        scores[entry["assetPath"]] = good_score if verdict == ACCEPT else bad_score
    return scores


def _bad_entry(**overrides) -> dict:
    entry = {
        "topic": "t",
        "jobId": "j-1",
        "sceneNumber": 1,
        "segmentIndex": 1,
        "assetPath": "data/videos/j/assets/seg.png",
        "queryUsed": "some query",
        "provider": "pixabay",
        "humanLabel": "CLEARLY_RELEVANT",
    }
    entry.update(overrides)
    return entry


# ── Label schema / count validation ──────────────────────────────────────────


def test_canonical_label_schema_validation() -> None:
    summary = validate_labels(_canonical())
    assert summary["total"] == 38
    assert summary["duplicateKeys"] == 0
    assert summary["emptyQueryUsed"] == 0


def test_canonical_totals_exact_16_14_8() -> None:
    summary = validate_labels(_canonical())
    assert summary["clearlyRelevant"] == 16
    assert summary["coarseButUsable"] == 14
    assert summary["falsePositiveOrUnusable"] == 8
    assert summary["accept"] == 30
    assert summary["reject"] == 8


def test_validation_rejects_missing_field() -> None:
    entries = [_bad_entry(queryUsed=None)]
    entries[0].pop("provider")
    try:
        validate_labels(entries)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "missing required field 'provider'" in str(exc)


def test_validation_rejects_unknown_label() -> None:
    entries = [_bad_entry(humanLabel="MAYBE")]
    try:
        validate_labels(entries)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "invalid humanLabel" in str(exc)


def test_validation_rejects_empty_query_used() -> None:
    entries = [_bad_entry(queryUsed="   ")]
    try:
        validate_labels(entries)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "queryUsed must be a non-empty string" in str(exc)


def test_validation_rejects_duplicate_key() -> None:
    base = _bad_entry()
    dup = dict(base)
    entries = [base, dup]
    try:
        validate_labels(entries)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "duplicate (jobId, sceneNumber, segmentIndex)" in str(exc)


# ── ACCEPT/REJECT mapping ────────────────────────────────────────────────────


def test_human_label_to_verdict_mapping() -> None:
    assert {human_label_to_verdict(l) for l in ACCEPTABLE_LABELS} == {ACCEPT}
    assert {human_label_to_verdict(l) for l in REJECTED_LABELS} == {REJECT}
    assert set(ACCEPTABLE_LABELS + REJECTED_LABELS) == set(ALLOWED_LABELS)


def test_human_label_to_verdict_unknown_raises() -> None:
    try:
        human_label_to_verdict("NOPE")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "unknown humanLabel" in str(exc)


# ── Confusion matrix / metrics ───────────────────────────────────────────────


def test_metrics_perfect_verdicts() -> None:
    entries = _canonical()
    verdicts = [human_label_to_verdict(e["humanLabel"]) for e in entries]
    m = evaluate_verdicts(entries, verdicts)
    assert m["acceptableRetained"] == 30
    assert m["badRejected"] == 8
    assert m["falseAcceptances"] == 0
    assert m["falseRejections"] == 0
    assert m["goodAssetRetention"] == 1.0
    assert m["badAssetRejectionRecall"] == 1.0
    assert m["confusionMatrix"] == {
        "truePositive": 30,
        "trueNegative": 8,
        "falsePositive": 0,
        "falseNegative": 0,
    }
    assert m["eligibility"]["eligible"] is True


def test_metrics_accept_all_verdicts() -> None:
    entries = _canonical()
    verdicts = [ACCEPT] * len(entries)
    m = evaluate_verdicts(entries, verdicts)
    assert m["acceptableRetained"] == 30
    assert m["badRejected"] == 0
    assert m["falseAcceptances"] == 8
    assert m["falseRejections"] == 0
    assert m["goodAssetRetention"] == 1.0
    assert m["badAssetRejectionRecall"] == 0.0
    assert m["eligibility"]["eligible"] is False
    assert m["eligibility"]["badRejectionMet"] is False
    assert m["eligibility"]["goodRetentionMet"] is True


def test_metrics_reject_all_verdicts() -> None:
    entries = _canonical()
    verdicts = [REJECT] * len(entries)
    m = evaluate_verdicts(entries, verdicts)
    assert m["acceptableRetained"] == 0
    assert m["badRejected"] == 8
    assert m["falseAcceptances"] == 0
    assert m["falseRejections"] == 30
    assert m["goodAssetRetention"] == 0.0
    assert m["badAssetRejectionRecall"] == 1.0
    assert m["eligibility"]["eligible"] is False


def test_metrics_dict_keyed_verdicts_and_invalid_verdict() -> None:
    entries = _canonical()
    verdicts = {
        e["assetPath"]: human_label_to_verdict(e["humanLabel"]) for e in entries
    }
    m = evaluate_verdicts(entries, verdicts)
    assert m["badRejected"] == 8
    bad = dict(verdicts)
    first = next(iter(bad))
    bad[first] = "MAYBE"
    try:
        evaluate_verdicts(entries, bad)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "expected ACCEPT or REJECT" in str(exc)


def test_metrics_missing_asset_path_in_scores_raises() -> None:
    entries = _canonical()
    scores = {e["assetPath"]: 1.0 for e in entries}
    del scores[entries[0]["assetPath"]]
    try:
        evaluate_scores(entries, scores, 0.5)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "missing values" in str(exc)


# ── Threshold sweep ──────────────────────────────────────────────────────────


def test_threshold_sweep_contains_boundaries() -> None:
    entries = _canonical()
    scores = _canonical_scores(good_score=0.9, bad_score=0.2)
    points = threshold_sweep(entries, scores)
    thresholds = [p["threshold"] for p in points]
    assert thresholds == sorted(thresholds)
    assert thresholds[0] == float("-inf")
    assert thresholds[-1] == float("inf")
    # Midpoint 0.55 between 0.2 and 0.9 perfectly separates: rejects all 8
    # bad, retains all 30 good.
    mid = next(p for p in points if p["threshold"] == 0.55)
    assert mid["acceptableRetained"] == 30
    assert mid["badRejected"] == 8
    assert mid["eligibility"]["eligible"] is True


def test_threshold_sweep_ascending_retention() -> None:
    entries = _canonical()
    scores = _canonical_scores(good_score=0.9, bad_score=0.2)
    points = threshold_sweep(entries, scores)
    retained = [p["acceptableRetained"] for p in points]
    # Retention is non-increasing as the threshold rises.
    assert retained == sorted(retained, reverse=True)


def test_select_threshold_meets_provisional_target() -> None:
    entries = _canonical()
    scores = _canonical_scores(good_score=0.9, bad_score=0.2)
    selected = select_threshold(entries, scores)
    assert selected["selected"] is True
    assert selected["threshold"] == 0.55
    assert selected["metrics"]["acceptableRetained"] == 30
    assert selected["metrics"]["badRejected"] == 8
    assert selected["metrics"]["eligibility"]["eligible"] is True
    assert "strictest threshold" in selected["reason"]


def test_select_threshold_accept_all_degenerate() -> None:
    # Bad assets scored high, good assets scored low: no threshold can reject
    # bad assets while keeping retention >= 0.80, so accept-all (-inf) wins
    # with badRejected == 0 and eligibility False.
    entries = _canonical()
    scores = _canonical_scores(good_score=0.1, bad_score=0.9)
    selected = select_threshold(entries, scores)
    assert selected["selected"] is True
    assert selected["threshold"] == float("-inf")
    assert selected["metrics"]["badRejected"] == 0
    assert selected["metrics"]["falseAcceptances"] == 8
    assert selected["metrics"]["eligibility"]["eligible"] is False
    assert "strictest threshold" in selected["reason"]


def test_select_threshold_no_viable_threshold() -> None:
    entries = _canonical()
    scores = _canonical_scores(good_score=0.9, bad_score=0.2)
    selected = select_threshold(entries, scores, min_good_retention=1.5)
    assert selected["selected"] is False
    assert selected["threshold"] is None
    assert "no threshold" in selected["reason"]


# ── Deterministic tie behavior ───────────────────────────────────────────────


def test_select_threshold_prefers_retained_among_badrejected_ties() -> None:
    entries = _canonical()
    # One good asset gets an intermediate score (0.6). Two thresholds tie on
    # badRejected (8), but the lower threshold (0.4) retains that good asset
    # while the higher one (0.75) would reject it for no additional bad-asset
    # gain. The rule must keep the asset (acceptableRetained 30 > 29).
    scores = _canonical_scores(good_score=0.9, bad_score=0.2)
    tie_key = None
    for e in entries:
        if human_label_to_verdict(e["humanLabel"]) == ACCEPT:
            tie_key = e["assetPath"]
            break
    scores[tie_key] = 0.6

    points = [p for p in threshold_sweep(entries, scores) if p["meetsMinGoodRetention"]]
    max_bad = max(p["badRejected"] for p in points)
    tied = [p for p in points if p["badRejected"] == max_bad]
    assert len(tied) > 1  # tie actually occurs
    assert {p["acceptableRetained"] for p in tied} == {30, 29}

    selected = select_threshold(entries, scores)
    assert selected["selected"] is True
    assert selected["metrics"]["acceptableRetained"] == 30
    assert selected["metrics"]["badRejected"] == 8
    # Not the strictest of the tied thresholds: retained wins.
    assert selected["threshold"] == 0.4
    assert "maximized acceptableRetained=30" in selected["reason"]


def test_select_best_point_strictest_on_full_tie() -> None:
    # Direct unit test of the final tie-break: when badRejected AND
    # acceptableRetained are both tied, the strictest (highest) threshold wins.
    def point(threshold, bad, retained):
        return {
            "threshold": threshold,
            "badRejected": bad,
            "acceptableRetained": retained,
            "meetsMinGoodRetention": True,
        }

    points = [
        point(0.1, 6, 24),
        point(0.4, 6, 24),  # full tie with 0.1
        point(0.7, 6, 22),  # same bad, fewer retained -> loses
        point(0.9, 5, 24),  # fewer bad -> loses
    ]
    best = _select_best_point(points, min_good_retention=0.80)
    assert best["threshold"] == 0.4


def test_select_best_point_retained_beats_strictest() -> None:
    def point(threshold, bad, retained):
        return {
            "threshold": threshold,
            "badRejected": bad,
            "acceptableRetained": retained,
            "meetsMinGoodRetention": True,
        }

    points = [
        point(0.3, 7, 24),
        point(0.8, 7, 23),  # same badRejected but fewer retained -> loses
        point(0.5, 8, 22),  # more badRejected wins
    ]
    best = _select_best_point(points, min_good_retention=0.80)
    assert best["threshold"] == 0.5


def test_select_threshold_is_deterministic() -> None:
    entries = _canonical()
    scores = _canonical_scores(good_score=0.9, bad_score=0.2)
    first = select_threshold(entries, scores)
    second = select_threshold(entries, scores)
    assert first == second
    assert first["threshold"] == second["threshold"]


# ── Score validation ─────────────────────────────────────────────────────────


def test_score_validation_rejects_bool() -> None:
    entries = _canonical()
    scores = _canonical_scores(good_score=0.9, bad_score=0.2)
    scores[entries[0]["assetPath"]] = True
    try:
        evaluate_scores(entries, scores, 0.5)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "bool is not accepted" in str(exc)


def test_score_validation_rejects_nan() -> None:
    entries = _canonical()
    scores = _canonical_scores(good_score=0.9, bad_score=0.2)
    scores[entries[0]["assetPath"]] = float("nan")
    try:
        threshold_sweep(entries, scores)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "non-finite score" in str(exc)


def test_score_validation_rejects_inf() -> None:
    entries = _canonical()
    scores = _canonical_scores(good_score=0.9, bad_score=0.2)
    scores[entries[0]["assetPath"]] = float("inf")
    try:
        select_threshold(entries, scores)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "non-finite score" in str(exc)


def test_score_validation_rejects_non_numeric() -> None:
    entries = _canonical()
    scores = _canonical_scores(good_score=0.9, bad_score=0.2)
    scores[entries[0]["assetPath"]] = "0.9"
    try:
        evaluate_scores(entries, scores, 0.5)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "non-numeric score" in str(exc)


def test_score_validation_boundary_thresholds_still_allowed() -> None:
    # -inf/+inf remain valid internal sweep boundaries even though model scores
    # themselves are required to be finite.
    entries = _canonical()
    scores = _canonical_scores(good_score=0.9, bad_score=0.2)
    points = threshold_sweep(entries, scores)
    assert points[0]["threshold"] == float("-inf")
    assert points[-1]["threshold"] == float("inf")


# ── No input mutation ────────────────────────────────────────────────────────


def test_no_input_mutation() -> None:
    entries = _canonical()
    snapshot = copy.deepcopy(entries)
    verdicts = [ACCEPT] * len(entries)
    evaluate_verdicts(entries, verdicts)
    evaluate_scores(entries, _canonical_scores(good_score=0.9, bad_score=0.2), 0.5)
    threshold_sweep(entries, _canonical_scores(good_score=0.9, bad_score=0.2))
    validate_labels(entries)
    assert entries == snapshot


# ── No dependency on local image files ───────────────────────────────────────


def test_no_dependency_on_data_videos_assets() -> None:
    # Real proof: relabeled clones with deliberately nonexistent paths must
    # evaluate fine. The harness must never require image existence.
    entries = _canonical()
    relabeled = []
    for i, e in enumerate(entries):
        clone = copy.deepcopy(e)
        clone["assetPath"] = f"/definitely/nonexistent/asset_{i:03d}.png"
        relabeled.append(clone)
        assert not Path(clone["assetPath"]).exists()

    summary = validate_labels(relabeled)
    assert summary["total"] == 38

    verdicts = [human_label_to_verdict(e["humanLabel"]) for e in relabeled]
    m_verdicts = evaluate_verdicts(relabeled, verdicts)
    assert m_verdicts["acceptableRetained"] == 30
    assert m_verdicts["badRejected"] == 8

    scores = {
        e["assetPath"]: (0.9 if human_label_to_verdict(e["humanLabel"]) == ACCEPT else 0.2)
        for e in relabeled
    }
    m_scores = evaluate_scores(relabeled, scores, 0.5)
    assert m_scores["total"] == 38
    assert m_scores["acceptableRetained"] == 30
    assert m_scores["badRejected"] == 8


# ── No network / ML imports ──────────────────────────────────────────────────


def test_module_source_has_no_ml_or_network_imports() -> None:
    import re

    source = (Path(_TOOLS) / "visual_fidelity_benchmark.py").read_text(
        encoding="utf-8"
    )
    import_lines = [
        line
        for line in source.splitlines()
        if re.match(r"^\s*(?:import|from)\s+", line)
    ]
    assert import_lines, "expected at least a stdlib import to scan"
    for token in (
        "torch",
        "open_clip",
        "transformers",
        "requests",
        "urllib",
        "socket",
        "subprocess",
        "http",
        "ssl",
    ):
        for line in import_lines:
            assert token not in line, f"forbidden import {token!r}: {line!r}"


def test_fixture_json_matches_canonical_counts() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert data["schemaVersion"] == 1
    assert set(data["allowedLabels"]) == set(ALLOWED_LABELS)
