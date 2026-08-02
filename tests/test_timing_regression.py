"""Regression tests for subtitle timing edge cases (hermetic).

These tests validate the pure subtitle-timing pipeline from
`bin/generate_audio.py` (canonical token matching + cue grouping) using
deterministic synthetic WordBoundary events. They do NOT invoke Edge TTS,
run any subprocess, open sockets, use Docker, write under `data/`, or depend
on a `.venv` or a persisted reference job.

Original integration tests exercised Edge TTS via subprocess (a real network
service) and were blocked by the suite-wide hermeticity policy (C5). Their
semantic invariants are preserved here against the pure functions.

Fixtures (semantics preserved from the original regression suite):
- sentence_boundary_crossing: no words leak across sentence boundaries
- punctuation_restoration: trailing commas/periods recovered from canonical text
- no_cross_scene_leakage: cues respect scene window boundaries
- no_single_word_by_boundary: no single-word cue created solely by boundary handling

Run: python3 -m pytest tests/test_timing_regression.py -v
"""

import importlib
import re
import socket
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT = Path("/home/javi/projects/shorts-creator")
BIN_DIR = PROJECT / "bin"

# Import the pure timing functions from the production module. Importing the
# module is side-effect free: `edge_tts` is imported lazily inside provider
# methods, not at module load.
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))

_ga = importlib.import_module("generate_audio")

split_sentences = _ga.split_sentences
build_full_narration = _ga.build_full_narration
_build_canonical_tokens = _ga._build_canonical_tokens
_match_words_to_canonical = _ga._match_words_to_canonical
group_words_into_cues = _ga.group_words_into_cues
_strip_punct = _ga._strip_punct

SENTENCE_BOUNDARY_TEXT = (
    "Primera oración. Segunda oración. Tercera oración."
)

CROSS_SCENE_TEXT = (
    "Escena uno termina aquí. "
    "Escena dos comienza aquí."
)

# Deterministic scenes mirroring the original metadata fixtures, but synthetic
# (no reference to any persisted job under data/videos/).
SCENES = [
    {"sceneNumber": 1, "voiceover": SENTENCE_BOUNDARY_TEXT},
    {"sceneNumber": 2, "voiceover": CROSS_SCENE_TEXT},
]

# Fixed word cadence (seconds) for synthetic WordBoundary events.
WORD_DURATION = 0.5


def _build_cues():
    """Run the pure timing pipeline and return cues grouped by scene number.

    Mimics the continuous-mode path in `generate_audio.py`:
    build_full_narration -> _build_canonical_tokens -> _match_words_to_canonical
    -> group_words_into_cues.
    """
    _, narration_units = build_full_narration(SCENES)
    canonical_tokens = _build_canonical_tokens(narration_units)

    # Synthetic WordBoundary events: one per canonical token, with deterministic
    # offsets/durations. Edge emits words without trailing punctuation; the
    # canonical token carries the punctuation that must be restored.
    words = []
    t = 0.0
    for ct in canonical_tokens:
        words.append({
            "startSec": round(t, 3),
            "endSec": round(t + WORD_DURATION, 3),
            "text": _strip_punct(ct["text"]),
        })
        t += WORD_DURATION

    annotated, metrics = _match_words_to_canonical(words, canonical_tokens)
    assert metrics["unmatchedRatio"] <= 0.10, (
        f"canonical matching degraded: {metrics['unmatchedEdgeWords']}"
    )
    cues = group_words_into_cues(annotated)

    by_scene = {}
    for cue in cues:
        by_scene.setdefault(cue.get("sceneNumber"), []).append(cue)
    return by_scene


def _cues_by_scene():
    return _build_cues()


@pytest.fixture()
def hermetic_guard(monkeypatch):
    """Guarantee the suite never reaches external effects.

    If any code path under test tries to spawn a real subprocess, open a
    socket, or instantiate a real TTS provider, the test fails immediately.
    `tmp_path`-scoped file writes remain allowed.
    """

    def _deny(*args, **kwargs):
        raise AssertionError(
            "Hermetic guard tripped: forbidden external effect in "
            "test_timing_regression (subprocess/socket/provider)."
        )

    monkeypatch.setattr(subprocess, "run", _deny)
    monkeypatch.setattr(subprocess, "Popen", _deny)
    monkeypatch.setattr(socket, "create_connection", _deny)
    monkeypatch.setattr(socket, "socket", _deny)
    monkeypatch.setattr(_ga, "get_provider", _deny)
    yield


def test_sentence_boundary_crossing(hermetic_guard):
    """No words leak across sentence boundaries within the same scene."""
    by_scene = _cues_by_scene()
    scene1_cues = by_scene.get(1, [])
    assert scene1_cues, "expected cues for scene 1"
    all_cue_text = " ".join(c["text"] for c in scene1_cues)
    assert "oración" in all_cue_text
    cues_text = " | ".join(c["text"] for c in scene1_cues)
    assert "Segunda" not in scene1_cues[0]["text"], \
        f"First cue leaks into second sentence: {cues_text}"
    assert "Tercera" not in scene1_cues[0]["text"], \
        f"First cue leaks into third sentence: {cues_text}"


def test_punctuation_restoration(hermetic_guard):
    """Trailing punctuation recovered from canonical text in Edge mode."""
    by_scene = _cues_by_scene()
    scene1_cues = by_scene.get(1, [])
    assert scene1_cues, "expected cues for scene 1"
    has_period = any("oración." in c["text"] for c in scene1_cues)
    assert has_period, \
        f"No cue contains period: {[c['text'] for c in scene1_cues]}"


def test_no_cross_scene_leakage(hermetic_guard):
    """Cues from scene 1 do not leak into scene 2 window and vice versa.
    Uses unique words from each scene to avoid false positives."""
    by_scene = _cues_by_scene()
    scene1_cues = by_scene.get(1, [])
    scene2_cues = by_scene.get(2, [])
    assert scene1_cues and scene2_cues, "expected cues for both scenes"
    scene1_unique = "Primera"
    scene2_unique = "comienza"
    for cue in scene1_cues:
        assert scene2_unique not in cue["text"], \
            f"Scene 1 cue contains scene 2 text: {cue['text']}"
    for cue in scene2_cues:
        assert scene1_unique not in cue["text"], \
            f"Scene 2 cue contains scene 1 text: {cue['text']}"


def test_no_single_word_by_boundary(hermetic_guard):
    """No single-word cue is created solely by sentence-boundary handling
    (a single-word cue is allowed if it's a brief word like an
    interjection, or is the last cue at a scene boundary)."""
    by_scene = _cues_by_scene()
    scene1_cues = by_scene.get(1, [])
    assert scene1_cues, "expected cues for scene 1"
    scene1_end = scene1_cues[-1]["endSec"] if scene1_cues else 999
    for cue in scene1_cues:
        word_count = len(cue["text"].split())
        is_last_cue = cue["endSec"] >= scene1_end - 0.1
        if word_count < 2 and is_last_cue:
            continue  # Allow single-word cue at scene boundary
        assert word_count >= 2, \
            f"Single-word cue found: '{cue['text']}' (start={cue['startSec']})"
