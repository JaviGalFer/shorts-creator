# Spec: Continuous Audio Narration

## Texto completo

```python
def build_full_narration(scenes: list) -> dict:
    """Construye el texto completo y las unidades de narración por escena/oración.

    Returns:
        full_text: str — texto completo para edge-tts
        narration_units: list[{sceneNumber, sentenceIndex, text}] — cada oración como unidad
    """
    parts = []
    narration_units = []
    for s in scenes:
        sn = s["sceneNumber"]
        text = s.get("voiceover", "").strip()
        if not text:
            continue
        # Dividir el voiceover en oraciones individuales
        sentences = split_sentences(text)
        for si, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue
            if sentence[-1] not in ".!?":
                sentence += "."
            narration_units.append({
                "sceneNumber": sn,
                "sentenceIndex": si,
                "text": sentence,
            })
            parts.append(sentence)

    full_text = " ".join(parts)
    return full_text, narration_units


def split_sentences(text: str) -> list[str]:
    """Divide texto en oraciones por puntuación fuerte."""
    import re
    # Split en .!? seguido de espacio o fin de texto
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in parts if p.strip()]
```

## Comando edge-tts

```python
communicate = edge_tts.Communicate(full_text, voice)
```

## SceneTiming detection — por secuencia de SentenceBoundary

**NO** se usa búsqueda de primera/última palabra (frágil ante repeticiones entre escenas).

```python
def compute_scene_timings_by_sentences(
    narration_units: list[dict],
    sentence_boundaries: list[dict]
) -> tuple[list, str, str]:
    """Asigna SentenceBoundary N a narration_unit N por orden secuencial.

    Returns:
        (scene_timings, timing_confidence, status_hint)
        status_hint: "PASS" | "REVIEW_REQUIRED"
    """
    if len(sentence_boundaries) != len(narration_units):
        return [], "low", "REVIEW_REQUIRED"

    def normalize(t: str) -> str:
        import re
        return re.sub(r'\s+', ' ', t.lower().strip()).strip(".,!?;: \"'")

    timings = []
    current_scene = None
    scene_start = None

    for i, sb in enumerate(sentence_boundaries):
        unit = narration_units[i]
        sb_text = normalize(sb.get("text", ""))
        unit_text = normalize(unit["text"])

        # Validación de similitud textual
        sb_words = set(sb_text.split())
        unit_words = set(unit_text.split())
        if sb_words and unit_words:
            intersection = sb_words & unit_words
            similarity = len(intersection) / max(len(unit_words), 1)
            if similarity < 0.7:
                return [], "low", "REVIEW_REQUIRED"

        sb_start = sb["offset"] / 10000000
        sb_dur = sb["duration"] / 10000000
        sb_end = sb_start + sb_dur

        if unit["sceneNumber"] != current_scene:
            if current_scene is not None:
                timings.append({
                    "sceneNumber": current_scene,
                    "startSec": scene_start,
                    "endSec": sb_start,
                })
            current_scene = unit["sceneNumber"]
            scene_start = sb_start

    # Cerrar última escena
    if current_scene is not None and sentence_boundaries:
        last_sb = sentence_boundaries[-1]
        last_end = last_sb["offset"] / 10000000 + last_sb["duration"] / 10000000
        timings.append({
            "sceneNumber": current_scene,
            "startSec": scene_start,
            "endSec": last_end,
        })

    return timings, "high", "PASS"
```

## Fallback: silence trimming per-scene

Si edge-tts falla con texto largo (>3000 chars):

```bash
# Detectar silencio por escena
ffmpeg -i scene-01.mp3 -af silencedetect=noise=-50dB:d=0.05 -f null -

# Recortar leading/trailing silence con Python:
from pydub import AudioSegment, silence
audio = AudioSegment.from_mp3(path)
chunks = silence.detect_nonsilent(audio, min_silence_len=50, silence_thresh=-50)
if chunks:
    first = chunks[0][0]
    last = chunks[-1][1]
    trimmed = audio[first:last]
```

## Metadata output

```json
"audio": {
  "provider": "edge_tts",
  "continuous": true,
  "path": "narration.mp3",
  "durationSec": 38.2,
  "narrationUnits": [
    {"sceneNumber": 1, "sentenceIndex": 0, "text": "Un día en 1453, Constantinopla cayó y con ella un imperio milenario."},
    {"sceneNumber": 2, "sentenceIndex": 0, "text": "La ciudad fue asediada por el sultán Mehmed II y su ejército otomano."}
  ],
  "sceneTimings": [
    {"sceneNumber": 1, "startSec": 0.0, "endSec": 5.8},
    {"sceneNumber": 2, "startSec": 5.8, "endSec": 10.2}
  ],
  "timingConfidence": "high"
}
```
