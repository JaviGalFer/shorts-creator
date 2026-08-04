# Sesión: Slice 6B — Retry temporal de duración (Build)

- Timestamp: `20260804-201703`
- ISO: `2026-08-04T20:17:03+02:00`
- Modelo: `opencode/deepseek-v4-flash-free`, variante `default`
- Modo: `Build`

## 1. Configuración

- Sesión: `retire-legacy-visual-v1-slice-6b-duration-retry-fix`
- Alcance: corregir la falta de convergencia del retry temporal detectada en el
  segundo E2E V2 canónico (exceso de palabras 69 > 52).
- Codebase Memory MCP: DESACTIVADO (0 llamadas).
- Subagentes: ninguno.

## 2. Estado Git inicial

- Rama: `main`
- HEAD: `e5e2a4eb25746bf10645e0c1c2fe458482bedc48`
- Historial: `e5e2a4e` (record Slice 6B script fix commit), `f48f98f` (fix
  prompt/retry), `496dd33`, `86170d3`.
- Staging: vacío.
- Sin stagear (preexistente):
  - `M docs/project/current-state.md`
  - `M openspec/changes/retire-legacy-visual-v1/tasks.md`
  - `?? docs/sessions/20260802-224326-retire-legacy-visual-v1-slice-6b-canonical-e2e-rerun.md`
- `bin/`, `tests/`, `src/` sin cambios.
- `git diff --check` limpio.
- Warning no bloqueante: permisos de `data/postgres/`.

## 3. Evidencia de ambos jobs

- Primer E2E (`cmo-2026-08-02-192443`): BLOCKED en `script` por enums V2
  inválidos (`animation`/`infographic`) + duración.
- Segundo E2E (`cmo-2026-08-02-204451`): BLOCKED únicamente por duración
  `DURATION_OUT_OF_RANGE` (69 > 52); contrato visual corregido
  (`structureValid=true`, cero enums inválidos, `allowGeneratedImages=false`).
- Retry history del segundo E2E: `60 → 56 → 69`.

## 4. Diagnóstico

Auditoría read-only del segundo E2E: `SLICE_6B_DURATION_REVIEW_CHANGES_REQUIRED`.

- D1 regeneración completa estocástica; D2 el retry no recibe el texto anterior;
  D3 sin reparto estricto del budget; D4 se pedía preservar campos no
  proporcionados; D6 sin protección anti-regresión; D7 cobertura insuficiente.
- D8 (incumplimiento del modelo) como factor contribuyente.

## 5. Separación retry estructural/temporal

`bin/generate_script.py`:

- Estructura inválida (`v2_valid == false`): regeneración completa contractual
  (`strategy="structural"`), conservando enum, paths, mensajes y gate de
  `generated`.
- Estructura válida + exceso (`v2_valid == true`, `wordCount > maximumWords`):
  retry especializado de compresión de voiceovers (`strategy="compression"`).
- Estructura válida, sin exceso: estrategia vigente (`strategy="duration"`,
  `expand_content`) preservada.

## 6. Distribución de caps

`_allocate_scene_word_caps(maximum_words, scene_count)`: reparto determinista,
suma exacta, `max - min <= 1`, caps enteros positivos.

- 52/4 → `[13,13,13,13]`
- 52/5 → `[11,11,10,10,10]`
- 52/6 → `[9,9,9,9,8,8]`

## 7. Prompt especializado

`_build_voiceover_compression_prompt(...)`: incluye `sceneNumber`,
`currentVoiceover`, `maximumWords` por escena, contador `str.split()`,
mínimo/máximo global, caps exactos, formato de salida reducido
(`{"scenes":[{"sceneNumber":1,"voiceover":"..."}]}`), prohibición de campos
adicionales y nota de que las restricciones visuales no son editables durante la
reparación.

## 8. Parseo y merge seguro

`_apply_voiceover_repair(base_script, payload, expected_scene_numbers=...)`:
trabaja sobre `copy.deepcopy`; sustituye únicamente `scenes[i].voiceover`;
rechaza payload no objeto, campos top-level adicionales, `scenes` no lista,
escenas faltantes/extra/duplicadas, orden incorrecto, voiceover vacío/no string
y campos adicionales por item. Devuelve errores estructurados.

## 9. Inmutabilidad

- El input original no se muta (T3 compara antes/después con `voiceover` como
  única diferencia y verifica que el original permanece idéntico).
- T8 verifica que un payload hostil (`visualPlan`/`subtitle`/`title`) se rechaza
  y nunca se aplica.

## 10. Best attempt

- Solo participan scripts `structureValid == true`.
- Métrica: `_distance_to_allowed_range` (0 en rango; diferencia respecto al
  mínimo o máximo fuera de rango).
- Empate: menor distancia a `preferredWords`; empate completo conserva el
  anterior.
- La protección aplica únicamente al agotamiento sin PASS; el bucle termina
  inmediatamente al encontrar PASS.

## 11. Retry history

- `retryHistory` ampliado: `attempt`, `strategy`, `wordCount`, `structureValid`,
  `durationStatus`, `sceneWordCounts`, `sceneWordCaps`,
  `distanceToAllowedRange`, `acceptedAsBest`, `repairPayloadValid`.
- `durationContract` ampliado: `bestAttempt`, `bestAttemptWordCount`,
  `lastAttemptDiscardedAsRegression`.
- Trazabilidad permite reconstruir `60 → 56 → 69` y `best=56`.

## 12. Tests añadidos

`tests/test_generate_script_v2.py` 92 → 113:

- T1 caps deterministas (4/5/6 escenas, suma exacta, `max - min <= 1`).
- T2 prompt de compresión (sceneNumber, voiceover, caps, `str.split()`,
  mín/máx, formato reducido, prohibición).
- T3 merge solo voiceover (antes/después idéntico salvo voiceover; input no
  mutado).
- T4 payloads inválidos parametrizados (ausente, extra, duplicada, orden,
  vacío, no string, campo extra, top-level extra, `scenes` no lista).
- T5/T6 flujos integrados 60→50 y 60→56→69 (best=56, `bestAttempt=1`).
- T7 no perder PASS (solo dos llamadas; tercer mock no consumido).
- T8 visual plan inmutable ante payload hostil.
- T9 caps por escena respetados y suma global <= 52.
- T10 estructura inválida mantiene retry completo (`strategy="structural"`).
- T11 cubierto por el test existente `MAX_SCRIPT_ATTEMPTS == 3`.
- T12 agotamiento sin candidato estructural válido inventa nada
  (`bestAttempt=None`, `VISUAL_PLAN_V2_INVALID`).

`tests/test_generate_script.py`: el test legacy
`test_main_retry_loop_3_attempts_3rd_succeeds` codificaba el comportamiento
antiguo de regeneración completa en exceso de palabras; se actualizó al nuevo
flujo de compresión. Desviación de alcance documentada: el archivo no estaba en
la lista de autorizados, pero es requisito para mantener la baseline.

## 13. Resultados focalizados

- `test_generate_script_v2.py`: **113 passed**.
- Generación combinada (`test_generate_script.py` + `test_generate_script_v2.py`
  + `test_duration_profiles.py` + `test_v2_only_generation_contract.py`):
  **159 passed**.
- `test_run_job.py`: **91 passed**.

## 14. Collect-only

- `1138 tests collected`, cero errores de colección.

## 15. Suite completa

- `1138 passed, 0 failed`.

## 16. Baseline nueva

- Baseline vigente: **`1138 passed, 0 failed`** (anterior `1117`; +21 tests).

## 17. Documentación corregida

- `openspec/changes/retire-legacy-visual-v1/tasks.md`: F8 corregido (párrafos
  que afirmaban pendientes reaprobación/commit/segundo E2E convertidos a historia
  explícita); secuencia de follow-up temporal añadida.
- `docs/project/current-state.md`: F9 corregido (numeración duplicada `8.`);
  sección Slice 6B temporal añadida; resumen y próximos pasos actualizados;
  fecha `2026-08-04`.
- Session log del segundo E2E: sección «Auditoría read-only del retry temporal»
  añadida (verdict, F1–F9, D1–D8, decisiones, estado del job intacto).

## 18. Archivos modificados

- `bin/generate_script.py`
- `tests/test_generate_script_v2.py`
- `tests/test_generate_script.py` (desviación de alcance documentada)
- `docs/project/current-state.md`
- `openspec/changes/retire-legacy-visual-v1/tasks.md`
- `docs/sessions/20260802-224326-retire-legacy-visual-v1-slice-6b-canonical-e2e-rerun.md`
- `docs/sessions/20260804-201703-retire-legacy-visual-v1-slice-6b-duration-retry-fix.md` (este log)

## 19. Estado Git final

- Rama `main`; HEAD sin cambios `e5e2a4eb25746bf10645e0c1c2fe458482bedc48`.
- Staging: 0.
- `git diff --check` limpio.
- Solo los archivos autorizados (más la desviación documentada de
  `tests/test_generate_script.py`).

## 20. Cero E2E

No se ejecutó ningún E2E. No se tocó ningún job.

## 21. Próximo paso

- Review read-only de la corrección temporal.
- Commit de la corrección temporal.
- Siguiente E2E V2 canónico.
- Tras un E2E PASS, auditoría y cierre formal del change.

---

# Auditoría read-only del Build

Sesión posterior: `retire-legacy-visual-v1-slice-6b-duration-retry-review-fixes`.

- La auditoría read-only de la corrección temporal terminó con
  `SLICE_6B_DURATION_FIX_REVIEW_CHANGES_REQUIRED`.
- Findings:
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
  - **F7 LOW** — `acceptedAsBest` significaba best-so-far y podía quedar `true`
    en varios intentos.
- Se requiere una corrección adicional.
- Cero commit. Baseline anterior `1138 passed, 0 failed` conservada como
  resultado histórico del Build.

# Follow-up de correcciones del review

- Aplicadas las correcciones F1–F7 (sesión
  `retire-legacy-visual-v1-slice-6b-duration-retry-review-fixes`):
  - F1: system prompt dedicado `VOICEOVER_COMPRESSION_SYSTEM_PROMPT`, selección
    por estrategia.
  - F2: `{expected}` interpolado a la secuencia real.
  - F3: enforcement de caps y mínimo por escena; semántica
    `repairShapeValid`/`repairBudgetValid`/`repairPayloadValid`.
  - F4: flag `lastAttemptDiscardedAsRegression` corregido vía `_candidate_rank`.
  - F5: representación canónica siempre participa y se persiste.
  - F6: telemetría de payload rechazado (`candidateReused`, `wordCountSource`).
  - F7: `acceptedAsBest` final inequívoco.
- Resultados reales (suite completa): **`1155 passed, 0 failed`** (baseline
  anterior `1138`; +17 tests). Cero skips, cero xfail, cero warnings.
- Validator, runner y perfiles intactos. `MAX_SCRIPT_ATTEMPTS == 3`.
- Pendiente: reaprobación read-only focalizada, commit y siguiente E2E V2
  canónico.

# Primera reaprobación del follow-up

- La primera reaprobación read-only focalizada de la corrección temporal terminó
  con `SLICE_6B_DURATION_REVIEW_FIXES_REAPPROVAL_CHANGES_REQUIRED`.
- **F8 MEDIUM bloqueante**: el compression prompt (`_build_voiceover_compression_prompt`)
  y el merge (`_apply_voiceover_repair`) recibían la representación raw en lugar
  de la canónica, pese a que `canonical` ya estaba disponible cuando
  `v2_valid == true`.
- **F9–F11 LOW** no bloqueantes (F9 aceptado; F10 gaps de cobertura; F11 tracking
  documental incorrectamente descrito).
- Resultados históricos del Build no reescritos. Ningún commit; ningún E2E.

# Corrección canónica F8

Sesión posterior: `retire-legacy-visual-v1-slice-6b-duration-canonical-followup`.

- Introducida una representación activa única y canónica (`candidate_script`):
  cuando `v2_valid == true`, `candidate_script = canonical`; la representación
  raw deja de participar en el flujo de un candidato estructuralmente válido.
- `candidate_script` alimenta `_count_voiceover_words`, `_scene_word_counts`,
  `scene_count`, el best candidate, `_build_voiceover_compression_prompt` y
  `_apply_voiceover_repair` (base del merge), el siguiente retry y la
  persistencia al agotar sin PASS.
- Cuando la estructura es inválida no se inventa un candidato canónico: se
  conserva el retry estructural y la respuesta raw se usa únicamente como
  evidencia de errores; no se entra en compression.
- Tras un repair válido, el resultado parte de una copia profunda del candidato
  canónico, modifica únicamente `voiceover` y continúa siendo la representación
  activa; no recupera campos raw.
- Tests añadidos (133 en `test_generate_script_v2.py`): compression prompt
  recibe candidato canónico; base del merge canonicalizada; seis escenas en el
  prompt.
- Resultados reales (suite completa): **`1158 passed, 0 failed`** (baseline
  anterior `1155`; +3 tests). Cero skips, cero xfail, cero warnings.
- Validator, runner y perfiles intactos. `MAX_SCRIPT_ATTEMPTS == 3`.
- Pendiente: reaprobación final read-only, commit y siguiente E2E V2 canónico.
