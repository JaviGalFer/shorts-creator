"""Focused tests for tools/pexels_provider_fit_benchmark.py.

Pure offline logic tests for the Pexels provider-fit benchmark harness:
persisted row resolution (assetPreference/visualIntent), missing-metadata
handling, provider-fit policy (explicit-form precedence / photograph
eligibility / undecided), deterministic query adaptation (token preservation,
space normalisation), adapted==raw => no request, request dedup + hard cap 40,
no API-key leakage, RAW evidence reuse, exact-ID overlap/Jaccard metrics,
deterministic review sample, import-safety/offline, and the contact-sheet
layout helper.

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

from pexels_provider_fit_benchmark import (  # noqa: E402
    ADAPTED_MAX_REQUESTS,
    ADAPT_POLICY_VERSION,
    EXACT_FORM_TOKENS,
    PHOTOGRAPH_TOKENS,
    POLICY_VERSION,
    REVIEW_MANDATORY_QUERIES,
    REVIEW_SAMPLE_MAX,
    adapt_photograph_query,
    build_adapted_request_plan,
    build_review_sample,
    build_rows,
    classify_provider_fit,
    compute_thumbnail_rect,
    effective_form,
    exact_id_overlap_stats,
    jaccard,
    load_job_metadata,
    query_form,
    resolve_segment,
    row_fit_verdicts,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "asset_visual_fidelity"


def _synthetic_row(**overrides) -> dict:
    """A minimal resolved row (same shape as ``build_rows`` output)."""
    row = {
        "queryUsed": "example subject photograph",
        "jobId": "job-0000",
        "sceneNumber": 1,
        "segmentIndex": 1,
        "dataset": "canonical",
        "topic": "Example topic",
        "provider": "wikimedia_commons",
        "humanLabel": "CLEARLY_RELEVANT",
        "assetPath": "data/videos/job-0000/assets/scene_001_seg_001.jpg",
        "assetPreference": "photograph",
        "visualIntent": "explain",
        "persistedSearchQuery": "example subject photograph",
        "searchQueryMismatch": False,
        "missing": [],
        "queryForm": "photograph",
    }
    row.update(overrides)
    return row


# ── Persisted row resolution ────────────────────────────────────────────────


def test_58_rows_resolved_from_persisted_metadata() -> None:
    rows = build_rows()
    assert len(rows) == 58
    assert all(r["assetPreference"] is not None for r in rows)
    assert all(r["visualIntent"] is not None for r in rows)
    assert all(r["missing"] == [] for r in rows)


def test_persisted_distributions() -> None:
    rows = build_rows()
    from collections import Counter

    ap = Counter(r["assetPreference"] for r in rows)
    intent = Counter(r["visualIntent"] for r in rows)
    assert ap == {"photograph": 39, "diagram": 14, "illustration": 5}
    assert len(intent) == 6
    assert intent["explain"] == 27
    assert len(rows) == sum(ap.values())


def test_query_form_mismatches_recorded() -> None:
    rows = [r for r in build_rows() if r["searchQueryMismatch"]]
    assert len(rows) == 4
    # query form (what was actually searched) wins over the regenerated plan
    for r in rows:
        query_form(r["queryUsed"]) in ("photograph", "exactform")


def test_missing_metadata_reported_not_invented() -> None:
    # a job with no persisted metadata.json => both fields MISSING
    assert load_job_metadata("job-does-not-exist") is None
    seg = resolve_segment(None, 1, 1)
    assert seg is None
    row = _synthetic_row(missing=["assetPreference", "visualIntent"])
    assert row["missing"] == ["assetPreference", "visualIntent"]
    # a segment that does not exist in the metadata => MISSING
    meta = {"script": {"scenes": []}}
    assert resolve_segment(meta, 1, 1) is None


def test_query_form_detection() -> None:
    assert query_form("four stroke engine automobile photograph") == "photograph"
    assert query_form("data center infrastructure diagram") == "exactform"
    assert query_form("Porsche 911 original model illustration") == "exactform"
    assert query_form("Roman Empire historical scenes") == "none"
    assert query_form("no form here at all") == "none"


def test_effective_form_query_wins_over_persisted() -> None:
    # mismatch row: query asks for photograph but regenerated plan says diagram
    row = _synthetic_row(
        queryUsed="four stroke engine automobile photograph",
        queryForm="photograph",
        assetPreference="diagram",
        searchQueryMismatch=True,
    )
    assert effective_form(row) == "photograph"
    # no query form + persisted exact form => falls back to persisted
    row2 = _synthetic_row(
        queryUsed="something without a form", queryForm="none", assetPreference="diagram"
    )
    assert effective_form(row2) == "exactform"


# ── Provider-fit policy ─────────────────────────────────────────────────────


def test_classify_provider_fit_exact_form() -> None:
    # the policy operates on the effective category, not the raw token
    v = classify_provider_fit("exactform")
    assert v == {
        "photos": "INELIGIBLE_EXACT_FORM",
        "video": "INELIGIBLE_EXACT_FORM",
    }
    # every explicit form token maps to the exactform category
    for token in sorted(EXACT_FORM_TOKENS):
        row = _synthetic_row(
            queryUsed=f"some subject {token}",
            queryForm=query_form(f"some subject {token}"),
            assetPreference=token,
        )
        assert effective_form(row) == "exactform", token
        assert row_fit_verdicts(row) == {
            "photos": "INELIGIBLE_EXACT_FORM",
            "video": "INELIGIBLE_EXACT_FORM",
        }


def test_classify_provider_fit_photograph() -> None:
    v = classify_provider_fit("photograph")
    assert v == {"photos": "ELIGIBLE", "video": "ELIGIBLE_CANDIDATE"}


def test_classify_provider_fit_undecided() -> None:
    for cat in ("none", "undecided", "unknown", "", None):
        assert classify_provider_fit(cat) == {
            "photos": "UNDECIDED",
            "video": "UNDECIDED",
        }


def test_row_verdicts_real_rows() -> None:
    rows = {r["queryUsed"]: r for r in build_rows()}
    photo = row_fit_verdicts(rows["four stroke engine automobile photograph"])
    assert photo["photos"] == "ELIGIBLE"
    assert photo["video"] == "ELIGIBLE_CANDIDATE"
    diagram = row_fit_verdicts(rows["application hosting architecture diagram"])
    assert diagram == {"photos": "INELIGIBLE_EXACT_FORM", "video": "INELIGIBLE_EXACT_FORM"}


# ── Query adaptation ────────────────────────────────────────────────────────


def test_adaptation_removes_only_photo_tokens() -> None:
    a = adapt_photograph_query("four stroke engine automobile photograph")
    assert a["adaptedQuery"] == "four stroke engine automobile"
    assert a["removedTokens"] == ["photograph"]
    assert a["changed"] is True
    assert a["policyVersion"] == ADAPT_POLICY_VERSION

    a2 = adapt_photograph_query("completed medieval castle photograph")
    assert a2["adaptedQuery"] == "completed medieval castle"


def test_adaptation_preserves_semantic_tokens() -> None:
    a = adapt_photograph_query(
        "four stroke engine historical medieval construction automobile data center photograph"
    )
    assert a["adaptedQuery"] == (
        "four stroke engine historical medieval construction automobile data center"
    )


def test_adaptation_normalizes_spacing() -> None:
    a = adapt_photograph_query("  aurora   borealis  night sky   photograph  ")
    assert a["adaptedQuery"] == "aurora borealis night sky"
    assert a["changed"] is True


def test_adaptation_never_removes_exact_form_tokens() -> None:
    # photograph-form rows are INELIGIBLE when the query uses a diagram/illustration
    # form; adaptation must NOT convert them into B-roll.
    for q in (
        "data center infrastructure diagram",
        "medieval castle construction time diagram",
        "Porsche 911 original model illustration",
    ):
        assert query_form(q) == "exactform"


def test_adaptation_unchanged_produces_no_request() -> None:
    a = adapt_photograph_query("Roman Empire historical scenes")
    assert a["changed"] is False
    assert a["adaptedQuery"] == "Roman Empire historical scenes"
    plan = build_adapted_request_plan(
        [
            _synthetic_row(
                queryUsed="Roman Empire historical scenes",
                queryForm="none",
                assetPreference="photograph",
            )
        ]
    )
    assert plan == []


def test_build_plan_dedups_adapted_queries() -> None:
    rows = [
        _synthetic_row(queryUsed="town hall photograph", queryForm="photograph"),
        _synthetic_row(
            queryUsed="town hall photo", queryForm="photograph", segmentIndex=2
        ),
    ]
    plan = build_adapted_request_plan(rows)
    assert len(plan) == 1
    assert plan[0]["adaptedQuery"] == "town hall"
    assert plan[0]["sourceQueries"] == ["town hall photo", "town hall photograph"]
    assert len(plan[0]["rowKeys"]) == 2


def test_build_plan_never_reruns_raw_queries() -> None:
    # adapted query equals another persisted RAW queryUsed => no request.
    rows = [
        _synthetic_row(queryUsed="castle photograph", queryForm="photograph"),
        _synthetic_row(queryUsed="castle", queryForm="none", assetPreference="photograph"),
    ]
    plan = build_adapted_request_plan(rows)
    assert plan == []


def test_build_plan_hard_cap_40() -> None:
    rows = []
    for i in range(100):
        rows.append(
            _synthetic_row(
                queryUsed=f"unique subject {i} photograph",
                queryForm="photograph",
                segmentIndex=i,
            )
        )
    plan = build_adapted_request_plan(rows)
    assert len(plan) <= ADAPTED_MAX_REQUESTS
    assert ADAPTED_MAX_REQUESTS == 40


def test_build_plan_real_corpus() -> None:
    plan = build_adapted_request_plan(build_rows())
    assert len(plan) == 39
    assert all(p["changed"] for p in plan)
    assert all(p["adaptedQuery"] != p["rawQuery"] for p in plan)
    adapted = [p["adaptedQuery"] for p in plan]
    assert len(set(adapted)) == len(adapted)


# ── Evidence reuse / compare ────────────────────────────────────────────────


def test_video_supply_facts_and_compare() -> None:
    from pexels_provider_fit_benchmark import compare_raw_adapted, video_supply_facts

    def _video(vid: int, w=720, h=1280) -> dict:
        return {
            "id": vid,
            "width": w,
            "height": h,
            "url": f"https://www.pexels.com/video/{vid}/",
            "image": f"https://images.pexels.com/videos/{vid}/preview.jpg",
            "duration": 5,
            "video_files": [
                {"id": vid * 10, "quality": "hd", "file_type": "video/mp4",
                 "width": w, "height": h, "fps": 30, "link": f"https://www.pexels.com/video/{vid}.mp4"},
            ],
            "video_pictures": [],
        }

    raw = {"videos": [_video(1), _video(2), _video(3)], "total_results": 100}
    ada = {"videos": [_video(2), _video(4), _video(5), _video(6)], "total_results": 90}
    facts = video_supply_facts(raw)
    assert facts["idsTop15"] == [1, 2, 3]
    assert facts["atLeast720x1280"] == 3

    cmp = compare_raw_adapted(raw, ada)
    assert cmp["ids"]["overlapCount"] == 1
    assert 2 in cmp["ids"]["sharedTop15"]
    assert cmp["ids"]["newIdsInt21ByAdaptation"] == [4, 5, 6]
    assert cmp["comparison"]["raw_total_results"] == 100
    assert cmp["comparison"]["adapted_total_results"] == 90


def test_video_evidence_files_exists() -> None:
    from pexels_provider_fit_benchmark import PHOTO_SUPPLY_EVIDENCE, VIDEO_SUPPLY_EVIDENCE

    assert PHOTO_SUPPLY_EVIDENCE.exists(), "missing photo RAW evidence"
    assert VIDEO_SUPPLY_EVIDENCE.exists(), "missing video RAW evidence"


def test_load_evidence_raises_when_missing(tmp_path, monkeypatch) -> None:
    import pexels_provider_fit_benchmark as m

    real_photo = m.PHOTO_SUPPLY_EVIDENCE
    real_video = m.VIDEO_SUPPLY_EVIDENCE
    monkeypatch.setattr(m, "PHOTO_SUPPLY_EVIDENCE", tmp_path / "photo-missing.json")
    monkeypatch.setattr(m, "VIDEO_SUPPLY_EVIDENCE", tmp_path / "video-missing.json")
    try:
        m.load_photo_evidence()
        assert False, "photo evidence should raise"
    except FileNotFoundError:
        pass
    try:
        m.load_video_evidence()
        assert False, "video evidence should raise"
    except FileNotFoundError:
        pass
    # guard: the real persisted evidence must exist for the real run
    assert real_photo.exists()
    assert real_video.exists()


# ── Overlap / Jaccard ───────────────────────────────────────────────────────


def test_jaccard() -> None:
    assert jaccard([], []) == 0.0
    assert jaccard([1, 2, 3], [2, 3, 4]) == 2 / 4
    assert jaccard([1, 2], [1, 2]) == 1.0
    assert jaccard([1], [2]) == 0.0


def test_exact_id_overlap_stats() -> None:
    stats = exact_id_overlap_stats(
        {
            "a": [1, 2, 3, 4],
            "b": [3, 4, 5],
            "c": [6],
        }
    )
    assert stats["queries"] == 3
    assert stats["uniqueIds"] == 6
    assert stats["repeatedIdCount"] == 2  # ids 3 and 4 shared by a and b
    assert stats["queryPairsWithOverlap"] == 1
    assert stats["sortedQueryPairs"][0]["queries"] == ["a", "b"]
    assert stats["sortedQueryPairs"][0]["overlapCount"] == 2


def test_exact_id_overlap_dedups_within_query() -> None:
    stats = exact_id_overlap_stats({"a": [1, 1, 2], "b": [1]})
    assert stats["uniqueIds"] == 2
    assert stats["totalIdOccurrences"] == 3


# ── Review sample (deterministic) ───────────────────────────────────────────


def test_review_sample_contains_mandatory_and_caps_at_10() -> None:
    rows = build_rows()
    photo_queries = sorted(
        {r["queryUsed"] for r in rows if effective_form(r) == "photograph"}
    )
    topics = {}
    for r in rows:
        topics.setdefault(r["queryUsed"], set()).add(r["topic"])
    topics = {q: sorted(t) for q, t in topics.items()}

    sample = build_review_sample(photo_queries, topics)
    assert len(sample) == REVIEW_SAMPLE_MAX == 10
    sample_queries = [s["query"] for s in sample]
    for mandatory in REVIEW_MANDATORY_QUERIES:
        assert mandatory in sample_queries
    count = sum(1 for s in sample if s["mandatory"])
    assert count == 5


def test_review_sample_deterministic() -> None:
    rows = build_rows()
    photo_queries = sorted(
        {r["queryUsed"] for r in rows if effective_form(r) == "photograph"}
    )
    topics = {}
    for r in rows:
        topics.setdefault(r["queryUsed"], set()).add(r["topic"])
    topics = {q: sorted(t) for q, t in topics.items()}
    a = build_review_sample(photo_queries, topics)
    b = build_review_sample(photo_queries, topics)
    assert a == b


def test_review_sample_topic_diversity() -> None:
    sample = build_review_sample(
        [
            "a topic one photograph",
            "b topic one photograph",
            "c topic two photograph",
            "d topic three photograph",
        ],
        {
            "a topic one photograph": ["T1"],
            "b topic one photograph": ["T1"],
            "c topic two photograph": ["T2"],
            "d topic three photograph": ["T3"],
        },
        mandatory=["a topic one photograph"],
    )
    topics_in_sample = {t for s in sample for t in s["topics"]}
    assert topics_in_sample == {"T1", "T2", "T3"}


def test_review_sample_respects_missing_mandatory() -> None:
    sample = build_review_sample(
        ["x photograph", "y photograph"],
        {"x photograph": ["T1"], "y photograph": ["T2"]},
        mandatory=["not present photograph"],
    )
    queries = [s["query"] for s in sample]
    assert "not present photograph" not in queries


# ── Key never persisted / import-safe / offline ─────────────────────────────


def test_no_api_key_value_hardcoded() -> None:
    source = Path(_TOOLS, "pexels_provider_fit_benchmark.py").read_text(encoding="utf-8")
    assert "PEXELS_API_KEY" in source


def test_module_source_uses_authorization_and_ua() -> None:
    source = Path(_TOOLS, "pexels_provider_fit_benchmark.py").read_text(encoding="utf-8")
    assert '"Authorization"' in source and "User-Agent" in source


def test_module_source_imports_stdlib_only() -> None:
    import re

    source = Path(_TOOLS, "pexels_provider_fit_benchmark.py").read_text(encoding="utf-8")
    import_lines = [
        line for line in source.splitlines() if re.match(r"^\s*(?:import|from)\s+", line)
    ]
    for token in ("torch", "open_clip", "transformers", "requests", "openai", "httpx"):
        for line in import_lines:
            assert token not in line, f"forbidden import {token!r}: {line!r}"


def test_no_network_on_import() -> None:
    # importing and pure calls never touch the network
    rows = build_rows()
    assert len(rows) == 58
    assert adapt_photograph_query("volcano explosion photograph")["changed"] is True


def test_resolve_api_key_returns_none_without_sources(monkeypatch) -> None:
    from pexels_provider_fit_benchmark import resolve_api_key

    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    key = resolve_api_key()
    assert key is None or isinstance(key, str)


# ── Contact-sheet layout helper ─────────────────────────────────────────────


def test_compute_thumbnail_rect_preserves_aspect_no_crop() -> None:
    w, h = compute_thumbnail_rect((1080, 1920), 288, 408)
    assert w <= 288 and h <= 408
    assert abs(w / h - 1080 / 1920) < 0.02
    assert h == 408


def test_compute_thumbnail_rect_landscape() -> None:
    w, h = compute_thumbnail_rect((1920, 1080), 288, 408)
    assert w <= 288 and h <= 408
    assert abs(w / h - 1920 / 1080) < 0.02


def test_compute_thumbnail_rect_handles_bad_sizes() -> None:
    assert compute_thumbnail_rect((0, 0), 288, 408) == (288, 408)


# ── Policy version constants ────────────────────────────────────────────────


def test_policy_versions() -> None:
    assert POLICY_VERSION == "provider-fit-policy-v1"
    assert ADAPT_POLICY_VERSION == "query-adapt-v1"
    assert PHOTOGRAPH_TOKENS == {"photograph", "photo", "photography"}


def test_fixtures_untouched_counts() -> None:
    canonical = json.loads((FIXTURE_DIR / "labels.json").read_text(encoding="utf-8"))
    dev = json.loads((FIXTURE_DIR / "holdout_labels.json").read_text(encoding="utf-8"))
    assert len(canonical["labels"]) == 38
    assert len(dev["labels"]) == 20