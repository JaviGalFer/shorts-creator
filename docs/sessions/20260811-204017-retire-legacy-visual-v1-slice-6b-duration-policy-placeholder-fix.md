# Slice 6B — Fix placeholder del compression prompt (policy placeholder fix)

- **Sesión:** `retire-legacy-visual-v1-slice-6b-duration-policy-placeholder-fix`
- **Modelo:** `opencode/deepseek-v4-flash-free` (variante `default`)
- **Modo:** Build
- **Fecha:** 2026-08-11T20:40:17+02:00

## Configuración

- Máximo de pasos agentic: 14; subagentes: ninguno.
- Codebase Memory MCP: DESACTIVADO; 0 llamadas MCP.
- Reindexado: no.
- No se ejecutó el cuarto E2E; no se hizo commit; no se cerró formalmente el
  change. Cero push, cero staging.

## Estado Git inicial

- Rama `main`; HEAD `ad86834b414ab5973ffee0d4701fa86ce7b30b47`.
- Staging vacío; `git diff --check` limpio.
- Working tree:
  - `M` bin/generate_script.py
  - `M` docs/project/current-state.md
  - `M` openspec/changes/retire-legacy-visual-v1/tasks.md
  - `M` tests/test_generate_script_v2.py
  - `??` docs/sessions/20260804-215808-retire-legacy-visual-v1-slice-6b-third-canonical-e2e.md
  - `??` docs/sessions/20260804-224050-retire-legacy-visual-v1-slice-6b-duration-policy-fix.md

## Review utilizado

- Verdict: `SLICE_6B_DURATION_POLICY_FIX_REVIEW_CHANGES_REQUIRED`.

## Finding MEDIUM

- Único blocker: placeholder `{min_w}/{max_w}` sin interpolar en
  `_build_voiceover_compression_prompt`:
  `"- Revisa que el total final esté entre {min_w} y {max_w}."` literal.
- Resultado runtime incorrecto:
  `Revisa que el total final esté entre {min_w} y {max_w}.`
- LOWs no bloqueantes aceptados: mínimo siete como guidance de generación
  completa; telemetría nullable/aliases en estrategias no-repair.

## Cambio productivo

- En `bin/generate_script.py`, dentro de `_build_voiceover_compression_prompt`,
  la línea:
  `"- Revisa que el total final esté entre {min_w} y {max_w}."`
  cambió a:
  `f"- Revisa que el total final esté entre {min_w} y {max_w}."`
- Únicamente se añadió el prefijo `f`. No se reformateó la función ni se tocaron
  otros strings.

## Test de regresión

- `tests/test_generate_script_v2.py::TestDurationRetryConvergence::test_t2_compression_prompt_contains_previous_attempt`
  ampliado (no añadido) con:
  - `assert "Revisa que el total final esté entre 47 y 52." in prompt`
  - `assert "47" in prompt`
  - `assert "52" in prompt`
  - `assert "{min_w}" not in prompt`
  - `assert "{max_w}" not in prompt`
  - `assert "{expected}" not in prompt`
- Mantiene cobertura de `expected sceneNumbers`, `currentWordCount`,
  `requiredReductionWords` y `recommendedTargetWords`.
- Fallaría con el código anterior (placeholders literales) y pasa tras el `f`.

## Prompt runtime antes/después

- Antes: `Revisa que el total final esté entre {min_w} y {max_w}.`
- Después (perfil 30s): `Revisa que el total final esté entre 47 y 52.`
- Prueba directa hermética: `{min_w}` ausente, `{max_w}` ausente,
  `{expected}` ausente; `"entre 47 y 52"` presente; caso canónico conserva
  `currentWordCount = 56`, `requiredReductionWords = 4`, targets
  `[12,12,9,7,12]`.

## Tests focalizados

- `test_generate_script_v2.py::TestDurationRetryConvergence::test_t2_compression_prompt_contains_previous_attempt`:
  `1 passed`.
- `test_generate_script_v2.py`: `140 passed`.
- Generación combinada (`test_generate_script.py` + `test_generate_script_v2.py`
  + `test_duration_profiles.py` + `test_v2_only_generation_contract.py`):
  `186 passed`.
- `test_run_job.py`: `91 passed`.

## Suite completa

- Collect-only: `1165 tests collected`, cero errores.
- Suite completa: **`1165 passed, 0 failed`** en 11.75s. Cero skips, cero xfail,
  cero warnings.

## Componentes protegidos

- `git diff --name-only` sobre `visual_plan_v2.py`, `run_job.py`,
  `duration_profiles.py`, `test_duration_profiles.py`, `test_run_job.py`,
  `test_generate_script.py`: vacío.
- `MAX_SCRIPT_ATTEMPTS == 3`; `minimumWords=47` / `preferredWords=52` /
  `maximumWords=52` confirmados.
- Targets dinámicos, repair shape-only, convergencia monotónica, anti-regresión,
  best attempt y telemetría intactos (policy-critical tests verdes).

## Documentación

- `openspec/changes/retire-legacy-visual-v1/tasks.md`: checklist de política
  actualizado (review marcado, placeholder corregido, cobertura añadida;
  reaprobación/commit/cuarto E2E pendientes).
- `docs/project/current-state.md`: sección «Slice 6B — Corrección de política
  temporal», resumen y próximos pasos actualizados con el review CHANGES_REQUIRED,
  la corrección del placeholder y el baseline vigente.
- `docs/sessions/20260804-224050-retire-legacy-visual-v1-slice-6b-duration-policy-fix.md`:
  añadida sección `# Review read-only`.
- `docs/sessions/20260804-215808-retire-legacy-visual-v1-slice-6b-third-canonical-e2e.md`:
  añadida nota histórica de follow-up.
- Este session log.

## Estado Git final

- Rama `main`; HEAD `ad86834…` sin cambios; staging vacío.
- `git diff --check` limpio.
- 4 archivos tracked modificados + 3 logs untracked.
- Ningún archivo de runner/validator/perfiles; ningún job modificado.
- Cero commit, cero push, cero amend/reset/rebase; cero MCP, cero reindexado.

## Cero E2E

- No se ejecutó el cuarto E2E. Cero PASS. Slice 6B y el change
  `retire-legacy-visual-v1` continúan abiertos.

## Próximo paso

1. Reaprobación read-only focalizada de la corrección de política temporal.
2. Commit de la corrección de política temporal.
3. Cuarto E2E V2 canónico.
4. Tras un PASS completo, auditoría y cierre formal del change.

## Verdict

`SLICE_6B_DURATION_POLICY_PLACEHOLDER_FIX_READY_FOR_REAPPROVAL`

# Reaprobación final

- f-string confirmado en `bin/generate_script.py:916`
  (`f"- Revisa que el total final esté entre {min_w} y {max_w}."`).
- Test de regresión confirmado:
  `tests/test_generate_script_v2.py::TestDurationRetryConvergence::test_t2_compression_prompt_contains_previous_attempt`
  (`1 passed`).
- Baseline funcional: **`1165 passed, 0 failed`**.
- Verdict final: `SLICE_6B_DURATION_POLICY_FINAL_REAPPROVED_FOR_COMMIT`.
- Commit A: `d377932` (`fix(script): refine V2 duration compression policy`).
- Cero cuarto E2E. Slice 6B y el change continúan abiertos.
