#!/usr/bin/env python3
"""Visual fidelity benchmark harness — offline, generic metric evaluation.

Second-stage pixel-validator evaluation for ``asset-visual-semantic-fidelity``
(Slice 1). It does NOT run any model: callers supply externally produced
verdicts (``ACCEPT``/``REJECT``) or numeric scores, and this module computes
benchmark metrics against the human-labeled dataset.

Behavior contract (Slice 1):
  - stdlib-only: no torch / transformers / open_clip / requests / network.
  - Offline: never downloads models or hits any API.
  - Read-only: never mutates the input labels or scores.
  - Labels are the canonical externally-reviewed 38-asset set from
    ``generic-content-pipeline-evaluation`` (CLOSED). Do NOT require the local
    image files to exist: evaluation is purely label + score driven.
  - Binary interpretation: ACCEPT = CLEARLY_RELEVANT + COARSE_BUT_USABLE,
    REJECT = FALSE_POSITIVE_OR_UNUSABLE.
  - Numeric-score mode supports deterministic threshold sweeping and selection.
  - No production threshold is defined. The experiment eligibility target is
    provisional: bad rejection >= 6/8 AND good retention >= 24/30. All
    underlying counts are always reported so the tiny 8-negative dataset is not
    hidden behind percentages.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

# ── Contract constants ───────────────────────────────────────────────────────

ACCEPT = "ACCEPT"
REJECT = "REJECT"

ACCEPTABLE_LABELS: tuple[str, ...] = (
    "CLEARLY_RELEVANT",
    "COARSE_BUT_USABLE",
)
REJECTED_LABELS: tuple[str, ...] = (
    "FALSE_POSITIVE_OR_UNUSABLE",
)

ALLOWED_LABELS: tuple[str, ...] = ACCEPTABLE_LABELS + REJECTED_LABELS

REQUIRED_LABEL_FIELDS: tuple[str, ...] = (
    "topic",
    "jobId",
    "sceneNumber",
    "segmentIndex",
    "assetPath",
    "queryUsed",
    "provider",
    "humanLabel",
)

# Provisional, benchmark-only eligibility target (NOT a production threshold).
ELIGIBILITY_BAD_REJECTED_MIN = 6
ELIGIBILITY_GOOD_RETAINED_MIN = 24

# Default good-asset retention floor for threshold selection.
DEFAULT_MIN_GOOD_RETENTION = 0.80

_FLOAT_EPS = 1e-9


# ── Label validation ─────────────────────────────────────────────────────────


def human_label_to_verdict(label: str) -> str:
    """Map a human label to the binary benchmark verdict."""
    if label in ACCEPTABLE_LABELS:
        return ACCEPT
    if label in REJECTED_LABELS:
        return REJECT
    raise ValueError(
        f"unknown humanLabel {label!r}; allowed: {', '.join(ALLOWED_LABELS)}"
    )


def _entry_key(entry: dict) -> tuple:
    return (
        entry.get("jobId"),
        entry.get("sceneNumber"),
        entry.get("segmentIndex"),
    )


def validate_labels(entries: Sequence[dict]) -> dict[str, Any]:
    """Validate the canonical label dataset.

    Checks schema (required fields), allowed labels, unique
    (jobId, sceneNumber, segmentIndex) keys and non-empty ``queryUsed``.

    Returns a summary dict of counts. Raises ``ValueError`` on any violation.
    """
    if not isinstance(entries, (list, tuple)):
        raise ValueError("labels must be a list of entry dicts")

    errors: list[str] = []
    seen_keys: set[tuple] = set()
    counts = {label: 0 for label in ALLOWED_LABELS}

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"labels[{i}]: entry must be a dict")
            continue
        for field in REQUIRED_LABEL_FIELDS:
            if field not in entry:
                errors.append(f"labels[{i}]: missing required field '{field}'")
        label = entry.get("humanLabel")
        if label not in ALLOWED_LABELS:
            errors.append(
                f"labels[{i}]: invalid humanLabel {label!r}; "
                f"allowed: {', '.join(ALLOWED_LABELS)}"
            )
        else:
            counts[label] += 1
        query_used = entry.get("queryUsed", "")
        if not isinstance(query_used, str) or not query_used.strip():
            errors.append(f"labels[{i}]: queryUsed must be a non-empty string")
        key = _entry_key(entry)
        if key in seen_keys:
            errors.append(
                f"labels[{i}]: duplicate (jobId, sceneNumber, segmentIndex) "
                f"key {key!r}"
            )
        seen_keys.add(key)

    if errors:
        raise ValueError("invalid label dataset:\n  " + "\n  ".join(errors))

    accept = sum(counts[label] for label in ACCEPTABLE_LABELS)
    reject = counts.get("FALSE_POSITIVE_OR_UNUSABLE", 0)
    return {
        "total": len(entries),
        "clearlyRelevant": counts.get("CLEARLY_RELEVANT", 0),
        "coarseButUsable": counts.get("COARSE_BUT_USABLE", 0),
        "falsePositiveOrUnusable": counts.get("FALSE_POSITIVE_OR_UNUSABLE", 0),
        "accept": accept,
        "reject": reject,
        "duplicateKeys": 0,
        "emptyQueryUsed": 0,
    }


def load_labels(path: str | Path) -> list[dict]:
    """Load and validate labels from a JSON file.

    Accepts either a top-level JSON list of entries or a wrapper object with a
    ``labels`` array (as produced for this benchmark).
    """
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and isinstance(data.get("labels"), list):
        entries = data["labels"]
    elif isinstance(data, list):
        entries = data
    else:
        raise ValueError(
            f"{path}: expected a JSON array or an object with a 'labels' array"
        )
    validate_labels(entries)
    return entries


# ── Metric evaluation ────────────────────────────────────────────────────────


def _resolve_per_entry_values(
    entries: Sequence[dict],
    values: Any,
    *,
    what: str,
) -> list[Any]:
    """Normalize ``values`` to a per-entry list (dict keyed by assetPath or list)."""
    if isinstance(values, dict):
        result: list[Any] = []
        missing: list[str] = []
        for entry in entries:
            key = entry.get("assetPath", "")
            if key not in values:
                missing.append(str(key))
            result.append(values.get(key))
        if missing:
            raise ValueError(
                f"{what} missing values for {len(missing)} entries; "
                f"first missing assetPath: {missing[0]!r}"
            )
        return result
    if isinstance(values, (list, tuple)):
        if len(values) != len(entries):
            raise ValueError(
                f"{what} list length {len(values)} != labels length {len(entries)}"
            )
        return list(values)
    raise ValueError(
        f"{what} must be a list aligned with labels or a dict keyed by assetPath"
    )


def _metrics_from_accept_verdicts(
    entries: Sequence[dict],
    accept_mask: list[bool],
) -> dict[str, Any]:
    """Compute benchmark metrics from a per-entry binary accept/reject mask."""
    good = [e for e in entries if human_label_to_verdict(e["humanLabel"]) == ACCEPT]
    bad = [e for e in entries if human_label_to_verdict(e["humanLabel"]) == REJECT]

    acceptable_retained = sum(
        1 for e, a in zip(entries, accept_mask)
        if human_label_to_verdict(e["humanLabel"]) == ACCEPT and a
    )
    bad_rejected = sum(
        1 for e, a in zip(entries, accept_mask)
        if human_label_to_verdict(e["humanLabel"]) == REJECT and not a
    )
    false_acceptances = sum(
        1 for e, a in zip(entries, accept_mask)
        if human_label_to_verdict(e["humanLabel"]) == REJECT and a
    )
    false_rejections = sum(
        1 for e, a in zip(entries, accept_mask)
        if human_label_to_verdict(e["humanLabel"]) == ACCEPT and not a
    )

    good_asset_retention = (
        acceptable_retained / len(good) if good else None
    )
    bad_asset_rejection_recall = bad_rejected / len(bad) if bad else None

    bad_rejection_met = bad_rejected >= ELIGIBILITY_BAD_REJECTED_MIN
    good_retention_met = acceptable_retained >= ELIGIBILITY_GOOD_RETAINED_MIN

    return {
        "total": len(entries),
        "goodAssets": len(good),
        "badAssets": len(bad),
        "acceptableRetained": acceptable_retained,
        "badRejected": bad_rejected,
        "goodAssetRetention": good_asset_retention,
        "badAssetRejectionRecall": bad_asset_rejection_recall,
        "falseAcceptances": false_acceptances,
        "falseRejections": false_rejections,
        "confusionMatrix": {
            "truePositive": acceptable_retained,
            "trueNegative": bad_rejected,
            "falsePositive": false_acceptances,
            "falseNegative": false_rejections,
        },
        "eligibility": {
            "provisionalTarget": {
                "badRejectedMin": ELIGIBILITY_BAD_REJECTED_MIN,
                "goodRetainedMin": ELIGIBILITY_GOOD_RETAINED_MIN,
            },
            "badRejectionMet": bad_rejection_met,
            "goodRetentionMet": good_retention_met,
            "eligible": bad_rejection_met and good_retention_met,
            "note": (
                "provisional benchmark-only target; NOT a production threshold"
            ),
        },
    }


def evaluate_verdicts(entries: Sequence[dict], verdicts: Any) -> dict[str, Any]:
    """Evaluate benchmark metrics from per-entry ACCEPT/REJECT verdicts.

    ``verdicts`` is either a list aligned with ``entries`` or a dict keyed by
    ``assetPath``.
    """
    resolved = _resolve_per_entry_values(entries, verdicts, what="verdicts")
    accept_mask: list[bool] = []
    for i, v in enumerate(resolved):
        if v == ACCEPT:
            accept_mask.append(True)
        elif v == REJECT:
            accept_mask.append(False)
        else:
            raise ValueError(
                f"verdicts[{i}]: expected ACCEPT or REJECT, got {v!r}"
            )
    return _metrics_from_accept_verdicts(entries, accept_mask)


def evaluate_scores(
    entries: Sequence[dict],
    scores: Any,
    threshold: float,
) -> dict[str, Any]:
    """Evaluate metrics at a fixed score threshold.

    Higher score means more similar/relevant; an entry is ACCEPT iff
    ``score >= threshold``.
    """
    resolved = _resolve_per_entry_values(entries, scores, what="scores")
    accept_mask = [s >= threshold for s in resolved]
    return _metrics_from_accept_verdicts(entries, accept_mask)


# ── Threshold sweeping / selection ───────────────────────────────────────────


def threshold_sweep(
    entries: Sequence[dict],
    scores: Any,
    *,
    min_good_retention: float = DEFAULT_MIN_GOOD_RETENTION,
) -> list[dict[str, Any]]:
    """Sweep deterministic thresholds over the score range.

    Candidate thresholds are the midpoints between consecutive sorted unique
    scores, plus the two boundaries ``-inf`` (accept all) and ``+inf``
    (reject all). Midpoints cleanly separate score groups so each threshold is
    a real, reproducible decision value. Each point reports the full metrics
    plus an ``eligible`` flag (provisional target) and whether it satisfies
    ``min_good_retention``.

    Note: a threshold here is a benchmark experiment parameter. It does NOT
    generalize beyond this labeled dataset and must not be treated as a
    production threshold.
    """
    resolved = _resolve_per_entry_values(entries, scores, what="scores")
    if not isinstance(resolved, list):
        resolved = list(resolved)
    unique = sorted({s for s in resolved})
    midpoints = [
        (low + high) / 2.0 for low, high in zip(unique, unique[1:])
    ]
    candidates = [float("-inf")] + midpoints + [float("inf")]

    points: list[dict[str, Any]] = []
    for t in candidates:
        accept_mask = [s >= t for s in resolved]
        metrics = _metrics_from_accept_verdicts(entries, accept_mask)
        retention_ok = (
            metrics["goodAssetRetention"] is not None
            and metrics["goodAssetRetention"] >= min_good_retention - _FLOAT_EPS
        )
        points.append(
            {
                "threshold": t,
                **metrics,
                "minGoodRetention": min_good_retention,
                "meetsMinGoodRetention": retention_ok,
            }
        )
    return points


def select_threshold(
    entries: Sequence[dict],
    scores: Any,
    *,
    min_good_retention: float = DEFAULT_MIN_GOOD_RETENTION,
) -> dict[str, Any]:
    """Deterministically select a score threshold.

    Selection rule (documented, deterministic):
      1. Consider only thresholds where ``goodAssetRetention >=
         min_good_retention`` (default 0.80).
      2. Among those, maximize ``badRejected`` (bad-asset rejection recall
         recall is not a target; the raw count is maximized on this tiny
         8-negative dataset).
      3. Tie-break: among thresholds with the maximal ``badRejected``, choose
         the STRICTEST threshold (highest score threshold -> fewest ACCEPTs).

    This threshold is a benchmark calibration result only. It does NOT
    generalize beyond this labeled dataset and is not a production threshold.

    Returns ``{"selected": bool, "threshold": float|None, "metrics": dict,
    "reason": str}``.
    """
    points = threshold_sweep(
        entries, scores, min_good_retention=min_good_retention
    )
    candidates = [p for p in points if p["meetsMinGoodRetention"]]

    if not candidates:
        return {
            "selected": False,
            "threshold": None,
            "metrics": None,
            "reason": (
                f"no threshold satisfies goodAssetRetention >= {min_good_retention}"
            ),
        }

    max_bad_rejected = max(p["badRejected"] for p in candidates)
    best = max(
        (p for p in candidates if p["badRejected"] == max_bad_rejected),
        key=lambda p: p["threshold"],
    )
    return {
        "selected": True,
        "threshold": best["threshold"],
        "metrics": {
            key: best[key]
            for key in (
                "acceptableRetained",
                "badRejected",
                "goodAssetRetention",
                "badAssetRejectionRecall",
                "falseAcceptances",
                "falseRejections",
                "confusionMatrix",
                "eligibility",
            )
        },
        "reason": (
            f"maximized badRejected={max_bad_rejected} subject to "
            f"goodAssetRetention >= {min_good_retention}; tie-break toward the "
            "strictest threshold"
        ),
    }


# ── CLI ──────────────────────────────────────────────────────────────────────


def _summarize(metrics: dict) -> str:
    return (
        f"total={metrics['total']} good={metrics['goodAssets']} "
        f"bad={metrics['badAssets']} "
        f"retained={metrics['acceptableRetained']}/{metrics['goodAssets']} "
        f"badRejected={metrics['badRejected']}/{metrics['badAssets']} "
        f"retention={metrics['goodAssetRetention']} "
        f"recall={metrics['badAssetRejectionRecall']} "
        f"falseAccept={metrics['falseAcceptances']} "
        f"falseReject={metrics['falseRejections']}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Offline visual fidelity benchmark metrics over the canonical "
            "38-asset labeled dataset (Slice 1)."
        )
    )
    parser.add_argument("labels", help="Path to the labels JSON file")
    parser.add_argument(
        "--scores",
        default=None,
        help=(
            "Path to a JSON dict keyed by assetPath (or list aligned with "
            "labels) of numeric similarity scores; higher = more relevant"
        ),
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Evaluate metrics at a fixed score threshold (score >= threshold => ACCEPT)",
    )
    parser.add_argument(
        "--select-threshold",
        action="store_true",
        help=(
            "Select the deterministic threshold maximizing badRejected subject "
            "to goodAssetRetention >= 0.80 (benchmark calibration only)"
        ),
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="Print the full deterministic threshold sweep",
    )
    args = parser.parse_args(argv)

    try:
        entries = load_labels(args.labels)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: failed to load labels: {exc}", file=sys.stderr)
        return 1

    summary = validate_labels(entries)
    print("### Label dataset")
    print(
        f"total={summary['total']} CR={summary['clearlyRelevant']} "
        f"CU={summary['coarseButUsable']} "
        f"FP={summary['falsePositiveOrUnusable']} "
        f"accept={summary['accept']} reject={summary['reject']}"
    )

    if args.scores is None:
        print("\n(no scores supplied; dataset summary only)")
        return 0

    try:
        with open(args.scores, "r", encoding="utf-8") as fh:
            scores = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: failed to load scores: {exc}", file=sys.stderr)
        return 1

    if args.threshold is not None:
        metrics = evaluate_scores(entries, scores, args.threshold)
        print(f"\n### Metrics @ threshold={args.threshold}")
        print(_summarize(metrics))
        print(json.dumps(metrics, indent=2, ensure_ascii=False))

    if args.select_threshold:
        selected = select_threshold(entries, scores)
        print("\n### Selected threshold (benchmark calibration only)")
        print(json.dumps(selected, indent=2, ensure_ascii=False))

    if args.sweep:
        print("\n### Threshold sweep")
        for p in threshold_sweep(entries, scores):
            print(
                f"t={p['threshold']:+.4f} "
                f"retained={p['acceptableRetained']}/{p['goodAssets']} "
                f"badRejected={p['badRejected']}/{p['badAssets']} "
                f"retention={p['goodAssetRetention']} "
                f"recall={p['badAssetRejectionRecall']} "
                f"eligible={p['eligibility']['eligible']}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
