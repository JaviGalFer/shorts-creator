# Sesión: Continuous Audio and Subtitle Timing — Diseño con correcciones

- Fecha: 2026-07-01
- Objetivo: Diseñar narración continua sin pausas artificiales, subtítulos desde audio real, validación de silencios y bloqueo de assets modernos fuera de contexto.
- Problema: El vídeo renderizado tiene pausas entre escenas por MP3 independientes. Subtítulos usan duración estimada. Assets modernos aparecen sin justificación narrativa.
- Estado inicial: Pipeline genera 1 MP3/escena vía edge-tts → FFmpeg concat introduce gaps. Subtítulos con timing estimado. RenderTimeline usa targetDurationSec.
- Cambio OpenSpec relacionado: `fix-continuous-audio-and-subtitle-timing` (nuevo, independiente del anterior)
- Agente responsable: AI (opencode)

## Correcciones aplicadas al diseño (según feedback)

1. **sceneTimings por SentenceBoundary sequence** (no first/last word):
   - Se construye `narration_units[]` con cada oración como unidad individual.
   - SentenceBoundary N se asigna a narration_unit N por orden secuencial.
   - Validación de similitud textual ≥70% entre SentenceBoundary.text y narration_unit.text.
   - Si el conteo de SentenceBoundary no coincide con narration_units, timingConfidence=low y REVIEW_REQUIRED.

2. **Silencios: diferenciar naturales de errores**:
   - Se ignoran: leading/trailing <0.3s, pausas post-puntuación (final de cue), límites de escena declarados.
   - BLOCKED solo: >0.8s mid-sentence, >0.8s entre escenas sin chapterBreak, >2 unexpected >0.45s.
   - Cada silencio se clasifica como natural/chapter_break/unexpected.

3. **Cobertura de audio**: ≥98% cubierto por sceneTimings, sin solapes, cada cue en una escena, texto de cues coincide con narración.

4. **Test controlado**: usa voz Edge TTS real (es-ES-AlvaroNeural), no tono sintético.

5. **Assets modernos**: Pexels no es automáticamente válido en consequence_or_legacy. Necesita keyword de presente + coherencia con beat concreto + "Estambul actual" explícito si es calle/edificio moderno.

6. **No cerrar OpenSpec anterior**: mantener job como REVIEW_REQUIRED hasta revisión visual.

## Documentos creados/actualizados

- `openspec/changes/fix-continuous-audio-and-subtitle-timing/proposal.md`
- `openspec/changes/fix-continuous-audio-and-subtitle-timing/design.md` (actualizado)
- `openspec/changes/fix-continuous-audio-and-subtitle-timing/tasks.md` (actualizado)
- `openspec/changes/fix-continuous-audio-and-subtitle-timing/specs/continuous-audio.md` (SentenceBoundary seq)
- `openspec/changes/fix-continuous-audio-and-subtitle-timing/specs/subtitle-timing.md`
- `openspec/changes/fix-continuous-audio-and-subtitle-timing/specs/audio-validation.md` (clasificación + cobertura)
- `openspec/changes/fix-continuous-audio-and-subtitle-timing/specs/modern-asset-blocking.md`

## Fase 0 — Diagnóstico de audio REAL completado

### Método
- Usar Docker FFmpeg (linuxserver/ffmpeg) con silencedetect (threshold -50dB, min duration 0.1s)
- ffprobe para duración de cada archivo
- Analizar cada MP3 de escena individualmente + el audio del MP4 final

### Tabla de resultados

| Escena | Dur.total | Sil.ini | Sil.fin | Pausa.int | Voz útil | % voz |
|--------|----------:|--------:|--------:|----------:|---------:|------:|
| scene-01.mp3 | 6.12s | 0.243s | 0.929s | 0.285s | 4.66s | 76% |
| scene-02.mp3 | 4.92s | 0.292s | 0.942s | 0.000s | 3.69s | 75% |
| scene-03.mp3 | 4.99s | 0.271s | 0.935s | 0.000s | 3.79s | 76% |
| scene-04.mp3 | 6.38s | 0.260s | 0.951s | 1.093s | 3.89s | 61% |
| scene-05.mp3 | 4.39s | 0.288s | 0.927s | 0.000s | 3.18s | 72% |
| scene-06.mp3 | 4.61s | 0.267s | 0.896s | 0.271s | 3.17s | 69% |
| **video.mp4** | **36.24s** | **0.243s** | **0.899s** | **4.588s** | **18.58s** | **51%** |

### Causa raíz

**COMBINACIÓN de tres factores:**

1. **EdgeTTS leading silence por escena** (~0.25s cada una, 1.62s total): Edge TTS inserta un silencio al inicio de cada generación de audio. Con 6 escenas, cada una con su propio MP3, se acumulan 1.62s de leading silence en puntos de transición.

2. **EdgeTTS trailing silence por escena** (~0.9s cada una, 5.58s total): Edge TTS añade silencio al final de cada locución. Es el contribuyente individual más grande — casi 1 segundo de pausa después de cada escena.

3. **Concat gaps del render** (+8.61s adicionales en el MP4): El MP4 tiene 17.66s de silencio total, pero los MP3 suman solo 9.04s de silencio. Los 8.61s adicionales provienen del proceso de render (probablemente: transiciones fade entre escenas + padding visual cuando la duración visual excede el audio + recomposición en FFmpeg).

**Métrica clave: 49% del vídeo es silencio** (17.66s de 36.24s).

Las pausas internas de EdgeTTS (dentro de una misma escena) son marginales: 1.84s total, y la más larga es de 1.09s (scene 4, probablemente pausa natural entre oraciones).

### Recomendación

Opción A (preferida): **Single narration MP3** — un solo edge-tts call para todo el texto.
- EdgeTTS produce audio continuo sin leading/trailing entre escenas.
- El render recibe 1 solo archivo de audio → 0 concat gaps entre escenas.
- Se eliminan ~7.20s de leading+trailing silence.
- Se eliminan ~8.61s de concat gaps adicionales.
- Total estimado de silencio eliminado: ~15.8s.
- El vídeo pasaría de 49% silencio a ~5% silencio (solo pausas narrativas naturales).

Opción B (fallback): Recortar leading/trailing de cada MP3 y concatenar con pausa controlada de 0.10–0.20s.

### Comando usado para diagnóstico
```
docker run --rm -v <project>:/workspace linuxserver/ffmpeg:latest \\
  -i /workspace/<path> -af silencedetect=noise=-50dB:d=0.1 -f null -
docker run --rm --entrypoint ffprobe linuxserver/ffmpeg:latest \\
  -v quiet -print_format json -show_format /workspace/<path>
```

### Próximo paso

Fase 2: Implementar single narration MP3 en generate_audio.py (modo `--continuous`).

---

## Fase 2-4, 8-9 — Implementación y pruebas completadas ✅

### Cambios realizados

#### `bin/generate_audio.py`
- `split_sentences()`: Divide voiceover en oraciones por puntuación fuerte.
- `build_full_narration()`: Construye texto completo + narration_units por oración/escena.
- `compute_scene_timings_by_sentences()`: Asigna SentenceBoundary N → narration_unit N por orden secuencial con validación de similitud textual ≥70%.
- Si SentenceBoundary count ≠ narration_units count → timingConfidence=low, REVIEW_REQUIRED.
- `main_continuous()`: Flujo completo de audio continuo (3 escenas de test, 6 de Constantinopla).
- `group_words_into_cues()`: Agrupa palabras en cues con reglas de puntuación.
- Cada cue recibe `sceneNumber` asignado por rango temporal contra sceneTimings.

#### `bin/prepare_job.py`
- **`build_render_timeline()`**: Acepta `audio_path` y `scene_timings` opcionales.
  - `scene_offset` desde sceneTimings (startSec absoluto).
  - `scene_duration` override desde sceneTimings (no targetDurationSec).
  - Último beat de cada escena extendido a sceneTiming.endSec para cubrir trailing silence.
  - Validación ALL-OR-NOTHING de índices de cue: si algún beat tiene índices fuera de rango, todos los beats usan división equitativa de scene_duration.
- **`generate_ass_from_cues()`**: Subtítulos con timestamps absolutos, deduplicación de cues.
- **`main()`**: Preserva `audio.continuous=true`, usa narration.mp3, expected duration de audio.durationSec.

#### `bin/render_job.py`
- **Single audio input**: En modo continuo, carga narration.mp3 como única fuente de audio.
- **Video-only concat**: Scene groups usan `concat=n=N:v=1:a=0` (sin audio por escena).
- **Narración directa**: `[narration_a]` mapeado como audio de salida.
- **`preflight_validate()`**: Acepta `expected_total` opcional. En modo continuo usa audio.durationSec.
- **`expected_duration`**: Desde `audio.durationSec`, no suma duración de segmentos en modo continuo.

#### `tests/test_continuous_audio.py`
- Prueba controlada: 3 escenas, Edge TTS real (es-ES-AlvaroNeural), assets existentes de Constantinopla.
- Steps: generate → prepare → render → validate.
- Validación: silencios, renderTimeline, cobertura, sincronización de cues.

### Bugs encontrados y corregidos

| Bug | Archivo | Síntoma | Fix |
|-----|---------|---------|-----|
| expected_duration duplicado | render_job.py:434 | 31.89s esperado vs 18.24s real | Guard `if not is_continuous_audio` (ya presente) |
| scene_duration de targetDurationSec | prepare_job.py:225 | RenderTimeline solo 13.5s, audio 18.24s | Override desde sceneTimings |
| Último beat no cubría trailing silence | prepare_job.py:243 | Último frame congelado 0.15-0.5s | Extender a st_entry.endSec |
| Beats con índices mixtos (válidos+inválidos) | prepare_job.py:240 | Entradas solapadas (Scene 2) | Validación ALL-OR-NOTHING de índices de cue |
| Preflight validación contra targetDurationSec | render_job.py:228 | 18.1s vs 14.0s esperado, abort | Usar audio.durationSec en continuo |

### Resultados de test controlado

```
Test metadata written ✓
Generate continuous audio ✓ (18.24s, 3 units, 3 SB, timingConfidence=high)
Prepare job ✓ (3 renderTimeline segments, 9 cues)
Render video ✓
─────────────────────────────────
Status: RENDERED
expectedDurationSec: 18.24
actualVideoDurationSec: 18.24
durationDeltaSec: 0.0
ffmpegExitCode: 0
blackFrameWarnings: 0
freezeFrameWarnings: 0
SceneTiming coverage: 99.2%
─────────────────────────────────
RenderTimeline:
  Scene 1: 0.10-5.69s (5.59s)
  Scene 2: 5.69-11.72s (6.04s)
  Scene 3: 11.72-18.19s (6.46s)
No overlaps, no gaps
```

### Resultados de Constantinopla regenerado

```
Regeneración con --continuous:
- 6 escenas, 7 narration units, 424 chars
- Audio: 30.864s continuo (vs 36.24s original con 49% silencio)
- SceneTimings: confidence=high
- Render: 10 segments, expected=30.864s, actual=30.86s, delta=-0.0s
- FFmpeg exit: 0, black frames: 0, freeze frames: 0
- Status: RENDERED
```

### Estado actual del pipeline

- Modo `--continuous` funcional y verificado.
- Test controlado pasa consistentemente.
- Constantinopla regenerado con audio continuo.
- Pendientes fases 5-7 (validación de pausas, cobertura, assets modernos).
