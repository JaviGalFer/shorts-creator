#!/usr/bin/env python3
"""Pexels Photos supply benchmark harness — evaluation-only.

Benchmark-first extension of the Pexels visual supply investigation. It measures
the RAW Pexels **Photos** search result against the same persisted ``queryUsed``
set used by the current Wikimedia/Pixabay stack.

  * It does NOT integrate Pexels Photos into production.
  * It does NOT touch rendering / OpenCLIP / BLIP / VLM / VisualPlan / datasets.
  * It does NOT re-label or modify the canonical / development fixtures.
  * It does NOT rewrite queries and does NOT apply ML/LLM reranking.

API used: `GET https://api.pexels.com/v1/search` with ``orientation=portrait``,
``locale=en-US``, ``per_page=15``, ``page=1``. The key is resolved with the
existing policy (process env first, then project `.env`), sent as an
``Authorization`` header with an explicit ``User-Agent``, and is never printed
or persisted.

This module is import-safe and offline: no network/ML on import. Real work only
happens through the explicit CLI actions (``run``, ``review-images``,
``contact-sheets``); pure parsing/selection/metrics/layout functions are
unit-testable without network.

Evidence is persisted under ``data/evaluations/pexels-visual-supply-benchmark/``
(git-ignored) alongside the video evidence from
``tools/pexels_video_supply_benchmark.py``.
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

from pexels_video_supply_benchmark import (  # noqa: E402
    CANONICAL_LABELS,
    DEVELOPMENT_LABELS,
    LOCALE,
    PAGE,
    PER_PAGE,
    REVIEW_12,
    classify_supply,
    dedup_queries,
    load_all_rows,
)

# ── API / experiment constants ───────────────────────────────────────────────

PHOTO_SEARCH_ENDPOINT = "https://api.pexels.com/v1/search"
ORIENTATION_PORTRAIT = "portrait"

# Max NEW API requests for Photos: 56 main + up to 14 diagnostic = 70.
PHOTO_MAX_MAIN_REQUESTS = 56
PHOTO_DIAGNOSTIC_BUDGET = 14
PHOTO_MAX_REQUESTS = PHOTO_MAX_MAIN_REQUESTS + PHOTO_DIAGNOSTIC_BUDGET

REVIEW_MAX_ORIGINALS = 12
# For rank #2/#3 previews use a large-but-not-original src variant.
RANK_23_SRC = "large2x"

# ── Dataset ─────────────────────────────────────────────────────────────────


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
    import json as _json

    def _load(path: Path) -> list[dict]:
        with open(path, "r", encoding="utf-8") as fh:
            data = _json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("labels"), list):
            return data["labels"]
        if isinstance(data, list):
            return data
        raise ValueError(f"{path}: unexpected label file structure")

    rows = [_row_from_entry(e, dataset="canonical") for e in _load(CANONICAL_LABELS)]
    rows += [_row_from_entry(e, dataset="development") for e in _load(DEVELOPMENT_LABELS)]
    return rows


# ── API key (no leak) / env ─────────────────────────────────────────────────


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


# ── Rate-limit header parsing ───────────────────────────────────────────────


def extract_rate_limit(headers: dict) -> dict:
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


# ── Photo payload parsing / normalization ────────────────────────────────────


def normalize_photo(photo: dict) -> dict:
    src = photo.get("src") or {}
    return {
        "id": photo.get("id"),
        "width": photo.get("width"),
        "height": photo.get("height"),
        "url": photo.get("url"),
        "photographer": photo.get("photographer"),
        "photographer_url": photo.get("photographer_url"),
        "photographer_id": photo.get("photographer_id"),
        "avg_color": photo.get("avg_color"),
        "alt": photo.get("alt"),
        "src": {
            "original": src.get("original"),
            "large2x": src.get("large2x"),
            "large": src.get("large"),
            "medium": src.get("medium"),
            "small": src.get("small"),
            "portrait": src.get("portrait"),
            "landscape": src.get("landscape"),
            "tiny": src.get("tiny"),
        },
    }


def parse_photo_search_response(payload: dict) -> dict:
    photos = [
        normalize_photo(p) for p in payload.get("photos", []) if isinstance(p, dict)
    ]
    return {
        "page": payload.get("page"),
        "per_page": payload.get("per_page"),
        "total_results": payload.get("total_results", 0),
        "url": payload.get("url"),
        "photos": photos,
    }


# ── Orientation / resolution helpers ────────────────────────────────────────


def is_portrait(photo: dict) -> bool:
    w = photo.get("width")
    h = photo.get("height")
    if not isinstance(w, int) or not isinstance(h, int):
        return False
    return w > 0 and h > 0 and w <= h


def original_at_least(photo: dict, min_width: int, min_height: int) -> bool:
    w = photo.get("width")
    h = photo.get("height")
    return (
        isinstance(w, int)
        and isinstance(h, int)
        and w >= min_width
        and h >= min_height
        and is_portrait(photo)
    )


# ── Supply metrics ──────────────────────────────────────────────────────────


def compute_supply_metrics(
    query_results: dict[str, dict],
    rows_by_query: dict[str, list[dict]],
) -> dict:
    queries = list(query_results.keys())

    def _total(q: str) -> int:
        return int(query_results[q].get("total_results", 0))

    def _photos(q: str) -> list[dict]:
        return query_results[q].get("photos", [])

    def _any_result(q: str) -> bool:
        return _total(q) > 0

    any_result = {q for q in queries if _any_result(q)}
    request_error = {q for q in queries if query_results[q].get("error")}
    zero_results = (set(queries) - any_result) | request_error

    all_photos: list[dict] = []
    for q in queries:
        all_photos.extend(_photos(q))

    per_query: dict[str, dict] = {}
    for q in queries:
        ps = _photos(q)
        per_query[q] = {
            "total_results": _total(q),
            "requestError": query_results[q].get("error"),
            "candidatesReturned": len(ps),
            "originalPortraitCount": sum(1 for p in ps if is_portrait(p)),
            "originalPortraitAtLeast720x1280": sum(
                1 for p in ps if original_at_least(p, 720, 1280)
            ),
            "originalPortraitAtLeast1080x1920": sum(
                1 for p in ps if original_at_least(p, 1080, 1920)
            ),
            "hasAtLeastOnePortraitCandidate": any(is_portrait(p) for p in ps),
            "hasAtLeastOne720x1280Candidate": any(
                original_at_least(p, 720, 1280) for p in ps
            ),
            "hasAtLeastOne1080x1920Candidate": any(
                original_at_least(p, 1080, 1920) for p in ps
            ),
        }

    n = len(queries)
    with720 = sum(1 for q in queries if per_query[q]["hasAtLeastOne720x1280Candidate"])
    with1080 = sum(1 for q in queries if per_query[q]["hasAtLeastOne1080x1920Candidate"])

    def _dataset_queries(dataset: str) -> set[str]:
        return {
            r["queryUsed"] for q, rows in rows_by_query.items() for r in rows
            if r["dataset"] == dataset
        }

    def _coverage(qs: set[str]) -> dict:
        if not qs:
            return {"queries": 0, "withAnyResult": 0, "fraction": None}
        with_any = sum(1 for q in qs if q in any_result)
        return {
            "queries": len(qs),
            "withAnyResult": with_any,
            "fraction": with_any / len(qs) if qs else None,
        }

    return {
        "queriesSearched": n,
        "queriesWithAnyResult": len(any_result),
        "queriesWithZeroResults": len(zero_results),
        "queriesWithRequestError": len(request_error),
        "medianTotalResults": statistics.median(_total(q) for q in queries) if n else None,
        "candidatesReturned": len(all_photos),
        "originalPortraitCount": sum(1 for p in all_photos if is_portrait(p)),
        "originalPortraitAtLeast720x1280": sum(
            1 for p in all_photos if original_at_least(p, 720, 1280)
        ),
        "originalPortraitAtLeast1080x1920": sum(
            1 for p in all_photos if original_at_least(p, 1080, 1920)
        ),
        "queriesWithAtLeastOne720x1280Candidate": with720,
        "queriesWithAtLeastOne1080x1920Candidate": with1080,
        "fractionQueriesWithAtLeastOne720x1280Candidate": (
            with720 / n if n else None
        ),
        "fractionQueriesWithAtLeastOne1080x1920Candidate": (
            with1080 / n if n else None
        ),
        "supplyClass_720x1280": classify_supply(with720 / n if n else None),
        "supplyClass_1080x1920": classify_supply(with1080 / n if n else None),
        "coverage_canonical": _coverage(_dataset_queries("canonical")),
        "coverage_development": _coverage(_dataset_queries("development")),
        "perQuery": per_query,
    }


# ── Diagnostic / request budget ─────────────────────────────────────────────


class RequestBudget:
    def __init__(self, cap: int):
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


def needs_diagnostic(query_result: dict) -> bool:
    if int(query_result.get("total_results", 0)) == 0:
        return True
    return not any(
        original_at_least(p, 720, 1280) for p in query_result.get("photos", [])
    )


def classify_search(query_result: dict, landscape_result: dict | None) -> str:
    if not needs_diagnostic(query_result):
        return "PORTRAIT_SUPPLY_OK"
    if landscape_result is None:
        return "NO_LANDSCAPE_REQUEST"
    if int(landscape_result.get("total_results", 0)) == 0:
        return "NO_CONTENT"
    return "CONTENT_EXISTS_BUT_NOT_PORTRAIT"


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


def _search_request(
    query: str,
    api_key: str,
    *,
    orientation: str | None,
    budget: RequestBudget,
) -> tuple[dict | None, dict, float | None]:
    if not budget.spend():
        return None, {}, None
    params = {"query": query, "page": PAGE, "per_page": PER_PAGE, "locale": LOCALE}
    if orientation:
        params["orientation"] = orientation
    url = f"{PHOTO_SEARCH_ENDPOINT}?{urlencode(params)}"
    try:
        payload, headers, latency = _http_get_json(url, api_key)
        return parse_photo_search_response(payload), extract_rate_limit(headers), latency
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}", "total_results": 0}, {}, None


def run_full_benchmark(api_key: str, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = load_all_rows()
    rows_by_query = dedup_queries(rows)
    main_budget = RequestBudget(PHOTO_MAX_MAIN_REQUESTS)

    query_results: dict[str, dict] = {}
    rate_limits: list[dict] = []
    for query in rows_by_query:
        if main_budget.exhausted:
            break
        result, rl, _lat = _search_request(
            query, api_key, orientation=ORIENTATION_PORTRAIT, budget=main_budget
        )
        rate_limits.append({"query": query, "rateLimit": rl})
        query_results[query] = result

    metrics = compute_supply_metrics(query_results, rows_by_query)

    # Diagnostics: only queries needing them, capped by the diagnostic budget.
    diag_budget = RequestBudget(PHOTO_DIAGNOSTIC_BUDGET)
    diagnostics: dict[str, str] = {}
    for query in query_results:
        if not needs_diagnostic(query_results[query]):
            diagnostics[query] = "PORTRAIT_SUPPLY_OK"
            continue
        if diag_budget.exhausted:
            diagnostics[query] = "NO_LANDSCAPE_REQUEST"
            continue
        landscape, _rl, _lat = _search_request(
            query, api_key, orientation=None, budget=diag_budget
        )
        diagnostics[query] = classify_search(query_results[query], landscape)

    diag_counts: dict[str, int] = defaultdict(int)
    for d in diagnostics.values():
        diag_counts[d] += 1

    record = {
        "schemaVersion": 1,
        "experiment": "pexels-photo-supply-benchmark",
        "queriesTotalLogical": len(rows),
        "queriesUnique": len(rows_by_query),
        "mainRequests": main_budget.used,
        "diagnosticRequests": diag_budget.used,
        "requestsUsed": main_budget.used + diag_budget.used,
        "requestCap": PHOTO_MAX_REQUESTS,
        "searchParams": {
            "endpoint": PHOTO_SEARCH_ENDPOINT,
            "per_page": PER_PAGE,
            "page": PAGE,
            "orientation": ORIENTATION_PORTRAIT,
            "locale": LOCALE,
        },
        "diagnostics": diagnostics,
        "classificationCounts": dict(diag_counts),
        "metrics": metrics,
        "rateLimits": rate_limits,
        "rawResults": query_results,
    }
    (out_dir / "photo-supply-benchmark.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return record


# ── Photo review images (reuse rawResults, no new searches) ─────────────────

PHOTO_EVAL_DIR = ROOT / "data" / "evaluations" / "pexels-visual-supply-benchmark"


def run_review_images(out_dir: Path, max_originals: int = REVIEW_MAX_ORIGINALS) -> dict:
    """Download rank #1 original (max 12) + rank #2/#3 large previews.

    Reuses the persisted ``photo-supply-benchmark.json`` rawResults, so no extra
    search requests are made. Rank #1 uses ``src.original``; ranks #2/#3 use
    ``src.large2x`` (fallback large) to avoid transferring originals.
    """
    import urllib.request  # lazy

    out_dir.mkdir(parents=True, exist_ok=True)
    img_dir = out_dir / "photos"
    img_dir.mkdir(parents=True, exist_ok=True)

    supply = json.loads((out_dir / "photo-supply-benchmark.json").read_text(encoding="utf-8"))
    raw = supply.get("rawResults", {})

    def _download(url: str, dest: Path) -> bool:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "shorts-creator-benchmark/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as fh:
                fh.write(resp.read())
            return True
        except Exception:  # noqa: BLE001
            return False

    results: list[dict] = []
    downloaded_orig = 0
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
        parsed = raw.get(query)
        if not parsed or parsed.get("error"):
            results.append({**entry, "status": "NO_RAW_RESULT", "error": (parsed or {}).get("error")})
            failures += 1
            continue
        photos = parsed.get("photos", [])
        if not photos:
            results.append({**entry, "status": "NO_PHOTOS"})
            failures += 1
            continue

        top3 = photos[:3]
        # rank #1 original
        r1 = top3[0]
        r1_src = (r1.get("src") or {}).get("original")
        dest1 = None
        if downloaded_orig < max_originals and r1_src:
            dest1 = img_dir / f"{query.replace(' ', '_')}__pid{r1['id']}__rank1.jpg"
            if not dest1.exists():
                if _download(r1_src, dest1):
                    downloaded_orig += 1
                else:
                    dest1 = None
            else:
                downloaded_orig += 1
        if dest1 is None and downloaded_orig < max_originals and r1_src:
            results.append({**entry, "status": "ORIGINAL_DOWNLOAD_FAILED", "pexelsId": r1["id"]})
            failures += 1
            continue
        if dest1 is None:
            results.append({**entry, "status": "ORIGINAL_SKIPPED_CAP", "pexelsId": r1["id"]})
            failures += 1
            continue

        # rank #2/#3 preview variants
        previews = []
        for idx, ph in enumerate(top3[1:3], start=2):
            src = (ph.get("src") or {})
            chosen = src.get(RANK_23_SRC) or src.get("large")
            if not chosen:
                previews.append({"rank": idx, "pexelsId": ph["id"], "url": None})
                continue
            tp = img_dir / f"{query.replace(' ', '_')}__pid{ph['id']}__rank{idx}.jpg"
            if not tp.exists():
                _download(chosen, tp)
            previews.append(
                {
                    "rank": idx,
                    "pexelsId": ph["id"],
                    "url": chosen,
                    "path": str(tp) if tp.exists() else None,
                }
            )

        results.append(
            {
                **entry,
                "status": "OK",
                "pexelsId": r1["id"],
                "originalResolution": f"{r1.get('width')}x{r1.get('height')}",
                "photographer": r1.get("photographer"),
                "url": r1.get("url"),
                "rank1OriginalPath": str(dest1),
                "previews": previews,
            }
        )

    record = {
        "schemaVersion": 1,
        "experiment": "pexels-visual-supply-benchmark-review-images",
        "queries": len(REVIEW_12),
        "originalsDownloaded": downloaded_orig,
        "failures": failures,
        "results": results,
    }
    (out_dir / "photo-review-images.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return record


# ── Contact sheet layout helper (pure, testable) ────────────────────────────


def compute_thumbnail_rect(
    img_size: tuple[int, int],
    target_w: int,
    target_h: int,
) -> tuple[int, int]:
    """Fit an image into a target box preserving aspect ratio (no crop).

    Returns the display ``(width, height)`` such that the image fits inside
    ``target_w x target_h`` while keeping aspect ratio and never exceeding the
    box. Deterministic and pure (testable offline).
    """
    w, h = img_size
    if w <= 0 or h <= 0:
        return (target_w, target_h)
    scale = min(target_w / w, target_h / h)
    return (max(1, int(w * scale)), max(1, int(h * scale)))


# ── 03 photo-vs-current contact sheet ───────────────────────────────────────


def generate_comparison_contact_sheet(out_dir: Path) -> dict:
    """Build 03-pexels-photo-vs-current-contact-sheet.png.

    For each of the 12 review queries a 4-column row:
      CURRENT (Wikimedia/Pixabay assetPath) | PEXELS #1 | #2 | #3
    with provider, Pexels ID, rank, original WxH and photographer. Aspect ratio
    preserved, no destructive crop, no overlap, complete image visible, legible
    labels. Pure-layout evidence for external human review (no semantic labels).
    """
    from PIL import Image, ImageDraw, ImageFont

    out_dir.mkdir(parents=True, exist_ok=True)
    supply = json.loads((out_dir / "photo-supply-benchmark.json").read_text(encoding="utf-8"))
    raw = supply.get("rawResults", {})
    review = json.loads((out_dir / "photo-review-images.json").read_text(encoding="utf-8"))
    review_by_query = {r["query"]: r for r in review.get("results", [])}

    # Current assetPath per review query from the dev fixture (unchanged).
    dev_rows = [r for r in load_all_rows() if r["dataset"] == "development"]
    current_by_query = {r["queryUsed"]: r for r in dev_rows}

    cell_w = 300
    cell_h = 420
    label_h = 84
    row_gap = 20
    col_gap = 14
    n_cols = 4

    img_w = 16 + n_cols * cell_w + (n_cols - 1) * col_gap + 16
    img_h = 16 + sum(label_h + row_gap + cell_h for _ in REVIEW_12) + 16

    sheet = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font_sm = ImageFont.truetype("DejaVuSans.ttf", 13)
        font_xs = ImageFont.truetype("DejaVuSans.ttf", 11)
    except Exception:  # noqa: BLE001
        font_sm = ImageFont.load_default()
        font_xs = font_sm

    def _place(path: str | None, box_x: int, box_y: int) -> None:
        thumb = None
        if path and Path(path).exists():
            thumb = Image.open(path).convert("RGB")
        if thumb is None:
            thumb = Image.new("RGB", (cell_w - 12, cell_h - 12), "lightgray")
            target_w, target_h = cell_w - 12, cell_h - 12
            dw, dh = target_w, target_h
        else:
            target_w, target_h = cell_w - 12, cell_h - 12
            dw, dh = compute_thumbnail_rect(thumb.size, target_w, target_h)
            thumb = thumb.resize((dw, dh), Image.LANCZOS)
        x = box_x + (cell_w - dw) // 2
        y = box_y + (cell_h - dh) // 2
        sheet.paste(thumb, (x, y))

    def _wrap(dr, text, x, y, max_w, fnt, fill, line_h=15):
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

    y = 16
    for spec in REVIEW_12:
        query = spec["queryUsed"]
        cur = current_by_query.get(query) or {}
        cur_path = cur.get("assetPath")
        rv = review_by_query.get(query) or {}
        top_photos = (raw.get(query) or {}).get("photos", [])[:3]

        _wrap(draw, f"{query}  |  {cur.get('jobId')} s{cur.get('sceneNumber')}.{cur.get('segmentIndex')}", 16, y, img_w - 32, font_sm, "black")
        yy = y + label_h

        col_x = [16 + i * (cell_w + col_gap) for i in range(n_cols)]

        # CURRENT
        _place(cur_path, col_x[0], yy)
        _wrap(draw, f"CURRENT\n{cur.get('provider','')}", col_x[0] + 4, yy + cell_h, cell_w - 8, font_xs, "black")

        # PEXELS #1/#2/#3
        for idx, ph in enumerate(top_photos[:3], start=1):
            c = col_x[idx]
            _place(rv.get("rank1OriginalPath") if idx == 1 else _rank_path(rv, idx), c, yy)
            meta = (
                f"PEXELS #{idx}  pid {ph.get('id')}\n"
                f"{ph.get('width')}x{ph.get('height')}\n"
                f"{ph.get('photographer','')}"
            )
            _wrap(draw, meta, c + 4, yy + cell_h, cell_w - 8, font_xs, "black")

        y = y + label_h + cell_h + row_gap

    sheet03 = out_dir / "03-pexels-photo-vs-current-contact-sheet.png"
    sheet.save(sheet03)
    return {"comparisonContactSheet": str(sheet03), "rows": len(REVIEW_12)}


def _rank_path(review_result: dict, rank: int) -> str | None:
    if rank == 1:
        return review_result.get("rank1OriginalPath")
    for p in review_result.get("previews", []):
        if p.get("rank") == rank:
            return p.get("path")
    return None


def _fmt_summary(record: dict) -> str:
    m = record["metrics"]
    last_rl = record.get("rateLimits", [])
    rl = last_rl[-1].get("rateLimit", {}) if last_rl else {}
    return (
        f"requestsUsed={record['requestsUsed']}/{record['requestCap']} "
        f"(main={record['mainRequests']} diag={record['diagnosticRequests']}) "
        f"rateLimit={rl}\n"
        f"queriesWithAnyResult={m['queriesWithAnyResult']}/{m['queriesSearched']} "
        f"zero={m['queriesWithZeroResults']}\n"
        f"fraction>=720x1280={m['fractionQueriesWithAtLeastOne720x1280Candidate']} "
        f"({m['supplyClass_720x1280']})\n"
        f"fraction>=1080x1920={m['fractionQueriesWithAtLeastOne1080x1920Candidate']} "
        f"({m['supplyClass_1080x1920']})\n"
        f"coverage_canonical={m['coverage_canonical']} "
        f"coverage_development={m['coverage_development']}\n"
        f"diagnostics={record['classificationCounts']}"
    )


# ── CLI ─────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pexels Photos supply benchmark (evaluation-only)")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("run", help="Run portrait Photo-supply benchmark + diagnostics")
    sub.add_parser("review-images", help="Download 12 rank#1 originals + rank 2/3 previews")
    sub.add_parser("contact-sheets", help="Build 03 photo-vs-current contact sheet")
    args = parser.parse_args(argv)

    out_dir = PHOTO_EVAL_DIR
    if args.action == "run":
        api_key = resolve_api_key()
        if not api_key:
            print("PEXELS_API_KEY_REQUIRED", file=sys.stderr)
            return 2
        record = run_full_benchmark(api_key, out_dir)
        print("### Pexels Photos supply benchmark")
        print(_fmt_summary(record))
        print(f"\npersisted: {out_dir / 'photo-supply-benchmark.json'}")
        return 0
    if args.action == "review-images":
        record = run_review_images(out_dir)
        print("### Review images")
        ok = [r for r in record["results"] if r["status"] == "OK"]
        print(f"queries={record['queries']} originalsDownloaded={record['originalsDownloaded']} failures={record['failures']}")
        for r in record["results"]:
            print(f"  [{r['status']}] {r['query']} -> pid {r.get('pexelsId','')} {r.get('originalResolution','')}")
        print(f"\npersisted: {out_dir / 'photo-review-images.json'}")
        return 0
    if args.action == "contact-sheets":
        record = generate_comparison_contact_sheet(out_dir)
        print("### Photo-vs-current contact sheet")
        print(f"rows={record['rows']}")
        print(f"sheet: {record['comparisonContactSheet']}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
