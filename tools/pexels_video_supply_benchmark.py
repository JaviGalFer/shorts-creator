#!/usr/bin/env python3
"""Pexels Video supply benchmark harness — evaluation-only.

Benchmark-first investigation: does the Pexels Video search API improve the
visual SUPPLY of the current Wikimedia/Pixabay stack?

  * It does NOT integrate Pexels into production.
  * It does NOT touch rendering / OpenCLIP / BLIP / VLM / VisualPlan / datasets.
  * It does NOT re-label or modify the canonical / development datasets.
  * It measures RAW Pexels results driven by the persisted ``queryUsed``.

Modules/providers:
  * tests/fixtures/asset_visual_fidelity/labels.json      → 38 canonical
  * tests/fixtures/asset_visual_fidelity/holdout_labels.json → 20 development

This module is import-safe and offline: importing it never performs network or
ML calls. Real work happens only through explicit CLI actions (``--run``,
``--diagnose``, ``--review-clips``). Pure parsing/selection/metrics functions
are unit-testable without any network access.

Data gets persisted under ``data/evaluations/pexels-video-supply-benchmark/``
(git-ignored). The Pexels API key is never printed or persisted.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
TOOLS = str(ROOT / "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

# ── API / experiment constants ───────────────────────────────────────────────

SEARCH_ENDPOINT = "https://api.pexels.com/v1/videos/search"
PER_PAGE = 15
PAGE = 1
ORIENTATION_PORTRAIT = "portrait"
LOCALE = "en-US"
MAX_REQUESTS = 100  # absolute hard cap for the whole experiment

SUPPLY_HIGH_FRACTION = 0.90
SUPPLY_MEDIUM_FRACTION = 0.70

REVIEW_MIN_RES_PREFERRED = (720, 1280)  # (width, height)
REVIEW_MIN_RES_FALLBACK = (540, 960)

EVAL_DIR = ROOT / "data" / "evaluations" / "pexels-video-supply-benchmark"

# ── Datasets ─────────────────────────────────────────────────────────────────

CANONICAL_LABELS = (
    ROOT / "tests" / "fixtures" / "asset_visual_fidelity" / "labels.json"
)
DEVELOPMENT_LABELS = (
    ROOT / "tests" / "fixtures" / "asset_visual_fidelity" / "holdout_labels.json"
)

# 12 focused review queries: 7 bad (FP/USABLE dev-20) + 4 good that BLIP
# false-rejected + 1 CLEARLY_RELEVANT control. role values are informational
# only; NO semantic judgment is produced by this harness.
REVIEW_12: list[dict] = [
    {
        "queryUsed": "four stroke engine automobile photograph",
        "jobId": "cmo-2026-08-18-210827",
        "sceneNumber": 1,
        "segmentIndex": 2,
        "role": "bad_dev",
    },
    {
        "queryUsed": "medieval castle construction photograph",
        "jobId": "cmo-2026-08-18-211151",
        "sceneNumber": 1,
        "segmentIndex": 1,
        "role": "bad_dev",
    },
    {
        "queryUsed": "medieval castle architectural plans illustration",
        "jobId": "cmo-2026-08-18-211151",
        "sceneNumber": 3,
        "segmentIndex": 1,
        "role": "bad_dev",
    },
    {
        "queryUsed": "completed medieval castle photograph",
        "jobId": "cmo-2026-08-18-211151",
        "sceneNumber": 4,
        "segmentIndex": 1,
        "role": "bad_dev",
    },
    {
        "queryUsed": "medieval castle construction time diagram",
        "jobId": "cmo-2026-08-18-211151",
        "sceneNumber": 4,
        "segmentIndex": 2,
        "role": "bad_dev",
    },
    {
        "queryUsed": "medieval castle historical significance photograph",
        "jobId": "cmo-2026-08-18-211151",
        "sceneNumber": 5,
        "segmentIndex": 1,
        "role": "bad_dev",
    },
    {
        "queryUsed": "data center infrastructure diagram",
        "jobId": "qu-2026-08-18-211511",
        "sceneNumber": 1,
        "segmentIndex": 2,
        "role": "bad_dev",
    },
    {
        "queryUsed": "medieval workers building castle illustration",
        "jobId": "cmo-2026-08-18-211151",
        "sceneNumber": 1,
        "segmentIndex": 2,
        "role": "good_bad_rejected_by_blip",
    },
    {
        "queryUsed": "application hosting architecture diagram",
        "jobId": "qu-2026-08-18-211511",
        "sceneNumber": 2,
        "segmentIndex": 2,
        "role": "good_bad_rejected_by_blip",
    },
    {
        "queryUsed": "data center security architecture diagram",
        "jobId": "qu-2026-08-18-211511",
        "sceneNumber": 4,
        "segmentIndex": 2,
        "role": "good_bad_rejected_by_blip",
    },
    {
        "queryUsed": "data center technology diagram",
        "jobId": "qu-2026-08-18-211511",
        "sceneNumber": 5,
        "segmentIndex": 2,
        "role": "good_bad_rejected_by_blip",
    },
    {
        "queryUsed": "four stroke engine parts photograph",
        "jobId": "cmo-2026-08-18-210827",
        "sceneNumber": 5,
        "segmentIndex": 2,
        "role": "clearly_relevant_control",
    },
]


# ── Dataset helpers ──────────────────────────────────────────────────────────


def load_label_file(path: Path) -> list[dict]:
    """Load a labels fixture file (either a JSON list or an object with labels)."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and isinstance(data.get("labels"), list):
        return data["labels"]
    if isinstance(data, list):
        return data
    raise ValueError(f"{path}: expected a JSON array or an object with a 'labels' array")


def _row_from_entry(entry: dict, *, dataset: str) -> dict:
    return {
        "queryUsed": entry["queryUsed"],
        "jobId": entry["jobId"],
        "sceneNumber": entry["sceneNumber"],
        "segmentIndex": entry["segmentIndex"],
        "topic": entry.get("topic"),
        "provider": entry.get("provider"),
        "humanLabel": entry.get("humanLabel"),
        "assetPath": entry.get("assetPath"),
        "dataset": dataset,
    }


def load_all_rows() -> list[dict]:
    """Build logical rows for canonical-38 + development-20 (58 rows)."""
    canonical = load_label_file(CANONICAL_LABELS)
    development = load_label_file(DEVELOPMENT_LABELS)
    rows = [_row_from_entry(e, dataset="canonical") for e in canonical]
    rows += [_row_from_entry(e, dataset="development") for e in development]
    return rows


def dedup_queries(rows: list[dict]) -> dict[str, list[dict]]:
    """Map each unique persisted ``queryUsed`` to its rows (job/scene/segment).

    Preserves full mapping (query → rows) while letting the caller fire one
    request per distinct query string. Order of insertion is preserved.
    """
    by_query: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        q = row["queryUsed"]
        by_query[q].append(row)
    return dict(by_query)


# ── Rate-limit header parsing ────────────────────────────────────────────────


def extract_rate_limit(headers: dict) -> dict:
    """Extract Pexels rate-limit metadata from a dict of HTTP headers.

    Keys are matched case-insensitively. Missing values become ``None``.
    """
    lowered = {str(k).lower(): v for k, v in headers.items()}
    result: dict = {}
    for key, out in (
        ("x-ratelimit-limit", "limit"),
        ("x-ratelimit-remaining", "remaining"),
        ("x-ratelimit-reset", "reset"),
    ):
        raw = lowered.get(key)
        try:
            result[out] = int(raw) if raw is not None and str(raw).strip() else None
        except (TypeError, ValueError):
            result[out] = None
    return result


# ── Pexels payload parsing / normalization ───────────────────────────────────


def _is_portrait(video_file: dict) -> bool:
    w = video_file.get("width")
    h = video_file.get("height")
    if not isinstance(w, int) or not isinstance(h, int):
        return False
    return w > 0 and h > 0 and w <= h


def _is_mp4(video_file: dict) -> bool:
    file_type = (video_file.get("file_type") or "").lower()
    return file_type == "video/mp4"


def normalize_video_file(vf: dict) -> dict:
    return {
        "id": vf.get("id"),
        "quality": vf.get("quality"),
        "file_type": vf.get("file_type"),
        "width": vf.get("width"),
        "height": vf.get("height"),
        "fps": vf.get("fps"),
        "link": vf.get("link"),
        "size": vf.get("size"),
    }


def normalize_video(video: dict) -> dict:
    """Normalize one Pexels video object into a compact record."""
    files = [
        normalize_video_file(vf)
        for vf in video.get("video_files", [])
        if isinstance(vf, dict)
    ]
    pictures = [
        {
            "id": p.get("id"),
            "picture": p.get("picture"),
            "nr": p.get("nr"),
        }
        for p in video.get("video_pictures", [])
        if isinstance(p, dict)
    ]
    user = video.get("user") or {}
    return {
        "id": video.get("id"),
        "width": video.get("width"),
        "height": video.get("height"),
        "url": video.get("url"),
        "image": video.get("image"),
        "duration": video.get("duration"),
        "user": {
            "id": user.get("id"),
            "name": user.get("name"),
            "url": user.get("url"),
        },
        "video_files": files,
        "video_pictures": pictures,
    }


def ndjson_safe(obj):
    """Convert an object into a JSON-serializable / hashable-safe form for dedup."""
    if isinstance(obj, dict):
        return {str(k): ndjson_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [ndjson_safe(v) for v in obj]
    return obj


def parse_video_search_response(payload: dict) -> dict:
    """Parse a raw Pexels /videos/search JSON payload into normalized records."""
    videos = [normalize_video(v) for v in payload.get("videos", []) if isinstance(v, dict)]
    return {
        "page": payload.get("page"),
        "per_page": payload.get("per_page"),
        "total_results": payload.get("total_results", 0),
        "url": payload.get("url"),
        "videos": videos,
    }


# ── Portrait MP4 selection ───────────────────────────────────────────────────


def candidate_portrait_mp4s(video: dict) -> list[dict]:
    """All playback MP4 files of a candidate that are portrait (width <= height)."""
    return [vf for vf in video.get("video_files", []) if _is_mp4(vf) and _is_portrait(vf)]


def has_portrait_mp4_at_least(video: dict, min_width: int, min_height: int) -> bool:
    return any(
        vf["width"] >= min_width and vf["height"] >= min_height
        for vf in candidate_portrait_mp4s(video)
    )


def select_review_mp4(video: dict) -> dict | None:
    """Select a portrait MP4 for human review, transfer-friendly.

    Preference order on portrait MP4 playback files:
      1. any variant meeting (>=720x1280); among those, the smallest ``size``
         (when present) to minimise transfer.
      2. else any variant meeting (>=540x960).
      3. else any portrait MP4.
    Returns the selected ``video_file`` dict or ``None``.

    This is a technical resolution/orientation choice — NOT a relevance judgment.
    """
    portrait = candidate_portrait_mp4s(video)
    if not portrait:
        return None

    def _score(vf: dict):
        # Within a resolution band, pick the cheapest transfer: smallest
        # height first, then smallest file size (when present).
        return (vf.get("height") or 0, vf.get("size") or 0)

    for min_w, min_h in (REVIEW_MIN_RES_PREFERRED, REVIEW_MIN_RES_FALLBACK):
        eligible = [
            vf for vf in portrait if vf["width"] >= min_w and vf["height"] >= min_h
        ]
        if eligible:
            return min(eligible, key=_score)
    return min(portrait, key=_score)


# ── API key resolution (no leak) ─────────────────────────────────────────────


def read_project_env() -> dict:
    """Read simple project .env values without returning them to any output."""
    values: dict = {}
    path = ROOT / ".env"
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_api_key() -> str | None:
    """Resolve the Pexels key: process env first, then project .env."""
    env = read_project_env()
    return os.environ.get("PEXELS_API_KEY") or env.get("PEXELS_API_KEY")


# ── Supply metrics ───────────────────────────────────────────────────────────


def classify_supply(fraction: float | None) -> str:
    """Technical availability classification (NOT semantic relevance)."""
    if fraction is None:
        return "NO_DATA"
    if fraction >= SUPPLY_HIGH_FRACTION:
        return "HIGH_SUPPLY"
    if fraction >= SUPPLY_MEDIUM_FRACTION:
        return "MEDIUM_SUPPLY"
    return "LOW_SUPPLY"


def duration_distribution(videos: list[dict]) -> dict:
    """Summary of candidate durations across a set of normalized videos."""
    durations = [v["duration"] for v in videos if isinstance(v.get("duration"), (int, float))]
    if not durations:
        return {"count": 0, "min": None, "median": None, "mean": None, "max": None}
    return {
        "count": len(durations),
        "min": min(durations),
        "median": statistics.median(durations),
        "mean": statistics.mean(durations),
        "max": max(durations),
    }


def compute_supply_metrics(
    query_results: dict[str, dict],
    rows_by_query: dict[str, list[dict]],
) -> dict:
    """Compute aggregate supply metrics over one request result per query.

    ``query_results`` maps queryUsed -> parsed search response (see
    ``parse_video_search_response``). ``rows_by_query`` is from
    ``dedup_queries``.
    """
    queries = list(query_results.keys())

    def _total(q: str) -> int:
        return int(query_results[q].get("total_results", 0))

    def _videos(q: str) -> list[dict]:
        return query_results[q].get("videos", [])

    def _any_result(q: str) -> bool:
        return _total(q) > 0

    any_result = {q for q in queries if _any_result(q)}
    request_error = {
        q for q in queries if "error" in query_results[q] and query_results[q].get("error")
    }
    zero_results = (set(queries) - any_result) | request_error

    all_videos: list[dict] = []
    for q in queries:
        all_videos.extend(_videos(q))

    per_query = {}
    for q in queries:
        vs = _videos(q)
        per_query[q] = {
            "total_results": _total(q),
            "requestError": query_results[q].get("error"),
            "candidates": len(vs),
            "portraitMp4": sum(1 for v in vs if candidate_portrait_mp4s(v)),
            "portraitMp4AtLeast540x960": sum(
                1 for v in vs if has_portrait_mp4_at_least(v, 540, 960)
            ),
            "portraitMp4AtLeast720x1280": sum(
                1 for v in vs if has_portrait_mp4_at_least(v, 720, 1280)
            ),
            "portraitMp4AtLeast1080x1920": sum(
                1 for v in vs if has_portrait_mp4_at_least(v, 1080, 1920)
            ),
            "hasAtLeastOne720x1280Candidate": any(
                has_portrait_mp4_at_least(v, 720, 1280) for v in vs
            ),
            "hasAtLeastOne1080x1920Candidate": any(
                has_portrait_mp4_at_least(v, 1080, 1920) for v in vs
            ),
        }

    with720 = sum(
        1 for q in queries if per_query[q]["hasAtLeastOne720x1280Candidate"]
    )
    with1080 = sum(
        1 for q in queries if per_query[q]["hasAtLeastOne1080x1920Candidate"]
    )

    n = len(queries)
    frac720 = with720 / n if n else None
    frac1080 = with1080 / n if n else None

    # Coverage split by dataset (canonical vs development) at the row level.
    def _dataset_queries(dataset: str) -> set[str]:
        return {
            r["queryUsed"]
            for q, rows in rows_by_query.items()
            for r in rows
            if r["dataset"] == dataset
        }

    def _coverage(qs: set[str]) -> dict:
        if not qs:
            return {"queries": 0, "withAnyResult": 0, "fraction": None}
        with_any = sum(1 for q in qs if q in any_result)
        return {
            "queries": len(qs),
            "withAnyResult": with_any,
            "fraction": with_any / len(qs),
        }

    canonical_qs = _dataset_queries("canonical")
    development_qs = _dataset_queries("development")

    return {
        "queriesSearched": n,
        "queriesWithAnyResult": len(any_result),
        "queriesWithZeroResults": len(zero_results),
        "queriesWithRequestError": len(request_error),
        "medianTotalResults": statistics.median(
            _total(q) for q in queries
        )
        if n
        else None,
        "candidatesReturned": len(all_videos),
        "portraitMp4Count": sum(
            1 for v in all_videos if candidate_portrait_mp4s(v)
        ),
        "portraitMp4AtLeast540x960": sum(
            1 for v in all_videos if has_portrait_mp4_at_least(v, 540, 960)
        ),
        "portraitMp4AtLeast720x1280": sum(
            1 for v in all_videos if has_portrait_mp4_at_least(v, 720, 1280)
        ),
        "portraitMp4AtLeast1080x1920": sum(
            1 for v in all_videos if has_portrait_mp4_at_least(v, 1080, 1920)
        ),
        "durationDistribution": duration_distribution(all_videos),
        "queriesWithAtLeastOne720x1280Candidate": with720,
        "queriesWithAtLeastOne1080x1920Candidate": with1080,
        "fractionQueriesWithAtLeastOne720x1280Candidate": frac720,
        "fractionQueriesWithAtLeastOne1080x1920Candidate": frac1080,
        "supplyClass_720x1280": classify_supply(frac720),
        "supplyClass_1080x1920": classify_supply(frac1080),
        "coverage_canonical": _coverage(canonical_qs),
        "coverage_development": _coverage(development_qs),
        "perQuery": per_query,
    }


# ── Request budget / landscape diagnostic ────────────────────────────────────


class RequestBudget:
    """Hard-cap traffic counter for the whole experiment (MAX_REQUESTS)."""

    def __init__(self, cap: int = MAX_REQUESTS):
        self.cap = cap
        self.used = 0

    @property
    def exhausted(self) -> bool:
        return self.used >= self.cap

    def spend(self) -> bool:
        if self.exhausted:
            return False
        self.used += 1
        return True


def needs_landscape_diagnostic(query_result: dict) -> bool:
    """True when a portrait request shows no usable portrait supply.

    Diagnostic trigger: zero portrait results OR no candidate with a portrait
    MP4 >= 720x1280. The landscape request then distinguishes NO_CONTENT from
    CONTENT_EXISTS_BUT_NOT_PORTRAIT.
    """
    if int(query_result["total_results"]) == 0:
        return True
    return not any(
        has_portrait_mp4_at_least(v, 720, 1280) for v in query_result["videos"]
    )


def classify_portrait_search(query_result: dict, landscape_result: dict | None) -> str:
    """Technical diagnostic outcome for a portrait query.

    * NO_CONTENT: even the unrestricted (no-orientation) search returns 0
      results → no content for this concept on Pexels.
    * CONTENT_EXISTS_BUT_NOT_PORTRAIT: portrait had 0 results / no >=720x1280
      portrait, but the unrestricted search found results.
    * PORTRAIT_SUPPLY_OK: the portrait request already had a >=720x1280
      candidate (no diagnostic request issued).
    * NO_LANDSCAPE_REQUEST: diagnostic was needed but was not run (budget).
    """
    if needs_landscape_diagnostic(query_result):
        if landscape_result is None:
            return "NO_LANDSCAPE_REQUEST"
        if int(landscape_result["total_results"]) == 0:
            return "NO_CONTENT"
        return "CONTENT_EXISTS_BUT_NOT_PORTRAIT"
    return "PORTRAIT_SUPPLY_OK"


# ── Real HTTP run (lazy urllib) ──────────────────────────────────────────────


def _http_get_json(url: str, api_key: str) -> tuple[dict, dict, float]:
    import urllib.request  # lazy: only when actually making network calls

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


def _search_request(
    query: str, api_key: str, *, orientation: str | None = None, budget: RequestBudget
) -> tuple[dict | None, dict, float | None]:
    """Issue a single Pexels search request within ``budget``.

    Returns (parsed_result_or_None, rate_limit_dict, latency_or_None).
    ``parsed_result_or_None`` is ``None`` when the budget is exhausted before
    the call or the request failed (never raises for the caller).
    """
    if not budget.spend():
        return None, {}, None
    params = {
        "query": query,
        "page": PAGE,
        "per_page": PER_PAGE,
        "locale": LOCALE,
    }
    if orientation:
        params["orientation"] = orientation
    url = f"{SEARCH_ENDPOINT}?{urlencode(params)}"
    try:
        payload, headers, latency = _http_get_json(url, api_key)
        return parse_video_search_response(payload), extract_rate_limit(headers), latency
    except Exception as exc:  # noqa: BLE001 — evaluation-only, record and continue
        # Evaluation-only; errors are individual and do not abort the run.
        return {"error": f"{type(exc).__name__}: {exc}", "total_results": 0}, {}, None


def run_full_benchmark(api_key: str, out_dir: Path) -> dict:
    """Run the portrait-supply benchmark over all deduplicated queries."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = load_all_rows()
    rows_by_query = dedup_queries(rows)
    budget = RequestBudget()

    query_results: dict[str, dict] = {}
    rate_limits: list[dict] = []
    for query in rows_by_query:
        if budget.exhausted:
            break
        result, rl, _lat = _search_request(query, api_key, orientation=ORIENTATION_PORTRAIT, budget=budget)
        rate_limits.append({"query": query, "rateLimit": rl})
        query_results[query] = result

    metrics = compute_supply_metrics(query_results, rows_by_query)

    record = {
        "schemaVersion": 1,
        "experiment": "pexels-video-supply-benchmark",
        "queriesTotalLogical": len(rows),
        "queriesUnique": len(rows_by_query),
        "requestsUsed": budget.used,
        "requestCap": MAX_REQUESTS,
        "searchParams": {
            "endpoint": SEARCH_ENDPOINT,
            "per_page": PER_PAGE,
            "page": PAGE,
            "orientation": ORIENTATION_PORTRAIT,
            "locale": LOCALE,
        },
        "metrics": metrics,
        "rateLimits": rate_limits,
        "rawResults": query_results,  # full normalized per-query results (reusable)
    }
    (out_dir / "supply-benchmark.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return record


def run_landscape_diagnostic(api_key: str, out_dir: Path) -> dict:
    """Issue landscape (no-orientation) diagnostic requests for failing queries."""
    out_dir.mkdir(parents=True, exist_ok=True)
    supply_path = out_dir / "supply-benchmark.json"
    if not supply_path.exists():
        raise FileNotFoundError(
            "run --run first: supply-benchmark.json not found; the diagnostic "
            "reuses the persisted portrait results"
        )
    prior = json.loads(supply_path.read_text(encoding="utf-8"))
    rows_by_query = dedup_queries(load_all_rows())
    queries = list(prior["metrics"]["perQuery"].keys())

    budget = RequestBudget(
        cap=MAX_REQUESTS - int(prior.get("requestsUsed", 0))
    )

    diagnostics: dict[str, dict] = {}
    for query in queries:
        portrait = prior["metrics"]["perQuery"][query]
        portraits_ok = bool(portrait["hasAtLeastOne720x1280Candidate"])
        needs = portrait["total_results"] == 0 or not portraits_ok

        landscape_result = None
        if needs and not budget.exhausted:
            landscape_result, _rl, _lat = _search_request(
                query, api_key, orientation=None, budget=budget
            )

        classification: str
        if not needs:
            classification = "PORTRAIT_SUPPLY_OK"
        elif landscape_result is None:
            classification = "NO_LANDSCAPE_REQUEST"
        elif int(landscape_result["total_results"]) == 0:
            classification = "NO_CONTENT"
        else:
            classification = "CONTENT_EXISTS_BUT_NOT_PORTRAIT"

        diagnostics[query] = {
            "portrait_total_results": portrait["total_results"],
            "portrait_has720x1280": portraits_ok,
            "landscape_total_results": (
                landscape_result["total_results"] if landscape_result else None
            ),
            "classification": classification,
        }

    counts: dict[str, int] = defaultdict(int)
    for d in diagnostics.values():
        counts[d["classification"]] += 1

    record = {
        "schemaVersion": 1,
        "experiment": "pexels-video-supply-benchmark-landscape-diagnostic",
        "requestsUsed": budget.used,
        "diagnostics": diagnostics,
        "classificationCounts": dict(counts),
    }
    (out_dir / "landscape-diagnostic.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return record


def run_review_clips(out_dir: Path, max_clips: int = 12) -> dict:
    """Download the rank-#1 portrait MP4 for the 12 focused review queries.

    Uses RAW rank #1 (no ML reranking), read from the persisted
    ``supply-benchmark.json`` (no new search requests). Selects a portrait MP4
    via ``select_review_mp4`` (prefer >=720x1280, fallback 540x960, no HLS).
    Evaluation-only; max 12 downloads; failures recorded explicitly.
    """
    import urllib.request  # lazy

    out_dir.mkdir(parents=True, exist_ok=True)
    clips_dir = out_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    supply_path = out_dir / "supply-benchmark.json"
    if not supply_path.exists():
        raise FileNotFoundError(
            "run --run first: supply-benchmark.json not found; review clips "
            "reuse the persisted rank-#1 raw results (no extra search requests)"
        )
    prior = json.loads(supply_path.read_text(encoding="utf-8"))
    raw = prior.get("rawResults", {})

    results: list[dict] = []
    downloaded = 0
    failures = 0

    for spec in REVIEW_12:
        query = spec["queryUsed"]
        entry = {
            "query": query,
            "jobId": spec["jobId"],
            "sceneNumber": spec["sceneNumber"],
            "segmentIndex": spec["segmentIndex"],
            "role": spec["role"],
        }
        if downloaded >= max_clips:
            results.append({**entry, "status": "SKIPPED_CAP"})
            continue

        parsed = raw.get(query)
        if not parsed or parsed.get("error"):
            results.append(
                {**entry, "status": "NO_RAW_RESULT", "error": (parsed or {}).get("error")}
            )
            failures += 1
            continue
        videos = parsed.get("videos", [])
        if not videos:
            results.append({**entry, "status": "NO_VIDEOS"})
            failures += 1
            continue

        top = videos[0]
        vf = select_review_mp4(top)
        if vf is None or not vf.get("link"):
            results.append(
                {
                    **entry,
                    "status": "NO_PORTRAIT_MP4",
                    "pexelsVideoId": top["id"],
                }
            )
            failures += 1
            continue

        dest = clips_dir / f"{query.replace(' ', '_')}__vid{top['id']}.mp4"
        if dest.exists():
            downloaded += 1
            results.append(
                {
                    **entry,
                    "status": "OK_CACHED",
                    "pexelsVideoId": top["id"],
                    "selectedResolution": f"{vf['width']}x{vf['height']}",
                    "localPath": str(dest),
                }
            )
            continue

        try:
            req = urllib.request.Request(vf["link"], headers={"User-Agent": "shorts-creator-benchmark/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as fh:
                fh.write(resp.read())
        except Exception as exc:  # noqa: BLE001
            results.append(
                {**entry, "status": "DOWNLOAD_FAILED", "pexelsVideoId": top["id"], "error": str(exc)}
            )
            failures += 1
            continue

        downloaded += 1
        results.append(
            {
                **entry,
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
        )

    record = {
        "schemaVersion": 1,
        "experiment": "pexels-video-supply-benchmark-review-clips",
        "clipsRequested": len(REVIEW_12),
        "downloaded": downloaded,
        "failures": failures,
        "results": results,
    }
    (out_dir / "review-clips.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return record


# ── Contact sheets (Docker ffmpeg/ffprobe; PIL assembly) ────────────────────


def _docker_cmd(
    project_root: Path, args: list[str], timeout: int = 180, *, entrypoint: str | None = None
) -> subprocess.CompletedProcess:
    import subprocess  # lazy import, only used off-network

    env = dict(os.environ)
    env.pop("DOCKER_API_VERSION", None)
    docker_args = ["docker", "run", "--rm", "-v", f"{project_root}:/workspace"]
    if entrypoint:
        docker_args += ["--entrypoint", entrypoint]
    cmd = docker_args + ["linuxserver/ffmpeg:latest"] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)


def _docker_probe_duration(ws_rel: str, project_root: Path) -> float | None:
    import json as _json

    # The image's default entrypoint is ffmpeg; ffprobe must be selected via
    # --entrypoint (same pattern as src/shorts_creator/validation/job.py).
    res = _docker_cmd(
        project_root,
        ["-v", "quiet", "-print_format", "json", "-show_format", ws_rel],
        timeout=120,
        entrypoint="ffprobe",
    )
    if res.returncode != 0:
        return None
    try:
        data = _json.loads(res.stdout)
        return float(data["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        return None


def _docker_extract_frame(
    ws_rel: str,
    timestamp: float,
    output_ws_rel: str,
    project_root: Path,
    timeout: int = 180,
) -> bool:
    # Default entrypoint is ffmpeg; do NOT prefix the binary name.
    res = _docker_cmd(
        project_root,
        ["-y", "-ss", f"{timestamp:.3f}", "-i", ws_rel, "-frames:v", "1", "-q:v", "2", output_ws_rel],
        timeout=timeout,
    )
    return res.returncode == 0


def generate_contact_sheets(out_dir: Path) -> dict:
    """Build the two human-review PNGs using Docker ffmpeg/ffprobe + PIL.

    01-pexels-video-temporal-contact-sheet.png: for each of the 12 downloaded
    clips, one row labelled with query / job.scene.segment / Pexels video ID /
    rank(1) / duration / resolution and three frames at 20/50/80 % of duration.

    02-pexels-top3-search-results.png: for the same 12 queries, the previews
    (Pexels ``image`` thumbnails) of RAW rank 1, 2 and 3 candidates with query,
    ID, duration and resolution/orientation.

    Both are technical evidence for external human review; NO semantic judgment
    is applied here.
    """
    from PIL import Image, ImageDraw, ImageFont

    import urllib.request as _ur

    out_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = out_dir / "frames"
    prev_dir = out_dir / "previews"
    frames_dir.mkdir(exist_ok=True)
    prev_dir.mkdir(exist_ok=True)

    review = json.loads((out_dir / "review-clips.json").read_text(encoding="utf-8"))
    supply = json.loads((out_dir / "supply-benchmark.json").read_text(encoding="utf-8"))
    raw = supply.get("rawResults", {})

    def _download(url: str, dest: Path) -> bool:
        try:
            req = _ur.Request(url, headers={"User-Agent": "shorts-creator-benchmark/1.0"})
            with _ur.urlopen(req, timeout=60) as resp, open(dest, "wb") as fh:
                fh.write(resp.read())
            return True
        except Exception:  # noqa: BLE001
            return False

    # ── 01 temporal contact sheet ───────────────────────────────────────────
    frame_px = 270  # each review frame displayed at 270 wide
    label_h = 74
    rows_data: list[dict] = []
    for r in review["results"]:
        if r["status"] not in ("OK", "OK_CACHED") or "localPath" not in r:
            continue
        clip = Path(r["localPath"])
        if not clip.exists():
            continue
        ws_rel = f"/workspace/{clip.relative_to(ROOT)}"
        dur = _docker_probe_duration(ws_rel, ROOT)
        if dur is None:
            dur = r.get("videoDuration") or 0.0
        timestamps = [dur * p for p in (0.20, 0.50, 0.80)]
        frame_paths: list[Path] = []
        for i, ts in enumerate(timestamps):
            fr = frames_dir / f"{clip.stem}__f{i}.png"
            _docker_extract_frame(ws_rel, ts, f"/workspace/{fr.relative_to(ROOT)}", ROOT)
            if fr.exists():
                frame_paths.append(fr)
        rows_data.append(
            {
                "query": r["query"],
                "jobScene": f"{r['jobId']} s{r['sceneNumber']}.{r['segmentIndex']}",
                "videoId": r.get("pexelsVideoId"),
                "rank": 1,
                "duration": r.get("videoDuration"),
                "resolution": r.get("selectedResolution") or r.get("videoOriginalResolution"),
                "frames": frame_paths,
                "role": r.get("role", ""),
            }
        )

    img_w = frame_px * 3 + 60
    img_h = 30 + sum(label_h + 10 + frame_px for _ in rows_data) + 20
    sheet = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 16)
        font_sm = ImageFont.truetype("DejaVuSans.ttf", 13)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()
        font_sm = font

    y = 10
    for row in rows_data:
        label = (
            f"{row['query']}  |  {row['jobScene']}  |  #{row['videoId']}  "
            f"rank {row['rank']}  dur {row['duration']}s  {row['resolution']}"
        )
        draw.text((10, y), label, fill="black", font=font_sm)
        yy = y + label_h
        for idx, fp in enumerate(row["frames"]):
            if fp.exists():
                im = Image.open(fp).convert("RGB")
                ratio = frame_px / im.width
                im = im.resize((frame_px, int(im.height * ratio)), Image.LANCZOS)
            else:
                im = Image.new("RGB", (frame_px, frame_px), "lightgray")
            sheet.paste(im, (10 + idx * (frame_px + 20), yy))
        y = yy + frame_px + 10

    sheet01 = out_dir / "01-pexels-video-temporal-contact-sheet.png"
    sheet.save(sheet01)

    # ── 02 top-3 search results ─────────────────────────────────────────────
    cell_w, cell_h = 200, 360
    thumb_w, thumb_h = 180, 240
    n_queries = len(rows_data)
    img_w2 = cell_w * 3 + 60
    img_h2 = 30 + sum(70 + thumb_h for _ in rows_data) + 20
    sheet2 = Image.new("RGB", (img_w2, img_h2), "white")
    draw2 = ImageDraw.Draw(sheet2)

    y2 = 10
    for row in rows_data:
        draw2.text((10, y2), f"{row['query']}  ({row['jobScene']})", fill="black", font=font_sm)
        yy = y2 + 70
        videos = (raw.get(row["query"]) or {}).get("videos", [])[:3]
        for col, v in enumerate(videos):
            x = 10 + col * (cell_w + 20)
            thumb = None
            img_url = v.get("image")
            if img_url:
                tp = prev_dir / f"{row['videoId'] or row['query'].replace(' ', '_')}__r{col}.jpg"
                if _download(img_url, tp):
                    thumb = Image.open(tp).convert("RGB")
            if thumb is not None:
                ratio = thumb_w / thumb.width
                thumb = thumb.resize((thumb_w, min(int(thumb.height * ratio), thumb_h)), Image.LANCZOS)
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
                draw2.text((x, yy + thumb_h + 4 + li * 16), line, fill="black", font=font_sm)
        y2 = yy + 70 + thumb_h

    sheet02 = out_dir / "02-pexels-top3-search-results.png"
    sheet2.save(sheet02)

    return {
        "schemaVersion": 1,
        "temporalContactSheet": str(sheet01),
        "top3ContactSheet": str(sheet02),
        "rows": len(rows_data),
    }


# ── CLI ──────────────────────────────────────────────────────────────────────


def _fmt_summary(record: dict) -> str:
    m = record["metrics"]
    lines = [
        f"requestsUsed={record['requestsUsed']}/{record['requestCap']}",
        f"queriesUnique={record['queriesUnique']} logicalRows={record['queriesTotalLogical']}",
        f"queriesWithAnyResult={m['queriesWithAnyResult']} zero={m['queriesWithZeroResults']}",
        f"fraction>=720x1280={m['fractionQueriesWithAtLeastOne720x1280Candidate']} "
        f"({m['supplyClass_720x1280']})",
        f"fraction>=1080x1920={m['fractionQueriesWithAtLeastOne1080x1920Candidate']} "
        f"({m['supplyClass_1080x1920']})",
        f"coverage canonical={m['coverage_canonical']}",
        f"coverage development={m['coverage_development']}",
    ]
    last = record.get("rateLimits", [])
    if last:
        rl = last[-1].get("rateLimit", {})
        lines.append(f"lastRateLimit={rl}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pexels video supply benchmark (evaluation-only)")
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("run", help="Run portrait-supply benchmark over deduplicated queries")
    sub.add_parser("diagnose", help="Landscape (no-orientation) diagnostic for failing queries")
    sub.add_parser("review-clips", help="Download 12 focused rank-#1 review clips")
    sub.add_parser("contact-sheets", help="Build the two human-review PNG contact sheets")

    args = parser.parse_args(argv)

    out_dir = EVAL_DIR
    if args.action == "run":
        api_key = resolve_api_key()
        if not api_key:
            print("PEXELS_API_KEY_REQUIRED", file=sys.stderr)
            return 2
        record = run_full_benchmark(api_key, out_dir)
        print("### Pexels supply benchmark")
        print(_fmt_summary(record))
        print(f"\npersisted: {out_dir / 'supply-benchmark.json'}")
        return 0
    if args.action == "diagnose":
        # diagnostic run needs an API key too
        api_key = resolve_api_key()
        if not api_key:
            print("PEXELS_API_KEY_REQUIRED", file=sys.stderr)
            return 2
        record = run_landscape_diagnostic(api_key, out_dir)
        print("### Landscape diagnostic")
        print(json.dumps(record.get("classificationCounts", {}), indent=2))
        print(f"\npersisted: {out_dir / 'landscape-diagnostic.json'}")
        return 0
    if args.action == "review-clips":
        record = run_review_clips(out_dir)
        print("### Review clips")
        ok = [r for r in record["results"] if r["status"] == "OK"]
        print(f"requested={record['clipsRequested']} downloaded={record['downloaded']} failures={record['failures']}")
        for r in record["results"]:
            status = r["status"]
            print(f"  [{status}] {r['query']} -> {r.get('pexelsVideoId','')} {r.get('selectedResolution','')}")
        print(f"\npersisted: {out_dir / 'review-clips.json'}")
        return 0
    if args.action == "contact-sheets":
        record = generate_contact_sheets(out_dir)
        print("### Contact sheets")
        print(f"rows={record['rows']}")
        print(f"temporal: {record['temporalContactSheet']}")
        print(f"top3:     {record['top3ContactSheet']}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
