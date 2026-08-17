"""Semantic relevance for visual asset candidates — provider-agnostic, deterministic.

Normalizes provider-native candidate metadata into a generic semantic contract and
scores it against the primary visual intent (``queryUsed``).

Pure module: no I/O, no HTTP, no CLIP/embeddings/LLM.  Stdlib only.

Scorer MUST NOT contain provider-specific branches.  Provider adapters in
``PROVIDER_ADAPTERS`` map native metadata into the generic contract.
"""

from __future__ import annotations

import re
from typing import Any

RELEVANT = "RELEVANT"
IRRELEVANT = "IRRELEVANT"
UNSCORABLE = "UNSCORABLE"

SEMANTIC_METHOD = "deterministic_anchor_coverage_v2"

# Generic media/stock filler tokens that carry no topical evidence.
GENERIC_FILLER: frozenset[str] = frozenset({
    "image", "images", "photo", "photos", "photograph", "photographs",
    "picture", "pictures", "illustration", "illustrations", "drawing",
    "drawings", "graphic", "graphics", "clipart", "stock", "digital",
    "free", "download", "downloads", "resolution", "wallpaper", "wallpapers",
    "background", "backgrounds", "jpeg", "jpg", "png", "webp", "gif",
    "high", "quality", "file", "files", "view", "views", "icon", "icons",
})

# Broad temporal, popularity, presentation, and platform-context terms can
# describe many unrelated assets. They remain visible in diagnostics but can
# never establish relevance without a discriminative query anchor.
WEAK_SUPPORT_TERMS: frozenset[str] = frozenset({
    "current", "early", "famous", "first", "formation", "future", "latest", "modern",
    "new", "old", "popular", "viral",
    "culture", "image", "images", "interface", "logo", "media", "photo",
    "photos", "screen", "screenshot", "screenshots", "section", "social",
    "video", "videos",
})

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Default semantic contract keys (generic).  ``other`` holds provider adapter output.
CONTRACT_KEYS: tuple[str, ...] = (
    "provider", "queryUsed", "title", "description", "tags", "labels", "assetType",
)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _adapter_generic(candidate: dict) -> dict:
    """Map generic semantic fields when present (no provider-specific logic)."""
    tags = _as_list(candidate.get("tags"))
    labels = _as_list(
        candidate.get("labels") or candidate.get("keywords") or candidate.get("categories")
    )
    asset_type = (
        candidate.get("assetType")
        or candidate.get("imageType")
        or candidate.get("mimeType")
        or ""
    )
    return {
        "provider": str(candidate.get("provider") or ""),
        "queryUsed": str(candidate.get("queryUsed") or ""),
        "title": str(candidate.get("title") or ""),
        "description": str(
            candidate.get("description") or candidate.get("caption") or ""
        ),
        "tags": tags,
        "labels": labels,
        "assetType": str(asset_type or ""),
    }


def _adapter_wikimedia(candidate: dict) -> dict:
    """Wikimedia native mapping: title is the ImageDescription, labels come from the file name."""
    sem = _adapter_generic(candidate)
    file_name = str(candidate.get("fileUrl") or candidate.get("sourceUrl") or "")
    stem = file_name.rsplit("/", 1)[-1]
    stem = stem.split("?")[0]
    stem = stem.rsplit(".", 1)[0] if "." in stem else stem
    stem = stem.replace("_", " ").replace("-", " ")
    extra = [t for t in stem.split() if t.strip()]
    combined = list(sem["labels"]) + [t for t in extra if t not in sem["labels"]]
    sem["labels"] = combined[:20]
    return sem


def _adapter_pixabay(candidate: dict) -> dict:
    """Pixabay native mapping: tags is a comma-separated label string."""
    sem = _adapter_generic(candidate)
    tags = _as_list(candidate.get("tags"))
    combined = list(tags) + [t for t in sem["labels"] if t not in tags]
    sem["tags"] = combined[:40]
    return sem


# Provider adapters map native metadata into the generic semantic contract.
# The scorer never branches on provider identity.
PROVIDER_ADAPTERS: dict[str, Any] = {
    "wikimedia_commons": _adapter_wikimedia,
    "wikimedia": _adapter_wikimedia,
    "pixabay": _adapter_pixabay,
}


def to_semantic_candidate(candidate: dict) -> dict:
    """Normalize a provider-native candidate dict into the generic semantic contract."""
    if not isinstance(candidate, dict):
        return {k: "" if k in ("provider", "queryUsed", "title", "description", "assetType") else [] for k in CONTRACT_KEYS}
    provider = str(candidate.get("provider") or "").lower()
    adapter = PROVIDER_ADAPTERS.get(provider, _adapter_generic)
    sem = adapter(candidate)
    return {k: sem.get(k, "" if k in ("provider", "queryUsed", "title", "description", "assetType") else []) for k in CONTRACT_KEYS}


def tokenize(text: Any) -> set[str]:
    """Lowercase alphanumeric token set from a string or list of strings."""
    tokens: set[str] = set()
    if isinstance(text, str):
        strings = [text]
    elif isinstance(text, (list, tuple)):
        strings = [str(s) for s in text]
    else:
        return tokens
    for s in strings:
        for tok in _TOKEN_RE.findall(str(s).lower()):
            if len(tok) >= 3 and tok not in GENERIC_FILLER:
                tokens.add(tok)
    return tokens


def _evidence_tokens(semantic: dict) -> set[str]:
    """Topic-evidence tokens from candidate metadata (title/description/tags/labels)."""
    return tokenize(
        [semantic.get("title", ""), semantic.get("description", "")]
    ) | tokenize(semantic.get("tags", [])) | tokenize(semantic.get("labels", []))


def _query_anchor_terms(query: str) -> tuple[set[str], set[str]]:
    """Split primary query evidence into discriminative anchors and weak terms."""
    query_terms = tokenize(query)
    return query_terms - WEAK_SUPPORT_TERMS, query_terms & WEAK_SUPPORT_TERMS


def _anchor_match_requirement(anchor_count: int) -> int:
    """Require one focused anchor or at least half of a multi-anchor query."""
    if anchor_count == 1:
        return 1
    return max(2, (anchor_count + 1) // 2)


def _assessment(
    *,
    verdict: str,
    score: int | None,
    reasons: list[str],
    anchor_terms: set[str],
    matched_anchors: set[str],
    weak_matches: set[str],
) -> dict:
    anchor_coverage = (
        len(matched_anchors) / len(anchor_terms) if anchor_terms else None
    )
    return {
        "verdict": verdict,
        "score": score,
        "reasons": reasons,
        # Only discriminative anchor matches establish semantic relevance.
        "matchedEvidence": sorted(matched_anchors),
        "anchorTerms": sorted(anchor_terms),
        "matchedAnchors": sorted(matched_anchors),
        "weakMatches": sorted(weak_matches),
        "anchorCoverage": anchor_coverage,
        "method": SEMANTIC_METHOD,
    }


def score_semantic_relevance(expected: dict, candidate: dict) -> dict:
    """Score a candidate's semantic metadata against expected visual intent.

    Args:
        expected: ``{"query": str, "subjects": list[str]}``.
        candidate: normalized generic semantic contract from
            ``to_semantic_candidate``.

    Returns:
        ``{"verdict", "score", "reasons", "matchedEvidence", "method"}``
        plus anchor diagnostics.
        - ``RELEVANT``: sufficient discriminative query-anchor coverage.
        - ``IRRELEVANT``: candidate lacks enough discriminative query anchors.
        - ``UNSCORABLE``: no substantive candidate evidence or query anchors.

    ``queryUsed`` is the primary intent. Subject tokens are intentionally not
    considered for the relevance verdict: they may describe a scene, but must
    never rescue a candidate that misses the primary query anchors.
    """
    evidence = _evidence_tokens(candidate)
    anchor_terms, weak_terms = _query_anchor_terms(expected.get("query", ""))
    matched_anchors = evidence & anchor_terms
    weak_matches = evidence & weak_terms

    if not evidence:
        return _assessment(
            verdict=UNSCORABLE,
            score=None,
            reasons=["no substantive candidate semantic metadata to compare"],
            anchor_terms=anchor_terms,
            matched_anchors=matched_anchors,
            weak_matches=weak_matches,
        )
    if not anchor_terms:
        return _assessment(
            verdict=UNSCORABLE,
            score=None,
            reasons=["no discriminative query anchors to compare"],
            anchor_terms=anchor_terms,
            matched_anchors=matched_anchors,
            weak_matches=weak_matches,
        )

    required = _anchor_match_requirement(len(anchor_terms))
    if len(matched_anchors) < required:
        return _assessment(
            verdict=IRRELEVANT,
            score=0,
            reasons=[
                "candidate lacks sufficient discriminative query-anchor coverage; "
                "weak/support matches cannot establish relevance"
            ],
            anchor_terms=anchor_terms,
            matched_anchors=matched_anchors,
            weak_matches=weak_matches,
        )

    anchor_coverage = len(matched_anchors) / len(anchor_terms)
    score = 60 + min(40, round(40 * anchor_coverage))
    return _assessment(
        verdict=RELEVANT,
        score=score,
        reasons=["candidate satisfies discriminative query-anchor coverage"],
        anchor_terms=anchor_terms,
        matched_anchors=matched_anchors,
        weak_matches=weak_matches,
    )


def assess_candidate(expected: dict, native_candidate: dict) -> dict:
    """One-shot: normalize a native candidate and score it against expected intent."""
    return score_semantic_relevance(expected, to_semantic_candidate(native_candidate))
