#!/usr/bin/env python3

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


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
        "; ASS subtitles for shorts-historicos",
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
                           style_name: str = "documentary_safe"):
    lines = _ass_header(style_name)

    seen = set()

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
                    f"Dialogue: 0,{fmt_ass_time(start)},{fmt_ass_time(end)},{style_name},,0,0,0,,{wrapped}"
                )
        else:
            duration = float(scene.get("targetDurationSec", 5))
            text = (scene.get("subtitle") or scene.get("voiceover") or "").strip()
            wrapped = wrap_line(ass_escape(text))

    subtitles_path.write_text('\n'.join(lines) + '\n')


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
                          scene_timings: list[dict] | None = None) -> list[dict]:
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
        else:
            seg_audio_path = str(scenes_dir / f"scene-{sn:02}.mp3")
            scene_offset = accumulated_time
            st_entry = {}

        beats = scene.get("narrativeBeats", [])
        asset_entry = asset_by_scene.get(sn, {})
        segments = asset_entry.get("segments", [])
        scene_duration = float(scene.get("targetDurationSec", 5))
        if is_continuous and st_entry:
            st_end = st_entry.get("endSec", 0.0)
            if st_end > scene_offset:
                scene_duration = st_end - scene_offset
        vs_map = _get_visual_seq_map(scene)

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
            cumulative = scene_offset
            for seg in segments:
                seg_idx = seg.get("segmentIndex", 1)
                dur_frac = seg.get("durationFraction", 1.0 / max(len(segments), 1))
                seg_duration = scene_duration * dur_frac
                start_sec = cumulative
                end_sec = cumulative + seg_duration

                motion_type = seg.get("motionType", "static")
                overlay_text = seg.get("overlayText", "")
                transition = seg.get("transition", "cut")
                is_last = (seg_idx == len(segments))

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('metadata_path')
    parser.add_argument('--subtitle-style', choices=list(ASS_STYLES.keys()),
                        default=None,
                        help="ASS style for subtitles (default: from request.subtitles.style or shorts_upper_dynamic)")
    args = parser.parse_args()

    metadata_path = Path(args.metadata_path).resolve()
    video_dir = metadata_path.parent
    scenes_dir = video_dir / 'scenes'
    data = json.loads(metadata_path.read_text())
    job_id = data['jobId']
    scenes = data['script']['scenes']

    # Determine subtitle style from request config, CLI override, or default
    req_subtitles = data.get("request", {}).get("subtitles", {})
    style_from_request = req_subtitles.get("style", "shorts_upper_dynamic")
    subtitle_style = args.subtitle_style or style_from_request
    if subtitle_style not in ASS_STYLES:
        print(f"WARNING: unknown style '{subtitle_style}', falling back to shorts_upper_dynamic")
        subtitle_style = "shorts_upper_dynamic"

    scenes_dir.mkdir(parents=True, exist_ok=True)

    audio_config = data.get('audio', {})
    is_continuous = audio_config.get('continuous', False)

    total_duration = 0.0
    audio_entries = []
    asset_entries = []
    asset_by_scene = {a['sceneNumber']: a for a in data.get('assets', []) if 'sceneNumber' in a}

    for scene in scenes:
        scene_num = int(scene['sceneNumber'])
        duration = float(scene['targetDurationSec'])

        if is_continuous:
            audio_path = scenes_dir / 'narration.mp3'
            audio_entries.append({'sceneNumber': scene_num, 'path': str(audio_path), 'exists': audio_path.exists()})
        else:
            audio_path = scenes_dir / f"scene-{scene_num:02}.mp3"
            audio_entries.append({'sceneNumber': scene_num, 'path': str(audio_path), 'exists': audio_path.exists()})

        asset_entry = asset_by_scene.get(scene_num, {})
        segments = asset_entry.get('segments')
        if segments:
            seg_paths = []
            for seg in segments:
                seg_path = Path(seg['path']) if seg.get('path') else None
                seg_paths.append(str(seg_path) if seg_path else None)
            all_exist = all(p and Path(p).exists() for p in seg_paths if p)
            asset_entries.append({
                'sceneNumber': scene_num,
                'path': seg_paths[0] if seg_paths else None,
                'exists': all_exist,
                'segments': segments,
            })
        else:
            asset_path = scenes_dir / f"scene-{scene_num:02}.jpg"
            asset_entries.append({'sceneNumber': scene_num, 'path': str(asset_path), 'exists': asset_path.exists()})

        total_duration += duration

    all_audio = all(item['exists'] for item in audio_entries)
    all_assets = all(item['exists'] for item in asset_entries)

    subtitle_format = data.get('subtitles', {}).get('format', 'ass')
    subtitle_path = video_dir / f"subtitle.{subtitle_format}"

    has_cues = any(
        scene.get("subtitleTiming", {}).get("cues", [])
        for scene in scenes
    )
    if has_cues:
        generate_ass_from_cues(scenes, subtitle_path, style_name=subtitle_style)
    else:
        generate_ass_fallback(scenes, subtitle_path, style_name=subtitle_style)

    if not is_continuous:
        data['audio'] = {'provider': 'edge-tts', 'continuous': False, 'scenes': audio_entries}
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

    if is_continuous:
        narration_path = str(scenes_dir / 'narration.mp3')
        scene_timings = audio_config.get('sceneTimings', [])
        render_timeline = build_render_timeline(
            scenes, merged_assets, scenes_dir,
            audio_path=narration_path, scene_timings=scene_timings
        )
        audio_dur = audio_config.get('durationSec', total_duration)
        total_duration = audio_dur
    else:
        render_timeline = build_render_timeline(scenes, merged_assets, scenes_dir)
        audio_dur = total_duration

    # Fill timeline gaps: extend visuals to cover silence between scene windows
    render_timeline = _fill_timeline_gaps(render_timeline, audio_dur)
    data['renderTimeline'] = render_timeline

    data['subtitles'] = {'path': str(subtitle_path), 'format': subtitle_format}
    data['render'] = {'path': str(video_dir / 'video.mp4'), 'durationSeconds': int(round(total_duration))}
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


if __name__ == '__main__':
    raise SystemExit(main())
