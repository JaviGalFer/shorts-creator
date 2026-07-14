# Sesion: Phase B Corrections — Per-scene Temporal Contract

**Timestamp:** 2026-07-11T20:20:00Z  
**Change:** `stabilize-visual-v2-runtime-contracts`  
**OpenSpec:** `openspec/changes/stabilize-visual-v2-runtime-contracts/`  
**Modelo:** DeepSeek V4 Pro  
**Modo:** Build (correcciones)

## 1. Perdida de durationSec detectada

`prepare_job.py` reemplazaba `data["audio"]` por un objeto nuevo:

```python
data['audio'] = {
    'provider': 'edge-tts',
    'continuous': False,
    'scenes': audio_entries,
}
```

Este nuevo objeto no contenia `durationSec` ni `voice`, perdiendo los datos persistidos por `generate_audio.py`.

## 2. Causa en prepare_job

El codigo solo actualizaba `path` y `exists` en las entradas de `audio_entries`, pero luego reemplazaba todo el diccionario `data["audio"]` en lugar de fusionar con el existente.

## 3. Correccion idempotente

Ahora `prepare_job` preserva el `audio_config` original y solo actualiza `path` y `exists`:

```python
preserved_audio = dict(audio_config)
preserved_scenes = preserved_audio.get('scenes', [])
# actualizar path/exists, preservar durationSec, voice, etc.
```

Dos ejecuciones consecutivas producen identico `durationSec`, `sceneWindowSec`, `renderTimeline` y `total_duration`.

## 4. Politica de fallo de ffprobe

`generate_audio.py` ahora:

- `durationSec = None` cuando el probe falla (nunca `0.0`)
- Si una escena tiene archivo MP3 pero el probe falla → `any_duration_missing = True`
- `any_duration_missing` → `REVIEW_REQUIRED` (exit code 1)
- Solo `all_ok and not any_duration_missing` → `AUDIO_READY`

Voice persistida en metadata per-scene: `audio.voice = "es-ES-AlvaroNeural"`.

## 5. Normalizacion de fracciones

`build_render_timeline` ahora:

1. Extrae `durationFraction` de cada segmento
2. Valida: numericas, finitas, > 0
3. Calcula suma total
4. Normaliza: `normalizedFraction = fraction / totalFraction`
5. Distribuye sobre `sceneWindowSec`
6. Ultimo segmento: `endSec = scene_offset + scene_duration` (cierra la ventana exactamente)

Rechaza: NaN, infinito, cero, negativo, string.

## 6. Deteccion de overlaps

`preflight_validate` ahora detecta ambos:

- `delta > 0.05` → `non-contiguous gap`
- `delta < -0.05` → `overlapping segments`
- `abs(delta) <= 0.05` → tolerado

Mensajes de error distintos para cada caso.

Preflight tambien resuelve audioPath desde las entries del renderTimeline (no solo hardcodeado `scenes/scene-XX.mp3`).

## 7. Helpers puros anadidos al render

`render_job.py` ahora exporta:

```python
build_per_scene_audio_filter(input_index, scene_number, scene_window_sec) -> str
# → f'[{input_index}:a]aresample=44100,asetpts=PTS-STARTPTS,apad,atrim=duration={scene_window_sec}[a{scene_number}]'

resolve_expected_duration(render_timeline, *, is_continuous_audio, continuous_duration_sec=None) -> float
# non-continuous: max(endSec), continuous: continuous_duration_sec
```

`main()` usa ambos helpers en lugar de construir cadenas inline.

## 8. Validacion de cues

`resolve_and_validate_global_cues(scenes, scene_offsets, scene_windows, tolerance=0.05)`:

- Valida start/end numericos, finitos, start >= 0, end > start
- Verifica cues dentro de scene window
- Orden global monotonicos
- Sin overlaps cross-scene
- No muta cues originales
- Continuous: retorna None (sin validacion)

`generate_ass_from_cues` acepta `scene_windows` y llama a `resolve_and_validate_global_cues` internamente.

## 9. Tests corregidos

- `test_render_job_scene_audio_contract.py`:
  - `test_window_10s_audio_6_9s_passes_mocked` — mockea via `__globals__` (resuelve contaminacion de `sys.modules`)
  - `test_window_5s_audio_6_9s_errors_mocked` — mismo patron
  - `test_overlapping_segments_error` — nuevo test de overlap

- `test_generate_audio_scene_duration_contract.py` (nuevo, 14 tests):
  - `_get_mp3_duration` local + Docker + fallback
  - Probe fallido → None (no 0.0)
  - Idempotencia de prepare_job
  - Bloqueo de durationSec invalido (0.0, None)

- `test_prepare_job_scene_temporal_contract.py` (extendido, +18 tests):
  - Normalizacion de fracciones (8 tests)
  - Cue validation (8 tests)
  - Last segment closure (2 tests)

- `tests/test_prepare_contract.py` y `tests/test_prepare_job_v2_assets_paths.py`:
  - Anadido `audio` block con `durationSec` a metadata de test

## 10. Archivos modificados

- `bin/generate_audio.py` — voice + REVIEW_REQUIRED en fallo
- `bin/prepare_job.py` — preservar audio, normalizar fracciones, validar cues
- `bin/render_job.py` — helpers puros, overlaps, audio path resolution

## 11. Resultado focalizado

```
tests/test_generate_audio_scene_duration_contract.py ... 14 passed
tests/test_prepare_job_scene_temporal_contract.py ....... 40 passed
tests/test_render_job_scene_audio_contract.py ........... 17 passed
Total nuevos/corregidos: 71 passed
```

## 12. Resultado full suite

```
980 passed, 16 failed
```

## 13. Comparacion con 947/16

| Fase | Passed | Failed | Delta |
|------|--------|--------|-------|
| Tras Phase B | 947 | 16 | — |
| **Tras correcciones** | **980** | **16** | **+33** |

+33 tests nuevos/corregidos. Los 16 fallos siguen siendo los preexistentes.

## 14. OpenSpec actualizado

- `tasks.md` — correcciones Phase B marcadas, bugs 7-12 anadidos
- `design.md` — ya actualizado con B.1-B.8
- `specs/per-scene-temporal-contract.md` — ya incluye REQ-B01 a REQ-B12

## 15. Confirmacion: no se ejecuto E2E

No se ejecuto E2E live. No se realizaron HTTP calls. No se descargaron imagenes.

## 16. Confirmacion: sin campos legacy

No se anadieron campos legacy.

## 17. Confirmacion: sin modos de dominio

No se anadieron modos historical, science, documentary, general, legacy.

## 18. Decision final sobre Phase B

Phase B lista para cerrar. Todos los contratos implementados, testeados y verificados. Contaminacion de `sys.modules` por `test_fetch_images_v2.py::test_no_v1_runtime_imports` resuelta usando `preflight_validate.__globals__` para el mock.

Recomendacion: ejecutar el E2E live y cerrar el change.
