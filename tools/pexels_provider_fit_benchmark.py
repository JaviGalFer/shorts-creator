#!/usr/bin/env python3
"""Pexels provider-fit benchmark harness — evaluation-only.

Follow-up to the CLOSED ``pexels-visual-supply-benchmark``. It determines WHEN
Pexels Photos/Video are adequate providers for a segment and whether a
deterministic query adaptation improves Pexels Video for the stock-compatible
(``photograph``-form) cases.

  * It does NOT integrate Pexels into production.
  * It does NOT touch rendering / OpenCLIP / BLIP / VLM / VisualPlan / datasets.
  * It does NOT re-label or modify the canonical / development fixtures.
  * It does NOT apply ML/LLM reranking and does NOT decide relevance.

Pipeline:

  1. Resolve the persisted rows by ``(jobId, sceneNumber, segmentIndex)`` from
     the job ``metadata.json`` files (assetPreference, visualIntent) cross-
     referenced with the label fixtures (queryUsed, topic, provider, humanLabel,
     assetPath). Missing fields are recorded explicitly; the historical
     ``humanLabel`` is context only and is never used to build the policy.
  2. Apply the provisional provider-fit policy (pure): explicit-form precedence
     (diagram/infographic/illustration/painting → INELIGIBLE_EXACT_FORM for both
     providers), ``photograph`` → Photos ELIGIBLE / Video ELIGIBLE_CANDIDATE,
     anything else/unknown → UNDECIDED.
  3. Define a deterministic query adaptation for the photograph-form queries:
     remove the tokens ``photograph``/``photo``/``photography`` only, preserving
     subject/entity/variant/action tokens; normalize spaces; never remove
     diagram/illustration/etc. (those rows are INELIGIBLE and must not be
     converted into B-roll).
  4. Fire NEW Pexels Video search requests ONLY for ELIGIBLE_CANDIDATE queries
     with ``adapted != raw``, deduplicated by adapted query, hard-capped at 40.
     RAW results are reused from the persisted supply evidence (no re-request).
  5. Compare RAW vs ADAPTED technical facts, run exact-ID overlap/duplicate
     analysis, build a ≤10-query deterministic human-review sample and three
     contact sheets (photo current-vs-pexels, video raw-vs-adapted top3, video
     temporal raw-vs-adapted). No automatic semantic judgment.

This module is import-safe and offline: importing it never performs network or
ML calls. Real work happens only through explicit CLI actions (``metadata``,
``policy``, ``adapt``, ``run-adapted``, ``compare``, ``overlap``,
``review-sample``, ``review-clips``, ``contact-sheets``). Pure functions are
unit-testable without network.

Evidence is persisted under ``data/evaluations/pexels-provider-fit-benchmark/``
(git-ignored). The Pexels API key is never printed or persisted.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
TOOLS = str(ROOT / "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

from pexels_video_supply_benchmark import (  # noqa: E402
    CANONICAL_LABELS,
    DEVELOPMENT_LABELS,
    LOCALE,
    PAGE,
    PER_PAGE,
    SEARCH_ENDPOINT as VIDEO_SEARCH_ENDPOINT,
    RequestBudget,
    candidate_portrait_mp4s,
    extract_rate_limit,
    has_portrait_mp4_at_least,
    load_label_file,
    select_review_mp4,
)
from pexels_video_supply_benchmark import _row_from_entry  # noqa: E402

# ── Experiment constants ─────────────────────────────────────────────────────

POLICY_VERSION = "provider-fit-policy-v1"
ADAPT_POLICY_VERSION = "query-adapt-v1"

ORIENTATION_PORTRAIT = "portrait"

# Max NEW Pexels Video search requests for adapted queries.
ADAPTED_MAX_REQUESTS = 40
# Absolute budget including diagnostics (adapted requests only here).
ADAPTED_REQUEST_CAP = ADAPTED_MAX_REQUESTS

# Query-form vocabulary (exact token match on the queryUsed tokens).
EXACT_FORM_TOKENS = frozenset(
    {"diagram", "infographic", "illustration", "painting"}
)
PHOTOGRAPH_TOKENS = frozenset({"photograph", "photo", "photography"})
# Tokens removed by the deterministic photograph-query adaptation.
ADAPT_REMOVE_TOKENS = PHOTOGRAPH_TOKENS

REVIEW_SAMPLE_MAX = 10
REVIEW_MANDATORY_QUERIES: list[str] = [
    "four stroke engine automobile photograph",
    "completed medieval castle photograph",
    "medieval castle construction photograph",
    "medieval castle historical significance photograph",
    "four stroke engine parts photograph",
]

EVAL_DIR = ROOT / "data" / "evaluations" / "pexels-provider-fit-benchmark"
VIDEO_EVAL_DIR = ROOT / "data" / "evaluations" / "pexels-video-supply-benchmark"
PHOTO_EVAL_DIR = ROOT / "data" / "evaluations" / "pexels-visual-supply-benchmark"

PHOTO_SUPPLY_EVIDENCE = PHOTO_EVAL_DIR / "photo-supply-benchmark.json"
VIDEO_SUPPLY_EVIDENCE = VIDEO_EVAL_DIR / "supply-benchmark.json"

# ── Dataset / persisted row resolution ──────────────────────────────────────


def load_all_rows() -> list[dict]:
    """Logical rows for canonical-38 + development-20 (58 rows)."""
    canonical = load_label_file(CANONICAL_LABELS)
    development = load_label_file(DEVELOPMENT_LABELS)
    rows = [_row_from_entry(e, dataset="canonical") for e in canonical]
    rows += [_row_from_entry(e, dataset="development") for e in development]
    return rows


def load_job_metadata(job_id: str) -> dict | None:
    """Load the persisted job ``metadata.json`` (or None when missing)."""
    path = ROOT / "data" / "videos" / job_id / "metadata.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def resolve_segment(
    job_meta: dict, scene_number: int, segment_index: int
) -> dict | None:
    """Resolve the visualPlan segment for a scene/segment in persisted metadata.

    Returns a dict with ``assetPreference`` and ``visualIntent`` (or None when
    the scene/segment cannot be found or ``metadata.json`` is missing).
    """
    if not job_meta:
        return None
    scenes = (job_meta.get("script") or {}).get("scenes") or []
    scene = next(
        (s for s in scenes if s.get("sceneNumber") == scene_number), None
    )
    if scene is None:
        return None
    visual_plan = scene.get("visualPlan") or {}
    sequence = visual_plan.get("visualSequence") or []
    segment = next(
        (s for s in sequence if s.get("segmentIndex") == segment_index), None
    )
    if segment is None:
        return None
    return {
        "assetPreference": segment.get("assetPreference"),
        "visualIntent": visual_plan.get("visualIntent"),
        "persistedSearchQuery": segment.get("searchQuery"),
    }


def build_rows() -> list[dict]:
    """Resolve each label row against the persisted job metadata.

    Fields resolved from metadata are recorded verbatim; absent ones are
    reported as ``MISSING`` (never invented). The historical ``humanLabel`` is
    kept as context only, never used by the provider-fit policy.
    """
    rows = load_all_rows()
    resolved: list[dict] = []
    for row in rows:
        seg = resolve_segment(
            load_job_metadata(row["jobId"]),
            row["sceneNumber"],
            row["segmentIndex"],
        )
        missing: list[str] = []
        if seg is None:
            missing = ["assetPreference", "visualIntent"]
        else:
            if seg["assetPreference"] is None:
                missing.append("assetPreference")
            if seg["visualIntent"] is None:
                missing.append("visualIntent")
        persisted_search_query = seg.get("persistedSearchQuery") if seg else None
        resolved.append(
            {
                **row,
                "assetPreference": (seg or {}).get("assetPreference"),
                "visualIntent": (seg or {}).get("visualIntent"),
                "persistedSearchQuery": persisted_search_query,
                "searchQueryMismatch": bool(
                    persisted_search_query is not None
                    and row["queryUsed"] != persisted_search_query
                ),
                "missing": missing,
                "queryForm": query_form(row["queryUsed"]),
            }
        )
    return resolved


# ── Query-form detection / effective preference ─────────────────────────────


def query_tokens(query: str) -> set[str]:
    """Lowercased alphanumeric tokens of a query string."""
    return set(re.findall(r"[a-z0-9]+", query.lower()))


def query_form(query: str) -> str:
    """Classify a query string by its explicit form term.

    Returns one of: ``exactform`` (diagram/infographic/illustration/painting),
    ``photograph`` (photograph/photo/photography), or ``none``.
    """
    toks = query_tokens(query)
    for form in ("diagram", "infographic", "illustration", "painting"):
        if form in toks:
            return "exactform"
    for form in ("photograph", "photo", "photography"):
        if form in toks:
            return "photograph"
    return "none"


def effective_form(row: dict) -> str:
    """Effective preference category used by the provider-fit policy.

    Forced by the query form actually sent to the provider (the ground truth of
    the search). Rows without an explicit form fall back to the persisted
    ``assetPreference`` when it is one of the closed-form values.
    """
    qf = row.get("queryForm") or query_form(row.get("queryUsed") or "")
    if qf == "photograph":
        return "photograph"
    if qf == "exactform":
        return "exactform"
    pref = row.get("assetPreference")
    if pref in EXACT_FORM_TOKENS:
        return "exactform"
    if pref in PHOTOGRAPH_TOKENS:
        return "photograph"
    return "undecided"


# ── Provider-fit policy (pure) ──────────────────────────────────────────────


def classify_provider_fit(form_category: str) -> dict:
    """Provisional provider-fit verdict for a preference category.

    Verdicts (per provider):

    * ``ELIGIBLE`` — Pexels Photos is a candidate provider.
    * ``ELIGIBLE_CANDIDATE`` — Pexels Video is a candidate (needs adaptation).
    * ``INELIGIBLE_EXACT_FORM`` — explicit-form preference, NOT stock-compatible
      as direct satisfaction; never converted into B-roll automatically.
    * ``UNDECIDED`` — no policy yet; reported for human review.
    """
    if form_category == "exactform":
        return {
            "photos": "INELIGIBLE_EXACT_FORM",
            "video": "INELIGIBLE_EXACT_FORM",
        }
    if form_category == "photograph":
        return {"photos": "ELIGIBLE", "video": "ELIGIBLE_CANDIDATE"}
    return {"photos": "UNDECIDED", "video": "UNDECIDED"}


def row_fit_verdicts(row: dict) -> dict:
    """Provider-fit verdicts for one resolved row."""
    return classify_provider_fit(effective_form(row))


# ── Query adaptation (pure) ─────────────────────────────────────────────────


def adapt_photograph_query(query: str) -> dict:
    """Deterministic adaptation of a photograph-form query.

    Removes ONLY the tokens ``photograph``/``photo``/``photography`` (image-
    static descriptors), preserving subject, entity, variant and action tokens
    (e.g. ``four stroke``, ``medieval``, ``construction``). Whitespace is
    normalised. Exact-form terms are never removed in this phase.
    """
    tokens = query.split()
    removed = [t for t in tokens if t.lower() in ADAPT_REMOVE_TOKENS]
    kept = [t for t in tokens if t.lower() not in ADAPT_REMOVE_TOKENS]
    adapted = " ".join(kept).strip()
    changed = bool(removed) and adapted != query.strip()
    return {
        "rawQuery": query,
        "adaptedQuery": adapted,
        "removedTokens": removed,
        "changed": changed,
        "policyVersion": ADAPT_POLICY_VERSION,
    }


def build_adapted_request_plan(rows: list[dict]) -> list[dict]:
    """Planned NEW adapted requests (deduped, capped, no raw duplicates).

    Only queries whose effective form is ``photograph`` AND whose adapted query
    differs from the raw one. Deduplicated by the exact adapted query; the plan
    never re-requests an existing RAW evidence query string. Hard cap 40.
    """
    by_query = defaultdict(dict)
    for row in rows:
        q = row["queryUsed"]
        by_query[q]["rows"] = by_query[q].get("rows", []) + [row]

    plan: dict[str, dict] = {}
    for query, info in by_query.items():
        row0 = info["rows"][0]
        if effective_form(row0) != "photograph":
            continue
        adaptation = adapt_photograph_query(query)
        if not adaptation["changed"]:
            continue
        adapted = adaptation["adaptedQuery"]
        # Never re-request an already-searched RAW query string.
        if adapted in by_query:
            continue
        entry = plan.setdefault(adapted, {**adaptation, "sourceQueries": [], "rowKeys": []})
        if query not in entry["sourceQueries"]:
            entry["sourceQueries"].append(query)
            entry["rowKeys"].extend(
                f"{r['jobId']} s{r['sceneNumber']}.{r['segmentIndex']}"
                for r in info["rows"]
            )

    ordered = list(plan.values())
    # Deterministic: source queries sorted per entry, plan ordered by them.
    for entry in ordered:
        entry["sourceQueries"] = sorted(entry["sourceQueries"])
        entry["rowKeys"] = sorted(entry["rowKeys"])
    ordered.sort(key=lambda p: p["sourceQueries"])
    return ordered[:ADAPTED_MAX_REQUESTS]


# ── Evidence reuse ──────────────────────────────────────────────────────────


def load_photo_evidence() -> dict:
    """Persisted RAW Pexels Photos evidence (raises when missing)."""
    if not PHOTO_SUPPLY_EVIDENCE.exists():
        raise FileNotFoundError(
            f"missing photo RAW evidence: {PHOTO_SUPPLY_EVIDENCE}"
        )
    return json.loads(PHOTO_SUPPLY_EVIDENCE.read_text(encoding="utf-8"))


def load_video_evidence() -> dict:
    """Persisted RAW Pexels Video evidence (raises when missing)."""
    if not VIDEO_SUPPLY_EVIDENCE.exists():
        raise FileNotFoundError(
            f"missing video RAW evidence: {VIDEO_SUPPLY_EVIDENCE}"
        )
    return json.loads(VIDEO_SUPPLY_EVIDENCE.read_text(encoding="utf-8"))


# ── RAW vs ADAPTED comparison ───────────────────────────────────────────────


def video_supply_facts(parsed: dict) -> dict:
    """Technical facts for a parsed video search response (no semantics)."""
    videos = parsed.get("videos", []) if parsed else []
    top15_ids = [v["id"] for v in videos]
    top3_ids = top15_ids[:3]
    return {
        "total_results": int(parsed.get("total_results", 0)) if parsed else 0,
        "requestError": parsed.get("error") if parsed else None,
        "candidates": len(videos),
        "candidatesWithPortraitMp4": sum(
            1 for v in videos if candidate_portrait_mp4s(v)
        ),
        "atLeast720x1280": sum(
            1 for v in videos if has_portrait_mp4_at_least(v, 720, 1280)
        ),
        "atLeast1080x1920": sum(
            1 for v in videos if has_portrait_mp4_at_least(v, 1080, 1920)
        ),
        "hasOne720x1280": any(has_portrait_mp4_at_least(v, 720, 1280) for v in videos),
        "hasOne1080x1920": any(has_portrait_mp4_at_least(v, 1080, 1920) for v in videos),
        "idsTop15": top15_ids,
        "idsTop3": top3_ids,
    }


def _rank_map(ids: list[int]) -> dict[int, int]:
    return {vid: pos + 1 for pos, vid in enumerate(ids)}


def compare_raw_adapted(raw_parsed: dict, adapted_parsed: dict) -> dict:
    """Compare RAW vs ADAPTED technical facts for one query."""
    raw = video_supply_facts(raw_parsed)
    ada = video_supply_facts(adapted_parsed)
    raw_ids = raw["idsTop15"]
    ada_ids = ada["idsTop15"]
    raw_set = set(raw_ids)
    ada_set = set(ada_ids)
    common = raw_set & ada_set
    raw_ranks = _rank_map(raw_ids)
    ada_ranks = _rank_map(ada_ids)

    rank_changes: dict[str, int] = {}
    for vid in sorted(common, key=lambda v: raw_ranks[v]):
        rr = raw_ranks[vid]
        ar = ada_ranks.get(vid)
        rank_changes[str(vid)] = ar - rr if ar is not None else rr

    return {
        "comparison": {
            "raw_total_results": raw["total_results"],
            "adapted_total_results": ada["total_results"],
            "raw_candidates": raw["candidates"],
            "adapted_candidates": ada["candidates"],
            "raw_720": raw["atLeast720x1280"],
            "adapted_720": ada["atLeast720x1280"],
            "raw_1080": ada["atLeast1080x1920"],
            "adapted_1080": ada["atLeast1080x1920"],
            "raw_has720": raw["hasOne720x1280"],
            "adapted_has720": ada["hasOne720x1280"],
            "raw_has1080": raw["hasOne1080x1920"],
            "adapted_has1080": ada["hasOne1080x1920"],
        },
        "ids": {
            "rawTop15": raw_ids,
            "adaptedTop15": ada_ids,
            "rawTop3": raw["idsTop3"],
            "adaptedTop3": ada["idsTop3"],
            "sharedTop15": sorted(common),
            "sharedTop3": [v for v in ada["idsTop3"] if v in raw_set],
            "newIdsInt21ByAdaptation": sorted(ada_set - raw_set),
            "lostIdsRemoving": sorted(raw_set - ada_set),
            "overlapCount": len(common),
            "overlapTop3": len(set(raw["idsTop3"]) & set(ada["idsTop3"])),
            "rankChanges": rank_changes,
        },
    }


# ── Exact-ID overlap / duplicate analysis ───────────────────────────────────


def jaccard(a: list[int], b: list[int]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def exact_id_overlap_stats(per_query_ids: dict[str, list[int]]) -> dict:
    """Exact-ID dedup metrics over a set of queries' top-N lists."""
    id_to_queries: dict[int, list[str]] = defaultdict(list)
    for query, ids in per_query_ids.items():
        for vid in dict.fromkeys(ids):  # dedup within one query's list
            id_to_queries[vid].append(query)

    repeated_ids = {
        vid: queries
        for vid, queries in id_to_queries.items()
        if len(queries) > 1
    }

    query_keys = list(per_query_ids.keys())
    pairs: list[dict] = []
    for i in range(len(query_keys)):
        for j in range(i + 1, len(query_keys)):
            a, b = query_keys[i], query_keys[j]
            overlap = set(per_query_ids[a]) & set(per_query_ids[b])
            if not overlap:
                continue
            pairs.append(
                {
                    "queries": [a, b],
                    "sharedIds": sorted(overlap),
                    "overlapCount": len(overlap),
                    "jaccard": jaccard(per_query_ids[a], per_query_ids[b]),
                }
            )
    pairs.sort(key=lambda p: (-p["overlapCount"], p["jaccard"], p["queries"]))

    return {
        "queries": len(query_keys),
        "uniqueIds": len(id_to_queries),
        "totalIdOccurrences": sum(len(dict.fromkeys(ids)) for ids in per_query_ids.values()),
        "repeatedIds": {str(vid): qs for vid, qs in repeated_ids.items()},
        "repeatedIdCount": len(repeated_ids),
        "queryPairsWithOverlap": len(pairs),
        "sortedQueryPairs": pairs,
    }


def within_job_repeated_ids(
    per_query_ids: dict[str, list[int]], rows: list[dict]
) -> dict:
    """Repeated IDs across queries belonging to the same job/topic.

    A repeated ID counts as within-job/within-topic when all the queries that
    share it resolve to the same persisted ``jobId`` (or to a single topic).
    """
    id_to_queries: dict[int, list[str]] = defaultdict(list)
    for query, ids in per_query_ids.items():
        for vid in dict.fromkeys(ids):
            id_to_queries[vid].append(query)

    jobs_by_query = {
        r["queryUsed"]: r["jobId"] for r in rows if r.get("jobId")
    }
    topics_by_query: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        if r.get("topic"):
            topics_by_query[r["queryUsed"]].add(r["topic"])

    by_job: dict[str, list[str]] = defaultdict(list)
    for vid, queries in id_to_queries.items():
        if len(queries) < 2:
            continue
        jobs = {jobs_by_query.get(q) for q in queries if jobs_by_query.get(q)}
        topics = {t for q in queries for t in topics_by_query.get(q, [])}
        if len(jobs) == 1 and len(queries) > 1:
            by_job[f"job:{sorted(jobs)[0]}"] = by_job[f"job:{sorted(jobs)[0]}"] + [str(vid)]
        if len(topics) == 1 and len(jobs) == 1:
            by_job[f"topic:{sorted(topics)[0]}"] = by_job[f"topic:{sorted(topics)[0]}"] + [str(vid)]
    return {k: sorted(v) for k, v in by_job.items()}


# ── Review sample (deterministic) ───────────────────────────────────────────


def build_review_sample(
    photo_queries: list[str],
    query_topics: dict[str, list[str]],
    mandatory: list[str] | None = None,
) -> list[dict]:
    """Deterministic ≤10-query review sample from photograph-form queries.

    Algorithm (recorded for reproducibility):

      1. Start with the mandatory queries in their fixed order.
      2. Candidates = remaining photograph-form queries sorted by
         ``(sorted(topic), query)``.
      3. Round-robin over topics: each round add one query per topic (topics in
         sorted order) until 10 or the pool is exhausted. This spreads topics
         and avoids filling the sample with a single job/topic.
    """
    mandatory = list(mandatory if mandatory is not None else REVIEW_MANDATORY_QUERIES)
    sample = [q for q in mandatory if q in photo_queries]
    pool = [q for q in photo_queries if q not in sample]

    def _topics(query: str) -> list[str]:
        return sorted(query_topics.get(query, []))

    while len(sample) < REVIEW_SAMPLE_MAX and pool:
        topics_sorted = sorted({t for q in pool for t in _topics(q)})
        added = False
        for topic in topics_sorted:
            if len(sample) >= REVIEW_SAMPLE_MAX:
                break
            candidates = sorted(q for q in pool if topic in _topics(q))
            if not candidates:
                continue
            chosen = candidates[0]
            sample.append(chosen)
            pool.remove(chosen)
            added = True
        if not added:
            break

    return [
        {"query": q, "mandatory": q in mandatory, "topics": _topics(q)}
        for q in sample
    ]


def query_topics_map(rows: list[dict]) -> dict[str, list[str]]:
    mapping: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if row.get("topic"):
            mapping[row["queryUsed"]].add(row["topic"])
    return {q: sorted(t) for q, t in mapping.items()}


# ── API key (no leak) ───────────────────────────────────────────────────────


def read_project_env() -> dict:
    values: dict = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_api_key() -> str | None:
    env = read_project_env()
    return os.environ.get("PEXELS_API_KEY") or env.get("PEXELS_API_KEY")


# ── Real HTTP (lazy urllib) ─────────────────────────────────────────────────


def _http_get_json(url: str, api_key: str) -> tuple[dict, dict, float]:
    import urllib.request  # lazy

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": api_key,
            "User-Agent": "shorts-creator-benchmark/1.0",
        },
    )
    start = time.monotonic()
    with urllib.request.urlopen(req, timeout=60) as resp:
        latency = time.monotonic() - start
        payload = json.loads(resp.read().decode("utf-8"))
        headers = {k: v for k, v in resp.headers.items()}
    return payload, headers, latency


def _video_search_request(
    query: str, api_key: str, *, budget: RequestBudget
) -> tuple[dict | None, dict, float | None]:
    from pexels_video_supply_benchmark import parse_video_search_response  # lazy

    if not budget.spend():
        return None, {}, None
    params = {
        "query": query,
        "page": PAGE,
        "per_page": PER_PAGE,
        "locale": LOCALE,
        "orientation": ORIENTATION_PORTRAIT,
    }
    url = f"{VIDEO_SEARCH_ENDPOINT}?{urlencode(params)}"
    try:
        payload, headers, latency = _http_get_json(url, api_key)
        return parse_video_search_response(payload), extract_rate_limit(headers), latency
    except Exception as exc:  # noqa: BLE001 — evaluation-only, record and continue
        return {"error": f"{type(exc).__name__}: {exc}", "total_results": 0}, {}, None


def run_adapted_video_requests(api_key: str, out_dir: Path) -> dict:
    """Fire the NEW adapted Pexels Video requests (hard cap 40, dedup)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = build_adapted_request_plan(build_rows())
    budget = RequestBudget(ADAPTED_REQUEST_CAP)
    results: dict[str, dict] = {}
    rate_limits: list[dict] = []
    for item in plan:
        if budget.exhausted:
            break
        parsed, rl, _lat = _video_search_request(
            item["adaptedQuery"], api_key, budget=budget
        )
        rate_limits.append({"query": item["adaptedQuery"], "rateLimit": rl})
        results[item["adaptedQuery"]] = parsed

    record = {
        "schemaVersion": 1,
        "experiment": "pexels-provider-fit-benchmark-adapted-videos",
        "policyVersion": ADAPT_POLICY_VERSION,
        "planned": len(plan),
        "requestsUsed": budget.used,
        "requestCap": ADAPTED_REQUEST_CAP,
        "searchParams": {
            "endpoint": VIDEO_SEARCH_ENDPOINT,
            "per_page": PER_PAGE,
            "page": PAGE,
            "orientation": ORIENTATION_PORTRAIT,
            "locale": LOCALE,
        },
        "perQueryPlan": plan,
        "rateLimits": rate_limits,
        "rawResults": results,
    }
    (out_dir / "adapted-video-supply.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return record


# ── RAW vs ADAPTED comparison / overlap records ─────────────────────────────


def compute_compare_record(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    video_raw = load_video_evidence()["rawResults"]
    adapted = json.loads(
        (out_dir / "adapted-video-supply.json").read_text(encoding="utf-8")
    )
    adapted_raw = adapted.get("rawResults", {})

    photo_raw = load_photo_evidence()["rawResults"]
    photo_ids = {
        q: [p["id"] for p in (photo_raw.get(q) or {}).get("photos", [])[:15]]
        for q in photo_raw
    }
    video_raw_ids = {
        q: [v["id"] for v in (video_raw.get(q) or {}).get("videos", [])[:15]]
        for q in video_raw
    }
    # Adapted results keyed by the RAW query string (1:1 via the plan), so
    # within-job analysis can resolve jobs/topics from the persisted rows.
    adapted_ids: dict[str, list[int]] = {}
    for item in adapted.get("perQueryPlan", []):
        raw_q = item["sourceQueries"][0]
        adapted_q = item["adaptedQuery"]
        adapted_ids[raw_q] = [
            v["id"] for v in (adapted_raw.get(adapted_q) or {}).get("videos", [])[:15]
        ]
    # Fair RAW vs ADAPTED overlap basis: RAW top-15 restricted to the same
    # photograph-form queries that were actually adapted.
    video_raw_photo_only_ids = {
        q: ids for q, ids in video_raw_ids.items() if q in adapted_ids
    }

    comparisons: dict[str, dict] = {}
    for item in adapted.get("perQueryPlan", []):
        raw_q = item["sourceQueries"][0]
        adapted_q = item["adaptedQuery"]
        comparisons[raw_q] = {
            "rawQuery": raw_q,
            "adaptedQuery": adapted_q,
            **compare_raw_adapted(video_raw.get(raw_q), adapted_raw.get(adapted_q)),
        }

    record = {
        "schemaVersion": 1,
        "experiment": "pexels-provider-fit-benchmark-compare",
        "policyVersion": POLICY_VERSION,
        "rawVsAdapted": comparisons,
        "overlap": {
            "photosTop15": exact_id_overlap_stats(photo_ids),
            "videoRawTop15": exact_id_overlap_stats(video_raw_ids),
            "videoRawPhotoOnlyTop15": exact_id_overlap_stats(video_raw_photo_only_ids),
            "videoAdaptedTop15": exact_id_overlap_stats(adapted_ids),
        },
        "withinJobRepeatedIds": {
            "photos": within_job_repeated_ids(photo_ids, rows),
            "videoRaw": within_job_repeated_ids(video_raw_ids, rows),
            "videoRawPhotoOnly": within_job_repeated_ids(video_raw_photo_only_ids, rows),
            "videoAdapted": within_job_repeated_ids(adapted_ids, rows),
        },
    }
    (out_dir / "raw-vs-adapted.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return record


# ── Review clips (RAW reuse + ADAPTED download) ─────────────────────────────


def run_review_clips(out_dir: Path, max_clips: int = 20) -> dict:
    """Download RAW + ADAPTED rank-#1 clips for the review sample (max 20).

    RAW clips reuse the previously persisted cache in the video evidence dir
    when the file already exists; otherwise they are downloaded. ADAPTED clips
    come from the new adapted results. Evaluation-only; failures recorded.
    """
    import urllib.request  # lazy

    out_dir.mkdir(parents=True, exist_ok=True)
    clips_dir = out_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    rows = build_rows()
    sample = build_review_sample(
        sorted({r["queryUsed"] for r in rows if effective_form(r) == "photograph"}),
        query_topics_map(rows),
    )
    sample_queries = [s["query"] for s in sample]

    video_raw = load_video_evidence()["rawResults"]
    adapted = json.loads(
        (out_dir / "adapted-video-supply.json").read_text(encoding="utf-8")
    )
    adapted_raw = adapted.get("rawResults", {})

    # mapping raw query -> adapted query for the review sample
    adapted_by_source = {
        item["sourceQueries"][0]: item["adaptedQuery"]
        for item in adapted.get("perQueryPlan", [])
    }

    cache_dir = VIDEO_EVAL_DIR / "clips"

    def _download(url: str, dest: Path) -> bool:
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "shorts-creator-benchmark/1.0"}
            )
            with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as fh:
                fh.write(resp.read())
            return True
        except Exception:  # noqa: BLE001
            return False

    results: list[dict] = []
    downloaded = 0
    failures = 0

    def _fetch(parsed, query: str, tag: str, dest_dir: Path):
        nonlocal downloaded, failures
        videos = (parsed or {}).get("videos", [])
        if not videos:
            return {"status": "NO_VIDEOS"}
        top = videos[0]
        vf = select_review_mp4(top)
        if vf is None or not vf.get("link"):
            failures += 1
            return {"status": "NO_PORTRAIT_MP4", "pexelsVideoId": top["id"]}
        prefix = f"{query.replace(' ', '_')}__vid{top['id']}"
        cached = cache_dir / f"{prefix}.mp4"
        if tag == "raw" and cached.exists():
            downloaded += 1
            return {
                "status": "OK_CACHED",
                "pexelsVideoId": top["id"],
                "selectedResolution": f"{vf['width']}x{vf['height']}",
                "localPath": str(cached),
            }
        if downloaded >= max_clips:
            return {"status": "SKIPPED_CAP"}
        dest = dest_dir / f"{prefix}__{tag}.mp4"
        if dest.exists():
            downloaded += 1
            return {
                "status": "OK_CACHED",
                "pexelsVideoId": top["id"],
                "selectedResolution": f"{vf['width']}x{vf['height']}",
                "localPath": str(dest),
            }
        if not _download(vf["link"], dest):
            failures += 1
            return {"status": "DOWNLOAD_FAILED", "pexelsVideoId": top["id"]}
        downloaded += 1
        return {
            "status": "OK",
            "pexelsVideoId": top["id"],
            "pexelsUrl": top["url"],
            "videoDuration": top["duration"],
            "videoOriginalResolution": f"{top['width']}x{top['height']}",
            "selectedFile": vf["link"],
            "selectedQuality": vf["quality"],
            "selectedResolution": f"{vf['width']}x{vf['height']}",
            "fps": vf["fps"],
            "localPath": str(dest),
        }

    for query in sample_queries:
        if downloaded >= max_clips:
            results.append(
                {
                    "query": query,
                    "rawRank1": {"status": "SKIPPED_CAP"},
                    "adaptedRank1": {"status": "SKIPPED_CAP"},
                }
            )
            continue
        raw_result = _fetch(video_raw.get(query), query, "raw", clips_dir)
        adapted_q = adapted_by_source.get(query)
        ada_result = None
        if adapted_q:
            ada_result = _fetch(adapted_raw.get(adapted_q), query, "adapted", clips_dir)
        results.append(
            {
                "query": query,
                "rawRank1": raw_result,
                "adaptedRank1": ada_result,
            }
        )

    record = {
        "schemaVersion": 1,
        "experiment": "pexels-provider-fit-benchmark-review-clips",
        "queries": len(sample_queries),
        "downloaded": downloaded,
        "failures": failures,
        "results": results,
    }
    (out_dir / "review-clips.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return record


# ── Docker ffmpeg helpers (frame extraction) ────────────────────────────────


def _docker_cmd(
    project_root: Path, args: list[str], timeout: int = 180, *, entrypoint: str | None = None
):
    import subprocess  # lazy

    env = dict(os.environ)
    env.pop("DOCKER_API_VERSION", None)
    docker_args = ["docker", "run", "--rm", "-v", f"{project_root}:/workspace"]
    if entrypoint:
        docker_args += ["--entrypoint", entrypoint]
    cmd = docker_args + ["linuxserver/ffmpeg:latest"] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)


def _docker_probe_duration(ws_rel: str, project_root: Path) -> float | None:
    import json as _json

    res = _docker_cmd(
        project_root,
        ["-v", "quiet", "-print_format", "json", "-show_format", ws_rel],
        timeout=120,
        entrypoint="ffprobe",
    )
    if res.returncode != 0:
        return None
    try:
        return float(_json.loads(res.stdout)["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        return None


def _docker_extract_frame(
    ws_rel: str, timestamp: float, output_ws_rel: str, project_root: Path
) -> bool:
    res = _docker_cmd(
        project_root,
        ["-y", "-ss", f"{timestamp:.3f}", "-i", ws_rel, "-frames:v", "1", "-q:v", "2", output_ws_rel],
        timeout=180,
    )
    return res.returncode == 0


# ── Contact-sheet layout helper (pure) ──────────────────────────────────────


def compute_thumbnail_rect(
    img_size: tuple[int, int], target_w: int, target_h: int
) -> tuple[int, int]:
    """Fit an image into a target box preserving aspect ratio (no crop)."""
    w, h = img_size
    if w <= 0 or h <= 0:
        return (target_w, target_h)
    scale = min(target_w / w, target_h / h)
    return (max(1, int(w * scale)), max(1, int(h * scale)))


# ── Contact sheets ──────────────────────────────────────────────────────────


def _download_media(url: str, dest: Path) -> bool:
    import urllib.request  # lazy

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "shorts-creator-benchmark/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as fh:
            fh.write(resp.read())
        return True
    except Exception:  # noqa: BLE001
        return False


def _load_image(path: Path, target: tuple[int, int], fill="lightgray"):
    from PIL import Image

    thumb = None
    if path and Path(path).exists():
        try:
            thumb = Image.open(path).convert("RGB")
        except Exception:  # noqa: BLE001
            thumb = None
    if thumb is None:
        thumb = Image.new("RGB", target, fill)
        return thumb, (target[0], target[1])
    dw, dh = compute_thumbnail_rect(thumb.size, target[0], target[1])
    thumb = thumb.resize((dw, dh), Image.LANCZOS)
    return thumb, (dw, dh)


def _draw_wrap(dr, text, x, y, max_w, fnt, fill, line_h=15):
    yy = y
    for raw_line in text.split("\n"):
        words = raw_line.split(" ")
        cur = ""
        for w in words:
            trial = (cur + " " + w).strip()
            if dr.textlength(trial, font=fnt) <= max_w:
                cur = trial
            else:
                if cur:
                    dr.text((x, yy), cur, fill=fill, font=fnt)
                    yy += line_h
                cur = w
        if cur:
            dr.text((x, yy), cur, fill=fill, font=fnt)
            yy += line_h
    return yy


def _fonts():
    from PIL import ImageDraw, ImageFont

    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 16)
        font_sm = ImageFont.truetype("DejaVuSans.ttf", 13)
        font_xs = ImageFont.truetype("DejaVuSans.ttf", 11)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()
        font_sm = font
        font_xs = font
    return ImageDraw, font, font_sm, font_xs


def _review_sample_queries() -> list[str]:
    rows = build_rows()
    return [
        s["query"]
        for s in build_review_sample(
            sorted({r["queryUsed"] for r in rows if effective_form(r) == "photograph"}),
            query_topics_map(rows),
        )
    ]


def generate_contact_sheets(out_dir: Path) -> dict:
    """Build the three human-review PNGs.

    01-provider-fit-photo-current-top3.png: CURRENT | PEXELS PHOTO #1 | #2 | #3
    02-provider-fit-video-raw-vs-adapted-top3.png: RAW vs ADAPTED top-3 previews
    03-provider-fit-video-temporal.png: RAW vs ADAPTED rank-#1 temporal frames
      at 20/50/80 % of clip duration.

    No semantic judgment; pure technical evidence for external human review.
    """
    from PIL import Image, ImageDraw  # noqa: F401  (ImageDraw used via _fonts)

    out_dir.mkdir(parents=True, exist_ok=True)

    rows = build_rows()
    rows_by_query = {r["queryUsed"]: r for r in rows}
    sample_queries = _review_sample_queries()

    photo_evidence = load_photo_evidence()["rawResults"]
    video_evidence = load_video_evidence()["rawResults"]
    adapted = json.loads(
        (out_dir / "adapted-video-supply.json").read_text(encoding="utf-8")
    )
    adapted_results = adapted.get("rawResults", {})

    report: dict = {}
    # ══ 01 photo current-vs-pexels ═══════════════════════════════════════════
    report["photoContactSheet"] = _sheet01_photo_current_vs_pexels(
        out_dir, sample_queries, rows_by_query, photo_evidence
    )

    # ══ 02 video raw-vs-adapted top3 ═════════════════════════════════════════
    report["videoTop3ContactSheet"] = _sheet02_video_raw_vs_adapted(
        out_dir, sample_queries, video_evidence, adapted_results
    )

    # ══ 03 video temporal raw-vs-adapted ═════════════════════════════════════
    review = json.loads((out_dir / "review-clips.json").read_text(encoding="utf-8"))
    report["temporalContactSheet"] = _sheet03_video_temporal(
        out_dir, review.get("results", [])
    )

    (out_dir / "contact-sheets.json").write_text(
        json.dumps({"schemaVersion": 1, **report, "queries": len(sample_queries)}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def _sheet01_photo_current_vs_pexels(
    out_dir: Path, sample_queries: list[str], rows_by_query: dict, photo_evidence: dict
) -> str:
    from PIL import Image

    ImageDraw, font, font_sm, font_xs = _fonts()
    prev_dir = out_dir / "photo_prev"
    prev_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = PHOTO_EVAL_DIR / "photos"

    cell_w, cell_h, label_h, row_gap, col_gap = 300, 420, 96, 20, 14
    n_cols = 4
    img_w = 16 + n_cols * cell_w + (n_cols - 1) * col_gap + 16
    img_h = 16 + sum(label_h + row_gap + cell_h for _ in sample_queries) + 16

    sheet = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(sheet)
    y = 16

    for query in sample_queries:
        row = rows_by_query.get(query) or {}
        cur_path = row.get("assetPath")
        cur_full = ROOT / cur_path if cur_path else None
        photos = (photo_evidence.get(query) or {}).get("photos", [])[:3]

        _draw_wrap(
            draw,
            f"{query}  |  {row.get('jobId')} s{row.get('sceneNumber')}.{row.get('segmentIndex')}",
            16, y, img_w - 32, font_sm, "black",
        )
        yy = y + label_h
        cols = [16 + i * (cell_w + col_gap) for i in range(n_cols)]

        _place = lambda path, bx, by: _place_cell(sheet, path, bx, by, cell_w - 12, cell_h - 12)
        _place(cur_full, cols[0], yy)
        _draw_wrap(draw, f"CURRENT\n{row.get('provider','')}", cols[0] + 4, yy + cell_h, cell_w - 8, font_xs, "black")

        for idx, ph in enumerate(photos, start=1):
            pid = ph.get("id")
            cached = cache_dir / f"{query.replace(' ', '_')}__pid{pid}__rank{idx}.jpg"
            path = cached if cached.exists() else None
            if path is None:
                src = (ph.get("src") or {}).get("large2x") or (ph.get("src") or {}).get("large")
                dest = prev_dir / f"{query.replace(' ', '_')}__pid{pid}__rank{idx}.jpg"
                if src and _download_media(src, dest):
                    path = dest
            _place(path, cols[idx], yy)
            _draw_wrap(
                draw,
                f"PEXELS PHOTO #{idx}  pid {pid}\n{ph.get('width')}x{ph.get('height')}\n{ph.get('photographer','')}",
                cols[idx] + 4, yy + cell_h, cell_w - 8, font_xs, "black",
            )
        y = y + label_h + cell_h + row_gap

    dest = out_dir / "01-provider-fit-photo-current-top3.png"
    sheet.save(dest)
    return str(dest)


def _place_cell(sheet, path, box_x, box_y, target_w, target_h, fill="lightgray"):
    from PIL import Image

    thumb, (dw, dh) = _load_image(Path(path) if path else None, (target_w, target_h), fill=fill)
    x = box_x + (target_w - dw) // 2
    y = box_y + (target_h - dh) // 2
    sheet.paste(thumb, (x, y))


def _sheet02_video_raw_vs_adapted(
    out_dir: Path, sample_queries: list[str], video_evidence: dict, adapted_results: dict
) -> str:
    from PIL import Image

    ImageDraw, font, font_sm, font_xs = _fonts()
    prev_dir = out_dir / "video_prev"
    prev_dir.mkdir(parents=True, exist_ok=True)

    adapted = json.loads((out_dir / "adapted-video-supply.json").read_text(encoding="utf-8"))
    adapted_by_source = {
        item["sourceQueries"][0]: item["adaptedQuery"]
        for item in adapted.get("perQueryPlan", [])
    }

    cell_w, cell_h, thumb_w, thumb_h = 200, 360, 180, 240
    label_h = 64
    rows_total = len(sample_queries) * 2  # RAW row + ADAPTED row per query
    img_w2 = cell_w * 3 + 60
    img_h2 = 20 + sum(label_h + thumb_h for _ in range(rows_total)) + 20
    sheet2 = Image.new("RGB", (img_w2, img_h2), "white")
    draw2 = ImageDraw.Draw(sheet2)

    y2 = 10
    for query in sample_queries:
        adapted_q = adapted_by_source.get(query)
        raws = (video_evidence.get(query) or {}).get("videos", [])[:3]
        adas = (adapted_results.get(adapted_q) or {}).get("videos", [])[:3] if adapted_q else []

        for label, videos in (("RAW", raws), ("ADAPTED", adas)):
            draw2.text((10, y2), f"{label}  {query}" + (f"  →  {adapted_q}" if label == "ADAPTED" else ""), fill="black", font=font_sm)
            yy = y2 + label_h
            for col, v in enumerate(videos):
                x = 10 + col * (cell_w + 20)
                thumb = None
                img_url = v.get("image")
                tp = prev_dir / f"{query.replace(' ', '_')}__{label.lower()}__r{col}.jpg"
                if img_url and not tp.exists() and _download_media(img_url, tp):
                    thumb = _load_image(tp, (thumb_w, thumb_h))[0]
                elif tp.exists():
                    thumb = _load_image(tp, (thumb_w, thumb_h))[0]
                else:
                    thumb = Image.new("RGB", (thumb_w, thumb_h), "lightgray")
                sheet2.paste(thumb, (x, yy))
                orientation = "portrait" if v.get("width") and v.get("height") and v["width"] <= v["height"] else "landscape"
                meta = (
                    f"#{v.get('id')} rank{col+1}\n"
                    f"dur {v.get('duration')}s\n"
                    f"{v.get('width')}x{v.get('height')} {orientation}"
                )
                for li, line in enumerate(meta.splitlines()):
                    draw2.text((x, yy + thumb_h + 4 + li * 16), line, fill="black", font=font_xs)
            y2 = yy + thumb_h + 20

    dest = out_dir / "02-provider-fit-video-raw-vs-adapted-top3.png"
    sheet2.save(dest)
    return str(dest)


def _sheet03_video_temporal(out_dir: Path, review_results: list[dict]) -> str:
    from PIL import Image

    ImageDraw, font, font_sm, font_xs = _fonts()
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    frame_px = 270
    gap = 20
    label_h = 84
    sub_label_h = 40
    bottom_margin = 30

    rows_data: list[dict] = []
    for entry in review_results:
        query = entry["query"]
        raw = entry.get("rawRank1") or {}
        ada = entry.get("adaptedRank1") or {}
        if not raw.get("localPath") and not ada.get("localPath"):
            continue
        row_frames = {"raw": None, "adapted": None}
        for tag, info in (("raw", raw), ("adapted", ada)):
            clip = Path(info.get("localPath") or "")
            if not info or not clip.exists():
                continue
            ws_rel = f"/workspace/{clip.relative_to(ROOT)}"
            dur = _docker_probe_duration(ws_rel, ROOT) or info.get("videoDuration") or 0.0
            frame_paths: list[Path] = []
            for i, frac in enumerate((0.20, 0.50, 0.80)):
                fr = frames_dir / f"{clip.stem}__f{i}.png"
                _docker_extract_frame(ws_rel, dur * frac, f"/workspace/{fr.relative_to(ROOT)}", ROOT)
                if fr.exists():
                    frame_paths.append(fr)
            row_frames[tag] = {
                "clip": clip,
                "duration": info.get("videoDuration"),
                "resolution": info.get("selectedResolution") or info.get("videoOriginalResolution"),
                "videoId": info.get("pexelsVideoId"),
                "frames": frame_paths,
            }
        rows_data.append(
            {
                "query": query,
                "raw": row_frames["raw"],
                "adapted": row_frames["adapted"],
            }
        )

    def _scaled(fp: Path):
        if not fp.exists():
            return None
        im = Image.open(fp).convert("RGB")
        ratio = frame_px / im.width
        return im, frame_px, max(1, int(im.height * ratio))

    # Pre-compute per column the scaled frames and their column height so rows
    # never overlap and aspect ratios are preserved (no crop).
    cols_data: list[dict] = []
    for row in rows_data:
        row_cols = {}
        for tag in ("raw", "adapted"):
            info = row.get(tag)
            if not info:
                row_cols[tag] = None
                continue
            scaled = [_scaled(fp) for fp in info["frames"]]
            col_h = max((s[2] for s in scaled if s is not None), default=frame_px)
            row_cols[tag] = {"info": info, "scaled": scaled, "col_h": col_h}
        cols_data.append(row_cols)

    col_w = frame_px * 3 + gap * 2
    n_rows = len(rows_data)
    img_w = 20 + col_w * 2 + 30
    img_h = 16 + sum(
        label_h
        + sub_label_h
        + max(
            (cols.get("raw") or {}).get("col_h", 0),
            (cols.get("adapted") or {}).get("col_h", 0),
        )
        + bottom_margin
        for cols in cols_data
    ) + 16

    sheet = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(sheet)

    y = 16
    for row, cols in zip(rows_data, cols_data):
        raw_c, ada_c = cols.get("raw"), cols.get("adapted")
        raw_pid = raw_c["info"]["videoId"] if raw_c else "-"
        ada_pid = ada_c["info"]["videoId"] if ada_c else "-"
        _draw_wrap(
            draw,
            f"{row['query']}  |  RAW #{raw_pid} vs ADAPTED #{ada_pid}",
            16, y, img_w - 32, font_sm, "black",
        )
        row_h = (
            label_h
            + sub_label_h
            + max(
                (raw_c.get("col_h", 0) if raw_c else 0),
                (ada_c.get("col_h", 0) if ada_c else 0),
            )
            + bottom_margin
        )
        yy = y + label_h
        for x, tag, col in (
            (16, "RAW", raw_c),
            (16 + col_w + 30, "ADAPTED", ada_c),
        ):
            if col is None:
                _draw_wrap(draw, f"{tag}: no clip", x, yy + 10, col_w - 10, font_sm, "black")
                continue
            info = col["info"]
            _draw_wrap(
                draw,
                f"{tag}  dur {info['duration']}s  {info['resolution']}",
                x, yy + 2, col_w - 10, font_xs, "black",
            )
            fy = yy + sub_label_h
            for i, s in enumerate(col["scaled"]):
                fx = x + i * (frame_px + gap)
                if s is not None:
                    im, _w, h = s
                    sheet.paste(im, (fx, fy))
                else:
                    draw.rectangle([fx, fy, fx + frame_px, fy + frame_px], fill="lightgray")
        y += row_h

    dest = out_dir / "03-provider-fit-video-temporal.png"
    sheet.save(dest)
    return str(dest)


# ── Reporting helpers ───────────────────────────────────────────────────────


def _persist_metadata_report(out_dir: Path, rows: list[dict]) -> dict:
    from collections import Counter

    ap_dist = Counter(r.get("assetPreference") or "MISSING" for r in rows)
    intent_dist = Counter(r.get("visualIntent") or "MISSING" for r in rows)
    combo = Counter(
        (r.get("visualIntent") or "MISSING", r.get("assetPreference") or "MISSING")
        for r in rows
    )
    missing_rows = [
        {
            "jobId": r["jobId"],
            "sceneNumber": r["sceneNumber"],
            "segmentIndex": r["segmentIndex"],
            "missing": r["missing"],
        }
        for r in rows
        if r["missing"]
    ]
    mismatches = [
        {
            "jobId": r["jobId"],
            "sceneNumber": r["sceneNumber"],
            "segmentIndex": r["segmentIndex"],
            "queryUsed": r["queryUsed"],
            "persistedSearchQuery": r["persistedSearchQuery"],
            "assetPreference": r["assetPreference"],
        }
        for r in rows
        if r["searchQueryMismatch"]
    ]

    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schemaVersion": 1,
        "experiment": "pexels-provider-fit-benchmark-metadata",
        "rowsTotal": len(rows),
        "datasets": Counter(r["dataset"] for r in rows),
        "assetPreferenceDistribution": dict(sorted(ap_dist.items())),
        "visualIntentDistribution": dict(sorted(intent_dist.items())),
        "intentXAssetPreference": {
            f"{i} × {a}": c for (i, a), c in sorted(combo.items())
        },
        "queryFormDistribution": dict(
            sorted(Counter(r["queryForm"] for r in rows).items())
        ),
        "missingRows": missing_rows,
        "searchQueryMismatches": mismatches,
    }
    (out_dir / "metadata-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def _persist_policy_report(out_dir: Path, rows: list[dict]) -> dict:
    from collections import Counter

    verdicts = [row_fit_verdicts(r) for r in rows]
    photos = Counter(v["photos"] for v in verdicts)
    video = Counter(v["video"] for v in verdicts)
    by_form: dict[str, dict] = {}
    for r in rows:
        cat = effective_form(r)
        bucket = by_form.setdefault(cat, {"rows": 0, "photos": Counter(), "video": Counter()})
        bucket["rows"] += 1
        v = row_fit_verdicts(r)
        bucket["photos"][v["photos"]] += 1
        bucket["video"][v["video"]] += 1

    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schemaVersion": 1,
        "experiment": "pexels-provider-fit-benchmark-policy",
        "policyVersion": POLICY_VERSION,
        "rows": len(rows),
        "photosVerdictDistribution": dict(sorted(photos.items())),
        "videoVerdictDistribution": dict(sorted(video.items())),
        "byForm": {
            cat: {
                "rows": b["rows"],
                "photos": dict(sorted(b["photos"].items())),
                "video": dict(sorted(b["video"].items())),
            }
            for cat, b in sorted(by_form.items())
        },
    }
    (out_dir / "policy-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def _persist_adapt_report(out_dir: Path, rows: list[dict]) -> dict:
    plan = build_adapted_request_plan(rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schemaVersion": 1,
        "experiment": "pexels-provider-fit-benchmark-adapt",
        "policyVersion": ADAPT_POLICY_VERSION,
        "photographFormQueries": sorted(
            {r["queryUsed"] for r in rows if effective_form(r) == "photograph"}
        ),
        "plannedRequests": len(plan),
        "requestCap": ADAPTED_REQUEST_CAP,
        "plan": plan,
    }
    (out_dir / "adapt-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def _persist_review_sample(out_dir: Path) -> dict:
    rows = build_rows()
    sample = build_review_sample(
        sorted({r["queryUsed"] for r in rows if effective_form(r) == "photograph"}),
        query_topics_map(rows),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "schemaVersion": 1,
        "experiment": "pexels-provider-fit-benchmark-review-sample",
        "maxQueries": REVIEW_SAMPLE_MAX,
        "algorithm": (
            "1. mandatory queries fixed order; "
            "2. candidates = photograph-form queries not in sample sorted by (sorted topics, query); "
            "3. round-robin over topics adding one query per topic per round until 10 or pool empty."
        ),
        "mandatoryQueries": REVIEW_MANDATORY_QUERIES,
        "sample": sample,
        "count": len(sample),
    }
    (out_dir / "review-sample.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return record


# ── CLI ─────────────────────────────────────────────────────────────────────


def _fmt_metadata(r: dict) -> str:
    lines = [
        f"rowsTotal={r['rowsTotal']}",
        f"assetPreference={r['assetPreferenceDistribution']}",
        f"visualIntent={r['visualIntentDistribution']}",
        f"queryForm={r['queryFormDistribution']}",
        f"missingRows={len(r['missingRows'])}",
        f"searchQueryMismatches={len(r['searchQueryMismatches'])}",
    ]
    return "\n".join(lines)


def _fmt_policy(r: dict) -> str:
    lines = [
        f"rows={r['rows']}",
        f"Photos verdicts: {r['photosVerdictDistribution']}",
        f"Video verdicts: {r['videoVerdictDistribution']}",
    ]
    for cat, b in r["byForm"].items():
        lines.append(f"  byForm[{cat}] rows={b['rows']} photos={b['photos']} video={b['video']}")
    return "\n".join(lines)


def _fmt_adapt(r: dict) -> str:
    return (
        f"photographFormQueries={len(r['photographFormQueries'])} "
        f"plannedRequests={r['plannedRequests']}/{r['requestCap']}"
    )


def _fmt_compare(r: dict) -> str:
    lines = [f"comparisons={len(r['rawVsAdapted'])}"]
    for query, c in r["rawVsAdapted"].items():
        d = c["comparison"]
        lines.append(
            f"  {query!r}: rawTotal={d['raw_total_results']} adaTotal={d['adapted_total_results']} "
            f"overlap={c['ids']['overlapCount']}/15 top3overlap={c['ids']['overlapTop3']}"
        )
    return "\n".join(lines)


def _fmt_overlap(o: dict) -> str:
    out: list[str] = []
    for key, val in o["overlap"].items():
        out.append(
            f"{key}: queries={val['queries']} uniqueIds={val['uniqueIds']} "
            f"repeatedIds={val['repeatedIdCount']} pairsWithOverlap={val['queryPairsWithOverlap']}"
        )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pexels provider-fit benchmark (evaluation-only)")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("metadata", help="Resolve persisted rows + distributions (offline)")
    sub.add_parser("policy", help="Apply provisional provider-fit policy (offline)")
    sub.add_parser("adapt", help="Deterministic query adaptation plan (offline)")
    sub.add_parser("review-sample", help="Build deterministic review sample (offline)")
    sub.add_parser("run-adapted", help="Fire NEW adapted Pexels Video requests (cap 40)")
    sub.add_parser("compare", help="RAW vs ADAPTED comparison + overlap metrics (reuses persisted results)")
    sub.add_parser("review-clips", help="Download RAW+ADAPTED rank-#1 clips for the review sample")
    sub.add_parser("contact-sheets", help="Build the three human-review PNG contact sheets")
    args = parser.parse_args(argv)

    out_dir = EVAL_DIR
    if args.action == "metadata":
        report = _persist_metadata_report(out_dir, build_rows())
        print("### Pexels provider-fit · metadata")
        print(_fmt_metadata(report))
        print(f"\npersisted: {out_dir / 'metadata-report.json'}")
        return 0
    if args.action == "policy":
        report = _persist_policy_report(out_dir, build_rows())
        print("### Pexels provider-fit · policy")
        print(_fmt_policy(report))
        print(f"\npersisted: {out_dir / 'policy-report.json'}")
        return 0
    if args.action == "adapt":
        report = _persist_adapt_report(out_dir, build_rows())
        print("### Pexels provider-fit · query adaptation")
        print(_fmt_adapt(report))
        print(f"\npersisted: {out_dir / 'adapt-report.json'}")
        return 0
    if args.action == "review-sample":
        report = _persist_review_sample(out_dir)
        print("### Pexels provider-fit · review sample")
        print(f"count={report['count']} max={report['maxQueries']}")
        for s in report["sample"]:
            print(f"  {'[M]' if s['mandatory'] else '   '} {s['query']}  topics={s['topics']}")
        print(f"\npersisted: {out_dir / 'review-sample.json'}")
        return 0
    if args.action == "run-adapted":
        api_key = resolve_api_key()
        if not api_key:
            print("PEXELS_API_KEY_REQUIRED", file=sys.stderr)
            return 2
        record = run_adapted_video_requests(api_key, out_dir)
        last = record["rateLimits"][-1] if record["rateLimits"] else {}
        print("### Adapted video requests")
        print(
            f"planned={record['planned']} used={record['requestsUsed']}/{record['requestCap']} "
            f"lastRateLimit={last.get('rateLimit')}"
        )
        print(f"\npersisted: {out_dir / 'adapted-video-supply.json'}")
        return 0
    if args.action == "compare":
        record = compute_compare_record(out_dir)
        print("### RAW vs ADAPTED")
        print(_fmt_compare(record))
        print("### overlap (exact-ID)")
        print(_fmt_overlap(record))
        print(f"\npersisted: {out_dir / 'raw-vs-adapted.json'}")
        return 0
    if args.action == "review-clips":
        record = run_review_clips(out_dir)
        print("### Review clips")
        print(f"queries={record['queries']} downloaded={record['downloaded']} failures={record['failures']}")
        for r in record["results"]:
            rr = r["rawRank1"] or {}
            ar = r["adaptedRank1"] or {}
            print(
                f"  {r['query']}: raw=[{rr.get('status')} #{rr.get('pexelsVideoId','')}] "
                f"adapted=[{ar.get('status')} #{ar.get('pexelsVideoId','')}]"
            )
        print(f"\npersisted: {out_dir / 'review-clips.json'}")
        return 0
    if args.action == "contact-sheets":
        record = generate_contact_sheets(out_dir)
        print("### Contact sheets")
        print(f"photo:     {record['photoContactSheet']}")
        print(f"videoTop3: {record['videoTop3ContactSheet']}")
        print(f"temporal:  {record['temporalContactSheet']}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())