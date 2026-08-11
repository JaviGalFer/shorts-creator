# Slice 6B — Corrección de política temporal (targets como guidance + convergencia monotónica)

- **Sesión:** `retire-legacy-visual-v1-slice-6b-duration-policy-fix`
- **Modelo:** `opencode/deepseek-v4-flash-free` (variante `default`)
- **Modo:** Build
- **Fecha:** 2026-08-11

## Configuración

- Máximo de pasos agentic: 26; subagentes: ninguno.
- Codebase Memory MCP: DESACTIVADO; 0 llamadas MCP.
- Reindexado: no.
- No se implementó el cuarto E2E, no se hizo commit y no se cerró formalmente el
  change. Cero push, cero staging.

## HEAD y estado Git inicial

- Rama: `main`
- HEAD: `ad86834b414ab5973ffee0d4701fa86ce7b30b47`
- Working tree inicial: `M docs/project/current-state.md`,
  `M openspec/changes/retire-legacy-visual-v1/tasks.md`,
  `?? docs/sessions/20260804-215808-retire-legacy-visual-v1-slice-6b-third-canonical-e2e.md`.
- Staging vacío; cero commit, cero push, cero amend/reset/rebase.
- `git diff --check` limpio.

## Baseline heredada

```text
1158 passed, 0 failed
```

- `test_generate_script_v2.py` = 133 passed; combinada generación = 179 passed;
  `test_run_job.py` = 91 passed.
- Constantes contractuales vigentes: `MAX_SCRIPT_ATTEMPTS == 3`,
  `minimumWords=47`, `preferredWords=52`, `maximumWords=52`,
  `strictness=balanced`.

## Falso negativo global (del tercer E2E `cmo-2026-08-04-195654`)

- El tercer E2E quedó BLOCKED por `DURATION_OUT_OF_RANGE` (56 > 52 palabras);
  el contrato visual y la estructura eran válidos.
- La política anterior exigía reducir **8** palabras (caps `[11,11,10,10,10]`
  frente a conteos `[14,13,9,7,13]`) y rechazaba retries con alguna escena por
  debajo de siete palabras, aunque el total global fuese válido. Solo hacían
  falta **4** palabras (56 → 52).
- Verdict de auditoría: `SLICE_6B_DURATION_POLICY_AUDIT_RECOMMENDS_CHANGES`.

## Decisión de política

- Los caps estáticos por escena y el mínimo duro de siete palabras se clasifican
  como mecanismos del repair, no como contracto.
- El presupuesto global (`minimumWords <= total <= maximumWords`) es el único
  contracto duro de duración.
- Los targets por escena pasan a ser guidance dinámica, sin bloquear merge ni
  PASS.
- La convergencia de candidatos debe ser monotónica sin aumentar
  `MAX_SCRIPT_ATTEMPTS`.

## Cambios de código (`bin/generate_script.py`)

- Eliminados `MIN_WORDS_PER_SCENE` y `_allocate_scene_word_caps`.
- `_compute_scene_word_targets(current_counts, maximum_words)`: water-filling
  determinista que distribuye `maximum_words` según los conteos actuales,
  manteniendo el orden y sin asignar por debajo del conteo de 1 por escena.
  Caso canónico `[14,13,9,7,13]`, max 52 → `[12,12,9,7,12]` (reducción 4).
  Valida `ValueError` ante listas vacías, booleanos, no-ints, valores < 1 y
  `maximum_words < len(current_counts)`.
- `_evaluate_scene_word_targets(actual_counts, targets) -> (bool, list[dict])`:
  devuelve si todos los targets se cumplen y la lista de desviaciones por escena
  (`sceneNumber`, `actualWords`, `recommendedTargetWords`, `delta`).
- `_build_voiceover_compression_prompt`: ahora recibe `scene_word_targets`
  (guidance) e integra `currentWordCount`, `requiredReductionWords`,
  `minimumWords`, `preferredWords`, `maximumWords`. Sin mención a "cap" ni a
  "mínimo siete palabras por escena".
- `_apply_voiceover_repair(base_script, repair_payload, *, expected_scene_numbers)`:
  validación exclusivamente de shape (JSON, root fields, escenas, `sceneNumber`,
  secuencia exacta, voiceover string no vacío). Sin argumentos de budget/caps.
- Bucle de compresión: computa targets del candidato activo, canonicaliza el
  propuesto, acepta PASS de inmediato, acepta mejora si
  `proposed_rank < active_candidate_rank`, si no reutiliza el candidato anterior
  (anti-regresión).
- Telemetría: nuevos campos `repairShapeValid`, `repairPayloadEligible`,
  `repairGlobalBudgetValid`, `repairSceneTargetsMet`,
  `repairSceneTargetDeviations`, `repairProposedWordCount`,
  `repairProposedSceneWordCounts`, `repairProposedCandidateRank`; aliases
  `repairPayloadValid=repairPayloadEligible`,
  `repairBudgetValid=repairGlobalBudgetValid`, `sceneWordCaps=sceneWordTargets`,
  `sceneWordCapsEnforced=false`, `sceneWordCapsDeprecated=true`; no-repair
  strategies con campos repair y `sceneWordTargets`/`sceneWordCaps` en `null`.
- `lastAttemptDiscardedAsRegression`: para `compression` compara
  `repairProposedCandidateRank` (no el `wordCount` efectivo), de modo que un
  payload shape-válido pero regresivo marca `true` y uno shape-inválido `false`.

## Cambios de tests (`tests/test_generate_script_v2.py`)

- Transformados los tests de caps a targets y a la nueva firma de
  `_apply_voiceover_repair`.
- Nueva clase `TestDurationPolicyFix` con cobertura T1–T9:
  - T2 PASS global con target no cumplido (el presupuesto global es el gate).
  - T3 convergencia 56 → 54 → 52.
  - T4 convergencia 56 → 58 → 52.
  - T6 escena de seis palabras supera el mínimo (sin `MIN_WORDS_PER_SCENE`).
  - T8 best attempt 54 ante 56 → 54 → 55.
  - T9 telemetría y aliases; telemetría de payload shape-inválido.
- Helpers `_full_counts`, `_five_scene_script`, `_repair_counts`, `_run`.

## Resultados de tests

- `tests/test_generate_script_v2.py`: 140 passed (anterior 133; +7).
- Combinada generación (`test_generate_script.py` +
  `test_generate_script_v2.py` + `test_duration_profiles.py` +
  `test_v2_only_generation_contract.py`): 186 passed (anterior 179).
- `tests/test_run_job.py`: 91 passed.
- Collect-only: `1165 tests collected`, cero errores.
- Suite completa `tests/`: **`1165 passed, 0 failed`**, sin skips, sin xfail,
  sin warnings, duración ~11.99s.

## Componentes protegidos

- `bin/visual_plan_v2.py`, `bin/run_job.py`, `bin/duration_profiles.py`,
  `tests/test_duration_profiles.py`, `tests/test_run_job.py`,
  `tests/test_generate_script.py`: diff vacío (baseline de hash legacy
  `6b443dea…` intacta).
- `MAX_SCRIPT_ATTEMPTS == 3` confirmado (`bin/generate_script.py:350`).
- Jobs históricos (`cmo-2026-08-02-192443`, `-204451`, `-08-04-195654`) sin
  cambios.

## Documentación

- `openspec/changes/retire-legacy-visual-v1/tasks.md`: nueva subsección de
  política temporal con checklist; estado de cierre actualizado.
- `docs/project/current-state.md`: sección «Slice 6B — Corrección de política
  temporal», resumen y próximos pasos actualizados.
- `docs/sessions/20260804-215808-retire-legacy-visual-v1-slice-6b-third-canonical-e2e.md`:
  sección «Auditoría de política temporal» y referencia a esta sesión.
- Este session log.

## Estado Git final

- Rama `main`; HEAD `ad86834…` sin cambios.
- Working tree con exactamente 6 archivos modificados (permitidos).
- Staging vacío; cero commit, cero push, cero amend/reset/rebase.
- `git diff --check` limpio.
- Cero MCP, cero reindexado.

# Review read-only

- Verdict: `SLICE_6B_DURATION_POLICY_FIX_REVIEW_CHANGES_REQUIRED`.
- La arquitectura funcional de la corrección de política temporal quedó
  **aprobada**.
- **Único finding MEDIUM (bloqueante):** el compression prompt mantenía un
  placeholder sin interpolar en `_build_voiceover_compression_prompt`:
  `"- Revisa que el total final esté entre {min_w} y {max_w}."` literal.
- **LOWs no bloqueantes aceptados:**
  - mínimo de siete palabras como guidance de generación completa
    (`SYSTEM_PROMPT_V2`, `_build_duration_prompt_instruction_v2`,
    `_build_retry_instruction_v2`) — no es hard gate del repair;
  - telemetría nullable/aliases (`sceneWordCapsEnforced`,
    `sceneWordCapsDeprecated`, `repairGlobalBudgetValid`) en estrategias
    no-repair/shape-invalid.
- **Corrección posterior aplicada:** la línea pasó a f-string
  (`f"- Revisa que el total final esté entre {min_w} y {max_w}."`), renderizando
  valores reales (`Revisa que el total final esté entre 47 y 52.` para el perfil
  de 30s). `tests/test_generate_script_v2.py::TestDurationRetryConvergence::test_t2_compression_prompt_contains_previous_attempt`
  ampliado con aserciones de ausencia de `{min_w}`/`{max_w}`/`{expected}` y
  presencia de `47`/`52` y de la frase exacta.
- Resultado de tests tras la corrección: suite completa **`1165 passed, 0
  failed`**; `test_generate_script_v2.py` = 140; combinada generación = 186;
  `test_run_job.py` = 91.
- Cero E2E ejecutado durante la corrección. La corrección queda pendiente de
  reaprobación read-only, commit y cuarto E2E V2 canónico.

## Próximos pasos

1. Reaprobación read-only focalizada de la corrección de política temporal.
2. Commit de la corrección de política temporal.
3. Cuarto E2E V2 canónico.
4. Tras un PASS completo, auditoría y cierre formal del change
   `retire-legacy-visual-v1`.

## Verdict

`SLICE_6B_DURATION_POLICY_PLACEHOLDER_FIX_READY_FOR_REAPPROVAL`

# Reaprobación final y versionado

- Verdict de reaprobación read-only final: `SLICE_6B_DURATION_POLICY_FINAL_REAPPROVED_FOR_COMMIT`.
- Cero findings HIGH/MEDIUM en la corrección de política temporal.
- LOWs aceptados como no bloqueantes: el mínimo de siete palabras como guidance de
  generación completa y la telemetría nullable/aliases en estrategias no-repair.
- Baseline funcional vigente: **`1165 passed, 0 failed`**.
- Commit A: completo `d3779327145d567971144f1cd67949ba2f6eb8e7`; corto `d377932`.
- Asunto: `fix(script): refine V2 duration compression policy`.
- Dos archivos: `bin/generate_script.py` y `tests/test_generate_script_v2.py`.
- Cuarto E2E V2 canónico pendiente. Slice 6B y el change `retire-legacy-visual-v1`
  continúan abiertos.
