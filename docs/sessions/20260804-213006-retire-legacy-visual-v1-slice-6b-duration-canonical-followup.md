# Sesión — retiro de legacy visual V1 · Slice 6B · Follow-up canónico (F8)

## 1. Configuración

- Sesión: `retire-legacy-visual-v1-slice-6b-duration-canonical-followup`
- Modelo: `opencode/deepseek-v4-flash-free` (variante `default`)
- Modo: `Build`
- Subagentes: ninguno
- Codebase Memory MCP: DESACTIVADO (0 llamadas)
- Reindexado: no

## 2. Estado Git inicial

- Rama `main`; HEAD `e5e2a4eb25746bf10645e0c1c2fe458482bedc48`.
- Últimos commits: `e5e2a4e` (record Slice 6B script fix), `f48f98f` (harden V2 prompt), `496dd33`, `86170d3`.
- Staging: 0.
- Cinco modificados: `bin/generate_script.py`, `docs/project/current-state.md`,
  `openspec/changes/retire-legacy-visual-v1/tasks.md`, `tests/test_generate_script.py`,
  `tests/test_generate_script_v2.py`.
- Tres session logs untracked (`20260802-224326-...`, `20260804-201703-...`,
  `20260804-211148-...`).
- `git diff --check` limpio. Warning de permisos de `data/postgres/` no bloqueante.

## 3. Reaprobación utilizada

Verdict: `SLICE_6B_DURATION_REVIEW_FIXES_REAPPROVAL_CHANGES_REQUIRED`.

- F1 — RESUELTO
- F2 — RESUELTO
- F3 — RESUELTO
- F4 — RESUELTO
- F5 — PARCIAL, convertido en F8 MEDIUM
- F6 — RESUELTO
- F7 — RESUELTO
- F8 — MEDIUM, bloqueante
- F9 — LOW, no bloqueante
- F10 — LOW, gaps de cobertura
- F11 — LOW, tracking documental incorrectamente descrito

## 4. F8

`_build_voiceover_compression_prompt` y `_apply_voiceover_repair` recibían la
representación raw en lugar de la canónica, pese a que `canonical` ya estaba
disponible cuando `v2_valid == true`.

Contrato esperado: la representación canónica debe ser la base del compression
prompt, del merge de voiceovers, del siguiente candidato, del best attempt y de
la persistencia.

## 5. Flujo anterior

Confirmado en `main()`:

- `canonical` está disponible cuando `v2_valid == true` (validación en el retry
  head y tras cada intento).
- Best candidate ya usaba `canonical`.
- Persistencia ya usaba `canonical` (PASS) o `best_candidate` (agotamiento).
- Compression prompt usaba `script_data` (raw).
- Merge usaba `script_data` (raw).

## 6. Candidato canónico activo

Cuando `v2_valid is True` y `canonical is not None`, se define
`candidate_script = canonical`. La representación raw deja de participar en el
flujo de un candidato estructuralmente válido.

`candidate_script` alimenta: `_count_voiceover_words`, `_scene_word_counts`,
`scene_count`, el best candidate, `_build_voiceover_compression_prompt`,
`_apply_voiceover_repair` (base del merge), la construcción del siguiente retry
y la persistencia al agotar sin PASS.

Rama estructural inválida intacta: no se inventa candidato canónico, se conserva
el retry estructural y la respuesta raw se usa únicamente como evidencia de
errores; no se entra en compression.

## 7. Objeto enviado al compression prompt

`_build_voiceover_compression_prompt(candidate_script, ...)` — la representación
canónica. Verificado por test integrado: `visualIntent == "explain"`,
`assetPreferences == ["diagram"]`, `transition == "cut"`, `subjects` sin padding,
`allowGeneratedImage == false`, `preferredProviders == []`, `period == null`,
`location == null`. No recibe la representación raw.

## 8. Objeto enviado al merge

`_apply_voiceover_repair(candidate_script, repair_payload, ...)` — la base del
merge es el candidato canónico. Verificado por test integrado: la base ya está
canonicalizada antes del merge.

## 9. Resultado tras repair

El resultado merged parte de una copia profunda del candidato canónico
(`_apply_voiceover_repair` usa `copy.deepcopy(base_script)`), modifica únicamente
`voiceover` y continúa siendo la representación activa (`script_data = repaired`);
vuelve a pasar por validación/canonicalización en la siguiente iteración y no
recupera campos raw. El objeto base interceptado no se muta.

## 10. Rama estructural sin cambios

Confirmado: cuando la estructura es inválida, no se inventa un candidato
canónico; se conserva el retry estructural y la respuesta raw se usa solo como
evidencia. No se entra en compression.

## 11. Test del compression prompt

`test_f8_canonical_flows_to_compression_prompt`: intercepta
`_build_voiceover_compression_prompt` durante un flujo real de `main()` y
confirma que el objeto recibido es canónico (no la representación raw). Fallaría
si se volviera a pasar `script_data`.

## 12. Test de la base del merge

`test_f8_canonical_base_used_by_merge`: intercepta `_apply_voiceover_repair`
durante un flujo real de `main()`, confirma que `base_script` ya está
canonicalizado, aplica un payload válido y confirma que el resultado conserva la
representación canónica, únicamente cambian los `voiceover`, el `visualPlan` no
vuelve a la forma raw y no se muta el objeto base interceptado.

## 13. Test de seis escenas

`test_f2_expected_interpolated_six_scenes`: `_build_voiceover_compression_prompt`
con seis escenas; `{expected}` no aparece y `[1, 2, 3, 4, 5, 6]` sí aparece.

## 14. Resultados focalizados

- `test_generate_script_v2.py`: **133 passed** (130 → 133; +3 tests).
- Generación combinada (`test_generate_script.py` + `test_generate_script_v2.py`
  + `test_duration_profiles.py` + `test_v2_only_generation_contract.py`): **179 passed**.
- `test_run_job.py`: **91 passed**.

## 15. Suite completa

- Collect-only: `1158 tests collected`, cero errores.
- Suite completa: **`1158 passed, 0 failed`** en 11.67s.
- Cero skips, cero xfail, cero warnings.

## 16. Baseline

Baseline vigente: **`1158 passed, 0 failed`** (baseline anterior `1155`; +3 tests).

## 17. F9 aceptado

F9 queda aceptado provisionalmente como LOW no bloqueante. Registrado
expresamente como:

> LOW aceptado para esta corrección; posible normalización futura a null/N/A.

No se amplía el schema de metadata. No afecta al retry, al PASS ni al best
candidate.

## 18. F11 corregido

En `docs/sessions/20260804-211148-retire-legacy-visual-v1-slice-6b-duration-retry-review-fixes.md`
se corrigió la enumeración que presentaba como `M` los logs `20260802-224326-...`
y `20260804-201703-...`. Ahora reflejan el estado real `??` / UNTRACKED. Se aclara
que los archivos contienen actualizaciones acumuladas en el working tree pero
todavía no están versionados. No se declara ningún commit oculto ni transición de
tracking.

## 19. Documentación

- `tasks.md`: secuencia de la primera reaprobación y del follow-up F8 añadida.
- `current-state.md`: sección «Slice 6B — Follow-up canónico F8», resumen y
  próximos pasos actualizados.
- Log del E2E (`20260802-224326`): sección «Primera reaprobación del follow-up temporal».
- Log del Build temporal (`20260804-201703`): secciones «Primera reaprobación del
  follow-up» y «Corrección canónica F8».
- Log de review fixes (`20260804-211148`): sección «Reaprobación read-only» y
  corrección F11.

## 20. Archivos modificados

- `M bin/generate_script.py`
- `M tests/test_generate_script_v2.py`
- `M docs/project/current-state.md`
- `M openspec/changes/retire-legacy-visual-v1/tasks.md`
- `M tests/test_generate_script.py` (pre-existente del Build anterior; no editado
  en esta sesión; hash inmutable)
- `?? docs/sessions/20260802-224326-retire-legacy-visual-v1-slice-6b-canonical-e2e-rerun.md`
- `?? docs/sessions/20260804-201703-retire-legacy-visual-v1-slice-6b-duration-retry-fix.md`
- `?? docs/sessions/20260804-211148-retire-legacy-visual-v1-slice-6b-duration-retry-review-fixes.md`
- `?? docs/sessions/20260804-213006-retire-legacy-visual-v1-slice-6b-duration-canonical-followup.md` (este log)

Validator (`visual_plan_v2.py`), runner (`run_job.py`), perfiles
(`duration_profiles.py`), `tests/test_duration_profiles.py` y `tests/test_run_job.py`
sin cambios. `MAX_SCRIPT_ATTEMPTS == 3`.

## 21. Estado Git final

- Rama `main`; HEAD `e5e2a4eb25746bf10645e0c1c2fe458482bedc48` (sin cambios).
- Staging: 0.
- Cinco modificados acumulados; cuatro session logs untracked.
- `git diff --check` limpio.
- Hash de `tests/test_generate_script.py` inmutable.

## 22. Cero E2E

No se ejecutó ningún E2E. No se tocó ningún job (`cmo-2026-08-02-192443`,
`cmo-2026-08-02-204451` permanecen intactos). Ningún PASS.

## 23. Próximo paso

- Reaprobación final read-only de la corrección temporal.
- Commit de la corrección temporal.
- Siguiente E2E V2 canónico; tras un PASS, auditoría y cierre formal del change.
- Slice 6B y el change completo continúan abiertos.

## 24. Reaprobación final y cierre mediante commit

- Verdict final de reaprobación: `SLICE_6B_DURATION_CANONICAL_FOLLOWUP_REAPPROVED_FOR_COMMIT`.
- Cero findings bloqueantes.
- F9 aceptado como LOW no bloqueante.
- Baseline vigente: **`1158 passed, 0 failed`**.
- La corrección temporal está cerrada y versionada mediante el Commit A:
  - Hash completo: `9eb1f13e2e70e053cdf968d665c3c705f67e27e2`
  - Hash corto: `9eb1f13`
  - Asunto: `fix(script): harden canonical duration retries`
  - Tres archivos: `bin/generate_script.py`, `tests/test_generate_script.py`,
    `tests/test_generate_script_v2.py`.
- Cero E2E durante el cierre.
- Próximo paso: tercer E2E V2 canónico; tras un PASS, auditoría y cierre formal del change.
- Slice 6B y el change completo continúan abiertos.
