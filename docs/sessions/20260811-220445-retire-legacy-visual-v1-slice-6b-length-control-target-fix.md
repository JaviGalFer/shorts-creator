# Slice 6B — Fix F1 del length-control hardening (target inicial)

## 1. Configuración

- Sesión: `retire-legacy-visual-v1-slice-6b-length-control-target-fix`
- Modelo: `opencode/deepseek-v4-flash-free`; variante `default`
- Modo: `Build`; máximo 16 pasos; cero subagentes.
- Codebase Memory MCP: DESACTIVADO; cero llamadas MCP.
- Reindexado: no.

## 2. Git inicial

- Rama: `main`; HEAD `d62c76a233774fefcb37f39fb2aac6f0039d4848`
- Staging vacío; `git diff --check` limpio.
- Working tree exacto: `bin/generate_script.py`, `docs/project/current-state.md`,
  `openspec/changes/retire-legacy-visual-v1/tasks.md`,
  `tests/test_generate_script_v2.py` modificados; dos session logs untracked
  (`20260811-205950-...`, `20260811-213354-...`).

## 3. Review heredado

- `SLICE_6B_LENGTH_CONTROL_HARDENING_REVIEW_CHANGES_REQUIRED`.
- HIGH: 0; F1 MEDIUM (doble target inicial); F2 LOW aceptado; F3 LOW asociado.
- Compression/temperatura/ranking/repair aprobados.

## 4. F1

La generación inicial comunicaba dos objetivos accionables (`≈52` y `50`) aunque
`52` también sea el hard maximum.

## 5. Línea anterior

```
- El total de palabras habladas debe estar entre 47 y 52, con aproximadamente 52 palabras objetivo (pausas entre escenas de ~350ms cada una)
```

## 6. Línea nueva

```
- El total de palabras habladas debe estar entre 47 y 52 (preferredWords del perfil: 52; pausas entre escenas de ~350ms cada una)
```

## 7. Semántica preferred/max/operational

- `preferredWords = 52` — dato/referencia del perfil, no target accionable.
- `maximumWords = 52` — hard boundary.
- `operationalWordTarget = 50` — único target accionable de generación.

## 8. C2 anterior

`TestInitialPromptHardening::test_c2_initial_prompt_contract` verificaba rango
47–52, máximo 52, operational 50, `LÍMITE ABSOLUTO`, `Objetivo operativo`, jerarquía
global > per-scene y autoconteo; no cubría el doble target.

## 9. C2 reforzado

Añadidas aserciones: `aproximadamente 52 palabras objetivo` ausente, `con
aproximadamente` ausente, `preferredWords del perfil: 52` presente (perfil) y
`Objetivo operativo: apunta a 50 ...` presente con `apunta a 52` ausente. Si alguien
restaurara la línea antigua, C2 falla.

## 10. Prompt runtime

```
## Restricción de duración (balanced)
- Duración objetivo: 30 segundos (ventana 27-30)
- El total de palabras habladas debe estar entre 47 y 52 (preferredWords del perfil: 52; pausas entre escenas de ~350ms cada una)
- Escenas: entre 4 y 6. Prefiere 5 escenas.
- Mínimo 7 palabras por escena. Aproximadamente 9-11 palabras por escena.
- El CTA debe incluirse dentro de la voz en off de la última escena, no como escena separada.
- NO uses frases de relleno, CTA repetido, oraciones duplicadas ni pausas dramáticas falsas.

## Presupuesto global de palabras (contrato)
- Rango válido final: 47-52 palabras habladas en total.
- LÍMITE ABSOLUTO: no superes 52 palabras de voiceover en total.
- Objetivo operativo: apunta a 50 palabras de voiceover en total.
- El límite global prevalece sobre cualquier orientación de palabras por escena.
- Cuenta únicamente las palabras de los campos voiceover, separadas por espacios. Antes de responder, autocuenta el total. Si supera 52, recorta el texto antes de devolver el JSON.
```

## 11. Regression checks

- `MAX_SCRIPT_ATTEMPTS == 3`; `minimumWords==47`; `preferredWords==52`;
  `maximumWords==52`; `strictness==balanced`; `operationalWordTarget==50`.
- Temperatura initial 0.8; compression 0.2.
- Compression attempt 1 = 1; attempt 2 = 2.
- 47/50/51/52 siguen siendo duration PASS (dentro del rango); `rank(52) < rank(50)`.

## 12. Tests focalizados

- C2 exacto: `1 passed`.
- C1–C11: `16 passed`.
- `test_generate_script_v2.py`: `156 passed`.

## 13. Suite completa

- `--collect-only tests/`: `1181 tests collected`.
- `pytest -q tests/`: `1181 passed, 0 failed`; cero skipped/xfailed/xpassed;
  cero warnings; duración `11.59s`.

## 14. Documentación

- `openspec/changes/retire-legacy-visual-v1/tasks.md`: bloque de hardening
  actualizado (review `[x]`, fix F1 `[x]`, C2 `[x]`; reaprobación/commit/quinto E2E
  `[ ]`).
- `docs/project/current-state.md`: estado vigente del hardening con F1 corregido;
  frase «presupuesto global inequívoco» corregida para indicar que se implementó
  con F1 y se corrigió en el follow-up.
- Logs cuarto E2E y hardening actualizados.

## 15. Archivos modificados

- `bin/generate_script.py`
- `tests/test_generate_script_v2.py`
- `docs/project/current-state.md`
- `openspec/changes/retire-legacy-visual-v1/tasks.md`
- `docs/sessions/20260811-205950-retire-legacy-visual-v1-slice-6b-fourth-canonical-e2e.md`
- `docs/sessions/20260811-213354-retire-legacy-visual-v1-slice-6b-length-control-hardening.md`
- `docs/sessions/20260811-220445-retire-legacy-visual-v1-slice-6b-length-control-target-fix.md` (este log)

## 16. Git final

- Staging vacío; `git diff --check` limpio; HEAD sigue `d62c76a...`.
- Componentes protegidos sin cambios: `tests/test_generate_script.py`,
  `bin/run_job.py`, `bin/visual_plan_v2.py`, `bin/duration_profiles.py`
  byte-identical.

## 17. Cero E2E

- Cero quinto E2E; cero providers reales (LLM/Wikimedia/Pixabay/Edge TTS);
  cero Docker; cero FFmpeg; cero `bin/run_job.py`; cero MCP; cero reindexado;
  cero staging; cero commit; cero push.

## 18. Próximo paso

- Reaprobación read-only focalizada del length-control hardening; tras
  aprobación, commit del hardening y quinto E2E V2 canónico. Cero PASS todavía;
  Slice 6B abierto; change abierto.

Verdict: `SLICE_6B_LENGTH_CONTROL_TARGET_FIX_READY_FOR_REAPPROVAL`.

# Reaprobación final

- Target único confirmado: `operationalWordTarget = 50` (único target accionable de generación).
- C2 capaz de detectar regresión del doble target (`aproximadamente 52 palabras objetivo` ausente; `preferredWords del perfil: 52` presente; `Objetivo operativo: apunta a 50` con `apunta a 52` ausente).
- Baseline: `1181 passed, 0 failed`.
- Verdict: `SLICE_6B_LENGTH_CONTROL_TARGET_FIX_REAPPROVED_FOR_COMMIT`.
- Commit A completo: `bafb2d5b8397d9b745f24bdc9153a016f1ac6383`; corto `bafb2d5` (asunto `fix(script): harden V2 word-budget control`).
- Cero quinto E2E.
