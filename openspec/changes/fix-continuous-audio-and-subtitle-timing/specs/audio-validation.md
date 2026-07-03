# Spec: Audio Silence & Coverage Validation

## 1. Silence detection

```python
import subprocess
import re

def detect_silence_ranges(audio_path: str, threshold_db: float = -50, min_silence_sec: float = 0.3) -> list:
    """Usa FFmpeg silencedetect para encontrar regiones de silencio."""
    cmd = [
        "ffmpeg", "-i", audio_path,
        "-af", f"silencedetect=noise={threshold_db}dB:d={min_silence_sec}",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    stderr = result.stderr

    silences = []
    start_pattern = re.compile(r"silence_start: ([\d.]+)")
    end_pattern = re.compile(r"silence_end: ([\d.]+)")
    starts = [float(m.group(1)) for m in start_pattern.finditer(stderr)]
    ends = [float(m.group(1)) for m in end_pattern.finditer(stderr)]

    for i in range(min(len(starts), len(ends))):
        silences.append({
            "startSec": round(starts[i], 3),
            "endSec": round(ends[i], 3),
            "durationSec": round(ends[i] - starts[i], 3),
        })

    return silences
```

## 2. Silence classification

Diferenciar pausas narrativas naturales de errores.

```python
def classify_silence(silence: dict, scene_timings: list, cues: list) -> str:
    """Clasifica un silencio como natural, chapter_break o unexpected."""
    start = silence["startSec"]
    end = silence["endSec"]

    # Leading silence muy corto (<0.3s desde inicio del audio)
    if start < 0.3:
        return "natural"

    # Trailing silence muy corto (<0.3s desde final del audio)
    total_dur = scene_timings[-1]["endSec"] if scene_timings else 0
    if total_dur > 0 and total_dur - end < 0.3:
        return "natural"

    # Pausa post-puntuación: ocurre justo después del final de un cue (final de frase)
    for cue in cues:
        if abs(cue["endSec"] - start) < 0.15:
            return "natural"

    # Pausa en límite de escena declarado
    for st in scene_timings:
        if abs(st["endSec"] - start) < 0.2:
            return "chapter_break"

    return "unexpected"
```

## 3. Validation rules

```python
def validate_audio(audio_path: str, scene_timings: list, cues: list) -> dict:
    silences = detect_silence_ranges(audio_path)

    classified = []
    for s in silences:
        s["classification"] = classify_silence(s, scene_timings, cues)
        classified.append(s)

    unexpected = [s for s in classified if s["classification"] == "unexpected"]
    max_unexpected = max((s["durationSec"] for s in unexpected), default=0.0)
    unexpected_count = len(unexpected)

    # BLOCKED conditions
    mid_sentence_long = any(
        s["classification"] == "unexpected" and s["durationSec"] > 0.8
        for s in classified
    )
    chapter_long = any(
        s["classification"] == "chapter_break" and s["durationSec"] > 0.8
        for s in classified
    )
    too_many_unexpected = unexpected_count > 2

    if mid_sentence_long or chapter_long or too_many_unexpected:
        status = "BLOCKED"
    elif max_unexpected > 0.45 or unexpected_count > 0:
        status = "REVIEW_REQUIRED"
    else:
        status = "PASS"

    return {
        "status": status,
        "silenceRanges": classified,
        "maxUnexpectedSilenceSec": round(max_unexpected, 3),
        "unexpectedSilenceCount": unexpected_count,
    }
```

## 4. Coverage validation

```python
def validate_audio_coverage(audio_path: str, scene_timings: list, cues: list, narration_text: str) -> dict:
    failures = []

    # Obtener duración real del audio
    audio_dur = get_audio_duration(audio_path)

    # 1. sceneTimings cubre ≥98% del audio
    covered = sum(st["endSec"] - st["startSec"] for st in scene_timings)
    coverage_pct = (covered / audio_dur * 100) if audio_dur > 0 else 0
    if coverage_pct < 98:
        failures.append({"rule": "audio_coverage_below_98", "message": f"sceneTimings covers {coverage_pct:.1f}% of audio"})

    # 2. No hay solapes entre escenas
    for i in range(1, len(scene_timings)):
        if scene_timings[i-1]["endSec"] > scene_timings[i]["startSec"]:
            failures.append({"rule": "scene_timing_overlap",
                "message": f"Scene {scene_timings[i-1]['sceneNumber']} overlaps scene {scene_timings[i]['sceneNumber']}"})

    # 3. Cada cue pertenece a una sola escena
    for cue in cues:
        matched = [st for st in scene_timings if st["startSec"] <= cue["startSec"] < st["endSec"]]
        if len(matched) != 1:
            failures.append({"rule": "cue_outside_scene",
                "message": f"Cue '{cue['text'][:30]}...' at {cue['startSec']}s not in exactly one scene"})

    # 4. Texto concatenado de cues coincide con narración normalizada
    cue_text = " ".join(c["text"] for c in cues)
    if normalize_text(cue_text) != normalize_text(narration_text):
        failures.append({"rule": "cue_text_mismatch", "message": "Concatenated cue text does not match narration"})

    return {
        "status": "BLOCKED" if failures else "PASS",
        "failures": failures,
        "coveragePercent": round(coverage_pct, 1),
        "hasOverlaps": any("overlap" in f["rule"] for f in failures),
    }


def normalize_text(t: str) -> str:
    import re
    return re.sub(r'\s+', ' ', t.lower().strip()).strip(".,!?;: \"'")


def get_audio_duration(path: str) -> float:
    import subprocess, json
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(r.stdout)
    return float(data["format"]["duration"])
```
