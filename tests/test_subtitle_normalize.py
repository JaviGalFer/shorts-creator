"""Tests for subtitle text normalization and cue/narration comparison.

Run: python3 -m pytest tests/test_subtitle_normalize.py -v
"""

import json
import sys
from pathlib import Path

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))

from subtitle_normalize import (
    normalize_subtitle_text,
    normalize_subtitle_tokens,
    cue_text_matches_narration,
    compare_cue_vs_narration_bulk,
)


# ── normalize_subtitle_text ────────────────────────────────────────────

def test_lowercase():
    assert normalize_subtitle_text("El Muro cayó") == "el muro cayo"


def test_collapse_whitespace():
    assert normalize_subtitle_text("  El   Muro  ") == "el muro"


def test_strip_punctuation():
    result = normalize_subtitle_text("El Muro cayó en 1989, un símbolo de libertad.")
    assert "1989" in result
    assert "," not in result
    assert "." not in result


def test_accent_insensitive():
    assert normalize_subtitle_text("Berlín") == "berlin"
    assert normalize_subtitle_text("canción") == "cancion"


def test_inverted_punctuation():
    result = normalize_subtitle_text("¿Qué pasó?")
    assert "que" in result
    assert "paso" in result
    assert "?" not in result
    assert "¿" not in result


def test_numeric_preserved():
    assert "1961" in normalize_subtitle_text("1961, comenzó")
    assert "160" in normalize_subtitle_text("160 kilómetros")


def test_empty_string():
    assert normalize_subtitle_text("") == ""
    assert normalize_subtitle_text(None) == ""


# ── cue_text_matches_narration ─────────────────────────────────────────

def test_punctuation_only_difference():
    """Punctuation/whitespace-only difference should match."""
    canonical = "El Muro cayó en 1989, un símbolo de libertad."
    cue = "El Muro cayó en 1989 un símbolo de libertad"
    matches, missing, extra = cue_text_matches_narration(cue, canonical)
    assert matches, f"Expected PASS, got missing={missing}, extra={extra}"


def test_whitespace_only_difference():
    canonical = "Explora  más sobre  la historia"
    cue = "Explora más sobre la historia"
    matches, missing, extra = cue_text_matches_narration(cue, canonical)
    assert matches, f"Expected PASS, got missing={missing}, extra={extra}"


def test_accent_difference():
    """Accent difference should match."""
    canonical = "Berlín quedó marcada"
    cue = "Berlin quedo marcada"
    matches, missing, extra = cue_text_matches_narration(cue, canonical)
    assert matches, f"Expected PASS, got missing={missing}, extra={extra}"


def test_wrong_meaningful_token():
    """Wrong meaningful word should FAIL."""
    canonical = "separaron familias y amigos"
    cue = "separaron familias y soldados"
    matches, missing, extra = cue_text_matches_narration(cue, canonical)
    assert not matches, "Expected FAIL for wrong meaningful token"
    assert "soldados" in extra, f"soldados should be in extra tokens: {extra}"
    assert "amigos" in missing, f"amigos should be in missing tokens: {missing}"


def test_missing_meaningful_token():
    canonical = "un símbolo de libertad y esperanza"
    cue = "un símbolo de libertad"
    matches, missing, extra = cue_text_matches_narration(cue, canonical)
    assert not matches, "Expected FAIL for missing meaningful token"
    assert "esperanza" in missing, f"esperanza should be missing: {missing}"


def test_comma_after_year():
    """The exact v9 issue: '1961, comenzó' vs '1961 comenzó' (comma only)."""
    canonical = "1961, comenzó"
    cue = "1961 comenzó"
    matches, missing, extra = cue_text_matches_narration(cue, canonical)
    assert matches, f"Expected PASS for comma-after-year, got missing={missing}, extra={extra}"


def test_v9_full_narration():
    """Full v9 narration concatenated vs all cues concatenated."""
    narration = (
        "En 1961, Berlín, dividida entre Oriente y Occidente, quedó marcada. "
        "El 13 de agosto de 1961, comenzó la construcción del Muro. "
        "Casi 160 kilómetros de muro separaron familias y amigos. "
        "El Muro cayó en 1989, un símbolo de libertad. "
        "Explora más sobre la historia del Muro y su legado, síguenos."
    )
    cues = (
        "En 1961, Berlín, dividida entre Oriente y "
        "Occidente, quedó marcada. "
        "El 13 de agosto de "
        "1961 comenzó la construcción del Muro. "
        "Casi 160 kilómetros de muro separaron familias y amigos. "
        "El Muro cayó en 1989, "
        "un símbolo de libertad. "
        "Explora más sobre la historia del Muro "
        "y su legado, síguenos."
    )
    matches, missing, extra = cue_text_matches_narration(cues, narration)
    assert matches, f"Expected PASS for v9 full, got missing={missing}, extra={extra}"


# ── compare_cue_vs_narration_bulk ──────────────────────────────────────

def test_bulk_comparison_pass():
    result = compare_cue_vs_narration_bulk(
        ["Hola mundo", "Esto es una prueba"],
        ["Hola mundo", "Esto es una prueba"],
    )
    assert result["status"] == "PASS"


def test_bulk_comparison_fail():
    result = compare_cue_vs_narration_bulk(
        ["Hola mundo"],
        ["Hola universo"],
    )
    assert result["status"] == "FAIL"


def test_bulk_v9_coverage_text():
    """Replicate v9 cue text validation with the fixed normalize."""
    cue_texts = [
        "En 1961, Berlín, dividida entre Oriente y",
        "Occidente, quedó marcada.",
        "El 13 de agosto de",
        "1961 comenzó la construcción del Muro.",
        "Casi 160 kilómetros de muro separaron familias y amigos.",
        "El Muro cayó en 1989,",
        "un símbolo de libertad.",
        "Explora más sobre la historia del Muro",
        "y su legado, síguenos.",
    ]
    nar_texts = [
        "En 1961, Berlín, dividida entre Oriente y Occidente, quedó marcada.",
        "El 13 de agosto de 1961, comenzó la construcción del Muro.",
        "Casi 160 kilómetros de muro separaron familias y amigos.",
        "El Muro cayó en 1989, un símbolo de libertad.",
        "Explora más sobre la historia del Muro y su legado, síguenos.",
    ]
    result = compare_cue_vs_narration_bulk(cue_texts, nar_texts)
    assert result["status"] == "PASS", f"Expected PASS for v9, got {result}"
