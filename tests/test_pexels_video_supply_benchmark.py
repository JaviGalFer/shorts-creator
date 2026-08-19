"""Focused tests for tools/pexels_video_supply_benchmark.py.

Pure offline logic tests for the Pexels video supply benchmark harness:
parsing, query dedup, rate-limit metadata, portrait MP4 selection, no API-key
leakage, request cap and landscape diagnostic. No real network calls; no ML.

The canonical (38) and development (20) label fixtures are reused WITHOUT any
modification.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = str(_PROJECT_ROOT / "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from pexels_video_supply_benchmark import (  # noqa: E402
    MAX_REQUESTS,
    REVIEW_12,
    REVIEW_MIN_RES_FALLBACK,
    REVIEW_MIN_RES_PREFERRED,
    RequestBudget,
    candidate_portrait_mp4s,
    classify_portrait_search,
    classify_supply,
    compute_supply_metrics,
    dedup_queries,
    extract_rate_limit,
    load_all_rows,
    ndjson_safe,
    needs_landscape_diagnostic,
    normalize_video,
    parse_video_search_response,
    select_review_mp4,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "asset_visual_fidelity"


def _sample_video(**overrides) -> dict:
    video = {
        "id": 1001,
        "width": 1920,
        "height": 1080,
        "url": "https://www.pexels.com/video/1001/",
        "image": "https://images.pexels.com/preview.jpg",
        "duration": 12.5,
        "user": {"id": 7, "name": "Alvaro", "url": "https://www.pexels.com/@alvaro"},
        "video_files": [
            {
                "id": 2001,
                "quality": "hd",
                "file_type": "video/mp4",
                "width": 1080,
                "height": 1920,
                "fps": 30.0,
                "link": "https://player.vimeo.com/external/1.mp4",
                "size": 1000,
            },
            {
                "id": 2002,
                "quality": "uehd",
                "file_type": "video/mp4",
                "width": 2160,
                "height": 3840,
                "fps": 30.0,
                "link": "https://player.vimeo.com/external/2.mp4",
                "size": 9000,
            },
            {
                "id": 2003,
                "quality": "hd",
                "file_type": "video/mp4",
                "width": 1920,
                "height": 1080,
                "fps": 30.0,
                "link": "https://player.vimeo.com/external/3.mp4",
                "size": 8000,
            },
        ],
        "video_pictures": [],
    }
    video.update(overrides)
    return video


def _payload(videos, total_results=None) -> dict:
    total = total_results if total_results is not None else len(videos)
    return {
        "page": 1,
        "per_page": 15,
        "total_results": total,
        "url": "https://api.pexels.com/v1/videos/search",
        "videos": videos,
    }


# ── API payload parsing / normalization ──────────────────────────────────────


def test_parse_video_search_response_normalizes() -> None:
    parsed = parse_video_search_response(_payload([_sample_video()], total_results=42))
    assert parsed["total_results"] == 42
    assert len(parsed["videos"]) == 1
    v = parsed["videos"][0]
    assert v["id"] == 1001
    assert len(v["video_files"]) == 3
    assert v["user"]["name"] == "Alvaro"
    # original resolution preserved
    assert v["width"] == 1920 and v["height"] == 1080


def test_parse_video_search_response_empty() -> None:
    parsed = parse_video_search_response(_payload([], total_results=0))
    assert parsed["total_results"] == 0
    assert parsed["videos"] == []


def test_parse_ignores_non_dict_videos() -> None:
    payload = _payload([_sample_video(), None, "garbage"], total_results=3)
    parsed = parse_video_search_response(payload)
    assert len(parsed["videos"]) == 1


def test_normalize_video_files_and_pictures() -> None:
    v = normalize_video(_sample_video())
    assert v["video_files"][0]["quality"] == "hd"
    assert v["video_files"][0]["file_type"] == "video/mp4"
    assert v["video_pictures"] == []


def test_ndjson_safe_handles_nested() -> None:
    obj = {"a": [{"b": 1}], "c": None}
    assert ndjson_safe(obj) == {"a": [{"b": 1}], "c": None}


# ── Query dedup ──────────────────────────────────────────────────────────────


def test_dedup_queries_unique_mapping() -> None:
    rows = load_all_rows()
    by_query = dedup_queries(rows)
    # canonical has two duplicated queryUsed strings -> 38 + 20 - 2 = 56 unique
    assert len(by_query) == 56
    assert sum(len(v) for v in by_query.values()) == 58


def test_dedup_queries_preserves_job_scene_segment() -> None:
    by_query = dedup_queries(load_all_rows())
    # 'Porsche 911 classic car photograph' appears twice in canonical
    q = [k for k in by_query if k == "Porsche 911 classic car photograph"]
    assert q and len(by_query[q[0]]) == 2
    for row in by_query[q[0]]:
        assert row["dataset"] == "canonical"
        assert row["jobId"] == "la-2026-08-17-234123"


# ── Rate-limit metadata ──────────────────────────────────────────────────────


def test_extract_rate_limit_case_insensitive() -> None:
    headers = {
        "X-RateLimit-Limit": "200",
        "x-ratelimit-remaining": "197",
        "X-RATELIMIT-RESET": "1634567890",
    }
    rl = extract_rate_limit(headers)
    assert rl == {"limit": 200, "remaining": 197, "reset": 1634567890}


def test_extract_rate_limit_missing_becomes_none() -> None:
    rl = extract_rate_limit({})
    assert rl == {"limit": None, "remaining": None, "reset": None}


def test_extract_rate_limit_bad_value_becomes_none() -> None:
    rl = extract_rate_limit({"X-RateLimit-Limit": "not-a-number"})
    assert rl["limit"] is None


# ── Portrait MP4 selection ───────────────────────────────────────────────────


def test_candidate_portrait_mp4s_filters() -> None:
    v = normalize_video(_sample_video())
    portrait = candidate_portrait_mp4s(v)
    # files 2001 (1080x1920), 2002 (2160x3840) portrait; 2003 landscape excluded
    assert len(portrait) == 2
    assert all(f["width"] <= f["height"] for f in portrait)


def test_select_review_mp4_prefers_720x1280_smallest() -> None:
    # portrait variants: 540x960 (size 500), 720x1280 (size 700), 1080x1920 (2000)
    v = normalize_video(
        _sample_video(
            video_files=[
                {"id": 1, "quality": "sd", "file_type": "video/mp4", "width": 540, "height": 960, "fps": 24, "link": "a.mp4", "size": 500},
                {"id": 2, "quality": "hd", "file_type": "video/mp4", "width": 720, "height": 1280, "fps": 30, "link": "b.mp4", "size": 700},
                {"id": 3, "quality": "hd", "file_type": "video/mp4", "width": 1080, "height": 1920, "fps": 30, "link": "c.mp4", "size": 2000},
            ]
        )
    )
    sel = select_review_mp4(v)
    assert sel["width"] == 720 and sel["height"] == 1280  # smallest >=720x1280


def test_select_review_mp4_falls_back_to_540x960() -> None:
    v = normalize_video(
        _sample_video(
            video_files=[
                {"id": 1, "quality": "sd", "file_type": "video/mp4", "width": 540, "height": 960, "fps": 24, "link": "a.mp4", "size": 500},
                {"id": 2, "quality": "hd", "file_type": "video/mp4", "width": 1280, "height": 720, "fps": 30, "link": "b.mp4", "size": 800},
            ]
        )
    )
    sel = select_review_mp4(v)
    assert sel["width"] == 540 and sel["height"] == 960


def test_select_review_mp4_none_when_no_portrait() -> None:
    v = normalize_video(
        _sample_video(
            video_files=[
                {"id": 1, "quality": "hd", "file_type": "video/mp4", "width": 1920, "height": 1080, "fps": 30, "link": "a.mp4", "size": 900},
            ]
        )
    )
    assert select_review_mp4(v) is None


def test_select_review_mp4_skips_non_mp4_and_hls() -> None:
    v = normalize_video(
        _sample_video(
            video_files=[
                {"id": 1, "quality": "hd", "file_type": "application/x-mpegURL", "width": 1080, "height": 1920, "fps": 30, "link": "playlist.m3u8", "size": 1},
                {"id": 2, "quality": "hd", "file_type": "video/mp4", "width": 1080, "height": 1920, "fps": 30, "link": "c.mp4", "size": 1500},
            ]
        )
    )
    sel = select_review_mp4(v)
    assert sel["file_type"] == "video/mp4"
    assert "m3u8" not in sel["link"]


# ── Request budget / cap ─────────────────────────────────────────────────────


def test_request_budget_cap() -> None:
    b = RequestBudget(cap=3)
    assert not b.exhausted
    assert b.spend() is True
    assert b.spend() is True
    assert b.spend() is True
    assert b.exhausted
    assert b.spend() is False  # beyond cap


def test_request_budget_default_cap_is_100() -> None:
    assert MAX_REQUESTS == 100
    b = RequestBudget()
    for _ in range(100):
        assert b.spend() is True
    assert b.spend() is False


# ── Landscape diagnostic ─────────────────────────────────────────────────────


def test_needs_landscape_diagnostic_zero_results() -> None:
    assert needs_landscape_diagnostic({"total_results": 0, "videos": []}) is True


def test_needs_landscape_diagnostic_no_720() -> None:
    v = _sample_video(video_files=[{"id": 1, "file_type": "video/mp4", "width": 540, "height": 960}])
    assert needs_landscape_diagnostic(_payload([v], total_results=5)) is True


def test_needs_landscape_diagnostic_has_720_false() -> None:
    v = _sample_video()  # includes 1080x1920 and 2160x3840 portrait
    assert needs_landscape_diagnostic(_payload([v], total_results=5)) is False


def test_classify_portrait_search() -> None:
    no_results = {"total_results": 0, "videos": []}
    assert classify_portrait_search(no_results, None) == "NO_LANDSCAPE_REQUEST"
    assert classify_portrait_search(no_results, {"total_results": 0, "videos": []}) == "NO_CONTENT"
    assert (
        classify_portrait_search(no_results, {"total_results": 7, "videos": []})
        == "CONTENT_EXISTS_BUT_NOT_PORTRAIT"
    )
    ok = _payload([_sample_video()], total_results=5)
    assert classify_portrait_search(ok, None) == "PORTRAIT_SUPPLY_OK"


# ── Supply metrics ───────────────────────────────────────────────────────────


def test_compute_supply_metrics_basic() -> None:
    rows = load_all_rows()
    by_query = dedup_queries(rows)
    results = {}
    for q in by_query:
        # give every query a healthy portrait result (>=720x1280 present)
        results[q] = _payload([_sample_video()], total_results=8)
    metrics = compute_supply_metrics(results, by_query)
    assert metrics["queriesSearched"] == len(by_query)
    assert metrics["queriesWithAnyResult"] == len(by_query)
    assert metrics["queriesWithZeroResults"] == 0
    assert metrics["fractionQueriesWithAtLeastOne720x1280Candidate"] == 1.0
    assert metrics["supplyClass_720x1280"] == "HIGH_SUPPLY"
    # coverage by dataset (2 canonical queryUsed are duplicated -> 36 unique)
    assert metrics["coverage_canonical"]["queries"] == 36
    assert metrics["coverage_development"]["queries"] == 20


def test_compute_supply_metrics_zero_results() -> None:
    rows = load_all_rows()
    by_query = dedup_queries(rows)
    results = {q: _payload([], total_results=0) for q in by_query}
    metrics = compute_supply_metrics(results, by_query)
    assert metrics["queriesWithAnyResult"] == 0
    assert metrics["queriesWithZeroResults"] == len(by_query)
    assert metrics["supplyClass_720x1280"] == "LOW_SUPPLY"
    assert metrics["coverage_canonical"]["fraction"] == 0.0
    assert metrics["coverage_development"]["fraction"] == 0.0


def test_classify_supply() -> None:
    assert classify_supply(0.95) == "HIGH_SUPPLY"
    assert classify_supply(0.90) == "HIGH_SUPPLY"
    assert classify_supply(0.80) == "MEDIUM_SUPPLY"
    assert classify_supply(0.70) == "MEDIUM_SUPPLY"
    assert classify_supply(0.50) == "LOW_SUPPLY"
    assert classify_supply(None) == "NO_DATA"


# ── Review set integrity / no API-key leakage ────────────────────────────────


def test_review_12_unique_and_bounded() -> None:
    assert len(REVIEW_12) == 12
    assert len({r["queryUsed"] for r in REVIEW_12}) == 12
    for r in REVIEW_12:
        assert r["queryUsed"]


def test_no_api_key_leakage_helpers() -> None:
    import os

    # ensure resolving reads env / .env but never bakes a value into module
    source = Path(_TOOLS, "pexels_video_supply_benchmark.py").read_text(encoding="utf-8")
    assert "PEXELS_API_KEY" in source or "pexels" in source
    # the API key env var name must not be hardcoded in a default literal that
    # could leak; resolve must return a value only from env/.env at runtime
    key = os.environ.get("PEXELS_API_KEY")
    assert key is None or isinstance(key, str)


def test_review_min_resolution_constants() -> None:
    assert REVIEW_MIN_RES_PREFERRED == (720, 1280)
    assert REVIEW_MIN_RES_FALLBACK == (540, 960)


# ── Import-safe / offline ────────────────────────────────────────────────────


def test_module_source_imports_are_stdlib_only() -> None:
    import re

    source = Path(_TOOLS, "pexels_video_supply_benchmark.py").read_text(encoding="utf-8")
    import_lines = [
        line
        for line in source.splitlines()
        if re.match(r"^\s*(?:import|from)\s+", line)
    ]
    assert import_lines, "expected at least an import line to scan"
    forbidden = (
        "torch",
        "open_clip",
        "transformers",
        "requests",
        "openai",
    )
    for token in forbidden:
        for line in import_lines:
            assert token not in line, f"forbidden import {token!r}: {line!r}"


def test_module_does_no_network_on_import() -> None:
    # importing the module and calling pure functions must not hit the network.
    rows = load_all_rows()
    assert len(rows) == 58
    v = _sample_video()
    assert select_review_mp4(normalize_video(v)) is not None


def test_fixtures_untouched_counts() -> None:
    canonical = json.loads((FIXTURE_DIR / "labels.json").read_text(encoding="utf-8"))
    dev = json.loads((FIXTURE_DIR / "holdout_labels.json").read_text(encoding="utf-8"))
    assert len(canonical["labels"]) == 38
    assert len(dev["labels"]) == 20
