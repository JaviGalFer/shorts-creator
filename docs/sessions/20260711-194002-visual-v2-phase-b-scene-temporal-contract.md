# Sesión: Phase B — Per-scene Temporal Contract

**Timestamp:** 2026-07-11T19:40:02Z  
**Change:** `stabilize-visual-v2-runtime-contracts`  
**OpenSpec:** `openspec/changes/stabilize-visual-v2-runtime-contracts/`  
**Modelo:** DeepSeek V4 Pro  
**Modo:** Build

## 1. Causa raíz de subtítulos solapados

Los `WordBoundary` de cada MP3 comienzan desde cero. `generate_ass_from_cues()` escribía esos tiempos locales directamente en el ASS. Como todas las escenas tenían cues entre 0 y ~7 segundos, aparecían simultáneamente. La solución: derivar offsets globales del `renderTimeline` y sumarlos a los tiempos locales de cada cue en `generate_ass_from_cues()`.

## 2. Causa raíz del audio truncado

En modo per-scene, `render_job.py` usaba `atrim=duration={dur}` donde `dur` era la duración del PRIMER segmento de cada escena, no la ventana completa. En escenas con varios segmentos, la narración se truncaba. La solución: calcular `sceneWindowSec` desde el renderTimeline (`max(endSec) - min(startSec)`) y usar ese valor en la cadena `apad,atrim=duration={sceneWindowSec}`.

## 3. Estructura final de audio.scenes[].durationSec

```json
{
  "provider": "edge-tts",
  "continuous": false,
  "scenes": [
    {
      "sceneNumber": 1,
      "path": "data/videos/job-xxx/scenes/scene-01.mp3",
      "exists": true,
      "durationSec": 6.576
    }
  ]
}
```

La duración se obtiene del archivo MP3 real vía `_get_mp3_duration()` (ffprobe local, fallback Docker).

## 4. Definición de sceneWindowSec

`resolve_scene_window_duration(target, audio)` en `bin/prepare_job.py`:

```python
sceneWindowSec = max(targetDurationSec, actualAudioDurationSec)
```

Validación: ambos finitos, positivos, rechaza NaN/inf/bool/str/negatives.

Ejemplos:
- target 8.0, audio 6.576 → 8.0
- target 5.0, audio 6.936 → 6.936
- target 12.0, audio 7.536 → 12.0

## 5. Distribución de segmentos

`build_render_timeline()` acepta `scene_audio_durations: dict[int, float] | None`. Para cada escena no continua:
1. `scene_duration = resolve_scene_window_duration(target, actual_audio_dur)`
2. Segmentos distribuidos por `durationFraction` sobre `scene_duration`
3. Escenas contiguas (accumulated_time)
4. Sin gaps, sin solapes

## 6. Fuente de offsets de subtítulos

Los offsets se derivan del `renderTimeline` ya resuelto: `min(startSec)` de las entradas de cada escena. Se pasan a `generate_ass_from_cues()` vía `scene_offsets`. El parámetro es opcional (None = backward-compatible).

## 7. Cadena FFmpeg final de padding y trim

```text
[{input}:a]aresample=44100,asetpts=PTS-STARTPTS,apad,atrim=duration={sceneWindowSec}[a{sn}]
```

Donde `sceneWindowSec = scene_windows[sn]["endSec"] - scene_windows[sn]["startSec"]`.

`apad` añade silencio si el audio es más corto. `atrim` garantiza duración exacta. No se usa la duración del primer segmento.

## 8. Preflight agregado

`preflight_validate()` agrupa entradas por `sceneNumber`:
- Contiguidad (gap ≤ 0.05s)
- Audio paths consistentes
- Audio ≤ scene_window + 0.10s (audio > ventana → error bloqueante)
- Ventana > audio → OK (padding añadido)

## 9. Continuous audio y V1 compatibility

- Audio continuo: sin cambios (sin doble offset, sin padding por escena, cues ya globales)
- V1: sin cambios (campos legacy, sourcing, asset validation, roles editoriales)
- `scene_offsets=None` en `generate_ass_from_cues()` preserva comportamiento original
- Sin campos legacy ni modos de dominio

## 10. Archivos modificados

- `bin/generate_audio.py` — `_get_mp3_duration()`, `durationSec` en per-scene metadata
- `bin/prepare_job.py` — `resolve_scene_window_duration()`, `build_render_timeline()` con scene_audio_durations, `generate_ass_from_cues()` con scene_offsets, reorder en `main()`
- `bin/render_job.py` — cadena audio per-scene (apad+atrim), preflight agregado, expected_duration desde timeline

## 11. Tests añadidos

- `tests/test_prepare_job_scene_temporal_contract.py` — 22 tests
- `tests/test_render_job_scene_audio_contract.py` — 26 tests
- Total: 48 tests nuevos

## 12. Resultados focalizados

```
48 passed in 0.09s
```

Todos los tests nuevos pasan:
- `resolve_scene_window_duration`: 18 tests (target/audio, valores inválidos, NaN/inf/bool/str)
- Timeline distribution: 7 tests (2-seg, 3-scene, single-seg, V2 paths)
- Subtitle offsets: 7 tests (global times, no mutation, missing offset, backward compat)
- Integration: 2 tests (scene window in timeline, offsets in ASS)
- Preflight: 8 tests (aggregate, non-contiguous, paths, continuous)
- Expected duration: 2 tests
- Scene audio window: 2 tests
- Backward compatibility: 3 tests

## 13. Resultado de la suite completa

```
947 passed, 16 failed
```

## 14. Comparación con baseline

| Fase | Passed | Failed | Delta |
|------|--------|--------|-------|
| Baseline (antes A) | 820 | 16 | — |
| Tras Build A | 874 | 16 | +54 |
| Tras correcciones A | 899 | 16 | +25 |
| **Tras Phase B** | **947** | **16** | **+48** |

48 tests nuevos, 0 regresiones. Los 16 fallos siguen siendo los preexistentes (15 test_run_job.py, 1 test_semantic_asset_validation.py).

## 15. OpenSpec actualizado

- `proposal.md` — Phase B descrita como completada
- `design.md` — Secciones B.1–B.8 añadidas
- `tasks.md` — Phase B tareas marcadas, resultados actualizados
- `specs/per-scene-temporal-contract.md` — 12 requisitos verificables (REQ-B01 a REQ-B12)

## 16. Confirmación: sin campos legacy

No se añadieron campos legacy a ningún archivo de metadata o código.

## 17. Confirmación: sin modos de dominio

No se añadieron modos historical, science, documentary, legacy ni general.

## 18. Confirmación: no se ejecutó E2E

No se ejecutó E2E live durante esta sesión. No se realizaron llamadas HTTP a providers. No se descargaron imágenes. No se publicaron vídeos.

## 19. Decisión sobre cierre de Phase B

Phase B está lista para cerrar. Todos los contratos están implementados, testeados y sin regresiones. Solo queda el E2E live.

## 20. Recomendación para repetir el E2E live

Para repetir el E2E con el contrato temporal corregido, usar un job nuevo con escenas multi-segmento que tengan duración de audio distinta al target:

```bash
python3 bin/run_job.py --topic "Tema histórico de prueba" \
  --duration-profile short_25_30
```

Ejecutar las etapas: script → (fetch_images_v2) → generate_audio → prepare_job → render_job

Verificar en el metadata.json final:
- `audio.scenes[].durationSec` presente y correcto
- `renderTimeline` con entradas distribuidas sobre sceneWindowSec
- `subtitle.ass` con tiempos globales (no comienzan en 0 para cada escena)
- `video.mp4` con audio no truncado en escenas multi-segmento
- `render.durationSeconds` = max(endSec) del renderTimeline
