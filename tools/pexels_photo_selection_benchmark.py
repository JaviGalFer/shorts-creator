#!/usr/bin/env python3
"""Offline Phase A preparation for the Pexels Photo selection benchmark.

This evaluation-only module reads persisted Pexels artifacts. It never performs
HTTP, reads environment variables, or mutates source evidence. Scoring deliberately
does not accept human preferences; evaluation is a separate operation and remains
blocked while the preference fixture is unlabeled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
PHOTO_SOURCE = ROOT / "data/evaluations/pexels-visual-supply-benchmark/photo-supply-benchmark.json"
REVIEW_SOURCE = ROOT / "data/evaluations/pexels-provider-fit-benchmark/review-sample.json"
MANIFEST_PATH = ROOT / "tests/fixtures/pexels_photo_selection/review_manifest.json"
PREFERENCES_PATH = ROOT / "tests/fixtures/pexels_photo_selection/human_preferences.json"
REVIEW_DIR = ROOT / "data/evaluations/pexels-photo-selection-benchmark/review"
PHASE_A_RESULT_PATH = ROOT / "data/evaluations/pexels-photo-selection-benchmark/phase-a.json"

RAW = "A0_RAW"
LEXICAL_RECALL = "A1_EXACT_LEXICAL_QUERY_RECALL"
BM25 = "A2_BM25"
STRATEGIES = frozenset({RAW, LEXICAL_RECALL, BM25})
ALIASES = ("A", "B", "C")
UNLABELED = "UNLABELED"
LABELED = "LABELED"
AWAITING_HUMAN_REVIEW = "AWAITING_HUMAN_REVIEW"
HUMAN_REVIEW_READY = "HUMAN_REVIEW_READY"
CANONICAL_REVIEW_QUERIES: tuple[str, ...] = (
    "four stroke engine automobile photograph",
    "completed medieval castle photograph",
    "medieval castle construction photograph",
    "medieval castle historical significance photograph",
    "four stroke engine parts photograph",
    "blue ringed octopus venom photograph",
    "PlayStation Nintendo 64 comparison photograph",
    "Java code snippet photograph",
    "engine explosion in piston photograph",
    "amortization chart graph photograph",
)
TOKEN_RE = re.compile(r"[a-z0-9]+")
GENERIC_FILLER = frozenset({
    "image", "images", "photo", "photos", "photograph", "photographs",
    "picture", "pictures", "illustration", "illustrations", "drawing",
    "drawings", "graphic", "graphics", "clipart", "stock", "digital",
    "free", "download", "downloads", "resolution", "wallpaper", "wallpapers",
    "background", "backgrounds", "jpeg", "jpg", "png", "webp", "gif",
    "high", "quality", "file", "files", "view", "views", "icon", "icons",
})
STOPWORDS = frozenset({
    "about", "after", "all", "also", "and", "any", "are", "because", "before",
    "but", "can", "could", "for", "from", "has", "have", "how", "into", "its",
    "may", "more", "most", "not", "of", "off", "onto", "or", "our", "over",
    "per", "than", "that", "the", "their", "then", "these", "they", "this",
    "those", "through", "under", "upon", "very", "was", "were", "what", "when",
    "where", "which", "while", "who", "why", "will", "with", "would", "you",
    "your",
})


def normalized_tokens(text: str | None) -> frozenset[str]:
    """Return the frozen Phase A token set without aliases or morphology rules."""
    normalized = unicodedata.normalize("NFKC", text or "").casefold()
    return frozenset(
        token for token in TOKEN_RE.findall(normalized)
        if token not in STOPWORDS and token not in GENERIC_FILLER
    )


def source_hash(path: Path = PHOTO_SOURCE) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"INVALID_JSON_OBJECT:{path}")
    return value


def load_review_queries() -> list[str]:
    sample = load_json(REVIEW_SOURCE).get("sample")
    if not isinstance(sample, list) or len(sample) != 10:
        raise ValueError("INVALID_REVIEW_SAMPLE")
    queries = [item.get("query") for item in sample if isinstance(item, dict)]
    if len(queries) != 10 or len(set(queries)) != 10 or not all(isinstance(q, str) for q in queries):
        raise ValueError("INVALID_REVIEW_QUERIES")
    return queries


def load_photo_candidates(query: str, limit: int = 15) -> list[dict[str, Any]]:
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > 15:
        raise ValueError("INVALID_CANDIDATE_LIMIT")
    raw = load_json(PHOTO_SOURCE).get("rawResults")
    if not isinstance(raw, dict) or not isinstance(raw.get(query), dict):
        raise ValueError(f"MISSING_QUERY:{query}")
    photos = raw[query].get("photos")
    if not isinstance(photos, list) or len(photos) < limit:
        raise ValueError(f"INSUFFICIENT_PHOTOS:{query}")
    candidates: list[dict[str, Any]] = []
    for rank, photo in enumerate(photos[:limit], start=1):
        if not isinstance(photo, dict) or not isinstance(photo.get("id"), int):
            raise ValueError(f"INVALID_PHOTO:{query}:{rank}")
        candidates.append({
            "candidateId": photo["id"],
            "pexelsQueryRank": rank,
            "alt": str(photo.get("alt") or ""),
            "width": photo.get("width"),
            "height": photo.get("height"),
        })
    if len({item["candidateId"] for item in candidates}) != len(candidates):
        raise ValueError(f"DUPLICATE_CANDIDATE_ID:{query}")
    return candidates


def lexical_recall_score(query: str, alt: str | None) -> float:
    query_tokens = normalized_tokens(query)
    if not query_tokens:
        return 0.0
    return len(query_tokens & normalized_tokens(alt)) / len(query_tokens)


def bm25_scores(query: str, candidates: Iterable[dict[str, Any]]) -> dict[int, float]:
    """Return fixed-parameter BM25 scores over one persisted query/page corpus."""
    items = list(candidates)
    if not items:
        return {}
    query_tokens = normalized_tokens(query)
    documents = [normalized_tokens(str(item.get("alt") or "")) for item in items]
    lengths = [len(document) for document in documents]
    avg_length = sum(lengths) / len(lengths)
    document_frequency = Counter(token for document in documents for token in document)
    scores: dict[int, float] = {}
    for item, document, length in zip(items, documents, lengths):
        score = 0.0
        for token in query_tokens:
            frequency = 1 if token in document else 0
            if not frequency:
                continue
            idf = math.log(1 + (len(items) - document_frequency[token] + 0.5) / (document_frequency[token] + 0.5))
            denominator = frequency + 1.2 * (1 - 0.75 + 0.75 * length / avg_length)
            score += idf * frequency * (1.2 + 1) / denominator
        scores[item["candidateId"]] = score
    return scores


def score_candidates(strategy: str, query: str, candidates: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score and order candidates; this API intentionally has no label argument."""
    if strategy not in STRATEGIES:
        raise ValueError(f"UNKNOWN_STRATEGY:{strategy}")
    items = [dict(candidate) for candidate in candidates]
    if any(not isinstance(item.get("pexelsQueryRank"), int) for item in items):
        raise ValueError("INVALID_RAW_RANK")
    if len({item["pexelsQueryRank"] for item in items}) != len(items):
        raise ValueError("DUPLICATE_RAW_RANK")
    if strategy == RAW:
        scores = {item["candidateId"]: None for item in items}
    elif strategy == LEXICAL_RECALL:
        scores = {item["candidateId"]: lexical_recall_score(query, item.get("alt")) for item in items}
    else:
        scores = bm25_scores(query, items)
    ordered = sorted(
        items,
        key=lambda item: (
            item["pexelsQueryRank"] if strategy == RAW else -float(scores[item["candidateId"]]),
            item["pexelsQueryRank"],
        ),
    )
    return [
        {**item, "selectorScore": scores[item["candidateId"]], "selectorRank": rank}
        for rank, item in enumerate(ordered, start=1)
    ]


def blind_alias_order(query: str, candidates: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign A/B/C by a score-independent SHA-256 permutation of raw top-3."""
    items = list(candidates)
    if len(items) != 3 or {item["pexelsQueryRank"] for item in items} != {1, 2, 3}:
        raise ValueError("BLIND_MAPPING_REQUIRES_RAW_TOP3")
    ordered = sorted(
        items,
        key=lambda item: hashlib.sha256(
            f"pexels-photo-selection-v1:{query}:{item['pexelsQueryRank']}".encode("utf-8")
        ).hexdigest(),
    )
    return [{**item, "alias": alias} for alias, item in zip(ALIASES, ordered)]


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    manifest = load_json(path)
    entries = manifest.get("queries")
    if manifest.get("mappingVersion") != "sha256-pexels-photo-selection-v1" or not isinstance(entries, list):
        raise ValueError("INVALID_REVIEW_MANIFEST")
    if len(entries) != 10:
        raise ValueError("INVALID_MANIFEST_QUERY_COUNT")
    seen_queries: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("queryUsed"), str):
            raise ValueError("INVALID_MANIFEST_QUERY")
        query = entry["queryUsed"]
        if query in seen_queries:
            raise ValueError("DUPLICATE_MANIFEST_QUERY")
        seen_queries.add(query)
        candidates = entry.get("candidates")
        if not isinstance(candidates, list) or len(candidates) != 3:
            raise ValueError(f"INVALID_MANIFEST_CANDIDATES:{query}")
        if {candidate.get("alias") for candidate in candidates} != set(ALIASES):
            raise ValueError(f"INVALID_MANIFEST_ALIASES:{query}")
        if {candidate.get("pexelsQueryRank") for candidate in candidates} != {1, 2, 3}:
            raise ValueError(f"INVALID_MANIFEST_RANKS:{query}")
        if len({candidate.get("candidateId") for candidate in candidates}) != 3:
            raise ValueError(f"INVALID_MANIFEST_IDS:{query}")
    return manifest


def preferences_status(path: Path | str = PREFERENCES_PATH) -> str:
    """Return the frozen status key for the preference fixture at path.

    Delegates to the authoritative pure validator: valid UNLABELED fixtures map
    to AWAITING_HUMAN_REVIEW, valid LABELED fixtures map to HUMAN_REVIEW_READY,
    and invalid fixtures raise a coherent ValueError. No Phase A verdict is
    computed here.
    """
    validation = validate_preferences(path)
    if validation["status"] == UNLABELED:
        return AWAITING_HUMAN_REVIEW
    if validation["status"] == LABELED:
        return HUMAN_REVIEW_READY
    raise ValueError(validation.get("reason", "INVALID_PREFERENCES"))


def validate_preferences(path: Path | str = PREFERENCES_PATH) -> dict[str, str]:
    """Validate the human preference fixture at path. Pure: reads and validates.

    The path is resolved against ROOT when relative, so validation does not
    depend on the process working directory. Only the frozen UNLABELED / LABELED
    contract is enforced; aliases, allUnusable rules, and the 10 canonical
    queries are unchanged.
    """
    fixture_path = Path(path)
    if not fixture_path.is_absolute():
        fixture_path = ROOT / fixture_path
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"status": "INVALID", "reason": "not a JSON object"}
    if data.get("schemaVersion") != 1:
        return {"status": "INVALID", "reason": "bad schemaVersion"}
    status = data.get("status")
    if status == UNLABELED:
        entries = data.get("preferences")
        if not isinstance(entries, list) or len(entries) != 10:
            return {"status": "INVALID", "reason": "expected 10 entries"}
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict):
                return {"status": "INVALID", "reason": f"entry {i}: not an object"}
            if not isinstance(entry.get("queryUsed"), str) or not entry.get("queryUsed"):
                return {"status": "INVALID", "reason": f"entry {i}: missing queryUsed"}
            if entry.get("preferredAliases") != []:
                return {"status": "INVALID", "reason": f"entry {i}: preferredAliases must be []"}
            if entry.get("allUnusable") is not None:
                return {"status": "INVALID", "reason": f"entry {i}: allUnusable must be null"}
            if not isinstance(entry.get("notes"), str):
                return {"status": "INVALID", "reason": f"entry {i}: notes must be string"}
        return {"status": UNLABELED, "description": "10 queries, all preferences empty, awaiting review"}
    if status == LABELED:
        entries = data.get("preferences")
        if not isinstance(entries, list) or len(entries) != 10:
            return {"status": "INVALID", "reason": "expected 10 entries"}
        present: list[str] = []
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict):
                return {"status": "INVALID", "reason": f"entry {i}: not an object"}
            query = entry.get("queryUsed")
            if not isinstance(query, str) or not query:
                return {"status": "INVALID", "reason": f"entry {i}: missing queryUsed"}
            present.append(query)
            if not isinstance(entry.get("notes"), str):
                return {"status": "INVALID", "reason": f"entry {i}: notes must be string"}
            aliases = entry.get("preferredAliases")
            if not isinstance(aliases, list):
                return {"status": "INVALID", "reason": f"entry {i}: preferredAliases must be a list"}
            all_unusable = entry.get("allUnusable")
            if len(aliases) == 0:
                if all_unusable is not True:
                    return {"status": "INVALID", "reason": f"entry {i}: allUnusable must be true when no aliases"}
            else:
                if all_unusable is not False:
                    return {"status": "INVALID", "reason": f"entry {i}: allUnusable must be false when aliases present"}
                if len(set(aliases)) != len(aliases):
                    return {"status": "INVALID", "reason": f"entry {i}: duplicate alias"}
                if any(alias not in set(ALIASES) for alias in aliases):
                    return {"status": "INVALID", "reason": f"entry {i}: alias outside A/B/C"}
        if len(set(present)) != len(present) or set(present) != set(CANONICAL_REVIEW_QUERIES):
            return {"status": "INVALID", "reason": "queries missing, duplicated, or outside canonical 10"}
        return {"status": LABELED, "description": "10 queries labeled by human review"}
    return {"status": "INVALID", "reason": f"unknown status: {status!r}"}


def validate_result_schema(result: dict[str, Any]) -> None:
    if not isinstance(result, dict) or not isinstance(result.get("status"), str):
        raise ValueError("INVALID_RESULT_SCHEMA")
    if result["status"] not in {
        AWAITING_HUMAN_REVIEW, HUMAN_REVIEW_READY,
        "METADATA_SELECTOR_VALIDATED", "METADATA_SELECTOR_NOT_USEFUL",
        "METADATA_SELECTION_EVIDENCE_INSUFFICIENT",
    }:
        raise ValueError("INVALID_RESULT_STATUS")
    if not isinstance(result.get("sourceArtifactSha256"), str):
        raise ValueError("MISSING_SOURCE_HASH")
    if not isinstance(result.get("reviewManifestSha256"), str):
        raise ValueError("MISSING_REVIEW_MANIFEST_HASH")


def prepare_review_package(output_dir: Path = REVIEW_DIR) -> list[Path]:
    """Create blinded contact sheets from existing local images only.

    Pillow is deliberately imported here rather than at module import, because it
    is presentation tooling and not a Phase A scoring dependency.
    """
    from PIL import Image, ImageDraw, ImageFont  # lazy optional presentation dependency

    manifest = load_manifest()
    output_dir.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default()
    generated: list[Path] = []
    for entry in manifest["queries"]:
        tiles: list[Image.Image] = []
        for candidate in entry["candidates"]:
            with Image.open(ROOT / candidate["sourceImagePath"]) as image:
                image = image.convert("RGB")
                image.thumbnail((360, 520))
                tile = Image.new("RGB", (380, 570), "white")
                tile.paste(image, ((380 - image.width) // 2, 45))
                ImageDraw.Draw(tile).text((12, 12), f"[{candidate['alias']}]", fill="black", font=font)
                tiles.append(tile)
        canvas = Image.new("RGB", (1140, 630), "white")
        ImageDraw.Draw(canvas).text((16, 12), entry["queryUsed"], fill="black", font=font)
        for index, tile in enumerate(tiles):
            canvas.paste(tile, (index * 380, 45))
        output = output_dir / f"review-{hashlib.sha256(entry['queryUsed'].encode()).hexdigest()[:12]}.jpg"
        canvas.save(output, quality=90)
        generated.append(output)
    return generated


def manifest_hash() -> str:
    """Return SHA-256 hex digest of the reviewed manifest bytes."""
    return hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()


def human_preferences_hash(path: Path | str = PREFERENCES_PATH) -> str:
    """Return SHA-256 of the sealed preference fixture without parsing its choices."""
    preference_path = Path(path)
    if not preference_path.is_absolute():
        preference_path = ROOT / preference_path
    return hashlib.sha256(preference_path.read_bytes()).hexdigest()


def load_labeled_preferences(path: Path | str = PREFERENCES_PATH) -> list[dict[str, Any]]:
    """Load only a fixture that has passed the frozen LABELED contract."""
    if preferences_status(path) != HUMAN_REVIEW_READY:
        raise ValueError("HUMAN_REVIEW_NOT_READY")
    preference_path = Path(path)
    if not preference_path.is_absolute():
        preference_path = ROOT / preference_path
    preferences = load_json(preference_path).get("preferences")
    if not isinstance(preferences, list):  # validate_preferences already proves this.
        raise ValueError("INVALID_PREFERENCES")
    return preferences


def _manifest_aliases(manifest: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Map the frozen aliases to candidate IDs; filenames never participate."""
    return {
        entry["queryUsed"]: {candidate["alias"]: candidate["candidateId"] for candidate in entry["candidates"]}
        for entry in manifest["queries"]
    }


def _review_topics() -> dict[str, tuple[str, ...]]:
    sample = load_json(REVIEW_SOURCE)["sample"]
    return {
        item["query"]: tuple(item.get("topics", []))
        for item in sample
        if isinstance(item, dict) and isinstance(item.get("query"), str)
    }


def evaluate_against_preferences(
    *,
    strategy: str,
    scored_candidates: dict[str, list[dict[str, Any]]],
    manifest: dict[str, Any],
    preferences: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate already-scored candidates against sealed human preferences.

    This is intentionally separate from ``score_candidates``: it maps aliases
    only through the frozen manifest and cannot change selector scores or order.
    Human accuracy uses the raw Pexels top-3 review window; top-15 remains a
    score/order diagnostic in the persisted per-query result.
    """
    aliases_by_query = _manifest_aliases(manifest)
    preferences_by_query = {entry["queryUsed"]: entry for entry in preferences}
    if set(scored_candidates) != set(aliases_by_query) or set(preferences_by_query) != set(aliases_by_query):
        raise ValueError("EVALUATION_QUERY_SET_MISMATCH")

    query_results: list[dict[str, Any]] = []
    top1_successes = 0
    usable_count = 0
    pairwise_accuracies: list[float] = []
    preferred_ranks: list[int] = []
    beneficial = harmful = unchanged = selector_ties = all_unusable = unknown = 0

    for query in CANONICAL_REVIEW_QUERIES:
        ordered = scored_candidates[query]
        alias_by_id = {candidate_id: alias for alias, candidate_id in aliases_by_query[query].items()}
        preference = preferences_by_query[query]
        preferred_aliases = preference["preferredAliases"]
        preferred_ids = {aliases_by_query[query][alias] for alias in preferred_aliases}
        all_unusable_query = preference["allUnusable"] is True
        raw_window = sorted(
            (item for item in ordered if item["pexelsQueryRank"] <= 3),
            key=lambda item: item["selectorRank"],
        )
        raw_window = [
            {**item, "reviewWindowRank": rank}
            for rank, item in enumerate(raw_window, start=1)
        ]
        raw_top1 = next(item for item in ordered if item["pexelsQueryRank"] == 1)
        selected = raw_window[0]
        top1_preferred: bool | None = None
        pairwise_accuracy: float | None = None
        best_preferred_rank: int | None = None
        selector_tie = False

        if all_unusable_query:
            all_unusable += 1
        else:
            usable_count += 1
            top1_preferred = selected["candidateId"] in preferred_ids
            top1_successes += int(top1_preferred)
            best_preferred_rank = min(
                item["reviewWindowRank"] for item in raw_window if item["candidateId"] in preferred_ids
            )
            preferred_ranks.append(best_preferred_rank)
            non_preferred = [item for item in raw_window if item["candidateId"] not in preferred_ids]
            if non_preferred:
                correct = sum(
                    preferred["reviewWindowRank"] < non_preferred_candidate["reviewWindowRank"]
                    for preferred in raw_window if preferred["candidateId"] in preferred_ids
                    for non_preferred_candidate in non_preferred
                )
                pairwise_accuracy = correct / (len(preferred_ids) * len(non_preferred))
                pairwise_accuracies.append(pairwise_accuracy)
            if strategy != RAW and len(raw_window) > 1:
                selector_tie = raw_window[0]["selectorScore"] == raw_window[1]["selectorScore"]
                selector_ties += int(selector_tie)
            raw_preferred = raw_top1["candidateId"] in preferred_ids
            beneficial += int(not raw_preferred and top1_preferred)
            harmful += int(raw_preferred and not top1_preferred)

        unchanged += int(selected["candidateId"] == raw_top1["candidateId"])
        query_results.append({
            "queryUsed": query,
            "topics": list(_review_topics()[query]),
            "candidateIds": [item["candidateId"] for item in ordered],
            "candidates": [
                {
                    "candidateId": item["candidateId"],
                    "alias": alias_by_id.get(item["candidateId"]),
                    "pexelsQueryRank": item["pexelsQueryRank"],
                    "selectorScore": item["selectorScore"],
                    "selectorRank": item["selectorRank"],
                    "reviewWindowRank": next(
                        window_item["reviewWindowRank"]
                        for window_item in raw_window
                        if window_item["candidateId"] == item["candidateId"]
                    ) if item["pexelsQueryRank"] <= 3 else None,
                }
                for item in ordered
            ],
            "preferredAliases": preferred_aliases,
            "preferredCandidateIds": sorted(preferred_ids),
            "allUnusable": all_unusable_query,
            "top1Preferred": top1_preferred,
            "pairwiseAccuracy": pairwise_accuracy,
            "bestPreferredSelectorRank": best_preferred_rank,
            "selectorTie": selector_tie,
        })

    playstation = next(row for row in query_results if row["queryUsed"] == "PlayStation Nintendo 64 comparison photograph")
    ranks = {candidate["pexelsQueryRank"]: candidate["reviewWindowRank"] for candidate in playstation["candidates"]}
    return {
        "strategy": strategy,
        "metrics": {
            "top1PreferredRate": top1_successes / usable_count if usable_count else None,
            "macroPairwiseAccuracy": sum(pairwise_accuracies) / len(pairwise_accuracies) if pairwise_accuracies else None,
            "meanPreferredRank": sum(preferred_ranks) / len(preferred_ranks) if preferred_ranks else None,
            "beneficialReorders": beneficial,
            "harmfulReorders": harmful,
            "unchanged": unchanged,
            "selectorTie": selector_ties if strategy != RAW else 0,
            "allUnusable": all_unusable,
            "unknown": unknown,
            "playstationRank3BeforeRank1": ranks[3] < ranks[1],
            "preferredCandidateGateSurvival": "NOT_COMPUTED",
        },
        "queries": query_results,
    }


def evidence_sufficiency(preferences: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply the frozen label, discriminating-query, and topic sufficiency gate."""
    topics = _review_topics()
    discriminating = [
        entry for entry in preferences
        if not entry["allUnusable"] and set(entry["preferredAliases"]) != set(ALIASES)
    ]
    topic_count = len({topic for entry in preferences for topic in topics[entry["queryUsed"]]})
    return {
        "labeledQueries": len(preferences),
        "discriminatingQueries": len(discriminating),
        "topicCount": topic_count,
        "sufficient": len(preferences) == 10 and len(discriminating) >= 8 and topic_count >= 5,
    }


def determine_phase_a_verdict(
    strategy_results: dict[str, dict[str, Any]],
    sufficiency: dict[str, Any],
) -> tuple[str, str | None, bool]:
    """Apply the frozen verdict criteria without changing any selector output."""
    if not sufficiency["sufficient"]:
        return "METADATA_SELECTION_EVIDENCE_INSUFFICIENT", None, False
    raw = strategy_results[RAW]["metrics"]

    def passes(strategy: str) -> bool:
        metrics = strategy_results[strategy]["metrics"]
        return (
            metrics["playstationRank3BeforeRank1"]
            and metrics["top1PreferredRate"] >= raw["top1PreferredRate"] + 0.20
            and metrics["macroPairwiseAccuracy"] >= raw["macroPairwiseAccuracy"] + 0.10
            and metrics["beneficialReorders"] >= 2
            and metrics["harmfulReorders"] <= 1
        )

    passing = [strategy for strategy in (LEXICAL_RECALL, BM25) if passes(strategy)]
    if passing:
        return "METADATA_SELECTOR_VALIDATED", LEXICAL_RECALL if LEXICAL_RECALL in passing else BM25, False
    improved_both = [
        strategy for strategy in (LEXICAL_RECALL, BM25)
        if strategy_results[strategy]["metrics"]["top1PreferredRate"] > raw["top1PreferredRate"]
        and strategy_results[strategy]["metrics"]["macroPairwiseAccuracy"] > raw["macroPairwiseAccuracy"]
    ]
    if (
        not improved_both
        or any(
            strategy_results[strategy]["metrics"]["harmfulReorders"]
            > strategy_results[strategy]["metrics"]["beneficialReorders"]
            for strategy in (LEXICAL_RECALL, BM25)
        )
        or (
            not strategy_results[LEXICAL_RECALL]["metrics"]["playstationRank3BeforeRank1"]
            and not strategy_results[BM25]["metrics"]["playstationRank3BeforeRank1"]
            and not improved_both
        )
    ):
        return "METADATA_SELECTOR_NOT_USEFUL", None, True
    return "METADATA_SELECTION_EVIDENCE_INSUFFICIENT", None, False


def evaluate_phase_a() -> dict[str, Any]:
    """Run the frozen offline Phase A and write no production state."""
    if preferences_status() != HUMAN_REVIEW_READY:
        raise ValueError("HUMAN_REVIEW_NOT_READY")
    manifest = load_manifest()
    preferences = load_labeled_preferences()
    scored = {
        strategy: {
            query: score_candidates(strategy, query, load_photo_candidates(query, limit=15))
            for query in CANONICAL_REVIEW_QUERIES
        }
        for strategy in (RAW, LEXICAL_RECALL, BM25)
    }
    strategy_results = {
        strategy: evaluate_against_preferences(
            strategy=strategy,
            scored_candidates=scored[strategy],
            manifest=manifest,
            preferences=preferences,
        )
        for strategy in (RAW, LEXICAL_RECALL, BM25)
    }
    sufficiency = evidence_sufficiency(preferences)
    verdict, selected_strategy, phase_b_required = determine_phase_a_verdict(strategy_results, sufficiency)
    return {
        "schemaVersion": 1,
        "status": verdict,
        "selectedStrategy": selected_strategy,
        "sourceArtifactSha256": source_hash(),
        "reviewManifestSha256": manifest_hash(),
        "humanPreferencesSha256": human_preferences_hash(),
        "evidenceSufficiency": sufficiency,
        "strategyResults": strategy_results,
        "playstationHistoricalEvidence": {"rawRank3BetterThanRawRank1": True},
        "diagnostics": {"preferredCandidateGateSurvival": "NOT_COMPUTED"},
        "phaseBRequired": phase_b_required,
    }


def write_phase_a_result(result: dict[str, Any], path: Path = PHASE_A_RESULT_PATH) -> None:
    """Persist the ignored evaluation artifact only after all offline evaluation succeeds."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare offline blinded Pexels Photo review material")
    parser.add_argument("action", choices=("prepare-review", "status", "evaluate-phase-a"))
    args = parser.parse_args(argv)
    if args.action == "prepare-review":
        generated = prepare_review_package()
        print(f"prepared {len(generated)} blinded review sheets in {REVIEW_DIR}")
    elif args.action == "status":
        result = {
            "status": preferences_status(),
            "sourceArtifactSha256": source_hash(),
            "reviewManifestSha256": manifest_hash(),
        }
        validate_result_schema(result)
        print(json.dumps(result, sort_keys=True))
    else:
        result = evaluate_phase_a()
        validate_result_schema(result)
        write_phase_a_result(result)
        summary = {
            "status": result["status"],
            "selectedStrategy": result["selectedStrategy"],
            "phaseBRequired": result["phaseBRequired"],
            "evidenceSufficiency": result["evidenceSufficiency"],
        }
        print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
