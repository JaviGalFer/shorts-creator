# Especificación: native-visual-plan-v2-generation

## Requisitos verificables

### R1: Selección explícita de schema

- `--visual-schema-version 1` usa `SYSTEM_PROMPT` y flujo v1
- `--visual-schema-version 2` usa `SYSTEM_PROMPT_V2` y flujo v2
- Default (ausente) equivale a `1`

### R2: Prompt v2 neutral

- `SYSTEM_PROMPT_V2` describe un generador divulgativo general
- No contiene modos de dominio (`historical`, `science`, `documentary`)
- No requiere `editorialRole`, `visualTemporalIntent`, `strategy`
- Requiere `_schemaVersion: 2`, `visualIntent`, `subjects`, `searchQueries`, `assetPreferences`, `visualSequence`

### R3: Generación directa de VisualPlan v2

- El LLM recibe instrucciones de generar VisualPlan v2 nativo
- No hay mapping v1 → v2
- Los campos prohibidos se listan explícitamente en el prompt

### R4: Canonicalización antes de persistir

- Cada `visualPlan` raw pasa por `canonicalize_visual_plan_v2()`
- Solo si todas las escenas validan se sustituye por `canonicalPlan`
- No se muta parcialmente el script durante la validación

### R5: Strict-native warning policy (true)

- **TODO warning** del canonicalizador → error estructural reparable
- No hay allowlist: `UNKNOWN_FIELD:*`, `UNKNOWN_SEGMENT_FIELD:*`, `UNRECOGNIZED_PROVIDER:*`, `IMAGE_PROMPT_WITHOUT_GENERATION_FLAG` y cualquier otro warning
- El repair retry recibe el código exacto del warning

### R6: Uniformidad de escenas y validación estructural

- 4-6 escenas (`INSUFFICIENT_SCENE_COUNT` / `EXCESSIVE_SCENE_COUNT`)
- sceneNumber: int, no bool, >0, exactamente `[1..N]` (`INVALID_SCENE_NUMBER_SEQUENCE`)
- targetDurationSec: int/float, `math.isfinite`, >0 (`INVALID_TARGET_DURATION`)
- voiceover no vacío, visualPlan presente y dict
- Todas las escenas deben tener `_schemaVersion == 2`

### R7: Retry acotado

- `MAX_SCRIPT_ATTEMPTS = 3`
- Repair instruction incluye errores por escena
- No incluye secretos ni API keys
- Tras 3 intentos: `REVIEW_REQUIRED`, `VISUAL_PLAN_V2_INVALID`

### R8: Persistencia de schemaVersion

- v2 éxito: `request.visuals.schemaVersion = 2`
- v1: sin campo `schemaVersion`

### R9: Compatibilidad v1

- V1 sin cambios en prompt, validación, retry, persistencia
- `call_llm()` con parámetro opcional, v1 no lo pasa
- Tests v1 pasan sin modificaciones

### R10: run_job sin cambios

- `run_job.py` no modificado
- Dispatch existente detecta `_schemaVersion == 2` automáticamente

### R11: Restricción de imágenes generadas (request-level enforcement)

- `allowGeneratedImages = false` en request → error `GENERATED_IMAGES_DISABLED_BY_REQUEST`
- Rechaza: `allowGeneratedImage=true`, `"generated"` en `assetPreferences`, `assetPreference="generated"` en segmentos, `imageGenerationPrompt` no nulo/no vacío
- Más restrictivo que el schema general del canonicalizador

### R12: Campos prohibidos en output nativo

- `editorialRole`, `strategy`, `primaryAssetType`, `secondaryAssetType`, `visualTemporalIntent`, `style`, `mood`, `licenseRequired`, `visualImportance`, `preferredSources`, `entities`, `visualPrompt`, `imagePrompt`, `assetType`, `motionType`, `focalRegion`, `cropMode`, `overlayText`, `editorialReason`, `score`, `scoreReasons`, `provider`, `sourceUrl`, `fileUrl`, `path`, `asset_namespace`, `sceneNumber`
- Ninguno de estos campos aparece en un VisualPlan v2 canónico

### R13: E2E final completado

- Job `cmo-2026-07-14-180923`: generación nativa v2, SCRIPT_DRAFT, 3 intentos, 5 escenas, 9 segmentos
- fetch_images_v2 → ASSETS_READY 9/9 (7 Pixabay, 2 Wikimedia)
- generate_audio → AUDIO_READY, prepare_job → SUBTITLES_READY
- render_job (Docker) → RENDERED: 1080x1920, 30.0s, H.264 + AAC, 2.2MB
- SHA-256: `db47881adcdf9e96e44631ef371ed3fb25d6929e84dcd05cd607c558413d0b15`
- validate_job → PASS, 0 errors, todos los gates PASS
- E2E_PASS

### R14: Resolución de PIXABAY_API_KEY

- `_resolve_pixabay_api_key()`: `os.environ` preferente, fallback a `.env`
- Sin persistencia de secretos en disco ni en metadata
- Corrige ASSETS_PARTIAL 6/9 del primer intento (3 RATE_LIMITED de Wikimedia, Pixabay no activado)

### R15: Bridge diagnostics `providerAttempts`

- Bridge de `run_job.py` lee `providerAttempts` (campo moderno) en vez de `attemptedProviders` (legacy)
- Métricas de diagnóstico expuestas como `diagnostics.providerAttempts` en log de fetch

### R16: Baseline final

- 1215 passed, 16 failed (preexistentes en `test_run_job.py` + `test_semantic_asset_validation.py`), 0 regresiones

### R14: Prompt dinámico neutral para v2

- `_build_duration_prompt_instruction_v2()` separado de v1
- Sin requisitos históricos: ni fechas, ni nombres propios, ni detalles históricos
- V1 conserva `_build_duration_prompt_instruction()` con todos los requisitos históricos
