#!/usr/bin/env python3
"""Subtitle alignment using faster-whisper with canonical text reconciliation.

Two modes:
  - whisper: transcribes audio with word-level timestamps via faster-whisper,
    then reconciles timestamps with canonical voiceover text so displayed text
    is always the canonical script, not the imperfect ASR transcript.
  - estimated: uniform distribution of words over known duration.

Configuration via environment variables:
  WHISPER_MODEL: model name (default: tiny)
  SUBTITLE_PROVIDER: estimated|whisper (default: estimated)

Usage:
    from shorts_creator.audio.whisper import align_with_canonical_text
    cues_by_scene, source, confidence, warnings = align_with_canonical_text(
        audio_path="narration.mp3",
        canonical_scenes=[...],  # [{sceneNumber, voiceover, targetDurationSec}]
        scene_timings=[...],     # [{sceneNumber, startSec, endSec}]
    )
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from typing import Optional


DOTENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def _load_env():
    env = {}
    if DOTENV_PATH.exists():
        for line in DOTENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip()
    return env


_ENV = _load_env()


# ── Normalization ────────────────────────────────────────────────────────

def _normalize_word(w: str) -> str:
    w = w.lower().strip(".,!?;: \"'¡¿()[]{}")
    w = unicodedata.normalize('NFKD', w).encode('ascii', 'ignore').decode('ascii')
    return w


def _normalize_text(t: str) -> str:
    return _normalize_word(t)


# ── Word alignment ──────────────────────────────────────────────────────

def _align_words_to_canonical(
    whisper_words: list[dict],
    canonical_text: str,
    scene_start: float,
    scene_end: float,
) -> tuple[list[dict], list[str]]:
    """Align canonical words to whisper word timestamps within a scene.

    Uses fuzzy greedy matching: for each canonical word, finds the best
    matching whisper word in order. Unmatched canonical words get
    interpolated timestamps.

    Returns (aligned_words, warnings) where each aligned word has:
      {text, startSec, endSec}
    """
    warnings: list[str] = []

    if not canonical_text.strip():
        return [], warnings

    canonical_words = canonical_text.split()
    if not canonical_words:
        return [], warnings

    if not whisper_words:
        dur = scene_end - scene_start if scene_end > scene_start else 5.0
        per_word = dur / max(len(canonical_words), 1)
        result = []
        for i, w in enumerate(canonical_words):
            result.append({
                "text": w,
                "startSec": round(scene_start + i * per_word, 3),
                "endSec": round(scene_start + (i + 1) * per_word, 3),
            })
        return result, warnings

    norm_canon = [_normalize_word(w) for w in canonical_words]
    norm_whisper = [_normalize_word(w["text"]) for w in whisper_words]

    aligned: list[dict] = []
    wi = 0

    for ci, cn in enumerate(norm_canon):
        best_idx: int | None = None
        # Try exact match first
        search_limit = min(wi + 8, len(whisper_words))
        for j in range(wi, search_limit):
            if norm_whisper[j] == cn:
                best_idx = j
                break
        # Try substring/partial match
        if best_idx is None:
            for j in range(wi, min(wi + 5, len(whisper_words))):
                if cn in norm_whisper[j] or norm_whisper[j] in cn:
                    best_idx = j
                    break

        if best_idx is not None:
            ww = whisper_words[best_idx]
            aligned.append({
                "text": canonical_words[ci],
                "startSec": ww["startSec"],
                "endSec": ww["endSec"],
            })
            wi = best_idx + 1
        else:
            if aligned:
                prev = aligned[-1]
                est_dur = max(0.1, (prev["endSec"] - prev["startSec"]))
                aligned.append({
                    "text": canonical_words[ci],
                    "startSec": round(prev["endSec"], 3),
                    "endSec": round(prev["endSec"] + est_dur, 3),
                })
            else:
                aligned.append({
                    "text": canonical_words[ci],
                    "startSec": round(scene_start, 3),
                    "endSec": round(scene_start + 0.3, 3),
                })
            warnings.append(f"Unmatched canonical word '{canonical_words[ci]}' (interpolated)")

    return aligned, warnings


# ── Cue grouping ────────────────────────────────────────────────────────

def _group_aligned_into_cues(aligned_words: list[dict]) -> list[dict]:
    cues = []
    buffer = []
    buffer_start = None

    def flush():
        nonlocal buffer, buffer_start
        if not buffer:
            return
        text = " ".join(w["text"] for w in buffer)
        text = re.sub(r'\s+([,.!?;:])', r'\1', text)
        text = re.sub(r'\s*\'\s*', '\'', text)
        text = text.strip()
        if not text:
            buffer = []
            buffer_start = None
            return
        cues.append({
            "startSec": round(buffer_start, 3),
            "endSec": round(buffer[-1]["endSec"], 3),
            "text": text,
        })
        buffer = []
        buffer_start = None

    for w in aligned_words:
        word_text = w.get("text", "").strip()
        if not word_text:
            continue
        if buffer_start is None:
            buffer_start = w["startSec"]
        buffer.append(w)

        is_end_of_sentence = word_text[-1] in ".!?"
        is_pause = len(buffer) >= 2 and (w["startSec"] - buffer[-2]["endSec"]) > 0.4
        is_long_enough = len(buffer) >= 7
        is_medium_with_punct = len(buffer) >= 4 and word_text[-1] in ",;:"

        if is_end_of_sentence or is_pause or is_long_enough or is_medium_with_punct:
            if len(buffer) >= 2 or is_end_of_sentence:
                flush()

    flush()

    if not cues:
        return cues

    filtered = []
    i = 0
    while i < len(cues):
        cue = cues[i]
        dur = cue["endSec"] - cue["startSec"]
        if dur < 0.7 and filtered and i > 0:
            prev = filtered[-1]
            prev["endSec"] = cue["endSec"]
            prev["text"] += " " + cue["text"]
        else:
            filtered.append(cue)
        i += 1

    final = []
    for cue in filtered:
        dur = cue["endSec"] - cue["startSec"]
        if dur > 4.0:
            words_in_cue = cue["text"].split()
            if len(words_in_cue) >= 4:
                mid = len(words_in_cue) // 2
                split_point = len(" ".join(words_in_cue[:mid])) + 1
                t1 = cue["text"][:split_point].strip()
                t2 = cue["text"][split_point:].strip()
                dur_per_word = dur / len(words_in_cue)
                split_sec = cue["startSec"] + dur_per_word * mid
                final.append({"startSec": cue["startSec"], "endSec": round(split_sec, 3), "text": t1})
                final.append({"startSec": round(split_sec, 3), "endSec": cue["endSec"], "text": t2})
                continue
        final.append(cue)

    return final


# ── Low-level whisper transcription ────────────────────────────────────

def _transcribe_whisper(audio_path: str, model_name: str = "tiny",
                        language: str = "es") -> Optional[list[dict]]:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_path, language=language,
                                   word_timestamps=True)

    all_words = []
    for seg in segments:
        if seg.words:
            for w in seg.words:
                word_text = w.word.strip()
                if word_text and word_text != "[BLANK_AUDIO]":
                    all_words.append({
                        "startSec": round(w.start, 3),
                        "endSec": round(w.end, 3),
                        "text": word_text,
                    })
        else:
            for w in _estimate_words_uniform(seg.text, seg.end - seg.start):
                all_words.append(w)

    return all_words


# ── Uniform estimation fallback ─────────────────────────────────────────

def _estimate_words_uniform(text: str, duration_sec: float) -> list[dict]:
    words = text.split()
    if not words or duration_sec <= 0:
        return []
    word_dur = duration_sec / len(words)
    result = []
    for i, w in enumerate(words):
        result.append({
            "startSec": round(i * word_dur, 3),
            "endSec": round((i + 1) * word_dur, 3),
            "text": w,
        })
    return result


# ── Per-scene uniform estimation ────────────────────────────────────────

def _estimate_scene_cues(canonical_text: str,
                         scene_start: float,
                         scene_end: float) -> list[dict]:
    dur = scene_end - scene_start
    words = _estimate_words_uniform(canonical_text, dur)
    return _group_aligned_into_cues(words)


# ── Main reconciliation entry point ──────────────────────────────────────

def align_with_canonical_text(
    audio_path: str,
    canonical_scenes: list[dict],
    scene_timings: list[dict],
    whisper_model: str = "tiny",
    language: str = "es",
) -> tuple[dict[int, list[dict]], str, str, list[str]]:
    """Transcribe audio with whisper, reconcile timestamps with canonical text.

    Args:
        audio_path: Path to the narration audio file.
        canonical_scenes: Scene list with keys 'sceneNumber' and 'voiceover'.
        scene_timings: Scene timing list with keys 'sceneNumber', 'startSec', 'endSec'.
        whisper_model: Whisper model name (default: tiny).
        language: Audio language code (default: es).

    Returns:
        (cues_by_scene, source, confidence, warnings)
        cues_by_scene: dict mapping sceneNumber → list of cues (canonical text + timestamps)
        source: "whisper_reconciled" or "estimated"
        confidence: "high" or "low"
        warnings: list of warning strings
    """
    all_warnings: list[str] = []

    if not Path(audio_path).exists():
        all_warnings.append(f"Audio file not found: {audio_path}. Falling back to estimated mode.")
        return _estimate_all_scenes(canonical_scenes, scene_timings, all_warnings)

    whisper_words = _transcribe_whisper(audio_path, whisper_model, language)
    if whisper_words is None:
        all_warnings.append("faster-whisper not installed. Falling back to estimated mode.")
        return _estimate_all_scenes(canonical_scenes, scene_timings, all_warnings)

    if not whisper_words:
        all_warnings.append("Whisper returned no words. Falling back to estimated mode.")
        return _estimate_all_scenes(canonical_scenes, scene_timings, all_warnings)

    timing_map = {st["sceneNumber"]: st for st in scene_timings}

    cues_by_scene: dict[int, list[dict]] = {}
    total_cues = 0

    for sc in canonical_scenes:
        sn = sc["sceneNumber"]
        voiceover = sc.get("voiceover", "").strip()
        st = timing_map.get(sn)
        if not st:
            all_warnings.append(f"Scene {sn}: no sceneTiming entry, using estimated mode")
            dur = float(sc.get("targetDurationSec", 5))
            cues = _estimate_scene_cues(voiceover, 0, dur)
            cues_by_scene[sn] = cues
            total_cues += len(cues)
            continue

        scene_start = st["startSec"]
        scene_end = st["endSec"]

        if not voiceover:
            cues_by_scene[sn] = []
            continue

        margin = 0.5
        scene_words = [
            w for w in whisper_words
            if (scene_start - margin) <= w["startSec"] <= (scene_end + margin)
        ]

        aligned, warns = _align_words_to_canonical(
            scene_words, voiceover, scene_start, scene_end
        )
        for w in warns:
            all_warnings.append(f"  Scene {sn}: {w}")

        if not aligned:
            cues = _estimate_scene_cues(voiceover, scene_start, scene_end)
            all_warnings.append(f"  Scene {sn}: no aligned words, using estimated cues")
        else:
            cues = _group_aligned_into_cues(aligned)

        cues_by_scene[sn] = cues
        total_cues += len(cues)

    confidence = "high" if total_cues > 0 else "low"
    return cues_by_scene, "whisper_reconciled", confidence, all_warnings


def _estimate_all_scenes(
    canonical_scenes: list[dict],
    scene_timings: list[dict],
    existing_warnings: list[str],
) -> tuple[dict[int, list[dict]], str, str, list[str]]:
    timing_map = {st["sceneNumber"]: st for st in scene_timings}
    cues_by_scene = {}
    for sc in canonical_scenes:
        sn = sc["sceneNumber"]
        st = timing_map.get(sn)
        start = st["startSec"] if st else 0
        end = st["endSec"] if st else float(sc.get("targetDurationSec", 5))
        cues = _estimate_scene_cues(sc.get("voiceover", ""), start, end)
        cues_by_scene[sn] = cues
    return cues_by_scene, "estimated", "low", existing_warnings


# ── Legacy compatibility wrapper ────────────────────────────────────────

def align_subtitles(audio_path: str, text: str, duration_sec: float,
                    mode: str = "estimated",
                    whisper_model: str | None = None,
                    language: str = "es") -> tuple[list[dict], str, str]:
    import warnings as _warnings
    _warnings.warn(
        "align_subtitles() is deprecated. Use align_with_canonical_text() instead.",
        DeprecationWarning, stacklevel=2,
    )

    if whisper_model is None:
        whisper_model = _ENV.get("WHISPER_MODEL", "tiny")

    if mode == "whisper":
        if not Path(audio_path).exists():
            print(f"WARNING: audio file not found: {audio_path}. Falling back to estimated mode.")
            mode = "estimated"
        else:
            words = _transcribe_whisper(audio_path, whisper_model, language)
            if words is not None:
                cues = _group_aligned_into_cues(words)
                if cues:
                    return cues, "whisper_word_timestamps", "high"

            print("WARNING: faster-whisper not installed or returned no cues. "
                  "Falling back to estimated mode. "
                  "Install: pip install faster-whisper")
            mode = "estimated"

    words = _estimate_words_uniform(text, duration_sec)
    cues = _group_aligned_into_cues(words)
    return cues, "estimated", "low"
