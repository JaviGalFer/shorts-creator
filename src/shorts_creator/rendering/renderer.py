#!/usr/bin/env python3

import json
import os
import subprocess
import re
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shorts_creator.validation import asset as asset_validation
from shorts_creator.contracts.duration import evaluate_requested_duration_compliance

FPS = 25
MAX_SEGMENT_DURATION = 20.0
MAX_TOTAL_DURATION = 120
DURATION_TOLERANCE = 2.0


def _to_workspace_path(local_path: Path, project_root: Path) -> str:
    return f"/workspace/{local_path.relative_to(project_root)}"


def _to_docker_asset_path(project_root: Path, video_rel: str, asset_path: str) -> str:
    p = Path(asset_path)
    if p.is_absolute():
        return f"/workspace/{p.relative_to(project_root)}"
    return f"{video_rel}/{asset_path}"


def _docker_ffmpeg(args: list[str], project_root: Path, timeout: int = 120) -> subprocess.CompletedProcess:
    cmd = [
        'docker', 'run', '--rm',
        '-v', f'{project_root}:/workspace',
        'linuxserver/ffmpeg:latest',
    ] + args
    env = os.environ.copy()
    env.pop("DOCKER_API_VERSION", None)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)


def _docker_ffprobe_duration(ws_path: str, project_root: Path, timeout: int = 30) -> float:
    """Extract duration from a media file using ffmpeg -i (ffprobe -show_entries not available)."""
    result = _docker_ffmpeg(['-i', ws_path], project_root, timeout=timeout)
    for line in result.stderr.split('\n'):
        m = re.search(r'Duration:\s*(\d+):(\d+):([\d.]+)', line)
        if m:
            h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
            return h * 3600 + mn * 60 + s
    return 0.0


def build_motion_filter(motion_type: str, duration_sec: float, width: int, height: int) -> str:
    """Build a motion filter that produces exactly `duration_sec` of output.

    Formula: frames = round(duration_sec * FPS)
    zoompan d=frames generates exactly `frames` output frames from 1 input frame.

    For pan filters, the expression `t` goes from 0 to duration_sec over the output.
    """
    total_frames = max(1, round(duration_sec * FPS))

    if motion_type == "slow_zoom_in":
        return (
            f"trim=end_frame=1,zoompan="
            f"z='if(lte(on,1),1,min(1.15,zoom+0.002))'"
            f":d={total_frames}"
            f":x='iw/2-(iw/zoom/2)'"
            f":y='ih/2-(ih/zoom/2)'"
            f":s=1080x1920"
            f",setsar=1,format=yuv420p"
        )
    elif motion_type == "slow_zoom_out":
        return (
            f"trim=end_frame=1,zoompan="
            f"z='if(lte(on,1),1.15,max(1.0,zoom-0.002))'"
            f":d={total_frames}"
            f":x='iw/2-(iw/zoom/2)'"
            f":y='ih/2-(ih/zoom/2)'"
            f":s=1080x1920"
            f",setsar=1,format=yuv420p"
        )
    elif motion_type == "pan_left":
        return (
            f"scale=1080:1920:force_original_aspect_ratio=increase"
            f",crop=1080:1920:'floor((iw-1080)*(1-t/{duration_sec}))':0"
            f",setsar=1,format=yuv420p"
            f",trim=duration={duration_sec}"
        )
    elif motion_type == "pan_right":
        return (
            f"scale=1080:1920:force_original_aspect_ratio=increase"
            f",crop=1080:1920:'floor((iw-1080)*t/{duration_sec})':0"
            f",setsar=1,format=yuv420p"
            f",trim=duration={duration_sec}"
        )
    elif motion_type == "pan_up":
        return (
            f"scale=1080:1920:force_original_aspect_ratio=increase"
            f",crop=1080:1920:0:'floor((ih-1920)*(1-t/{duration_sec}))'"
            f",setsar=1,format=yuv420p"
            f",trim=duration={duration_sec}"
        )
    elif motion_type == "pan_down":
        return (
            f"scale=1080:1920:force_original_aspect_ratio=increase"
            f",crop=1080:1920:0:'floor((ih-1920)*t/{duration_sec})'"
            f",setsar=1,format=yuv420p"
            f",trim=duration={duration_sec}"
        )
    elif motion_type == "detail_crop":
        scale_factor = max(1080 / width, 1920 / height) if width and height else 1.85
        return (
            f"scale={int(width * scale_factor)}:{int(height * scale_factor)}"
            f":force_original_aspect_ratio=increase"
            f",crop=1080:1920"
            f",setsar=1,format=yuv420p"
            f",trim=duration={duration_sec}"
        )
    else:
        return (
            f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
            f",setsar=1,format=yuv420p"
            f",trim=duration={duration_sec}"
        )


def build_asset_base_filter(asset_type: str, focal_region: str, w: int, h: int, motion_type: str, duration_sec: float) -> str:
    """Build base asset treatment without duration control (duration added by motion filter)."""
    is_landscape = w > h if w and h else False
    needs_map_treatment = asset_type in ("historical_map", "map", "document") and is_landscape

    if needs_map_treatment:
        if focal_region == "north":
            crop_expr = "crop=1080:1920:0:0"
        elif focal_region == "south":
            crop_expr = "crop=1080:1920:0:max(0,ih-1920)"
        elif focal_region == "east":
            crop_expr = "crop=1080:1920:max(0,iw-1080):0"
        elif focal_region == "west":
            crop_expr = "crop=1080:1920:0:0"
        else:
            crop_expr = "crop=1080:1920:(iw-1080)/2:(ih-1920)/2"
        return (
            f"split[bg][fg];"
            f"[bg]scale=1080:1920:force_original_aspect_ratio=increase,{crop_expr},"
            f"gblur=sigma=40,format=yuv420p[bgb];"
            f"[fg]scale=1080:1920:force_original_aspect_ratio=increase,setsar=1,format=rgba,{crop_expr}[fgc];"
            f"[bgb][fgc]overlay=(W-w)/2:(H-h)/2"
        )
    elif asset_type == "generated_reconstruction":
        return (
            "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            "setsar=1,format=yuv420p,colorlevels=rimax=0.85:gimax=0.85:bimax=0.85,"
            "noise=alls=3:allf=t+u,format=yuv420p"
        )
    else:
        return "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,format=yuv420p"


def build_overlay_filter(overlay_text: str, input_label: str, out_label: str) -> str:
    if not overlay_text:
        return f"[{input_label}]null[{out_label}]"
    escaped = overlay_text.replace("'", "'\\\\\\''").replace(":", "\\:").replace("}", "\\}")
    return (
        f"[{input_label}]drawtext="
        f"text='{escaped}'"
        f":fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        f":fontsize=42"
        f":fontcolor=white@0.9"
        f":box=1"
        f":boxcolor=black@0.5"
        f":x=(w-text_w)/2"
        f":y=80"
        f":boxborderw=12"
        f"[{out_label}]"
    )


# ---------------------------------------------------------------------------
# Cross-job artifact isolation
# ---------------------------------------------------------------------------

_PATH_KEYS = {
    "path", "imagepath", "assetpath", "audiopath",
}


def _collect_local_paths(obj: Any) -> list[str]:
    """Collect string values from known path fields in metadata."""
    paths: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key_lower = k.lower()
            if isinstance(v, str) and (key_lower in _PATH_KEYS or key_lower.endswith("path")):
                val = v.strip()
                if val and not val.lower().startswith(("http://", "https://", "data:")):
                    paths.append(val)
            elif isinstance(v, (dict, list)):
                paths.extend(_collect_local_paths(v))
    elif isinstance(obj, list):
        for item in obj:
            paths.extend(_collect_local_paths(item))
    return paths


def validate_no_cross_job_paths(data: dict, video_dir: Path, project_root: Path) -> list[str]:
    """Return errors for any local path that does not belong to the current job directory."""
    errors: list[str] = []
    video_dir_resolved = video_dir.resolve()
    for raw in _collect_local_paths(data):
        raw_path = Path(raw)
        if raw_path.is_absolute():
            resolved = raw_path.resolve()
        else:
            candidate = video_dir_resolved / raw_path
            candidate2 = project_root.resolve() / raw_path
            if candidate.exists():
                resolved = candidate.resolve()
            elif candidate2.exists():
                resolved = candidate2.resolve()
            else:
                resolved = candidate
        try:
            resolved.relative_to(video_dir_resolved)
        except ValueError:
            errors.append(
                f"CROSS_JOB_ARTIFACT_REFERENCE: path={raw} resolves outside current job dir "
                f"({video_dir_resolved})"
            )
    return errors


# ---------------------------------------------------------------------------
# Preflight validation
# ---------------------------------------------------------------------------

def build_per_scene_audio_filter(
    input_index: int,
    scene_number: int,
    scene_window_sec: float,
    active_audio_sec: float | None = None,
) -> str:
    """Build FFmpeg audio filter chain for a per-scene MP3 input.

    Chain: aresample=44100 → asetpts=PTS-STARTPTS →
           (atrim=duration=active_audio if provided) →
           apad → atrim=duration=window

    When active_audio_sec is provided, the audio is first trimmed to
    that duration (removing room tone), then apad adds the configured
    tail pause.
    """
    if not isinstance(input_index, int) or isinstance(input_index, bool):
        raise TypeError(f"input_index must be int, got {type(input_index).__name__}")
    if input_index < 0:
        raise ValueError(f"input_index must be non-negative, got {input_index}")
    if not isinstance(scene_number, int) or isinstance(scene_number, bool):
        raise TypeError(f"scene_number must be int, got {type(scene_number).__name__}")
    if scene_number <= 0:
        raise ValueError(f"scene_number must be positive, got {scene_number}")
    if not isinstance(scene_window_sec, (int, float)) or isinstance(scene_window_sec, bool):
        raise TypeError(
            f"scene_window_sec must be numeric, got {type(scene_window_sec).__name__}"
        )
    if not math.isfinite(scene_window_sec):
        raise ValueError(f"scene_window_sec must be finite, got {scene_window_sec}")
    if scene_window_sec <= 0:
        raise ValueError(f"scene_window_sec must be positive, got {scene_window_sec}")

    if active_audio_sec is not None:
        if not isinstance(active_audio_sec, (int, float)) or isinstance(active_audio_sec, bool):
            raise TypeError(f"active_audio_sec must be numeric, got {type(active_audio_sec).__name__}")
        if not math.isfinite(active_audio_sec) or active_audio_sec <= 0:
            raise ValueError(f"active_audio_sec must be finite and positive, got {active_audio_sec}")
        if active_audio_sec > scene_window_sec:
            raise ValueError(
                f"active_audio_sec={active_audio_sec} must not exceed scene_window_sec={scene_window_sec}"
            )
        return (
            f'[{input_index}:a]aresample=44100,asetpts=PTS-STARTPTS,'
            f'atrim=duration={active_audio_sec},apad,atrim=duration={scene_window_sec}[a{scene_number}]'
        )

    return (
        f'[{input_index}:a]aresample=44100,asetpts=PTS-STARTPTS,'
        f'apad,atrim=duration={scene_window_sec}[a{scene_number}]'
    )


def resolve_expected_duration(
    render_timeline: list[dict],
    *,
    is_continuous_audio: bool,
    continuous_duration_sec: float | None = None,
) -> float:
    """Return expected video duration from the render timeline.

    Non-continuous: max(endSec) from timeline entries.
    Continuous: uses the provided continuous_duration_sec.
    """
    if is_continuous_audio:
        if continuous_duration_sec is None:
            raise ValueError("continuous_duration_sec is required for continuous audio")
        if not isinstance(continuous_duration_sec, (int, float)) or isinstance(continuous_duration_sec, bool):
            raise TypeError(
                f"continuous_duration_sec must be numeric, got {type(continuous_duration_sec).__name__}"
            )
        if not math.isfinite(continuous_duration_sec):
            raise ValueError(f"continuous_duration_sec must be finite, got {continuous_duration_sec}")
        if continuous_duration_sec <= 0:
            raise ValueError(f"continuous_duration_sec must be positive, got {continuous_duration_sec}")
        return float(continuous_duration_sec)

    if not render_timeline:
        raise ValueError("render_timeline must be non-empty for non-continuous audio")

    end_values = []
    for entry in render_timeline:
        end = entry.get("endSec", 0)
        if not isinstance(end, (int, float)) or isinstance(end, bool):
            raise TypeError(f"endSec must be numeric, got {type(end).__name__}")
        if not math.isfinite(end):
            raise ValueError(f"endSec must be finite, got {end}")
        if end < 0:
            raise ValueError(f"endSec must be non-negative, got {end}")
        end_values.append(float(end))

    return round(max(end_values), 3)


def preflight_validate(render_timeline: list[dict], scenes: list[dict], project_root: Path, video_dir: Path,
                       expected_total: float | None = None,
                       is_continuous_audio: bool = False,
                       metadata: dict | None = None) -> list[str]:
    errors = []

    if metadata is not None:
        errors.extend(validate_no_cross_job_paths(metadata, video_dir, project_root))

    audio_durations = {}

    for sc in scenes:
        sn = sc["sceneNumber"]
        audio_path = video_dir / "scenes" / f"scene-{sn:02}.mp3"
        if audio_path.exists():
            try:
                ws_path = _to_workspace_path(audio_path.resolve(), project_root)
                dur = _docker_ffprobe_duration(ws_path, project_root)
                if dur > 0:
                    audio_durations[sn] = dur
            except Exception:
                pass

    if is_continuous_audio:
        starts = []
        ends = []
        for entry in render_timeline:
            starts.append(entry.get("startSec", 0))
            ends.append(entry.get("endSec", 0))
        total_video_sec = max(ends) - min(starts) if ends else 0.0
    else:
        total_video_sec = max(
            (entry.get("endSec", 0) for entry in render_timeline),
            default=0.0,
        )

    for i, entry in enumerate(render_timeline):
        prefix = f"  entry[{i}] scene={entry.get('sceneNumber')} beat={entry.get('beatIndex')}"
        dur = entry.get("durationSec", 0)
        start = entry.get("startSec", 0)
        end = entry.get("endSec", 0)

        if not isinstance(start, (int, float)) or isinstance(start, bool) or not math.isfinite(start):
            errors.append(f"{prefix}: startSec={start} is not a finite number")
        if not isinstance(end, (int, float)) or isinstance(end, bool) or not math.isfinite(end):
            errors.append(f"{prefix}: endSec={end} is not a finite number")
        if not isinstance(dur, (int, float)) or isinstance(dur, bool) or not math.isfinite(dur):
            errors.append(f"{prefix}: durationSec={dur} is not a finite number")

        if start < 0:
            errors.append(f"{prefix}: startSec={start} < 0")
        if end <= start:
            errors.append(f"{prefix}: endSec={end} <= startSec={start}")
        if dur <= 0:
            errors.append(f"{prefix}: durationSec={dur} <= 0")
        if dur > MAX_SEGMENT_DURATION:
            errors.append(f"{prefix}: durationSec={dur} > {MAX_SEGMENT_DURATION}s (max segment)")
        expected_dur = end - start
        if abs(dur - expected_dur) > 0.05:
            errors.append(f"{prefix}: durationSec={dur:.3f} != end-start={expected_dur:.3f}")

        asset_path = entry.get("assetPath") or ""
        if not asset_path:
            errors.append(f"{prefix}: assetPath is empty/null — unresolved asset")
        else:
            p = Path(asset_path)
            if p.is_absolute():
                full_path = p
            else:
                full_path = video_dir / asset_path
            if not full_path.exists():
                errors.append(f"{prefix}: assetPath={asset_path} not found")

    # ── Per-scene aggregate audio validation (non-continuous) ────────
    if not is_continuous_audio:
        scene_entries: dict[int, list[dict]] = {}
        for entry in render_timeline:
            sn = entry.get("sceneNumber")
            if sn is not None:
                scene_entries.setdefault(sn, []).append(entry)

        for sn, entries in scene_entries.items():
            entries.sort(key=lambda e: e.get("startSec", 0))
            scene_start = min(e.get("startSec", 0) for e in entries)
            scene_end = max(e.get("endSec", 0) for e in entries)
            scene_window = scene_end - scene_start

            # Check contiguous: gaps and overlaps between entries
            for i in range(len(entries) - 1):
                curr_end = entries[i].get("endSec", 0)
                next_start = entries[i + 1].get("startSec", 0)
                delta = next_start - curr_end
                if delta > 0.05:
                    errors.append(
                        f"scene {sn}: non-contiguous gap: "
                        f"entry[{i}] end={curr_end:.3f}s → entry[{i+1}] start={next_start:.3f}s "
                        f"(gap={delta:.3f}s)"
                    )
                elif delta < -0.05:
                    errors.append(
                        f"scene {sn}: overlapping segments: "
                        f"entry[{i}] end={curr_end:.3f}s → entry[{i+1}] start={next_start:.3f}s "
                        f"(overlap={-delta:.3f}s)"
                    )

            # Check audio paths consistent within scene
            audio_paths = {e.get("audioPath", "") for e in entries}
            if len(audio_paths) > 1:
                errors.append(
                    f"scene {sn}: inconsistent audio paths: {audio_paths}"
                )

            # Resolve audio path from entries (with fallback to canonical)
            resolved_audio_path = None
            for e in entries:
                ap = e.get("audioPath", "")
                if ap and isinstance(ap, str) and ap.strip():
                    p = Path(ap)
                    if p.is_absolute():
                        resolved_audio_path = p
                    else:
                        resolved_audio_path = video_dir / ap
                    if not resolved_audio_path.exists():
                        resolved_audio_path = None
                    else:
                        break
            if resolved_audio_path is None:
                canonical = video_dir / "scenes" / f"scene-{sn:02}.mp3"
                if canonical.exists():
                    resolved_audio_path = canonical

            if resolved_audio_path and resolved_audio_path.exists():
                try:
                    ws_path = _to_workspace_path(resolved_audio_path.resolve(), project_root)
                    dur = _docker_ffprobe_duration(ws_path, project_root)
                    if dur > 0:
                        audio_durations[sn] = dur
                except Exception:
                    pass

            audio_dur = audio_durations.get(sn)
            if audio_dur is not None and audio_dur > 0:
                # Use active audio duration when available (room tone is trimmed)
                effective_audio = audio_dur
                if metadata is not None:
                    for ae in metadata.get("audio", {}).get("scenes", []):
                        if ae.get("sceneNumber") == sn:
                            act = ae.get("activeAudioDurationSec")
                            if isinstance(act, (int, float)) and not isinstance(act, bool):
                                if math.isfinite(act) and act > 0:
                                    effective_audio = min(effective_audio, float(act))
                            break
                tolerance = 0.10
                if effective_audio > scene_window + tolerance:
                    errors.append(
                        f"scene {sn}: audio={audio_dur:.2f}s > "
                        f"scene_window={scene_window:.2f}s + tolerance={tolerance}s "
                        f"(audio would be truncated)"
                    )

    if expected_total is None:
        expected_total = sum(
            float(sc.get("targetDurationSec", 0)) for sc in scenes
        )
    if abs(total_video_sec - expected_total) > 3.0:
        errors.append(
            f"total timeline={total_video_sec:.1f}s vs expected={expected_total:.1f}s "
            f"(delta={abs(total_video_sec - expected_total):.1f}s > 3.0s)"
        )
    if total_video_sec > MAX_TOTAL_DURATION:
        errors.append(f"total timeline={total_video_sec:.1f}s > {MAX_TOTAL_DURATION}s")

    return errors


# ---------------------------------------------------------------------------
# Post-render validation
# ---------------------------------------------------------------------------

def post_render_validate(video_path: Path, expected_duration: float, metadata: dict, project_root: Path,
                         is_continuous_audio: bool = False) -> dict:
    """Run ffprobe-based validation on the rendered file."""
    ws_path = _to_workspace_path(video_path.resolve(), project_root)
    actual_duration = _docker_ffprobe_duration(ws_path, project_root)
    audio_duration = _docker_ffprobe_duration(ws_path, project_root)

    delta = actual_duration - expected_duration

    # Tight tolerance (0.10s) for continuous audio; 2.0s for per-scene audio
    tolerance = 0.10 if is_continuous_audio else DURATION_TOLERANCE

    return {
        "expectedDurationSec": round(expected_duration, 2),
        "actualVideoDurationSec": round(actual_duration, 2),
        "actualAudioDurationSec": round(audio_duration, 2),
        "durationDeltaSec": round(delta, 2),
        "durationOk": abs(delta) <= tolerance,
        "durationToleranceSec": tolerance,
        "maxDurationOk": actual_duration <= MAX_TOTAL_DURATION,
    }


def extract_validation_frames(video_path: Path, output_dir: Path, project_root: Path, points: list[float] | None = None):
    """Extract frames at given percentage points for visual validation."""
    if points is None:
        points = [0.0, 0.25, 0.50, 0.75, 0.95]
    output_dir.mkdir(parents=True, exist_ok=True)

    ws_path = _to_workspace_path(video_path.resolve(), project_root)
    duration = _docker_ffprobe_duration(ws_path, project_root)

    if duration <= 0:
        return []

    frames = []
    for pct in points:
        ts = duration * pct
        local_out = output_dir / f"frame_{pct*100:.0f}pct.png"
        ws_out = _to_workspace_path(local_out.resolve(), project_root)
        _docker_ffmpeg(
            ["-y", "-ss", str(ts), "-i", ws_path,
             "-vframes", "1", "-q:v", "2", ws_out],
            project_root, timeout=60
        )
        if local_out.exists():
            frames.append({"timestamp": round(ts, 2), "path": str(local_out), "pct": pct})

    return frames


def detect_black_frames(video_path: Path, project_root: Path, threshold: float = 25.0) -> list[dict]:
    """Detect near-black frames using ffmpeg's blackdetect filter."""
    ws_path = _to_workspace_path(video_path.resolve(), project_root)
    result = _docker_ffmpeg(
        ["-i", ws_path,
         "-vf", "blackdetect=d=0.5:pix_th=0.10",
         "-f", "null", "-"],
        project_root, timeout=120
    )
    warnings = []
    stderr = result.stderr
    for match in re.finditer(
        r"blackdetect.*black_start:([\d.]+).*black_end:([\d.]+).*black_duration:([\d.]+)",
        stderr
    ):
        warnings.append({
            "startSec": float(match.group(1)),
            "endSec": float(match.group(2)),
            "durationSec": float(match.group(3)),
        })
    return warnings


def validate_ass_style(ass_path: Path, expected_style: str = "shorts_upper_dynamic") -> dict:
    """Parse the final ASS file and validate subtitle style matches the resolved config.
    Returns {'ok': bool, 'checks': dict, 'errors': list}."""
    checks = {}
    errors = []
    if not ass_path.exists():
        return {"ok": False, "checks": {}, "errors": ["ASS file not found"]}

    text = ass_path.read_text()
    style_found = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Style:"):
            parts = line.split(",")
            if len(parts) >= 10:
                name = parts[0].replace("Style:", "").strip()
                if name == expected_style:
                    style_found = parts
                    break

    if not style_found:
        for line in text.splitlines():
            if line.startswith("Style:"):
                style_found = line.split(",")
                break

    if not style_found:
        return {"ok": False, "checks": {}, "errors": ["No Style line found in ASS"]}

    parts = style_found
    # Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour,
    #         OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut,
    #         ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow,
    #         Alignment, MarginL, MarginR, MarginV, Encoding
    try:
        border_style = int(parts[15].strip()) if len(parts) > 15 else None
        outline = float(parts[16].strip()) if len(parts) > 16 else None
        shadow = float(parts[17].strip()) if len(parts) > 17 else None
        alignment = int(parts[18].strip()) if len(parts) > 18 else None
        margin_v = int(parts[21].strip()) if len(parts) > 21 else None
        back_colour = parts[6].strip() if len(parts) > 6 else ""
        fontname = parts[1].strip() if len(parts) > 1 else ""
        fontsize = float(parts[2].strip()) if len(parts) > 2 else None
    except (ValueError, IndexError):
        return {"ok": False, "checks": {}, "errors": ["Failed to parse ASS Style line"]}

    # Upper-middle checks
    if alignment is not None:
        checks["alignment"] = alignment
        if alignment != 8:
            errors.append(f"Alignment={alignment}, expected 8 (upper-middle)")
    else:
        errors.append("Alignment not found in ASS style")

    if margin_v is not None:
        checks["marginV"] = margin_v
        if margin_v < 300 or margin_v > 600:
            errors.append(f"MarginV={margin_v}, expected ~430 (upper-middle range 300-600)")
    else:
        errors.append("MarginV not found in ASS style")

    if border_style is not None:
        checks["borderStyle"] = border_style
        if border_style != 1:
            errors.append(f"BorderStyle={border_style}, expected 1")
    else:
        errors.append("BorderStyle not found")

    if outline is not None:
        checks["outline"] = outline
        if outline < 3:
            errors.append(f"Outline={outline}, expected >= 3")
    else:
        errors.append("Outline not found")

    if shadow is not None:
        checks["shadow"] = shadow
        if shadow < 1:
            errors.append(f"Shadow={shadow}, expected >= 1")
    else:
        errors.append("Shadow not found")

    # Background box check: back_colour alpha should be 00 (fully transparent) for no box
    if back_colour.startswith("&H"):
        alpha = back_colour[2:4] if len(back_colour) >= 4 else ""
        checks["backColourAlpha"] = alpha
        if alpha and alpha != "00":
            errors.append(f"BackColour alpha={alpha}, expected 00 (no background box)")
    else:
        checks["backColour"] = back_colour

    checks["fontname"] = fontname
    checks["fontsize"] = fontsize

    return {"ok": len(errors) == 0, "checks": checks, "errors": errors}


def detect_freeze_frames(video_path: Path, project_root: Path, threshold: float = 0.01) -> list[dict]:
    """Detect frozen frames by comparing consecutive frames with ffmpeg's freezedetect."""
    ws_path = _to_workspace_path(video_path.resolve(), project_root)
    result = _docker_ffmpeg(
        ["-i", ws_path,
         "-vf", f"freezedetect=d=3:noise=0.01",
         "-f", "null", "-"],
        project_root, timeout=120
    )
    warnings = []
    stderr = result.stderr
    for match in re.finditer(
        r"freezedetect.*freeze_start:([\d.]+).*freeze_end:([\d.]+).*freeze_duration:([\d.]+)",
        stderr
    ):
        warnings.append({
            "startSec": float(match.group(1)),
            "endSec": float(match.group(2)),
            "durationSec": float(match.group(3)),
        })
    return warnings


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def resolve_manifest_scene_audio_duration(
        audio_config: dict,
        scene_number: int,
) -> float | None:
    """Return the actual audio duration for a scene from metadata.

    Looks up audio.scenes[] by sceneNumber. Returns None if:
    - scene not found
    - durationSec is None, NaN, inf, bool, str, zero, or negative
    - audio is continuous (use audio.durationSec instead)
    """
    if audio_config.get("continuous", False):
        return None

    scenes = audio_config.get("scenes", [])
    for entry in scenes:
        if entry.get("sceneNumber") == scene_number:
            dur = entry.get("durationSec")
            if not isinstance(dur, (int, float)) or isinstance(dur, bool):
                return None
            if not math.isfinite(dur) or dur <= 0:
                return None
            return float(dur)
    return None


def render_job(
    *,
    metadata_path: str | Path,
    skip_validation: bool = False,
    skip_asset_validation: bool = False,
    skip_render: bool = False,
) -> int:
    """Render one prepared job and persist render validation metadata."""
    metadata_path = Path(metadata_path).resolve()
    project_root = metadata_path.parents[3]
    video_dir = metadata_path.parent
    data = json.loads(metadata_path.read_text())

    render_timeline = data.get("renderTimeline")
    if not render_timeline:
        print("ERROR: no renderTimeline in metadata. Run prepare_job.py first.")
        return 1

    # -- Asset validation quality gate --
    if not skip_asset_validation:
        asset_result = asset_validation.validate_job_for_render(data, project_root, video_dir)
        data["assetValidation"] = asset_result
        if asset_result["status"] == "BLOCKED":
            print("ASSET VALIDATION BLOCKED — render aborted:")
            for f in asset_result["failures"]:
                print(f"  [{f['rule']}] {f['message']}")
            print(json.dumps({"jobId": data["jobId"], "assetValidation": asset_result["status"], "summary": asset_result["summary"]}))
            data["status"] = "ASSET_FAILED"
            data["updatedAt"] = datetime.utcnow().isoformat() + "Z"
            metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            return 1
        elif asset_result["status"] == "REVIEW_REQUIRED":
            print("WARNING: Asset validation requires review. Rendering anyway.")
            if data.get("status") not in ("ASSET_FAILED", "RENDERED"):
                data["status"] = "REVIEW_REQUIRED"
        else:
            print(f"Asset validation PASSED ({asset_result['summary']['validAssets']}/{asset_result['summary']['totalSegments']} segments valid)")
    else:
        print("Asset validation skipped (--skip-asset-validation)")

    audio_config = data.get('audio', {})
    is_continuous_audio = audio_config.get('continuous', False)

    # -- Resolve expected duration (single source of truth) --
    expected_duration = resolve_expected_duration(
        render_timeline,
        is_continuous_audio=is_continuous_audio,
        continuous_duration_sec=(
            audio_config.get("durationSec") if is_continuous_audio else None
        ),
    )

    # -- Preflight validation --
    if not skip_validation:
        errors = preflight_validate(render_timeline, data["script"]["scenes"], project_root, video_dir,
                                    expected_total=expected_duration, is_continuous_audio=is_continuous_audio,
                                    metadata=data)
        if errors:
            print("PREFLIGHT VALIDATION FAILED:")
            for e in errors:
                print(f"  {e}")
            print("Aborting render. Fix issues and retry.")
            print(json.dumps({"jobId": data["jobId"], "preflightErrors": errors, "preflightOk": False}))
            data["validation"] = data.get("validation", {})
            data["validation"]["preflight"] = {"ok": False, "errors": errors}
            data["status"] = "RENDER_FAILED"
            data["updatedAt"] = datetime.utcnow().isoformat() + "Z"
            metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            return 1
        else:
            print("Preflight validation PASSED")

    validation_dir = video_dir / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)

    video_rel = f'/workspace/{video_dir.relative_to(project_root)}'
    cta = data.get("cta", {})

    ffmpeg_args = [
        'docker', 'run', '--rm',
        '-v', f'{project_root}:/workspace',
        'linuxserver/ffmpeg:latest',
        '-y',
    ]

    filter_parts = []
    input_index = 0
    scene_audio_map = {}
    narration_audio_ix = None

    # ── Active audio duration map from metadata ────────────────────────
    active_audio_map: dict[int, float] = {}
    if not is_continuous_audio:
        for ae in audio_config.get("scenes", []):
            sn = ae.get("sceneNumber")
            active = ae.get("activeAudioDurationSec")
            if isinstance(sn, int) and isinstance(active, (int, float)) and not isinstance(active, bool):
                if math.isfinite(active) and active > 0:
                    active_audio_map[sn] = float(active)

    # ── Per-scene window computation ──────────────────────────────────
    scene_windows: dict[int, dict[str, float]] = {}
    for entry in render_timeline:
        sn = int(entry["sceneNumber"])
        start = float(entry.get("startSec", 0))
        end = float(entry.get("endSec", 0))
        if sn not in scene_windows:
            scene_windows[sn] = {"startSec": start, "endSec": end}
        else:
            scene_windows[sn]["startSec"] = min(scene_windows[sn]["startSec"], start)
            scene_windows[sn]["endSec"] = max(scene_windows[sn]["endSec"], end)

    if is_continuous_audio:
        narration_rel = str(video_dir / "scenes" / "narration.mp3")
        docker_narration = narration_rel.replace(str(project_root) + "/", "/workspace/")
        ffmpeg_args.extend(['-i', docker_narration])
        narration_audio_ix = input_index
        filter_parts.append(
            f'[{input_index}:a]aresample=44100,asetpts=PTS-STARTPTS[narration_a]'
        )
        input_index += 1

    for entry in render_timeline:
        sn = entry["sceneNumber"]
        dur = entry["durationSec"]
        seg_idx = entry.get("segmentIndex", 1)
        asset_path = entry.get("assetPath") or ""

        if not asset_path:
            print(f"FATAL: entry scene={sn} has null assetPath — unresolved asset, aborting")
            ffmpeg_ok = False
            ffmpeg_exit_code = -1
            break

        img_rel = _to_docker_asset_path(project_root, video_rel, asset_path)

        ffmpeg_args.extend(['-loop', '1', '-i', img_rel])
        video_ix = input_index
        input_index += 1

        # Audio input (per-scene only in non-continuous mode)
        if not is_continuous_audio:
            if sn not in scene_audio_map:
                audio_rel = entry.get("audioPath", "")
                if not audio_rel:
                    audio_rel = str(video_dir / "scenes" / f"scene-{sn:02}.mp3")
                docker_audio = audio_rel.replace(str(project_root) + "/", "/workspace/")
                ffmpeg_args.extend(['-i', docker_audio])
                scene_audio_map[sn] = input_index
                sw = scene_windows.get(sn, {"startSec": 0, "endSec": dur})
                scene_window_sec = round(sw["endSec"] - sw["startSec"], 3)
                active_sec = active_audio_map.get(sn)
                filter_parts.append(
                    build_per_scene_audio_filter(input_index, sn, scene_window_sec, active_audio_sec=active_sec)
                )
                input_index += 1

        # Build visual filter chain
        asset_type = entry.get("assetType", "broll")
        w = entry.get("width", 0) or 0
        h = entry.get("height", 0) or 0
        focal_region = entry.get("focalRegion", "center")
        motion_type = entry.get("motionType", "static")
        overlay_text = entry.get("overlayText", "")

        motion_filter = build_motion_filter(motion_type, dur, w, h)

        if asset_type in ("historical_map", "map", "document") and (w or h) and (w > h if w and h else False):
            base = build_asset_base_filter(asset_type, focal_region, w, h, motion_type, dur)
            if motion_type in ("slow_zoom_in", "slow_zoom_out"):
                # base includes overlay but NOT trim; motion includes trim=end_frame+zoompan+d
                out_label = f"s{sn}_{seg_idx}"
                filter_parts.append(f"[{video_ix}:v]{base}[m_base_{out_label}];[m_base_{out_label}]{motion_filter}[{out_label}]")
            else:
                out_label = f"s{sn}_{seg_idx}"
                filter_parts.append(f"[{video_ix}:v]{base},{motion_filter}[{out_label}]")
        elif motion_type in ("slow_zoom_in", "slow_zoom_out"):
            base = build_asset_base_filter(asset_type, focal_region, w, h, motion_type, dur)
            out_label = f"s{sn}_{seg_idx}"
            filter_parts.append(f"[{video_ix}:v]{base},{motion_filter}[{out_label}]")
        else:
            out_label = f"s{sn}_{seg_idx}"
            filter_parts.append(f"[{video_ix}:v]{motion_filter}[{out_label}]")

        # Overlay (only render if explicitly enabled or env var set)
        overlay_enabled = entry.get("overlayEnabled", False) or os.environ.get("ENABLE_EDITORIAL_OVERLAYS", "").lower() in ("true", "1")
        overlay_label = f"ov_{sn}_{seg_idx}"
        if overlay_text and overlay_enabled:
            ov_filter = build_overlay_filter(overlay_text, out_label, overlay_label)
        else:
            ov_filter = f"[{out_label}]null[{overlay_label}]"
        filter_parts.append(ov_filter)
        entry["_vlabel"] = overlay_label

    # Build scene groups with concat
    scene_groups = {}
    for entry in render_timeline:
        sn = entry["sceneNumber"]
        scene_groups.setdefault(sn, []).append(entry)

    for sn, entries in scene_groups.items():
        if len(entries) == 1:
            e = entries[0]
            filter_parts.append(f'[{e["_vlabel"]}]null[scene_v{sn}]')
        else:
            seg_labels = []
            for i, e in enumerate(entries):
                vl = e["_vlabel"]

                if i > 0:
                    fade_duration = min(0.35, e["durationSec"] * 0.15)
                    fade_duration = max(0.15, fade_duration)
                    prev_vl = entries[i - 1]["_vlabel"]
                    prev_dur = entries[i - 1]["durationSec"]
                    fade_out = (
                        f"[{prev_vl}]fade=t=out:st={prev_dur - fade_duration}:d={fade_duration}"
                        f",setpts=PTS-STARTPTS[fo_{prev_vl}]"
                    )
                    filter_parts.append(fade_out)
                    seg_labels[-1] = f'[fo_{prev_vl}]'

                    fade_in = (
                        f"[{vl}]fade=t=in:st=0:d={fade_duration}"
                        f",setpts=PTS-STARTPTS[fi_{vl}]"
                    )
                    filter_parts.append(fade_in)
                    seg_labels.append(f'[fi_{vl}]')
                else:
                    seg_labels.append(f'[{vl}]')

            concat_segments = ''.join(seg_labels) + f'concat=n={len(entries)}:v=1:a=0[scene_v{sn}]'
            filter_parts.append(concat_segments)

    # Interleave video + audio
    sorted_sns = sorted(scene_groups.keys())
    interleaved = []
    for sn in sorted_sns:
        interleaved.append(f'[scene_v{sn}]')
        if not is_continuous_audio:
            interleaved.append(f'[a{sn}]')

    if is_continuous_audio:
        concat_all = ''.join(interleaved) + f'concat=n={len(scene_groups)}:v=1:a=0[vcat]'
    else:
        concat_all = ''.join(interleaved) + f'concat=n={len(scene_groups)}:v=1:a=1[vcat][acat]'
    filter_parts.append(concat_all)

    # Subtitles
    subtitle_format = data.get('subtitles', {}).get('format', 'ass')
    subtitle_rel = f'{video_rel}/subtitle.{subtitle_format}'
    if subtitle_format == 'ass':
        filter_parts.append(f'[vcat]ass={subtitle_rel}[vsub]')
    else:
        filter_parts.append(
            f"[vcat]subtitles={subtitle_rel}"
            f":force_style='FontName=Arial,FontSize=18,Alignment=2,MarginV=60,Outline=2,Shadow=1'[vsub]"
        )

    # CTA
    if cta.get("enabled") and cta.get("text"):
        cta_dur = cta.get("durationSec", 2.0)
        cta_asset = cta.get("assetPath", "")
        if cta_asset:
            cta_img_rel = f'{video_rel}/{cta_asset}'
        else:
            cta_img_rel = f'{video_rel}/scenes/scene-{sorted_sns[-1]:02}-01.jpg'

        ffmpeg_args.extend(['-loop', '1', '-t', str(cta_dur), '-i', cta_img_rel])
        cta_video_ix = input_index
        input_index += 1

        cta_text = cta.get("text", "").replace("'", "'\\\\\\''").replace(":", "\\:")
        cta_filter = (
            f"[{cta_video_ix}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"setsar=1,format=yuv420p,"
            f"drawtext=text='{cta_text}'"
            f":fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            f":fontsize=56"
            f":fontcolor=white@0.95"
            f":box=1"
            f":boxcolor=black@0.6"
            f":x=(w-text_w)/2"
            f":y=(h-text_h)/2"
            f":boxborderw=20"
            f"[cta_v]"
        )
        filter_parts.append(cta_filter)
        filter_parts.append(f"[vsub][cta_v]concat=n=2:v=1:a=0[cta_out]")
        if is_continuous_audio:
            filter_parts.append(f"[narration_a]anull[acta_out]")
        else:
            filter_parts.append(f"[acat]anull[acta_out]")
        vout_label = "cta_out"
        aout_label = "acta_out"
        expected_duration += cta_dur
    else:
        vout_label = "vsub"
        aout_label = "narration_a" if is_continuous_audio else "acat"

    # ── Music mixing ──────────────────────────────────────────────────
    music_cfg = data.get("request", {}).get("music", {})
    music_enabled = music_cfg.get("enabled", False)
    music_path_str = music_cfg.get("path") or ""
    music_volume_db = float(music_cfg.get("volumeDb", -24))
    music_duck = music_cfg.get("duckUnderVoice", True)
    music_fade_in = int(music_cfg.get("fadeInMs", 300))
    music_fade_out = int(music_cfg.get("fadeOutMs", 500))

    if music_enabled:
        music_path = Path(music_path_str)
        if music_path_str and music_path.exists():
            docker_music = str(music_path).replace(str(project_root) + "/", "/workspace/")
            ffmpeg_args.extend(['-i', docker_music])
            music_input_ix = input_index
            input_index += 1

            volume_filter = f"volume={music_volume_db}dB"
            fade_filter = (
                f"afade=t=in:d={music_fade_in/1000:.3f}"
                f",afade=t=out:st={expected_duration - music_fade_out/1000:.3f}"
                f":d={music_fade_out/1000:.3f}"
            ) if expected_duration > 0 else f"afade=t=in:d={music_fade_in/1000:.3f}"

            music_label = "music_mixed"
            filter_parts.append(
                f"[{music_input_ix}:a]{volume_filter},{fade_filter}[music_proc]"
            )

            if music_duck:
                # Sidechain compression: duck music when narration is present
                duck_filter = (
                    f"[music_proc]asidedata[m];"
                    f"[{aout_label}][m]sidechaincompress=threshold=0.015:ratio=3:attack=10:release=100"
                    f":makeup=1[mixed]"
                )
                filter_parts.append(duck_filter)
                aout_label = "mixed"
            else:
                filter_parts.append(
                    f"[{aout_label}][music_proc]amix=inputs=2:duration=first:dropout_transition=2[mixed]"
                )
                aout_label = "mixed"

            print(f"  Music enabled: {music_path.name} at {music_volume_db}dB, duck={music_duck}")
        else:
            print(f"WARNING: Music enabled but path not found: {music_path_str}")
            data.setdefault("reviewReasons", []).append(
                "MUSIC_ENABLED_NO_PATH: music.enabled=true but source/path is missing"
            )
            if data.get("status") not in ("RENDERED", "RENDERED_WITH_WARNINGS", "RENDERED_WITH_ASSET_WARNINGS"):
                data["status"] = "REVIEW_REQUIRED"

    output_rel = f'{video_rel}/video.mp4'

    # Determine if shortest should be applied: trim video to audio length
    # unless an explicit outro is configured
    request = data.get("request", {})
    outro_enabled = request.get("outro", {}).get("enabled", False)
    use_shortest = is_continuous_audio and not outro_enabled

    ffmpeg_args.extend([
        '-filter_complex', ';'.join(filter_parts),
        '-map', f'[{vout_label}]',
        '-map', f'[{aout_label}]',
        '-c:v', 'libx264',
        '-preset', 'veryfast',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
    ])
    if use_shortest:
        ffmpeg_args.extend(['-shortest'])
    ffmpeg_args.append(output_rel)

    render_path = Path(data['render']['path'])

    if not skip_render:
        print(f"Rendering {len(render_timeline)} segments, expected duration: {expected_duration:.1f}s")
        print(f"FFmpeg filter complex: {len(filter_parts)} filter parts")

        try:
            env = os.environ.copy()
            env.pop("DOCKER_API_VERSION", None)
            subprocess.run(ffmpeg_args, check=True, timeout=1800, env=env)
            ffmpeg_ok = True
            ffmpeg_exit_code = 0
        except subprocess.CalledProcessError as e:
            ffmpeg_ok = False
            ffmpeg_exit_code = e.returncode
            print(f"WARNING: FFmpeg exited with code {e.returncode}")

        # -- Post-render validation --
        video_path = video_dir / "video.mp4"

        post = post_render_validate(video_path, expected_duration, data, project_root,
                                     is_continuous_audio=is_continuous_audio)
        black_warnings = detect_black_frames(video_path, project_root)
        freeze_warnings = detect_freeze_frames(video_path, project_root)
        validation_frames = extract_validation_frames(video_path, validation_dir, project_root)

        validation_result = {
            "ffmpegOk": ffmpeg_ok,
            "ffmpegExitCode": ffmpeg_exit_code,
            "preflightOk": skip_validation or True,
            "postRender": post,
            "blackFrameWarnings": len(black_warnings),
            "blackFrames": black_warnings[:10],
            "freezeFrameWarnings": len(freeze_warnings),
            "freezeFrames": freeze_warnings[:10],
            "validationFrames": validation_frames,
        }

        # -- Subtitle style validation --
        ass_path = video_dir / "subtitle.ass"
        expected_style = "shorts_upper_dynamic"
        if data.get("request", {}).get("subtitles", {}).get("style"):
            expected_style = data["request"]["subtitles"]["style"]
        ass_validation = validate_ass_style(ass_path, expected_style)
        validation_result["subtitleStyleValidation"] = ass_validation

        # -- Audio validation (Fase 5) --
        audio_validation_result = None
        if is_continuous_audio:
            try:
                from shorts_creator.validation.audio import run_audio_validation
                narration_path = video_dir / "scenes" / "narration.mp3"
                scene_timings = audio_config.get("sceneTimings", [])
                cues_by_scene = {}
                for sc in data["script"]["scenes"]:
                    sn = sc["sceneNumber"]
                    cues_by_scene[sn] = sc.get("subtitleTiming", {}).get("cues", [])
                audio_validation_result = run_audio_validation(
                    narration_path, scene_timings, cues_by_scene, project_root
                )
                validation_result["audioValidation"] = audio_validation_result
            except Exception as e:
                validation_result["audioValidation"] = {"error": str(e)}

        # -- Coverage validation (Fase 6) --
        coverage_result = None
        try:
            if is_continuous_audio:
                from shorts_creator.validation.coverage import run_coverage_validation
                scene_timings = audio_config.get("sceneTimings", [])
                audio_dur = audio_config.get("durationSec", 0)
                cues_by_scene = {}
                for sc in data["script"]["scenes"]:
                    sn = sc["sceneNumber"]
                    cues_by_scene[sn] = sc.get("subtitleTiming", {}).get("cues", [])
                narration_units = audio_config.get("narrationUnits", [])
                coverage_result = run_coverage_validation(
                    scene_timings, audio_dur, cues_by_scene, narration_units
                )
            else:
                from shorts_creator.validation.subtitle_context import build_validation_context
                ctx = build_validation_context(data, video_dir=video_dir)
                coverage_result = {
                    "status": ctx["status"],
                    "mode": ctx["mode"],
                    "totalCues": ctx["totalCues"],
                    "errors": ctx.get("errors", []),
                    "warnings": ctx.get("warnings", []),
                }
            validation_result["coverageValidation"] = coverage_result
        except Exception as e:
            validation_result["coverageValidation"] = {"error": str(e)}

        # ── Structured validation gates ───────────────────────────────
        ass_style_ok = ass_validation.get("ok", True)
        technical_pass = (
            ffmpeg_ok
            and post["durationOk"]
            and post["maxDurationOk"]
            and len(black_warnings) == 0
            and len(freeze_warnings) == 0
            and ass_style_ok
        )

        coverage_status = (coverage_result or {}).get("status", "N/A")
        asset_result = data.get("assetValidation", {})
        asset_status = asset_result.get("status", "N/A")
        asset_was_skipped = skip_asset_validation
        has_asset_issues = (asset_status == "REVIEW_REQUIRED") or asset_was_skipped

        # ── Pacing validation ────────────────────────────────────────
        pacing_result = None
        if not is_continuous_audio:
            try:
                from shorts_creator.validation.pacing import validate_audio_pacing
                scene_windows = [
                    {"sceneNumber": sn, "startSec": sw["startSec"], "endSec": sw["endSec"]}
                    for sn, sw in scene_windows.items()
                ]
                word_count = sum(
                    len(s.get("voiceover", "").split())
                    for s in data["script"]["scenes"]
                )
                pacing_result = validate_audio_pacing(
                    video_path=video_path,
                    scene_windows=scene_windows,
                    total_duration_sec=expected_duration,
                    project_root=project_root,
                    word_count=word_count,
                )
                validation_result["pacingValidation"] = pacing_result
            except Exception as e:
                validation_result["pacingValidation"] = {"error": str(e)}

        pacing_status = (pacing_result or {}).get("status", "N/A") if pacing_result else "NOT_APPLICABLE"

        request_duration = data.get("request", {}).get("duration", {})
        required_duration_fields = ("targetSec", "minSec", "maxSec")
        if isinstance(request_duration, dict) and all(k in request_duration for k in required_duration_fields):
            try:
                requested_compliance = evaluate_requested_duration_compliance(
                    actual_video_duration_sec=post["actualVideoDurationSec"],
                    target_sec=request_duration["targetSec"],
                    min_sec=request_duration["minSec"],
                    max_sec=request_duration["maxSec"],
                )
            except (TypeError, ValueError):
                requested_compliance = {"status": "NOT_APPLICABLE"}
        else:
            requested_compliance = {"status": "NOT_APPLICABLE"}
        validation_result["requestedDurationCompliance"] = requested_compliance

        gates = {
            "technicalValidation": "PASS" if technical_pass else "FAIL",
            "renderDurationIntegrity": "PASS" if post["durationOk"] else "FAIL",
            "requestedDurationCompliance": requested_compliance["status"],
            "subtitleCoverageValidation": coverage_status,
            "assetValidation": asset_status if asset_status != "N/A" else "NOT_APPLICABLE",
            "pacingValidation": pacing_status,
        }
        gate_failures = [k for k, v in gates.items() if v == "FAIL"]
        gate_warnings = [k for k, v in gates.items() if v in ("REVIEW_REQUIRED", "WARNING", "PASS_WITH_WARNINGS")]

        qualityGate = "FAIL" if gate_failures else ("WARNING" if gate_warnings else "PASS")
        gates["qualityGate"] = qualityGate

        data["validation"] = validation_result
        data["validation"]["gates"] = gates

        if requested_compliance["status"] == "FAIL":
            data.setdefault("reviewReasons", [])
            reason = "REQUESTED_DURATION_OUT_OF_RANGE"
            if reason not in data["reviewReasons"]:
                data["reviewReasons"].append(reason)
            data["status"] = "RENDERED_WITH_WARNINGS"
        elif not technical_pass:
            data["status"] = "RENDERED_WITH_WARNINGS"
        elif has_asset_issues:
            data["status"] = "RENDERED_WITH_ASSET_WARNINGS"
        else:
            data["status"] = "RENDERED"

        all_pass = (data["status"] == "RENDERED")
    else:
        print("Render skipped (--skip-render). Generating manifest only.")
        ffmpeg_ok = True
        ffmpeg_exit_code = 0
        post = {"durationOk": True, "maxDurationOk": True, "actualVideoDurationSec": 0, "durationDeltaSec": 0}
        black_warnings = []
        freeze_warnings = []
        validation_result = {
            "ffmpegOk": True,
            "ffmpegExitCode": 0,
            "preflightOk": skip_validation or True,
            "postRender": post,
            "blackFrameWarnings": 0,
            "blackFrames": [],
            "freezeFrameWarnings": 0,
            "freezeFrames": [],
            "validationFrames": [],
        }
        audio_validation_result = None
        coverage_result = None
        all_pass = True
        if is_continuous_audio:
            expected_duration = audio_config.get("durationSec", 0)
        data["validation"] = validation_result
        data["validation"]["gates"] = {
            "technicalValidation": "NOT_APPLICABLE",
            "renderDurationIntegrity": "NOT_APPLICABLE",
            "requestedDurationCompliance": "NOT_APPLICABLE",
            "subtitleCoverageValidation": "NOT_APPLICABLE",
            "assetValidation": "NOT_APPLICABLE",
            "qualityGate": "NOT_APPLICABLE",
        }
        data["status"] = "RENDER_SKIPPED"

        # In non-continuous mode, still run subtitle validation even with --skip-render
        if not is_continuous_audio:
            try:
                from shorts_creator.validation.subtitle_context import build_validation_context
                ctx = build_validation_context(data, video_dir=video_dir)
                cov_status = ctx["status"]
                gates = data["validation"]["gates"]
                gates["subtitleCoverageValidation"] = cov_status
                sub_gates = {k: v for k, v in gates.items() if k != "qualityGate"}
                gate_failures = [k for k, v in sub_gates.items() if v == "FAIL"]
                gate_warnings = [k for k, v in sub_gates.items() if v in ("REVIEW_REQUIRED", "WARNING")]
                gates["qualityGate"] = (
                    "FAIL" if gate_failures
                    else ("WARNING" if gate_warnings else "PASS")
                )
            except Exception:
                pass

    # ── Build resolvedConfig from request + actual values ─────────────
    req = data.get("request", {})
    subtitle_style = req.get("subtitles", {}).get("style", "shorts_upper_dynamic")
    voice_provider = audio_config.get("provider", "edge_tts")
    voice_id = audio_config.get("voice", "es-ES-AlvaroNeural")
    resolved = {
        "durationProfile": req.get("durationProfile", "short_25_30"),
        "duration": {
            "targetSec": req.get("duration", {}).get("targetSec", 28),
            "minSec": req.get("duration", {}).get("minSec", 25),
            "maxSec": req.get("duration", {}).get("maxSec", 30),
            "strictness": req.get("duration", {}).get("strictness", "balanced"),
        },
        "voice": {
            "provider": voice_provider,
            "voiceId": voice_id,
        },
        "subtitles": {
            "enabled": req.get("subtitles", {}).get("enabled", True),
            "timingProvider": audio_config.get("timingProvider", "auto"),
            "style": subtitle_style,
            "position": req.get("subtitles", {}).get("position", "upper_middle"),
            "fontSize": req.get("subtitles", {}).get("fontSize", 64),
            "outline": req.get("subtitles", {}).get("outline", 4),
            "shadow": req.get("subtitles", {}).get("shadow", 2),
            "backgroundBox": req.get("subtitles", {}).get("backgroundBox", False),
            "globalOffsetMs": audio_config.get("globalOffsetMs", 0),
        },
        "visuals": {
            "mode": req.get("visuals", {}).get("mode", "images"),
            "allowGeneratedImages": req.get("visuals", {}).get("allowGeneratedImages", False),
        },
        "music": {
            "enabled": music_enabled if music_enabled else False,
            "source": music_path_str if music_enabled else "none",
            "path": music_path_str if music_enabled else None,
            "volumeDb": music_volume_db if music_enabled else -24,
            "duckUnderVoice": music_duck if music_enabled else True,
            "fadeInMs": music_fade_in if music_enabled else 300,
            "fadeOutMs": music_fade_out if music_enabled else 500,
        },
        "editorialOverlays": {
            "enabled": req.get("editorialOverlays", {}).get("enabled", False),
        },
        "outputProfile": {
            "resolution": "1080x1920",
            "format": "shorts-9x16",
            "fps": FPS,
        },
    }
    audio_pacing = data.get("audioPacing", {})
    if isinstance(audio_pacing, dict) and audio_pacing:
        resolved["audioPacing"] = dict(audio_pacing)
    data["resolvedConfig"] = resolved

    data["render"]["path"] = str(render_path)
    data["review"] = {"status": "PENDING"}
    data["updatedAt"] = datetime.now(timezone.utc).isoformat()
    metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    # -- Generate job manifest --
    try:
        def _get_subtitle_provider():
            for sc in data["script"]["scenes"]:
                src = sc.get("subtitleTiming", {}).get("timingSource", "")
                if src:
                    return src
            for sc in data["script"]["scenes"]:
                cues = sc.get("subtitleTiming", {}).get("cues", [])
                if cues:
                    return "estimated"
            return "unknown"

        def _get_scene_audio_info(scene_num: int) -> dict:
            sdir = video_dir / "scenes"
            if is_continuous_audio:
                return {
                    "audioPath": str((sdir / "narration.mp3").relative_to(project_root)),
                    "audioDurationSec": audio_config.get("durationSec", 0),
                }
            audio_path = sdir / f"scene-{scene_num:02}.mp3"
            dur = resolve_manifest_scene_audio_duration(audio_config, scene_num)
            if dur is None:
                dur = None
            return {
                "audioPath": str(audio_path.relative_to(project_root)) if audio_path.exists() else "",
                "audioDurationSec": dur,
            }

        def _resolve_relative(p: str) -> str:
            raw = Path(p)
            if raw.is_absolute():
                try:
                    return str(raw.relative_to(project_root))
                except ValueError:
                    return p
            return p

        def _get_scene_visual_info(scene_num: int) -> dict:
            asset_entry = None
            for a in data.get("assets", []):
                if a.get("sceneNumber") == scene_num:
                    asset_entry = a
                    break

            raw_path = ""
            if asset_entry and asset_entry.get("segments"):
                raw_path = asset_entry["segments"][0].get("path", "")
            elif asset_entry and asset_entry.get("path"):
                raw_path = asset_entry["path"]

            vpath = ""
            if raw_path:
                raw = Path(raw_path)
                if raw.is_absolute():
                    local_file = raw
                else:
                    local_file = video_dir / raw_path
                if local_file.exists():
                    vpath = str(local_file.relative_to(project_root))
            if not vpath:
                local_default = video_dir / "scenes" / f"scene-{scene_num:02}.jpg"
                if local_default.exists():
                    vpath = str(local_default.relative_to(project_root))
            if not vpath and raw_path:
                rel = _resolve_relative(raw_path)
                candidate = project_root / rel
                if candidate.exists():
                    vpath = rel
            if not vpath:
                vpath = f"{video_dir.relative_to(project_root)}/scenes/scene-{scene_num:02}.jpg"
            return {"visualType": "image", "visualPath": vpath}

        manifest = {
            "jobId": data["jobId"],
            "createdAt": data.get("updatedAt", data.get("createdAt", "")),
            "scriptPath": str(metadata_path.relative_to(project_root)),
            "renderProfile": "shorts_upper_dynamic",
            "resolution": "1080x1920",
            "tts": {
                "provider": audio_config.get("provider", "edge_tts"),
                "voice": audio_config.get("voice", ""),
            },
            "subtitles": {
                "provider": _get_subtitle_provider(),
                "path": str(Path(data.get("subtitles", {}).get("path", "subtitle.ass")).relative_to(project_root))
                if data.get("subtitles", {}).get("path") else f"{video_dir.relative_to(project_root)}/subtitle.ass",
            },
            "scenes": [],
            "outputVideoPath": str(render_path.relative_to(project_root)),
        }

        for sc in data["script"]["scenes"]:
            sn = sc["sceneNumber"]
            audio_info = _get_scene_audio_info(sn)
            visual_info = _get_scene_visual_info(sn)
            manifest["scenes"].append({
                "sceneNumber": sn,
                "visualType": visual_info["visualType"],
                "visualPath": visual_info["visualPath"],
                "audioPath": audio_info["audioPath"],
                "audioDurationSec": audio_info["audioDurationSec"],
            })

        manifest["request"] = data.get("request", {})
        manifest["resolvedConfig"] = data.get("resolvedConfig", data.get("request", {}))
        manifest["validation"] = {
            "preflightOk": skip_validation or True,
            "durationOk": post["durationOk"],
            "blackFrameWarnings": len(black_warnings),
            "freezeFrameWarnings": len(freeze_warnings),
            "coverageStatus": (coverage_result or {}).get("status", "N/A"),
            "requestedDurationCompliance": validation_result.get("requestedDurationCompliance", {"status": "NOT_APPLICABLE"}),
            "gates": validation_result.get("gates", {}),
        }
        import json as _json
        manifest_path = video_dir / "job-manifest.json"
        manifest_path.write_text(_json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        print(f"Manifest: {manifest_path}")
    except Exception as e:
        print(f"WARNING: could not generate manifest: {e}")

    av = (audio_validation_result or {}).get("metrics", {})
    cv_status = (coverage_result or {}).get("status", "N/A")
    print(json.dumps({
        "jobId": data["jobId"],
        "render": str(render_path),
        "expectedDurationSec": expected_duration,
        "actualVideoDurationSec": post["actualVideoDurationSec"],
        "durationDeltaSec": post["durationDeltaSec"],
        "ffmpegExitCode": ffmpeg_exit_code,
        "blackFrameWarnings": len(black_warnings),
        "freezeFrameWarnings": len(freeze_warnings),
        "audioValidationTechnical": (audio_validation_result or {}).get("technicalStatus"),
        "audioValidationQuality": (audio_validation_result or {}).get("qualityStatus"),
        "totalSilenceSec": av.get("totalSilenceSec"),
        "maxChapterBreakSec": av.get("maxChapterBreakSec"),
        "chapterBreakCount": av.get("chapterBreakCount"),
        "unexpectedSilenceCount": av.get("unexpectedSilenceCount"),
        "coverageStatus": cv_status,
        "status": data["status"],
    }))
    return 0 if all_pass else 1
