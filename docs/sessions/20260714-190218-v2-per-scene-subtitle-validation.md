# Sesión 20260714-190218 — Validación per-scene para audio no continuo

## Resumen

Corrección de falsos positivos en `validate_job.py` y `render_job.py` para jobs con audio no continuo. Los cues de subtítulos son locales a cada escena pero el validator legacy los concatenaba como si fueran globales, generando overlaps falsos.

## Causa raíz

`validate_job.py._check_subtitle_cues()` y `_check_subtitle_alignment()` concatenaban todos los cues locales y los comparaban directamente sin aplicar offsets desde `renderTimeline`. Para audio no continuo, cada escena tiene sus propios cues locales que empiezan en ~0.1s.

`render_job.py` llamaba a `run_coverage_validation()` con `sceneTimings` vacío, `narrationUnits` vacío y `audio.durationSec=0`, generando coverage 0% y errores de cross-scene tokens.

## Solución

Módulo compartido `bin/subtitle_validation_context.py` con:

- **Detección de modo**: `audio.continuous=True` → legacy `coverage_validation`. `False` → per-scene.
- **Contexto por escena**: deriva `sceneStartSec`/`sceneEndSec` desde `renderTimeline`, `actualAudioDurationSec` desde `audio.scenes[]`.
- **Validación de cues locales**: monotonic, no overlaps, no excede audio real.
- **Cues globales**: `globalStart = sceneStart + localStart`, sin mutación de metadata.
- **Validación ASS**: parsea `Dialogue:` del archivo real, compara tiempos y texto normalizado.
- **Quality gate**: `subtitleCoverageValidation = PASS` para per-scene correcto.

## Archivos

| Archivo | Acción |
|---------|--------|
| `bin/subtitle_validation_context.py` | Creado — módulo compartido |
| `bin/validate_job.py` | Modificado — branching per-scene vs legacy |
| `bin/render_job.py` | Modificado — branching en coverage validation + skip-render |
| `tests/test_subtitle_validation_context.py` | Creado — 29 tests |
| `docs/project/current-state.md` | Actualizado |
| `docs/sessions/20260714-190218-v2-per-scene-subtitle-validation.md` | Bitácora (este archivo) |

## Contrato compartido

### Funciones de `subtitle_validation_context.py`

```python
build_validation_context(metadata, video_dir=None) -> dict
```

Retorna:
```json
{
  "mode": "continuous" | "per_scene",
  "status": "PASS" | "FAIL" | "REVIEW_REQUIRED",
  "totalCues": 8,
  "errors": [],
  "warnings": [],
  "globalCues": [...],  // solo per_scene
  "coveragePercent": 0.0  // solo continuous
}
```

### Cálculo de offsets

```text
sceneStartSec = min(renderTimeline[scene].startSec)
sceneEndSec = max(renderTimeline[scene].endSec)
globalStartSec = sceneStartSec + localStartSec
globalEndSec = sceneStartSec + localEndSec
```

Para el job E2E:
```text
Scene 1: 0.100 → 2.612, 3.475 → 5.700
Scene 2: 8.100 → 9.450, 9.462 → 11.487, 11.500 → 14.062
Scene 3: 18.100 → 20.087, 20.100 → 22.175, 23.037 → 24.675
```

### Validación ASS

- Cuenta líneas `Dialogue:` y compara con cues esperados.
- Tiempos ASS deben coincidir con cues globales dentro de 0.10s.
- Texto normalizado debe coincidir.
- Escenas 2+ no deben empezar cerca de cero.

## Resultados

### Tests

```text
1113 passed, 16 failed (preexistentes), 0 regresiones nuevas
```

Los 16 fallos son preexistentes en `test_run_job.py` y `test_semantic_asset_validation.py`.

### Revalidación E2E

```text
subtitleCoverageValidation: PASS
assetValidation: PASS
technicalValidation: PASS
qualityGate: PASS
coverageStatus: PASS
```

`video.mp4` no fue regenerado (MD5 sin cambios).

## Siguiente acción

Corregir `MAX_SEGMENT_DURATION=8.0` en `validate_job.py._check_durations()` para que no falsee errores en escenas expandidas con múltiples beats.
