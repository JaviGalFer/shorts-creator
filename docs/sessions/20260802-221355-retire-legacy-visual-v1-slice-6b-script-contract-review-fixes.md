# Sesión: Slice 6B — correcciones F1–F6 del review de prompt/retry

Timestamp real capturado: `2026-08-02T22:13:55+02:00`
Sesión: `retire-legacy-visual-v1-slice-6b-script-contract-review-fixes`

## 1. Configuración

- Sesión: `retire-legacy-visual-v1-slice-6b-script-contract-review-fixes`
- Modelo: `opencode/deepseek-v4-flash-free`, variante `default`
- Modo: `Build`; máx. 22 pasos agentic; sin subagentes
- Codebase Memory MCP: desactivado; 0 llamadas MCP; sin reindexado
- Objetivo: corregir exclusivamente los findings F1–F6 de la auditoría read-only
  de la corrección de prompt/retry de Slice 6B. Sin nuevo E2E; sin commit; sin
  cierre de Slice 6B ni del change completo.

## 2. Estado Git inicial

- Rama: `main`
- HEAD: `496dd33abd07acb7dda5534613a882adf81ac84e`
- Historial: `496dd33` (record 6A closure), `86170d3` (6A baseline), `3866cc6` (5B closure)
- Staging vacío; working tree:
  - `M  bin/generate_script.py`
  - `M  docs/project/current-state.md`
  - `M  openspec/changes/retire-legacy-visual-v1/tasks.md`
  - `M  tests/test_generate_script_v2.py`
  - `?? docs/sessions/20260802-212305-retire-legacy-visual-v1-slice-6b-e2e.md`
  - `?? docs/sessions/20260802-214507-retire-legacy-visual-v1-slice-6b-script-contract-fix.md`
- `git diff --check` limpio
- Único aviso: warning de permisos ignorado de `data/postgres/` (no bloqueante)

## 3. Findings F1–F6 utilizados

Verdict recibido: `SLICE_6B_FIX_REVIEW_CHANGES_REQUIRED`

- **F1 MEDIUM:** el primer prompt no transmite de forma request-scoped que `allowGeneratedImages=false`.
- **F2 MEDIUM:** `tasks.md` presenta el E2E simultáneamente completado y pendiente dentro de Slice 6A.
- **F3 LOW:** la prohibición `animation/infographic/photo/image/video` no está explícitamente limitada a valores del enum.
- **F4 LOW:** el retry no imprime `issue["path"]` explícitamente.
- **F5 LOW:** falta una prueba integrada del flujo real `reduce_content`.
- **F6 LOW:** T1, T4 y T5 tienen comprobaciones insuficientemente precisas.

Decisiones mantenidas: no modificar `visual_plan_v2.py`; no modificar `run_job.py`;
no modificar `duration_profiles.py`; no relajar el contrato temporal; no aumentar
`MAX_SCRIPT_ATTEMPTS`; no normalizar `animation`; no implementar `infographic →
diagram`; no ejecutar otro E2E.

## 4. Gate request-scoped implementado (F1)

- `allow_generated_images = False` se define en `main()` antes de construir
  `base_prompt`.
- Nuevo helper `_build_generated_images_gate_block(allow_generated_images)` que
  genera el bloque `## Restricción visual de esta request` con el valor real.
- `_build_user_prompt_v2` recibe `allow_generated_images: bool` como argumento
  keyword-only y añade el bloque al final del user prompt (tras la instrucción de
  duración).
- El caso `True` es admisible (gate condiciona `generated` a `allowGeneratedImage=true`
  con prompts correspondientes), sin activarse en `main()`.

## 5. Unificación del booleano `allow_generated_images`

- Un único booleano en `main()` gobierna:
  - primer user prompt (`_build_user_prompt_v2`),
  - retry (`_build_user_prompt_v2` en la rama `retries > 0` y
    `_build_retry_instruction_v2`),
  - validación (`_validate_and_canonicalize_script_v2(..., allow_generated_images=...)`),
  - metadata de request (`visuals_request["allowGeneratedImages"] = allow_generated_images`).
- Se elimina el `False` literal duplicado de `visuals_request`.

## 6. Scope del enum corregido (F3)

- En `_build_asset_preferences_section` y `_build_asset_preference_constraint_block`
  la prohibición ahora es: «No uses animation, animated, infographic, photo, image
  ni video como valores de `assetPreferences` o `visualSequence[].assetPreference`».
- Se añade la aclaración de que esos términos pueden aparecer en `searchQueries`,
  `subjects` o texto descriptivo cuando sean semánticamente necesarios; la
  prohibición afecta únicamente al valor del enum.

## 7. Paths explícitos (F4)

- `_build_retry_instruction_v2` imprime cada issue estructural con tres líneas
  separadas: `[{code}]`, `Path: {path}`, `Message: {message}`.
- No duplica `scenes[x].visualPlan` si el path ya viene completamente cualificado
  (el validator ya lo prefija).
- Aplica también a issues sin `sceneNumber` (rama `else`).
- No se modifica el validator.

## 8. Integración `reduce_content` (F5)

- Test hermético `test_f5_integrated_reduce_content_through_main` que reproduce el
  bug original a través de `main()`:
  - Primer intento: script estructuralmente V2 válido, 5 escenas, `assetPreferences`
    y `visualSequence` válidos, 12 palabras/escena (60 > `maximumWords=52`).
  - Captura todos los prompts; el segundo contiene: gate `allowGeneratedImages=false`,
    `generated` prohibido, los nueve valores del enum, máximo absoluto `52`,
    `como máximo 52`, preservación de escenas/`sceneNumber`/`visualPlan`/
    `assetPreferences`/`visualSequence`.
  - Segundo intento: script válido, dentro de rango, <=52 palabras, sin `generated`.
  - Assertions: `calls == 2`, `status == SCRIPT_DRAFT`, `durationContract.status == PASS`.
  - Sin red, sin `.env` real. Falla si `main()` deja de adjuntar
    `_build_retry_instruction_v2` al segundo prompt.

## 9. Mejoras T1/T2/T4/T5 (F6)

- **T1:** `_prompt_asset_pref_enum_values` añade `assert start >= 0` y
  `assert end > start` (no produce slice incorrecto con encabezado ausente).
- **T2:** nuevos tests del gate real: `test_t2_request_gate_false` (false
  incondicional: `allowGeneratedImages es false`, `allowGeneratedImage=false`,
  `generated` prohibido, sin condicional a request desconocida),
  `test_t2_request_gate_true` (mínimo) y `test_t2_first_prompt_contains_false_gate`
  (verifica el gate real en el primer prompt de `main()` vía dry-run).
- **T4:** tests con issues independientes que verifican `Path: assetPreferences[0]`
  y `Path: visualSequence[0].assetPreference`, más un caso sin `sceneNumber`
  (`Path: scenes`). Falla si se elimina la impresión explícita de `issue["path"]`.
- **T5:** parametrizado sobre `["animation", "infographic"]`; verifica que el
  validator reporta ambos paths `scenes[1].visualPlan.assetPreferences[0]` y
  `scenes[1].visualPlan.visualSequence[0].assetPreference`, no solo
  `any("INVALID_ENUM_VALUE" in code)`.
- **T3, T6, T7:** conservadas sin cambios de garantías.

## 10. Corrección de `tasks.md` (F2)

- Slice 6A: eliminada la entrada `- [x] Ejecutar E2E V2 canónico` y la sección
  `Pendientes` que re-listaba E2E/cierre. Añadida nota: «el E2E V2 canónico
  pertenece a Slice 6B y no forma parte de las tareas de cierre de Slice 6A».
- Slice 6B: secuencia canónica única:
  `[x]` primer intento, `[x]` auditoría del primer intento, `[x]` corrección
  prompt/retry, `[x]` cobertura enum/retries, `[x]` auditoría de la corrección
  (`SLICE_6B_FIX_REVIEW_CHANGES_REQUIRED`), `[x]` correcciones F1–F6; `[ ]`
  reaprobación, `[ ]` commit, `[ ]` nuevo E2E, `[ ]` PASS, `[ ]` cierre formal.

## 11. Corrección de `current-state.md`

- La frase «Slice 6B es el siguiente trabajo y todavía no se ha iniciado» se
  reformuló como hecho histórico: «En el momento del cierre de Slice 6A, Slice 6B
  todavía no se había iniciado. Posteriormente se ejecutó el primer E2E».
- Añadida la sección «Review del Build y correcciones F1–F6» con el estado vigente:
  primer E2E BLOCKED; auditoría inicial CHANGES_REQUIRED; primer Build implementado;
  review del Build CHANGES_REQUIRED por F1/F2; F3–F6 aceptados; correcciones F1–F6
  aplicadas; reaprobación pendiente; ningún nuevo E2E; ningún commit; ningún PASS;
  change abierto.

## 12. Logs actualizados

- E2E log: añadida la sección «Review del Build de la corrección» con verdict,
  F1–F6, sin nuevo E2E, correcciones en sesión separada y resultado histórico del
  job intacto.
- Build log: añadida la sección «Auditoría read-only de la corrección» con verdict,
  F1–F6, suite `1110` validada, prohibición de commit, follow-up requerido, sin
  nuevo E2E, y precisión sobre paths (Build inicial dependía de paths embebidos en
  code/message; el follow-up transmite `issue["path"]` explícitamente).

## 13. Tests focalizados

- `python3 -m pytest -q tests/test_generate_script_v2.py --tb=short`: **92 passed**.
- Combinación de generación (`test_generate_script.py`, `test_generate_script_v2.py`,
  `test_duration_profiles.py`, `test_v2_only_generation_contract.py`): **138 passed**.
- `python3 -m pytest -q tests/test_run_job.py --tb=short`: **91 passed**.

## 14. Collect-only

- `python3 -m pytest --collect-only -q tests/`: **1117 tests collected**, cero
  errores de colección.

## 15. Suite completa

- `python3 -m pytest -q tests/ --tb=short`: **1117 passed, 0 failed** en ~11.68s.

## 16. Baseline resultante

- **`1117 passed, 0 failed`** (baseline anterior `1110`; +7 tests en
  `test_generate_script_v2.py`).
- Cero skips, cero xfail, cero warnings.

## 17. Archivos modificados

- `bin/generate_script.py` (F1 gate request-scoped, F3 scope enum, F4 paths).
- `tests/test_generate_script_v2.py` (F5 integración reduce_content, F6 T1/T2/T4/T5).
- `docs/project/current-state.md` (documental).
- `openspec/changes/retire-legacy-visual-v1/tasks.md` (documental, F2).
- `docs/sessions/20260802-212305-retire-legacy-visual-v1-slice-6b-e2e.md` (session log E2E).
- `docs/sessions/20260802-214507-retire-legacy-visual-v1-slice-6b-script-contract-fix.md` (Build log).
- `docs/sessions/20260802-221355-retire-legacy-visual-v1-slice-6b-script-contract-review-fixes.md` (este session log, nuevo).

## 18. Estado Git final

- Rama `main`; HEAD `496dd33abd07acb7dda5534613a882adf81ac84e` (sin cambios).
- Staging vacío; únicamente el conjunto autorizado de archivos modificados.
- `git diff --check` limpio.
- Job `cmo-2026-08-02-192443` preservado sin modificar.

## 19. Cero E2E y providers

- No se ejecutó `bin/run_job.py`.
- Sin LLM real, providers visuales, Edge TTS, ElevenLabs, Docker ni FFmpeg.
- Sin staging, commit, push, amend, MCP ni reindexado.

## 20. Próximo paso

- Reaprobación read-only focalizada de las correcciones F1–F6.
- Tras reaprobación: commit de la corrección.
- Después: nuevo E2E V2 canónico para verificar PASS.
- Tras PASS: auditoría y cierre formal del change `retire-legacy-visual-v1`.
- Slice 6B queda pendiente de reaprobación; el change completo continúa abierto.

# Reaprobación read-only focalizada

- Sesión: `retire-legacy-visual-v1-slice-6b-script-contract-reapproval`.
- Modelo: `opencode/deepseek-v4-flash-free`, variante `default`.
- Modo: Plan / read-only.
- MCP: 0 llamadas (desactivado).
- Verdict: `SLICE_6B_REVIEW_FIXES_REAPPROVED_FOR_COMMIT`.
- F1–F6 confirmados como resueltos.
- Cero findings MEDIUM o superiores.
- Un NOTE futuro no bloqueante sobre la rama `allow_generated_images=True`.
- Resultados focalizados: `test_generate_script_v2.py` = 92; generación combinada = 138; `test_run_job.py` = 91.
- Collect-only: `1117 tests collected`.
- Suite completa: `1117 passed, 0 failed`.
- Hashes de código y tests inmutables durante la reaprobación.
- Cero edición; cero staging; cero commit; cero nuevo E2E.
- Commit de la corrección pendiente.
