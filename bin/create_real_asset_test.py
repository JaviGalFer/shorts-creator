#!/usr/bin/env python3
"""Create a test job with 3 real historical assets from Wikimedia Commons.
Validates end-to-end: asset validation gate → render → post-render validation."""

import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "videos"

REAL_ASSETS = [
    {
        "segmentIndex": 1,
        "sceneNumber": 1,
        "url": "https://upload.wikimedia.org/wikipedia/commons/a/ad/Istanbul_And_Constantinople_%28Arabic%29.jpg",
        "filename": "scene-01-01.jpg",
        "assetType": "historical_map",
        "editorialRole": "context_map",
        "provider": "wikimedia_commons",
        "sourceUrl": "https://upload.wikimedia.org/wikipedia/commons/a/ad/Istanbul_And_Constantinople_%28Arabic%29.jpg",
        "license": "CC0",
        "author": "Aziz911q8 (Wikimedia Commons)",
        "score": 80,
        "searchQuery": "Map of Constantinople 1453",
        "editorialReason": "Historical map showing Constantinople",
        "overlayText": "Constantinopla, 1453",
        "motionType": "slow_zoom_in",
        "durationSec": 4.0,
    },
    {
        "segmentIndex": 1,
        "sceneNumber": 2,
        "url": "https://upload.wikimedia.org/wikipedia/commons/f/f3/Sarayi_Album_10a.jpg",
        "filename": "scene-02-01.jpg",
        "assetType": "historical_art_or_document",
        "editorialRole": "portrait",
        "provider": "wikimedia_commons",
        "sourceUrl": "https://upload.wikimedia.org/wikipedia/commons/f/f3/Sarayi_Album_10a.jpg",
        "license": "Public Domain",
        "author": "Ottoman miniature, Sarayi Album",
        "score": 90,
        "searchQuery": "Sultan Mehmed II portrait",
        "editorialReason": "Portrait of Sultan Mehmed II",
        "overlayText": "",
        "motionType": "slow_zoom_in",
        "durationSec": 4.0,
    },
    {
        "segmentIndex": 1,
        "sceneNumber": 3,
        "url": "https://upload.wikimedia.org/wikipedia/commons/b/bb/Byzantine_Constantinople-en.png",
        "filename": "scene-03-01.jpg",
        "assetType": "historical_map",
        "editorialRole": "context_map",
        "provider": "wikimedia_commons",
        "sourceUrl": "https://upload.wikimedia.org/wikipedia/commons/b/bb/Byzantine_Constantinople-en.png",
        "license": "CC BY-SA 3.0",
        "author": "Cplakidas / Wikimedia Commons",
        "score": 85,
        "searchQuery": "Byzantine Constantinople map",
        "editorialReason": "Map of Byzantine Constantinople",
        "overlayText": "",
        "motionType": "pan_right",
        "durationSec": 4.0,
    },
]


def download_image(url: str, path: Path) -> bool:
    print(f"  Downloading {url} -> {path.name}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ShortsHistoricos/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            path.write_bytes(r.read())
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def generate_audio(path: Path, duration_sec: float):
    subprocess.run(
        ["docker", "run", "--rm",
         "-v", f"{PROJECT_ROOT}:/workspace",
         "linuxserver/ffmpeg:latest",
         "-y", "-f", "lavfi", "-i",
         f"sine=frequency=400:duration={duration_sec}",
         "-c:a", "libmp3lame", "-b:a", "128k",
         f"/workspace/{path.relative_to(PROJECT_ROOT)}"],
        check=True, capture_output=True, timeout=30
    )


def generate_ass(path: Path, scenes: list[dict]):
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
    for sc in scenes:
        for cue in sc.get("subtitleTiming", {}).get("cues", []):
            start = _fmt_ts(cue["startSec"])
            end = _fmt_ts(cue["endSec"])
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{cue['text']}")
    path.write_text("\n".join(lines), encoding="utf-8")


def _fmt_ts(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:06.3f}"


def main():
    now = datetime.utcnow()
    job_id = f"test-real-{now.strftime('%Y-%m-%d-%H%M%S')}"
    video_dir = DATA_DIR / job_id
    scenes_dir = video_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    scenes_data = []
    asset_segments = {}
    render_segments = []

    for asset in REAL_ASSETS:
        sn = asset["sceneNumber"]
        si = asset["segmentIndex"]
        img_path = scenes_dir / asset["filename"]

        ok = download_image(asset["url"], img_path)
        if not ok:
            print(f"FATAL: Could not download {asset['url']}")
            return 1
        time.sleep(0.3)

        seg_key = (sn, si)
        asset_segments.setdefault(sn, []).append({
            "segmentIndex": si,
            "path": str(img_path),
            "assetType": asset["assetType"],
            "durationSec": asset["durationSec"],
            "transition": "cut",
            "provider": asset["provider"],
            "sourceUrl": asset["sourceUrl"],
            "license": asset["license"],
            "author": asset["author"],
            "score": asset["score"],
            "searchQuery": asset["searchQuery"],
            "editorialReason": asset["editorialReason"],
            "editorialRole": asset["editorialRole"],
            "width": None,
            "height": None,
            "downloadedAt": now.isoformat() + "Z",
        })

        render_segments.append({
            "sceneNumber": sn,
            "beatIndex": 1,
            "assetPath": f"scenes/{asset['filename']}",
            "startSec": 0.0,
            "endSec": asset["durationSec"],
            "durationSec": asset["durationSec"],
            "transitionIn": "cut",
            "transitionOut": "fade",
            "motionType": asset["motionType"],
            "overlayText": asset["overlayText"],
            "subtitleCueIndexes": [sn - 1],
            "audioPath": str(scenes_dir / f"scene-{sn:02}.mp3"),
            "segmentIndex": si,
            "assetType": asset["assetType"],
            "width": None,
            "height": None,
            "focalRegion": "center",
            "cropMode": "full_map",
        })

        scenes_data.append({
            "sceneNumber": sn,
            "purpose": f"Test scene {sn}: {asset['assetType']}",
            "narrativeFunction": "hook" if sn == 1 else "setup",
            "voiceover": f"Escena de prueba número {sn}.",
            "subtitle": f"Escena {sn}",
            "targetDurationSec": asset["durationSec"],
            "visualPlan": {
                "visualSequence": [{
                    "segmentIndex": si,
                    "assetType": asset["assetType"],
                    "searchQuery": asset["searchQuery"],
                    "durationFraction": 1.0,
                    "transition": "cut",
                    "motionType": asset["motionType"],
                    "overlayText": asset["overlayText"],
                }]
            },
            "narrativeBeats": [{
                "beatIndex": 1,
                "text": f"Escena de prueba número {sn}.",
                "startCueIndex": 0,
                "endCueIndex": 0,
                "visualIntent": "abstract",
                "preferredAssetType": asset["assetType"],
            }],
            "subtitleTiming": {
                "timingSource": "estimated",
                "timingConfidence": "low",
                "cues": [
                    {"startSec": 0.0, "endSec": asset["durationSec"], "text": f"Escena de prueba número {sn}."}
                ],
            },
        })

        print(f"  Generating audio: scene-{sn:02}.mp3 ({asset['durationSec']}s)")
        generate_audio(scenes_dir / f"scene-{sn:02}.mp3", asset["durationSec"])

    # Build assets array for metadata
    assets_meta = []
    for sn, segs in sorted(asset_segments.items()):
        first_seg = segs[0]
        assets_meta.append({
            "sceneNumber": sn,
            "selected": True,
            "path": first_seg["path"],
            "strategy": "historical_archive",
            "assetType": first_seg["assetType"],
            "provider": first_seg["provider"],
            "sourceUrl": first_seg["sourceUrl"],
            "originalUrl": first_seg["sourceUrl"],
            "license": first_seg["license"],
            "author": first_seg["author"],
            "score": first_seg["score"],
            "scoreReasons": [f"Manual test asset, score {first_seg['score']}"],
            "downloadedAt": now.isoformat() + "Z",
            "exists": True,
            "segments": segs,
        })

    generate_ass(video_dir / "subtitle.ass", scenes_data)

    expected_total = sum(a["durationSec"] for a in REAL_ASSETS)

    metadata = {
        "jobId": job_id,
        "status": "ASSETS_READY",
        "topic": "La caída de Constantinopla",
        "language": "es-ES",
        "format": "shorts-9x16",
        "targetDurationSeconds": expected_total,
        "script": {
            "title": "Test: Real Assets Pipeline",
            "hook": "Test de validación de assets reales.",
            "summary": "Validando el pipeline con 3 assets históricos reales.",
            "totalTargetDurationSec": expected_total,
            "scenes": scenes_data,
        },
        "assets": assets_meta,
        "renderTimeline": render_segments,
        "subtitles": {
            "path": str(video_dir / "subtitle.ass"),
            "format": "ass",
        },
        "render": {
            "path": str(video_dir / "video.mp4"),
            "durationSeconds": expected_total,
        },
        "review": {"status": "PENDING"},
        "createdAt": now.isoformat() + "Z",
        "updatedAt": now.isoformat() + "Z",
    }

    metadata_path = video_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
    print(f"\nTest job with REAL ASSETS created: {video_dir}")
    print(f"Metadata: {metadata_path}")
    print(f"Expected duration: {expected_total}s")
    print(f"\nRun validation: .venv/bin/python bin/asset_validation.py {metadata_path}")
    print(f"Run render: .venv/bin/python bin/render_job.py {metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
