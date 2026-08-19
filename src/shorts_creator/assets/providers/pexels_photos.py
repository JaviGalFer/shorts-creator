"""Pexels Photos page-1 candidate mapping and provisional ordering."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
import math
import re
import unicodedata
from typing import Any, Iterable, Mapping

from shorts_creator.assets.candidates import CandidateAttribution, CandidateEnvelope, CandidateSemanticMetadata, RAW
from shorts_creator.assets.providers.pexels import (
    MALFORMED_RESPONSE,
    PexelsClientError,
    PexelsJsonResponse,
    get_json,
    resolve_pexels_api_key,
)
from shorts_creator.contracts.visual_media import IMAGE
from shorts_creator.contracts.visual_terms import GENERIC_FILLER, STOPWORDS

PEXELS_PHOTOS_SEARCH_PATH = "/v1/search"
PEXELS_PHOTOS_PARAMS: Mapping[str, str | int] = {
    "orientation": "portrait", "locale": "en-US", "page": 1, "per_page": 15,
}
PROVISIONAL_BM25 = "PROVISIONAL_BM25"
BM25_K1 = 1.2
BM25_B = 0.75
NO_RESULTS = "NO_RESULTS"

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class PexelsPhotoCandidate:
    """Provider-specific provenance that wraps the generic lifecycle envelope."""

    envelope: CandidateEnvelope
    pexels_photo_id: str
    pexels_photo_url: str
    pexels_query_rank: int
    selector_identity: str | None = None
    selector_score: float | None = None
    photographer_id: str | None = None


@dataclass(frozen=True)
class PexelsPhotoSearchResult:
    status: str
    candidates: tuple[PexelsPhotoCandidate, ...]
    telemetry: Mapping[str, str]


def normalized_bm25_tokens(text: str | None) -> frozenset[str]:
    """Return the frozen A2 token set without importing benchmark code."""
    normalized = unicodedata.normalize("NFKC", text or "").casefold()
    return frozenset(
        token for token in _TOKEN_RE.findall(normalized)
        if token not in STOPWORDS and token not in GENERIC_FILLER
    )


def _bm25_scores(query: str, candidates: Iterable[PexelsPhotoCandidate]) -> dict[str, float]:
    items = list(candidates)
    if not items:
        return {}
    query_tokens = normalized_bm25_tokens(query)
    documents = [normalized_bm25_tokens(candidate.envelope.semantic_metadata.description) for candidate in items]
    lengths = [len(document) for document in documents]
    average_length = sum(lengths) / len(lengths)
    frequencies = Counter(token for document in documents for token in document)
    scores: dict[str, float] = {}
    for candidate, document, length in zip(items, documents, lengths):
        score = 0.0
        for token in query_tokens:
            if token not in document:
                continue
            idf = math.log(1 + (len(items) - frequencies[token] + 0.5) / (frequencies[token] + 0.5))
            denominator = 1 + BM25_K1 * (1 - BM25_B + BM25_B * length / average_length)
            score += idf * (BM25_K1 + 1) / denominator
        scores[candidate.pexels_photo_id] = score
    return scores


def order_candidates_bm25(query_used: str, candidates: Iterable[PexelsPhotoCandidate]) -> tuple[PexelsPhotoCandidate, ...]:
    """Order the raw page-1 candidate stream with the fixed provisional BM25."""
    items = tuple(candidates)
    scores = _bm25_scores(query_used, items)
    ordered = sorted(items, key=lambda item: (-scores[item.pexels_photo_id], item.pexels_query_rank))
    return tuple(
        replace(
            item,
            envelope=replace(item.envelope, provider_rank=rank, provider_score=scores[item.pexels_photo_id]),
            selector_identity=PROVISIONAL_BM25,
            selector_score=scores[item.pexels_photo_id],
        )
        for rank, item in enumerate(ordered, start=1)
    )


def bind_lifecycle_positions(
    candidates: Iterable[PexelsPhotoCandidate],
    *,
    query_index: int,
    provider_rank_start: int,
) -> tuple[PexelsPhotoCandidate, ...]:
    """Bind one already-filtered page to its final lifecycle stream positions."""
    return tuple(
        replace(
            item,
            envelope=replace(
                item.envelope,
                query_index=query_index,
                provider_rank=provider_rank_start + offset,
            ),
        )
        for offset, item in enumerate(candidates, start=1)
    )


def _required_string(photo: Mapping[str, Any], key: str) -> str | None:
    value = photo.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _required_positive_int(photo: Mapping[str, Any], key: str) -> int | None:
    value = photo.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _map_photo(photo: Mapping[str, Any], query_used: str, raw_rank: int) -> PexelsPhotoCandidate | None:
    photo_id = _required_positive_int(photo, "id")
    width = _required_positive_int(photo, "width")
    height = _required_positive_int(photo, "height")
    source_url = _required_string(photo, "url")
    photographer = _required_string(photo, "photographer")
    src = photo.get("src")
    if not isinstance(src, Mapping):
        return None
    acquisition_url = _required_string(src, "original")
    if None in (photo_id, width, height, source_url, photographer, acquisition_url):
        return None
    alt = photo.get("alt") if isinstance(photo.get("alt"), str) else ""
    photographer_url = _required_string(photo, "photographer_url")
    preview_url = _required_string(src, "large2x")
    photographer_id = _required_positive_int(photo, "photographer_id")
    envelope = CandidateEnvelope(
        capability_id="pexels.photos.stock", provider="pexels", provider_asset_id=str(photo_id),
        media_kind=IMAGE, source_type="STOCK", query_used=query_used,
        query_variant=RAW, query_index=0, provider_rank=None, provider_score=None,
        semantic_metadata=CandidateSemanticMetadata(description=alt), source_url=source_url,
        preview_url=preview_url, acquisition_url=acquisition_url, mime_type=None,
        width=width, height=height,
        attribution=CandidateAttribution(author=photographer, author_url=photographer_url),
    )
    return PexelsPhotoCandidate(
        envelope=envelope, pexels_photo_id=str(photo_id), pexels_photo_url=source_url,
        pexels_query_rank=raw_rank,
        photographer_id=str(photographer_id) if photographer_id is not None else None,
    )


def map_photo_response(response: Mapping[str, Any], query_used: str) -> PexelsPhotoSearchResult:
    """Map a Pexels Photos response, skipping malformed individual photos."""
    photos = response.get("photos")
    if not isinstance(photos, list):
        raise PexelsClientError(MALFORMED_RESPONSE, "Pexels Photos response has invalid photos")
    if not photos:
        return PexelsPhotoSearchResult(NO_RESULTS, (), {})
    candidates = tuple(
        candidate
        for raw_rank, photo in enumerate(photos[:15], start=1)
        if isinstance(photo, Mapping)
        for candidate in [_map_photo(photo, query_used, raw_rank)]
        if candidate is not None
    )
    if not candidates:
        raise PexelsClientError(MALFORMED_RESPONSE, "Pexels Photos response has no valid photos")
    return PexelsPhotoSearchResult("OK", candidates, {})


def search_pexels_photos(query_used: str, *, api_key: str | None = None, timeout: int = 30) -> PexelsPhotoSearchResult:
    """Search one raw Pexels Photos page and return its provisional order."""
    response: PexelsJsonResponse = get_json(
        path=PEXELS_PHOTOS_SEARCH_PATH,
        params={"query": query_used, **PEXELS_PHOTOS_PARAMS},
        api_key=api_key if api_key is not None else resolve_pexels_api_key(), timeout=timeout,
    )
    mapped = map_photo_response(response.data, query_used)
    if mapped.status == NO_RESULTS:
        return PexelsPhotoSearchResult(NO_RESULTS, (), response.telemetry)
    return PexelsPhotoSearchResult("OK", order_candidates_bm25(query_used, mapped.candidates), response.telemetry)
