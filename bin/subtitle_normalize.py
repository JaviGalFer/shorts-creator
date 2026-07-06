"""Shared subtitle text normalization for coverage validation.

Provides a single normalization function used by all subtitle validators
to ensure consistent comparison between Edge WordBoundary cue text and
canonical narration text.
"""

import re
import unicodedata


def normalize_subtitle_text(text: str) -> str:
    """Normalize subtitle/cue text for comparison.

    Rules:
    - lowercase
    - trim and collapse whitespace
    - punctuation-insensitive (strip all non-word characters)
    - accent-insensitive (NFKD decompose + remove combining marks)
    - normalize inverted Spanish punctuation
    - preserve meaningful words (alphanumeric sequences)
    """
    if not text:
        return ""
    if not isinstance(text, str):
        return ""

    # Normalize unicode: decompose accented characters
    text = unicodedata.normalize("NFKD", text)

    # Remove combining diacritical marks (accents)
    text = "".join(c for c in text if not unicodedata.combining(c))

    # Lowercase
    text = text.lower()

    # Remove all punctuation: keep only word chars and whitespace
    text = re.sub(r"[^\w\s]", " ", text)

    # Collapse and trim whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def normalize_subtitle_tokens(text: str) -> list[str]:
    """Split normalized text into meaningful tokens."""
    norm = normalize_subtitle_text(text)
    return [w for w in norm.split() if len(w) > 0]


def cue_text_matches_narration(
    cue_text: str,
    narration_text: str,
    threshold: float = 0.95,
) -> tuple[bool, list[str], list[str]]:
    """Check whether cue text matches narration text under normalization.

    Returns (matches, missing_tokens, extra_tokens).

    - missing_tokens: normalized tokens in narration but absent from cue
    - extra_tokens: normalized tokens in cue but absent from narration
    """
    cue_norm = normalize_subtitle_text(cue_text)
    nar_norm = normalize_subtitle_text(narration_text)

    # Fast path: normalized strings match exactly
    if cue_norm == nar_norm:
        return True, [], []

    cue_tokens = normalize_subtitle_tokens(cue_text)
    nar_tokens = normalize_subtitle_tokens(narration_text)

    cue_set = set(cue_tokens)
    nar_set = set(nar_tokens)

    missing = sorted(t for t in nar_tokens if t not in cue_set)
    extra = sorted(t for t in cue_tokens if t not in nar_set)

    if not missing and not extra:
        return True, [], []

    # Only punctuation/whitespace artifacts: all missing/extra tokens
    # are very short (<=2 chars) or purely numeric punctuation artifacts.
    meaningful_missing = [t for t in missing if len(t) > 2 or t.isalpha()]
    meaningful_extra = [t for t in extra if len(t) > 2 or t.isalpha()]

    if not meaningful_missing and not meaningful_extra:
        return True, [], []

    # Calculate token overlap ratio for threshold check
    if nar_tokens:
        overlap = len(nar_set & cue_set) / len(nar_set)
        if overlap >= threshold:
            return True, meaningful_missing, meaningful_extra

    return False, meaningful_missing, meaningful_extra


def compare_cue_vs_narration_bulk(
    cue_texts: list[str],
    narration_texts: list[str],
) -> dict:
    """Compare concatenated cue texts vs concatenated narration texts.

    Returns a result dict compatible with coverage validation.
    """
    all_cue = " ".join(cue_texts)
    all_nar = " ".join(narration_texts)

    matches, missing, extra = cue_text_matches_narration(all_cue, all_nar)

    result = {
        "status": "PASS" if matches else "FAIL",
    }

    if missing:
        result["missingTokens"] = missing
    if extra:
        result["extraTokens"] = extra
    if not matches:
        result["error"] = "Cue text does not match narration text"

    return result
