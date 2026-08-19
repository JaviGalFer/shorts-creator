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

RAW = "A0_RAW"
LEXICAL_RECALL = "A1_EXACT_LEXICAL_QUERY_RECALL"
BM25 = "A2_BM25"
STRATEGIES = frozenset({RAW, LEXICAL_RECALL, BM25})
ALIASES = ("A", "B", "C")
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


def preferences_status(path: Path = PREFERENCES_PATH) -> str:
    preferences = load_json(path)
    entries = preferences.get("preferences")
    if preferences.get("status") != "UNLABELED" or not isinstance(entries, list) or len(entries) != 10:
        raise ValueError("INVALID_PREFERENCES_TEMPLATE")
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("preferredAliases") != [] or entry.get("allUnusable") is not None:
            raise ValueError("PREFERENCES_ARE_NOT_UNLABELED")
    return "AWAITING_HUMAN_REVIEW"


def validate_result_schema(result: dict[str, Any]) -> None:
    if not isinstance(result, dict) or not isinstance(result.get("status"), str):
        raise ValueError("INVALID_RESULT_SCHEMA")
    if result["status"] not in {
        "AWAITING_HUMAN_REVIEW", "METADATA_SELECTOR_VALIDATED",
        "METADATA_SELECTOR_NOT_USEFUL", "METADATA_SELECTION_EVIDENCE_INSUFFICIENT",
    }:
        raise ValueError("INVALID_RESULT_STATUS")
    if not isinstance(result.get("sourceArtifactSha256"), str):
        raise ValueError("MISSING_SOURCE_HASH")


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare offline blinded Pexels Photo review material")
    parser.add_argument("action", choices=("prepare-review", "status"))
    args = parser.parse_args(argv)
    if args.action == "prepare-review":
        generated = prepare_review_package()
        print(f"prepared {len(generated)} blinded review sheets in {REVIEW_DIR}")
    else:
        result = {"status": preferences_status(), "sourceArtifactSha256": source_hash()}
        validate_result_schema(result)
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
