# Sesión: Slice 6B — corrección de prompt/retry del contrato de script

Timestamp real capturado: `2026-08-02T21:45:07+02:00`
Sesión: `retire-legacy-visual-v1-slice-6b-script-contract-fix`

## 1. Configuración

- Modelo: `opencode/deepseek-v4-flash-free`, variante `default`
- Modo: `Build`; máx. 24 pasos agentic; sin subagentes
- Codebase Memory MCP: desactivado; 0 llamadas MCP; sin reindexado
- Objetivo: implementar las correcciones derivadas de la auditoría read-only del
  primer E2E de Slice 6B (prompt + retry + cobertura). Sin nuevo E2E; sin cierre
  de Slice 6B ni del change completo.

## 2. Estado Git heredado

- Rama: `main`
- HEAD: `496dd33abd07acb7dda5534613a882adf81ac84e`
- Historial: `496dd33` (record 6A closure), `86170d3` (6A baseline), `3866cc6` (5B closure)
- Staging vacío; working tree:
  - `M  docs/project/current-state.md`
  - `M  openspec/changes/retire-legacy-visual-v1/tasks.md`
  - `?? docs/sessions/20260802-212305-retire-legacy-visual-v1-slice-6b-e2e.md`
- `git diff --check` limpio; `bin/` y `tests/` sin cambios
- Único aviso: warning de permisos ignorado de `data/postgres/` (no bloqueante)

## 3. Evidencia del job utilizada

- Job: `data/videos/cmo-2026-08-02-192443`
- `status=REVIEW_REQUIRED`; `lastCompletedStage=script`; exit code top-level 0
- Errores finales: `animation` e `infographic` en `assetPreferences[0]` y
  `visualSequence[0].assetPreference` (escenas 3 y 5); 54 palabras;
  `estimatedDurationSec=30.9`; máximo contractual=52 palabras (perfil
  `short_25_30`, strictness=balanced)

## 4. Diagnóstico E1–E6

- **E1 — Prompt drift:** causa principal. Lista manual de `assetPreferences` en el
  prompt independiente del contrato; rama de retry `reduce_content` no
  re-declaraba el enum. Confirmado.
- **E2 — Retry feedback incompleto:** causa contribuyente. Retries de duración no
  recordaban el contrato visual. Confirmado.
- **E5 — Incumplimiento estocástico del modelo:** contribuyente. Confirmado.
- **E6 — Cobertura insuficiente:** confirmado (faltaban tests de enum/retry).
- **E3 — Canonicalización insuficiente:** parcial.
- **E4 — Validator incorrecto:** descartado. El validator rechaza correctamente
  `animation` e `infographic`; la causa es el prompt/retry, no el validator.

## 5. Fuente contractual del enum

- `ALLOWED_ASSET_PREFERENCES` (en `bin/visual_plan_v2.py`) es la única fuente
  contractual. Contiene: archive, diagram, document, generated, illustration,
  map, painting, photograph, stock (9 valores).
- `sorted(ALLOWED_ASSET_PREFERENCES)` proporciona una representación estable,
  independiente del orden de un set/frozenset.

## 6. Cambios en el prompt

- `bin/generate_script.py`:
  - Import de `ALLOWED_ASSET_PREFERENCES` desde `visual_plan_v2`.
  - Nueva `_build_asset_preferences_section()`: construye la sección
    «AssetPreferences permitidos» a partir de `sorted(ALLOWED_ASSET_PREFERENCES)`,
    con descripciones en `_ASSET_PREF_DESCRIPTIONS`. Sin listas manuales
    divergentes.
  - `SYSTEM_PROMPT_V2` se construye por concatenación y `replace()` del bloque
    generado (la lista manual se eliminó). Se conserva como string triple-comilla
    para minimizar el cambio.
  - La fila de tabla de `assetPreferences` ya no lista valores hardcodeados;
    remite al enum cerrado de la sección.
  - `diagram` definido como valor exacto: «Diagramas, esquemas explicativos y
    composiciones tipo infografía; el valor del enum debe ser exactamente
    "diagram"» (evita inducir `infographic`).
  - `generated` condicionado a `allowGeneratedImage`.
  - Regla de enum cerrado y términos prohibidos: «No uses: animation, animated,
    infographic, photo, image, video».

## 7. Cambios en retries

- `_build_asset_preference_constraint_block(allow_generated_images)`: re-declara
  el enum cerrado y prohíbe sinónimos.
- `_build_retry_instruction_v2` ahora es siempre contractual:
  1. Enum cerrado exacto (toda rama, incluida `reduce_content`).
  2. Prohibición de inventar sinónimos.
  3. Preservar campos válidos del `visualPlan` (escenas, `sceneNumber`, campos y
     enums ya válidos).
  4. Límite absoluto de palabras: «LÍMITE ABSOLUTO: la narración total NO debe
     superar {max_w} palabras» y, en `reduce_content`, «a como máximo {max_w}.
     No superes {max_w}». La reducción aproximada se conserva solo como
     información adicional.
  5. Revalidación mental de estructura y duración antes de responder.
- Retry combinado (estructural + duración): conserva paths/mensajes estructurales,
  enum exacto, máximo de palabras y pide corregir ambos contratos preservando los
  campos ya válidos.

## 8. Alias aplicado o descartado

- **`infographic → diagram`: descartado (no implementado).** La canonicalización
  contractual vive dentro de `canonicalize_visual_plan_v2` en
  `bin/visual_plan_v2.py` (fuera de alcance) y no existe un punto pre-validator
  seguro y centralizado en el flujo de `generate_script.py`. Implementarlo
  exigiría una segunda arquitectura de canonicalización, explícitamente prohibida.
  Se documenta como mejora futura no bloqueante.
- `animation`: NO se normaliza (no hay mapping contractual inequívoco).

## 9. Confirmación de validator intacto

- `bin/visual_plan_v2.py` NO se modificó. Validator, canonicalización y
  `ALLOWED_ASSET_PREFERENCES` intactos. `animation` e `infographic` siguen siendo
  rechazados.

## 10. Confirmación de `MAX_SCRIPT_ATTEMPTS=3`

- `MAX_SCRIPT_ATTEMPTS == 3` sin cambios. No se aumentó para ocultar el problema.
- Contrato temporal intacto: targetSec=30, minSec=27, maxSec=30,
  spokenWordsPerMinute=110, strictness=balanced, word budget 47/52/52.

## 11. Tests añadidos

- `tests/test_generate_script_v2.py`: se actualizó la resolución de
  `SYSTEM_PROMPT_V2` (ahora usa `gs.SYSTEM_PROMPT_V2`, ya que el prompt se
  construye dinámicamente) y se añadieron 8 tests:
  - T1 — paridad enum prompt/contrato (deriva de `ALLOWED_ASSET_PREFERENCES`, 9 valores).
  - T2 — prompt inequívoco (diagram exacto, enum cerrado, `generated` condicionado).
  - T3 — retry de duración con límite absoluto (52), enum y preservación.
  - T4 — retry combinado estructural + duración.
  - T5 — regresión de valores reales: `animation` e `infographic` rechazados.
  - T6 — preservación durante `reduce_content`.
  - T7 — `MAX_SCRIPT_ATTEMPTS == 3`.
- Restricciones: sin red, LLM real, Docker, Edge TTS, archivos persistentes ni
  `.env` real. Sin skip/xfail.

## 12. Resultados focalizados

- `tests/test_generate_script_v2.py`: **85 passed** (77 previos + 8 nuevos).
- Combinación de generación (`test_generate_script.py`,
  `test_generate_script_v2.py`, `test_duration_profiles.py`,
  `test_v2_only_generation_contract.py`): **131 passed**.
- `tests/test_run_job.py`: **91 passed**.

## 13. Collect-only

- `python3 -m pytest --collect-only -q tests/`: **1110 tests collected**, cero
  errores de colección.

## 14. Suite completa

- `python3 -m pytest -q tests/ --tb=short`: **1110 passed, 0 failed** en ~11.7s.

## 15. Baseline nueva

- **`1110 passed, 0 failed`** (baseline anterior `1102`; +8 tests nuevos).
- Cero skips, cero xfail, cero warnings.

## 16. Archivos modificados

- `bin/generate_script.py` (código productivo).
- `tests/test_generate_script_v2.py` (tests).
- `docs/project/current-state.md` (documental).
- `openspec/changes/retire-legacy-visual-v1/tasks.md` (documental).
- `docs/sessions/20260802-212305-retire-legacy-visual-v1-slice-6b-e2e.md`
  (session log E2E, sección de auditoría añadida).
- `docs/sessions/20260802-214507-retire-legacy-visual-v1-slice-6b-script-contract-fix.md`
  (este session log, nuevo).

## 17. Estado Git final

- Rama `main`; HEAD `496dd33abd07acb7dda5534613a882adf81ac84e` (sin cambios).
- Staging vacío; únicamente el conjunto autorizado de archivos modificados.
- `git diff --check` limpio.
- Job `cmo-2026-08-02-192443` preservado sin modificar.

## 18. Cero E2E y providers

- No se ejecutó `bin/run_job.py`.
- Sin LLM real, providers visuales, Edge TTS, ElevenLabs, Docker ni FFmpeg.
- Sin staging, commit, push, amend, MCP ni reindexado.

## 19. Próximo paso

- Review read-only de la corrección (prompt/retry + tests + documentación).
- Commit de la corrección (sesión posterior).
- Nuevo E2E V2 canónico para verificar PASS.
- Tras PASS, auditoría y cierre formal del change `retire-legacy-visual-v1`.
- Slice 6B queda pendiente de review; el change completo continúa abierto.

# Auditoría read-only de la corrección

Añadido posteriormente (2026-08-02) tras la auditoría read-only de la corrección
de prompt/retry de este Build.

- Verdict: `SLICE_6B_FIX_REVIEW_CHANGES_REQUIRED`
- Findings:
  - **F1 MEDIUM:** el primer prompt no transmitía de forma request-scoped que
    `allowGeneratedImages=false`.
  - **F2 MEDIUM:** `tasks.md` presentaba el E2E simultáneamente completado y
    pendiente dentro de Slice 6A.
  - **F3 LOW:** la prohibición `animation/infographic/photo/image/video` no estaba
    explícitamente limitada a valores del enum.
  - **F4 LOW:** el retry no imprimía `issue["path"]` explícitamente.
  - **F5 LOW:** faltaba una prueba integrada del flujo real `reduce_content`.
  - **F6 LOW:** T1, T4 y T5 tenían comprobaciones insuficientemente precisas.
- Suite `1110 passed` del Build validada como baseline previa.
- Prohibición de commit en esta auditoría: ningún commit, push, staging, MCP ni
  reindexado.
- Follow-up requerido: aplicar las correcciones F1–F6 en una sesión de Build
  separada, después reaprobación read-only focalizada y, finalmente, un nuevo E2E.
- No se ejecutó un nuevo E2E en esta auditoría.
- Precisión sobre paths: el Build inicial dependía de paths embebidos en el
  `code`/`message` del error; el follow-up pasa ahora a transmitir `issue["path"]`
  de forma explícita (código, path y mensaje separados) en
  `_build_retry_instruction_v2`, tanto para issues con `sceneNumber` como sin él.
- Las correcciones F1–F6 se aplicaron en la sesión de Build
  `20260802-221355-retire-legacy-visual-v1-slice-6b-script-contract-review-fixes`.
- Baseline de la sesión de correcciones F1–F6: **`1117 passed, 0 failed`**
  (suite completa; `test_generate_script_v2.py` = 92, generación combinada = 138,
  `test_run_job.py` = 91). Cero skips, cero xfail, cero warnings.
