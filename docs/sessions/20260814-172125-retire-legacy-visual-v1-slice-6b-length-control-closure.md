# Slice 6B — Cierre del length-control hardening (Commit A)

## 1. Configuración

- Sesión: `retire-legacy-visual-v1-slice-6b-length-control-closure`
- Modelo: `opencode/deepseek-v4-flash-free`; variante `default`
- Modo: `Build`; máximo 20 pasos; cero subagentes.
- Codebase Memory MCP: DESACTIVADO; cero llamadas MCP.
- Reindexado: no.
- No se implementa funcionalidad nueva; no se ejecuta quinto E2E; no se cierra
  Slice 6B ni el change.

## 2. Git inicial

- Rama `main`; HEAD `d62c76a233774fefcb37f39fb2aac6f0039d4848`.
- Staging vacío; `git diff --check` limpio.
- Working tree exacto: `M bin/generate_script.py`, `M
  docs/project/current-state.md`, `M openspec/changes/retire-legacy-visual-v1/tasks.md`,
  `M tests/test_generate_script_v2.py`; tres session logs untracked
  (`20260811-205950-...`, `20260811-213354-...`, `20260811-220445-...`).

## 3. Cuarto E2E heredado

- Job `cmo-2026-08-11-185926`: BLOCKED (`REVIEW_REQUIRED` controlado por contrato
  en `script`) por `DURATION_OUT_OF_RANGE` (62 > 52 palabras).
- Convergencia monotónica `69 → 63 → 62`; targets por escena orientativos; sin
  hard caps ni mínimo duro; política de candidatos correcta; el modelo no comprimió
  hasta 47–52.

## 4. Auditoría de control de generación

- `SLICE_6B_COMPRESSION_CONTROL_AUDIT_RECOMMENDS_CHANGES`.
- La política de candidatos funcionó; el problema restante es el control de
  generación/compliance del LLM.

## 5. Hardening implementado

- Target operativo interior `_compute_operational_word_target` (para 30s = 50).
- Presupuesto global inequívoco en la generación inicial.
- Compression system prompt con primacía del presupuesto global.
- Compression prompt imperativo (reducción mínima obligatoria + reducción
  deseada + escalado del segundo intento).
- Temperatura específica de compression 0.2 frente al resto 0.8.
- Contratos 47/52/52 y `MAX_SCRIPT_ATTEMPTS == 3` intactos.
- Cobertura C1–C11; baseline `1181 passed, 0 failed`.

## 6. Review CHANGES_REQUIRED

- `SLICE_6B_LENGTH_CONTROL_HARDENING_REVIEW_CHANGES_REQUIRED`.
- HIGH: 0.
- **F2 LOW** aceptado y no corregido (branch defensivo de
  `_compute_operational_word_target`; input inalcanzable en runtime productivo).
- Compression system/user prompt, temperatura, attempt wiring, escalado del
  segundo intento, candidato canónico, repair shape-only, ranking, best candidate,
  anti-regresión y operational target como no-gate quedaron aprobados.

## 7. F1 MEDIUM

- La generación inicial presentaba el doble target accionable
  `preferredWords≈52` (formulado como objetivo) junto al operational target `50`.

## 8. Fix F1

- `preferredWords=52` queda como dato/referencia del perfil; `maximumWords=52`
  como hard boundary; `operationalWordTarget=50` como único target accionable.
- C2 reforzado contra el doble target (`aproximadamente 52 palabras objetivo`
  ausente; `preferredWords del perfil: 52` presente; `Objetivo operativo` solo con
  `50`).

## 9. Reaprobación

- `SLICE_6B_LENGTH_CONTROL_TARGET_FIX_REAPPROVED_FOR_COMMIT`.
- Cero findings HIGH/MEDIUM; F1 resuelto; F2 LOW aceptado.

## 10. F2 LOW aceptado

- `_compute_operational_word_target` budget inválido `52/52/47 → 0` queda
  `ACCEPTED NON-BLOCKING`. No se corrige.

## 11. Baseline

- **`1181 passed, 0 failed`** (heredada y confirmada en cierre).

## 12. Tests ejecutados en cierre

- C2 exacto: `1 passed`.
- C1–C11 (16 node IDs): `16 passed`.
- `test_generate_script_v2.py`: `156 passed`.
- `--collect-only tests/`: `1181 tests collected`, cero errores.
- `pytest -q tests/`: `1181 passed, 0 failed`; cero skipped, cero xfailed, cero
  xpassed, cero warnings; duración `11.82s`.

## 13. Commit A completo y corto

- `bafb2d5b8397d9b745f24bdc9153a016f1ac6383` / `bafb2d5`.

## 14. Asunto Commit A

- `fix(script): harden V2 word-budget control`.

## 15. Archivos Commit A

- `bin/generate_script.py`
- `tests/test_generate_script_v2.py`

Commit A contiene exactamente dos archivos.

## 16. Cero quinto E2E

- Cero quinto E2E; cero providers reales (LLM/Wikimedia/Pixabay/Edge TTS); cero
  Docker; cero FFmpeg; cero `bin/run_job.py`; cero push; cero amend; cero reset;
  cero rebase; cero MCP; cero reindexado.

## 17. Cero PASS completo

- Ningún E2E V2 canónico ha alcanzado PASS; ningún vídeo nuevo.

## 18. Slice 6B abierto

- Slice 6B continúa abierto hasta obtener un E2E V2 canónico PASS.

## 19. Change abierto

- El change `retire-legacy-visual-v1` continúa abierto.

## 20. Próximo paso

- Quinto E2E V2 canónico.