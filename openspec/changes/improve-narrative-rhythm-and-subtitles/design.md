# Design: Narrative Rhythm & Subtitles

## 1. subtitleTiming

### Contrato

```json
{
  "subtitleTiming": {
    "timingSource": "edge_tts_word_boundary|estimated",
    "timingConfidence": "high|medium|low",
    "cues": [
      {"startSec": 0.0, "endSec": 1.8, "text": "En 1453, Constantinopla"},
      {"startSec": 1.8, "endSec": 3.9, "text": "seguía siendo la gran muralla"}
    ]
  }
}
```

### Reglas

- Los cues se agrupan en frases de 2-6 palabras o unidades semánticas completas.
- Si timingSource="estimated": cues distribuidos proporcionalmente por nº de palabras / duración total.
- Si timingSource="edge_tts_word_boundary": timestamps reales desde el TTS.

### Fuente de datos

- `edge_tts.SubMaker` captura eventos WordBoundary durante la generación de audio.
- Cada evento contiene: offset (ticks de 100ns), duration (ticks), text (palabra individual).
- Se agrupan palabras en cues de 2-6 palabras respetando puntuación.

### Fallback

- Si no hay cues (audio preexistente, error): distribución uniforme de palabras sobre duración total.
- Marcado como timingConfidence="low".

## 2. narrativeBeats

### Contrato (en script.scenes[].narrativeBeats)

```json
{
  "sceneNumber": 3,
  "narrativeBeats": [
    {
      "beatIndex": 1,
      "text": "Mehmed II reunió un ejército enorme",
      "startCueIndex": 0,
      "endCueIndex": 1,
      "visualIntent": "character_and_army",
      "preferredAssetType": "portrait_or_historical_art"
    },
    {
      "beatIndex": 2,
      "text": "y colocó cañones capaces de romper las murallas",
      "startCueIndex": 2,
      "endCueIndex": 3,
      "visualIntent": "siege_technology",
      "preferredAssetType": "historical_art_or_document"
    }
  ]
}
```

### Reglas

- Escenas ≤4s: 1 beat (opcional).
- Escenas 5-7s: mínimo 2 beats.
- Escenas ≥8s: 2-3 beats.
- Cada beat debe tener startCueIndex y endCueIndex que referencian subtitleTiming.cues[].
- visualIntent describe qué mostrar.

## 3. renderTimeline

### Contrato (generado por prepare_job.py)

```json
{
  "renderTimeline": [
    {
      "sceneNumber": 3,
      "beatIndex": 1,
      "assetPath": "scenes/scene-03-01.jpg",
      "startSec": 12.4,
      "endSec": 15.1,
      "durationSec": 2.7,
      "transitionIn": "cut",
      "transitionOut": "fade",
      "motionType": "slow_zoom_in",
      "overlayText": "MEHMED II · 1453",
      "subtitleCueIndexes": [6, 7]
    }
  ]
}
```

### Reglas de construcción

- startSec/endSec derivados de subtitleTiming.cues[beat.startCueIndex].startSec a cues[beat.endCueIndex].endSec.
- transitionIn: cómo entra el segmento ("cut" o "fade"). Default: "cut".
- transitionOut: cómo sale ("cut" o "fade"). Default: "cut", "fade" para último beat de escena.
- motionType heredado de visualSequence[segmento].motionType.
- overlayText heredado de segmento o visualSequence.

## 4. motionType

### Tipos admitidos

| motionType | Descripción | Filter FFmpeg |
|-----------|-------------|---------------|
| slow_zoom_in | Zoom lento (1.0→1.15) centrado | zoompan=z='if(lte(on,1),1,zoom+0.002)':d=N*25:s=1080x1920 |
| slow_zoom_out | Zoom out lento (1.15→1.0) centrado | zoompan=z='if(lte(on,1),1.15,zoom-0.002)':d=N*25:s=1080x1920 |
| pan_left | Paneo horizontal de derecha a izquierda | crop=1080:1920:'floor(iw-1080)*t/N':0 |
| pan_right | Paneo horizontal de izquierda a derecha | crop=1080:1920:'floor(iw-1080)*(1-t/N)':0 |
| pan_up | Paneo vertical de abajo arriba | crop=1080:1920:0:'floor(ih-1920)*t/N' |
| pan_down | Paneo vertical de arriba abajo | crop=1080:1920:0:'floor(ih-1920)*(1-t/N)' |
| static | Sin movimiento | scale+crop center estándar |
| detail_crop | Crop a detalle específico | crop=1080:1920 + scale |

### Reglas

- Cada segmento DEBE tener motionType.
- No repetir mismo motionType en >2 segmentos consecutivos.
- Retratos: slow_zoom_in, pan_up, detail_crop.
- Mapas: slow_zoom_in, pan_left, pan_right.
- B-roll: static, slow_zoom_in (no exagerado).

## 5. Subtítulos y overlays

### Capa A — Subtítulos (ASS)
- Texto: fragmentos del voiceover real agrupados por cues.
- Posición: inferior, max 2 líneas, ~16-22 chars/line.
- Timing: real desde edge-tts WordBoundary.
- Formato: ASS (compatible con render actual).

### Capa B — Overlay editorial (opcional, drawtext/drawbox)
- Posición: superior o lateral.
- Contenido: fecha, lugar, nombre, evento, "RECREACIÓN VISUAL".
- Nunca competir con subtítulos.
- Máximo 1 overlay por segmento.

## 6. CTA final

### Contrato

```json
{
  "cta": {
    "enabled": true,
    "text": "Más historia en menos de un minuto",
    "durationSec": 2.0,
    "assetPath": "scenes/scene-XX-01.jpg"
  }
}
```

### Reglas

- 1.5-2.5s máximo.
- No repetir asset del segmento anterior.
- Puede omitirse (enabled=false).
- Texto simple, sin competir con subtítulos.
