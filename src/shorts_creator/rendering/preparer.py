#!/usr/bin/env python3

import json
import math
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_SCENE_TAIL_PAUSE_SEC = 0.35


def resolve_scene_window_duration(
    actual_audio_duration_sec: float,
    tail_pause_sec: float = DEFAULT_SCENE_TAIL_PAUSE_SEC,
) -> float:
    """Return the canonical visual window for a non-continuous scene.

    sceneWindowSec = actualAudioDurationSec + tailPauseSec

    actualAudioDurationSec must be positive, finite, and numeric (not bool).
    tailPauseSec must be non-negative, finite, and numeric (not bool).
    Returns the sum rounded to 3 decimal places.
    """
    for val, label in [(actual_audio_duration_sec, "actualAudioDurationSec"),
                         (tail_pause_sec, "tailPauseSec")]:
        if not isinstance(val, (int, float)):
            raise TypeError(f"{label} must be int or float, got {type(val).__name__}")
        if isinstance(val, bool):
            raise TypeError(f"{label} must not be bool")
        if not math.isfinite(val):
            raise ValueError(f"{label} must be finite, got {val}")
        if val < 0:
            raise ValueError(f"{label} must be non-negative, got {val}")

    if actual_audio_duration_sec <= 0:
        raise ValueError(f"actualAudioDurationSec must be positive, got {actual_audio_duration_sec}")

    if tail_pause_sec > 1.0:
        raise ValueError(f"tailPauseSec must not exceed 1.0s, got {tail_pause_sec}")

    window = actual_audio_duration_sec + tail_pause_sec
    return round(window, 3)


def _get_tail_pause_sec(data: dict) -> float:
    """Resolve the tail pause duration from metadata or default."""
    pacing = data.get("audioPacing", {})
    if isinstance(pacing, dict):
        val = pacing.get("sceneTailPauseSec")
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            if math.isfinite(val) and 0 <= val <= 1.0:
                return float(val)
    return DEFAULT_SCENE_TAIL_PAUSE_SEC


def fmt_srt_time(seconds: float) -> str:
    ms_total = int(round(seconds * 1000))
    hours = ms_total // 3600000
    ms_total %= 3600000
    minutes = ms_total // 60000
    ms_total %= 60000
    secs = ms_total // 1000
    millis = ms_total % 1000
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def fmt_ass_time(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hrs = total_ms // 3600000
    total_ms %= 3600000
    mins = total_ms // 60000
    total_ms %= 60000
    secs = total_ms // 1000
    centisecs = (total_ms % 1000) // 10
    return f"{hrs}:{mins:02}:{secs:02}.{centisecs:02}"


def ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def wrap_line(text: str, max_chars: int = 20) -> str:
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 > max_chars and current:
            lines.append(current.strip())
            current = word
        else:
            current += " " + word if current else word
    if current:
        lines.append(current.strip())
    return "\\N".join(lines) if lines else text


ASS_STYLES = {
    "documentary_safe": {
        "name": "documentary_safe",
        "fontname": "Arial Bold",
        "fontsize": 55,
        "primary": "&H00FFFFFF",
        "secondary": "&H000000FF",
        "outline_colour": "&H00000000",
        "back_colour": "&H80000000",
        "bold": -1,
        "border_style": 3,
        "outline": 0,
        "shadow": 0,
        "alignment": 2,
        "margin_l": 60,
        "margin_r": 60,
        "margin_v": 50,
    },
    "shorts_dynamic": {
        "name": "shorts_dynamic",
        "fontname": "Arial Bold",
        "fontsize": 65,
        "primary": "&H00FFFFFF",
        "secondary": "&H000000FF",
        "outline_colour": "&H00000000",
        "back_colour": "&H40000000",
        "bold": -1,
        "border_style": 1,
        "outline": 2,
        "shadow": 2,
        "alignment": 2,
        "margin_l": 60,
        "margin_r": 60,
        "margin_v": 40,
    },
    "shorts_upper_dynamic": {
        "name": "shorts_upper_dynamic",
        "fontname": "DejaVu Sans Bold",
        "fontsize": 64,
        "primary": "&H00FFFFFF",
        "secondary": "&H000000FF",
        "outline_colour": "&H00000000",
        "back_colour": "&H00000000",
        "bold": -1,
        "border_style": 1,
        "outline": 4,
        "shadow": 2,
        "alignment": 8,
        "margin_l": 140,
        "margin_r": 140,
        "margin_v": 430,
    },
}


def _ass_style_line(s: dict) -> str:
    return (
        f"Style: {s['name']},{s['fontname']},{s['fontsize']},"
        f"{s['primary']},{s['secondary']},{s['outline_colour']},{s['back_colour']},"
        f"{s['bold']},0,0,0,100,100,0,0,"
        f"{s['border_style']},{s['outline']},{s['shadow']},{s['alignment']},"
        f"{s['margin_l']},{s['margin_r']},{s['margin_v']},1"
    )


def _ass_header(style_name: str) -> list[str]:
    style = ASS_STYLES.get(style_name, ASS_STYLES["documentary_safe"])
    return [
        "[Script Info]",
        "; ASS subtitles generated by shorts-creator",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "; Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        _ass_style_line(style),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]


def generate_ass_fallback(scenes: list, subtitles_path: Path,
                          style_name: str = "documentary_safe"):
    lines = _ass_header(style_name)
    current = 0.0
    for scene in scenes:
        duration = float(scene['targetDurationSec'])
        start = current
        end = current + duration
        text = (scene.get('subtitle') or scene.get('voiceover') or '').strip()
        wrapped = wrap_line(ass_escape(text))
        lines.append(
            f"Dialogue: 0,{fmt_ass_time(start)},{fmt_ass_time(end)},{style_name},,0,0,0,,{wrapped}"
        )
        current = end
    subtitles_path.write_text('\n'.join(lines) + '\n')


def generate_ass_from_cues(scenes: list, subtitles_path: Path,
                           style_name: str = "documentary_safe",
                           scene_offsets: dict[int, float] | None = None,
                           scene_windows: dict[int, tuple[float, float]] | None = None):

    lines = _ass_header(style_name)
    seen = set()

    if scene_offsets is not None and scene_windows is not None:
        global_cues = resolve_and_validate_global_cues(
            scenes, scene_offsets, scene_windows
        )
        for gc in global_cues:
            text = gc.get("text", "").strip()
            if not text:
                continue
            key = (round(gc["startSec"], 2), round(gc["endSec"], 2), text)
            if key in seen:
                continue
            seen.add(key)
            wrapped = wrap_line(ass_escape(text))
            lines.append(
                f"Dialogue: 0,{fmt_ass_time(gc['startSec'])},{fmt_ass_time(gc['endSec'])},"
                f"{style_name},,0,0,0,,{wrapped}"
            )
    elif scene_offsets is not None:
        for scene in scenes:
            sn = int(scene.get("sceneNumber", 0))
            cues = scene.get("subtitleTiming", {}).get("cues", [])
            if cues:
                offset = scene_offsets.get(sn)
                if offset is None:
                    raise ValueError(
                        f"scene_offsets missing for scene {sn} that has cues"
                    )
                for cue in cues:
                    start = cue["startSec"] + offset
                    end = cue["endSec"] + offset
                    text = cue.get("text", "").strip()
                    if not text:
                        continue
                    key = (round(start, 2), round(end, 2), text)
                    if key in seen:
                        continue
                    seen.add(key)
                    wrapped = wrap_line(ass_escape(text))
                    lines.append(
                        f"Dialogue: 0,{fmt_ass_time(start)},{fmt_ass_time(end)},"
                        f"{style_name},,0,0,0,,{wrapped}"
                    )
    else:
        for scene in scenes:
            cues = scene.get("subtitleTiming", {}).get("cues", [])
            if cues:
                for cue in cues:
                    start = cue["startSec"]
                    end = cue["endSec"]
                    text = cue.get("text", "").strip()
                    if not text:
                        continue
                    key = (round(start, 2), round(end, 2), text)
                    if key in seen:
                        continue
                    seen.add(key)
                    wrapped = wrap_line(ass_escape(text))
                    lines.append(
                        f"Dialogue: 0,{fmt_ass_time(start)},{fmt_ass_time(end)},"
                        f"{style_name},,0,0,0,,{wrapped}"
                    )

    subtitles_path.write_text('\n'.join(lines) + '\n')


def resolve_and_validate_global_cues(
    scenes: list,
    scene_offsets: dict[int, float] | None = None,
    scene_windows: dict[int, tuple[float, float]] | None = None,
    tolerance: float = 0.05,
) -> list[dict] | None:
    """Validate cues globally after applying scene offsets.

    For non-continuous audio:
    - Every cue must have a valid offset
    - startSec and endSec must be numeric, finite, startSec >= 0, endSec > startSec
    - Cue must stay within its scene window
    - Global order must be monotonic (input is canonical; reordering is not allowed)
    - No cross-scene overlaps
    Returns validated global cues or raises ValueError.

    When scene_offsets is None (continuous): returns None (no validation).
    """
    if scene_offsets is None:
        return None

    global_cues: list[dict] = []
    prev_end: float | None = None

    for scene in scenes:
        sn = int(scene.get("sceneNumber", 0))
        cues = scene.get("subtitleTiming", {}).get("cues", [])
        if not cues:
            continue

        offset = scene_offsets.get(sn)
        if offset is None:
            raise ValueError(f"scene_offsets missing for scene {sn} that has cues")

        sw = None if scene_windows is None else scene_windows.get(sn)

        for cue in cues:
            local_start = cue.get("startSec")
            local_end = cue.get("endSec")

            for val, label in [(local_start, "startSec"), (local_end, "endSec")]:
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    raise ValueError(
                        f"scene {sn} cue {label} must be numeric, got {type(val).__name__}"
                    )
                if not math.isfinite(val):
                    raise ValueError(
                        f"scene {sn} cue {label} must be finite, got {val}"
                    )

            start = local_start + offset
            end = local_end + offset

            if start < 0:
                raise ValueError(
                    f"scene {sn} cue startSec={start:.3f} < 0 after offset"
                )
            if end <= start:
                raise ValueError(
                    f"scene {sn} cue endSec={end:.3f} <= startSec={start:.3f}"
                )

            if sw is not None:
                sw_start, sw_end = sw
                if start < sw_start - tolerance:
                    raise ValueError(
                        f"scene {sn} cue start={start:.3f} < scene window start={sw_start:.3f}"
                    )
                if end > sw_end + tolerance:
                    raise ValueError(
                        f"scene {sn} cue end={end:.3f} > scene window end={sw_end:.3f}"
                    )

            # Monotonic check: input is already in canonical order
            if prev_end is not None and start < prev_end - tolerance:
                raise ValueError(
                    f"cross-scene cue overlap or non-monotonic order: "
                    f"previous cue ended at {prev_end:.3f}s, "
                    f"scene {sn} cue starts at {start:.3f}s"
                )
            prev_end = end

            global_cues.append({
                "startSec": round(start, 3),
                "endSec": round(end, 3),
                "text": cue.get("text", ""),
                "sceneNumber": sn,
            })

    return global_cues


def build_timeline(scenes: list, assets: list, video_dir: Path, scenes_dir: Path) -> list[dict]:
    timeline = []
    current_time = 0.0
    asset_by_scene = {a['sceneNumber']: a for a in assets} if assets else {}

    for scene in scenes:
        sn = int(scene['sceneNumber'])
        duration = float(scene['targetDurationSec'])
        audio_path = str(scenes_dir / f"scene-{sn:02}.mp3")
        asset_entry = asset_by_scene.get(sn, {})
        segments = asset_entry.get('segments')

        if segments:
            for seg in segments:
                start = current_time
                dur = seg.get('durationSec', duration / len(segments))
                end = start + dur
                timeline.append({
                    "index": len(timeline) + 1,
                    "sceneNumber": sn,
                    "segmentIndex": seg.get('segmentIndex', 1),
                    "imagePath": seg.get('path', ''),
                    "audioPath": audio_path,
                    "startSec": round(start, 2),
                    "durationSec": round(dur, 1),
                    "transition": seg.get('transition', 'cut'),
                    "assetType": seg.get('assetType', 'broll'),
                    "width": seg.get('width'),
                    "height": seg.get('height'),
                    "duplicateRisk": seg.get('duplicateRisk', 'none'),
                    "focalRegion": seg.get('focalRegion', 'center'),
                    "cropMode": seg.get('cropMode', 'full_map'),
                    "overlayText": seg.get('overlayText', ''),
                    "mapReadabilityScore": seg.get('mapReadabilityScore'),
                    "visualAuthenticityRisk": seg.get('visualAuthenticityRisk'),
                    "editorialReason": seg.get('editorialReason', ''),
                })
                current_time = end
        else:
            start = current_time
            end = start + duration
            timeline.append({
                "index": len(timeline) + 1,
                "sceneNumber": sn,
                "segmentIndex": 1,
                "imagePath": str(scenes_dir / f"scene-{sn:02}.jpg"),
                "audioPath": audio_path,
                "startSec": round(start, 2),
                "durationSec": duration,
                "transition": "cut",
                "assetType": asset_entry.get('assetType', 'broll'),
            })
            current_time = end

    return timeline


def _get_visual_seq_map(scene):
    vs_map = {}
    for vs in scene.get("visualPlan", {}).get("visualSequence", []):
        vs_map[vs.get("segmentIndex", 1)] = vs
    return vs_map


def _merge_segment_fields(seg, vs_map):
    seg_idx = seg.get("segmentIndex", 1)
    vs = vs_map.get(seg_idx, {})
    merged = dict(seg)
    if "motionType" not in merged or not merged.get("motionType"):
        merged["motionType"] = vs.get("motionType", "static")
    if "overlayText" not in merged or not merged.get("overlayText"):
        merged["overlayText"] = vs.get("overlayText", "")
    if "overlayEnabled" not in merged:
        merged["overlayEnabled"] = vs.get("overlayEnabled", False)
    if "transition" not in merged or not merged.get("transition"):
        merged["transition"] = vs.get("transition", "cut")
    return merged


def build_render_timeline(scenes: list, assets: list, scenes_dir: Path,
                          audio_path: str | None = None,
                          scene_timings: list[dict] | None = None,
                          scene_audio_durations: dict[int, float] | None = None,
                          tail_pause_sec: float = DEFAULT_SCENE_TAIL_PAUSE_SEC) -> list[dict]:
    render_timeline = []
    asset_by_scene = {a['sceneNumber']: a for a in assets} if assets else {}
    is_continuous = audio_path is not None and scene_timings is not None
    timing_by_scene = {st["sceneNumber"]: st for st in (scene_timings or [])}
    accumulated_time = 0.0

    for scene in scenes:
        sn = int(scene['sceneNumber'])
        cues = scene.get("subtitleTiming", {}).get("cues", [])

        if is_continuous:
            seg_audio_path = audio_path
            st_entry = timing_by_scene.get(sn, {})
            scene_offset = st_entry.get("startSec", 0.0)
            scene_duration = float(scene.get("targetDurationSec", 5))
            if st_entry:
                st_end = st_entry.get("endSec", 0.0)
                if st_end > scene_offset:
                    scene_duration = st_end - scene_offset
        else:
            seg_audio_path = str(scenes_dir / f"scene-{sn:02}.mp3")
            scene_offset = accumulated_time
            st_entry = {}
            actual_audio_dur = (scene_audio_durations or {}).get(sn)
            if actual_audio_dur is not None and actual_audio_dur > 0:
                scene_duration = resolve_scene_window_duration(
                    actual_audio_dur,
                    tail_pause_sec=tail_pause_sec,
                )
            else:
                raise ValueError(
                    f"scene {sn}: actual audio duration is missing or invalid "
                    f"(got {actual_audio_dur!r}); prepare_job requires measured durations"
                )
        vs_map = _get_visual_seq_map(scene)

        beats = scene.get("narrativeBeats", [])
        asset_entry = asset_by_scene.get(sn, {})
        segments = asset_entry.get("segments", [])

        segments = [_merge_segment_fields(s, vs_map) for s in segments]

        if beats and cues:
            all_cue_indices_valid = all(
                b.get("startCueIndex", 0) < len(cues) and b.get("endCueIndex", 0) < len(cues)
                for b in beats
            )
            for beat in beats:
                bi = beat["beatIndex"]
                start_cue_idx = beat.get("startCueIndex", 0)
                end_cue_idx = beat.get("endCueIndex", 0)

                if all_cue_indices_valid and start_cue_idx < len(cues) and end_cue_idx < len(cues):
                    start_sec = scene_offset + cues[start_cue_idx]["startSec"]
                    end_sec = scene_offset + cues[end_cue_idx]["endSec"]
                else:
                    beat_share = 1.0 / len(beats)
                    beat_start = (bi - 1) * scene_duration * beat_share
                    beat_end = bi * scene_duration * beat_share
                    start_sec = scene_offset + beat_start
                    end_sec = scene_offset + beat_end

                if is_continuous and st_entry:
                    scene_end = st_entry.get("endSec", scene_offset + scene_duration)
                    if bi == 1:
                        start_sec = min(start_sec, scene_offset)
                    if bi == len(beats):
                        end_sec = max(end_sec, scene_end)

                seg_idx = (bi - 1) % max(len(segments), 1)
                seg = segments[seg_idx] if segments else {}
                seg_sn = seg.get("segmentIndex", 1)

                transition = seg.get("transition", "cut")
                is_last_beat = (bi == len(beats))
                transition_in = "cut"
                transition_out = "fade" if is_last_beat else transition

                motion_type = seg.get("motionType", "static")
                overlay_text = seg.get("overlayText", "")

                asset_path = (seg.get("path") or "") if segments else str(scenes_dir / f"scene-{sn:02}.jpg")

                render_timeline.append({
                    "sceneNumber": sn,
                    "beatIndex": bi,
                    "assetPath": asset_path,
                    "startSec": round(start_sec, 3),
                    "endSec": round(end_sec, 3),
                    "durationSec": round(end_sec - start_sec, 3),
                    "transitionIn": transition_in,
                    "transitionOut": transition_out,
                    "motionType": motion_type,
                    "overlayText": overlay_text,
                    "overlayEnabled": seg.get("overlayEnabled", False),
                    "subtitleCueIndexes": list(range(start_cue_idx, end_cue_idx + 1)),
                    "audioPath": seg_audio_path,
                    "segmentIndex": seg_sn,
                    "assetType": seg.get("assetType", "broll"),
                    "width": seg.get("width"),
                    "height": seg.get("height"),
                    "focalRegion": seg.get("focalRegion", "center"),
                    "cropMode": seg.get("cropMode", "full_map"),
                })
        elif segments:
            raw_fractions = []
            for seg in segments:
                df = seg.get("durationFraction", 1.0 / max(len(segments), 1))
                if not isinstance(df, (int, float)) or isinstance(df, bool):
                    raise ValueError(
                        f"durationFraction must be numeric, got {type(df).__name__} "
                        f"for scene {sn} segmentIndex {seg.get('segmentIndex', '?')}"
                    )
                if not math.isfinite(df) or df <= 0:
                    raise ValueError(
                        f"durationFraction must be finite and positive, got {df} "
                        f"for scene {sn} segmentIndex {seg.get('segmentIndex', '?')}"
                    )
                raw_fractions.append(df)

            total_fraction = sum(raw_fractions)
            if total_fraction <= 0:
                raise ValueError(
                    f"total durationFraction must be positive for scene {sn}"
                )
            normalized = [f / total_fraction for f in raw_fractions]

            cumulative = scene_offset
            for i, seg in enumerate(segments):
                seg_idx = seg.get("segmentIndex", i + 1)
                is_last = (i == len(segments) - 1)
                start_sec = cumulative
                if is_last:
                    end_sec = scene_offset + scene_duration
                else:
                    end_sec = cumulative + scene_duration * normalized[i]
                seg_duration = end_sec - start_sec

                motion_type = seg.get("motionType", "static")
                overlay_text = seg.get("overlayText", "")
                transition = seg.get("transition", "cut")

                render_timeline.append({
                    "sceneNumber": sn,
                    "beatIndex": seg_idx,
                    "assetPath": seg.get("path") or "",
                    "startSec": round(start_sec, 3),
                    "endSec": round(end_sec, 3),
                    "durationSec": round(seg_duration, 3),
                    "transitionIn": "cut",
                    "transitionOut": "fade" if is_last else transition,
                    "motionType": motion_type,
                    "overlayText": overlay_text,
                    "overlayEnabled": seg.get("overlayEnabled", False),
                    "subtitleCueIndexes": [],
                    "audioPath": seg_audio_path,
                    "segmentIndex": seg_idx,
                    "assetType": seg.get("assetType", "broll"),
                    "width": seg.get("width"),
                    "height": seg.get("height"),
                    "focalRegion": seg.get("focalRegion", "center"),
                    "cropMode": seg.get("cropMode", "full_map"),
                })
                cumulative = end_sec
        else:
            render_timeline.append({
                "sceneNumber": sn,
                "beatIndex": 1,
                "assetPath": str(scenes_dir / f"scene-{sn:02}.jpg"),
                "startSec": scene_offset,
                "endSec": scene_offset + scene_duration,
                "durationSec": scene_duration,
                "transitionIn": "cut",
                "transitionOut": "fade",
                "motionType": "static",
                "overlayText": "",
                "subtitleCueIndexes": [],
                "audioPath": seg_audio_path,
                "segmentIndex": 1,
                "assetType": asset_entry.get("assetType", "broll"),
                "width": None,
                "height": None,
                "focalRegion": "center",
                "cropMode": "full_map",
            })

        accumulated_time += scene_duration

    return render_timeline


def _fill_timeline_gaps(timeline: list[dict], narration_duration_sec: float | None = None) -> list[dict]:
    """Fill gaps between render timeline entries by extending previous visual coverage.

    Ensures: visual start <= 0.05s, gap <= 0.05s between entries, end at narration_duration.
    """
    if not timeline:
        return timeline

    # Sort by startSec
    timeline.sort(key=lambda e: e.get("startSec", 0))

    # Fix start: first entry must begin at <= 0.0
    if timeline[0].get("startSec", 0) > 0.05:
        timeline[0]["startSec"] = 0.0
        timeline[0]["durationSec"] = round(timeline[0]["endSec"] - timeline[0]["startSec"], 3)

    # Fill gaps between entries
    for i in range(len(timeline) - 1):
        current_end = timeline[i].get("endSec", 0)
        next_start = timeline[i + 1].get("startSec", 0)
        gap = next_start - current_end
        if gap > 0.05:
            # Extend current entry's end to cover gap
            timeline[i]["endSec"] = round(next_start, 3)
            timeline[i]["durationSec"] = round(timeline[i]["endSec"] - timeline[i]["startSec"], 3)

    # Fix end: last entry must reach narration duration
    if narration_duration_sec:
        last_end = timeline[-1].get("endSec", 0)
        if narration_duration_sec - last_end > 0.05:
            timeline[-1]["endSec"] = round(narration_duration_sec, 3)
            timeline[-1]["durationSec"] = round(timeline[-1]["endSec"] - timeline[-1]["startSec"], 3)

    return timeline


def _invalidate_derived_artifacts(data: dict, video_dir: Path) -> None:
    """Remove stale prepare-generated artifacts and metadata fields.

    Does NOT delete: source metadata, audio files, downloaded assets, logs.
    """
    # Remove subtitle file if present
    subtitle_path = video_dir / "subtitle.ass"
    try:
        if subtitle_path.exists():
            subtitle_path.unlink()
    except OSError:
        pass

    # Remove stale timeline / renderTimeline metadata
    data.pop("timeline", None)
    data.pop("renderTimeline", None)
    data.pop("subtitles", None)
    data.pop("render", None)
    data.pop("review", None)


def _resolve_asset_path(video_dir: Path, path_val: str) -> Path | None:
    if not path_val or not isinstance(path_val, str) or not path_val.strip():
        return None
    candidate = Path(path_val)
    if not candidate.is_absolute():
        candidate = (video_dir / candidate).resolve()
    else:
        candidate = candidate.resolve()
    try:
        candidate.relative_to(video_dir.resolve())
    except ValueError:
        return None
    return candidate


def _validate_asset_completion(data: dict, video_dir: Path) -> list[dict]:
    """Validate every required visualSequence segment has a resolved asset.

    Returns list of failure dicts.  Empty list means all segments valid.
    """
    failures: list[dict] = []
    scenes = data.get("script", {}).get("scenes", [])
    asset_by_scene: dict[int, dict] = {}
    for a in data.get("assets", []):
        sn = a.get("sceneNumber")
        if sn is not None:
            asset_by_scene[int(sn)] = a

    for scene in scenes:
        sn = scene.get("sceneNumber")
        vs_list = (scene.get("visualPlan") or {}).get("visualSequence") or []
        asset_entry = asset_by_scene.get(sn, {})
        segments = asset_entry.get("segments", [])
        seg_by_idx = {s.get("segmentIndex"): s for s in segments}

        for vs in vs_list:
            si = vs.get("segmentIndex", 1)
            seg = seg_by_idx.get(si)

            failure = {
                "sceneNumber": sn,
                "segmentIndex": si,
                "requestedAssetType": vs.get("assetType"),
                "path": None,
                "validationStatus": None,
                "error": None,
                "failureCode": None,
            }

            if not seg:
                failure["failureCode"] = "SEGMENT_MISSING"
                failure["error"] = "No asset segment entry"
                failures.append(failure)
                continue

            path_val = seg.get("path")
            failure["path"] = path_val
            failure["validationStatus"] = seg.get("segmentValidationStatus")
            failure["error"] = seg.get("error")

            if seg.get("error"):
                failure["failureCode"] = "SEGMENT_ERROR"
                failures.append(failure)
                continue

            if seg.get("segmentValidationStatus") != "PASS":
                failure["failureCode"] = "SEGMENT_VALIDATION_FAILED"
                failures.append(failure)
                continue

            if not path_val or not isinstance(path_val, str) or not path_val.strip():
                failure["failureCode"] = "SEGMENT_PATH_NULL"
                failures.append(failure)
                continue

            resolved = _resolve_asset_path(video_dir, path_val)
            if resolved is None:
                failure["failureCode"] = "SEGMENT_PATH_OUTSIDE_JOB"
                failures.append(failure)
                continue

            if not resolved.is_file():
                failure["failureCode"] = "SEGMENT_FILE_MISSING"
                failures.append(failure)
                continue

    # Also check scene-level selected flag
    for sn, asset_entry in asset_by_scene.items():
        selected = asset_entry.get("selected")
        if selected is not True:
            scene = _find_scene_by_number(scenes, sn)
            if scene:
                vsl = (scene.get("visualPlan") or {}).get("visualSequence") or []
                if vsl:
                    failures.append({
                        "sceneNumber": sn,
                        "segmentIndex": None,
                        "requestedAssetType": None,
                        "path": None,
                        "validationStatus": None,
                        "error": f"Scene not selected (selected={selected!r})",
                        "failureCode": "SCENE_NOT_SELECTED",
                    })

    return failures


def _find_scene_by_number(scenes: list, sn: int) -> dict | None:
    for s in scenes:
        if s.get("sceneNumber") == sn:
            return s
    return None
def prepare_job(*, metadata_path: str | Path, subtitle_style: str | None = None) -> int:
    """Prepare timelines, subtitles, and render metadata for one job."""
    metadata_path = Path(metadata_path).resolve()
    video_dir = metadata_path.parent
    scenes_dir = video_dir / 'scenes'
    data = json.loads(metadata_path.read_text())
    job_id = data['jobId']
    scenes = data['script']['scenes']

    # Determine subtitle style from request config, CLI override, or default
    req_subtitles = data.get("request", {}).get("subtitles", {})
    style_from_request = req_subtitles.get("style", "shorts_upper_dynamic")
    subtitle_style = subtitle_style or style_from_request
    if subtitle_style not in ASS_STYLES:
        print(f"WARNING: unknown style '{subtitle_style}', falling back to shorts_upper_dynamic")
        subtitle_style = "shorts_upper_dynamic"

    scenes_dir.mkdir(parents=True, exist_ok=True)

    # ─── Asset completion validation ─────────────────────────────────────
    asset_failures = _validate_asset_completion(data, video_dir)
    if asset_failures:
        # Invalidate stale derived artifacts
        _invalidate_derived_artifacts(data, video_dir)
        data["status"] = "ASSET_UNRESOLVED"
        data["assetFailures"] = asset_failures
        data["updatedAt"] = datetime.now(timezone.utc).isoformat()
        metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({
            "jobId": job_id,
            "status": "ASSET_UNRESOLVED",
            "failures": len(asset_failures),
            "details": asset_failures[:10],
        }))
        return 1

    audio_config = data.get('audio', {})
    is_continuous = audio_config.get('continuous', False)

    if not is_continuous and audio_config.get("duration_estimated", False):
        data["status"] = "REVIEW_REQUIRED"
        data.setdefault("reviewReasons", []).append(
            "AUDIO_DURATION_MISSING: audio.duration_estimated is true — durations not measured"
        )
        data["updatedAt"] = datetime.now(timezone.utc).isoformat()
        metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({
            "jobId": job_id,
            "status": "REVIEW_REQUIRED",
            "reason": "AUDIO_DURATION_MISSING: audio.duration_estimated is true",
        }))
        return 1

    audio_entries = []
    asset_entries = []
    asset_by_scene = {a['sceneNumber']: a for a in data.get('assets', []) if 'sceneNumber' in a}
    scene_audio_durations: dict[int, float] = {}
    missing_duration_scenes: list[int] = []

    for scene in scenes:
        scene_num = int(scene['sceneNumber'])
        duration = float(scene['targetDurationSec'])

        if is_continuous:
            audio_path = scenes_dir / 'narration.mp3'
            audio_entries.append({'sceneNumber': scene_num, 'path': str(audio_path), 'exists': audio_path.exists()})
        else:
            audio_path = scenes_dir / f"scene-{scene_num:02}.mp3"
            exists = audio_path.exists()
            audio_entries.append({'sceneNumber': scene_num, 'path': str(audio_path), 'exists': exists})
            audio_scenes_meta = audio_config.get('scenes', [])
            dur_val = None
            dur_source = None
            for as_entry in audio_scenes_meta:
                if as_entry.get('sceneNumber') == scene_num:
                    dur_val = as_entry.get('durationSec')
                    dur_source = as_entry.get('durationSource')
                    break
            if dur_val is None or (isinstance(dur_val, bool)):
                missing_duration_scenes.append(scene_num)
            elif not dur_source or not isinstance(dur_source, str) or not dur_source.strip():
                missing_duration_scenes.append(scene_num)
            elif isinstance(dur_val, (int, float)):
                dur_f = float(dur_val)
                if math.isfinite(dur_f) and dur_f > 0:
                    scene_audio_durations[scene_num] = dur_f
                else:
                    missing_duration_scenes.append(scene_num)

            # Try active audio duration for scene window calculation
            active_dur = as_entry.get("activeAudioDurationSec")
            if active_dur is not None:
                if isinstance(active_dur, (int, float)) and not isinstance(active_dur, bool):
                    if math.isfinite(active_dur) and active_dur > 0:
                        if active_dur <= dur_f:
                            scene_audio_durations[scene_num] = float(active_dur)

        asset_entry = asset_by_scene.get(scene_num, {})
        segments = asset_entry.get('segments')
        if segments:
            seg_paths = []
            seg_exists_list = []
            for seg in segments:
                p = seg.get("path")
                if p and isinstance(p, str) and p.strip():
                    resolved = _resolve_asset_path(video_dir, p)
                    seg_paths.append(p)
                    seg_exists_list.append(resolved is not None and resolved.is_file())
                else:
                    seg_paths.append(None)
                    seg_exists_list.append(False)
            all_exist = all(seg_exists_list)
            asset_entries.append({
                'sceneNumber': scene_num,
                'path': seg_paths[0] if seg_paths else None,
                'exists': all_exist,
                'segments': segments,
            })
        else:
            asset_path = scenes_dir / f"scene-{scene_num:02}.jpg"
            asset_entries.append({'sceneNumber': scene_num, 'path': str(asset_path), 'exists': asset_path.exists()})

    all_audio = all(item['exists'] for item in audio_entries)
    all_assets = all(item['exists'] for item in asset_entries)

    if not is_continuous and missing_duration_scenes:
        data["status"] = "REVIEW_REQUIRED"
        data.setdefault("reviewReasons", []).append(
            f"AUDIO_DURATION_MISSING: scenes {missing_duration_scenes} lack valid durationSec"
        )
        data["updatedAt"] = datetime.now(timezone.utc).isoformat()
        metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({
            "jobId": job_id,
            "status": "REVIEW_REQUIRED",
            "reason": f"AUDIO_DURATION_MISSING: scenes {missing_duration_scenes} lack valid durationSec",
        }))
        return 1

    subtitle_format = data.get('subtitles', {}).get('format', 'ass')
    subtitle_path = video_dir / f"subtitle.{subtitle_format}"

    # ── Preserve audio metadata, only update path/exists ──────────────
    if not is_continuous:
        preserved_audio = dict(audio_config)
        preserved_scenes = preserved_audio.get('scenes', [])
        existing_scene_index = {as_entry.get('sceneNumber'): i for i, as_entry in enumerate(preserved_scenes)}
        for new_entry in audio_entries:
            sn = new_entry['sceneNumber']
            if sn in existing_scene_index:
                idx = existing_scene_index[sn]
                preserved_scenes[idx]['path'] = new_entry['path']
                preserved_scenes[idx]['exists'] = new_entry['exists']
            else:
                preserved_scenes.append(new_entry)
        preserved_audio['scenes'] = preserved_scenes
        preserved_audio['continuous'] = False
        data['audio'] = preserved_audio
    else:
        # Preserve continuous audio metadata from generate_audio.py
        data['audio']['path'] = str(scenes_dir / 'narration.mp3')

    existing_assets = {a['sceneNumber']: a for a in data.get('assets', []) if 'sceneNumber' in a}
    merged_assets = []
    for new_entry in asset_entries:
        sn = new_entry['sceneNumber']
        if sn in existing_assets:
            existing_assets[sn]['exists'] = new_entry['exists']
            if new_entry.get('segments'):
                existing_assets[sn]['segments'] = new_entry['segments']
            merged_assets.append(existing_assets[sn])
        else:
            merged_assets.append(new_entry)
    data['assets'] = merged_assets

    timeline = build_timeline(scenes, merged_assets, video_dir, scenes_dir)
    data['timeline'] = timeline

    tail_pause = _get_tail_pause_sec(data)
    if is_continuous:
        narration_path = str(scenes_dir / 'narration.mp3')
        scene_timings = audio_config.get('sceneTimings', [])
        render_timeline = build_render_timeline(
            scenes, merged_assets, scenes_dir,
            audio_path=narration_path, scene_timings=scene_timings,
            tail_pause_sec=tail_pause,
        )
        audio_dur = audio_config.get('durationSec', 0)
        total_duration = audio_dur
    else:
        render_timeline = build_render_timeline(
            scenes, merged_assets, scenes_dir,
            scene_audio_durations=scene_audio_durations,
            tail_pause_sec=tail_pause,
        )
        total_duration = max(
            (entry.get("endSec", 0) for entry in render_timeline),
            default=0.0,
        )

    # Fill timeline gaps: extend visuals to cover silence between scene windows
    render_timeline = _fill_timeline_gaps(render_timeline, total_duration)

    # ─── Subtitle offsets for non-continuous mode ─────────────────────
    scene_offsets: dict[int, float] | None = None
    scene_windows: dict[int, tuple[float, float]] | None = None
    if not is_continuous:
        scene_offsets = {}
        scene_windows = {}
        for entry in render_timeline:
            sn = entry.get("sceneNumber")
            start = entry.get("startSec", 0)
            end = entry.get("endSec", 0)
            if sn is not None:
                if sn not in scene_offsets:
                    scene_offsets[sn] = start
                else:
                    scene_offsets[sn] = min(scene_offsets[sn], start)
                if sn not in scene_windows:
                    scene_windows[sn] = (start, end)
                else:
                    sw = scene_windows[sn]
                    scene_windows[sn] = (min(sw[0], start), max(sw[1], end))

    has_cues = any(
        scene.get("subtitleTiming", {}).get("cues", [])
        for scene in scenes
    )
    if has_cues:
        generate_ass_from_cues(
            scenes, subtitle_path,
            style_name=subtitle_style,
            scene_offsets=scene_offsets if not is_continuous else None,
            scene_windows=scene_windows if not is_continuous else None,
        )
    else:
        generate_ass_fallback(scenes, subtitle_path, style_name=subtitle_style)

    data['renderTimeline'] = render_timeline

    if not is_continuous:
        tail = _get_tail_pause_sec(data)
        data['audioPacing'] = {
            "sceneTailPauseSec": tail,
            "durationPolicy": "active_audio_plus_tail",
            "speechEndGuardSec": 0.15,
        }

    data['subtitles'] = {'path': str(subtitle_path), 'format': subtitle_format}
    data['render'] = {'path': str(video_dir / 'video.mp4'), 'durationSeconds': round(total_duration, 3)}
    data['review'] = {'status': 'PENDING'}
    if all_audio and all_assets:
        data['status'] = 'SUBTITLES_READY'
    elif all_audio:
        data['status'] = 'AUDIO_READY'
    elif all_assets:
        data['status'] = 'ASSETS_READY'
    data['updatedAt'] = datetime.now(timezone.utc).isoformat()

    has_motion = any(
        seg.get("motionType")
        for entry in merged_assets
        for seg in (entry.get("segments") or [])
    )

    metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({
        'jobId': job_id,
        'metadata': str(metadata_path),
        'subtitle': str(subtitle_path),
        'audioReady': all_audio,
        'assetsReady': all_assets,
        'renderTarget': data['render']['path'],
        'timelineSegments': len(timeline),
        'renderTimelineSegments': len(render_timeline),
        'subtitleTimingCues': sum(len(s.get("subtitleTiming", {}).get("cues", [])) for s in scenes),
        'hasMotionTypes': has_motion,
        'ctaEnabled': data.get("cta", {}).get("enabled", False),
    }))
    return 0
