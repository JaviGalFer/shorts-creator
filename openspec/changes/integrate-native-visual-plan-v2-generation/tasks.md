# Tareas: integrate-native-visual-plan-v2-generation

## Fase 1: Documentación OpenSpec

- [x] Crear `proposal.md`
- [x] Crear `design.md`
- [x] Crear `tasks.md`
- [x] Crear `specs/native-visual-plan-v2-generation.md`

## Fase 2: Implementación en generate_script.py

- [x] Añadir `SYSTEM_PROMPT_V2`
- [x] Añadir `--visual-schema-version` al CLI
- [x] Modificar `call_llm()` con `system_prompt` opcional (default `SYSTEM_PROMPT`)
- [x] Añadir `_validate_and_canonicalize_script_v2()`
- [x] Añadir `_build_user_prompt_v2()`
- [x] Añadir `_build_retry_instruction_v2()`
- [x] Modificar `main()` para bifurcar en `visual_schema_version`
- [x] Añadir persistencia de `request.visuals.schemaVersion`

## Fase 3: Tests

- [x] Crear `tests/test_generate_script_v2.py` (48 tests)
- [x] Suite focal: 197 passed
- [x] Suite completa: 1180 passed, 16 failed (preexistentes), 0 regresiones
- [x] Baseline: +48 tests sobre baseline previo

## Fase 2: Correcciones post-Build A

- [x] Fix 1: Prompt dinámico neutral separado v1/v2 (`_build_duration_prompt_instruction_v2`)
- [x] Fix 2: Enforcement request-level de `allowGeneratedImages=false` (`GENERATED_IMAGES_DISABLED_BY_REQUEST`)
- [x] Fix 3: Validación estructural 4-6 escenas, sceneNumber secuencial exacto, targetDurationSec finito
- [x] Fix 4: True strict-native — TODOS los warnings del canonicalizador son errores
- [x] 28 tests nuevos añadidos a test_generate_script_v2
- [x] Suite focal: 226 passed
- [x] Suite completa: 1209 passed, 16 failed (preexistentes), 0 regresiones

## Fase 2.5: Corrección de Pixabay + Bridge diagnostics

- [x] Diagnóstico: PIXABAY_API_KEY en `.env` pero no en `os.environ`
- [x] Fix: `_resolve_pixabay_api_key()` en fetch_images_v2.py (os.environ → .env fallback)
- [x] Fix: bridge lee `providerAttempts` (campo moderno) en vez de `attemptedProviders`
- [x] Tests: +3 key resolution, +2 bridge diagnostics
- [x] Suite focal: 290 passed
- [x] Suite completa: 1215 passed, 16 failed (preexistentes), 0 regresiones

## Fase 3: Build B — E2E live

- [x] Reejecutar fetch_images_v2 → ASSETS_READY 9/9 (7 Pixabay, 2 Wikimedia)
- [x] generate_audio → AUDIO_READY
- [x] prepare_job → SUBTITLES_READY
- [x] render_job (Docker) → RENDERED (1080x1920, 30.0s, 2.2MB)
- [x] validate_job → PASS (0 errors)
- [x] E2E_PASS

## Cierre

- [x] Actualizar `docs/project/current-state.md`
- [x] Actualizar session document
- [x] Actualizar design.md y specs
- [x] Cierre formal del change (tras revisión)
