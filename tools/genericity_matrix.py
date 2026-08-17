#!/usr/bin/env python3
"""Genericity evaluation matrix — offline, read-only extractor.

Reads persisted pipeline ``metadata.json`` files and extracts a per-job
evaluation row (job, visual plan, assets) for the generic-content-pipeline
evaluation.

Behavior contract (Fase 1):
  - Read-only: never mutates the job metadata.
  - Offline: no network, no LLM calls, no provider searches.
  - Usable as an importable module (``build_job_metrics``) and as a CLI.
  - Reuses the existing pure guard ``contracts.visual_specificity.
    assess_query_specificity`` only for VALID/VAGUE query counts.
  - Does NOT attempt automated factual-quality judgment, and does NOT decide
    whether an image is visually correct from metadata alone. Those remain
    manual review in Fase 2.

Manual fields (coherence, hallucination, query/scene-intent quality, image
false positive, coarse-but-usable) are intentionally NOT derived here.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = str(_PROJECT_ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from shorts_creator.contracts.visual_specificity import assess_query_specificity  # noqa: E402


# ── JOB level ────────────────────────────────────────────────────────────────


def _job_metrics(metadata: dict) -> dict:
    script = metadata.get("script")
    if not isinstance(script, dict):
        script = {}
    scenes = script.get("scenes")
    if not isinstance(scenes, list):
        scenes = []
    duration_contract = metadata.get("durationContract")
    return {
        "jobId": metadata.get("jobId"),
        "topic": metadata.get("topic") or metadata.get("requestedTopic"),
        "status": metadata.get("status"),
        "sceneCount": len(scenes),
        # Bootstrap WPM duration is telemetry only: a FAIL here is NOT an
        # automatic genericity failure (design contract A).
        "bootstrapDurationContractStatus": (
            duration_contract.get("status") if isinstance(duration_contract, dict) else None
        ),
    }


# ── VISUAL PLAN level ────────────────────────────────────────────────────────


def _iter_plan_queries(scenes: list) -> list[dict]:
    """Yield all persisted visual queries as {'kind','path','text'}."""
    queries: list[dict] = []
    for si, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        vp = scene.get("visualPlan")
        if not isinstance(vp, dict):
            continue
        scene_queries = vp.get("searchQueries")
        if isinstance(scene_queries, list):
            for qi, q in enumerate(scene_queries):
                if isinstance(q, str) and q.strip():
                    queries.append({
                        "kind": "scene",
                        "path": f"scenes[{si}].visualPlan.searchQueries[{qi}]",
                        "text": q,
                    })
        seq = vp.get("visualSequence")
        if isinstance(seq, list):
            for vi, seg in enumerate(seq):
                if not isinstance(seg, dict):
                    continue
                sq = seg.get("searchQuery")
                if isinstance(sq, str) and sq.strip():
                    queries.append({
                        "kind": "segment",
                        "path": f"scenes[{si}].visualPlan.visualSequence[{vi}].searchQuery",
                        "text": sq,
                    })
    return queries


def _asset_pref_counts(scenes: list) -> Counter:
    counter: Counter = Counter()
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        vp = scene.get("visualPlan")
        if not isinstance(vp, dict):
            continue
        prefs = vp.get("assetPreferences")
        if isinstance(prefs, list):
            for p in prefs:
                if isinstance(p, str) and p.strip():
                    counter[f"plan:{p}"] += 1
        seq = vp.get("visualSequence")
        if isinstance(seq, list):
            for seg in seq:
                if not isinstance(seg, dict):
                    continue
                ap = seg.get("assetPreference")
                if isinstance(ap, str) and ap.strip():
                    counter[f"segment:{ap}"] += 1
    return counter


def _visual_plan_metrics(metadata: dict) -> dict:
    script = metadata.get("script")
    scenes = script.get("scenes") if isinstance(script, dict) else []
    if not isinstance(scenes, list):
        scenes = []

    queries = _iter_plan_queries(scenes)
    scene_queries = [q for q in queries if q["kind"] == "scene"]
    segment_queries = [q for q in queries if q["kind"] == "segment"]

    valid = 0
    vague = 0
    for q in queries:
        verdict = assess_query_specificity(q["text"]).get("verdict")
        if verdict == "VALID":
            valid += 1
        else:
            vague += 1

    total_segments = 0
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        vp = scene.get("visualPlan")
        if isinstance(vp, dict) and isinstance(vp.get("visualSequence"), list):
            total_segments += len(vp["visualSequence"])

    pref_counter = _asset_pref_counts(scenes)
    return {
        "totalSceneSearchQueries": len(scene_queries),
        "totalSegmentSearchQueries": len(segment_queries),
        "totalQueriesAssessed": len(queries),
        "specificityValid": valid,
        "specificityVague": vague,
        "totalSegments": total_segments,
        "assetPreferencesDistribution": dict(sorted(pref_counter.items())),
    }


# ── ASSETS level ─────────────────────────────────────────────────────────────


def _asset_metrics(metadata: dict) -> dict:
    assets = metadata.get("assets")
    segments: list[dict] = []
    if isinstance(assets, list):
        for entry in assets:
            if not isinstance(entry, dict):
                continue
            segs = entry.get("segments")
            if isinstance(segs, list):
                for seg in segs:
                    if isinstance(seg, dict):
                        segments.append(seg)

    resolved = 0
    unresolved = 0
    provider_counter: Counter = Counter()
    query_used: list[Any] = []
    semantic_assessments: list[dict] = []
    semantic_verdict_counts: Counter = Counter()
    executor_status: Counter = Counter()
    unresolved_reasons: list[Any] = []

    for seg in segments:
        status = seg.get("segmentValidationStatus")
        if status == "PASS":
            resolved += 1
            provider = seg.get("provider")
            if isinstance(provider, str) and provider:
                provider_counter[provider] += 1
            qu = seg.get("queryUsed")
            if isinstance(qu, str) and qu:
                query_used.append(qu)
            sa = seg.get("semanticAssessment")
            if isinstance(sa, dict):
                semantic_assessments.append({
                    "verdict": sa.get("verdict"),
                    "matchedAnchors": sa.get("matchedAnchors"),
                    "anchorTerms": sa.get("anchorTerms"),
                })
                verdict = sa.get("verdict")
                if isinstance(verdict, str):
                    semantic_verdict_counts[verdict] += 1
        else:
            unresolved += 1
            es = seg.get("_executorStatus")
            if isinstance(es, str) and es:
                executor_status[es] += 1
            else:
                executor_status["UNKNOWN"] += 1
            err = seg.get("error")
            if isinstance(err, str) and err:
                unresolved_reasons.append(err)

    total_counted = resolved + unresolved
    ratio = round(resolved / total_counted, 4) if total_counted else None

    has_assets_field = "assets" in metadata
    return {
        "hasAssetsField": has_assets_field,
        "resolved": resolved,
        "unresolvedOrFailed": unresolved,
        "resolutionRatio": ratio,
        "providerDistribution": dict(sorted(provider_counter.items())),
        "queryUsedForResolved": query_used,
        "semanticAssessments": semantic_assessments,
        "semanticVerdictCounts": dict(sorted(semantic_verdict_counts.items())),
        "executorStatusCounts": dict(sorted(executor_status.items())),
        "unresolvedReasons": unresolved_reasons,
    }


# ── Public API ───────────────────────────────────────────────────────────────


def build_job_metrics(metadata: dict) -> dict:
    """Build the full evaluation row for one persisted job metadata dict.

    Does not mutate ``metadata``.
    """
    return {
        "job": _job_metrics(metadata),
        "visualPlan": _visual_plan_metrics(metadata),
        "assets": _asset_metrics(metadata),
    }


def format_table(rows: list[dict]) -> str:
    """Render a compact human-readable table from a list of metric rows."""
    header = (
        "jobId | topic | status | scenes | durBootstrap | scnQ | segQ | "
        "specV/V | totalSeg | res | unres | ratio | providers"
    )
    lines = [header, "-" * len(header)]
    for r in rows:
        job = r["job"]
        vp = r["visualPlan"]
        a = r["assets"]
        providers = ",".join(a["providerDistribution"].keys()) or "-"
        spec = f"{vp['specificityValid']}/{vp['specificityVague']}"
        ratio = "-" if a["resolutionRatio"] is None else f"{a['resolutionRatio']:.2f}"
        lines.append(
            f"{job['jobId']} | {job['topic']} | {job['status']} | {job['sceneCount']} | "
            f"{job['bootstrapDurationContractStatus']} | {vp['totalSceneSearchQueries']} | "
            f"{vp['totalSegmentSearchQueries']} | {spec} | {vp['totalSegments']} | "
            f"{a['resolved']} | {a['unresolvedOrFailed']} | {ratio} | {providers}"
        )
    return "\n".join(lines)


def _load_metadata(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: metadata root must be a JSON object")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline genericity evaluation matrix from persisted job metadata."
    )
    parser.add_argument("metadata_paths", nargs="+", help="One or more metadata.json paths")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit only the machine-readable JSON summary (no human table)",
    )
    args = parser.parse_args(argv)

    rows: list[dict] = []
    for p in args.metadata_paths:
        pth = Path(p)
        if not pth.exists():
            print(f"ERROR: metadata not found: {pth}", file=sys.stderr)
            return 1
        try:
            data = _load_metadata(str(pth))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"ERROR: failed to load {pth}: {exc}", file=sys.stderr)
            return 1
        rows.append({"path": str(pth), **build_job_metrics(data)})

    summary = {
        "tool": "generic-content-pipeline-evaluation",
        "phase": "1",
        "jobs": rows,
    }

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        print("\n### Compact summary")
        print(format_table(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
