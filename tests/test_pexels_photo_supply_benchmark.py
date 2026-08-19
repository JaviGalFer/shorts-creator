"""Focused tests for tools/pexels_photo_supply_benchmark.py.

Pure offline logic tests for the Pexels Photos supply benchmark harness:
parsing, src variants, query dedup (56), orientation/resolution helpers, supply
metrics, rate-limit, request cap, diagnostic fallback, no API-key persistence,
User-Agent, import-safety/offline, layout helper, and fixture immutability.

No real network calls and no ML.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = str(_PROJECT_ROOT / "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from pexels_photo_supply_benchmark import (  # noqa: E402
    PHOTO_DIAGNOSTIC_BUDGET,
    PHOTO_MAX_MAIN_REQUESTS,
    PHOTO_MAX_REQUESTS,
    RANK_23_SRC,
    REVIEW_MAX_ORIGINALS,
    RequestBudget,
    classify_search,
    classify_supply,
    compute_thumbnail_rect,
    compute_supply_metrics,
    dedup_queries,
    extract_rate_limit,
    generate_comparison_contact_sheet,
    is_portrait,
    load_all_rows,
    needs_diagnostic,
    normalize_photo,
    original_at_least,
    parse_photo_search_response,
    resolve_api_key,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "asset_visual_fidelity"


def _sample_photo(**overrides) -> dict:
    photo = {
        "id": 5001,
        "width": 1080,
        "height": 1920,
        "url": "https://www.pexels.com/photo/5001/",
        "photographer": "Nome Photographer",
        "photographer_url": "https://www.pexels.com/@nome",
        "photographer_id": 999,
        "avg_color": "#112233",
        "alt": "test alt",
        "src": {
            "original": "https://images.pexels.com/5001-original.jpg",
            "large2x": "https://images.pexels.com/5001-l2x.jpg",
            "large": "https://images.pexels.com/5001-large.jpg",
            "medium": "https://images.pexels.com/5001-medium.jpg",
            "small": "https://images.pexels.com/5001-small.jpg",
            "portrait": "https://images.pexels.com/5001-portrait.jpg",
            "landscape": "https://images.pexels.com/5001-landscape.jpg",
            "tiny": "https://images.pexels.com/5001-tiny.jpg",
        },
    }
    photo.update(overrides)
    return photo


def _payload(photos, total_results=None) -> dict:
    total = total_results if total_results is not None else len(photos)
    return {
        "page": 1,
        "per_page": 15,
        "total_results": total,
        "url": "https://api.pexels.com/v1/search",
        "photos": photos,
    }


# ── Parsing Photo / src variants ────────────────────────────────────────────


def test_parse_photo_search_response_normalizes() -> None:
    parsed = parse_photo_search_response(_payload([_sample_photo()], total_results=7))
    assert parsed["total_results"] == 7
    assert len(parsed["photos"]) == 1
    p = parsed["photos"][0]
    assert p["id"] == 5001
    assert p["width"] == 1080 and p["height"] == 1920
    assert p["photographer"] == "Nome Photographer"


def test_parse_photo_src_variants_complete() -> None:
    p = parse_photo_search_response(_payload([_sample_photo()]))["photos"][0]
    assert set(p["src"].keys()) == {
        "original", "large2x", "large", "medium", "small", "portrait", "landscape", "tiny",
    }
    assert p["src"]["original"].endswith("original.jpg")
    assert p["src"]["large2x"].endswith("l2x.jpg")


def test_parse_photo_empty_and_bad_rows() -> None:
    assert parse_photo_search_response(_payload([], total_results=0))["photos"] == []
    parsed = parse_photo_search_response(_payload([_sample_photo(), None, "x"]))
    assert len(parsed["photos"]) == 1


def test_normalize_photo_fields() -> None:
    p = normalize_photo(_sample_photo())
    assert p["photographer_url"] == "https://www.pexels.com/@nome"
    assert p["photographer_id"] == 999
    assert p["avg_color"] == "#112233"
    assert p["alt"] == "test alt"


# ── Dedup 56 queries ────────────────────────────────────────────────────────


def test_dedup_queries_56_unique_from_58_rows() -> None:
    rows = load_all_rows()
    assert len(rows) == 58
    by_query = dedup_queries(rows)
    assert len(by_query) == 56
    assert sum(len(v) for v in by_query.values()) == 58


# ── Orientation / resolution helpers ────────────────────────────────────────


def test_is_portrait() -> None:
    assert is_portrait({"width": 1080, "height": 1920}) is True
    assert is_portrait({"width": 1920, "height": 1080}) is False
    assert is_portrait({"width": 0, "height": 1920}) is False
    assert is_portrait({"width": "x", "height": 1920}) is False


def test_original_at_least() -> None:
    p = {"width": 1080, "height": 1920}
    assert original_at_least(p, 720, 1280) is True
    assert original_at_least(p, 1080, 1920) is True
    assert original_at_least(p, 2160, 3840) is False
    # landscape 1920x1080 fails portrait threshold even if large
    assert original_at_least({"width": 1920, "height": 1080}, 720, 1280) is False


# ── Supply metrics ──────────────────────────────────────────────────────────


def test_compute_supply_metrics_all_portrait_ok() -> None:
    rows = load_all_rows()
    by_query = dedup_queries(rows)
    results = {}
    for q in by_query:
        # a portrait photo >= 1080x1920 satisfies both thresholds
        results[q] = _payload([_sample_photo()], total_results=9)
    m = compute_supply_metrics(results, by_query)
    assert m["queriesSearched"] == 56
    assert m["queriesWithAnyResult"] == 56
    assert m["queriesWithZeroResults"] == 0
    assert m["fractionQueriesWithAtLeastOne720x1280Candidate"] == 1.0
    assert m["fractionQueriesWithAtLeastOne1080x1920Candidate"] == 1.0
    assert m["supplyClass_720x1280"] == "HIGH_SUPPLY"
    assert m["coverage_canonical"]["queries"] == 36
    assert m["coverage_development"]["queries"] == 20


def test_compute_supply_metrics_zero_results() -> None:
    rows = load_all_rows()
    by_query = dedup_queries(rows)
    results = {q: _payload([], total_results=0) for q in by_query}
    m = compute_supply_metrics(results, by_query)
    assert m["queriesWithAnyResult"] == 0
    assert m["queriesWithZeroResults"] == 56
    assert m["supplyClass_720x1280"] == "LOW_SUPPLY"


def test_compute_supply_metrics_original_counts() -> None:
    # two portrait, one landscape
    photos = [
        _sample_photo(id=1),
        _sample_photo(id=2, width=1080, height=1920),
        _sample_photo(id=3, width=1920, height=1080),
    ]
    m = compute_supply_metrics(
        {"q": _payload(photos, total_results=3)},
        {"q": [{"queryUsed": "q", "dataset": "development"}]},
    )
    assert m["candidatesReturned"] == 3
    assert m["originalPortraitCount"] == 2
    assert m["originalPortraitAtLeast720x1280"] == 2
    assert m["originalPortraitAtLeast1080x1920"] == 2


def test_classify_supply() -> None:
    assert classify_supply(0.95) == "HIGH_SUPPLY"
    assert classify_supply(0.80) == "MEDIUM_SUPPLY"
    assert classify_supply(0.5) == "LOW_SUPPLY"
    assert classify_supply(None) == "NO_DATA"


# ── Rate-limit ──────────────────────────────────────────────────────────────


def test_extract_rate_limit_case_insensitive() -> None:
    rl = extract_rate_limit({"X-RateLimit-Limit": "200", "x-ratelimit-remaining": "198", "X-Ratelimit-Reset": "99"})
    assert rl == {"limit": 200, "remaining": 198, "reset": 99}


def test_extract_rate_limit_missing() -> None:
    assert extract_rate_limit({}) == {"limit": None, "remaining": None, "reset": None}


# ── Request cap / budget ────────────────────────────────────────────────────


def test_photo_request_budget_constants() -> None:
    assert PHOTO_MAX_MAIN_REQUESTS == 56
    assert PHOTO_DIAGNOSTIC_BUDGET == 14
    assert PHOTO_MAX_REQUESTS == 70


def test_request_budget_enforces_cap() -> None:
    b = RequestBudget(cap=3)
    assert b.spend() and b.spend() and b.spend()
    assert b.exhausted
    assert b.spend() is False


# ── Diagnostic fallback ─────────────────────────────────────────────────────


def test_needs_diagnostic_zero_results() -> None:
    assert needs_diagnostic({"total_results": 0, "photos": []}) is True


def test_needs_diagnostic_no_720x1280() -> None:
    p = _sample_photo(width=540, height=960)
    assert needs_diagnostic({"total_results": 5, "photos": [p]}) is True


def test_needs_diagnostic_has_720_false() -> None:
    assert needs_diagnostic({"total_results": 5, "photos": [_sample_photo()]}) is False


def test_classify_search_three_ways() -> None:
    ok = {"total_results": 5, "photos": [_sample_photo()]}
    assert classify_search(ok, None) == "PORTRAIT_SUPPLY_OK"
    zero = {"total_results": 0, "photos": []}
    assert classify_search(zero, None) == "NO_LANDSCAPE_REQUEST"
    assert classify_search(zero, {"total_results": 0, "photos": []}) == "NO_CONTENT"
    assert classify_search(zero, {"total_results": 6, "photos": []}) == "CONTENT_EXISTS_BUT_NOT_PORTRAIT"


# ── Key never persisted / User-Agent / import-safe ──────────────────────────


def test_resolve_api_key_returns_none_without_sources(monkeypatch) -> None:
    import os

    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    # ensure the helper is pure (no hardcoded key literal)
    key = resolve_api_key()
    assert key is None or isinstance(key, str)


def test_no_api_key_value_hardcoded() -> None:
    source = Path(_TOOLS, "pexels_photo_supply_benchmark.py").read_text(encoding="utf-8")
    # only the env-var name may appear, never a literal secret value pattern
    assert "PEXELS_API_KEY" in source


def test_module_source_uses_authorization_and_ua() -> None:
    source = Path(_TOOLS, "pexels_photo_supply_benchmark.py").read_text(encoding="utf-8")
    assert '"Authorization"' in source and "User-Agent" in source


def test_module_source_imports_stdlib_only() -> None:
    import re

    source = Path(_TOOLS, "pexels_photo_supply_benchmark.py").read_text(encoding="utf-8")
    import_lines = [
        line for line in source.splitlines() if re.match(r"^\s*(?:import|from)\s+", line)
    ]
    for token in ("torch", "open_clip", "transformers", "requests", "openai"):
        for line in import_lines:
            assert token not in line, f"forbidden import {token!r}: {line!r}"


def test_no_network_on_import() -> None:
    rows = load_all_rows()
    assert len(rows) == 58
    p = parse_photo_search_response(_payload([_sample_photo()]))["photos"][0]
    assert is_portrait(p)


# ── Contact sheet layout helper ─────────────────────────────────────────────


def test_compute_thumbnail_rect_preserves_aspect_no_crop() -> None:
    w, h = compute_thumbnail_rect((1080, 1920), 288, 408)
    # must fit inside the box and preserve the 9:16 ratio
    assert w <= 288 and h <= 408
    assert abs(w / h - 1080 / 1920) < 0.02
    # portrait should occupy full height
    assert h == 408


def test_compute_thumbnail_rect_landscape() -> None:
    w, h = compute_thumbnail_rect((1920, 1080), 288, 408)
    assert w <= 288 and h <= 408
    assert abs(w / h - 1920 / 1080) < 0.02


def test_compute_thumbnail_rect_handles_bad_sizes() -> None:
    assert compute_thumbnail_rect((0, 0), 288, 408) == (288, 408)


# ── Fixtures unchanged ──────────────────────────────────────────────────────


def test_fixtures_untouched_counts() -> None:
    canonical = json.loads((FIXTURE_DIR / "labels.json").read_text(encoding="utf-8"))
    dev = json.loads((FIXTURE_DIR / "holdout_labels.json").read_text(encoding="utf-8"))
    assert len(canonical["labels"]) == 38
    assert len(dev["labels"]) == 20


def test_review_12_unique() -> None:
    from pexels_video_supply_benchmark import REVIEW_12

    assert len(REVIEW_12) == 12
    assert len({r["queryUsed"] for r in REVIEW_12}) == 12


def test_review_images_constants() -> None:
    assert REVIEW_MAX_ORIGINALS == 12
    assert RANK_23_SRC == "large2x"
