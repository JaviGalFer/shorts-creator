# Slice 6B — Cuarto E2E V2 canónico (ejecutado 2026-08-11)

## Configuración

- Sesión: `retire-legacy-visual-v1-slice-6b-fourth-canonical-e2e`
- Modelo: `opencode/deepseek-v4-flash-free`; variante `default`
- Modo: `Build`; máximo 28 pasos; cero subagentes.
- Codebase Memory MCP: DESACTIVADO; cero llamadas MCP.
- Reindexado: no.

## HEAD e historial

- Rama: `main`
- HEAD inicial: `d62c76a233774fefcb37f39fb2aac6f0039d4848`
- Working tree limpio; staging vacío; untracked cero; `git diff --check` limpio.
- Historial:
  - `d62c76a` docs(project): record Slice 6B duration policy closure
  - `d377932` fix(script): refine V2 duration compression policy
  - `ad86834` docs(project): record Slice 6B duration fix closure
  - `9eb1f13` fix(script): harden canonical duration retries
  - `e5e2a4e` docs(project): record Slice 6B script fix commit
  - `f48f98f` fix(script): harden V2 prompt and retry contract

## Baseline heredada

- `1165 passed, 0 failed`
- Contrato 30s: `minimumWords=47`, `preferredWords=52`, `maximumWords=52`,
  `strictness=balanced`, `MAX_SCRIPT_ATTEMPTS=3`.

## Hashes iniciales

- `bin/generate_script.py`      603c8b2166ed6aabdea2172c1807a9c9800c2e32950f9b4c2e7de846bfa82679
- `bin/run_job.py`              6240606ba8ea1b5a07c56e0d0dcf25fc30a4b4eed58a82a2dffbaeecb7f67d0f
- `bin/visual_plan_v2.py`       37c5c463d2a9069627705fa26c4b7b94b3fd3121fcc02d6ca5d6dad77cad66ff
- `bin/duration_profiles.py`    41e12bcafd30c79d122fa93d23fda7a02f64ac25ee88e544d45df18311a5f45d
- `tests/test_generate_script_v2.py` e3b635ea9bcfcfbcb806ea272e255a19f988be352cac5d147510b7471319ad5d

## Preflight

- Placeholder `test_t2_compression_prompt_contains_previous_attempt`: 1 passed.
- Policy-critical (`test_policy_t3_progressive_56_54_52`,
  `test_policy_t4_non_regression_56_58_52`, `test_policy_t8_best_attempt_56_54_55`,
  `test_policy_t2_global_pass_with_unmet_target`, `test_policy_t6_six_word_scene_pass`):
  5 passed.
- Dry-run `test_visual_v2_dry_run_e2e.py`: 22 passed.

## Constantes runtime

- `MAX_SCRIPT_ATTEMPTS == 3`
- `minimumWords == 47`, `preferredWords == 52`, `maximumWords == 52`
- `strictness == balanced`
- Existen `_compute_scene_word_targets`, `_evaluate_scene_word_targets`,
  `VOICEOVER_COMPRESSION_SYSTEM_PROMPT`.
- No existe en runtime `MIN_WORDS_PER_SCENE`, `REPAIR_SCENE_WORD_CAP_EXCEEDED`,
  `REPAIR_SCENE_WORD_MINIMUM_NOT_MET`.

## Providers efectivos

- LLM provider: `openai`; LLM model: `gpt-4o-mini`.
- TTS provider: `edge_tts`.
- Wikimedia: enabled, implemented, sin API key.
- Pixabay: enabled, implemented, requiere API key (key presente).
- Pexels: disabled, not implemented.
- FreeAI: disabled, not implemented.
- Pollinations: disabled, not implemented.
- `request.visuals.allowGeneratedImages == false`.

## Docker

- client 29.1.3, server 29.1.3.
- Imagen `linuxserver/ffmpeg:latest` presente (id `sha256:9872...20a297e`).
- Espacio: 943G disponibles.
- `data/videos` escribible.
- No se descargaron imágenes Docker nuevas.

## Snapshot de jobs

- 87 jobs antes; 88 después; exactamente un job nuevo.
- Históricos presentes e intactos: `cmo-2026-08-02-192443`,
  `cmo-2026-08-02-204451`, `cmo-2026-08-04-195654`.

## Comando exacto

```bash
python3 bin/run_job.py --topic "Cómo se forma un arcoíris" --duration 30
```

- Una única invocación top-level confirmada.
- Inicio: `2026-08-11T20:59:03+02:00` (epoch `1786474743`).
- Fin: `2026-08-11T20:59:26+02:00` (epoch `1786474766`).
- Duración wall-clock: 23 s.
- Exit code: 0.

## stdout resumido

```
REVIEW_REQUIRED: job cmo-2026-08-11-185926 needs human review
{"jobId": "cmo-2026-08-11-185926", ..., "status": "REVIEW_REQUIRED", "lastCompletedStage": "script", "outputVideoPath": null, "validationStatus": null}
```

## stderr resumido

- Sin errores en stderr.

## Job

- Job ID: `cmo-2026-08-11-185926`
- Path: `data/videos/cmo-2026-08-11-185926`
- Archivos producidos: `metadata.json` (único artefacto; pipeline detenido en `script`).

## Request

- topic: `Cómo se forma un arcoíris`
- target duration: 30s (profile `short_25_30`)
- visual schemaVersion: 2
- allowGeneratedImages: false
- LLM provider: openai; LLM model: gpt-4o-mini
- TTS provider: edge_tts

## Contrato visual

- `schemaVersion == 2`; `allowGeneratedImages == false`
- 5 escenas; `sceneNumber` secuencial 1–5
- `visualPlan._schemaVersion == 2` en todas
- Cero campos V1 residuales (`editorialRole`, `strategy`, `primaryAssetType`,
  `secondaryAssetType`, `visualTemporalIntent`)
- Enums usados en `assetPreferences`: photograph, diagram, illustration, stock — todos válidos
- `structureValid == true`; `structureIssues == []`

## Contrato temporal (final)

- `targetSec=30`, `minSec=27`, `maxSec=30`, `strictness=balanced`,
  `spokenWordsPerMinute=110`
- `wordCount=62`, `sceneCount=5`, `sceneWordCounts=[12,13,9,14,14]`
- `spokenDurationSec=33.8`, `pauseDurationSec=1.4`, `estimatedDurationSec=35.2`
- `minimumWords=47`, `preferredWords=52`, `maximumWords=52`
- `status=FAIL`; `retries=3`
- `bestAttempt=2`; `bestAttemptWordCount=62`;
  `lastAttemptDiscardedAsRegression=false`
- `reviewReasons`: `DURATION_OUT_OF_RANGE: estimated=35.2s (spoken=33.8s +
  pauses=1.4s), target=30s, min=27s, max=30s, words=62, scenes=5`

## Retry history

| attempt | strategy | wordCount | structureValid | durationStatus | candidateUpdated | candidateReused | becameBest | acceptedAsBest | rank |
|---------|----------|----------:|----------------|----------------|------------------|-----------------|------------|----------------|------|
| 0 | initial | 69 | true | FAIL | true | false | true | false | [17,17] |
| 1 | compression | 63 | true | FAIL | true | false | true | false | [11,11] |
| 2 | compression | 62 | true | FAIL | true | false | true | true | [10,10] |

- Attempt 0 (`wordCountSource=generated_candidate`): sceneWordCounts `[12,13,11,16,17]`; sceneWordTargets null (no-repair); distance 17.
- Attempt 1 (`wordCountSource=repaired_candidate`): sceneWordTargets `[10,10,10,11,11]`; repairShapeValid=true, repairPayloadEligible=true, repairPayloadValid=true, repairGlobalBudgetValid=false, repairSceneTargetsMet=false, repairBudgetValid=false, repairProposedWordCount=63, repairProposedSceneWordCounts `[12,12,9,14,16]`, repairProposedCandidateRank `[11,11]`; sceneWordCaps `[10,10,10,11,11]`, sceneWordCapsEnforced=false, sceneWordCapsDeprecated=true; targetReductionWords=17.
- Attempt 2 (`wordCountSource=repaired_candidate`): sceneWordTargets `[10,11,9,11,11]`; repairShapeValid=true, repairPayloadEligible=true, repairPayloadValid=true, repairGlobalBudgetValid=false, repairSceneTargetsMet=false, repairBudgetValid=false, repairProposedWordCount=62, repairProposedSceneWordCounts `[12,13,9,14,14]`, repairProposedCandidateRank `[10,10]`; sceneWordCaps `[10,11,9,11,11]`, sceneWordCapsEnforced=false, sceneWordCapsDeprecated=true; targetReductionWords=11.
- Todos los intentos `repairGlobalBudgetValid=false`; el total final nunca alcanzó 47–52.
- Cero payloads rechazados por hard caps (`REPAIR_SCENE_WORD_CAP_EXCEEDED` ausente) ni hard minimum (`REPAIR_SCENE_WORD_MINIMUM_NOT_MET` ausente).

## Targets y candidate evolution

- Convergencia monotónica: 69 → 63 → 62; cada candidato mejoró el ranking.
- Targets por escena como guidance; en todos los intentos `repairSceneTargetsMet=false` pero eso no bloqueó la aceptación del candidato (mejoró ranking y se aceptó como activo).
- `acceptedAsBest=true` únicamente en el intento final (2).
- `bestAttempt=2`, `bestAttemptWordCount=62` coherente con el candidato persistido.
- Anti-regresión: cero `candidateReused=true` (todos los candidatos mejoraron o empataron ranking); `lastAttemptDiscardedAsRegression=false`.

## Evaluación de la política temporal

- La política se comportó según diseño: targets orientativos, presupuesto global como único contracto duro, convergencia monotónica, anti-regresión, sin hard caps ni hard minimum.
- **No resolvió el bloqueo**: el modelo no comprimió por debajo de 52 (terminó en 62), por lo que `DURATION_OUT_OF_RANGE` persistió. El bloqueo de duración del tercer E2E (56 > 52) sigue presente en esencia (62 > 52).

## Comparativa de los cuatro E2E

| E2E | Job                     | Estructura | Words | Retry               | Estado script   | Pipeline |
| --- | ----------------------- | ---------: | ----: | ------------------- | --------------- | -------- |
| 1   | `cmo-2026-08-02-192443` |   inválida |    54 | regeneración        | REVIEW_REQUIRED | detenido |
| 2   | `cmo-2026-08-02-204451` |     válida |    69 | regeneración        | REVIEW_REQUIRED | detenido |
| 3   | `cmo-2026-08-04-195654` |     válida |    56 | compression antigua | REVIEW_REQUIRED | detenido |
| 4   | `cmo-2026-08-11-185926` |     válida |    62 | compression nueva   | REVIEW_REQUIRED | detenido |

- La política nueva validó el mecanismo de retry (convergencia, targets orientativos,
  sin hard caps) pero el candidato inicial volvió a superar 52 y los retries de
  compresión no lograron llevarlo al rango. El bloqueo observado en el tercer E2E
  (no entrar en 47–52) **no** quedó resuelto en ejecución real.

## Assets / Audio / Prepare / Render / Validate / Quality gate

- No alcanzadas: el pipeline se detuvo en `script` (`REVIEW_REQUIRED`).
- Sin vídeo final; `outputVideoPath=null`; `validationStatus=null`; ffprobe no aplica.

## Resultado global

- **BLOCKED** (`REVIEW_REQUIRED` controlado por contrato en `script`), por
  `DURATION_OUT_OF_RANGE` (62 > 52).
- Verdict: `SLICE_6B_FOURTH_E2E_SCRIPT_BLOCKED_NEEDS_FOLLOWUP`

## Criterios PASS E2E

- Exit code top-level = 0: sí.
- Status final no REVIEW_REQUIRED: no.
- Script V2 válido: sí; `structureValid=true`: sí.
- `47 <= wordCount <= 52`: no (62).
- durationContract PASS: no (FAIL).
- Assets/audio/prepare/render/validate completos: no.
- Vídeo final existe: no.
- `validationStatus=PASS`, `qualityGate=PASS`: no.
- PASS E2E completo: **no**.

## Estado Git final

- Working tree: `docs/project/current-state.md` (M), `openspec/changes/retire-legacy-visual-v1/tasks.md` (M), `docs/sessions/20260811-205950-...-fourth-canonical-e2e.md` (??).
- Staging vacío. Cero commit, cero push, cero amend.
- Source tree (`bin tests src`): sin cambios; hashes idénticos al snapshot inicial.
- `git diff --check` limpio.

## Restricciones

- Una sola invocación de `bin/run_job.py`; cero segunda ejecución.
- Cero cambios de código; cero cambios de tests; cero staging/commit/push.
- Cero MCP; cero reindexado.
- Cero ejecución manual de etapas; no se reanudó el job.
- Jobs históricos intactos.

## Próximo paso

- Auditoría read-only del cuarto E2E y una nueva corrección del exceso de palabras
  (el candidato inicial y los retries siguen superando `maximumWords=52`), seguida
  de un quinto E2E V2 canónico. Slice 6B y el change permanecen abiertos.

# Auditoría de control de generación

- Verdict: `SLICE_6B_COMPRESSION_CONTROL_AUDIT_RECOMMENDS_CHANGES`.
- Compresión real `69→63→62`; reducciones parciales `69→63` (6/69 ≈ 8.7%) y
  `63→62` (1/63 ≈ 1.6%); reducción global acumulada `7` sobre el exceso de `17`
  hasta el máximo (`7/17 ≈ 41.2%`). La política de candidatos funcionó
  (convergencia monotónica, canonicalización, anti-regresión, best candidate),
  pero el LLM no comprimió hasta 47–52.
- El system prompt de compression era débil: solo pedía forma JSON y restringía
  los campos, sin transmitir primacía del presupuesto global ni exigir recorte.
- `requiredReductionWords` (alias) era poco saliente: un campo discreto dentro
  del JSON de contexto, sin bloque imperativo ni obligación de reducir.
- El segundo retry de compresión no estaba escalado: no recordaba el
  incumplimiento anterior ni exigía eliminar las palabras restantes.
- La generación usaba `temperature=0.8` en todas las estrategias, incluidas las
  de compresión; mayor dispersión y menor determinismo en el recorte.
- Initial overshoot 4/4: los cuatro E2E reales produjeron candidatos iniciales
  por encima del máximo (`74, 60, 56, 69`), overshoot frente a 52 de
  `+22, +8, +4, +17`.
- Decisión de no ejecutar un quinto E2E en esta sesión: primero se implementa el
  hardening de control de longitud y se cierra con review/commit.
- Build posterior implementado (2026-08-11, session
  `20260811-213354-retire-legacy-visual-v1-slice-6b-length-control-hardening`):
  target operativo interior (para 30s = 50), presupuesto global inequívoco en la
  generación inicial, compression system prompt con primacía del presupuesto
  global, compression prompt imperativo con reducción mínima/deseada y escalado
  del segundo intento, y temperatura de compression 0.2 / resto 0.8.
- Baseline resultante: **`1181 passed, 0 failed`**.
- El resultado histórico de este job sigue siendo BLOCKED; esta sección no lo
  altera.

## Nota posterior — review del length-control hardening

La review del length-control hardening detectó un único blocker MEDIUM:
el prompt inicial mantenía preferredWords=52 formulado como objetivo junto al
operational target=50. Se corrigió en el follow-up sin modificar compression,
ranking ni contrato de aceptación.

## Nota final — reaprobación y versionado del follow-up

El follow-up de length-control fue posteriormente reaprobado y versionado mediante `bafb2d5`. El quinto E2E V2 canónico sigue pendiente.
