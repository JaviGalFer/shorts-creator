#!/usr/bin/env python3
"""Validación automatizada de jobs de vídeos cortos.

Uso:
    python3 bin/validate_job.py data/videos/{jobId}/metadata.json
    python3 bin/validate_job.py data/videos/{jobId}/metadata.json --json  # output JSON
    python3 bin/validate_job.py data/videos/{jobId}/metadata.json --verbose

Comprueba:
  - Assets visuales existen por escena
  - Audio existe por escena
  - Ningún archivo relevante tiene tamaño cero
  - Duraciones válidas (>0)
  - ASS existe y es válido
  - Cues de subtítulos no se solapan
  - Cues cubren el audio razonablemente
  - Manifiesto existe y rutas son válidas
  - Si video.mp4 existe, confirmar resolución 1080x1920 vía ffprobe
  - Exit code != 0 en errores bloqueantes
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from visual_normalize import normalize_scene_visual
from subtitle_normalize import normalize_subtitle_text, normalize_subtitle_tokens


FPS = 25
MAX_SEGMENT_DURATION = 20.0
MAX_TOTAL_DURATION = 120
EXPECTED_WIDTH = 1080
EXPECTED_HEIGHT = 1920


# ── Helpers ──────────────────────────────────────────────────────────────


def _run_local_ffprobe(args: list[str]) -> subprocess.CompletedProcess | None:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return None
    try:
        return subprocess.run([ffprobe] + args, capture_output=True, text=True, timeout=30)
    except Exception:
        return None


def _run_docker_ffprobe(args: list[str], project_root: Path) -> subprocess.CompletedProcess | None:
    try:
        env = {**os.environ, "DOCKER_API_VERSION": "1.43"}
        return subprocess.run(
            ["docker", "run", "--rm",
             "-v", f"{project_root}:/workspace",
             "--entrypoint", "ffprobe",
             "linuxserver/ffmpeg:latest"] + args,
            capture_output=True, text=True, timeout=30,
            env=env,
        )
    except Exception:
        return None


def _get_ffprobe_duration(video_path: Path, project_root: Path) -> float | None:
    local_args = ["-v", "quiet", "-print_format", "json", "-show_format", str(video_path)]
    result = _run_local_ffprobe(local_args)
    if result is not None and result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            return float(data["format"]["duration"])
        except Exception:
            pass

    ws_path = f"/workspace/{video_path.relative_to(project_root)}"
    docker_args = ["-v", "quiet", "-print_format", "json", "-show_format", ws_path]
    result = _run_docker_ffprobe(docker_args, project_root)
    if result is not None and result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            return float(data["format"]["duration"])
        except Exception:
            pass

    return None


def _get_ffprobe_resolution(video_path: Path, project_root: Path) -> tuple[int, int] | None:
    local_args = ["-v", "quiet", "-print_format", "json", "-show_streams", str(video_path)]
    result = _run_local_ffprobe(local_args)
    if result is not None and result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    return int(stream.get("width", 0)), int(stream.get("height", 0))
        except Exception:
            pass

    ws_path = f"/workspace/{video_path.relative_to(project_root)}"
    docker_args = ["-v", "quiet", "-print_format", "json", "-show_streams", ws_path]
    result = _run_docker_ffprobe(docker_args, project_root)
    if result is not None and result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    return int(stream.get("width", 0)), int(stream.get("height", 0))
        except Exception:
            pass

    return None


# ── Checks ────────────────────────────────────────────────────────────────

Severity = str  # "ERROR" | "WARNING" | "INFO"
CheckResult = tuple[bool, list[tuple[Severity, str]]]


class JobValidator:
    def __init__(self, metadata_path: Path, verbose: bool = False):
        self.metadata_path = metadata_path.resolve()
        self.project_root = self.metadata_path.parents[3]
        self.video_dir = self.metadata_path.parent
        self.scenes_dir = self.video_dir / "scenes"
        self.verbose = verbose
        self.all_checks: list[tuple[str, CheckResult]] = []

        with open(self.metadata_path) as f:
            self.data = json.load(f)

        self.job_id = self.data.get("jobId", "unknown")
        self.status = self.data.get("status", "unknown")
        self.scenes = self.data.get("script", {}).get("scenes", [])
        self.assets = self.data.get("assets", [])
        self.audio_config = self.data.get("audio", {})
        self.is_continuous = self.audio_config.get("continuous", False)
        self.timing_source = self.audio_config.get("timingSource", "unknown")
        self.timing_provider = self.audio_config.get("timingProvider", "unknown")
        self.global_offset_ms = self.audio_config.get("globalOffsetMs", 0)

    def _ok(self, msg: str):
        self._result.append(("INFO", msg))

    def _warn(self, msg: str):
        self._result.append(("WARNING", msg))
        self._has_warnings = True

    def _err(self, msg: str):
        self._result.append(("ERROR", msg))
        self._has_errors = True

    def _check(self, name: str) -> CheckResult:
        self._result: list[tuple[Severity, str]] = []
        self._has_errors = False
        self._has_warnings = False
        try:
            getattr(self, f"_check_{name.replace('-', '_')}")()
        except Exception as e:
            self._err(f"Exception in check '{name}': {e}")
        result = (not self._has_errors, self._result)
        self.all_checks.append((name, result))
        return result

    def run(self) -> bool:
        checks = [
            "timing-info",
            "assets",
            "audio",
            "file-sizes",
            "durations",
            "subtitles-ass",
            "subtitle-cues",
            "subtitle-coverage",
            "subtitle-alignment",
            "manifest",
            "video-resolution",
            "pacing",
        ]
        all_pass = True
        for name in checks:
            ok, msgs = self._check(name)
            if not ok:
                all_pass = False
            if self.verbose or not ok:
                for sev, msg in msgs:
                    print(f"  [{sev}] {msg}")
        return all_pass

    # ── Timing info ─────────────────────────────────────────────────

    def _check_timing_info(self):
        self._ok(f"Timing source: {self.timing_source}")
        self._ok(f"Timing provider: {self.timing_provider}")
        if self.global_offset_ms != 0:
            self._ok(f"Global offset: {self.global_offset_ms}ms ({self.global_offset_ms/1000:+.3f}s)")
        else:
            self._ok(f"Global offset: 0ms (none)")
        audio_path = self.audio_config.get("path", "")
        if audio_path:
            self._ok(f"Audio used: {Path(audio_path).name}")
        if self.is_continuous:
            trimmed_path = self.scenes_dir / "narration_trimmed.mp3"
            if trimmed_path.exists():
                self._ok(f"Trimmed audio exists: narration_trimmed.mp3")
            else:
                self._ok("No trimmed audio (no trim applied)")

    # ── Asset checks ─────────────────────────────────────────────────

    def _check_assets(self):
        if not self.scenes:
            self._err("No scenes in metadata")
            return

        asset_by_scene = {a["sceneNumber"]: a for a in self.assets if "sceneNumber" in a}

        for scene in self.scenes:
            sn = scene["sceneNumber"]
            asset_entry = asset_by_scene.get(sn, {})

            if asset_entry.get("segments"):
                for seg in asset_entry["segments"]:
                    p = seg.get("path", "")
                    full = Path(p)
                    if not full.is_absolute():
                        full = self.video_dir / p
                    if not full.exists():
                        self._err(f"Scene {sn}: segment asset not found: {p}")
                    elif full.stat().st_size == 0:
                        self._err(f"Scene {sn}: segment asset is empty: {p}")
                    else:
                        self._ok(f"Scene {sn}: segment asset OK ({full.name})")
            else:
                p = asset_entry.get("path", "")
                if not p:
                    p = f"scenes/scene-{sn:02}.jpg"
                full = self.video_dir / p
                if not full.exists():
                    self._err(f"Scene {sn}: asset not found: {p}")
                elif full.stat().st_size == 0:
                    self._err(f"Scene {sn}: asset is empty: {p}")
                else:
                    self._ok(f"Scene {sn}: asset OK ({full.name})")

    # ── Audio checks ─────────────────────────────────────────────────

    def _check_audio(self):
        if not self.scenes:
            return

        if self.is_continuous:
            audio_path = self.scenes_dir / "narration.mp3"
            if audio_path.exists():
                dur = _get_ffprobe_duration(audio_path, self.project_root)
                size = audio_path.stat().st_size
                if dur is None:
                    self._warn(f"Continuous audio: ffprobe unavailable (duration check skipped)")
                    dur = 0.0
                elif dur <= 0:
                    self._err(f"Continuous audio duration is 0 or could not be measured: {audio_path}")
                else:
                    self._ok(f"Continuous audio: {audio_path.name} ({size} bytes, {dur:.1f}s)")
                self._audio_dur = dur
            else:
                self._err(f"Continuous audio not found: {audio_path}")
                self._audio_dur = 0.0
        else:
            for scene in self.scenes:
                sn = scene["sceneNumber"]
                audio_path = self.scenes_dir / f"scene-{sn:02}.mp3"
                if audio_path.exists():
                    self._ok(f"Scene {sn}: audio OK ({audio_path.name})")
                    if audio_path.stat().st_size == 0:
                        self._err(f"Scene {sn}: audio is empty")
                else:
                    self._err(f"Scene {sn}: audio not found: {audio_path}")

    # ── File size checks ─────────────────────────────────────────────

    def _check_file_sizes(self):
        for fpath in self.scenes_dir.glob("*"):
            if fpath.is_file() and fpath.stat().st_size == 0:
                self._err(f"Zero-size file: {fpath.name}")
        for ext in [".ass", ".srt"]:
            sub_path = self.video_dir / f"subtitle{ext}"
            if sub_path.exists() and sub_path.stat().st_size == 0:
                self._err(f"Zero-size subtitle: subtitle{ext}")
        manifest_path = self.video_dir / "job-manifest.json"
        if manifest_path.exists() and manifest_path.stat().st_size == 0:
            self._err(f"Zero-size manifest: job-manifest.json")

    # ── Duration checks ──────────────────────────────────────────────

    def _check_durations(self):
        import math

        # ── Level 1: scene targetDurationSec ────────────────────────────
        for scene in self.scenes:
            dur = scene.get("targetDurationSec", 0)
            sn = scene["sceneNumber"]
            if isinstance(dur, bool) or not isinstance(dur, (int, float)):
                self._err(f"Scene {sn}: targetDurationSec={dur!r} is not a number")
            elif not math.isfinite(dur):
                self._err(f"Scene {sn}: targetDurationSec={dur} is not finite")
            elif dur <= 0:
                self._err(f"Scene {sn}: targetDurationSec={dur} <= 0")
            else:
                self._ok(f"Scene {sn}: target duration {dur}s OK")

        # ── Level 2: renderTimeline entries ─────────────────────────────
        timeline = self.data.get("renderTimeline", [])
        if timeline:
            for i, entry in enumerate(timeline):
                sn = entry.get("sceneNumber", "?")
                start = entry.get("startSec")
                end = entry.get("endSec")
                dur = entry.get("durationSec")
                prefix = f"Timeline[{i}] scene {sn}"

                for field_name, val in [("startSec", start), ("endSec", end), ("durationSec", dur)]:
                    if isinstance(val, bool) or not isinstance(val, (int, float)):
                        self._err(f"{prefix}: {field_name}={val!r} is not a number")
                    elif not math.isfinite(val):
                        self._err(f"{prefix}: {field_name}={val} is not finite")

                is_valid = all(
                    isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                    for v in [start, end, dur]
                )
                if not is_valid:
                    continue

                if start < 0:
                    self._err(f"{prefix}: startSec={start} < 0")
                if end <= start:
                    self._err(f"{prefix}: endSec={end} <= startSec={start}")
                if dur <= 0:
                    self._err(f"{prefix}: durationSec={dur} <= 0")
                if dur > MAX_SEGMENT_DURATION:
                    self._err(f"{prefix}: durationSec={dur} > {MAX_SEGMENT_DURATION}s (max segment)")

                expected_dur = end - start
                if abs(dur - expected_dur) > 0.05:
                    self._err(f"{prefix}: durationSec={dur:.3f} != end-start={expected_dur:.3f}")

            # ── Level 3: scene aggregate windows ────────────────────────
            scene_entries: dict[int, list[tuple[float, float]]] = {}
            for entry in timeline:
                sn = entry.get("sceneNumber")
                s = entry.get("startSec")
                e = entry.get("endSec")
                if sn is None:
                    continue
                if isinstance(s, bool) or not isinstance(s, (int, float)):
                    continue
                if isinstance(e, bool) or not isinstance(e, (int, float)):
                    continue
                if not math.isfinite(s) or not math.isfinite(e):
                    continue
                scene_entries.setdefault(sn, []).append((float(s), float(e)))

            for sn, spans in sorted(scene_entries.items()):
                spans.sort()
                scene_start = spans[0][0]
                scene_end = spans[-1][1]
                scene_window = scene_end - scene_start

                if scene_window <= 0:
                    self._err(f"Scene {sn}: aggregate window is zero or negative")
                else:
                    self._ok(f"Scene {sn}: aggregate window {scene_window:.1f}s ({len(spans)} segments)")

                for i in range(1, len(spans)):
                    prev_end = spans[i - 1][1]
                    curr_start = spans[i][0]
                    gap = curr_start - prev_end
                    if gap < -0.05:
                        self._err(f"Scene {sn}: overlap between segments ({prev_end:.3f}s -> {curr_start:.3f}s)")
                    elif gap > 0.05:
                        self._err(f"Scene {sn}: gap between segments ({prev_end:.3f}s -> {curr_start:.3f}s)")

            # ── Level 4: total duration from renderTimeline ──────────────
            finite_ends = []
            for entry in timeline:
                e = entry.get("endSec")
                if isinstance(e, (int, float)) and not isinstance(e, bool) and math.isfinite(e):
                    finite_ends.append(e)
            total_duration = max(finite_ends) if finite_ends else 0
            if total_duration <= 0:
                self._err("Total duration from renderTimeline is zero or negative")
            elif total_duration > MAX_TOTAL_DURATION:
                self._err(f"Total duration {total_duration:.1f}s > {MAX_TOTAL_DURATION}s")
            else:
                self._ok(f"Total duration (from timeline): {total_duration:.1f}s")
        else:
            # ── Legacy metadata without renderTimeline ──────────────────
            total = sum(float(s.get("targetDurationSec", 0)) for s in self.scenes)
            if total <= 0:
                self._err("Total duration is 0")
            elif total > MAX_TOTAL_DURATION:
                self._err(f"Total duration {total:.1f}s > {MAX_TOTAL_DURATION}s")
            else:
                self._ok(f"Total duration (from targets): {total:.1f}s")

        # ── Continuous audio check ──────────────────────────────────────
        if self.is_continuous:
            dur = self.audio_config.get("durationSec", 0)
            if dur <= 0:
                self._err("Continuous audio duration is 0")
            elif dur > MAX_TOTAL_DURATION:
                self._err(f"Continuous audio duration {dur}s > {MAX_TOTAL_DURATION}s")

    # ── Subtitle ASS check ───────────────────────────────────────────

    def _check_subtitles_ass(self):
        sub_format = self.data.get("subtitles", {}).get("format", "ass")
        sub_path = self.video_dir / f"subtitle.{sub_format}"
        if not sub_path.exists():
            self._err(f"Subtitle file not found: subtitle.{sub_format}")
            return

        content = sub_path.read_text()
        if "[Script Info]" not in content:
            self._err(f"subtitle.{sub_format}: missing [Script Info] header")
        if "[V4+ Styles]" not in content:
            self._err(f"subtitle.{sub_format}: missing [V4+ Styles]")
        if "[Events]" not in content:
            self._err(f"subtitle.{sub_format}: missing [Events]")

        dialogue_lines = [l for l in content.splitlines() if l.startswith("Dialogue:")]
        if not dialogue_lines:
            self._warn(f"subtitle.{sub_format}: no Dialogue lines found")
        else:
            self._ok(f"subtitle.{sub_format}: {len(dialogue_lines)} Dialogue lines")

    # ── Subtitle cue checks ──────────────────────────────────────────

    def _check_subtitle_cues(self):
        if self.is_continuous:
            self._check_subtitle_cues_legacy()
        else:
            self._check_subtitle_cues_per_scene()

    def _check_subtitle_cues_legacy(self):
        all_cues = []
        for scene in self.scenes:
            cues = scene.get("subtitleTiming", {}).get("cues", [])
            for c in cues:
                all_cues.append(c)

        if not all_cues:
            self._warn("No subtitle timing cues found")
            return

        for i, cue in enumerate(all_cues):
            start = cue.get("startSec", 0)
            end = cue.get("endSec", 0)
            dur = end - start
            if dur < 0:
                self._err(f"Cue {i}: startSec={start} > endSec={end}")
            if start < 0:
                self._err(f"Cue {i}: startSec={start} < 0")
            if dur > 6.0:
                self._warn(f"Cue {i}: duration {dur:.1f}s > 6s (too long)")

        sorted_cues = sorted(all_cues, key=lambda c: c.get("startSec", 0))
        for i in range(1, len(sorted_cues)):
            prev_end = sorted_cues[i - 1].get("endSec", 0)
            curr_start = sorted_cues[i].get("startSec", 0)
            if curr_start < prev_end - 0.1:
                self._err(f"Cue overlap: cue {i-1} ends at {prev_end:.3f}s, cue {i} starts at {curr_start:.3f}s")

        self._ok(f"{len(all_cues)} subtitle cues, all non-overlapping")

    def _check_subtitle_cues_per_scene(self):
        from subtitle_validation_context import build_validation_context
        ctx = build_validation_context(self.data, video_dir=self.video_dir)
        self._per_scene_subtitle_ctx = ctx

        if ctx["totalCues"] == 0:
            self._warn("No subtitle timing cues found")
            return

        for err in ctx.get("errors", []):
            self._err(err)
        for warn in ctx.get("warnings", []):
            self._warn(warn)

        if not ctx.get("errors"):
            self._ok(f"{ctx['totalCues']} subtitle cues, all non-overlapping (per-scene)")

    # ── Subtitle coverage check ──────────────────────────────────────

    def _check_subtitle_coverage(self):
        if self.is_continuous:
            self._check_subtitle_coverage_legacy()
        else:
            self._check_subtitle_coverage_per_scene()

    def _check_subtitle_coverage_legacy(self):
        all_cues = []
        for scene in self.scenes:
            cues = scene.get("subtitleTiming", {}).get("cues", [])
            for c in cues:
                all_cues.append(c)

        if not all_cues:
            self._warn("No cues for coverage check")
            return

        audio_dur = self.audio_config.get("durationSec", 0)

        if audio_dur <= 0:
            self._warn("Cannot check coverage: audio duration unknown")
            return

        sorted_cues = sorted(all_cues, key=lambda c: c.get("startSec", 0))
        if not sorted_cues:
            return

        first_start = sorted_cues[0].get("startSec", 0)
        last_end = sorted_cues[-1].get("endSec", 0)

        gap_start = first_start
        gap_end = audio_dur - last_end

        if gap_start > 1.0:
            self._warn(f"Coverage gap at start: {gap_start:.1f}s before first cue")
        if gap_end > 1.0:
            self._warn(f"Coverage gap at end: {gap_end:.1f}s after last cue")

        total_covered = sum(c.get("endSec", 0) - c.get("startSec", 0) for c in sorted_cues)
        coverage_pct = (total_covered / audio_dur * 100) if audio_dur > 0 else 0
        if coverage_pct < 50:
            self._warn(f"Subtitle coverage: {coverage_pct:.0f}% of audio ({total_covered:.1f}s / {audio_dur:.1f}s)")
        else:
            self._ok(f"Subtitle coverage: {coverage_pct:.0f}% of audio ({total_covered:.1f}s / {audio_dur:.1f}s)")

    def _check_subtitle_coverage_per_scene(self):
        ctx = getattr(self, "_per_scene_subtitle_ctx", None)
        if ctx is None:
            from subtitle_validation_context import build_validation_context
            ctx = build_validation_context(self.data, video_dir=self.video_dir)
            self._per_scene_subtitle_ctx = ctx

        if ctx["totalCues"] == 0:
            self._warn("No cues for coverage check")
            return

        global_cues = ctx.get("globalCues", [])
        if not global_cues:
            return

        scene_windows = _build_scene_windows_from_metadata(self.data)
        total_visual = sum(
            w["endSec"] - w["startSec"] for w in scene_windows.values()
        )
        total_covered = sum(c["endSec"] - c["startSec"] for c in global_cues)

        if total_visual > 0:
            coverage_pct = total_covered / total_visual * 100
            self._ok(
                f"Subtitle coverage: {coverage_pct:.0f}% of visual timeline "
                f"({total_covered:.1f}s / {total_visual:.1f}s)"
            )
        else:
            self._warn("Cannot check coverage: visual timeline unknown")

    # ── Subtitle alignment check ────────────────────────────────────

    def _check_subtitle_alignment(self):
        if self.is_continuous:
            self._check_subtitle_alignment_legacy()
        else:
            self._check_subtitle_alignment_per_scene()

    def _check_subtitle_alignment_legacy(self):
        scene_timings = self.data.get("audio", {}).get("sceneTimings", [])
        if not scene_timings:
            self._warn("No sceneTimings available (alignment check skipped)")
            return

        timing_map = {st["sceneNumber"]: st for st in scene_timings}
        narration_units = self.data.get("audio", {}).get("narrationUnits", [])
        all_cues = []
        seen_cues = set()
        has_errors = False

        for scene in self.scenes:
            sn = scene["sceneNumber"]
            st = timing_map.get(sn)
            cues = scene.get("subtitleTiming", {}).get("cues", [])
            voiceover = scene.get("voiceover", "")
            scene_narration = " ".join(
                u["text"] for u in narration_units if u["sceneNumber"] == sn
            )

            for ci, cue in enumerate(cues):
                start = cue.get("startSec", 0)
                end = cue.get("endSec", 0)
                text = cue.get("text", "")

                # Check cue is within scene time window (tight 0.05s tolerance)
                if st:
                    tolerance = 0.05
                    if start < st["startSec"] - tolerance:
                        self._err(f"Scene {sn} cue {ci}: startSec={start:.3f} < scene start {st['startSec']:.3f}")
                        has_errors = True
                    if end > st["endSec"] + tolerance:
                        self._err(f"Scene {sn} cue {ci}: endSec={end:.3f} > scene end {st['endSec']:.3f}")
                        has_errors = True

                # Cross-scene text check — uses canonical token ownership
                # With canonical matching, cues should only contain words from their assigned scene.
                # A few shared words across scenes are expected (e.g., "era", "su", "los").
                # If many foreign words appear, it's worth a warning.
                if scene_narration and text:
                    def _strip_punct(w):
                        return w.strip(".,!?;:\"'()[]¿¡-")
                    cue_words = {_strip_punct(w) for w in text.lower().split()}
                    scene_words = {_strip_punct(w) for w in scene_narration.lower().split()}
                    foreign = [w for w in cue_words if w not in scene_words and len(w) > 3]
                    if len(foreign) >= 3:
                        self._warn(
                            f"Scene {sn} cue {ci}: {len(foreign)} words may be from another scene: "
                            f"{foreign[:5]} in '{text[:60]}'"
                        )

                # Check for duplicate text across scenes
                norm = re.sub(r'\s+', ' ', text.lower().strip(".,!?;: "))
                if norm in seen_cues:
                    self._warn(f"Scene {sn} cue {ci}: duplicate text across scenes: '{text[:40]}'")
                seen_cues.add(norm)

                # Check text similarity with voiceover (normalized comparison)
                if voiceover and text:
                    vo_norm = normalize_subtitle_text(voiceover)
                    cue_norm = normalize_subtitle_text(text)
                    ratio = difflib.SequenceMatcher(None, cue_norm, vo_norm).ratio()
                    if ratio < 0.3:
                        self._warn(f"Scene {sn} cue {ci}: low text similarity ({ratio:.0%}) vs voiceover: '{text[:50]}'")

        # Check all cues are globally ordered
        flat_cues = []
        for scene in self.scenes:
            cues = scene.get("subtitleTiming", {}).get("cues", [])
            for c in cues:
                flat_cues.append((scene["sceneNumber"], c))
        flat_cues.sort(key=lambda x: x[1].get("startSec", 0))

        for i in range(1, len(flat_cues)):
            prev_sn, prev_c = flat_cues[i - 1]
            curr_sn, curr_c = flat_cues[i]
            prev_end = prev_c.get("endSec", 0)
            curr_start = curr_c.get("startSec", 0)
            if curr_start < prev_end - 0.1:
                self._err(f"Cross-scene cue overlap: scene {prev_sn} ends {prev_end:.2f}s, scene {curr_sn} starts {curr_start:.2f}s")
                has_errors = True

        if not has_errors:
            self._ok(f"Cue alignment: all {len(flat_cues)} cues within scene windows")

    def _check_subtitle_alignment_per_scene(self):
        ctx = getattr(self, "_per_scene_subtitle_ctx", None)
        if ctx is None:
            from subtitle_validation_context import build_validation_context
            ctx = build_validation_context(self.data, video_dir=self.video_dir)
            self._per_scene_subtitle_ctx = ctx

        for err in ctx.get("errors", []):
            self._err(err)
        for warn in ctx.get("warnings", []):
            self._warn(warn)

        if not ctx.get("errors"):
            self._ok(f"Cue alignment: all {ctx['totalCues']} cues within scene windows (per-scene)")

    # ── Manifest check ───────────────────────────────────────────────

    def _check_manifest(self):
        manifest_path = self.video_dir / "job-manifest.json"
        if not manifest_path.exists():
            self._err("job-manifest.json not found")
            return

        try:
            manifest = json.loads(manifest_path.read_text())
        except json.JSONDecodeError as e:
            self._err(f"job-manifest.json is not valid JSON: {e}")
            return

        required = ["jobId", "createdAt", "tts", "subtitles", "scenes", "outputVideoPath"]
        for field in required:
            if field not in manifest:
                self._err(f"job-manifest.json: missing required field '{field}'")
            elif field == "scenes" and not manifest["scenes"]:
                self._err(f"job-manifest.json: 'scenes' is empty")

        if "tts" in manifest:
            tts = manifest["tts"]
            if "provider" not in tts:
                self._err("job-manifest.json: tts.provider missing")
            if "voice" not in tts:
                self._err("job-manifest.json: tts.voice missing")

        if "subtitles" in manifest:
            subs = manifest["subtitles"]
            if "provider" not in subs:
                self._err("job-manifest.json: subtitles.provider missing")

        for sc in manifest.get("scenes", []):
            for f in ["sceneNumber", "visualType", "visualPath", "audioPath"]:
                if f not in sc:
                    self._err(f"job-manifest.json scene {sc.get('sceneNumber')}: missing '{f}'")

        output_video = manifest.get("outputVideoPath", "")
        if output_video:
            full = self.project_root / output_video
            if not full.exists():
                self._warn(f"job-manifest.json: outputVideoPath not found: {output_video}")

        self._ok("job-manifest.json: valid structure")

    # ── Video resolution check ───────────────────────────────────────

    def _check_video_resolution(self):
        video_path = self.video_dir / "video.mp4"
        if not video_path.exists():
            self._warn("video.mp4 not found (resolution check skipped)")
            return

        res = _get_ffprobe_resolution(video_path, self.project_root)
        if res is None:
            self._warn("video.mp4: ffprobe unavailable (resolution check skipped)")
        else:
            w, h = res
            if w == EXPECTED_WIDTH and h == EXPECTED_HEIGHT:
                self._ok(f"video.mp4: resolution {w}x{h} OK")
            else:
                self._err(f"video.mp4: resolution {w}x{h}, expected {EXPECTED_WIDTH}x{EXPECTED_HEIGHT}")

    # ── Pacing check ───────────────────────────────────────────────

    def _check_pacing(self):
        if self.is_continuous:
            self._ok("Pacing check skipped (continuous audio)")
            return

        video_path = self.video_dir / "video.mp4"
        if not video_path.exists():
            self._ok("Pacing check skipped (no video.mp4)")
            return

        try:
            from pacing_validation import validate_audio_pacing

            render_timeline = self.data.get("renderTimeline", [])
            scene_windows = []
            seen = set()
            for entry in render_timeline:
                sn = entry.get("sceneNumber")
                if sn is None:
                    continue
                start = entry.get("startSec", 0)
                end = entry.get("endSec", 0)
                if sn not in seen:
                    scene_windows.append({"sceneNumber": sn, "startSec": start, "endSec": end})
                    seen.add(sn)

            word_count = sum(
                len(s.get("voiceover", "").split())
                for s in self.scenes
            )

            result = validate_audio_pacing(
                video_path=video_path,
                scene_windows=scene_windows,
                total_duration_sec=self.data.get("render", {}).get("durationSeconds"),
                project_root=self.project_root,
                word_count=word_count,
            )

            for err in result.get("errors", []):
                self._err(err)
            for warn in result.get("warnings", []):
                self._warn(warn)

            metrics = result.get("metrics", {})
            self._ok(
                f"Pacing: silenceRatio={metrics.get('silenceRatio', '?')}, "
                f"narrationCoverage={metrics.get('narrationCoverageRatio', '?')}, "
                f"status={result.get('status', '?')}"
            )
        except Exception as e:
            self._warn(f"Pacing check failed: {e}")

    # ── Report ───────────────────────────────────────────────────────

    def report(self, as_json: bool = False) -> dict:
        total_errors = 0
        total_warnings = 0
        details = []

        for name, (ok, msgs) in self.all_checks:
            for sev, msg in msgs:
                if sev == "ERROR":
                    total_errors += 1
                elif sev == "WARNING":
                    total_warnings += 1
                details.append({"check": name, "severity": sev, "message": msg})

        result = {
            "jobId": self.job_id,
            "status": self.status,
            "validatedAt": datetime.now(timezone.utc).isoformat(),
            "passed": total_errors == 0,
            "totalErrors": total_errors,
            "totalWarnings": total_warnings,
            "details": details,
        }

        if as_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"\n{'='*50}")
            print(f"Validation result: {'PASS' if result['passed'] else 'FAIL'}")
            print(f"  Job: {self.job_id}")
            print(f"  Status: {self.status}")
            print(f"  Errors: {total_errors}")
            print(f"  Warnings: {total_warnings}")
            print(f"{'='*50}")

        return result


def _build_scene_windows_from_metadata(data: dict) -> dict[int, dict[str, float]]:
    windows: dict[int, dict[str, float]] = {}
    for entry in data.get("renderTimeline", []):
        sn = entry.get("sceneNumber")
        start = entry.get("startSec", 0)
        end = entry.get("endSec", 0)
        if sn is None:
            continue
        if sn not in windows:
            windows[sn] = {"startSec": float(start), "endSec": float(end)}
        else:
            windows[sn]["startSec"] = min(windows[sn]["startSec"], float(start))
            windows[sn]["endSec"] = max(windows[sn]["endSec"], float(end))
    return windows


def update_manifest_gates(metadata_path: Path):
    """Re-run coverage validation and update quality gates in job-manifest.json."""
    with open(metadata_path) as f:
        data = json.load(f)

    video_dir = metadata_path.parent
    manifest_path = video_dir / "job-manifest.json"
    if not manifest_path.exists():
        print(f"job-manifest.json not found: {manifest_path}")
        return False

    manifest = json.loads(manifest_path.read_text())

    audio_config = data.get("audio", {})
    is_continuous = audio_config.get("continuous", False)

    if is_continuous:
        from coverage_validation import run_coverage_validation
        scene_timings = audio_config.get("sceneTimings", [])
        audio_dur = audio_config.get("durationSec", 0)
        cues_by_scene = {}
        for sc in data.get("script", {}).get("scenes", []):
            sn = sc["sceneNumber"]
            cues_by_scene[sn] = sc.get("subtitleTiming", {}).get("cues", [])
        narration_units = audio_config.get("narrationUnits", [])
        coverage_result = run_coverage_validation(
            scene_timings, audio_dur, cues_by_scene, narration_units
        )
        coverage_status = coverage_result.get("status", "N/A")
    else:
        from subtitle_validation_context import build_validation_context
        ctx = build_validation_context(data, video_dir=video_dir)
        coverage_status = ctx["status"]

    gates = manifest.get("validation", {}).get("gates", {})
    if not gates:
        manifest.setdefault("validation", {})
        gates = {}
        manifest["validation"]["gates"] = gates

    gates["subtitleCoverageValidation"] = coverage_status

    sub_gates = {k: v for k, v in gates.items() if k != "qualityGate"}
    gate_failures = [k for k, v in sub_gates.items() if v == "FAIL"]
    gate_warnings = [k for k, v in sub_gates.items() if v in ("REVIEW_REQUIRED", "WARNING", "PASS_WITH_WARNINGS")]
    gate_unavailable = [k for k, v in sub_gates.items() if v == "NOT_APPLICABLE"]
    gates["qualityGate"] = (
        "FAIL" if gate_failures
        else ("WARNING" if gate_warnings
              else ("WARNING" if gate_unavailable else "PASS"))
    )
    manifest["validation"]["gates"] = gates

    manifest["validation"]["coverageStatus"] = coverage_status

    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"Updated manifest: subtitleCoverageValidation={coverage_status}, "
          f"qualityGate={gates.get('qualityGate', 'N/A')}")
    return coverage_status == "PASS"


def main() -> int:

    parser = argparse.ArgumentParser(
        description="Validate a shorts-creator job"
    )
    parser.add_argument("metadata_path", help="Path to metadata.json")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all checks")
    parser.add_argument("--update-manifest", action="store_true",
                        help="Re-run coverage validation and update manifest gates")
    args = parser.parse_args()

    metadata_path = Path(args.metadata_path).resolve()
    if not metadata_path.exists():
        print(f"ERROR: metadata not found: {metadata_path}")
        return 1

    if args.update_manifest:
        ok = update_manifest_gates(metadata_path)
        return 0 if ok else 1

    import io
    validator = JobValidator(metadata_path, verbose=args.verbose)

    if args.json:
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        all_pass = validator.run()
        sys.stdout = old_stdout
        result = validator.report(as_json=True)
        return 0 if result["passed"] else 1
    else:
        all_pass = validator.run()
        validator.report(as_json=False)
        return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
