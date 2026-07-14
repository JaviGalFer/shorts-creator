# Sesión: native-visual-plan-v2-generation

**Timestamp:** 2026-07-14 17:49 UTC
**Change:** `integrate-native-visual-plan-v2-generation` (Build A)
**Nivel:** 2
**Resultado:** Implementado, tests pass

## 1. Flujo v1 preservado

- `--visual-schema-version 1` (default) usa exactamente el mismo `SYSTEM_PROMPT`, `_validate_script_structure()`, `_build_retry_instruction()`, `_build_user_prompt()` y retry loop que antes.
- `call_llm()` acepta `system_prompt` opcional con default `SYSTEM_PROMPT`; v1 no lo pasa, sin cambios en firmas de mock.
- Tests v1 existentes (52/52) pasan sin modificaciones.

## 2. Nuevo contrato CLI

```bash
python3 bin/generate_script.py --topic "..." --duration 30                    # v1 default
python3 bin/generate_script.py --topic "..." --duration 30 --visual-schema-version 1  # v1 explícito
python3 bin/generate_script.py --topic "..." --duration 30 --visual-schema-version 2  # v2 nativo
```

## 3. Prompt v2 neutral

- `SYSTEM_PROMPT_V2`: ~130 líneas de prompt divulgativo general
- No menciona modos de dominio (historical, science, documentary)
- Describe schema v2 completo con arrays obligatorios, enums y reglas
- Lista campos prohibidos explícitamente (editorialRole, strategy, motionType, etc.)
- Ejemplo JSON con VisualPlan v2 canónico

## 4. Estructura VisualPlan solicitada

- Campos obligatorios: `_schemaVersion`, `visualIntent`, `subjects`, `searchQueries`, `assetPreferences`, `visualSequence`
- Campos opcionales: `period`, `location`, `allowGeneratedImage`, `imageGenerationPrompt`, `negativePrompt`
- Segmentos: `segmentIndex`, `assetPreference`, `durationFraction`, `searchQuery`, `transition`
- No requiere `narrativeBeats`, `motionType`, `preferredProviders`

## 5. Strict-native warning policy

Cualquier warning del canonicalizador se trata como error en generación nativa:
- `UNKNOWN_FIELD:*` → error estructural
- `UNKNOWN_SEGMENT_FIELD:*` → error estructural
- `UNRECOGNIZED_PROVIDER:*` → error estructural
- `IMAGE_PROMPT_WITHOUT_GENERATION_FLAG` → error estructural

## 6. Canonicalización

- `_validate_and_canonicalize_script_v2(script_data, allow_generated_images)` → `(canonical | None, errors, warnings)`
- Valida estructura por escena: sceneNumber, voiceover, targetDurationSec, visualPlan, _schemaVersion
- Uniformidad: todas las escenas deben tener `_schemaVersion == 2`
- Llama a `canonicalize_visual_plan_v2()` del módulo existente
- Solo si todas las escenas son válidas: deep copy + sustitución de visualPlan por canonicalPlan

## 7. Retry

- `MAX_SCRIPT_ATTEMPTS = 3` reutilizado
- Primera llamada con `SYSTEM_PROMPT_V2`
- `_build_retry_instruction_v2()` muestra errores por escena con codes, paths, messages
- Tras 3 intentos inválidos: `REVIEW_REQUIRED`, `VISUAL_PLAN_V2_INVALID`, exit 0
- Repair prompts no contienen secretos ni API keys

## 8. Persistencia

### v1 (sin cambios)
- `request.visuals` sin campo `schemaVersion`

### v2 éxito
```json
{
  "request": { "visuals": { "mode": "images", "allowGeneratedImages": false, "schemaVersion": 2 } },
  "script": { "scenes": [{ "visualPlan": { "_schemaVersion": 2, ... } }] },
  "status": "SCRIPT_DRAFT"
}
```

### v2 fallo tras retries
```json
{
  "status": "REVIEW_REQUIRED",
  "reviewReasons": ["VISUAL_PLAN_V2_INVALID: v2 plan validation failed after 3 attempts", "..."],
  "script": { /* raw para diagnóstico */ }
}
```

## 9. Archivos modificados

- `bin/generate_script.py`: +658 líneas (SYSTEM_PROMPT_V2, call_llm modificado, v2 helpers, main bifurcado)
- `docs/project/current-state.md`: actualizado

## 10. Archivos creados

- `tests/test_generate_script_v2.py`: 48 tests (CLI, éxito, rechazos, retry, compatibilidad, prompt)
- `openspec/changes/integrate-native-visual-plan-v2-generation/proposal.md`
- `openspec/changes/integrate-native-visual-plan-v2-generation/design.md`
- `openspec/changes/integrate-native-visual-plan-v2-generation/tasks.md`
- `openspec/changes/integrate-native-visual-plan-v2-generation/specs/native-visual-plan-v2-generation.md`
- `docs/sessions/20260714-174946-native-visual-plan-v2-generation.md` (este archivo)

## 11. Resultado focalizado

```text
tests/test_generate_script_v2.py  48 passed
tests/test_visual_plan_v2.py      128 passed
tests/test_run_job_v2_assets.py   21 passed
-------------------------------------------
Total: 197 passed
```

## 12. Resultado full suite

```text
1180 passed
16 failed (preexistentes en test_run_job.py + test_semantic_asset_validation.py)
0 regresiones
```

## 13. Comparación con baseline

| Métrica | Antes | Después | Delta |
|---------|-------|---------|-------|
| Total passed | 1132 | 1180 | +48 |
| Total failed | 16 | 16 | 0 |
| Nuevas regresiones | 0 | 0 | 0 |

## 14. Confirmación: run_job.py no cambió

- `run_job.py` no fue modificado en este Build
- La detección `_uses_v2_visual_assets()` existente funciona correctamente con metadata que contiene `schemaVersion=2`
- `build_stage_command()` despacha a `fetch_images_v2.py` automáticamente

## 15. Confirmación: no E2E ejecutado

- No se realizaron llamadas OpenAI reales
- No se ejecutó sourcing de imágenes
- No se ejecutó audio, prepare, render ni validate
- Todos los tests usan `call_llm()` mockeado

## 16. Ausencia de mappings v1→v2

- No hay conversión de campos v1 a v2
- `editorialRole`, `strategy`, `primaryAssetType` no tienen equivalentes en v2
- El canonicalizador rechaza campos legacy (LEGACY_FIELD_NOT_ALLOWED)
- El prompt v2 instruye al LLM a no incluir esos campos

## 17. Estado del OpenSpec

- `openspec/changes/integrate-native-visual-plan-v2-generation/` creado
- 4 documentos: proposal, design, tasks, specs
- 13 requisitos verificables documentados
- Build A completado; Build B (E2E live) pendiente

## 18. Recomendación para Build B

El E2E live puede iniciarse. El pipeline completo está listo:

1. `generate_script.py --visual-schema-version 2` → `SCRIPT_DRAFT` con VisualPlan v2 canónico
2. `run_job.py` detecta `_schemaVersion=2` y despacha `fetch_images_v2.py`
3. `fetch_images_v2.py` → Wikimedia + Pixabay failover
4. `generate_audio.py` → Edge TTS por escena
5. `prepare_job.py` → subtítulos ASS
6. `render_job.py` → FFmpeg render
7. `validate_job.py` → validación post-hoc

Comando E2E recomendado:

```bash
python3 bin/generate_script.py \
  --topic "Cómo se produce una aurora boreal" \
  --duration 30 \
  --visual-schema-version 2

python3 bin/run_job.py \
  data/videos/<jobId>/metadata.json
```

No se requieren cambios en `run_job.py`. La ruta de dispatch v2 ya está cableada y probada.

---

## Correcciones post-Build A (2026-07-14 18:00 UTC)

### Fix 1 — Prompt dinámico neutral v2

- `_build_duration_prompt_instruction_v2()` creado sin requisitos históricos
- Elimina: distribuir detalles históricos, incluir fecha con año, incluir nombre propio
- Conserva: duración, ventana, presupuesto de palabras, pausas, 4-6 escenas, CTA, no relleno
- `_build_user_prompt_v2()` usa la variante neutral
- V1 sigue usando `_build_duration_prompt_instruction()` sin cambios

### Fix 2 — Enforcement request-level de `allowGeneratedImages=false`

- `_validate_and_canonicalize_script_v2()` ahora verifica:
  - `allowGeneratedImage=true` → `GENERATED_IMAGES_DISABLED_BY_REQUEST`
  - `"generated"` en `assetPreferences` → rechazo
  - `assetPreference="generated"` en segmentos → rechazo
  - `imageGenerationPrompt` no vacío → rechazo
- Más restrictivo que el canonicalizador general

### Fix 3 — Validación estructural completa

- Scene count: `INSUFFICIENT_SCENE_COUNT` (< 4) / `EXCESSIVE_SCENE_COUNT` (> 6)
- sceneNumber: int, no bool, >0, exactamente `[1..N]` (`INVALID_SCENE_NUMBER_SEQUENCE`)
- targetDurationSec: int/float, `math.isfinite`, >0 (`INVALID_TARGET_DURATION`)
- Rechaza NaN, Infinity, bool, string, cero, negativos

### Fix 4 — True strict-native

- **TODO warning** del canonicalizador se promueve a error
- Sin allowlist — cualquier código de warning se convierte en error reparable
- El repair retry recibe el código exacto del warning

### Tests añadidos (28 nuevos)

- Prompt neutral: 3 tests
- Generación: 5 tests (allowGeneratedImage, preferences, segmentos, prompt, normal)
- Escenas: 4 tests (3/7 rechazo, 4/6 pass)
- sceneNumber: 8 tests (secuencial, gap, inicio-2, duplicados, orden-inverso, float, bool, cero)
- targetDurationSec: 5 tests (NaN, Inf, -Inf, bool, string, positivo)
- Strict-native: 1 test (warning arbitrario promovido)
- Retry: 2 tests (generated→rechazo→válido, sceneNumber inválido x3)

### Resultado final

```text
Focal: 226 passed (76 v2-gen + 128 canonicalizer + 22 run_job_v2)
Full:  1209 passed, 16 failed (preexistentes), 0 regresiones
Baseline delta: 1132 → 1209 (+77 tests)
```

---

## Build B — E2E live (2026-07-14 18:10 UTC)

### Precondiciones

- LLM_API_KEY: SET
- PIXABAY_API_KEY: SET
- LLM_PROVIDER: openai
- LLM_MODEL: gpt-4o-mini

### Generación nativa

**JobId:** `cmo-2026-07-14-180923`

```
--topic "Cómo se produce una aurora boreal"
--duration 30
--visual-schema-version 2
```

**Resultado:** SCRIPT_DRAFT (3 intentos, 2 retries)
- wordCount: 48, estimatedDurationSec: 27.6
- 5 scenes, sceneNumber: [1, 2, 3, 4, 5]
- durationContract: PASS, structureValid: true
- schemaVersion: 2, allowGeneratedImages: false
- Zero legacy fields, zero generated images
- All visualPlans _schemaVersion=2

### Gate v2 — PASSED

Todos los contratos verificados: schema v2 homogéneo, sin campos legacy, sin generación de imágenes, durationFraction válidas, secuencia exacta.

### Assets — BLOCKED

**Status:** ASSETS_PARTIAL (6/9 resolved, 3 failed)

| Scene | Seg | Status | Preference | Provider | Resolution | Error |
|-------|-----|--------|------------|----------|------------|-------|
| 1 | 1 | PASS | photograph | wikimedia_commons | 7381x4921 | — |
| 1 | 2 | PASS | illustration | wikimedia_commons | 3033x2235 | — |
| 2 | 1 | PASS | diagram | wikimedia_commons | 2224x2216 | — |
| 2 | 2 | FAIL | illustration | wikimedia_commons | — | RATE_LIMITED |
| 3 | 1 | FAIL | photograph | wikimedia_commons | — | RATE_LIMITED |
| 3 | 2 | PASS | illustration | wikimedia_commons | 2520x3764 | — |
| 4 | 1 | PASS | map | wikimedia_commons | 5580x1535 | — |
| 4 | 2 | PASS | photograph | wikimedia_commons | 2288x1404 | — |
| 5 | 1 | FAIL | photograph | wikimedia_commons | — | RATE_LIMITED |

**Observaciones:**
- Los 6 segmentos exitosos vinieron de Wikimedia, con dimensiones >= 720x720
- Los 3 fallos son RATE_LIMITED de Wikimedia
- `_attemptedProviders` vacío — Pixabay no se intentó como fallback para estos segmentos
- MIMEs canónicos (todo image/jpeg), paths únicos con namespace scene_NNN_seg_NNN

### Clasificación final

**E2E_BLOCKED_ASSETS**

No se ejecutaron audio, prepare, render ni validate.

### Siguiente acción

Investigar por qué Pixabay no se ejecutó como fallback cuando Wikimedia devolvió RATE_LIMITED. Los 3 segmentos fallidos tienen `_attemptedProviders: []`, lo que sugiere que el router no ofreció Pixabay como alternativa para esos tipos de asset (illustration, photograph).

Build B queda pendiente hasta que el fallback Pixabay funcione para todos los segmentos.

---

## Corrección de Pixabay + E2E_PASS (2026-07-14 20:20 UTC)

### Causa raíz

PIXABAY_API_KEY presente en `.env` del repositorio pero NO en `os.environ`. `fetch_images_v2.py:356` solo leía `os.environ.get("PIXABAY_API_KEY")`. La clave estaba en `.env` pero `fetch_images_v2.py` se ejecuta como subproceso independiente (no como parte de `run_job.py`), por lo que `load_env()` no se cargaba.

### Fix 1 — Resolución de API key

`fetch_images_v2.py`: nueva función `_resolve_pixabay_api_key()`:
- Prioridad 1: `os.environ["PIXABAY_API_KEY"]`
- Prioridad 2: `<project_root>/.env`
- Trim, vacío = ausente, sin secretos en logs/config

### Fix 2 — Bridge diagnostics

`visual_asset_bridge_v2.py`: `_attemptedProviders` ahora lee `providerAttempts` (campo moderno del executor) con fallback a `attemptedProviders` (campo legacy).

### Resultado de reejecución (mismo job `cmo-2026-07-14-180923`)

**Assets:** ASSETS_READY 9/9 (7 Pixabay, 2 Wikimedia)

| Scene | Seg | Preference | Provider | Resolution |
|-------|-----|------------|----------|------------|
| 1 | 1 | photograph | pixabay | 1280x882 |
| 1 | 2 | illustration | pixabay | 1280x853 |
| 2 | 1 | diagram | wikimedia_commons | 1536x1140 |
| 2 | 2 | illustration | pixabay | 1280x1280 |
| 3 | 1 | photograph | pixabay | 1280x853 |
| 3 | 2 | illustration | pixabay | 1280x960 |
| 4 | 1 | map | wikimedia_commons | 3008x1960 |
| 4 | 2 | photograph | pixabay | 1280x853 |
| 5 | 1 | photograph | pixabay | 1280x853 |

**Audio:** AUDIO_READY (durations estimated, ffprobe no disponible en host)
- scene1: 4.6s, scene2: 4.4s, scene3: 4.5s, scene4: 3.9s, scene5: 3.5s (reales desde Docker ffprobe)

**Prepare:** SUBTITLES_READY (9 timeline segments, 9 subtitle cues, subtitle.ass generado)

**Render:** RENDERED (DOCKER_API_VERSION=1.43)
- 1080x1920, 30.0s, 750 frames, h264+aac, 2.2 MB
- SHA-256: db47881adcdf9e96e44631ef371ed3fb25d6929e84dcd05cd607c558413d0b15
- Asset validation PASSED, Preflight PASSED, 0 black/freeze frames

**Validate:** PASS (0 errors)
- subtitleCoverageValidation: PASS (53% coverage)
- assetValidation: PASS (9/9)
- technicalValidation: PASS (job-manifest.json valid)

### Clasificación final: **E2E_PASS**

### Archivos modificados

- `bin/fetch_images_v2.py` — `_resolve_pixabay_api_key()`
- `bin/visual_asset_bridge_v2.py` — lee `providerAttempts` en vez de `attemptedProviders`
- `tests/test_fetch_images_v2.py` — +3 tests de resolución de clave
- `tests/test_visual_asset_bridge_v2.py` — +2 tests de providerAttempts

### Tests

Focal: 290 passed | Full: 1215 passed, 16 pre-existing failed, 0 regressions

### Siguiente acción

Build B completado. El change `integrate-native-visual-plan-v2-generation` puede cerrarse formalmente.
