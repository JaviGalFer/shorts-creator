# Specs: per-scene-temporal-contract

## REQ-B01: audio.scenes[].durationSec

El sistema DEBE persistir la duración real del audio por escena en `audio.scenes[].durationSec`.

- La duración DEBE proceder del archivo MP3 real, no de estimaciones
- DEBE usar `_get_mp3_duration()` (ffprobe local o Docker) en `generate_audio.py`
- El valor DEBE ser un número finito y positivo, o `null` si no se puede obtener
- Si el probe falla:
  - `durationSec = null`
  - `status = REVIEW_REQUIRED`
  - `reviewReasons` incluye `AUDIO_DURATION_MISSING`
  - exit code no cero
  - el metadata DEBE persistirse antes de devolver
- Audio continuo: NO DEBE modificar el contrato existente
- `main_per_scene` DEBE escribir metadata.json exactamente una vez al final, independientemente del exit code

## REQ-B02: sceneWindowSec = max(target, audio)

El sistema DEBE definir la ventana visual canónica de una escena como `max(targetDurationSec, actualAudioDurationSec)`.

- `resolve_scene_window_duration(target, audio)` DEBE ser pura y testeable
- DEBE rechazar: NaN, infinito, booleanos, strings, negativos, None
- Ambos valores deben ser finitos y positivos
- target 8.0, audio 6.576 → 8.0
- target 5.0, audio 6.936 → 6.936
- target 12.0, audio 7.536 → 12.0
- Sin redondeo agresivo (round a 3 decimales)

## REQ-B03: Distribución de durationFraction sobre sceneWindowSec

Para audio no continuo, `build_render_timeline()` DEBE:

- Conservar `durationFraction` de cada segmento
- Distribuir los segmentos de cada escena sobre `sceneWindowSec`
- La suma de duraciones DEBE ser igual a `sceneWindowSec` (tolerancia 0.1s)
- `startSec`, `endSec`, `durationSec` DEBEN ser monotónicos dentro de cada escena
- Sin huecos ni solapes entre segmentos de la misma escena
- `startSec` de la siguiente escena DEBE coincidir con el `endSec` de la anterior
- No cambiar paths de assets

## REQ-B04: Cues locales convertidos a globales mediante offsets del timeline

Para audio no continuo, los subtítulos DEBEN tener offsets globales:

- Los `subtitleTiming.cues` son scene-local (empiezan en 0)
- El offset global DEBE proceder del `renderTimeline` ya resuelto
- Offset de cada escena = `min(startSec)` de sus entries en renderTimeline
- `generate_ass_from_cues()` DEBE aceptar `scene_offsets: dict[int, float] | None` y `scene_windows: dict[int, tuple[float, float]] | None`
- Con ambos → valida y escribe desde `resolve_and_validate_global_cues()`
- Sin windows pero con offsets → escribe con offsets sin validación (backward compat)
- Sin offsets → comportamiento original (continuous)
- Los cues originales NO deben mutarse
- Si falta offset para una escena con cues → ValueError
- Escena sin cues → no verifica offset

## REQ-B05: Audio padded hasta la ventana de escena

En modo no continuo, la cadena FFmpeg del audio DEBE:

1. Preservar el MP3 completo
2. Añadir silencio al final cuando sea más corto que la ventana
3. Producir exactamente `sceneWindowSec`
4. NO usar la duración del primer segmento para recortar el audio completo
5. NO adelantar el audio de la escena siguiente

Cadena equivalente:

```text
aresample=44100,asetpts=PTS-STARTPTS,apad,atrim=duration={sceneWindowSec}
```

## REQ-B06: Audio nunca truncado en metadata válido

Antes del render, el preflight DEBE garantizar `actualAudioDurationSec <= sceneWindowSec + tolerance`.

- `atrim=duration=sceneWindowSec` no corta narración si el metadata está correctamente preparado
- Cuando el audio es más largo que `targetDurationSec`, la ventana se amplía (REQ-B02)
- `atrim` es una protección final para duración exacta, no un recorte funcional

## REQ-B07: Preflight agregado por escena

`preflight_validate()` DEBE validar audio no continuo por escena, no por entry individual:

- Agrupar entries por `sceneNumber`
- Para cada escena validar:
  - Segmentos contiguos (gap ≤ 0.05s) y no solapados (overlap ≤ 0.05s)
  - Audio paths consistentes dentro de la escena
  - `audio_duration <= scene_window + 0.10s` (audio > ventana → error)
  - Ventana visual > audio → válido (padding añadido)
- Audio continuo: comportamiento anterior preservado
- `render_job.main()` DEBE resolver `expected_duration` antes del preflight y pasarlo como `expected_total`
- Para audio no continuo: `expected_total = max(renderTimeline.endSec)`
- La suma original de `targetDurationSec` NO es canonical después de ampliar escenas

## REQ-B08: Continuous audio sin regresiones

El audio continuo DEBE conservar su comportamiento sin cambios:

- Sin doble offset
- Sin padding por escena
- Sin división por sceneNumber
- Cues ya globales (sin offsets adicionales)
- Único stream de audio sin cambios
- Duración canonical sin alteración

## REQ-B09: V1 preservado

El pipeline V1 DEBE conservar su comportamiento:

- Campos legacy sin cambios
- Sourcing v1 sin cambios
- Asset validation v1 sin cambios
- Roles editoriales sin cambios
- Lógica semántica histórica sin cambios
- Parámetros nuevos con defaults compatibles

## REQ-B10: expected_duration desde timeline final

La duración esperada del render DEBE proceder del timeline global resuelto:

- No continuo: `max(renderTimeline.endSec)`
- No usar: suma de MP3 sin padding, primer segmento, target total original

## REQ-B11: Sin modos de dominio

No se añaden modos de dominio (historical, science, documentary, legacy, etc.).

## REQ-B12: Sin campos legacy

No se añaden campos legacy al metadata.

## REQ-B13: Orden monotónico de cues

Para audio no continuo, `resolve_and_validate_global_cues()` DEBE:

- Recorrer escenas y cues en su orden canonical (NO reordenar)
- Validar que cada cue global comience después del anterior (dentro de tolerancia)
- Si un cue retrocede temporalmente → ValueError explícito
- Detectar overlap cross-scene → ValueError
- Permitir pausas entre cues
- No mutar los cues originales
- `generate_ass_from_cues` DEBE escribir las cues desde la lista validada (no recalcular offsets)

Para audio continuo (scene_offsets=None): conserva comportamiento anterior.

## REQ-B14: Manifest con audioDurationSec real

`resolve_manifest_scene_audio_duration(audio_config, scene_number)` DEBE:

- Buscar en `audio.scenes[]` por sceneNumber
- Devolver duración finita y positiva, o None
- No usar ffprobe (fuente: metadata ya validado)
- No usar targetDurationSec como fallback
- No inventar 0.0

`job-manifest.scenes[].audioDurationSec` DEBE proceder de `audio.scenes[].durationSec`.

Si falta una duración válida: `audioDurationSec: null` (nunca 0.0).
