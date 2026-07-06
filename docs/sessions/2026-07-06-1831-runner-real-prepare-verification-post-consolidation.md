# Sesión: Runner real prepare verification post-consolidation

- Fecha: 2026-07-06
- Objetivo: Primera verificación real del runner tras integrar validador compartido, fallback restringido, clasificación de fallos y bookkeeping anti-repetición de fallback.
- Cambio OpenSpec: `improve-historical-visual-pipeline` (Phase 23 verification)
- Comando: `python3 bin/run_job.py --topic "La caída del Muro de Berlín" --duration 30 --duration-max 35 --stop-after prepare --verbose`

## Precondiciones

| Prerrequisito | Estado |
|---------------|--------|
| git clean (solo archivos modificados intencionalmente) | OK |
| Scripts importables (`generate_script`, `fetch_images`, `generate_audio`, `prepare_job`, `run_job`) | OK |
| Edge TTS (`edge_tts`) | OK |
| `LLM_API_KEY` en `.env` | PRESENT |
| `LLM_PROVIDER` en `.env` | PRESENT |
| `PEXELS_API_KEY` en `.env` | PRESENT |
| `PIXABAY_API_KEY` en `.env` | PRESENT |
| `.env` sin modificar | OK |

## Resultado: Bloqueo en script stage

**Job ID:** `la-2026-07-06-183114`
**Job path:** `data/videos/la-2026-07-06-183114`

### Runner JSON final

```json
{
  "jobId": "la-2026-07-06-183114",
  "jobPath": "/home/javi/projects/shorts-creator/data/videos/la-2026-07-06-183114",
  "status": "REVIEW_REQUIRED",
  "lastCompletedStage": "script",
  "outputVideoPath": null,
  "validationStatus": null
}
```

### Orchestration statusHistory

| Stage | Status |
|-------|--------|
| script | REVIEW_REQUIRED |

Runner stopped correctly — no assets, audio, or prepare executed.

### Duration contract

| Campo | Valor |
|-------|-------|
| `totalWordCount` | None (script no válido) |
| `estimatedDurationSec` | 4.4 |
| `minimumWords` | 50 |
| `preferredWords` | 55 |
| `maximumWords` | 64 |
| `status` | FAIL |
| `sceneCount` | 1 |

### Retry history

| Retry | Reason | Words | Min | Pref | Max | Est. Duration | Instruction |
|-------|--------|-------|-----|------|-----|---------------|-------------|
| 0 | `above_maximum_words` | 70 | 47 | 52 | 61 | 39.6s | `reduce_content` |
| 1 | `below_minimum_words` | 8 | 50 | 55 | 64 | 4.4s | `expand_factual_content` |

Retry 0: LLM generó 70 palabras (por encima del máximo de 61 del presupuesto provisional con 5 escenas). Recibió instrucción de reducir. Retry 1: LLM sobre-redujo a 8 palabras con 1 sola escena (scene 5: `consequence_or_legacy`, `legacy_or_commemoration`). Recibió instrucción de expandir pero no se ejecutó un tercer intento — el bucle de retry se agotó en 2 intentos.

### Estado final del script

- `status`: `REVIEW_REQUIRED`
- Scenes generadas: 1 (scene 5, CTA genérica, 8 palabras)
- El guion no cumple el contrato de duración.

### Fallo no relacionado con el validador/fallback

El bloqueo ocurrió en el script stage, antes de que `fetch_images.py` se ejecutara. Las nuevas integraciones de `_validate_segment_for_role`, `_try_hard_role_fallback`, `failure_classification` y `accepted_candidate` no fueron ejercitadas en este job.

## No verificado

- Runner a través de prepare (no ejecutado).
- Asset validation, fallback, reuse en producción.
- Audio, prepare, render, validate stages.
- Ningún stage posterior a script fue ejecutado.

## Archivos

- Job: `data/videos/la-2026-07-06-183114/`
- Sin archivos modificados (solo creación de metadata.json por `generate_script.py` y orchestration por `run_job.py`).
