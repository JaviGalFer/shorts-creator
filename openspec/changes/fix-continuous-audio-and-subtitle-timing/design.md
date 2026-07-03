# Design: Continuous Audio and Subtitle Timing

## 1. Arquitectura de audio continuo

### 1.1 Estrategia preferida: single narration MP3 por job

```
Texto completo = voiceover(scene1) + ". " + voiceover(scene2) + ". " + ...
                            |
                        edge-tts
                            |
                     narration.mp3
                            |
               +-------------+-------------+
               |                           |
       sceneTimings[]              subtitleTiming[]
       {scene, startSec, endSec}   {cueStart, cueEnd, text}
```

**Formato metadata:**

```json
{
  "audio": {
    "provider": "edge_tts",
    "path": "narration.mp3",
    "durationSec": 38.2,
    "continuous": true,
    "sceneTimings": [
      {"sceneNumber": 1, "startSec": 0.0, "endSec": 5.8},
      {"sceneNumber": 2, "startSec": 5.8, "endSec": 10.2}
    ]
  }
}
```

**Generación del texto completo:**

- Concatenar voiceovers con puntuación natural:
  - Si el voiceover termina en punto (`.`), agregar espacio.
  - Si no termina en puntuación, agregar punto + espacio.
  - Si termina en `?` o `!`, agregar espacio directamente.
- Cada escena mantiene su `sceneNumber` para mapeo temporal.
- Construir `narration_units[]`: lista ordenada de `{sceneNumber, text}` donde cada `text` es un voiceover normalizado. Una escena puede tener múltiples unidades si su voiceover contiene varias oraciones.

### 1.2 Obtención de timings por secuencia de SentenceBoundary

**NO** se usa búsqueda de primera/última palabra — es frágil ante palabras repetidas entre escenas.

**Algoritmo correcto:**

1. Construir `narration_units`: lista plana y ordenada de `{sceneNumber, sentenceIndex, text}` donde cada entrada corresponde a una oración del voiceover. Si un voiceover tiene 3 oraciones, genera 3 entradas con el mismo sceneNumber.

2. edge-tts produce SentenceBoundary events en orden secuencial. Cada SentenceBoundary tiene `offset` (ticks 100ns), `duration` (ticks 100ns) y `text`.

3. Asignar el SentenceBoundary N a la narration_unit N por orden secuencial.

4. Validar similitud textual entre el SentenceBoundary.text y narration_unit.text:
   - Normalizar ambos (minúsculas, sin puntuación, sin espacios extra).
   - Si la similitud es <70% (diferencia de tokens), marcar `timingConfidence: "low"` y dejar la escena como `REVIEW_REQUIRED`.
   - No inventar timings ni hacer fallback silencioso.

5. Si una escena tiene múltiples oraciones, el sceneTiming abarca desde el inicio de su primer SentenceBoundary hasta el final de su último SentenceBoundary.

6. Si el número de SentenceBoundary no coincide con el número de narration_units esperado:
   - Marcar `timingConfidence: "low"`.
   - La escena queda como `REVIEW_REQUIRED` o `BLOCKED`.
   - No asignar timings por estimación uniforme sin advertencia explícita.

```python
def compute_scene_timings_by_sentences(
    narration_units: list[dict],   # [{sceneNumber, sentenceIndex, text}, ...]
    sentence_boundaries: list[dict]  # [{offset, duration, text}, ...]
) -> tuple[list, str, str]:
    """
    Returns (scene_timings, confidence, status_hint).
    """
    if len(sentence_boundaries) != len(narration_units):
        return [], "low", "REVIEW_REQUIRED"

    timings = []
    current_scene = None
    scene_start = None

    for i, sb in enumerate(sentence_boundaries):
        unit = narration_units[i]
        sb_text = sb["text"].strip().lower()
        unit_text = unit["text"].strip().lower()
        similarity = text_similarity(sb_text, unit_text)

        if similarity < 0.7:
            return [], "low", "REVIEW_REQUIRED"

        sb_start = sb["offset"] / 10000000
        sb_end = sb_start + (sb["duration"] / 10000000)

        if unit["sceneNumber"] != current_scene:
            if current_scene is not None:
                timings.append({
                    "sceneNumber": current_scene,
                    "startSec": scene_start,
                    "endSec": sb_start,  # tentative, will be overwritten
                })
            current_scene = unit["sceneNumber"]
            scene_start = sb_start

    # Close last scene
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

### 1.3 Estrategia real usada: recorte de silencios post-EdgeTTS

EdgeTTS produce trailing silence de ~1.1s después de cada `. ` (SentenceBoundary). Esto es intrínseco al modelo y no se puede eliminar cambiando puntuación.

**Pipeline real (Constantinopla):**

1. Generar single MP3 con edge-tts (narration.mp3, 30.864s).
2. Detectar silencios con FFmpeg silencedetect.
3. Clasificar silencios como `chapter_break` (entre escenas) vs `natural` (entre oraciones dentro de escena).
4. Recortar silencios chapter_break a 0.35s usando `atrim` + `aevalsrc` + `concat` de FFmpeg.
5. Generar `narration_trimmed.mp3` (27.098s, reducción de ~3.77s).
6. Remapear sceneTimings proporcionalmente por escena al audio recortado.
7. Remapear cues proporcionalmente dentro de cada escena.

**Herramienta:** `bin/trim_narration_silences.py` — acepta sceneTimings originales, produce trimmed MP3 + sceneTimings y cues remapeados.

**Umbrales finales (Constantinopla render):**
- Chapter breaks: 0.35s cada uno (5 breaks total, 1.755s total)
- Unexpected silences: 0 (EdgeTTS intra-scene pauses clasificadas como natural con tolerancia 0.6s)
- Total silence: 4.74s / 27.098s = 17.5% (incluye chapter_breaks + naturales)
- sceneTimings coverage: 100% (endSec extendido hasta el startSec de la siguiente escena)

## 2. Subtítulos

### 2.1 Principios

- Los subtítulos se derivan EXCLUSIVAMENTE del texto narrado real.
- No crear frases editoriales, resúmenes, ni dividir por duración uniforme.
- Timing basado en WordBoundary → SentenceBoundary → estimación proporcional.
- Cada cue pertenece a una sola escena (validado por sceneTimings).
- El texto concatenado de todos los cues debe coincidir con la narración normalizada.

### 2.2 Reglas de cue

- mínimo 0.7s por cue
- máximo 2.5s por cue
- sin saltos visuales sin texto (no cues vacíos)
- dividir por puntuación y grupos semánticos, no por duración uniforme

### 2.3 Almacenamiento

```json
"subtitleTiming": {
  "timingSource": "edge_tts_word_boundary",
  "timingConfidence": "high",
  "cues": [
    {"sceneNumber": 1, "startSec": 0.1, "endSec": 2.1, "text": "Un día en 1453,"},
    {"sceneNumber": 1, "startSec": 2.1, "endSec": 5.1, "text": "Constantinopla cayó y con ella un imperio milenario."}
  ]
}
```

## 3. RenderTimeline con audio real

- Cada escena tiene `sceneTiming.startSec` y `endSec` absolutos.
- `renderTimeline[].startSec` = absoluto desde cues/subtitleTiming.
- No usar `targetDurationSec` como fuente primaria de duración.
- Los cues de subtítulos tienen timings absolutos.
- ASS subtitle generator debe recibir timings absolutos.

## 4. Validación automática de pausas

### 4.1 Detección

Usar FFmpeg silencedetect.

### 4.2 Reglas de validación — diferenciar pausas naturales de errores

**NO** bloquear por:
- silencio inicial/final muy corto (<0.3s)
- pausas posteriores a punto, coma fuerte o cambio de escena declarado en sceneTimings
- pausas justificadas por puntuación (.!?;:)

**BLOCKED solo si:**
- silencio >0.8s dentro de una frase (mismo scene, mid-sentence según cues)
- silencio >0.8s entre escenas sin `chapterBreak: true`
- más de dos pausas inesperadas >0.45s

**REVIEW_REQUIRED:**
- silencio 0.45–0.8s en límite de escena
- 1–2 pausas inesperadas >0.45s

```python
def classify_silence(silence: dict, scene_timings: list, cues: list) -> str:
    """Clasifica un silencio como 'natural' o 'unexpected'."""
    start = silence["startSec"]
    end = silence["endSec"]

    # Leading/trailing muy corto
    if start < 0.3:
        return "natural"
    total_dur = scene_timings[-1]["endSec"] if scene_timings else 0
    if total_dur - end < 0.3:
        return "natural"

    # Post-punctuation pause (pausa natural después de punto)
    for cue in cues:
        if abs(cue["endSec"] - start) < 0.15:
            return "natural"

    # Scene boundary
    for st in scene_timings:
        if abs(st["endSec"] - start) < 0.2:
            return "chapter_break"

    return "unexpected"
```

### 4.3 Formato en metadata

```json
"audioValidation": {
  "status": "PASS|REVIEW_REQUIRED|BLOCKED",
  "silenceRanges": [
    {"startSec": 5.9, "endSec": 6.8, "durationSec": 0.9, "classification": "unexpected"}
  ],
  "maxUnexpectedSilenceSec": 0.9,
  "unexpectedSilenceCount": 1
}
```

## 5. Validación de cobertura de audio

Se comprueba sobre sceneTimings, cues y audio:

- La suma de duración de sceneTimings cubre ≥98% del audio útil.
- No hay solapes entre escenas (scene N endSec <= scene N+1 startSec).
- Cada cue de subtítulo pertenece a una sola escena (por rango temporal).
- El texto concatenado de todos los cues coincide con la narración normalizada (diferencia permitida: solo espacios/puntuación).

## 6. Validación editorial de assets modernos

### 6.1 Regla

Un asset moderno (Pexels, b-roll, queries con términos modernos) SOLO es válido si:

1. `editorialRole == "consequence_or_legacy"` (rol soft de legado presente)
2. El beat narrativo menciona EXPLÍCITAMENTE el presente, legado o consecuencia contemporánea.
3. Hay coherencia con el beat concreto: si el asset muestra una calle moderna, el texto debe mencionar "Estambul actual" o similar explícito.
4. Pexels NO se considera automáticamente válido solo por estar en consequence_or_legacy — debe cumplir puntos 2 y 3.

### 6.2 Keywords de legado presente

```python
LEGACY_KEYWORDS = {
    "hoy", "hoy en día", "actual", "actualmente", "hoy día",
    "Estambul", "moderno", "moderna", "legado", "consecuencia",
    "contemporáneo", "contemporánea", "presente", "hoy,",
    "en la actualidad", "a día de hoy", "todavía", "aún",
    "today", "present", "modern", "legacy", "istanbul"
}
```

### 6.3 Validación

```python
def check_modern_asset_context(segment: dict, beat_text: str, editorial_role: str) -> list:
    if not is_modern_asset(segment):
        return []

    if editorial_role not in SOFT_ROLES:
        return [{"rule": "modern_asset_hard_role", "message": f"Modern asset in hard role '{editorial_role}'"}]

    text_lower = beat_text.lower()
    has_legacy_keyword = any(kw in text_lower for kw in LEGACY_KEYWORDS)
    if not has_legacy_keyword:
        return [{"rule": "modern_asset_no_legacy_context", "message": "Modern asset without legacy keywords in narration"}]

    # Si el asset es específicamente una calle/edificio moderno, "Estambul actual" debe estar en el texto
    if is_modern_street(segment) and "estambul" not in text_lower:
        return [{"rule": "modern_asset_missing_city_context", "message": "Modern street/building asset without 'Estambul actual' in narration"}]

    return []
```

## 7. Prueba controlada

### 7.1 Test de 12–15s con voz Edge TTS real

Antes de regenerar Constantinopla:

1. Crear 3 escenas con voiceovers reales (no tono sintético ni senoidal).
2. Generar single MP3 con edge-tts (voz real `es-ES-AlvaroNeural`).
3. Extraer SentenceBoundary y WordBoundary.
4. Calcular sceneTimings por secuencia de SentenceBoundary.
5. Generar cues de subtítulos desde WordBoundary.
6. Construir renderTimeline con timings absolutos.
7. Renderizar con FFmpeg.
8. Validar pausas, cobertura, sincronización de subtítulos.

### 7.2 Métricas de éxito

- Duración audio: 12–15s
- Silencio máximo inesperado: <0.35s
- Cues de subtítulos: 4–6
- sceneTimings cubren ≥98% del audio
- Sin solapes entre escenas
- FFmpeg exit code: 0
- Black frames: 0, Freeze frames: 0

## 8. Cierre

- No cerrar el OpenSpec actual (`fail-closed-assets-and-render-quality`).
- Mantener el estado del job como `REVIEW_REQUIRED` hasta revisión visual final.
- Este cambio produce primero una prueba controlada exitosa y luego un nuevo render de Constantinopla.
