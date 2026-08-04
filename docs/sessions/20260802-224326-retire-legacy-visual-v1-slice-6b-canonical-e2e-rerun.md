# Session — Slice 6B segundo E2E V2 canónico (rerun)

- **Sesión:** `retire-legacy-visual-v1-slice-6b-canonical-e2e-rerun`
- **Modelo:** `opencode/deepseek-v4-flash-free` (variante `default`)
- **Modo:** Build
- **Timestamp session log:** `20260802-224326`
- **Fecha:** 2026-08-02
- **Objetivo:** ejecutar el segundo E2E V2 canónico tras la corrección de prompt/retry.

## 1. Configuración

- Rama `main`; HEAD `e5e2a4eb25746bf10645e0c1c2fe458482bedc48`.
- Baseline heredada: `1117 passed, 0 failed`.
- Commit de corrección heredado: `f48f98f`.
- Reindexado: no. MCP: desactivado. Subagentes: ninguno.

## 2. Estado Git inicial

```
main
e5e2a4eb25746bf10645e0c1c2fe458482bedc48
e5e2a4e docs(project): record Slice 6B script fix commit
f48f98f fix(script): harden V2 prompt and retry contract
496dd33 docs(project): record Slice 6A closure commit
86170d3 test(v2): establish clean Slice 6A baseline
```

- Working tree limpio; staging 0; untracked 0.
- `git diff --check` limpio (solo warning ignorado de `data/postgres/`).

## 3. Baseline heredada

`1117 passed, 0 failed`.

## 4. Preflight de tests

- `python3 -m pytest -q tests/test_generate_script_v2.py --tb=short` → **92 passed**.
- `python3 -m pytest -q tests/test_visual_v2_dry_run_e2e.py --tb=short` → **22 passed**.

No se ejecutó la suite completa (ya validada en la reaprobación).

## 5. Verificación del contrato corregido

Script read-only con `PYTHONPATH=bin`:

- `MAX_SCRIPT_ATTEMPTS == 3` → True.
- Primer user prompt con `allow_generated_images=False` contiene `allowGeneratedImages es false` → True, `allowGeneratedImage=false` → True.
- Budget `short_25_30` (30s): minimumWords=47, preferredWords=52, maximumWords=52.
- Retry de reducción contiene `como máximo 52` → True; enum cerrado → todos los valores de `ALLOWED_ASSET_PREFERENCES` presentes; preservación de `visualPlan`, `assetPreferences`, `visualSequence` → True.

## 6. Variables SET/UNSET

```
LLM_PROVIDER=SET
LLM_API_KEY=SET
LLM_MODEL=SET
PIXABAY_API_KEY=SET
TTS_PROVIDER=SET
```

- Provider LLM `openai`; Edge TTS seleccionado; ElevenLabs no seleccionado.
- Wikimedia activo; Pixabay activo (key presente); Pexels/FreeAI/Pollinations deshabilitados.

## 7. Docker e imagen

- `docker version` OK; `ServerVersion` `29.1.3`.
- `linuxserver/ffmpeg:latest` presente localmente (`IMAGE_PRESENT`).
- `df -h .`: 943G disponibles.
- `data/videos/` escribible.

## 8. Snapshot previo

Snapshot de `data/videos` tomado; no existía `cmo-2026-08-02-204451`.

## 9. Comando exacto

```bash
python3 bin/run_job.py --topic "Cómo se forma un arcoíris" --duration 30
```

Flags verificados vía `python3 bin/run_job.py --help`.

## 10. Confirmación de una sola invocación

Una única invocación top-level de `bin/run_job.py`. No se ejecutó una segunda invocación.

## 11. Exit code y duración

- Inicio: `2026-08-02T22:44:02+02:00`; fin: `2026-08-02T22:44:51+02:00`; duración 49s.
- Exit code: 0 (terminación controlada).
- stdout: `REVIEW_REQUIRED: job cmo-2026-08-02-204451 needs human review` + JSON de estado.
- stderr: vacío.

## 12. Job ID

- Job ID: `cmo-2026-08-02-204451`.
- Path: `data/videos/cmo-2026-08-02-204451`.
- Archivos: `metadata.json` (único artefacto). Tamaño ~16K.

## 13. Comparación con el primer E2E

| Aspecto | `cmo-2026-08-02-192443` (1º) | `cmo-2026-08-02-204451` (2º) |
|---------|-------------------------------|-------------------------------|
| Resultado | REVIEW_REQUIRED | REVIEW_REQUIRED |
| Etapa final | script | script |
| Enums inválidos | `animation`, `infographic` | **cero** |
| structureValid | false | **true** |
| allowGeneratedImages | — | false |
| Exceso de palabras | 54 > 52 | **69 > 52** |
| Bloqueo | enums + duración | solo duración |

La corrección de prompt/retry eliminó los enums inválidos y arregló la estructura; el bloqueo restante es únicamente el contrato de duración.

## 14. Request visual

- `request.visuals.schemaVersion == 2`.
- `request.visuals.allowGeneratedImages == false`.
- Gate `allowGeneratedImages=false` → **OK**.

## 15. Script y retries

- 5 escenas, `sceneNumber` secuencial 1–5, todas `_schemaVersion == 2`.
- Cero campos V1; cero enums inválidos; cero `imageGenerationPrompt`/`negativePrompt`.
- `structureValid == true`; `structureIssues == []`.
- Retries: 3.

## 16. Duración

- `wordCount`=69; `sceneCount`=5; `spokenDurationSec`=37.6; `pauseDurationSec`=1.4; `estimatedDurationSec`=39.0.
- `minimumWords`=47; `preferredWords`=52; `maximumWords`=52.
- `status`=FAIL.
- `retryHistory`: retry 0 = 60 (reduce_content); retry 1 = 56 (reduce_content); retry 2 = 69 (reduce_content; empeoró).
- `reviewReasons`: `DURATION_OUT_OF_RANGE: estimated=39.0s ... words=69, scenes=5`.
- Word count (69) > maximumWords (52) → contrato de duración NO superado.

## 17. Assets

No alcanzada (pipeline detenido en `script`).

## 18. Audio

No alcanzada.

## 19. Prepare

No alcanzada.

## 20. Render

No alcanzada.

## 21. Validate

No alcanzada.

## 22. Quality gate

No ejecutado.

## 23. ffprobe

No aplicable (sin vídeo final).

## 24. Vídeo final

Ninguno.

## 25. Warnings

Sin warnings en stdout/stderr.

## 26. Errores

Sin excepciones. Fallo de contrato controlado: `DURATION_OUT_OF_RANGE` en `script`.

## 27. Resultado

**BLOCKED** (`REVIEW_REQUIRED` controlado por contrato en `script`).

Verdict: `SLICE_6B_E2E_RERUN_NEEDS_FOLLOWUP`.

## 28. Documentación actualizada

- `docs/project/current-state.md` (resumen superior stale corregido + sección Slice 6B + Resumen + Próximos pasos).
- `openspec/changes/retire-legacy-visual-v1/tasks.md` (tarea «Nuevo E2E V2 canónico» marcada, con resultado detallado).
- Este session log.

## 29. Estado Git final

- Rama `main`; HEAD sin cambios `e5e2a4eb25746bf10645e0c1c2fe458482bedc48`.
- Staging 0; únicamente los tres archivos documentales sin stagear; job nuevo preservado bajo `data/videos/`.
- `git diff --check` limpio.

## 30. Cero cambios productivos

`bin/`, `tests/`, `src/` intactos. Sin cambios en `.env`, configuración ni Docker.

## 31. Cero segundo intento

No se ejecutó una segunda invocación del pipeline.

## 32. Próximo paso

- Auditoría read-only del segundo E2E.
- Sesión de corrección para el exceso de palabras persistente (69 > 52) manteniendo el contrato visual corregido.
- Tras un E2E V2 canónico PASS, cerrar formalmente el change.

---

# Auditoría read-only del retry temporal

Sesión de auditoría del segundo E2E V2 canónico (follow-up temporal).

## Verdict

`SLICE_6B_DURATION_REVIEW_CHANGES_REQUIRED`.

## Findings F1–F9

- **F1 (MEDIUM):** el retry temporal no recibía el texto anterior que debía
  comprimir: pedía una regeneración completa, por lo que el modelo no tenía
  contexto de los voiceovers a reducir.
- **F2 (MEDIUM):** no existía un reparto estricto del budget por escena; se
  pedía "máximo 11 palabras por escena" pero cinco escenas de 11 superaban el
  máximo global (55 > 52).
- **F3 (MEDIUM):** no había separación entre retry estructural y retry temporal;
  ambos usaban el mismo mecanismo de regeneración completa.
- **F4 (LOW):** el retry pedía preservar campos que no se le proporcionaban
  (visualPlan, subtitle, etc.) en el bloque editable.
- **F6 (MEDIUM):** no existía protección anti-regresión: el intento 3 (69
  palabras) sustituía al mejor intento anterior (56) al persistir el último.
- **F7 (MEDIUM):** cobertura insuficiente: no había tests de convergencia de
  compresión, caps por escena ni best attempt.
- **F8 (LOW):** `tasks.md` y `current-state.md` conservaban párrafos que
  afirmaban que reaprobación, commit y segundo E2E quedaban pendientes cuando ya
  estaban cerrados. Corregido a historia explícita.
- **F9 (LOW):** `current-state.md` presentaba numeración duplicada (`8.` dos
  veces) en la sección «Próximos pasos». Corregido a numeración secuencial.

## Diagnóstico D1–D8

- **D1 — Regeneración completa estocástica:** cada retry re-generaba el guion
  completo desde cero; el modelo podía empeorar (69) en lugar de converger.
- **D2 — El retry no recibía el texto anterior:** confirmado (F1); sin el
  voiceover anterior no se puede comprimir de forma dirigida.
- **D3 — Sin reparto estricto del budget por escena:** confirmado (F2); el
  máximo global no se distribuía de forma determinista ni sumaba exacta.
- **D4 — Se pedía preservar campos que no se proporcionan:** confirmado (F4).
- **D6 — Sin protección anti-regresión:** confirmado (F6); se persistía el
  último intento aunque empeorara.
- **D7 — Cobertura insuficiente:** confirmado (F7); faltaban tests de
  convergencia temporal.
- **D8 — Incumplimiento del modelo:** factor contribuyente, no causa raíz.

## Decisiones

- No modificar `visual_plan_v2.py`.
- No modificar `run_job.py`.
- No modificar `duration_profiles.py`.
- No aumentar `MAX_SCRIPT_ATTEMPTS` (sigue 3).
- No relajar `minimumWords`/`preferredWords`/`maximumWords`.
- No implementar truncado ciego.
- No ejecutar otro E2E en la sesión de corrección.
- Se requiere un Build de corrección del retry temporal.

## Estado del job

- El resultado histórico del job `cmo-2026-08-02-204451` permanece intacto:
  BLOCKED (`REVIEW_REQUIRED`) en `script` por `DURATION_OUT_OF_RANGE`
  (69 > 52 palabras); contrato visual válido.
- El job no se modifica ni se re-ejecuta.

---

# Review de la primera corrección temporal

Sesión posterior: `retire-legacy-visual-v1-slice-6b-duration-retry-review-fixes`.

- La auditoría read-only de la corrección temporal de duración (Build
  `20260804-201703`) terminó con `SLICE_6B_DURATION_FIX_REVIEW_CHANGES_REQUIRED`.
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
- La suite quedó verde (baseline `1138 passed, 0 failed`) pero con cobertura
  incompleta: los findings no se corrigieron en el Build original.
- No se hizo commit; no se ejecutó un nuevo E2E.
- El follow-up de las correcciones F1–F7 se aplicó en la sesión
  `retire-legacy-visual-v1-slice-6b-duration-retry-review-fixes`.
- El resultado histórico del job `cmo-2026-08-02-204451` no cambia.

# Primera reaprobación del follow-up temporal

Sesión posterior: `retire-legacy-visual-v1-slice-6b-duration-canonical-followup`.

- La primera reaprobación read-only focalizada de la corrección temporal terminó
  con `SLICE_6B_DURATION_REVIEW_FIXES_REAPPROVAL_CHANGES_REQUIRED`.
- **F8 MEDIUM bloqueante**: el compression prompt y el merge recibían la
  representación raw en lugar de la canónica, pese a que `canonical` estaba
  disponible cuando `v2_valid == true`.
- **F9–F11 LOW** no bloqueantes.
- El job histórico `cmo-2026-08-02-204451` permanece intacto; no se re-ejecuta.
- Ningún nuevo E2E en esta revisión.
