# Propuesta: integrate-native-visual-plan-v2-generation

## Problema actual

El runtime Visual v2 está plenamente operativo:

- `fetch_images_v2.py` con failover Wikimedia + Pixabay
- Audio, prepare, render, validate compatibles con v2
- `run_job.py` detecta `_schemaVersion == 2` y despacha a `fetch_images_v2.py`

Sin embargo, `generate_script.py` solo genera VisualPlan v1. Para ejecutar el pipeline v2 de principio a fin, es necesario generar el guion externamente con VisualPlan v2 ya incrustado.

## Solución implementada

Generación nativa de VisualPlan v2 en `generate_script.py` mediante:

1. Flag `--visual-schema-version {1,2}` con default 1
2. Prompt `SYSTEM_PROMPT_V2` neutro (divulgativo general)
3. Validación y canonicalización usando la API pública de `visual_plan_v2.py`
4. Política strict-native: warnings del canonicalizador tratados como errores reparables
5. Retry estructural con `MAX_SCRIPT_ATTEMPTS = 3`
6. Persistencia de `request.visuals.schemaVersion = 2`
7. Restricción de imágenes generadas (`allowGeneratedImages=false`)
8. Dispatch automático existente en `run_job.py` sin cambios

## Correcciones aplicadas durante el change

- **Fix 1:** Prompt dinámico neutral separado v1/v2 (`_build_duration_prompt_instruction_v2`)
- **Fix 2:** Enforcement request-level de `allowGeneratedImages=false` (`GENERATED_IMAGES_DISABLED_BY_REQUEST`)
- **Fix 3:** Validación estructural (4-6 escenas, sceneNumber secuencial, targetDurationSec finito)
- **Fix 4:** True strict-native — TODOS los warnings del canonicalizador tratados como errores
- **Fix 5:** PIXABAY_API_KEY — resolución con fallback `os.environ` → `.env`, sin persistencia de secretos
- **Fix 6:** Bridge diagnostics — `providerAttempts` en vez de `attemptedProviders` (legacy)

## Alcance

- `bin/generate_script.py`: CLI, prompt v2, validación, canonicalización, retry, persistencia
- `bin/fetch_images_v2.py`: `_resolve_pixabay_api_key()`, bridge diagnostics
- `tests/test_generate_script_v2.py`: tests mockeados (76 tests)
- Documentación OpenSpec y sesión

## Resultado final

### Build A — Generación nativa

- Suite focal: 226 passed
- Suite completa: 1209 passed, 16 failed (preexistentes), 0 regresiones

### Corrección de Pixabay + Bridge diagnostics

- +5 tests (3 key resolution, 2 bridge diagnostics)
- Suite focal: 290 passed
- Suite completa: 1215 passed, 16 failed (preexistentes), 0 regresiones

### Build B — E2E live

- **Job:** `cmo-2026-07-14-180923`
- Generación: SCRIPT_DRAFT, 3 intentos internos, 5 escenas, 9 segmentos, 48 palabras, 27.6 s
- VisualPlan v2 homogéneo, 0 campos legacy
- fetch_images_v2 → ASSETS_READY 9/9 (7 Pixabay, 2 Wikimedia)
- generate_audio → AUDIO_READY
- prepare_job → SUBTITLES_READY
- render_job (Docker) → RENDERED (1080x1920, 30.0s, 2.2MB)
- validate_job → PASS, 0 errors
- Gates: subtitleCoverageValidation PASS, assetValidation PASS, technicalValidation PASS, qualityGate PASS
- E2E_PASS

### Primer intento bloqueado (documentado como evidencia)

- E2E `cmo-2026-07-14-180923` intento inicial: ASSETS_PARTIAL 6/9 — 3 RATE_LIMITED de Wikimedia
- **Causa raíz:** PIXABAY_API_KEY en `.env` pero no en `os.environ`
- **Corrección:** `_resolve_pixabay_api_key()` con fallback de `os.environ` a `.env`

### Baseline final

- 1215 passed, 16 failed (preexistentes en `test_run_job.py` + `test_semantic_asset_validation.py`), 0 regresiones

## Criterios de éxito (todos cumplidos)

1. `--visual-schema-version 2` produce VisualPlan v2 canónico ✓
2. Default y `--visual-schema-version 1` preservan v1 exactamente ✓
3. Warnings del canonicalizador tratados como errores en generación nativa ✓
4. Retry estructural funcional (max 3 intentos) ✓
5. `REVIEW_REQUIRED` con `VISUAL_PLAN_V2_INVALID` tras agotar retries ✓
6. `run_job.py` sin cambios ✓
7. Restricción de imágenes generadas activa ✓
8. PIXABAY_API_KEY resuelta con fallback `.env` ✓
9. E2E final completo: ASSETS_READY 9/9, RENDERED, PASS ✓
10. Baseline: 1215 passed, 16 failed, 0 regresiones ✓

## Deuda fuera de alcance

- Calidad y relevancia semántica de assets
- Mejora de prompts de búsqueda (`improve-visual-query-relevance-v2`)
- Mejora de voz Edge TTS
- Integración con n8n
- Gestión de ffprobe en host
