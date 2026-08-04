# Sesión: Slice 6B — Review fixes del retry temporal

- Timestamp: `20260804-211148`
- ISO: `2026-08-04T21:11:48+02:00`
- Modelo: `opencode/deepseek-v4-flash-free`, variante `default`
- Modo: `Build`

## 1. Configuración

- Sesión: `retire-legacy-visual-v1-slice-6b-duration-retry-review-fixes`
- Alcance: corregir exclusivamente los findings F1–F7 de la auditoría read-only
  de la corrección temporal de duración.
- Codebase Memory MCP: DESACTIVADO (0 llamadas, 0 herramientas).
- Subagentes: ninguno.
- No ejecutar otro E2E. No hacer commit. No cerrar Slice 6B ni el change.

## 2. Estado Git inicial

- Rama: `main`
- HEAD: `e5e2a4eb25746bf10645e0c1c2fe458482bedc48`
- Staging vacío. `git diff --check` limpio.
- Working tree:
  - `M bin/generate_script.py`
  - `M docs/project/current-state.md`
  - `M openspec/changes/retire-legacy-visual-v1/tasks.md`
  - `M tests/test_generate_script.py`
  - `M tests/test_generate_script_v2.py`
  - `?? docs/sessions/20260802-224326-retire-legacy-visual-v1-slice-6b-canonical-e2e-rerun.md`
  - `?? docs/sessions/20260804-201703-retire-legacy-visual-v1-slice-6b-duration-retry-fix.md`

## 3. Findings F1–F7

- **F1 HIGH** — `compression` usaba `SYSTEM_PROMPT_V2`, contradiciendo el user
  prompt reducido.
- **F2 MEDIUM** — `{expected}` llegaba literalmente al modelo.
- **F3 MEDIUM** — `sceneWordCaps` se declaraban pero no se validaban.
- **F4 MEDIUM** — `lastAttemptDiscardedAsRegression=true` cuando el último
  intento era best.
- **F5 LOW** — best candidate válido se persistía en representación raw, no
  canónica.
- **F6 LOW** — `repairPayloadValid` y `retryHistory.wordCount` con semántica
  ambigua.
- **F7 LOW** — `acceptedAsBest` significaba best-so-far y podía quedar `true` en
  varios intentos.

## 4. System prompt dedicado

- Nueva constant `VOICEOVER_COMPRESSION_SYSTEM_PROMPT`: exige SOLO JSON con
  `sceneNumber` + `voiceover`, prohíbe campos adicionales y no requiere guion
  completo ni `visualPlan`.
- No menciona `assetPreferences` ni `visualSequence`; no pide título, hook ni
  summary. Compatible con `response_format={"type":"json_object"}`.

## 5. Selección de system prompt

- Por estrategia: `prompt_strategy == "compression"` → `VOICEOVER_COMPRESSION_SYSTEM_PROMPT`;
  resto (inicial / estructural / expansión) → `SYSTEM_PROMPT_V2`.
- La llamada usa `call_llm(..., system_prompt=attempt_system_prompt)`.

## 6. Interpolación

- La línea `Revisa que los sceneNumber sean ...` ahora es un f-string e
  interpola la secuencia real (`[1, 2, 3, 4, 5]` para 5 escenas); `{expected}`
  ya no llega literal al modelo.

## 7. Enforcement de caps

- `_apply_voiceover_repair` recibe `scene_word_caps` y valida por escena
  `MIN_WORDS_PER_SCENE <= wordCount <= sceneWordCap` con el contador productivo
  `len(voiceover.split())`.
- Errores: `REPAIR_SCENE_WORD_CAP_EXCEEDED`, `REPAIR_SCENE_WORD_MINIMUM_NOT_MET`,
  `REPAIR_INVALID_SCENE_CAPS` (cada uno con `sceneNumber`, path, word count real,
  mínimo/cap esperado y mensaje).
- Sin merge parcial: si falla cualquier condición, no se modifica `script_data` y
  el intento se consume dentro de `MAX_SCRIPT_ATTEMPTS`.

## 8. Mínimo por escena

- Valida `MIN_WORDS_PER_SCENE <= wordCount` (mínimo 7) además del cap.

## 9. Semántica del payload

- `repairShapeValid` = shape/estructura válida (objeto, lista, campos,
  `sceneNumber`, secuencia, voiceover string/no vacío).
- `repairBudgetValid` = budget por escena válido.
- `repairPayloadValid = repairShapeValid and repairBudgetValid`.

## 10. Best candidate

- Solo participan candidatos `structureValid == true`.
- El best se selecciona por ranking mínimo (distancia al rango + cercanía a
  `preferredWords`); empate completo conserva el candidato anterior.
- En PASS, el intento PASS es el best final.

## 11. Flag de regresión

- `lastAttemptDiscardedAsRegression` es `true` únicamente cuando el último
  intento produjo un nuevo candidato estructuralmente válido con ranking
  estrictamente peor que el best final y se persistió un intento anterior.
- `false` cuando el último es best, hay empate, el payload fue rechazado, el
  último fue estructuralmente inválido o no existe best.

## 12. Canonicalización

- `_candidate_rank(word_count, budget)` centraliza el ranking
  `(_distance_to_allowed_range, abs(word_count - preferredWords))`.
- La representación canónica participa siempre (best candidate, siguiente retry,
  compresión, persistencia) aunque falle la duración; se persiste canónico si la
  estructura es válida.

## 13. Telemetría

- Por intento: `candidateUpdated`, `candidateReused`, `candidateRank`,
  `wordCountSource` (`previous_candidate` / `repaired_candidate` /
  `generated_candidate`), `repairShapeValid`, `repairBudgetValid`,
  `repairPayloadValid`, `becameBestCandidate`.
- Payloads rechazados no se persisten (ni su contenido completo); se conserva el
  candidato anterior.

## 14. `acceptedAsBest`

- Final e inequívoco: tras el bucle se resetea a `false` en todas las entradas y
  se marca `true` únicamente en `bestAttempt` (o el intento PASS).
- `becameBestCandidate` queda como telemetría del momento.

## 15. Tests añadidos

- `tests/test_generate_script_v2.py`: 113 → 130 (clase `TestDurationReviewFixes`):
  F1 par system/user de compresión; F2 interpolación 4 y 5 escenas; F3 caps
  (over-cap, bajo mínimo, caps inválidos en longitud/tipo/booleano/<7, payload
  válido, caso `[20,8,8,8,8]`); F5 casos B/C/D (último best, empate, payload
  final rechazado); F6 canonicalización persistida; F7 telemetría de payload
  rechazado; F8 `acceptedAsBest` (sum 1 y sum 0); F9 forma del system prompt.
- `tests/test_generate_script.py`: `test_main_retry_loop_3_attempts_3rd_succeeds`
  actualizado al flujo real (60 → 40 bajo mínimo → 48 expansión PASS).

## 16. Resultados focalizados

- `test_generate_script_v2.py`: 130 passed.
- Generación combinada: 176 passed.
- `test_run_job.py`: 91 passed.

## 17. Collect-only

- `python3 -m pytest --collect-only -q tests/`: `1155 tests collected`, cero
  errores de colección.

## 18. Suite completa

- `python3 -m pytest -q tests/ --tb=short`: `1155 passed, 0 failed` en `11.59s`.

## 19. Baseline

- Nueva baseline: **`1155 passed, 0 failed`** (anterior `1138`; +17 tests).
- Cero skips, cero xfail, cero warnings.

## 20. Documentación

- `openspec/changes/retire-legacy-visual-v1/tasks.md`: marcados review
  (`SLICE_6B_DURATION_FIX_REVIEW_CHANGES_REQUIRED`), F1–F4 y F5–F7; pendientes
  reaprobación, commit y E2E.
- `docs/project/current-state.md`: nueva sección «Slice 6B — Review fixes del
  retry temporal», resumen de Slice 6B, change activo y próximos pasos
  actualizados.
- Log del E2E (`20260802-224326`): sección «Review de la primera corrección
  temporal».
- Log del Build temporal (`20260804-201703`): secciones «Auditoría read-only del
  Build» y «Follow-up de correcciones del review».

## 21. Archivos modificados

- `M bin/generate_script.py`
- `M tests/test_generate_script_v2.py`
- `M tests/test_generate_script.py`
- `M docs/project/current-state.md`
- `M openspec/changes/retire-legacy-visual-v1/tasks.md`
- `?? docs/sessions/20260802-224326-retire-legacy-visual-v1-slice-6b-canonical-e2e-rerun.md`
- `?? docs/sessions/20260804-201703-retire-legacy-visual-v1-slice-6b-duration-retry-fix.md`
- `?? docs/sessions/20260804-211148-retire-legacy-visual-v1-slice-6b-duration-retry-review-fixes.md` (este log)

> Nota de tracking (F11): los tres logs de sesión figuran como `??` (UNTRACKED).
> Los archivos contienen actualizaciones acumuladas en el working tree, pero
> todavía no están versionados. No existe ningún commit oculto ni transición de
> tracking para estos logs.

## 22. Estado Git final

- Rama `main`; HEAD `e5e2a4eb25746bf10645e0c1c2fe458482bedc48` (sin cambios).
- Staging: 0. `git diff --check` limpio.
- Solo los archivos autorizados.

## 23. Cero E2E

- No se ejecutó ningún E2E; no se tocó ningún job. Ningún PASS.

## 24. Próximo paso

- Reaprobación read-only focalizada de la corrección temporal.
- Commit de la corrección temporal.
- Siguiente E2E V2 canónico; tras un PASS, auditoría y cierre formal del change.
- Slice 6B y el change completo continúan abiertos.

# Reaprobación read-only

Ejecutada en la sesión de follow-up canónico (ver
`20260804-213006-retire-legacy-visual-v1-slice-6b-duration-canonical-followup.md`).

- F1–F4 y F6–F7 confirmados como resueltos.
- F5 quedó parcial y se convirtió en **F8 MEDIUM bloqueante**: el compression
  prompt (`_build_voiceover_compression_prompt`) y el merge
  (`_apply_voiceover_repair`) recibían la representación raw en lugar de la
  canónica, pese a que `canonical` ya estaba disponible cuando `v2_valid == true`.
- F9–F11 LOW no bloqueantes (F9 aceptado; F10 gaps de cobertura; F11 tracking
  documental incorrectamente descrito).
- Verdict: `SLICE_6B_DURATION_REVIEW_FIXES_REAPPROVAL_CHANGES_REQUIRED`.
- La corrección posterior (F8) se aplicó en otra sesión (`...duration-canonical-followup`).
- Tracking real de los logs: los tres logs de sesión figuran como `??` (UNTRACKED),
  con actualizaciones acumuladas en el working tree sin versionar (corrección F11).
