#!/usr/bin/env python3
"""Prueba controlada: 3 escenas, single narration MP3, Edge TTS real, render 12-15s."""

import json
import subprocess
import sys
from pathlib import Path

PROJECT = Path("/home/javi/projects/shorts-creator")
TEST_JOB_DIR = PROJECT / "data/videos/test-continuous-audio"
REF_JOB_DIR = PROJECT / "data/videos/la-2026-07-01-173458"
VENV_PYTHON = str(PROJECT / ".venv" / "bin" / "python3")

# ─── 1. Crear metadata de prueba ───
def build_test_metadata() -> dict:
    return {
        "jobId": "test-continuous-audio",
        "status": "SCRIPT_DRAFT",
        "topic": "Prueba de audio continuo",
        "language": "es-ES",
        "format": "shorts-9x16",
        "targetDurationSeconds": 14,
        "script": {
            "title": "Test: Audio Continuo",
            "scenes": [
                {
                    "sceneNumber": 1,
                    "voiceover": "Esta es la primera escena de prueba para verificar que el audio continuo funciona correctamente.",
                    "subtitle": "Escena uno: inicio de la narración continua",
                    "targetDurationSec": 5,
                    "visualPlan": {
                        "strategy": "historical_archive",
                        "editorialRole": "context_map",
                        "primaryAssetType": "historical_map",
                        "period": "Imperio Bizantino, 1453",
                        "location": "Constantinopla",
                        "preferredSources": ["wikimedia_commons"],
                        "allowGeneratedImage": False,
                    },
                    "narrativeBeats": [
                        {"beatIndex": 1, "text": "Escena uno: inicio de la narración continua.",
                         "visualIntent": "context_map", "startCueIndex": 0, "endCueIndex": 1}
                    ],
                },
                {
                    "sceneNumber": 2,
                    "voiceover": "La segunda escena continúa la narración sin pausa, demostrando que no hay silencios entre escenas.",
                    "subtitle": "Escena dos: sin pausas",
                    "targetDurationSec": 5,
                    "visualPlan": {
                        "strategy": "historical_archive",
                        "editorialRole": "battle_or_assault",
                        "primaryAssetType": "historical_art_or_document",
                        "period": "Imperio Otomano, 1453",
                        "location": "Constantinopla",
                        "preferredSources": ["wikimedia_commons"],
                        "allowGeneratedImage": False,
                    },
                    "narrativeBeats": [
                        {"beatIndex": 1, "text": "Escena dos: sin pausas.",
                         "visualIntent": "battle_action", "startCueIndex": 0, "endCueIndex": 1}
                    ],
                },
                {
                    "sceneNumber": 3,
                    "voiceover": "Y la tercera escena concluye la prueba confirmando que la narración fluye de principio a fin sin interrupciones.",
                    "subtitle": "Escena tres: conclusión",
                    "targetDurationSec": 4,
                    "visualPlan": {
                        "strategy": "historical_archive",
                        "editorialRole": "civilian_impact",
                        "primaryAssetType": "historical_art_or_document",
                        "period": "Imperio Bizantino, 1453",
                        "location": "Constantinopla",
                        "preferredSources": ["wikimedia_commons"],
                        "allowGeneratedImage": False,
                    },
                    "narrativeBeats": [
                        {"beatIndex": 1, "text": "Escena tres: conclusión.",
                         "visualIntent": "civilian_impact", "startCueIndex": 0, "endCueIndex": 1}
                    ],
                },
            ],
        },
        "assets": [
            {
                "sceneNumber": 1,
                "selected": True,
                "path": str(REF_JOB_DIR / "scenes" / "scene-01-01.jpg"),
                "strategy": "historical_archive",
                "assetType": "historical_map",
                "segments": [{
                    "segmentIndex": 1,
                    "path": str(REF_JOB_DIR / "scenes" / "scene-01-01.jpg"),
                    "assetType": "historical_map",
                    "durationSec": 5.0,
                    "provider": "wikimedia_commons",
                    "sourceUrl": "https://upload.wikimedia.org/wikipedia/commons/3/34/The_fall_of_Constantinople%2C_6_april_1453_-_29_may_1453-ar.png",
                    "license": "Public domain",
                    "score": 30,
                    "width": 828,
                    "height": 546,
                    "editorialRole": "context_map",
                    "motionType": "static",
                    "transition": "cut",
                }],
            },
            {
                "sceneNumber": 2,
                "selected": True,
                "path": str(REF_JOB_DIR / "scenes" / "scene-02-01.jpg"),
                "strategy": "historical_archive",
                "assetType": "historical_art_or_document",
                "segments": [{
                    "segmentIndex": 1,
                    "path": str(REF_JOB_DIR / "scenes" / "scene-02-01.jpg"),
                    "assetType": "historical_art_or_document",
                    "durationSec": 5.0,
                    "provider": "wikimedia_commons",
                    "sourceUrl": "https://upload.wikimedia.org/wikipedia/commons/6/6e/Bellini%2C_Gentile_-_Sultan_Mehmet_II.jpg",
                    "license": "Public domain",
                    "score": 55,
                    "width": 3132,
                    "height": 4226,
                    "editorialRole": "battle_or_assault",
                    "motionType": "static",
                    "transition": "cut",
                }],
            },
            {
                "sceneNumber": 3,
                "selected": True,
                "path": str(REF_JOB_DIR / "scenes" / "scene-03-01.jpg"),
                "strategy": "historical_archive",
                "assetType": "historical_art_or_document",
                "segments": [{
                    "segmentIndex": 1,
                    "path": str(REF_JOB_DIR / "scenes" / "scene-03-01.jpg"),
                    "assetType": "historical_art_or_document",
                    "durationSec": 4.0,
                    "provider": "wikimedia_commons",
                    "sourceUrl": "https://upload.wikimedia.org/wikipedia/commons/c/c0/Le siège de Constantinople.jpg",
                    "license": "Public domain",
                    "score": 40,
                    "width": 1210,
                    "height": 1788,
                    "editorialRole": "civilian_impact",
                    "motionType": "static",
                    "transition": "cut",
                }],
            },
        ],
    }


def run_step(desc: str, cmd: list[str]) -> bool:
    print(f"\n{'='*60}")
    print(f"STEP: {desc}")
    print(f"{'='*60}")
    print(f"  $ {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.stdout:
        for line in r.stdout.strip().split('\n'):
            print(f"  {line}")
    if r.stderr:
        for line in r.stderr.strip().split('\n'):
            print(f"  [stderr] {line}")
    if r.returncode != 0:
        print(f"  FAILED (exit={r.returncode})")
        return False
    print(f"  OK")
    return True


def main() -> int:
    # Crear directorio de test
    TEST_JOB_DIR.mkdir(parents=True, exist_ok=True)
    scenes_dir = TEST_JOB_DIR / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    val_dir = TEST_JOB_DIR / "validation"
    val_dir.mkdir(parents=True, exist_ok=True)

    # Escribir metadata de prueba
    meta = build_test_metadata()
    meta_path = TEST_JOB_DIR / "metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    print(f"Test metadata written to {meta_path}")

    # Copiar imágenes de referencia
    for asset in meta["assets"]:
        src = Path(asset["path"])
        if src.exists():
            dst = scenes_dir / src.name
            if not dst.exists():
                dst.write_bytes(src.read_bytes())
                print(f"  Copied {src.name}")

    # Step 1: Generate continuous audio
    ok = run_step("Generate continuous audio", [
        VENV_PYTHON, str(PROJECT / "bin" / "generate_audio.py"),
        str(meta_path), "--continuous", "--voice", "es-ES-AlvaroNeural"
    ])
    if not ok:
        print("FATAL: Audio generation failed")
        return 1

    # Step 2: Prepare job (timeline, subtitles, renderTimeline)
    ok = run_step("Prepare job", [
        VENV_PYTHON, str(PROJECT / "bin" / "prepare_job.py"),
        str(meta_path),
    ])
    if not ok:
        print("FATAL: Job preparation failed")
        return 1

    # Step 3: Render
    ok = run_step("Render video", [
        VENV_PYTHON, str(PROJECT / "bin" / "render_job.py"),
        str(meta_path), "--skip-asset-validation",
    ])
    if not ok:
        print("FATAL: Render failed")
        return 1

    # Step 4: Measure results
    print(f"\n{'='*60}")
    print(f"VALIDACIÓN")
    print(f"{'='*60}")

    # Read final metadata
    data = json.loads(meta_path.read_text())
    audio = data.get("audio", {})
    rt = data.get("renderTimeline", [])
    render = data.get("render", {})

    print(f"\nAudio: continuous={audio.get('continuous')}")
    print(f"  durationSec={audio.get('durationSec')}")
    print(f"  timingConfidence={audio.get('timingConfidence')}")
    print(f"  sceneTimings={json.dumps(audio.get('sceneTimings', []), indent=2)}")
    print(f"  narrationUnits={len(audio.get('narrationUnits', []))}")
    print(f"  timingSource={audio.get('timingSource')}")

    # Analyze silences in narration.mp3
    narration_path = scenes_dir / "narration.mp3"
    if narration_path.exists():
        dur = audio.get('durationSec', 0)
        print(f"\n  narration.mp3 exists: {narration_path.stat().st_size} bytes")

        # Silence detection via Docker FFmpeg
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{PROJECT}:/workspace",
            "linuxserver/ffmpeg:latest",
            "-i", f"/workspace/data/videos/test-continuous-audio/scenes/narration.mp3",
            "-af", "silencedetect=noise=-50dB:d=0.1",
            "-f", "null", "-"
        ]
        r = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=30)
        import re
        starts = [float(m.group(1)) for m in re.finditer(r"silence_start: ([\d.]+)", r.stderr)]
        ends = [float(m.group(1)) for m in re.finditer(r"silence_end: ([\d.]+)", r.stderr)]

        silences = []
        for i in range(min(len(starts), len(ends))):
            silences.append({
                "startSec": round(starts[i], 3),
                "endSec": round(ends[i], 3),
                "durationSec": round(ends[i] - starts[i], 3),
            })
        max_expected = max((s["durationSec"] for s in silences), default=0.0)
        print(f"\n  Silences in narration.mp3: {len(silences)}")
        for s in silences:
            tag = "LEAD" if s["startSec"] < 0.3 else "TRAIL" if dur - s["endSec"] < 0.3 else "INT"
            print(f"    [{tag}] {s['startSec']:.3f}-{s['endSec']:.3f} ({s['durationSec']:.3f}s)")
        print(f"  Max unexpected silence: {max_expected:.3f}s")

    # RenderTimeline summary
    print(f"\n  RenderTimeline entries: {len(rt)}")
    for e in rt:
        print(f"    Scene {e['sceneNumber']}: {e['startSec']:.2f}-{e['endSec']:.2f}s "
              f"(dur={e['durationSec']:.2f}s) audio={Path(e['audioPath']).name}")

    # Video output
    video_path = TEST_JOB_DIR / "video.mp4"
    if video_path.exists():
        print(f"\n  Video: {video_path.stat().st_size / 1024 / 1024:.1f}MB, "
              f"duration={render.get('durationSeconds', '?')}s")

    # Coverage check
    st = audio.get('sceneTimings', [])
    if st and dur:
        total_covered = sum(s["endSec"] - s["startSec"] for s in st)
        coverage = (total_covered / dur * 100) if dur > 0 else 0
        print(f"\n  SceneTiming coverage: {coverage:.1f}% ({total_covered:.2f}s of {dur:.2f}s)")

    # Cue text verification
    cues = data["script"]["scenes"][0].get("subtitleTiming", {}).get("cues", [])
    cue_text = " ".join(c["text"] for c in cues)
    full_text = " ".join(u["text"] for u in audio.get("narrationUnits", []))
    print(f"\n  Cues: {len(cues)}")
    print(f"  Cue text matches narration: {normalize(cue_text) == normalize(full_text)}")

    print(f"\n{'='*60}")
    print(f"TEST {'PASSED' if ok else 'FAILED'}")
    print(f"{'='*60}")
    return 0 if ok else 1


def normalize(t: str) -> str:
    import re
    return re.sub(r'\s+', ' ', t.lower().strip()).strip(".,!?;: \"'")


if __name__ == "__main__":
    raise SystemExit(main())
