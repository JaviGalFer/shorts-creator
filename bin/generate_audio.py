#!/usr/bin/env python3

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tts_provider import get_provider, TTSOptions

TICK = 10_000_000

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
        cues.append({
            "startSec": round(buffer_start, 3),
            "endSec": round(buffer[-1]["endSec"], 3),
            "text": text,
        })
        buffer = []
        buffer_start = None

    for w in words:
        word_text = w["text"].strip()
        if not word_text:
            continue

        # Scene boundary enforcement: flush if next word belongs to a different scene
        if buffer and w.get("sceneNumber") is not None and buffer[0].get("sceneNumber") is not None:
            if w["sceneNumber"] != buffer[0]["sceneNumber"]:
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
                final.append({"startSec": cue["startSec"], "endSec": round(split_sec, 3), "text": t1})
                final.append({"startSec": round(split_sec, 3), "endSec": cue["endSec"], "text": t2})
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
                                         scene_timings_for_words: list[dict] | None = None):
    provider = get_provider("edge_tts", voice=voice)
    options = TTSOptions(voice=voice)

    try:
        result = await provider.synthesize_with_timing_async(text, str(output_path), options)
    except ImportError:
        print("ERROR: edge-tts not installed. Run: pip install edge-tts")
        return None, None, None, []

    td = result.timing_data or {}
    word_boundaries = td.get("word_boundaries", [])
    sentence_boundaries = td.get("sentence_boundaries", [])
    timing_source = td.get("timing_source", "")

    if word_boundaries:
        annotated = _annotate_word_punctuation(word_boundaries, text)
        if scene_timings_for_words:
            annotated = _assign_words_to_scenes(annotated, scene_timings_for_words)
        cues = group_words_into_cues(annotated, sentence_boundaries)
        return cues, timing_source or "edge_tts_word_boundary", "high", sentence_boundaries

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
            return cues, timing_source or "edge_tts_sentence_boundary", "medium", sentence_boundaries

    return None, None, None, sentence_boundaries


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
    data = json.loads(metadata_path.read_text())
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
    cues, source, confidence, sentence_boundaries = await generate_audio_with_timestamps(
        full_text, output_path, voice
    )

    if not cues or not source:
        print("ERROR: edge-tts returned no cues/timestamps for continuous audio")
        print(f"  SentenceBoundary count: {len(sentence_boundaries)}")
        print(f"  Narration units: {len(narration_units)}")
        return 1

    # Use native WordBoundary-based scene timings when word-level data is available
    words = getattr(cues, 'words', None) or _extract_words_from_cues(cues)
    native_timings = _compute_native_scene_timings(words, narration_units) if words else None

    if native_timings:
        scene_timings, timing_confidence, timing_status = native_timings
        timing_source_label = "native_word_boundary"
        print(f"  Native scene timings: {len(scene_timings)} scenes from word boundaries")
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

    has_word_boundary = source and "word_boundary" in source.lower()
    has_sentence_boundary = source and "sentence_boundary" in source.lower()
    whisper_available = False
    try:
        import faster_whisper  # noqa
        whisper_available = True
    except ImportError:
        pass

    if subtitle_provider == "edge_tts" or (subtitle_provider == "auto" and has_word_boundary):
        # Edge TTS native WordBoundary as primary source
        cues_by_scene = _assign_scene_numbers(cues, scene_timings)
        cues_by_scene = _split_overflow_cues(cues_by_scene, scene_timings)
        print(f"  Edge TTS WordBoundary: {sum(len(v) for v in cues_by_scene.values())} cues, source={source}")

    elif subtitle_provider == "whisper" or (subtitle_provider == "auto" and whisper_available):
        try:
            from whisper_subtitles import align_with_canonical_text
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
        _env["DOCKER_API_VERSION"] = "1.43"
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

    # ── Duration contract validation ──────────────────────────────────
    DEFAULT_DURATION_CONTRACT = {
        "targetSec": 35,
        "minSec": 30,
        "maxSec": 40,
        "strictness": "balanced",
    }
    raw_request = data.get("request", {})
    dur_cfg = raw_request.get("duration", DEFAULT_DURATION_CONTRACT)
    target = dur_cfg.get("targetSec", 35)
    min_sec = dur_cfg.get("minSec", 30)
    max_sec = dur_cfg.get("maxSec", 40)
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

    audio_entry = {
        "provider": "edge_tts",
        "voice": voice,
        "continuous": True,
        "path": str(output_path),
        "durationSec": round(audio_dur, 3) if audio_dur else 0,
        "narrationUnits": narration_units,
        "sceneTimings": scene_timings,
        "timingConfidence": timing_confidence,
        "timingSource": source,
        "timingProvider": subtitle_provider,
        "globalOffsetMs": offset_ms,
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
    if timing_status == "PASS" and duration_pass:
        data["status"] = "AUDIO_READY"
    else:
        reasons = []
        if timing_status != "PASS":
            reasons.append("timing")
        if not duration_pass:
            reasons.append(f"duration: {'; '.join(duration_validation.get('errors', []))}")
        data["status"] = "REVIEW_REQUIRED"
        data["reviewReasons"] = reasons
        print(f"REVIEW_REQUIRED: {'; '.join(reasons)}")

    metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

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


async def main_per_scene(metadata_path: Path, voice: str) -> int:
    data = json.loads(metadata_path.read_text())
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

        if dest.exists() and dest.stat().st_size > 1000:
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

        cues, source, confidence, _ = await generate_audio_with_timestamps(text, dest, voice)

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
    data["audio"] = {
        "provider": "edge-tts",
        "continuous": False,
        "scenes": [
            {
                "sceneNumber": r["sceneNumber"],
                "path": str(sdir / f"scene-{r['sceneNumber']:02}.mp3"),
                "exists": r["success"],
            }
            for r in results
        ],
    }

    for scene_data in data["script"]["scenes"]:
        sn = scene_data["sceneNumber"]
        for r in results:
            if r["sceneNumber"] == sn and r["timing"]:
                scene_data["subtitleTiming"] = r["timing"]
                break

    data["updatedAt"] = datetime.now(timezone.utc).isoformat()
    if all_ok:
        data["status"] = "AUDIO_READY"
    metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    cue_counts = {r["sceneNumber"]: len(r["timing"]["cues"]) if r["timing"] else 0 for r in results}
    sources = {r["sceneNumber"]: r["timing"]["timingSource"] if r["timing"] else "none" for r in results}
    print(json.dumps({"jobId": job_id, "success": all_ok, "cueCounts": cue_counts, "sources": sources}))
    return 0 if all_ok else 1


async def main_async() -> int:
    import os as _os
    _os.environ['DOCKER_API_VERSION'] = '1.43'
    default_voice = _ENV.get("TTS_VOICE", "es-ES-AlvaroNeural")
    default_provider = _ENV.get("TTS_PROVIDER", "edge_tts")
    default_subtitle = _ENV.get("SUBTITLE_TIMING_PROVIDER") or _ENV.get("SUBTITLE_PROVIDER", "auto")

    parser = argparse.ArgumentParser()
    parser.add_argument("metadata_path")
    parser.add_argument("--voice", default=default_voice)
    parser.add_argument("--tts-provider", default=default_provider,
                        choices=["edge_tts", "elevenlabs"],
                        help=f"TTS provider (default: {default_provider}, from TTS_PROVIDER env)")
    parser.add_argument("--subtitle-timing-provider", default=default_subtitle,
                        choices=["auto", "edge_tts", "whisper", "estimated"],
                        help=f"Subtitle timing source (default: {default_subtitle}, from SUBTITLE_TIMING_PROVIDER or SUBTITLE_PROVIDER env). "
                             "auto = prefer edge-tts WordBoundary, fallback whisper, then estimated")
    parser.add_argument("--continuous", action="store_true",
                        help="Generate single narration MP3 for the whole job")
    parser.add_argument("--join-style", choices=["period", "semicolon", "comma"],
                        default="period",
                        help="Punctuation between scenes. Only 'period' works with SentenceBoundary detection. "
                             "semicolon/comma break SentenceBoundary matching (edge-tts behavior). "
                             "Use scene.joinToNext for custom connectors.")
    args = parser.parse_args()
    subtitle_provider = args.subtitle_timing_provider  # alias for compatibility

    metadata_path = Path(args.metadata_path).resolve()

    if args.tts_provider != "edge_tts":
        provider = get_provider(args.tts_provider, voice=args.voice)
        if not provider.is_available():
            print(f"ERROR: TTS provider '{args.tts_provider}' is not available")
            return 1

    if args.continuous:
        return await main_continuous(
            metadata_path, args.voice, join_style=args.join_style,
            subtitle_provider=args.subtitle_timing_provider,
        )
    else:
        return await main_per_scene(metadata_path, args.voice)


def main():
    try:
        return asyncio.run(main_async())
    except ImportError:
        print("ERROR: edge-tts not installed. Run: pip install edge-tts")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
