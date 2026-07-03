#!/usr/bin/env python3
"""Generate a minimal 8-12s test job to validate the render pipeline."""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "videos"
FPS = 25
SCENES = [
    {
        "sceneNumber": 1,
        "purpose": "Test scene 1 with zoompan",
        "narrativeFunction": "hook",
        "voiceover": "Escena uno de prueba con zoom.",
        "subtitle": "Escena uno",
        "targetDurationSec": 4,
        "visualPlan": {
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetType": "broll",
                    "searchQuery": "test pattern",
                    "durationFraction": 1.0,
                    "transition": "cut",
                    "motionType": "slow_zoom_in",
                    "overlayText": "Test Zoom In",
                }
            ]
        },
        "narrativeBeats": [
            {
                "beatIndex": 1,
                "text": "Escena uno de prueba con zoom.",
                "startCueIndex": 0,
                "endCueIndex": 1,
                "visualIntent": "abstract",
                "preferredAssetType": "broll",
            }
        ],
        "subtitleTiming": {
            "timingSource": "estimated",
            "timingConfidence": "low",
            "cues": [
                {"startSec": 0.0, "endSec": 2.0, "text": "Escena uno de prueba"},
                {"startSec": 2.0, "endSec": 4.0, "text": "con zoom."},
            ],
        },
    },
    {
        "sceneNumber": 2,
        "purpose": "Test scene 2 with pan and fade",
        "narrativeFunction": "climax",
        "voiceover": "Escena dos con paneo y fundido.",
        "subtitle": "Escena dos",
        "targetDurationSec": 6,
        "visualPlan": {
            "visualSequence": [
                {
                    "segmentIndex": 1,
                    "assetType": "broll",
                    "searchQuery": "test pan",
                    "durationFraction": 0.5,
                    "transition": "cut",
                    "motionType": "pan_right",
                    "overlayText": "",
                },
                {
                    "segmentIndex": 2,
                    "assetType": "broll",
                    "searchQuery": "test static",
                    "durationFraction": 0.5,
                    "transition": "fade",
                    "motionType": "static",
                    "overlayText": "",
                },
            ]
        },
        "narrativeBeats": [
            {
                "beatIndex": 1,
                "text": "Escena dos con paneo.",
                "startCueIndex": 0,
                "endCueIndex": 1,
                "visualIntent": "abstract",
                "preferredAssetType": "broll",
            },
            {
                "beatIndex": 2,
                "text": "Escena dos con fundido.",
                "startCueIndex": 1,
                "endCueIndex": 2,
                "visualIntent": "abstract",
                "preferredAssetType": "broll",
            },
        ],
        "subtitleTiming": {
            "timingSource": "estimated",
            "timingConfidence": "low",
            "cues": [
                {"startSec": 0.0, "endSec": 3.0, "text": "Escena dos con paneo"},
                {"startSec": 3.0, "endSec": 6.0, "text": "y fundido."},
            ],
        },
    },
]


def generate_placeholder_image(path: Path, width: int, height: int, label: str, r: int, g: int, b: int):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (width, height), color=(r, g, b))
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), label, font=None)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((width - tw) / 2, (height - th) / 2), label, fill=(255, 255, 255))
    img.save(path)


def generate_audio(path: Path, duration_sec: float, frequency: int = 440):
    subprocess.run(
        ["docker", "run", "--rm",
         "-v", f"{PROJECT_ROOT}:/workspace",
         "linuxserver/ffmpeg:latest",
         "-y", "-f", "lavfi", "-i",
         f"sine=frequency={frequency}:duration={duration_sec}",
         "-c:a", "libmp3lame", "-b:a", "128k",
         f"/workspace/{path.relative_to(PROJECT_ROOT)}"],
        check=True, capture_output=True, timeout=30
    )


def generate_ass(path: Path, scenes_data: list[dict]) -> str:
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Arial,36,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,50,50,100,0",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    cue_index = 0
    for sc in scenes_data:
        cues = sc.get("subtitleTiming", {}).get("cues", [])
        for cue in cues:
            start = _fmt_ts(cue["startSec"])
            end = _fmt_ts(cue["endSec"])
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{cue['text']}")
            cue_index += 1
    content = "\n".join(lines)
    path.write_text(content, encoding="utf-8")
    return content


def _fmt_ts(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:06.3f}"


def build_render_timeline(scenes_data: list[dict], video_dir: Path) -> list[dict]:
    timeline = []
    for sc in scenes_data:
        sn = sc["sceneNumber"]
        beats = sc.get("narrativeBeats", [])
        visual_seq = sc.get("visualPlan", {}).get("visualSequence", [])
        target_dur = sc.get("targetDurationSec", 4)
        audio_path = str(video_dir / "scenes" / f"scene-{sn:02}.mp3")

        for beat in beats:
            bi = beat["beatIndex"]
            start_cue = beat.get("startCueIndex", 0)
            end_cue = beat.get("endCueIndex", 1)
            cues = sc.get("subtitleTiming", {}).get("cues", [])

            seg = visual_seq[bi - 1] if bi - 1 < len(visual_seq) else visual_seq[-1]
            seg_dur = target_dur / len(beats)
            asset_path = f"scenes/scene-{sn:02}-{seg['segmentIndex']:02}.jpg"

            timeline.append({
                "sceneNumber": sn,
                "beatIndex": bi,
                "assetPath": asset_path,
                "startSec": (bi - 1) * seg_dur,
                "endSec": bi * seg_dur,
                "durationSec": seg_dur,
                "transitionIn": seg.get("transition", "cut") if bi > 1 else "cut",
                "transitionOut": seg.get("transition", "cut"),
                "motionType": seg.get("motionType", "static"),
                "overlayText": seg.get("overlayText", ""),
                "subtitleCueIndexes": list(range(start_cue, end_cue + 1)),
                "audioPath": audio_path,
                "segmentIndex": seg["segmentIndex"],
                "assetType": seg.get("assetType", "broll"),
                "width": 1920,
                "height": 1080,
                "focalRegion": "center",
                "cropMode": "full_map",
            })

    return timeline


def main():
    now = datetime.utcnow()
    job_id = f"test-{now.strftime('%Y-%m-%d-%H%M%S')}"
    video_dir = DATA_DIR / job_id
    scenes_dir = video_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    # Generate placeholder images
    colors = [
        (40, 80, 180),   # blue
        (180, 60, 40),   # red
        (40, 160, 80),   # green
    ]
    for sc in SCENES:
        sn = sc["sceneNumber"]
        for seg in sc["visualPlan"]["visualSequence"]:
            si = seg["segmentIndex"]
            label = f"Scene {sn} Seg {si}\n{seg['motionType']}"
            path = scenes_dir / f"scene-{sn:02}-{si:02}.jpg"
            print(f"  Generating image: {path.name}")
            c = colors[(sn * 10 + si) % len(colors)]
            generate_placeholder_image(path, 1920, 1080, label, c[0], c[1], c[2])

    # Generate audio
    for sc in SCENES:
        sn = sc["sceneNumber"]
        dur = sc["targetDurationSec"]
        freq = 300 + sn * 80
        path = scenes_dir / f"scene-{sn:02}.mp3"
        print(f"  Generating audio: {path.name} ({dur}s, {freq}Hz)")
        generate_audio(path, dur, freq)

    # Build render timeline
    render_timeline = build_render_timeline(SCENES, video_dir)

    # Build ASS subtitles
    generate_ass(video_dir / "subtitle.ass", SCENES)

    # Build metadata
    metadata = {
        "jobId": job_id,
        "status": "ASSETS_READY",
        "topic": "Test Render Pipeline",
        "language": "es-ES",
        "format": "shorts-9x16",
        "targetDurationSeconds": sum(sc["targetDurationSec"] for sc in SCENES),
        "script": {
            "title": "Test: Render Pipeline Validation",
            "hook": "This is a test.",
            "summary": "Validating the render pipeline fix.",
            "totalTargetDurationSec": sum(sc["targetDurationSec"] for sc in SCENES),
            "scenes": SCENES,
        },
        "assets": [],
        "renderTimeline": render_timeline,
        "subtitles": {
            "path": str(video_dir / "subtitle.ass"),
            "format": "ass",
        },
        "render": {
            "path": str(video_dir / "video.mp4"),
            "durationSeconds": sum(sc["targetDurationSec"] for sc in SCENES),
        },
        "review": {"status": "PENDING"},
        "createdAt": now.isoformat() + "Z",
        "updatedAt": now.isoformat() + "Z",
    }

    metadata_path = video_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
    print(f"\nTest job created at: {video_dir}")
    print(f"Metadata: {metadata_path}")
    print(f"Render command: python bin/render_job.py {metadata_path}")
    print(f"Expected duration: {metadata['targetDurationSeconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
