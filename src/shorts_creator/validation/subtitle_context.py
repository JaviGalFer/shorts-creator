#!/usr/bin/env python3
"""Shared per-scene subtitle validation for non-continuous audio.

Provides a single validation context used by both render_job.py (quality gate)
and validate_job.py (post-hoc validation), ensuring both use the same offset
and timing logic.

Continuous audio: delegates to legacy coverage_validation module.
Non-continuous audio: builds per-scene context from renderTimeline +
audio.scenes[], computes global cue offsets, validates against subtitle.ass.
"""

from __future__ import annotations

import difflib
import json
import math
import re
from pathlib import Path
from typing import Any

from shorts_creator.validation.subtitle_normalize import normalize_subtitle_text


# ── Public API ──────────────────────────────────────────────────────────


def build_validation_context(
    metadata: dict,
    video_dir: Path | None = None,
) -> dict:
    """Return a standardized validation context dict.

    Fields:
      mode: "continuous" | "per_scene"
      status: "PASS" | "FAIL" | "REVIEW_REQUIRED"
      totalCues: int
      errors: list[str]
      warnings: list[str]
      globalCues: list[dict]  (only in per_scene mode)
      coveragePercent: float  (only in continuous mode)
    """
    audio_config = metadata.get("audio", {})
    is_continuous = audio_config.get("continuous", False)

    if is_continuous:
        return _build_continuous_context(metadata)
    else:
        return _build_per_scene_context(metadata, video_dir)


# ── Continuous mode ─────────────────────────────────────────────────────


def _build_continuous_context(metadata: dict) -> dict:
    from shorts_creator.validation.coverage import run_coverage_validation

    audio_config = metadata.get("audio", {})
    scene_timings = audio_config.get("sceneTimings", [])
    audio_dur = audio_config.get("durationSec", 0)
    cues_by_scene: dict[int, list[dict]] = {}
    for sc in metadata.get("script", {}).get("scenes", []):
        sn = sc["sceneNumber"]
        cues_by_scene[sn] = sc.get("subtitleTiming", {}).get("cues", [])
    narration_units = audio_config.get("narrationUnits", [])

    result = run_coverage_validation(
        scene_timings, audio_dur, cues_by_scene, narration_units
    )

    total_cues = sum(len(c) for c in cues_by_scene.values())
    return {
        "mode": "continuous",
        "status": result.get("status", "N/A"),
        "totalCues": total_cues,
        "errors": _flatten_errors(result),
        "warnings": result.get("coverage", {}).get("warnings", []),
        "coveragePercent": result.get("coverage", {}).get("coveragePercent", 0),
    }


# ── Per-scene mode ──────────────────────────────────────────────────────


def _build_per_scene_context(
    metadata: dict,
    video_dir: Path | None = None,
) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    scenes = metadata.get("script", {}).get("scenes", [])
    render_timeline = metadata.get("renderTimeline", [])
    audio_config = metadata.get("audio", {})
    audio_scenes = audio_config.get("scenes", [])

    # 1. Build scene windows from renderTimeline
    scene_windows = _build_scene_windows(render_timeline, errors)
    audio_duration_map = _build_audio_duration_map(audio_scenes, errors)

    # 2. Validate scene windows and audio durations
    _validate_scene_context(scenes, scene_windows, audio_duration_map, errors)

    # 3. Validate local cues
    all_local_cues: list[dict] = []
    for scene in scenes:
        sn = scene["sceneNumber"]
        cues = scene.get("subtitleTiming", {}).get("cues", [])
        window = scene_windows.get(sn)
        audio_dur = audio_duration_map.get(sn)
        _validate_local_cues(sn, cues, audio_dur, errors, warnings)
        for c in cues:
            all_local_cues.append({"sceneNumber": sn, "cue": c})

    if not all_local_cues:
        warnings.append("No subtitle timing cues found")
        return {
            "mode": "per_scene",
            "status": "FAIL" if errors else "PASS",
            "totalCues": 0,
            "errors": errors,
            "warnings": warnings,
            "globalCues": [],
        }

    # 4. Build global cues with offsets
    global_cues = _build_global_cues(all_local_cues, scene_windows, errors)

    # 5. Validate global cues (monotonic, cross-scene overlap, within window)
    _validate_global_cues(global_cues, scene_windows, errors)

    # 6. Validate text per scene (not using narrationUnits)
    _validate_cue_text_per_scene(scenes, errors, warnings)

    # 7. Validate against subtitle.ass if available
    if video_dir:
        ass_path = video_dir / "subtitle.ass"
        if ass_path.exists():
            _validate_ass_dialogues(ass_path, global_cues, scenes, scene_windows, errors)

    status = "FAIL" if errors else ("REVIEW_REQUIRED" if warnings else "PASS")
    return {
        "mode": "per_scene",
        "status": status,
        "totalCues": len(global_cues),
        "errors": errors,
        "warnings": warnings,
        "globalCues": global_cues,
    }


# ── Scene windows ───────────────────────────────────────────────────────


def _build_scene_windows(
    render_timeline: list[dict],
    errors: list[str],
) -> dict[int, dict[str, float]]:
    windows: dict[int, dict[str, float]] = {}
    if not render_timeline:
        errors.append("renderTimeline is empty")
        return windows

    for entry in render_timeline:
        sn = entry.get("sceneNumber")
        start = entry.get("startSec", 0)
        end = entry.get("endSec", 0)
        if sn is None:
            errors.append(f"renderTimeline entry missing sceneNumber: {entry}")
            continue
        if sn not in windows:
            windows[sn] = {"startSec": float(start), "endSec": float(end)}
        else:
            windows[sn]["startSec"] = min(windows[sn]["startSec"], float(start))
            windows[sn]["endSec"] = max(windows[sn]["endSec"], float(end))
    return windows


def _build_audio_duration_map(
    audio_scenes: list[dict],
    errors: list[str],
) -> dict[int, float]:
    dur_map: dict[int, float] = {}
    seen = set()
    for entry in audio_scenes:
        sn = entry.get("sceneNumber")
        dur = entry.get("durationSec")
        if sn is None:
            errors.append(f"audio.scenes entry missing sceneNumber: {entry}")
            continue
        if sn in seen:
            errors.append(f"audio.scenes: duplicate sceneNumber {sn}")
            continue
        seen.add(sn)
        if not isinstance(dur, (int, float)) or isinstance(dur, bool):
            errors.append(f"audio.scenes scene {sn}: durationSec is not numeric (got {type(dur).__name__})")
            continue
        if not math.isfinite(dur):
            errors.append(f"audio.scenes scene {sn}: durationSec is not finite")
            continue
        if dur <= 0:
            errors.append(f"audio.scenes scene {sn}: durationSec={dur} <= 0")
            continue
        dur_map[sn] = float(dur)
    return dur_map


def _validate_scene_context(
    scenes: list[dict],
    scene_windows: dict[int, dict[str, float]],
    audio_duration_map: dict[int, float],
    errors: list[str],
) -> None:
    for scene in scenes:
        sn = scene["sceneNumber"]
        if sn <= 0:
            errors.append(f"Scene {sn}: sceneNumber must be positive")
            continue
        window = scene_windows.get(sn)
        if not window:
            errors.append(f"Scene {sn}: no renderTimeline entry")
            continue
        sw = window["endSec"] - window["startSec"]
        if sw <= 0 or not math.isfinite(sw):
            errors.append(f"Scene {sn}: scene window {sw} is not a positive finite number")
            continue
        aud = audio_duration_map.get(sn)
        if aud is None:
            errors.append(f"Scene {sn}: no valid audio duration in audio.scenes[]")
        elif aud <= 0 or not math.isfinite(aud):
            errors.append(f"Scene {sn}: audio duration {aud} is invalid")


# ── Local cue validation ────────────────────────────────────────────────


def _validate_local_cues(
    scene_number: int,
    cues: list[dict],
    audio_duration_sec: float | None,
    errors: list[str],
    warnings: list[str],
) -> None:
    if not cues:
        warnings.append(f"Scene {scene_number}: no cues")
        return

    sorted_cues = list(cues)

    for i, cue in enumerate(sorted_cues):
        start = cue.get("startSec")
        end = cue.get("endSec")

        if isinstance(start, bool) or isinstance(end, bool):
            errors.append(
                f"Scene {scene_number} cue {i}: startSec={start} or endSec={end} is bool"
            )
            continue

        if not isinstance(start, (int, float)):
            errors.append(
                f"Scene {scene_number} cue {i}: startSec={start} is not numeric"
            )
            continue
        if not isinstance(end, (int, float)):
            errors.append(
                f"Scene {scene_number} cue {i}: endSec={end} is not numeric"
            )
            continue
        if not math.isfinite(start) or not math.isfinite(end):
            errors.append(
                f"Scene {scene_number} cue {i}: startSec={start} endSec={end} is not finite"
            )
            continue
        if start < 0:
            errors.append(
                f"Scene {scene_number} cue {i}: startSec={start:.3f} < 0"
            )
        if end <= start:
            errors.append(
                f"Scene {scene_number} cue {i}: startSec={start:.3f} >= endSec={end:.3f}"
            )
        if audio_duration_sec is not None and end > audio_duration_sec + 0.1:
            errors.append(
                f"Scene {scene_number} cue {i}: endSec={end:.3f} exceeds audio duration "
                f"{audio_duration_sec:.3f} (tolerance 0.1s)"
            )

        if start > 6.0:
            warnings.append(
                f"Scene {scene_number} cue {i}: starts at {start:.1f}s (late start)"
            )

    if len(sorted_cues) >= 2:
        for i in range(1, len(sorted_cues)):
            prev = sorted_cues[i - 1]
            curr = sorted_cues[i]
            pe = prev.get("endSec", 0)
            cs = curr.get("startSec", 0)
            if isinstance(pe, (int, float)) and isinstance(cs, (int, float)):
                if not isinstance(pe, bool) and not isinstance(cs, bool):
                    if cs < pe:
                        errors.append(
                            f"Scene {scene_number} cue {i}: startSec={cs:.3f} < "
                            f"previous endSec={pe:.3f} (local overlap)"
                        )


# ── Global cues ─────────────────────────────────────────────────────────


def _build_global_cues(
    all_local_cues: list[dict],
    scene_windows: dict[int, dict[str, float]],
    errors: list[str],
) -> list[dict]:
    global_cues: list[dict] = []

    for entry in all_local_cues:
        sn = entry["sceneNumber"]
        cue = entry["cue"]
        window = scene_windows.get(sn)

        local_start = cue.get("startSec")
        local_end = cue.get("endSec")
        text = cue.get("text", "")

        if window is None:
            errors.append(f"Scene {sn}: no window for cue offset")
            continue

        if not isinstance(local_start, (int, float)) or isinstance(local_start, bool):
            continue
        if not isinstance(local_end, (int, float)) or isinstance(local_end, bool):
            continue

        scene_start = window["startSec"]
        scene_end = window["endSec"]

        global_start = round(scene_start + float(local_start), 3)
        global_end = round(scene_start + float(local_end), 3)

        global_cues.append({
            "sceneNumber": sn,
            "startSec": global_start,
            "endSec": global_end,
            "text": text,
            "localStartSec": float(local_start),
            "localEndSec": float(local_end),
        })

    return global_cues


def _validate_global_cues(
    global_cues: list[dict],
    scene_windows: dict[int, dict[str, float]],
    errors: list[str],
) -> None:
    if not global_cues:
        return

    sorted_cues = sorted(global_cues, key=lambda c: c["startSec"])

    for i in range(1, len(sorted_cues)):
        prev = sorted_cues[i - 1]
        curr = sorted_cues[i]
        prev_end = prev["endSec"]
        curr_start = curr["startSec"]
        if curr_start < prev_end - 0.1:
            errors.append(
                f"Cross-scene cue overlap: scene {prev['sceneNumber']} cue "
                f"ends at {prev_end:.3f}s, scene {curr['sceneNumber']} cue "
                f"starts at {curr_start:.3f}s (overlap={prev_end - curr_start:.3f}s)"
            )

    for i, cue in enumerate(sorted_cues):
        sn = cue["sceneNumber"]
        window = scene_windows.get(sn)
        if window:
            if cue["endSec"] > window["endSec"] + 0.1:
                errors.append(
                    f"Global cue {i} (scene {sn}): endSec={cue['endSec']:.3f} > "
                    f"scene window end {window['endSec']:.3f}"
                )


# ── Text validation per scene ───────────────────────────────────────────


def _validate_cue_text_per_scene(
    scenes: list[dict],
    errors: list[str],
    warnings: list[str],
) -> None:
    seen_norms = set()
    for scene in scenes:
        sn = scene["sceneNumber"]
        voiceover = scene.get("voiceover", "")
        cues = scene.get("subtitleTiming", {}).get("cues", [])

        vo_norm = normalize_subtitle_text(voiceover)

        for ci, cue in enumerate(cues):
            text = cue.get("text", "")
            if not text:
                continue
            cue_norm = normalize_subtitle_text(text)

            if cue_norm in seen_norms:
                warnings.append(f"Scene {sn} cue {ci}: duplicate text across scenes: '{text[:40]}'")
            seen_norms.add(cue_norm)

            if voiceover and text:
                ratio = difflib.SequenceMatcher(None, cue_norm, vo_norm).ratio()
                if ratio < 0.2:
                    warnings.append(
                        f"Scene {sn} cue {ci}: low text similarity ({ratio:.0%}) "
                        f"vs voiceover: '{text[:50]}'"
                    )

    _validate_cue_text_concatenation(scenes, errors)


def _validate_cue_text_concatenation(
    scenes: list[dict],
    errors: list[str],
) -> None:
    for scene in scenes:
        sn = scene["sceneNumber"]
        voiceover = scene.get("voiceover", "")
        cues = scene.get("subtitleTiming", {}).get("cues", [])
        if not voiceover or not cues:
            continue

        all_cue_text = " ".join(c.get("text", "") for c in cues)
        vo_norm = normalize_subtitle_text(voiceover)
        cue_norm = normalize_subtitle_text(all_cue_text)

        ratio = difflib.SequenceMatcher(None, cue_norm, vo_norm).ratio()
        if ratio < 0.5:
            errors.append(
                f"Scene {sn}: concatenated cues do not match voiceover "
                f"(similarity={ratio:.0%})"
            )


# ── ASS validation ──────────────────────────────────────────────────────


ASS_TIME_RE = re.compile(r"(\d+):(\d{2}):(\d{2})\.(\d{2})")


def _parse_ass_time(timestr: str) -> float:
    m = ASS_TIME_RE.match(timestr.strip())
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 100.0
    return 0.0


def _validate_ass_dialogues(
    ass_path: Path,
    global_cues: list[dict],
    scenes: list[dict],
    scene_windows: dict[int, dict[str, float]],
    errors: list[str],
) -> None:
    content = ass_path.read_text()
    dialogue_lines = [l for l in content.splitlines() if l.startswith("Dialogue:")]

    if len(dialogue_lines) != len(global_cues):
        errors.append(
            f"ASS dialogue count mismatch: {len(dialogue_lines)} dialogues, "
            f"{len(global_cues)} cues expected"
        )

    ass_entries: list[dict] = []
    for line in dialogue_lines:
        parts = line.split(",", 9)
        if len(parts) < 10:
            errors.append(f"ASS: malformed Dialogue line: {line[:80]}")
            continue
        start_str = parts[1].strip()
        end_str = parts[2].strip()
        text = parts[9].replace("\\N", " ").strip()
        ass_entries.append({
            "startSec": _parse_ass_time(start_str),
            "endSec": _parse_ass_time(end_str),
            "text": text,
        })

    if len(ass_entries) != len(global_cues):
        return

    for i in range(min(len(global_cues), len(ass_entries))):
        gc = global_cues[i]
        ae = ass_entries[i]

        tolerance = 0.10
        if abs(ae["startSec"] - gc["startSec"]) > tolerance:
            errors.append(
                f"ASS cue {i}: startSec mismatch: ASS={ae['startSec']:.3f}, "
                f"expected={gc['startSec']:.3f} (delta={abs(ae['startSec'] - gc['startSec']):.3f}s)"
            )
        if abs(ae["endSec"] - gc["endSec"]) > tolerance:
            errors.append(
                f"ASS cue {i}: endSec mismatch: ASS={ae['endSec']:.3f}, "
                f"expected={gc['endSec']:.3f} (delta={abs(ae['endSec'] - gc['endSec']):.3f}s)"
            )
        if text and ae["text"]:
            ass_norm = normalize_subtitle_text(ae["text"])
            cue_norm = normalize_subtitle_text(gc["text"])
            if ass_norm and cue_norm and ass_norm != cue_norm:
                errors.append(
                    f"ASS cue {i}: text mismatch: ASS='{ae['text'][:50]}', "
                    f"expected='{gc['text'][:50]}'"
                )

    if len(ass_entries) >= 2:
        for i in range(1, len(ass_entries)):
            prev_end = ass_entries[i - 1]["endSec"]
            curr_start = ass_entries[i]["startSec"]
            if curr_start < prev_end - 0.05:
                errors.append(
                    f"ASS overlap: dialogue {i - 1} ends at {prev_end:.3f}s, "
                    f"dialogue {i} starts at {curr_start:.3f}s"
                )

    scene_start_sec = {
        sn: w["startSec"] for sn, w in scene_windows.items()
    }

    if global_cues:
        for gc in global_cues:
            sn = gc["sceneNumber"]
            if sn >= 2:
                s_start = scene_start_sec.get(sn, 0)
                if s_start > 0 and gc["startSec"] < s_start - 0.5:
                    errors.append(
                        f"Scene {sn}: cue starts at {gc['startSec']:.3f}s, "
                        f"near zero instead of ~{s_start:.1f}s"
                    )


# ── Internal helpers ────────────────────────────────────────────────────


def _flatten_errors(legacy_result: dict) -> list[str]:
    errors: list[str] = []
    errors.extend(legacy_result.get("coverage", {}).get("errors", []))
    errors.extend(legacy_result.get("cuesPerScene", {}).get("errors", []))
    errors.extend(legacy_result.get("cueText", {}).get("errors", []))
    errors.extend(legacy_result.get("cueIntegrity", {}).get("errors", []))
    errors.extend(legacy_result.get("remapValidation", {}).get("errors", []))
    for ce in legacy_result.get("canonicalValidation", {}).get("errors", []):
        if isinstance(ce, dict):
            errors.append(
                f"CROSS_SCENE_CUE: {ce.get('offendingToken', '?')} from scene "
                f"{ce.get('targetScene', '?')} leaked into scene {ce.get('sourceScene', '?')}"
            )
        else:
            errors.append(str(ce))
    return errors
