#!/usr/bin/env python3

import json
import math
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from shorts_creator.audio.tts_provider import TTSOptions, get_provider
from shorts_creator.infrastructure.metadata_store import load_metadata, save_metadata

TICK = 10_000_000

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOTENV_PATH = PROJECT_ROOT / ".env"


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


def _get_mp3_duration(audio_path: Path) -> "tuple[float, str] | tuple[None, None]":
    """Get actual duration of an MP3 file using ffprobe (local then Docker).

    Returns (duration_sec, source) where source is "ffprobe_local" or
    "ffprobe_docker".  Returns (None, None) if all probing methods fail.
    """
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            r = subprocess.run(
                [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format",
                 str(audio_path)],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0:
                dur = float(json.loads(r.stdout)["format"]["duration"])
                if dur > 0 and math.isfinite(dur):
                    return dur, "ffprobe_local"
        except Exception:
            pass

    docker_env = os.environ.copy()
    docker_env.pop("DOCKER_API_VERSION", None)
    try:
        ws_path = audio_path.relative_to(PROJECT_ROOT)
    except ValueError:
        ws_path = audio_path.relative_to(audio_path.parents[3])
    try:
        r = subprocess.run(
            ["docker", "run", "--rm",
             "-v", f"{PROJECT_ROOT}:/workspace",
             "--entrypoint", "ffprobe",
             "linuxserver/ffmpeg:latest",
             "-v", "quiet", "-print_format", "json", "-show_format",
             f"/workspace/{ws_path}"],
            capture_output=True, text=True, timeout=30,
            env=docker_env,
        )
        if r.returncode == 0:
            dur = float(json.loads(r.stdout)["format"]["duration"])
            if dur > 0 and math.isfinite(dur):
                return dur, "ffprobe_docker"
    except Exception:
        pass

    return None, None


SPEECH_END_GUARD_SEC = 0.15


def _compute_active_audio_duration(
    scene_data: dict,
    physical_duration_sec: float | None,
) -> float | None:
    """Compute active audio duration from last subtitle cue + guard."""
    if physical_duration_sec is None or physical_duration_sec <= 0:
        return None
    cues = (scene_data.get("subtitleTiming") or {}).get("cues", [])
    if not cues:
        return None
    last_end = max(
        (c.get("endSec", 0) for c in cues),
        default=None,
    )
    if last_end is None or not isinstance(last_end, (int, float)) or isinstance(last_end, bool):
        return None
    if not math.isfinite(last_end) or last_end < 0:
        return None
    active = min(physical_duration_sec, last_end + SPEECH_END_GUARD_SEC)
    if active <= 0:
        return None
    return round(active, 3)


def video_dir(metadata_path: Path) -> Path:
    return metadata_path.parent


def scenes_dir(metadata_path: Path) -> Path:
    return video_dir(metadata_path) / "scenes"


def split_sentences(text: str) -> list[str]:
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in parts if p.strip()]


def build_full_narration(scenes: list, join_style: str = "period",
                         scene_joins: dict[int, str] | None = None) -> tuple[str, list[dict]]:
    parts = []
    narration_units = []
    joins = scene_joins or {}

    for s in scenes:
        sn = s["sceneNumber"]
        text = s.get("voiceover", "").strip()
        if not text:
            continue
        sentences = split_sentences(text)
        if not sentences:
            sentences = [text]
        for si, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue
            if sentence[-1] not in ".!?":
                sentence += "."
            narration_units.append({
                "sceneNumber": sn,
                "sentenceIndex": si,
                "text": sentence,
            })
            parts.append(sentence)

    # Apply joinToNext connectors (replace ". " between scenes)
    if joins and parts:
        for scene_num, connector in sorted(joins.items(), reverse=True):
            # Find the first narration_unit of this scene
            insert_idx = None
            for i, nu in enumerate(narration_units):
                if nu["sceneNumber"] == scene_num and nu["sentenceIndex"] == 0:
                    insert_idx = i
                    break
            if insert_idx is not None and insert_idx > 0:
                prev_text = parts[insert_idx - 1]
                if prev_text.endswith("."):
                    parts[insert_idx - 1] = prev_text[:-1] + connector

    if join_style != "period" and parts:
        scene_ends = set()
        current_sn = None
        for i, nu in enumerate(narration_units):
            if nu["sceneNumber"] != current_sn:
                if i > 0:
                    scene_ends.add(i - 1)
                current_sn = nu["sceneNumber"]
        # Last scene also ends
        if narration_units:
            scene_ends.add(len(narration_units) - 1)

        for idx in sorted(scene_ends)[:-1]:
            if idx >= len(parts):
                continue
            last_char = parts[idx][-1]
            if last_char == ".":
                if join_style == "semicolon":
                    parts[idx] = parts[idx][:-1] + ";"
                elif join_style == "comma":
                    parts[idx] = parts[idx][:-1] + ","

    full_text = " ".join(parts)
    return full_text, narration_units


def text_similarity(a: str, b: str) -> float:
    a_words = set(a.split())
    b_words = set(b.split())
    if not b_words:
        return 0.0
    intersection = a_words & b_words
    return len(intersection) / len(b_words)


def compute_scene_timings_by_sentences(
    narration_units: list[dict],
    sentence_boundaries: list[dict],
) -> tuple[list[dict], str, str]:
    if len(sentence_boundaries) != len(narration_units):
        return [], "low", "REVIEW_REQUIRED"

    timings = []
    current_scene = None
    scene_start = None

    for i, sb in enumerate(sentence_boundaries):
        unit = narration_units[i]
        sb_text = re.sub(r'\s+', ' ', sb.get("text", "").lower().strip()).strip(".,!?;:¡¿ \"'")
        unit_text = re.sub(r'\s+', ' ', unit["text"].lower().strip()).strip(".,!?;:¡¿ \"'")

        sim = text_similarity(sb_text, unit_text)
        if sim < 0.7:
            return [], "low", "REVIEW_REQUIRED"

        sb_start = sb["offset"] / TICK
        sb_dur = sb["duration"] / TICK
        sb_end = sb_start + sb_dur

        if unit["sceneNumber"] != current_scene:
            if current_scene is not None:
                timings.append({
                    "sceneNumber": current_scene,
                    "startSec": round(scene_start, 3),
                    "endSec": round(sb_start, 3),
                })
            current_scene = unit["sceneNumber"]
            scene_start = sb_start

    if current_scene is not None and sentence_boundaries:
        last_sb = sentence_boundaries[-1]
        last_end = round(last_sb["offset"] / TICK + last_sb["duration"] / TICK, 3)
        timings.append({
            "sceneNumber": current_scene,
            "startSec": round(scene_start, 3),
            "endSec": last_end,
        })

    return timings, "high", "PASS"


def _extract_words_from_cues(cues: list[dict]) -> list[dict]:
    """Reconstruct word-level data from already-grouped cues.
    Each cue's text is split into words with estimated even timing."""
    words = []
    for cue in cues:
        text = cue.get("text", "")
        start = cue.get("startSec", 0)
        end = cue.get("endSec", 0)
        cue_words = text.split()
        if not cue_words or end <= start:
            continue
        dur_per_word = (end - start) / len(cue_words)
        for i, w in enumerate(cue_words):
            words.append({
                "startSec": round(start + i * dur_per_word, 3),
                "endSec": round(start + (i + 1) * dur_per_word, 3),
                "text": w,
                "sceneNumber": cue.get("sceneNumber"),
            })
    return words


def _compute_native_scene_timings(words, narration_units=None):
    """Compute scene windows from first/last WordBoundary per scene.
    Returns (timings, confidence, status) or None if insufficient data."""
    if not words:
        return None
    scene_word_times = {}
    for w in words:
        sn = w.get("sceneNumber")
        if sn is None:
            continue
        ws = w.get("startSec", 0)
        we = w.get("endSec", 0)
        if sn not in scene_word_times:
            scene_word_times[sn] = {"startSec": ws, "endSec": we}
        else:
            if ws < scene_word_times[sn]["startSec"]:
                scene_word_times[sn]["startSec"] = ws
            if we > scene_word_times[sn]["endSec"]:
                scene_word_times[sn]["endSec"] = we
    if not scene_word_times:
        return None
    sorted_sns = sorted(scene_word_times.keys())
    for i in range(len(sorted_sns) - 1):
        curr_sn = sorted_sns[i]
        next_sn = sorted_sns[i + 1]
        scene_word_times[curr_sn]["endSec"] = min(
            scene_word_times[curr_sn]["endSec"],
            scene_word_times[next_sn]["startSec"],
        )
    timings = [{
        "sceneNumber": sn,
        "startSec": round(t["startSec"], 3),
        "endSec": round(t["endSec"], 3),
    } for sn, t in sorted(scene_word_times.items())]
    if narration_units and len(timings) == len(set(nu["sceneNumber"] for nu in narration_units)):
        return (timings, "high", "PASS")
    return (timings, "medium", "PASS")


def _assign_words_to_scenes(words, scene_timings, narration_units=None):
    for w in words:
        ws = w.get("startSec", 0)
        w["sceneNumber"] = None
        for st in scene_timings:
            if st["startSec"] <= ws < st["endSec"]:
                w["sceneNumber"] = st["sceneNumber"]
                break
        if w["sceneNumber"] is None and scene_timings:
            w["sceneNumber"] = scene_timings[-1]["sceneNumber"]
    return words


def _build_canonical_tokens(narration_units: list[dict]) -> list[dict]:
    """Build ordered list of canonical tokens with sceneNumber and narrationUnitIndex."""
    tokens = []
    for nu in narration_units:
        for word in nu["text"].split():
            tokens.append({
                "text": word,
                "sceneNumber": nu["sceneNumber"],
                "narrationUnitIndex": nu.get("sentenceIndex", 0),
            })
    return tokens


# Spanish number ↔ digit mappings for canonical matching.
# Edge TTS speaks numbers as words, canonical tokens may contain digits.
_SPANISH_NUMBERS = {
    "cero": 0, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
    "veinte": 20, "veintiuno": 21, "veintidos": 22, "veintitres": 23,
    "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintisiete": 27,
    "veintiocho": 28, "veintinueve": 29,
    "treinta": 30, "cuarenta": 40, "cincuenta": 50,
    "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90,
    "cien": 100, "ciento": 100,
    "doscientos": 200, "trescientos": 300, "cuatrocientos": 400,
    "quinientos": 500, "seiscientos": 600, "setecientos": 700,
    "ochocientos": 800, "novecientos": 900,
    "mil": 1000,
}

# Digits 0-9 for building multi-digit numbers
_SPANISH_DIGITS = ["", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve"]


def _parse_spanish_number_sequence(words: list[str], start: int) -> tuple[str | None, int]:
    """Parse a Spanish number word sequence starting at index `start` in `words`.

    Handles: 13→trece, 160→ciento sesenta, 1961→mil novecientos sesenta y uno.
    Returns (digit_string, words_consumed) or (None, 0) if not a number.
    """
    if start >= len(words):
        return None, 0
    clean = _strip_punct(words[start]).lower()
    if clean in _SPANISH_NUMBERS:
        val = _SPANISH_NUMBERS[clean]
        consumed = 1
        remaining = words[start + 1:]
        ri = 0

        # Try to parse compound numbers after "mil"
        if val >= 1000 and ri < len(remaining):
            n2 = _strip_punct(remaining[ri]).lower()
            if n2 in _SPANISH_NUMBERS and _SPANISH_NUMBERS[n2] < 1000:
                val += _SPANISH_NUMBERS[n2]
                consumed += 1
                ri += 1
                remaining = remaining[1:]
                # After hundreds, try tens+digits (e.g., "mil novecientos sesenta y uno")
                if ri == 0 and remaining:
                    n3 = _strip_punct(remaining[0]).lower()
                    if n3 in _SPANISH_NUMBERS and _SPANISH_NUMBERS[n3] < 100 and _SPANISH_NUMBERS[n3] >= 20:
                        val += _SPANISH_NUMBERS[n3]
                        consumed += 1
                        ri += 1
                        remaining = remaining[1:]
                        # Try "y" + digit (e.g., "sesenta y uno")
                        if remaining and _strip_punct(remaining[0]).lower() == "y" and len(remaining) > 1:
                            n4 = _strip_punct(remaining[1]).lower()
                            if n4 in _SPANISH_NUMBERS and _SPANISH_NUMBERS[n4] < 10:
                                val += _SPANISH_NUMBERS[n4]
                                consumed += 2

        # Try "y" + digit for tens (e.g., "treinta y seis")
        elif 20 <= val < 100:
            if ri < len(remaining) and _strip_punct(remaining[ri]).lower() == "y":
                if ri + 1 < len(remaining):
                    n3 = _strip_punct(remaining[ri + 1]).lower()
                    if n3 in _SPANISH_NUMBERS and _SPANISH_NUMBERS[n3] < 10:
                        val += _SPANISH_NUMBERS[n3]
                        consumed += 2

        # Try "cientos" for 100-900 range followed by tens
        elif val == 100 and ri < len(remaining):
            n2 = _strip_punct(remaining[ri]).lower()
            if n2 in _SPANISH_NUMBERS and _SPANISH_NUMBERS[n2] < 100:
                val += _SPANISH_NUMBERS[n2]
                consumed += 1
                ri += 1
                if ri < len(remaining) and _strip_punct(remaining[ri]).lower() == "y" and ri + 1 < len(remaining):
                    n3 = _strip_punct(remaining[ri + 1]).lower()
                    if n3 in _SPANISH_NUMBERS and _SPANISH_NUMBERS[n3] < 10:
                        val += _SPANISH_NUMBERS[n3]
                        consumed += 2

        # Try digit-string for 0-999 range that wasn't caught above: ciento → 100, not 100+more
        # Already handled by the direct lookup

        return str(val), consumed

    # Check if it's already a digit string like "1961"
    if re.match(r'^\d+$', clean):
        return clean, 1

    return None, 0


def _spanish_number_to_words(num: int) -> list[str]:
    """Convert an integer to Spanish word sequence. Returns list of words."""
    if num == 0:
        return ["cero"]
    if num < 30:
        for k, v in _SPANISH_NUMBERS.items():
            if v == num:
                return [k]
    result = []
    if num >= 1000:
        thousands = num // 1000
        remainder = num % 1000
        if thousands == 1:
            result.append("mil")
        else:
            result.extend(_spanish_number_to_words(thousands))
            result.append("mil")
        num = remainder
    if num >= 100:
        hundreds = num // 100
        remainder = num % 100
        if hundreds == 1 and remainder == 0:
            result.append("cien")
        elif hundreds == 1:
            result.append("ciento")
        else:
            for k, v in _SPANISH_NUMBERS.items():
                if v == hundreds * 100:
                    result.append(k)
                    break
        num = remainder
    if num >= 20:
        tens = (num // 10) * 10
        ones = num % 10
        for k, v in _SPANISH_NUMBERS.items():
            if v == tens:
                result.append(k)
                break
        if ones > 0:
            result.append("y")
            result.append(_SPANISH_DIGITS[ones])
    elif num > 0:
        for k, v in _SPANISH_NUMBERS.items():
            if v == num:
                result.append(k)
                break
    return result


def _strip_punct(text: str) -> str:
    return text.strip(".,!?;:¡¿()\"'-")


def _accent_fold(text: str) -> str:
    """Fold accented characters to ASCII equivalents for comparison."""
    accents = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
    return text.translate(accents)


def _match_words_to_canonical(words, canonical_tokens):
    """Span-aware canonical matching with strict scene ownership.

    Matches Edge WordBoundary events to canonical narration-unit tokens using:
    - One-to-one direct matching (punctuation- and accent-insensitive)
    - One Edge event → multiple canonical tokens (e.g. "160 kilómetros" → "160" + "kilómetros")
    - Multi-word Spanish number span matching (e.g. "mil novecientos sesenta y uno" → "1961")
    - Strict sequential ownership: never advances to a later scene until
      all canonical tokens of the current scene are resolved.
    - Unmatched events get sceneNumber=None (no inheritance).

    Returns (annotated, metrics).
    """
    # Group canonical tokens by (sceneNumber, narrationUnitIndex)
    units: dict[tuple[int, int], list[dict]] = {}
    unit_keys: list[tuple[int, int]] = []
    for ct in canonical_tokens:
        key = (ct["sceneNumber"], ct["narrationUnitIndex"])
        if key not in units:
            units[key] = []
            unit_keys.append(key)
        units[key].append(ct)

    annotated: list[dict] = []
    matched = 0
    total = len(words)
    unmatched_edge: list[str] = []
    skipped_canon: list[dict] = []
    number_fallbacks: list[dict] = []
    current_unit_idx = 0
    ci = 0  # index within current unit's tokens
    unresolved_units: set[tuple[int, int]] = set()

    def _current_unit() -> tuple[int, int] | None:
        if current_unit_idx < len(unit_keys):
            return unit_keys[current_unit_idx]
        return None

    def _scene_for_unit(key: tuple[int, int]) -> int:
        return key[0]

    # Track per-unit consumed canonical token indices (set of indices within unit)
    unit_consumed: dict[tuple[int, int], set[int]] = {}
    for uk in unit_keys:
        unit_consumed[uk] = set()

    for w in words:
        wt = w["text"].strip()
        if not wt:
            annotated.append({**w, "sceneNumber": None, "narrationUnitIndex": None})
            continue

        unit_key = _current_unit()
        matched_this_word = False
        consumed_ct = 0
        match_index_in_unit = -1

        unit_tokens: list[dict] = []
        sn = 0
        nui = 0
        ws = ""
        if unit_key is not None:
            unit_tokens = units[unit_key]
            sn = unit_key[0]
            nui = unit_key[1]

            if unit_tokens:
                ws = _strip_punct(wt)

                # --- Phase 1: Sequential matching (try ci first) ---
                if not matched_this_word and ci < len(unit_tokens) and ci not in unit_consumed[unit_key]:
                    ct = unit_tokens[ci]
                    cs = _strip_punct(ct["text"])

                    # Direct match (punctuation- and accent-insensitive)
                    if _accent_fold(ws.lower()) == _accent_fold(cs.lower()):
                        matched_this_word = True
                        consumed_ct = 1
                        match_index_in_unit = ci

                    # Digit-to-digit match
                    if not matched_this_word and re.match(r'^\d+$', ws) and re.match(r'^\d+$', cs):
                        if ws == cs:
                            matched_this_word = True
                            consumed_ct = 1
                            match_index_in_unit = ci

                    # Edge Spanish number → canonical digit
                    if not matched_this_word and re.match(r'^\d+$', cs):
                        remaining_words = [wt] + [x["text"] for x in words[words.index(w) + 1:words.index(w) + 6]]
                        num_val, num_consumed = _parse_spanish_number_sequence(remaining_words, 0)
                        if num_val is not None and cs == num_val:
                            matched_this_word = True
                            consumed_ct = 1
                            match_index_in_unit = ci
                            number_fallbacks.append({
                                "edgeWord": " ".join(remaining_words[:num_consumed]),
                                "canonicalToken": ct["text"],
                                "resolvedAs": num_val,
                            })

                    # Edge digit → canonical Spanish number
                    if not matched_this_word and re.match(r'^\d+$', ws):
                        canon_words = _spanish_number_to_words(int(ws))
                        if canon_words:
                            ct_text = _strip_punct(ct["text"]).lower()
                            if _accent_fold(ct_text) == _accent_fold(canon_words[0].lower()):
                                matched_this_word = True
                                consumed_ct = 1
                                match_index_in_unit = ci
                                number_fallbacks.append({
                                    "edgeWord": wt,
                                    "canonicalToken": ct["text"],
                                    "resolvedAs": ws,
                                })

                    # One Edge event → multiple canonical tokens (span match)
                    if not matched_this_word:
                        edge_parts = wt.split()
                        if len(edge_parts) > 1:
                            matched_parts = 0
                            for ei, ep in enumerate(edge_parts):
                                ep_clean = _strip_punct(ep)
                                if ci + ei < len(unit_tokens) and (ci + ei) not in unit_consumed[unit_key]:
                                    next_cs = _strip_punct(unit_tokens[ci + ei]["text"])
                                    if _accent_fold(ep_clean.lower()) == _accent_fold(next_cs.lower()):
                                        matched_parts += 1
                                    else:
                                        break
                                else:
                                    break
                            if matched_parts > 0 and matched_parts == len(edge_parts):
                                matched_this_word = True
                                consumed_ct = len(edge_parts)
                                match_index_in_unit = ci

                # --- Phase 2: Bounded set-matching within the same unit ---
                # If sequential match failed, try any remaining unmatched token in this unit
                if not matched_this_word:
                    for cand_ci in range(len(unit_tokens)):
                        if cand_ci in unit_consumed[unit_key]:
                            continue
                        ct = unit_tokens[cand_ci]
                        cs = _strip_punct(ct["text"])
                        if _accent_fold(ws.lower()) == _accent_fold(cs.lower()):
                            matched_this_word = True
                            consumed_ct = 1
                            match_index_in_unit = cand_ci
                            break
                        # Check digit ↔ digit
                        if re.match(r'^\d+$', ws) and re.match(r'^\d+$', cs) and ws == cs:
                            matched_this_word = True
                            consumed_ct = 1
                            match_index_in_unit = cand_ci
                            break

                # --- Phase 3: One-to-many span via set matching ---
                if not matched_this_word:
                    edge_parts = wt.split()
                    if len(edge_parts) > 1:
                        for cand_ci in range(len(unit_tokens) - len(edge_parts) + 1):
                            all_available = all((cand_ci + ei) not in unit_consumed[unit_key] for ei in range(len(edge_parts)))
                            if not all_available:
                                continue
                            matched_parts = 0
                            for ei, ep in enumerate(edge_parts):
                                ep_clean = _strip_punct(ep)
                                next_cs = _strip_punct(unit_tokens[cand_ci + ei]["text"])
                                if _accent_fold(ep_clean.lower()) == _accent_fold(next_cs.lower()):
                                    matched_parts += 1
                                else:
                                    break
                            if matched_parts == len(edge_parts):
                                matched_this_word = True
                                consumed_ct = len(edge_parts)
                                match_index_in_unit = cand_ci
                                break

            if matched_this_word:
                # Consume the matched token(s)
                for ci_offset in range(consumed_ct):
                    unit_consumed[unit_key].add(match_index_in_unit + ci_offset)

                punct = ""
                if consumed_ct == 1:
                    cw_text = unit_tokens[match_index_in_unit]["text"]
                    cs_clean = _strip_punct(cw_text)
                    if len(cw_text) > len(cs_clean):
                        for ch in cw_text[len(cs_clean):]:
                            if ch in ".,!?;:":
                                punct += ch
                annotated.append({
                    **w,
                    "text": wt + punct if (punct and consumed_ct == 1) else wt,
                    "sceneNumber": sn,
                    "narrationUnitIndex": nui,
                    "wordOwnershipSource": "canonical_span_match",
                })
                matched += 1

                # Advance ci to first unconsumed index in this unit
                ci = match_index_in_unit + consumed_ct
                while ci < len(unit_tokens) and ci in unit_consumed[unit_key]:
                    ci += 1

                # If unit fully consumed → advance to next unit
                if len(unit_consumed[unit_key]) >= len(unit_tokens):
                    current_unit_idx += 1
                    ci = 0
                continue

        # --- No match found for this Edge word ---
        if unit_key is not None and not matched_this_word:
            if ci >= len(units[unit_key]):
                # Current unit fully consumed (or skipped past end).
                # Try set-matching against the next unconsumed unit.
                next_uk_idx = current_unit_idx + 1
                while next_uk_idx < len(unit_keys):
                    nuk = unit_keys[next_uk_idx]
                    if nuk not in unit_consumed:
                        unit_consumed[nuk] = set()
                    consumed_here = unit_consumed[nuk]
                    for cand_ci in range(len(units[nuk])):
                        if cand_ci in consumed_here:
                            continue
                        cand_ct = units[nuk][cand_ci]
                        if _accent_fold(_strip_punct(wt).lower()) == _accent_fold(_strip_punct(cand_ct["text"]).lower()):
                            # Found match in next unit — switch to it
                            current_unit_idx = next_uk_idx
                            consumed_here.add(cand_ci)
                            ci = cand_ci + 1
                            while ci < len(units[nuk]) and ci in consumed_here:
                                ci += 1
                            matched_this_word = True
                            matched += 1
                            annotated.append({
                                **w,
                                "sceneNumber": nuk[0],
                                "narrationUnitIndex": nuk[1],
                                "wordOwnershipSource": "canonical_span_match",
                            })
                            break
                    if matched_this_word:
                        break
                    # Not in this unit either — mark it resolved (no matchable tokens)
                    if unit_key not in unresolved_units:
                        unresolved_units.add(nuk)
                    next_uk_idx += 1

                if not matched_this_word:
                    # Advance past this unit entirely
                    if unit_key not in unresolved_units:
                        unresolved_units.add(unit_key)
                    current_unit_idx += 1
                    ci = 0
                    # Re-try this word against the new current unit
                    continue
            else:
                # Try to skip this canonical token (it may be absent in Edge output)
                skipped_canon.append({
                    "canonicalToken": unit_tokens[ci]["text"],
                    "sceneNumber": sn,
                    "edgeWord": wt,
                })
                ci += 1
                # After skipping, check if this word matches the next canonical token
                if ci < len(unit_tokens):
                    next_ct = unit_tokens[ci]
                    if _accent_fold(_strip_punct(wt).lower()) == _accent_fold(_strip_punct(next_ct["text"]).lower()):
                        unit_consumed[unit_key].add(ci)
                        ci += 1
                        while ci < len(unit_tokens) and ci in unit_consumed[unit_key]:
                            ci += 1
                        matched_this_word = True
                        matched += 1
                        annotated.append({
                            **w,
                            "sceneNumber": sn,
                            "narrationUnitIndex": nui,
                            "wordOwnershipSource": "canonical_span_match",
                        })

        if not matched_this_word:
            # Edge word belongs to no scene — emit unmatched with no scene inheritance
            unmatched_edge.append(wt)
            annotated.append({**w, "sceneNumber": None, "narrationUnitIndex": None,
                              "unmatched": True, "wordOwnershipSource": "unmatched"})

    total_unmatched = len(unmatched_edge)
    unmatched_ratio = total_unmatched / total if total > 0 else 0
    if unmatched_ratio > 0.25:
        confidence = "low"
    elif unmatched_ratio > 0.10:
        confidence = "medium"
    else:
        confidence = "high"

    metrics = {
        "totalWordCount": total,
        "matchedWordCount": matched,
        "unmatchedEdgeWords": unmatched_edge[:20],
        "skippedCanonicalTokens": skipped_canon[:20],
        "numberNormalizationFallbacks": number_fallbacks[:20],
        "unmatchedRatio": round(unmatched_ratio, 3),
        "confidence": confidence,
    }
    return annotated, metrics


def _annotate_word_punctuation(words, full_text):
    canon = full_text.split()
    annotated = []
    ci = 0
    for w in words:
        wt = w["text"].strip()
        if not wt:
            annotated.append(w)
            continue
        while ci < len(canon):
            cw = canon[ci]
            cs = cw.strip(".,!?;:¡¿()\"'-")
            if wt.lower() == cs.lower():
                punct = ""
                if len(cw) > len(cs):
                    for ch in cw[len(cs):]:
                        if ch in ".,!?;:":
                            punct += ch
                annotated.append({**w, "text": wt + punct})
                ci += 1
                break
            ci += 1
        else:
            annotated.append(w)
    return annotated


def group_words_into_cues(words, sentence_boundaries=None):
    cues = []
    buffer = []
    buffer_start = None
    sb_end_times = []

    if sentence_boundaries:
        for i, sb in enumerate(sentence_boundaries):
            if i < len(sentence_boundaries) - 1:
                end_sec = sentence_boundaries[i + 1]["offset"] / 10_000_000
            else:
                end_sec = (sb["offset"] + sb["duration"]) / 10_000_000
            sb_end_times.append(round(end_sec, 3))

    sb_breaks = list(sb_end_times)

    def is_past_sentence_boundary(word_start_sec):
        return sb_end_times and word_start_sec >= sb_end_times[0]

    def pop_sentence_boundary():
        if sb_end_times:
            sb_end_times.pop(0)

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
        sn = buffer[0].get("sceneNumber")
        cues.append({
            "startSec": round(buffer_start, 3),
            "endSec": round(buffer[-1]["endSec"], 3),
            "text": text,
            "sceneNumber": sn,
        })
        buffer = []
        buffer_start = None

    for w in words:
        word_text = w["text"].strip()
        if not word_text:
            continue

        # Canonical boundary enforcement: flush if next word belongs to a different
        # scene OR a different narration unit (within the same scene)
        if buffer:
            buf_sn = buffer[0].get("sceneNumber")
            buf_nui = buffer[0].get("narrationUnitIndex")
            w_sn = w.get("sceneNumber")
            w_nui = w.get("narrationUnitIndex")
            if buf_sn is not None and w_sn is not None:
                if w_sn != buf_sn or (w_nui is not None and buf_nui is not None and w_nui != buf_nui):
                    flush()

        while sb_end_times and is_past_sentence_boundary(w["startSec"]):
            pop_sentence_boundary()

        if buffer_start is None:
            buffer_start = w["startSec"]
        buffer.append(w)

        is_end_of_sentence = word_text[-1] in ".!?"
        is_pause = len(buffer) >= 2 and (w["startSec"] - buffer[-2]["endSec"]) > 0.5
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
        starts_at_break = sb_breaks and any(
            abs(cue["startSec"] - b) < 0.1 for b in sb_breaks
        )
        if dur < 0.7 and filtered and i > 0 and not starts_at_break:
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
                t1 = " ".join(words_in_cue[:mid])
                t2 = " ".join(words_in_cue[mid:])
                dur_per_word = dur / len(words_in_cue)
                split_sec = cue["startSec"] + dur_per_word * mid
                sn = cue.get("sceneNumber")
                final.append({"startSec": cue["startSec"], "endSec": round(split_sec, 3), "text": t1, "sceneNumber": sn})
                final.append({"startSec": round(split_sec, 3), "endSec": cue["endSec"], "text": t2, "sceneNumber": sn})
                continue
        final.append(cue)

    return final


def estimate_words_from_text(text: str, sentence_start: float, sentence_end: float):
    words = text.split()
    if not words or sentence_end <= sentence_start:
        return []
    word_duration = (sentence_end - sentence_start) / len(words)
    result = []
    for i, w in enumerate(words):
        result.append({
            "startSec": sentence_start + i * word_duration,
            "endSec": sentence_start + (i + 1) * word_duration,
            "text": w,
        })
    return result


async def generate_audio_with_timestamps(text: str, output_path: Path, voice: str = "es-ES-AlvaroNeural",
                                         scene_timings_for_words: list[dict] | None = None,
                                         narration_units: list[dict] | None = None):
    provider = get_provider("edge_tts", voice=voice)
    options = TTSOptions(voice=voice)

    try:
        result = await provider.synthesize_with_timing_async(text, str(output_path), options)
    except ImportError:
        print("ERROR: edge-tts not installed. Run: pip install edge-tts")
        return None, None, None, [], {}

    td = result.timing_data or {}
    word_boundaries = td.get("word_boundaries", [])
    sentence_boundaries = td.get("sentence_boundaries", [])
    timing_source = td.get("timing_source", "")

    matching_metrics = {}

    if word_boundaries:
        if narration_units:
            canonical_tokens = _build_canonical_tokens(narration_units)
            annotated, matching_metrics = _match_words_to_canonical(word_boundaries, canonical_tokens)
        else:
            annotated = _annotate_word_punctuation(word_boundaries, text)
            if scene_timings_for_words:
                annotated = _assign_words_to_scenes(annotated, scene_timings_for_words)
            matching_metrics = {"totalWordCount": len(word_boundaries), "matchedWordCount": 0,
                                "unmatchedEdgeWords": [], "skippedCanonicalTokens": [],
                                "numberNormalizationFallbacks": [], "unmatchedRatio": 0,
                                "confidence": "medium", "note": "no canonical tokens available"}
        cues = group_words_into_cues(annotated, sentence_boundaries)
        return cues, timing_source or "edge_tts_word_boundary", "high", sentence_boundaries, matching_metrics

    if sentence_boundaries:
        all_words = []
        for sb in sentence_boundaries:
            sb_start = sb["offset"] / TICK
            sb_dur = sb["duration"] / TICK
            sb_end = sb_start + sb_dur
            words = estimate_words_from_text(sb["text"], sb_start, sb_end)
            if scene_timings_for_words:
                words = _assign_words_to_scenes(words, scene_timings_for_words)
            all_words.extend(words)
        if all_words:
            cues = group_words_into_cues(all_words)
            return cues, timing_source or "edge_tts_sentence_boundary", "medium", sentence_boundaries, matching_metrics

    return None, None, None, sentence_boundaries, matching_metrics


def estimate_cues_uniform(text: str, duration_sec: float):
    words = text.split()
    if not words or duration_sec <= 0:
        return [], "estimated", "low"

    word_duration = duration_sec / len(words)
    words_data = []
    for i, w in enumerate(words):
        words_data.append({
            "startSec": i * word_duration,
            "endSec": (i + 1) * word_duration,
            "text": w,
        })
    cues = group_words_into_cues(words_data)
    return cues, "estimated", "low"


async def main_continuous(metadata_path: Path, voice: str, join_style: str = "period",
                          subtitle_provider: str = "estimated") -> int:
    data = load_metadata(str(metadata_path))
    scenes = data["script"]["scenes"]
    sdir = scenes_dir(metadata_path)
    sdir.mkdir(parents=True, exist_ok=True)

    scene_joins = {
        s["sceneNumber"]: s.get("joinToNext", "")
        for s in scenes if s.get("joinToNext")
    }
    full_text, narration_units = build_full_narration(
        scenes, join_style=join_style, scene_joins=scene_joins
    )
    if not full_text:
        print("ERROR: no voiceover text found")
        return 1

    print(f"Building continuous narration: {len(narration_units)} units, "
          f"{len(full_text)} chars, voice={voice}")

    output_path = sdir / "narration.mp3"
    cues, source, confidence, sentence_boundaries, matching_metrics = await generate_audio_with_timestamps(
        full_text, output_path, voice, narration_units=narration_units
    )

    if not cues or not source:
        print("ERROR: edge-tts returned no cues/timestamps for continuous audio")
        print(f"  SentenceBoundary count: {len(sentence_boundaries)}")
        print(f"  Narration units: {len(narration_units)}")
        return 1

    has_word_boundary = source and "word_boundary" in source.lower()
    has_sentence_boundary = source and "sentence_boundary" in source.lower()

    # Use native WordBoundary-based scene timings when word-level data is available
    words = getattr(cues, 'words', None) or _extract_words_from_cues(cues)
    native_timings = _compute_native_scene_timings(words, narration_units) if words else None

    if native_timings:
        scene_timings, timing_confidence, timing_status = native_timings
        timing_source_label = "native_word_boundary"
        print(f"  Native scene timings: {len(scene_timings)} scenes from word boundaries")
    elif has_word_boundary and narration_units:
        # WordBoundary data available but no sentence boundaries (edge-tts with boundary="WordBoundary")
        # Compute proportional scene timings from target durations, scaled to actual cue times
        total_target = sum(float(s.get("targetDurationSec", 5)) for s in scenes)
        timings = []
        current = 0.0
        for s in scenes:
            dur = float(s.get("targetDurationSec", 5))
            timings.append({
                "sceneNumber": s["sceneNumber"],
                "startSec": round(current, 3),
                "endSec": round(current + dur, 3),
            })
            current += dur
        if cues and total_target > 0:
            last_cue_end = max(c["endSec"] for c in cues)
            scale = last_cue_end / total_target if total_target > 0 else 1.0
            for t in timings:
                t["startSec"] = round(t["startSec"] * scale, 3)
                t["endSec"] = round(t["endSec"] * scale, 3)
        scene_timings = timings
        timing_confidence = "medium"
        timing_status = "PASS"
        timing_source_label = "proportional_word_boundary"
        print(f"  Proportional scene timings from WordBoundary: {len(scene_timings)} scenes")
    else:
        scene_timings, timing_confidence, timing_status = compute_scene_timings_by_sentences(
            narration_units, sentence_boundaries
        )
        timing_source_label = "sentence_boundary"

    if timing_status == "REVIEW_REQUIRED":
        print(f"WARNING: SentenceBoundary count mismatch or low similarity")
        print(f"  SentenceBoundary count: {len(sentence_boundaries)}")
        print(f"  Narration units: {len(narration_units)}")
        print(f"  Timing confidence: {timing_confidence}")
        print(f"  Status: REVIEW_REQUIRED — will not proceed to render")

    warnings: list[str] = []
    cues_by_scene: dict[int, list[dict]] = {}

    # ── Hybrid timing provider ─────────────────────────────────────────────
    def _assign_scene_numbers(raw_cues, scene_timings):
        for cue in raw_cues:
            cue["sceneNumber"] = None
            for st in scene_timings:
                if st["startSec"] <= cue["startSec"] < st["endSec"]:
                    cue["sceneNumber"] = st["sceneNumber"]
                    break
            if cue["sceneNumber"] is None and scene_timings:
                cue["sceneNumber"] = scene_timings[-1]["sceneNumber"]
        result = {}
        for sn in set(c.get("sceneNumber") for c in raw_cues):
            result[sn] = [c for c in raw_cues if c.get("sceneNumber") == sn]
        return result

    def _build_scene_groups(raw_cues, expected_total_scenes=None):
        groups = {}
        for c in raw_cues:
            sn = c.get("sceneNumber")
            if sn is not None:
                groups.setdefault(sn, []).append(c)
        # Fallback: if too few distinct scenes, assign by sequential position
        if expected_total_scenes and len(groups) < expected_total_scenes:
            null_cues = [c for c in raw_cues if c.get("sceneNumber") is None]
            if null_cues:
                groups.clear()
                cues_per_scene = max(1, len(raw_cues) // expected_total_scenes)
                for i, c in enumerate(raw_cues):
                    sn = min(i // cues_per_scene + 1, expected_total_scenes)
                    groups.setdefault(sn, []).append(c)
        return groups

    # ── Post-hoc cross-scene cue fix ────────────────────────────────────
    def _split_overflow_cues(cues_by_scene, scene_timings, tolerance=0.05):
        timing_map = {st["sceneNumber"]: st for st in scene_timings}
        result = {}
        for sn, cues in sorted(cues_by_scene.items()):
            st = timing_map.get(sn)
            if not st:
                result[sn] = list(cues)
                continue
            scene_end = st["endSec"]
            next_sn = sn + 1
            out = []
            overflow = []
            for c in cues:
                if c["endSec"] > scene_end + tolerance:
                    words = c["text"].split()
                    if len(words) <= 1:
                        out.append(c)
                        continue
                    dur = c["endSec"] - c["startSec"]
                    split_ratio = max(0.1, min(0.9, (scene_end - c["startSec"]) / dur))
                    split_idx = max(1, min(len(words) - 1, int(len(words) * split_ratio)))
                    left_text = " ".join(words[:split_idx])
                    right_text = " ".join(words[split_idx:])
                    dur_per_word = dur / len(words)
                    split_sec = round(c["startSec"] + dur_per_word * split_idx, 3)
                    left = {"startSec": c["startSec"], "endSec": round(min(scene_end, split_sec), 3), "text": left_text}
                    right = {"startSec": split_sec, "endSec": c["endSec"], "text": right_text}
                    out.append(left)
                    overflow.append(right)
                else:
                    out.append(c)
            result[sn] = result.get(sn, []) + out
            if overflow and next_sn in timing_map:
                result[next_sn] = overflow + result.get(next_sn, [])
        return result

    whisper_available = False
    try:
        import faster_whisper  # noqa
        whisper_available = True
    except ImportError:
        pass

    if subtitle_provider == "edge_tts" or (subtitle_provider == "auto" and has_word_boundary):
        # Edge TTS native WordBoundary as primary source
        # Prefer canonical scene numbers from cue grouping; fall back to proportional timing
        has_canonical_scenes = any(c.get("sceneNumber") is not None for c in cues)
        if has_canonical_scenes:
            expected_scenes = len(scenes)
            cues_by_scene = _build_scene_groups(cues, expected_scenes)
            expected = expected_scenes
            actual = len(cues_by_scene)
            if actual < expected:
                print(f"  WARNING: expected {expected} scenes but canonical grouping produced {actual}")
            print(f"  Canonical cue grouping: {sum(len(v) for v in cues_by_scene.values())} cues")
        else:
            cues_by_scene = _assign_scene_numbers(cues, scene_timings)
        cues_by_scene = _split_overflow_cues(cues_by_scene, scene_timings)
        print(f"  Edge TTS WordBoundary: {sum(len(v) for v in cues_by_scene.values())} cues, source={source}")

    elif subtitle_provider == "whisper" or (subtitle_provider == "auto" and whisper_available):
        try:
            from shorts_creator.audio.whisper import align_with_canonical_text
            w_cues_by_scene, wsource, wconfidence, w_warnings = align_with_canonical_text(
                audio_path=str(output_path),
                canonical_scenes=[
                    {"sceneNumber": s["sceneNumber"], "voiceover": s.get("voiceover", "")}
                    for s in scenes
                ],
                scene_timings=scene_timings,
            )
            warnings = w_warnings
            if wsource.startswith("whisper"):
                cues_by_scene = w_cues_by_scene
                source = wsource
                confidence = wconfidence
                total = sum(len(v) for v in cues_by_scene.values())
                print(f"  Whisper reconciled: {total} cues, source={source}, confidence={confidence}")
                for w in warnings:
                    print(f"    Warning: {w}")
            else:
                print("  Whisper fell back to estimated mode. Falling through to edge-tts cues.")
                cues_by_scene = _assign_scene_numbers(cues, scene_timings)
                cues_by_scene = _split_overflow_cues(cues_by_scene, scene_timings)
        except ImportError:
            print("WARNING: faster-whisper not installed. Falling through to edge-tts cues.")
            cues_by_scene = _assign_scene_numbers(cues, scene_timings)
            cues_by_scene = _split_overflow_cues(cues_by_scene, scene_timings)
        except Exception as e:
            print(f"WARNING: whisper failed ({e}). Falling through to edge-tts cues.")
            import traceback
            traceback.print_exc()
            cues_by_scene = _assign_scene_numbers(cues, scene_timings)
            cues_by_scene = _split_overflow_cues(cues_by_scene, scene_timings)

    else:
        # estimated mode or auto with no WordBoundary and no whisper
        cues_by_scene = _assign_scene_numbers(cues, scene_timings)
        cues_by_scene = _split_overflow_cues(cues_by_scene, scene_timings)

    audio_dur = 0.0
    try:
        import subprocess as _sp
        _env = os.environ.copy()
        _env.pop("DOCKER_API_VERSION", None)
        video_dir_name = metadata_path.parent.name
        r = _sp.run([
            "docker", "run", "--rm",
            "-v", f"{metadata_path.parents[3]}:/workspace",
            "--entrypoint", "ffprobe",
            "linuxserver/ffmpeg:latest",
            "-v", "quiet", "-print_format", "json", "-show_format",
            f"/workspace/data/videos/{video_dir_name}/scenes/narration.mp3"
        ], capture_output=True, text=True, timeout=30, env=_env)
        audio_dur = float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        pass

    # ── Rescale proportional scene timings to actual audio duration ──
    if scene_timings and audio_dur > 0 and timing_source_label == "proportional_word_boundary":
        last_end = scene_timings[-1]["endSec"]
        if last_end > 0 and abs(last_end - audio_dur) > 0.10:
            scale = audio_dur / last_end
            for t in scene_timings:
                t["startSec"] = round(t["startSec"] * scale, 3)
                t["endSec"] = round(t["endSec"] * scale, 3)
            print(f"  Rescaled proportional scene timings to audio duration ({last_end:.3f}→{audio_dur:.3f}s, scale={scale:.4f})")

    # ── Duration contract validation ──────────────────────────────────
    DEFAULT_DURATION_CONTRACT = {
        "targetSec": 28,
        "minSec": 25,
        "maxSec": 30,
        "strictness": "balanced",
    }
    raw_request = data.get("request", {})
    dur_cfg = raw_request.get("duration", DEFAULT_DURATION_CONTRACT)
    target = dur_cfg.get("targetSec", 28)
    min_sec = dur_cfg.get("minSec", 25)
    max_sec = dur_cfg.get("maxSec", 30)
    strictness = dur_cfg.get("strictness", "balanced")

    duration_validation = {"targetSec": target, "actualSec": round(audio_dur, 3)}
    duration_errors = []
    if strictness == "strict":
        margin = target * 0.10
        if audio_dur < target - margin:
            duration_errors.append(f"audio={audio_dur:.1f}s < target={target}s - 10%")
        elif audio_dur > target + margin:
            duration_errors.append(f"audio={audio_dur:.1f}s > target={target}s + 10%")
    elif strictness == "balanced":
        if audio_dur < min_sec:
            duration_errors.append(f"audio={audio_dur:.1f}s < minSec={min_sec}s")
        elif audio_dur > max_sec:
            duration_errors.append(f"audio={audio_dur:.1f}s > maxSec={max_sec}s")
    # relaxed: always pass

    duration_validation["errors"] = duration_errors
    duration_validation["status"] = "FAIL" if duration_errors else "PASS"
    if duration_errors:
        print(f"DURATION CONTRACT: {'; '.join(duration_errors)}")
        duration_validation["strictness"] = strictness

    data["durationValidation"] = duration_validation

    # ── Apply SUBTITLE_GLOBAL_OFFSET_MS if set ──────────────────────────
    offset_ms = int(_ENV.get("SUBTITLE_GLOBAL_OFFSET_MS", "0"))
    if offset_ms != 0:
        offset_sec = offset_ms / 1000.0
        for sn, scene_cues in cues_by_scene.items():
            for cue in scene_cues:
                cue["startSec"] = round(max(0, cue["startSec"] + offset_sec), 3)
                cue["endSec"] = round(max(0, cue["endSec"] + offset_sec), 3)
        print(f"  Applied SUBTITLE_GLOBAL_OFFSET_MS={offset_ms} ({offset_sec:+.3f}s) to all cues")

    # Derive overall confidence from canonical matching quality
    matching_conf = matching_metrics.get("confidence", "medium")
    if matching_conf == "low":
        overall_confidence = "low"
    elif matching_conf == "medium" or timing_confidence == "medium":
        overall_confidence = "medium"
    else:
        overall_confidence = "high"

    audio_entry = {
        "provider": "edge_tts",
        "voice": voice,
        "continuous": True,
        "path": str(output_path),
        "durationSec": round(audio_dur, 3) if audio_dur else 0,
        "narrationUnits": narration_units,
        "sceneTimings": scene_timings,
        "timingConfidence": overall_confidence,
        "timingSource": source,
        "timingProvider": subtitle_provider,
        "globalOffsetMs": offset_ms,
        "canonicalMatching": matching_metrics,
    }
    data["audio"] = audio_entry

    for scene_data in scenes:
        sn = scene_data["sceneNumber"]
        scene_cues = cues_by_scene.get(sn, [])
        # Remove sceneNumber from individual cues (stored in parent)
        for c in scene_cues:
            c.pop("sceneNumber", None)
        scene_timing_entry = {
            "timingSource": source,
            "timingConfidence": confidence,
            "cues": scene_cues,
        }
        scene_data["subtitleTiming"] = scene_timing_entry

    data["updatedAt"] = datetime.now(timezone.utc).isoformat()

    duration_pass = len(duration_validation.get("errors", [])) == 0
    canonical_pass = matching_conf != "low"
    if timing_status == "PASS" and duration_pass and canonical_pass:
        data["status"] = "AUDIO_READY"
    else:
        reasons = []
        if timing_status != "PASS":
            reasons.append("timing")
        if not duration_pass:
            reasons.append(f"duration: {'; '.join(duration_validation.get('errors', []))}")
        if not canonical_pass:
            reasons.append(f"canonicalMatching: confidence={matching_conf}")
        data["status"] = "REVIEW_REQUIRED"
        data["reviewReasons"] = reasons
        print(f"REVIEW_REQUIRED: {'; '.join(reasons)}")

    save_metadata(str(metadata_path), data)

    total_cues = sum(len(v) for v in cues_by_scene.values())
    print(json.dumps({
        "jobId": data["jobId"],
        "continuous": True,
        "audioDurationSec": audio_dur,
        "narrationUnits": len(narration_units),
        "sentenceBoundaries": len(sentence_boundaries),
        "sceneTimings": scene_timings,
        "timingConfidence": timing_confidence,
        "cues": total_cues,
        "source": source,
        "status": data["status"],
    }))
    return 0 if data["status"] == "AUDIO_READY" else 1


async def main_per_scene(
    metadata_path: Path,
    voice: str,
    *,
    force_regenerate: bool = False,
    tts_provider: str = "edge_tts",
    subtitle_timing_provider: str = "auto",
) -> int:
    data = load_metadata(str(metadata_path))
    job_id = data["jobId"]
    scenes = data["script"]["scenes"]

    sdir = scenes_dir(metadata_path)
    sdir.mkdir(parents=True, exist_ok=True)

    results = []
    for scene in scenes:
        scene_num = int(scene["sceneNumber"])
        text = scene.get("voiceover", "").strip()
        if not text:
            print(f"  scene {scene_num}: no voiceover, skipping")
            results.append({"sceneNumber": scene_num, "success": False, "timing": None})
            continue

        dest = sdir / f"scene-{scene_num:02}.mp3"
        subtitle_timing = None

        if not force_regenerate and dest.exists() and dest.stat().st_size > 1000:
            duration = float(scene.get("targetDurationSec", 5))
            cues, source, confidence = estimate_cues_uniform(text, duration)
            subtitle_timing = {
                "timingSource": source,
                "timingConfidence": confidence,
                "cues": cues,
            }
            print(f"  scene {scene_num}: audio exists, {source} ({len(cues)} cues)")
            results.append({"sceneNumber": scene_num, "success": True, "timing": subtitle_timing})
            continue

        cues, source, confidence, _, _ = await generate_audio_with_timestamps(text, dest, voice)

        if cues and source:
            subtitle_timing = {
                "timingSource": source,
                "timingConfidence": confidence,
                "cues": cues,
            }
        else:
            duration = float(scene.get("targetDurationSec", 5))
            cues, source, confidence = estimate_cues_uniform(text, duration)
            subtitle_timing = {
                "timingSource": source,
                "timingConfidence": confidence,
                "cues": cues,
            }

        ok = dest.exists() and dest.stat().st_size > 1000
        status = "OK" if ok else "FAIL"
        print(f"  scene {scene_num}: {status} ({subtitle_timing['timingSource']}, "
              f"{len(subtitle_timing['cues'])} cues, {voice})")
        results.append({"sceneNumber": scene_num, "success": ok, "timing": subtitle_timing})

    all_ok = all(r["success"] for r in results)

    audio_scenes = []
    any_duration_missing = False
    missing_duration_scenes: list[int] = []
    for r in results:
        sn = r["sceneNumber"]
        mp3_path = sdir / f"scene-{sn:02}.mp3"
        duration_sec = None
        duration_source = None
        if r["success"]:
            dur, source = _get_mp3_duration(mp3_path)
            if dur is not None:
                duration_sec = round(dur, 3)
                duration_source = source
            else:
                print(f"WARNING: could not probe duration for {mp3_path.name}")
                any_duration_missing = True
                missing_duration_scenes.append(sn)
        audio_scenes.append({
            "sceneNumber": sn,
            "path": str(mp3_path),
            "exists": r["success"],
            "durationSec": duration_sec,
            "durationSource": duration_source,
        })

    duration_estimated = any_duration_missing
    data["audio"] = {
        "provider": tts_provider,
        "voice": voice,
        "timingProvider": subtitle_timing_provider,
        "continuous": False,
        "scenes": audio_scenes,
        "duration_estimated": duration_estimated,
    }

    for scene_data in data["script"]["scenes"]:
        sn = scene_data["sceneNumber"]
        for r in results:
            if r["sceneNumber"] == sn and r["timing"]:
                scene_data["subtitleTiming"] = r["timing"]
                break

    # Compute active audio duration from cues
    scene_by_num = {s["sceneNumber"]: s for s in data["script"]["scenes"]}
    for entry in audio_scenes:
        sn = entry["sceneNumber"]
        sd = scene_by_num.get(sn)
        physical = entry.get("durationSec")
        if sd is not None and physical is not None and physical > 0:
            active = _compute_active_audio_duration(sd, physical)
            if active is not None:
                entry["activeAudioDurationSec"] = active
                entry["activeDurationSource"] = "edge_tts_last_cue_plus_guard"
            else:
                entry["activeAudioDurationSec"] = None
        else:
            entry["activeAudioDurationSec"] = None

    data["updatedAt"] = datetime.now(timezone.utc).isoformat()

    if all_ok and not any_duration_missing:
        data["status"] = "AUDIO_READY"
        exit_code = 0
    elif any_duration_missing and all_ok:
        data["status"] = "REVIEW_REQUIRED"
        reasons = data.setdefault("reviewReasons", [])
        reasons.append(
            f"AUDIO_DURATION_MISSING: scenes {missing_duration_scenes} lack valid measured duration"
        )
        exit_code = 0
    else:
        data["status"] = "REVIEW_REQUIRED"
        reasons = data.setdefault("reviewReasons", [])
        if any_duration_missing:
            reasons.append(
                f"AUDIO_DURATION_MISSING: scenes {missing_duration_scenes} lack valid measured duration"
            )
        if not all_ok:
            failed = [r["sceneNumber"] for r in results if not r["success"]]
            reasons.append(
                f"AUDIO_GENERATION_FAILED: scenes {failed} did not produce valid MP3"
            )
        exit_code = 1

    save_metadata(str(metadata_path), data)

    cue_counts = {r["sceneNumber"]: len(r["timing"]["cues"]) if r["timing"] else 0 for r in results}
    sources = {r["sceneNumber"]: r["timing"]["timingSource"] if r["timing"] else "none" for r in results}
    print(json.dumps({
        "jobId": job_id,
        "success": data["status"] == "AUDIO_READY",
        "status": data["status"],
        "cueCounts": cue_counts,
        "sources": sources,
    }))
    return exit_code


def get_audio_defaults() -> dict[str, str]:
    """Return environment-derived defaults used by the CLI adapter."""
    return {
        "voice": _ENV.get("TTS_VOICE", "es-ES-AlvaroNeural"),
        "tts_provider": _ENV.get("TTS_PROVIDER", "edge_tts"),
        "subtitle_timing_provider": (
            _ENV.get("SUBTITLE_TIMING_PROVIDER")
            or _ENV.get("SUBTITLE_PROVIDER", "auto")
        ),
    }


def resolve_audio_regeneration_config(metadata: dict) -> dict[str, str]:
    """Resolve the effective per-scene audio configuration from job metadata."""
    defaults = get_audio_defaults()
    audio = metadata.get("audio", {})
    request = metadata.get("request", {})
    request_voice = request.get("voice", {}) if isinstance(request, dict) else {}
    request_subtitles = request.get("subtitles", {}) if isinstance(request, dict) else {}
    return {
        "tts_provider": audio.get("provider") or request_voice.get("provider") or defaults["tts_provider"],
        "voice": audio.get("voice") or request_voice.get("voiceId") or defaults["voice"],
        "subtitle_timing_provider": audio.get("timingProvider") or request_subtitles.get("timingProvider") or defaults["subtitle_timing_provider"],
    }


async def generate_audio(
    *,
    metadata_path: str | Path,
    voice: str,
    tts_provider: str,
    subtitle_timing_provider: str,
    continuous: bool = False,
    join_style: str = "period",
    force_regenerate: bool = False,
) -> int:
    """Generate audio artifacts and update metadata for one job."""
    resolved_metadata_path = Path(metadata_path).resolve()

    if tts_provider != "edge_tts":
        provider = get_provider(tts_provider, voice=voice)
        if not provider.is_available():
            print(f"ERROR: TTS provider '{tts_provider}' is not available")
            return 1

    if continuous:
        return await main_continuous(
            resolved_metadata_path,
            voice,
            join_style=join_style,
            subtitle_provider=subtitle_timing_provider,
        )
    return await main_per_scene(
        resolved_metadata_path, voice, force_regenerate=force_regenerate,
        tts_provider=tts_provider, subtitle_timing_provider=subtitle_timing_provider,
    )
