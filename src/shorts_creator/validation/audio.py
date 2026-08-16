#!/usr/bin/env python3

import re
import json
import subprocess
from pathlib import Path


TICK = 10_000_000


def detect_silence_ranges(audio_path: Path, project_root: Path,
                          noise_db: int = -50, min_duration: float = 0.1) -> list[dict]:
    """Run FFmpeg silencedetect and return list of {startSec, endSec, durationSec}."""
    ws_path = f"/workspace/{audio_path.relative_to(project_root)}"
    result = subprocess.run(
        ["docker", "run", "--rm",
         "-v", f"{project_root}:/workspace",
         "linuxserver/ffmpeg:latest",
         "-i", ws_path,
         "-af", f"silencedetect=noise={noise_db}dB:d={min_duration}",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=60
    )
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", result.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", result.stderr)]
    silences = []
    for i in range(min(len(starts), len(ends))):
        silences.append({
            "startSec": round(starts[i], 3),
            "endSec": round(ends[i], 3),
            "durationSec": round(ends[i] - starts[i], 3),
        })
    return silences


def classify_silence(silence: dict, scene_timings: list[dict],
                     cues: list[dict], total_duration: float) -> str:
    start = silence["startSec"]
    end = silence["endSec"]
    dur = end - start

    if start < 0.3:
        return "natural"
    if total_duration - end < 0.3:
        return "natural"

    for st in scene_timings:
        scene_end = st["endSec"]
        if start < scene_end < end:
            return "chapter_break"
        if start >= scene_end - 1.2 and start <= scene_end + 0.5:
            return "chapter_break"
        if end >= scene_end - 0.1 and end <= scene_end + 0.3:
            return "chapter_break"

    for cue in cues:
        if abs(start - cue["endSec"]) < 0.6:
            return "natural"
        if abs(end - cue["endSec"]) < 0.4:
            return "natural"
        if dur < 0.5 and cue["startSec"] <= start <= cue["endSec"]:
            return "natural"

    return "unexpected"


def classify_silences(silences: list[dict], scene_timings: list[dict],
                      cues_by_scene: dict[int, list[dict]],
                      total_duration: float) -> list[dict]:
    all_cues = []
    for sc_cues in cues_by_scene.values():
        all_cues.extend(sc_cues)

    for s in silences:
        s["classification"] = classify_silence(s, scene_timings, all_cues, total_duration)
    return silences


def compute_quality_grade(silences: list[dict]) -> dict:
    chapter_breaks = [s for s in silences if s["classification"] == "chapter_break"]
    unexpected = [s for s in silences if s["classification"] == "unexpected"]

    max_chapter = max((s["durationSec"] for s in chapter_breaks), default=0.0)
    breaks_above_060 = len([s for s in chapter_breaks if s["durationSec"] > 0.60])
    breaks_035_060 = len([s for s in chapter_breaks if 0.35 < s["durationSec"] <= 0.60])
    max_unexpected = max((s["durationSec"] for s in unexpected), default=0.0)
    unexpected_count = len(unexpected)

    technical_status = "PASS"
    if unexpected_count > 2 and max_unexpected > 0.45:
        technical_status = "BLOCKED"
    elif max_unexpected > 0.8:
        technical_status = "BLOCKED"
    elif unexpected_count > 0 or max_unexpected > 0.45:
        technical_status = "REVIEW_REQUIRED"

    quality_status = "PASS"
    if max_chapter > 0.60:
        quality_status = "QUALITY_WARNING"
    if breaks_above_060 > 2:
        quality_status = "QUALITY_WARNING"
    if breaks_035_060 > 0 and max_chapter <= 0.60:
        quality_status = "REVIEW_REQUIRED"

    return {
        "technicalStatus": technical_status,
        "qualityStatus": quality_status,
        "maxChapterBreakSec": round(max_chapter, 3),
        "chapterBreakCount": len(chapter_breaks),
        "chapterBreaksAbove060": breaks_above_060,
        "chapterBreaks035_060": breaks_035_060,
        "maxUnexpectedSilenceSec": round(max_unexpected, 3),
        "unexpectedSilenceCount": unexpected_count,
        "totalSilenceSec": round(sum(s["durationSec"] for s in silences), 3),
        "totalDurationSec": round(max((s["endSec"] for s in silences), default=0.0), 3),
    }


def run_audio_validation(narration_path: Path, scene_timings: list[dict],
                         cues_by_scene: dict[int, list[dict]],
                         project_root: Path) -> dict:
    silences = detect_silence_ranges(narration_path, project_root)
    total_dur = scene_timings[-1]["endSec"] if scene_timings else 0
    silences = classify_silences(silences, scene_timings, cues_by_scene, total_dur)
    grade = compute_quality_grade(silences)

    return {
        "silenceRanges": silences,
        "technicalStatus": grade["technicalStatus"],
        "qualityStatus": grade["qualityStatus"],
        "metrics": {
            "maxChapterBreakSec": grade["maxChapterBreakSec"],
            "chapterBreakCount": grade["chapterBreakCount"],
            "chapterBreaksAbove060": grade["chapterBreaksAbove060"],
            "chapterBreaks035_060": grade["chapterBreaks035_060"],
            "maxUnexpectedSilenceSec": grade["maxUnexpectedSilenceSec"],
            "unexpectedSilenceCount": grade["unexpectedSilenceCount"],
            "totalSilenceSec": grade["totalSilenceSec"],
            "totalDurationSec": grade["totalDurationSec"],
        },
    }
