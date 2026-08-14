# Session — Slice 6B length-control hardening (Build)

Timestamp: 2026-08-11T21:33:54+02:00
Session: `retire-legacy-visual-v1-slice-6b-length-control-hardening`
Modo: Build. Modelo: `opencode/deepseek-v4-flash-free` (variante `default`).

## 1. Configuración

- Sesión: `retire-legacy-visual-v1-slice-6b-length-control-hardening`
- Modo: Build; subagentes: ninguno; MCP: DESACTIVADO (0 llamadas); reindexado: no.
- No se ejecuta quinto E2E; no se hace commit; no se cierra Slice 6B ni el change.

## 2. Git inicial

- Rama `main`; HEAD `d62c76a233774fefcb37f39fb2aac6f0039d4848`.
- Staging vacío; `git diff --check` limpio.
- Working tree exacto: `M docs/project/current-state.md`, `M
  openspec/changes/retire-legacy-visual-v1/tasks.md`, `??
  docs/sessions/20260811-205950-...-fourth-canonical-e2e.md`.
- Sin cambios en `bin/ tests/ src/`.

## 3. Auditoría utilizada

- `SLICE_6B_COMPRESSION_CONTROL_AUDIT_RECOMMENDS_CHANGES` (auditoría read-only
  del cuarto E2E).

## 4. Diagnóstico

- La política de candidatos funcionó en el cuarto E2E (`69→63→62`): candidatos
  shape-valid, canonicalización correcta, ranking monotónico, `candidateUpdated=true`,
  targets por escena orientativos, sin hard caps ni mínimo duro, best candidate y
  anti-regresión correctos. El problema restante es el control de
  generación/compliance del LLM.

## 5. Initial overshoot

- Los cuatro E2E reales produjeron candidatos iniciales por encima del máximo:
  `74, 60, 56, 69`; overshoot frente a 52: `+22, +8, +4, +17`.
- Cuarto E2E: compresión real `69→63→62`; reducción global `7/17 ≈ 41%`.

## 6. Operational target

- Helper puro `_compute_operational_word_target(budget)`.
- Semántica: guidance de generación, NO contrato; no sustituye a
  `preferredWords` ni `maximumWords`; siempre dentro de
  `[minimumWords, maximumWords]`; margen respecto al techo cuando `preferredWords`
  está pegado al máximo.
- No cambia `calculate_word_budget()`.

## 7. Algoritmo del target

- `midpoint = ceil((min_w + max_w) / 2)`
- `operational = min(max(pref_w, min_w), midpoint, max_w)`; `operational = max(min_w, operational)`.
- Defensivo: `max_w <= 0` o `max_w < min_w` → retorno acotado sin crash.

## 8. Caso 47/52/52 → 50

- Para `minimumWords=47 / preferredWords=52 / maximumWords=52`:
  `midpoint = ceil(99/2) = 50`; `min(max(52,47),50,52) = 50` → `operationalWordTarget = 50`.
- Hard range 47–52; operational target 50.

## 9. Otros casos del helper

- `47/50/52 → 50`; `47/49/52 → 49`; `52/52/52 → 52`.
- Defensivo: `52/52/47 → 0` (max < min); `47/52/0 → 0` (max <= 0).

## 10. Initial hardening

- `_build_duration_prompt_instruction_v2` añade el bloque `Presupuesto global de
  palabras (contrato)`: rango válido final, LÍMITE ABSOLUTO, objetivo operativo,
  jerarquía global > per-scene y autoconteo de voiceovers.
- Se conserva la referencia `Mínimo 7 palabras por escena` como guidance.
- La temperatura inicial permanece 0.8.

## 11. Compression system hardening

- `VOICEOVER_COMPRESSION_SYSTEM_PROMPT` añade primacía del presupuesto global,
  `nunca devuelvas un total superior a maximumWords`, conteo de palabras, seguir
  recortando y targets por escena como recomendación; sigue limitado a
  `sceneNumber`/`voiceover` sin exigir guion completo.

## 12. Compression user hardening

- `_build_voiceover_compression_prompt` añade el bloque imperativo
  `CONTRATO DE COMPRESIÓN — PRIORIDAD MÁXIMA` (candidato actual, límite absoluto,
  reducción mínima obligatoria, `N+1 o más incumple`, objetivo operativo y
  reducción deseada) y campos informativos (`currentWordCount`, `minimumWords`,
  `preferredWords`, `maximumWords`, `operationalWordTarget`,
  `minimumRequiredReductionWords`, `desiredReductionWords`; `requiredReductionWords`
  conservado como alias).
- Dos conceptos diferenciados:
  - `minimumRequiredReductionWords = max(0, actual - max)`;
  - `desiredReductionWords = max(0, actual - operational_target)`.
- Caso real 69→max52: mínimo 17 / deseado 19 (target 50). Caso 63→max52:
  mínimo 11 / deseado 13.

## 13. Temperature routing

- `DEFAULT_LLM_TEMPERATURE = 0.8`; `COMPRESSION_LLM_TEMPERATURE = 0.2`.
- `_llm_temperature_for_system_prompt(system_prompt)` → 0.2 para
  `VOICEOVER_COMPRESSION_SYSTEM_PROMPT`, 0.8 para el resto.
- `call_llm` conserva su firma pública; no se añade `temperature=` en `main()`.

## 14. Escalado del segundo intento

- `compression_attempt >= 2` añade `SEGUNDO INTENTO DE COMPRESIÓN` con el
  incumplimiento anterior y las palabras restantes; sin metadata histórica nueva.
- El primer compression attempt no menciona una compresión anterior fallida.

## 15. Contratos preservados

- `MAX_SCRIPT_ATTEMPTS == 3`; `47/52/52`; `strictness=balanced`.
- Targets por escena como guidance; presupuesto global como único hard duration
  gate; repair shape-only; candidato canónico; ranking actual; best candidate;
  anti-regresión; PASS inmediato dentro del rango.
- No se restauran `MIN_WORDS_PER_SCENE`, `REPAIR_SCENE_WORD_CAP_EXCEEDED` ni
  `REPAIR_SCENE_WORD_MINIMUM_NOT_MET`.
- No se implementa cuarto retry, hard caps por escena, truncado local ni
  eliminación heurística de frases.
- Metadata sin ampliación (el target operativo se deriva del budget).

## 16. Tests C1–C11

- Añadidos en `tests/test_generate_script_v2.py`:
  - C1 target operativo (casos canónicos + defensivos);
  - C2 prompt inicial (hard max 52 vs operational 50, jerarquía global, autoconteo);
  - C3 system prompt compression (presupuesto global, maximumWords, nunca superior,
    contar palabras, seguir recortando, targets como recomendación);
  - C4 temperatura hermética (SYSTEM_PROMPT_V2→0.8, compression→0.2, None→0.8);
  - C5 primer compression prompt (69→min 17, target 50, deseado 19, sin escalado);
  - C6 segundo compression prompt (63→min 11, target 50, deseado 13, escalado);
  - C7 placeholders ausentes (compression + initial);
  - C8 temperatura initial sigue 0.8;
  - C9 convergencia 69→63→52 (PASS; segundo prompt desde 63 canónico);
  - C10 anti-regresión 69→70→52;
  - C11 invariantes de contrato (global PASS con scene target incumplido;
    `MAX_SCRIPT_ATTEMPTS == 3`).

## 17. Focalizados

- Nuevos tests C1–C11: `16 passed`.
- `test_generate_script_v2.py`: `156 passed` (anterior `140`; +16).
- Combinada generación (`test_generate_script.py` + `test_generate_script_v2.py`
  + `test_duration_profiles.py` + `test_v2_only_generation_contract.py`):
  `202 passed` (anterior `186`).
- `test_run_job.py`: `91 passed` (sin cambios).

## 18. Suite completa

- Collect-only: `1181 tests collected`, cero errores de colección.
- Suite completa: **`1181 passed, 0 failed`** (anterior `1165`; +16). Cero
  skips, cero xfail, cero xpassed, cero warnings. Duración ~11.7s.
- Validator, runner y perfiles intactos.

## 19. Documentación

- `openspec/changes/retire-legacy-visual-v1/tasks.md`: checklist del hardening
  (C1–C11 marcado, review/commit/quinto E2E pendientes) y wording stale del
  cuarto E2E corregido.
- `docs/project/current-state.md`: resumen global, sección del hardening, resumen
  de Slice 6B y próximos pasos actualizados.
- `docs/sessions/20260811-205950-...-fourth-canonical-e2e.md`: sección
  `Auditoría de control de generación` añadida; resultado BLOCKED histórico no
  alterado.

## 20. Archivos modificados

- `bin/generate_script.py`
- `tests/test_generate_script_v2.py`
- `docs/project/current-state.md`
- `openspec/changes/retire-legacy-visual-v1/tasks.md`
- `docs/sessions/20260811-205950-retire-legacy-visual-v1-slice-6b-fourth-canonical-e2e.md`
- `docs/sessions/20260811-213354-retire-legacy-visual-v1-slice-6b-length-control-hardening.md` (este log)

## 21. Git final

- Staging vacío; `git diff --check` limpio; HEAD sigue `d62c76a...`.
- Solo los seis archivos autorizados modificados. `tests/test_generate_script.py`
  byte-identical (hash `6b443deaaee6f2ab7e7c6354c2736d4609eadd10ec926a403d13d071dbfbe24c`).

## 22. Cero E2E

- Cero quinto E2E; cero providers reales (LLM/Wikimedia/Pixabay/Edge TTS);
  cero Docker; cero FFmpeg; cero `bin/run_job.py`; cero MCP; cero reindexado;
  cero staging; cero commit; cero push.

## 23. Próximo paso

- Review read-only del length-control hardening; tras aprobación, commit del
  hardening y quinto E2E V2 canónico. Cero PASS todavía; Slice 6B abierto; change abierto.

Verdict: `SLICE_6B_LENGTH_CONTROL_HARDENING_READY_FOR_REVIEW`.

# Review read-only

- Verdict: `SLICE_6B_LENGTH_CONTROL_HARDENING_REVIEW_CHANGES_REQUIRED`.
- HIGH: 0.
- **F1 MEDIUM:** la generación inicial presentaba el doble target accionable
  `preferredWords≈52` (formulado como objetivo) junto al operational target `50`.
  El resto del diseño quedó aprobado: compression system/user prompt, temperatura
  (0.8/0.2), attempt wiring (1 y 2), escalado del segundo intento, candidato
  canónico, repair shape-only, ranking, best candidate, anti-regresión y
  operational target como no-gate.
- **F2 LOW** aceptado y no corregido (branch defensivo de
  `_compute_operational_word_target`; input inalcanzable en runtime productivo).
- **F3 LOW** asociado: la documentación sobreafirmaba el presupuesto inicial como
  inequívoco.
- **Fix aplicado posteriormente** (follow-up `length-control-target-fix`):
  la generación inicial ya no expone `preferredWords` como target accionable;
  `preferredWords=52` queda como dato del perfil, `maximumWords=52` como hard
  boundary y `operationalWordTarget=50` como único target accionable.
- **C2 reforzado** contra el doble target (`aproximadamente 52 palabras objetivo`
  ausente; `preferredWords del perfil: 52` presente; `Objetivo operativo` solo con
  `50`).
- **Baseline:** `1181 passed, 0 failed`.
- Cero quinto E2E.

# Reaprobación final y versionado

- Verdict de reaprobación read-only final: `SLICE_6B_LENGTH_CONTROL_TARGET_FIX_REAPPROVED_FOR_COMMIT`.
- F1 resuelto (la generación inicial ya no expone `preferredWords` como target accionable; `50` es el único target accionable).
- F2 LOW aceptado (branch defensivo de `_compute_operational_word_target`; no corregido).
- Cero nuevos findings HIGH/MEDIUM.
- Baseline: `1181 passed, 0 failed`.
- Commit A completo: `bafb2d5b8397d9b745f24bdc9153a016f1ac6383`; corto `bafb2d5`.
- Asunto: `fix(script): harden V2 word-budget control`.
- Archivos Commit A (exactamente dos): `bin/generate_script.py`, `tests/test_generate_script_v2.py`.
- Quinto E2E V2 canónico pendiente.
