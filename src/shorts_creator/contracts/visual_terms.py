"""Shared pure lexical vocabulary for visual query/semantic processing.

Owns the neutral token primitives used by the semantic candidate scorer
(``assets/semantic.py``) and by the upstream visual-query specificity guard
(``contracts/visual_specificity.py``).  Single source of truth so both layers
agree on which tokens carry discriminative evidence.

Pure module: no I/O, no HTTP, no provider calls, no pipeline imports.

``GENERIC_FILLER`` and ``WEAK_SUPPORT_TERMS`` are the historical semantic
vocabulary moved from ``assets/semantic.py`` without changing their values.
``STOPWORDS`` is guard-only (determiners/prepositions/conjunctions): it is used
exclusively by specificity validation and never by the semantic scorer.
"""

from __future__ import annotations

import re
from typing import Any

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

# Guard-only stopwords: function words that carry no topical evidence but are
# not filler/media tokens.  Used by the specificity guard so prepositions,
# determiners and conjunctions can never inflate the anchor count of a vague
# query.  Deliberately NOT used by the semantic scorer.
STOPWORDS: frozenset[str] = frozenset({
    "about", "after", "all", "also", "and", "any", "are", "because", "before",
    "but", "can", "could", "for", "from", "has", "have", "how", "into", "its",
    "may", "more", "most", "not", "of", "off", "onto", "or", "our", "over",
    "per", "than", "that", "the", "their", "then", "these", "they", "this",
    "those", "through", "under", "upon", "very", "was", "were", "what", "when",
    "where", "which", "while", "who", "why", "will", "with", "would", "you",
    "your",
})

_TOKEN_RE = re.compile(r"[a-z0-9]+")


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