"""Pacing validation — silence and narration coverage analysis.

Uses ffmpeg silencedetect (via Docker) to measure silence in the
rendered MP4 and compares against scene windows to produce pacing
metrics and a quality gate status.

No imports from v1 pipeline modules.  Stdlib + subprocess (Docker) only.
"""

from __future__ import annotations

import abc
import math
import os
import re
import subprocess
from pathlib import Path
from typing import Any

# ── Thresholds ──────────────────────────────────────────────────────────

SILENCE_RATIO_PASS = 0.25
SILENCE_RATIO_WARN = 0.35
MAX_INTER_SCENE_SILENCE_PASS = 0.80
MAX_INTER_SCENE_SILENCE_WARN = 1.50
LEADING_SILENCE_PASS = 0.30
TRAILING_SILENCE_PASS = 0.80
TRAILING_SILENCE_FAIL = 2.00
NARRATION_COVERAGE_PASS = 0.75
NARRATION_COVERAGE_WARN = 0.65

# ── Helpers ─────────────────────────────────────────────────────────────

_SILENCE_RE = re.compile(
    r"silence_start:\s*([\d.]+)\s*\|?\s*silence_end:\s*([\d.]+)\s*\|?\s*silence_duration:\s*([\d.]+)"
)

_SILENCE_START_ALT = re.compile(r"silence_start:\s*([\d.]+)")
_SILENCE_END_ALT = re.compile(r"silence_end:\s*([\d.]+)")
_SILENCE_DUR_ALT = re.compile(r"silence_duration:\s*([\d.]+)")


def _docker_ffmpeg(args: list[str], project_root: Path, timeout: int = 120) -> subprocess.CompletedProcess:
    docker_env = os.environ.copy()
    docker_env.pop("DOCKER_API_VERSION", None)
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{project_root}:/workspace",
        "linuxserver/ffmpeg:latest",
    ] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=docker_env)


def _detect_silence_periods(video_path: Path, project_root: Path) -> "tuple[list[dict], bool, str | None]":
    """Run silencedetect on the video, return (periods, ok, error).

    Returns (periods, True, None) on success.
    Returns ([], False, error_message) on failure.
    """
    ws_path = f"/workspace/{video_path.relative_to(project_root)}"
    try:
        result = _docker_ffmpeg(
            ["-i", ws_path,
             "-af", "silencedetect=noise=-30dB:d=0.05",
             "-f", "null", "-"],
            project_root, timeout=120,
        )
    except Exception as e:
        return [], False, f"ffmpeg invocation failed: {e}"

    if result.returncode != 0:
        return [], False, f"ffmpeg exit code {result.returncode}: {result.stderr[:200]}"

    combined = result.stderr

    periods: list[dict] = []
    for m in _SILENCE_RE.finditer(combined):
        periods.append({
            "startSec": float(m.group(1)),
            "endSec": float(m.group(2)),
            "durationSec": float(m.group(3)),
        })

    if not periods:
        starts = [float(m.group(1)) for m in _SILENCE_START_ALT.finditer(combined)]
        ends = [float(m.group(1)) for m in _SILENCE_END_ALT.finditer(combined)]
        durs = [float(m.group(1)) for m in _SILENCE_DUR_ALT.finditer(combined)]
        n = min(len(starts), len(ends), len(durs))
        for i in range(n):
            periods.append({
                "startSec": starts[i],
                "endSec": ends[i],
                "durationSec": durs[i],
            })

    return periods, True, None


def _compute_max_inter_scene_silence(
    periods: list[dict],
    scene_windows: list[dict],
    total_dur: float,
) -> float:
    """Compute max silence that crosses a scene boundary.

    Uses scene windows to find boundary timestamps, then finds the
    largest silence period that contains (or is near) a boundary.
    Excludes leading and trailing silence.
    """
    if not scene_windows or len(scene_windows) < 2:
        return 0.0

    sorted_windows = sorted(scene_windows, key=lambda w: w.get("startSec", 0))
    boundaries: list[float] = []
    for w in sorted_windows[:-1]:
        end = w.get("endSec", 0)
        if isinstance(end, (int, float)) and not isinstance(end, bool) and math.isfinite(end):
            boundaries.append(float(end))

    tolerance = 0.15

    max_inter = 0.0
    for p in periods:
        start = p["startSec"]
        end = p["endSec"]
        dur = p["durationSec"]

        if start <= 0.05:
            continue
        if end >= total_dur - 0.05:
            continue

        crosses = any(
            abs(start - b) <= tolerance or abs(end - b) <= tolerance or (start <= b <= end)
            for b in boundaries
        )
        if crosses and dur > max_inter:
            max_inter = dur

    return round(max_inter, 3)


# ── Public API ──────────────────────────────────────────────────────────


def validate_audio_pacing(
    *,
    video_path: Path | None = None,
    scene_windows: list[dict] | None = None,
    total_duration_sec: float | None = None,
    project_root: Path | None = None,
    silence_periods: list[dict] | None = None,
    word_count: int | None = None,
) -> dict[str, Any]:
    """Validate the pacing of a rendered video."""
    errors: list[str] = []
    warnings: list[str] = []

    if video_path is None and silence_periods is None:
        return {
            "status": "NOT_APPLICABLE",
            "metrics": {},
            "errors": ["no video_path or silence_periods provided"],
            "warnings": [],
        }

    periods: list[dict] = []
    ffprobe_ok = True

    if silence_periods is not None:
        periods = list(silence_periods)
    elif video_path is not None and project_root is not None:
        periods, ffprobe_ok, probe_error = _detect_silence_periods(video_path, project_root)
        if not ffprobe_ok:
            return {
                "status": "REVIEW_REQUIRED",
                "metrics": {},
                "metricStatuses": {},
                "errors": [f"silencedetect tool failure: {probe_error}"],
                "warnings": [],
                "silencePeriods": [],
            }
    else:
        return {
            "status": "NOT_APPLICABLE",
            "metrics": {},
            "errors": ["video_path and project_root required"],
            "warnings": [],
        }

    total_dur = total_duration_sec or 0.0
    if total_dur <= 0 and periods:
        total_dur = max(p["endSec"] for p in periods)

    # Derived from actual durations
    total_silence = sum(p["durationSec"] for p in periods)
    silence_ratio = total_silence / total_dur if total_dur > 0 else 0.0
    active_speech_dur = total_dur - total_silence

    leading_silence = 0.0
    for p in periods:
        if p["startSec"] <= 0.05:
            leading_silence += p["durationSec"]

    trailing_silence = 0.0
    for p in periods:
        if p["endSec"] >= total_dur - 0.05:
            trailing_silence += p["durationSec"]

    max_inter = _compute_max_inter_scene_silence(periods, scene_windows or [], total_dur)

    narration_coverage = 1.0 - silence_ratio

    timeline_wpm: float | None = None
    effective_speech_wpm: float | None = None
    if word_count and word_count > 0 and total_dur > 0:
        timeline_wpm = round(word_count / (total_dur / 60.0), 1)
    if word_count and word_count > 0 and active_speech_dur > 0:
        effective_speech_wpm = round(word_count / (active_speech_dur / 60.0), 1)

    metrics = {
        "totalSilenceSec": round(total_silence, 3),
        "silenceRatio": round(silence_ratio, 3),
        "maxInterSceneSilenceSec": max_inter,
        "leadingSilenceSec": round(leading_silence, 3),
        "trailingSilenceSec": round(trailing_silence, 3),
        "narrationCoverageRatio": round(narration_coverage, 3),
    }
    if timeline_wpm is not None:
        metrics["timelineWordsPerMinute"] = timeline_wpm
    if effective_speech_wpm is not None:
        metrics["effectiveSpeechWordsPerMinute"] = effective_speech_wpm
    if word_count is not None:
        metrics["wordCount"] = word_count
    if total_dur > 0:
        metrics["totalDurationSec"] = round(total_dur, 3)
    if active_speech_dur > 0:
        metrics["activeSpeechDurationSec"] = round(active_speech_dur, 3)

    metric_statuses: dict[str, str] = {}

    if silence_ratio <= SILENCE_RATIO_PASS:
        metric_statuses["silenceRatio"] = "PASS"
    elif silence_ratio <= SILENCE_RATIO_WARN:
        metric_statuses["silenceRatio"] = "WARNING"
        warnings.append(f"silenceRatio={silence_ratio:.3f}")
    else:
        metric_statuses["silenceRatio"] = "FAIL"
        errors.append(f"silenceRatio={silence_ratio:.3f} exceeds FAIL threshold {SILENCE_RATIO_WARN}")

    if max_inter <= MAX_INTER_SCENE_SILENCE_PASS:
        metric_statuses["maxInterSceneSilenceSec"] = "PASS"
    elif max_inter <= MAX_INTER_SCENE_SILENCE_WARN:
        metric_statuses["maxInterSceneSilenceSec"] = "WARNING"
        warnings.append(f"maxInterSceneSilenceSec={max_inter:.3f}s")
    else:
        metric_statuses["maxInterSceneSilenceSec"] = "FAIL"
        errors.append(f"maxInterSceneSilenceSec={max_inter:.3f}s exceeds FAIL threshold {MAX_INTER_SCENE_SILENCE_WARN}s")

    if trailing_silence <= TRAILING_SILENCE_PASS:
        metric_statuses["trailingSilenceSec"] = "PASS"
    elif trailing_silence <= TRAILING_SILENCE_FAIL:
        metric_statuses["trailingSilenceSec"] = "WARNING"
        warnings.append(f"trailingSilenceSec={trailing_silence:.3f}s")
    else:
        metric_statuses["trailingSilenceSec"] = "FAIL"
        errors.append(f"trailingSilenceSec={trailing_silence:.3f}s exceeds FAIL threshold {TRAILING_SILENCE_FAIL}s")

    if narration_coverage >= NARRATION_COVERAGE_PASS:
        metric_statuses["narrationCoverageRatio"] = "PASS"
    elif narration_coverage >= NARRATION_COVERAGE_WARN:
        metric_statuses["narrationCoverageRatio"] = "WARNING"
        warnings.append(f"narrationCoverageRatio={narration_coverage:.3f}")
    else:
        metric_statuses["narrationCoverageRatio"] = "FAIL"
        errors.append(f"narrationCoverageRatio={narration_coverage:.3f} below FAIL threshold {NARRATION_COVERAGE_WARN}")

    if leading_silence <= LEADING_SILENCE_PASS:
        metric_statuses["leadingSilenceSec"] = "PASS"
    else:
        metric_statuses["leadingSilenceSec"] = "WARNING"

    has_fail = "FAIL" in metric_statuses.values()
    has_warning = "WARNING" in metric_statuses.values()

    if has_fail:
        status = "FAIL"
    elif has_warning:
        status = "PASS_WITH_WARNINGS"
    else:
        status = "PASS"

    return {
        "status": status,
        "metrics": metrics,
        "metricStatuses": metric_statuses,
        "errors": errors,
        "warnings": warnings,
        "silencePeriods": periods,
    }
