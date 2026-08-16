#!/usr/bin/env python3
"""Post-process narration.mp3 to trim chapter_break silences to target duration."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _package_bootstrap import ensure_src_on_path

ensure_src_on_path()

from shorts_creator.validation.audio import detect_silence_ranges, classify_silences, compute_quality_grade

TARGET_CHAPTER_BREAK_SEC = 0.35
TARGET_LEADING_SEC = 0.1
TARGET_TRAILING_SEC = 0.2


def build_trim_command(narration_path: Path, silences: list[dict],
                       scene_timings: list[dict], cues_by_scene: dict,
                       project_root: Path) -> list[str]:
    all_cues = []
    for sc_cues in cues_by_scene.values():
        all_cues.extend(sc_cues)
    total_dur = scene_timings[-1]["endSec"] if scene_timings else 0

    classify_silences(silences, scene_timings, cues_by_scene, total_dur)

    chapter_breaks = [s for s in silences if s["classification"] == "chapter_break"]
    naturals = [s for s in silences if s["classification"] == "natural"]

    speech_segments = []
    cursor = 0.0

    for cb in chapter_breaks:
        if cb["startSec"] > cursor:
            speech_segments.append((cursor, cb["startSec"]))
        cursor = cb["endSec"]

    if cursor < total_dur:
        speech_segments.append((cursor, total_dur))

    filter_parts = []
    input_labels = []
    silence_count = 0

    for i, (start, end) in enumerate(speech_segments):
        label = f"sp{i}"
        filter_parts.append(
            f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[{label}]"
        )
        input_labels.append(f"[{label}]")

        if i < len(chapter_breaks):
            silence_label = f"sil{i}"
            silence_dur = TARGET_CHAPTER_BREAK_SEC
            filter_parts.append(
                f"aevalsrc=0:d={silence_dur}[{silence_label}]"
            )
            input_labels.append(f"[{silence_label}]")
            silence_count += 1

    concat_n = len(input_labels)
    concat_filter = f"{''.join(input_labels)}concat=n={concat_n}:v=0:a=1[trimmed]"
    filter_parts.append(concat_filter)

    ws_dir = f"/workspace/{narration_path.parent.relative_to(project_root)}"
    output_path = narration_path.parent / "narration_trimmed.mp3"
    ws_output = f"{ws_dir}/narration_trimmed.mp3"

    cmd = [
        "docker", "run", "--rm",
        "-v", f"{project_root}:/workspace",
        "linuxserver/ffmpeg:latest",
        "-y",
        "-i", f"/workspace/{narration_path.relative_to(project_root)}",
        "-filter_complex", ";".join(filter_parts),
        "-map", "[trimmed]",
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        ws_output,
    ]

    return cmd, output_path


def compute_trimmed_scene_timings(original_timings: list[dict],
                                  silences: list[dict]) -> list[dict]:
    trimmed = []
    total_removed_before = 0.0

    cb_silences = [s for s in silences if s["classification"] == "chapter_break"]
    natural_silences = [s for s in silences if s["classification"] == "natural"]

    for st in original_timings:
        start_remove = 0.0
        end_remove = 0.0

        for cb in cb_silences:
            if abs(cb["startSec"] - st["endSec"]) < 1.5 or (cb["startSec"] < st["endSec"] < cb["endSec"]):
                removed = cb["durationSec"] - TARGET_CHAPTER_BREAK_SEC
                if removed < 0:
                    removed = 0
                end_remove = removed

        new_start = max(0.0, st["startSec"] - total_removed_before)
        new_end = max(new_start + 0.1, st["endSec"] - total_removed_before - end_remove)
        trimmed.append({
            "sceneNumber": st["sceneNumber"],
            "startSec": round(new_start, 3),
            "endSec": round(new_end, 3),
        })
        total_removed_before += end_remove

    return trimmed


def build_trim_operations(silences: list[dict]) -> list[dict]:
    cb_silences = [s for s in silences if s["classification"] == "chapter_break"]
    ops = []
    for cb in cb_silences:
        removed = round(cb["durationSec"] - TARGET_CHAPTER_BREAK_SEC, 3)
        ops.append({
            "type": "chapter_break",
            "originalStart": round(cb["startSec"], 3),
            "originalEnd": round(cb["endSec"], 3),
            "originalDuration": round(cb["durationSec"], 3),
            "targetDuration": TARGET_CHAPTER_BREAK_SEC,
            "removed": max(0.0, removed),
        })
    return ops


def cumulative_offset(cue_start: float, trim_ops: list[dict]) -> float:
    offset = 0.0
    for op in trim_ops:
        if op["originalEnd"] <= cue_start:
            offset += op["removed"]
    return offset


def adjust_cues_cumulative(cues: list[dict], trim_ops: list[dict]) -> tuple[list[dict], list[dict]]:
    remapped = []
    for cue in cues:
        cs = cue["startSec"]
        ce = cue["endSec"]
        off = cumulative_offset(cs, trim_ops)
        new_start = round(cs - off, 3)
        new_end = round(ce - off, 3)

        crosses = False
        for op in trim_ops:
            if cs < op["originalStart"] < ce:
                crosses = True
                break

        remapped.append({
            "originalStart": round(cs, 3),
            "originalEnd": round(ce, 3),
            "adjustedStart": new_start,
            "adjustedEnd": new_end,
            "driftMs": round(abs((ce - cs) - (new_end - new_start)) * 1000, 1),
            "crossesTrim": crosses,
            "text": cue["text"],
            "sceneNumber": cue.get("sceneNumber"),
        })

    adjusted = [
        {"startSec": r["adjustedStart"], "endSec": r["adjustedEnd"],
         "text": r["text"], "sceneNumber": r["sceneNumber"]}
        for r in remapped
    ]
    return adjusted, remapped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata_path", type=str)
    parser.add_argument("--target-chapter-break", type=float, default=TARGET_CHAPTER_BREAK_SEC)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    project_root = Path.cwd()
    meta_path = Path(args.metadata_path).resolve()
    video_dir = meta_path.parent
    data = json.loads(meta_path.read_text())
    audio_config = data["audio"]
    narration_path = video_dir / "scenes" / "narration.mp3"

    if not narration_path.exists():
        print(f"ERROR: narration.mp3 not found at {narration_path}")
        return 1

    scene_timings = audio_config.get("sceneTimings", [])
    cues_by_scene = {}
    for sc in data["script"]["scenes"]:
        sn = sc["sceneNumber"]
        cues_by_scene[sn] = sc.get("subtitleTiming", {}).get("cues", [])

    print("Detecting silences...")
    silences = detect_silence_ranges(narration_path, project_root)

    print("Classifying silences...")
    classify_silences(silences, scene_timings, cues_by_scene,
                      scene_timings[-1]["endSec"] if scene_timings else 0)

    cb = [s for s in silences if s["classification"] == "chapter_break"]
    nat = [s for s in silences if s["classification"] == "natural"]
    unexp = [s for s in silences if s["classification"] == "unexpected"]
    print(f"  Chapter breaks: {len(cb)}, Natural: {len(nat)}, Unexpected: {len(unexp)}")
    for s in cb:
        print(f"    CB {s['startSec']:.3f}-{s['endSec']:.3f} ({s['durationSec']:.3f}s → {args.target_chapter_break:.3f}s)")

    if unexp:
        print(f"WARNING: {len(unexp)} unexpected silences found — audio may have issues")
        for s in unexp:
            print(f"  UN {s['startSec']:.3f}-{s['endSec']:.3f} ({s['durationSec']:.3f}s)")

    if args.dry_run:
        print("Dry run — no changes made")
        return 0

    print(f"Building FFmpeg trim command...")
    cmd, output_path = build_trim_command(
        narration_path, silences, scene_timings, cues_by_scene, project_root
    )

    print("Running FFmpeg silence trim...")
    try:
        subprocess.run(cmd, check=True, timeout=120)
        print(f"  Trimmed audio saved to {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: FFmpeg failed with code {e.returncode}")
        return 1

    trimmed_dur = 0.0
    try:
        r = subprocess.run([
            "docker", "run", "--rm",
            "-v", f"{project_root}:/workspace",
            "--entrypoint", "ffprobe",
            "linuxserver/ffmpeg:latest",
            "-v", "quiet", "-print_format", "json", "-show_format",
            f"/workspace/{output_path.relative_to(project_root)}"
        ], capture_output=True, text=True, timeout=30)
        trimmed_dur = float(json.loads(r.stdout)["format"]["duration"])
    except Exception as e:
        print(f"WARNING: could not get trimmed audio duration: {e}")

    new_scene_timings = compute_trimmed_scene_timings(scene_timings, silences)
    all_old_cues = []
    for sc_cues in cues_by_scene.values():
        all_old_cues.extend(sc_cues)

    trim_ops = build_trim_operations(silences)
    new_cues, remapped_cues = adjust_cues_cumulative(all_old_cues, trim_ops)

    print(f"Original duration: {audio_config.get('durationSec', 0):.3f}s")
    print(f"Trimmed duration: {trimmed_dur:.3f}s")
    print(f"Removed: {audio_config.get('durationSec', 0) - trimmed_dur:.3f}s")
    print(f"New scene timings:")
    for st in new_scene_timings:
        old = next((o for o in scene_timings if o["sceneNumber"] == st["sceneNumber"]), None)
        old_dur = (old["endSec"] - old["startSec"]) if old else 0
        new_dur = st["endSec"] - st["startSec"]
        print(f"  Scene {st['sceneNumber']}: [{st['startSec']:.3f}-{st['endSec']:.3f}] ({new_dur:.3f}s, was {old_dur:.3f}s)")

    print(f"New cue count: {len(new_cues)}")
    for r in remapped_cues:
        flags = []
        if r["crossesTrim"]:
            flags.append("CROSSES_TRIM")
        if r["driftMs"] > 1.0:
            flags.append(f"DRIFT={r['driftMs']:.1f}ms")
        if flags:
            print(f"  Cue warn: [{r['originalStart']:.3f}-{r['originalEnd']:.3f}] → [{r['adjustedStart']:.3f}-{r['adjustedEnd']:.3f}] {' '.join(flags)}")

    data["audio"]["path"] = str(output_path)
    data["audio"]["durationSec"] = round(trimmed_dur, 3)
    data["audio"]["sceneTimings"] = new_scene_timings

    if "subtitleTiming" not in data:
        data["subtitleTiming"] = {}
    data["subtitleTiming"]["originalCues"] = all_old_cues
    data["subtitleTiming"]["trimOperations"] = trim_ops
    data["subtitleTiming"]["remappedCues"] = remapped_cues
    data["subtitleTiming"]["remapStrategy"] = "cumulative_offset"

    for sc in data["script"]["scenes"]:
        sn = sc["sceneNumber"]
        scene_cues = [c for c in new_cues if c.get("sceneNumber") == sn]
        sc["subtitleTiming"]["cues"] = scene_cues

    data["updatedAt"] = "2026-07-01T19:47:00.000000+00:00"
    meta_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    print(f"Metadata updated at {meta_path}")
    print(f"Done — trimmed narration ready for re-render")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
