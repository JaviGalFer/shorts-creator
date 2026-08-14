# Estado actual del proyecto

**Última actualización:** 2026-08-14

## Estado global

Pipeline funcional de vídeos cortos verticales con duración configurable. Scripts en `bin/` operativos. n8n como orquestador legacy. Docker para render.

**Último change completado:** `integrate-native-visual-plan-v2-generation` (2026-07-14)

**Change pausado:** `improve-short-form-audio-pacing-v2` — Phase A completada, Phase B pendiente (se reanudará tras migrar dominio script)

**Change activo:** `retire-legacy-visual-v1` — Primera fase del plan de transformación modular. Slice 1 implementado, revisado y commiteado. Slice 2 implementado, revisado y cerrado mediante commit. Slice 3A implementado, revisado y cerrado mediante commit. Slice 3B1 implementado, revisado y cerrado mediante el commit de esta iteración. Slice 3B2 implementado, revisado y cerrado mediante el commit de esta iteración. Slice 3B3 implementado, revisado y cerrado mediante el commit de esta iteración. Slice 4A implementado, revisado y cerrado mediante el commit de esta iteración. Slice 4B1 implementado, revisado y cerrado mediante el commit de esta iteración. Slice 4B2 implementado, revisado y cerrado mediante el commit de esta iteración. Slice 4 completo. Slice 5A implementado, revisado, corregido, reaprobado y cerrado mediante el commit `f2a8078`. Slice 5B implementado, auditado, corregido, reaprobado y cerrado mediante el commit `1d9fe37`. Slice 6A implementado, auditado, corregido, reaprobado y cerrado mediante el commit `86170d3`. Slice 6B ejecutado con E2E V2 canónico BLOCKED (controlado por contrato en `script`); auditado read-only con `SLICE_6B_REVIEW_CHANGES_REQUIRED`; corrección de prompt/retry implementada; auditado read-only de la corrección con `SLICE_6B_FIX_REVIEW_CHANGES_REQUIRED` y correcciones F1–F6 aplicadas; corrección de prompt/retry reaprobada y cerrada mediante `f48f98f`; nuevo E2E ejecutado en esta sesión; auditado read-only del nuevo E2E con `SLICE_6B_DURATION_REVIEW_CHANGES_REQUIRED`; corrección del retry temporal de duración implementada (baseline `1138 passed, 0 failed`); auditado read-only de la corrección con `SLICE_6B_DURATION_FIX_REVIEW_CHANGES_REQUIRED` y correcciones F1–F7 aplicadas (baseline `1155 passed, 0 failed`); primera reaprobación read-only con `SLICE_6B_DURATION_REVIEW_FIXES_REAPPROVAL_CHANGES_REQUIRED` (F8 MEDIUM detectado); F8 corregido en el follow-up canónico mediante candidato canónico en compression prompt y merge (baseline `1158 passed, 0 failed`); corrección temporal reaprobada (`SLICE_6B_DURATION_CANONICAL_FOLLOWUP_REAPPROVED_FOR_COMMIT`), cerrada y versionada mediante `9eb1f13`; F1–F8 resueltos; F9 LOW aceptado; tercer E2E V2 canónico ejecutado (job `cmo-2026-08-04-195654`) BLOCKED (`REVIEW_REQUIRED`) en `script` por `DURATION_OUT_OF_RANGE` (56 > 52 palabras); contrato visual y estructura ya válidos (`structureValid=true`, cero enums inválidos, `allowGeneratedImages=false`); compresión temporal no logró payload budget-valid, se conservó el candidato inicial de 56 palabras como best attempt; auditoría de política temporal del tercer E2E con `SLICE_6B_DURATION_POLICY_AUDIT_RECOMMENDS_CHANGES`; corrección de política temporal implementada (targets por escena como guidance + presupuesto global como único contracto duro + convergencia monotónica; baseline funcional `1165 passed, 0 failed`); review read-only de la corrección de política con `SLICE_6B_DURATION_POLICY_FIX_REVIEW_CHANGES_REQUIRED` (arquitectura funcional aprobada; único blocker MEDIUM: placeholder `{min_w}/{max_w}` sin interpolar en el compression prompt); placeholder corregido a f-string y test de regresión ampliado (baseline funcional vigente `1165 passed, 0 failed`); corrección de política temporal reaprobada (`SLICE_6B_DURATION_POLICY_FINAL_REAPPROVED_FOR_COMMIT`), cerrada y versionada mediante `d377932`; cuarto E2E V2 canónico ejecutado (job `cmo-2026-08-11-185926`) BLOCKED (`REVIEW_REQUIRED`) en `script` por `DURATION_OUT_OF_RANGE` (62 > 52 palabras); contrato visual y estructura válidos (`structureValid=true`, cero enums inválidos, `allowGeneratedImages=false`); política temporal validada en comportamiento (convergencia monotónica 69→63→62, targets orientativos, sin hard caps, anti-regresión) pero el modelo no comprimió hasta 47–52 (terminó en 62); `SLICE_6B_FOURTH_E2E_SCRIPT_BLOCKED_NEEDS_FOLLOWUP`; auditoría read-only del cuarto E2E con `SLICE_6B_COMPRESSION_CONTROL_AUDIT_RECOMMENDS_CHANGES`; hardening de control de longitud implementado (Build 2026-08-11): target operativo interior `_compute_operational_word_target` (para 30s = 50, dentro de `[minimumWords, maximumWords]`), presupuesto global en la generación inicial (LÍMITE ABSOLUTO, objetivo operativo, jerarquía global > per-scene, autocuenta), compression system prompt con primacía del presupuesto global, compression prompt imperativo (reducción mínima obligatoria + reducción deseada al target operativo + escalado del segundo intento), temperatura específica de compression 0.2 frente al resto 0.8; contratos 47/52/52 y `MAX_SCRIPT_ATTEMPTS==3` intactos; baseline funcional `1181 passed, 0 failed`; review read-only del hardening con `SLICE_6B_LENGTH_CONTROL_HARDENING_REVIEW_CHANGES_REQUIRED` (F1 MEDIUM: doble target inicial `≈52` vs `50`; F2 LOW aceptado; compression/temperatura/ranking/repair aprobados); F1 corregido en el follow-up (`preferredWords=52` como dato del perfil, `maximumWords=52` como hard boundary, `operationalWordTarget=50` como único target accionable); C2 reforzado; length-control hardening re-aprobado read-only (`SLICE_6B_LENGTH_CONTROL_TARGET_FIX_REAPPROVED_FOR_COMMIT`, cero HIGH/MEDIUM, F1 resuelto, F2 LOW aceptado), cerrado y versionado mediante Commit A `bafb2d5` (`fix(script): harden V2 word-budget control`); baseline funcional vigente `1181 passed, 0 failed`; quinto E2E V2 canónico ejecutado (job `cmo-2026-08-14-153529`): script PASS por primera vez en la serie y length-control hardening validado mediante E2E real (`55 → 52`, `status=PASS`, `structureValid=true`); assets completos (`ASSETS_READY`, 10/10); pipeline bloqueado posteriormente en `audio` por `AUDIO_DURATION_MISSING` (medida de duración de los 5 mp3 no devuelta durante el run); verdict `SLICE_6B_FIFTH_E2E_LENGTH_CONTROL_VALIDATED_PIPELINE_BLOCKED`; pendiente diagnóstico del bloqueo de audio y auditoría read-only final.

### Slice 6B — Corrección de política temporal (Build 2026-08-11)

- Tercer E2E V2 canónico (job `cmo-2026-08-04-195654`): BLOCKED (`REVIEW_REQUIRED`) en `script` por `DURATION_OUT_OF_RANGE` (56 > 52 palabras). Contrato visual y estructura válidos (`structureValid=true`, cero enums inválidos, `allowGeneratedImages=false`).
- Auditoría read-only de política temporal: `SLICE_6B_DURATION_POLICY_AUDIT_RECOMMENDS_CHANGES`.
- **Falso negativo global confirmado:** el tercer E2E necesitaba reducir 4 palabras (56 → 52), pero la política anterior (caps estáticos por escena + mínimo duro de siete palabras + rechazo completo antes del ranking) exigía una reducción de 8 y rechazaba retries con alguna escena por debajo de siete palabras aunque el total global fuese válido. Caps y mínimo siete se clasifican como mecanismos del repair, no como contracto.
- **Política nueva implementada:**
  - Targets dinámicos por escena como guidance (`_compute_scene_word_targets` water-filling determinista + `_evaluate_scene_word_targets`); caso canónico `[14,13,9,7,13] → [12,12,9,7,12]`.
  - Hard gate por escena: únicamente shape (voiceover string no vacío, secuencia exacta de `sceneNumber`); retirado `MIN_WORDS_PER_SCENE == 7`.
  - Presupuesto global como hard duration contract (`minimumWords <= total <= maximumWords`); un repair globalmente válido alcanza PASS aunque no coincida con la distribución recomendada.
  - Convergencia monotónica de candidatos: `56 → 54 → 52`, `56 → 58 → 52`, `56 → 54 → 55` sin aumentar `MAX_SCRIPT_ATTEMPTS`; protección anti-regresión y best attempt conservados.
  - Telemetría separada: campos globales (`repairGlobalBudgetValid`, `repairProposedWordCount`, `repairProposedCandidateRank`, …) y orientativos por escena (`repairSceneTargetsMet`, `repairSceneTargetDeviations`); aliases de compatibilidad (`repairPayloadValid`, `repairBudgetValid`, `sceneWordCaps=sceneWordTargets`, `sceneWordCapsEnforced=false`, `sceneWordCapsDeprecated=true`); no-repair strategies con campos repair en `null`.
- Validator (`visual_plan_v2.py`), runner (`run_job.py`) y perfiles (`duration_profiles.py`) intactos. `MAX_SCRIPT_ATTEMPTS == 3`; `minimumWords=47` / `preferredWords=52` / `maximumWords=52` intactos.
- Baseline funcional nueva: **`1165 passed, 0 failed`** (anterior `1158`; +7 tests). `test_generate_script_v2.py` = 140 passed; combinada generación = 186 passed; `test_run_job.py` = 91 passed.
- Review read-only de la corrección de política: `SLICE_6B_DURATION_POLICY_FIX_REVIEW_CHANGES_REQUIRED`. La arquitectura funcional quedó aprobada; el único blocker MEDIUM fue un placeholder de prompt sin interpolar en `_build_voiceover_compression_prompt` (`"- Revisa que el total final esté entre {min_w} y {max_w}."` literal). LOWs no bloqueantes aceptados: el mínimo de siete palabras como guidance de generación completa y la telemetría nullable/aliases en estrategias no-repair.
- **Corrección del placeholder (Build, esta sesión):** la línea pasó a f-string (`f"- Revisa que el total final esté entre {min_w} y {max_w}."`), renderizando valores reales (`Revisa que el total final esté entre 47 y 52.` para el perfil de 30s). No se reformateó la función ni se tocaron otros strings. `test_generate_script_v2.py::TestDurationRetryConvergence::test_t2_compression_prompt_contains_previous_attempt` ampliado con aserciones de ausencia de `{min_w}`/`{max_w}`/`{expected}` y presencia de `47`/`52` y de la frase exacta.
- Baseline funcional vigente: **`1165 passed, 0 failed`** (1165 collected). `test_generate_script_v2.py` = 140 passed (test ampliado, no añadido); combinada generación = 186 passed; `test_run_job.py` = 91 passed.
- Reaprobación read-only final de la corrección de política: `SLICE_6B_DURATION_POLICY_FINAL_REAPPROVED_FOR_COMMIT`. Cero findings HIGH/MEDIUM; LOWs aceptados (mínimo de siete como guidance y telemetría nullable/aliases).
- Corrección de política temporal cerrada y versionada mediante el Commit A `d377932` (`fix(script): refine V2 duration compression policy`). Baseline vigente: **`1165 passed, 0 failed`**.
- Pendiente únicamente el cuarto E2E V2 canónico. Cero cuarto E2E; cero PASS completo todavía. Slice 6B y el change `retire-legacy-visual-v1` continúan abiertos. Cero push, cero MCP, cero reindexado.

### Slice 6B — Cuarto E2E V2 canónico (ejecutado 2026-08-11)

- HEAD de ejecución: `d62c76a233774fefcb37f39fb2aac6f0039d4848`; working tree limpio.
- Comando exacto: `python3 bin/run_job.py --topic "Cómo se forma un arcoíris" --duration 30`.
- Una única invocación top-level; inicio `2026-08-11T20:59:03+02:00` (epoch `1786474743`); fin `2026-08-11T20:59:26+02:00` (epoch `1786474766`); duración 23 s; exit code 0.
- Job ID: `cmo-2026-08-11-185926`; path `data/videos/cmo-2026-08-11-185926`; único artefacto `metadata.json`.
- Providers: LLM `openai` (`gpt-4o-mini`); Wikimedia activo + Pixabay activo (con key); Pexels/FreeAI/Pollinations deshabilitados; TTS `edge_tts` (no alcanzado); Docker/FFmpeg no alcanzados.
- **Resultado: BLOCKED** (`REVIEW_REQUIRED` controlado por contrato en `script`) por `DURATION_OUT_OF_RANGE` (62 > 52 palabras).
- Contrato visual y estructura válidos: `schemaVersion==2`, `allowGeneratedImages=false`, `structureValid=true`, `structureIssues==[]`, 5 escenas, `visualPlan._schemaVersion==2` en todas, cero campos V1, enums válidos (photograph/diagram/illustration/stock).
- Contrato temporal final: `wordCount=62`, `sceneWordCounts=[12,13,9,14,14]`, `spokenDurationSec=33.8`, `pauseDurationSec=1.4`, `estimatedDurationSec=35.2`; `minimumWords=47`/`preferredWords=52`/`maximumWords=52`; `status=FAIL`; `retries=3`; `bestAttempt=2`; `bestAttemptWordCount=62`; `lastAttemptDiscardedAsRegression=false`.
- Retry sequence: initial 69 → compression 63 → compression 62 (convergencia monotónica; todos `candidateUpdated=true`, `candidateReused=false`; `acceptedAsBest=true` solo en el intento final).
- Targets por escena orientativos: intento 1 `[10,10,10,11,11]`, intento 2 `[10,11,9,11,11]`; en ambos `repairSceneTargetsMet=false` y `repairGlobalBudgetValid=false`, sin bloquear la aceptación del candidato mejorado (`repairPayloadValid=true`).
- Sin hard caps ni hard minimum: `sceneWordCapsEnforced=false`, `sceneWordCapsDeprecated=true`; ausentes `REPAIR_SCENE_WORD_CAP_EXCEEDED` y `REPAIR_SCENE_WORD_MINIMUM_NOT_MET`.
- Política temporal validada en comportamiento (targets como guidance, presupuesto global como único contracto duro, convergencia monotónica, anti-regresión) **pero no resolvió el bloqueo**: el modelo no comprimió hasta 47–52 (terminó en 62), el contrato visual y estructura ya eran válidos y el pipeline se detuvo en `script`.
- Etapas posteriores (assets/audio/prepare/render/validate) no alcanzadas; sin vídeo final; `outputVideoPath=null`; `validationStatus=null`; `qualityGate` no ejecutado.
- Verdict: `SLICE_6B_FOURTH_E2E_SCRIPT_BLOCKED_NEEDS_FOLLOWUP`.
- Cero cambios productivos (`bin tests src` intactos; hashes idénticos al snapshot inicial); cero segunda invocación; cero MCP; cero reindexado; cero commit/push; jobs históricos (`cmo-2026-08-02-192443`, `cmo-2026-08-02-204451`, `cmo-2026-08-04-195654`) intactos.
- Slice 6B y el change `retire-legacy-visual-v1` permanecen abiertos.

### Slice 6B — Hardening de control de longitud (Build, ejecutado 2026-08-11)

- **Auditoría:** `SLICE_6B_COMPRESSION_CONTROL_AUDIT_RECOMMENDS_CHANGES`.
- **Diagnóstico:** la política de candidatos funcionó correctamente en el cuarto E2E
  (`69 → 63 → 62`; candidatos shape-valid; canonicalización correcta; ranking
  monotónico; `candidateUpdated=true`; targets orientativos; sin hard caps; sin
  mínimo duro; best candidate correcto; anti-regresión correcta). El problema
  restante es **control de generación/compliance del LLM**.
- **Initial overshoot 4/4:** los cuatro E2E reales produjeron candidatos iniciales
  por encima del máximo (`74, 60, 56, 69`), overshoot frente a 52 de
  `+22, +8, +4, +17`. El cuarto E2E comprimió `69→63→62` (reducción global
  `7/17 ≈ 41%`) pero no alcanzó 47–52.
- **Target operativo interior:** helper puro `_compute_operational_word_target(budget)`
  que devuelve guidance de generación, no contrato, siempre dentro de
  `[minimumWords, maximumWords]`. Para `47/52/52` → **50** (hard range 47–52,
  target operativo 50). Otros casos: `47/50/52 → 50`, `47/49/52 → 49`,
  `52/52/52 → 52`. No sustituye a `preferredWords` ni `maximumWords`.
- **Hardening de generación inicial** (`_build_duration_prompt_instruction_v2`):
  presupuesto global — `Rango válido final: 47-52 palabras habladas`,
  `LÍMITE ABSOLUTO: no superes 52 palabras de voiceover en total`,
  `Objetivo operativo: apunta a 50 palabras de voiceover en total`; jerarquía
  `global maximum > per-scene guidance`; autoconteo de voiceovers antes de
  responder. Referencia `Mínimo 7 palabras por escena` conservada como guidance.
  Temperatura inicial intacta (0.8). Inicialmente declaraba el presupuesto global
  como inequívoco (F1); el review detectó que `preferredWords≈52` seguía formulado
  como objetivo junto al operational target `50`, y se corrigió en el follow-up
  (ver «Review read-only y fix F1» más abajo).
- **Hardening del compression system prompt:** `VOICEOVER_COMPRESSION_SYSTEM_PROMPT`
  añade primacía del presupuesto global, `nunca devuelvas un total superior a
  maximumWords`, conteo de palabras, seguir recortando y targets por escena como
  recomendación; sigue limitado a `sceneNumber`/`voiceover` sin exigir guion completo.
- **Compression prompt imperativo** (`_build_voiceover_compression_prompt`): bloque
  `CONTRATO DE COMPRESIÓN — PRIORIDAD MÁXIMA` con `Candidato actual`, `LÍMITE
  ABSOLUTO`, `eliminar AL MENOS N`, `N+1 o más incumple`, objetivo operativo y
  reducción deseada. Dos conceptos diferenciados:
  - `minimumRequiredReductionWords = max(0, actual - max)`;
  - `desiredReductionWords = max(0, actual - operational_target)`.
  - Caso real 69→max52: mínimo 17 / deseado 19 (target 50). Caso 63→max52:
    mínimo 11 / deseado 13.
- **Escalado del segundo compression attempt** (`compression_attempt >= 2`):
  bloque `SEGUNDO INTENTO DE COMPRESIÓN` que recuerda el incumplimiento anterior
  y exige eliminar las palabras restantes; sin metadata histórica nueva. El
  primer compression attempt no menciona compresión anterior fallida.
- **Temperatura específica de compression:** `DEFAULT_LLM_TEMPERATURE = 0.8` y
  `COMPRESSION_LLM_TEMPERATURE = 0.2`; `_llm_temperature_for_system_prompt`
  selecciona 0.2 para `VOICEOVER_COMPRESSION_SYSTEM_PROMPT` y 0.8 para el resto
  (initial/structural/duration). `call_llm` conserva su firma pública.
- **Targets por escena continúan siendo guidance:** wording inequívoco en el
  compression prompt (`Los targets por escena son recomendaciones. No es
  obligatorio cumplirlos exactamente. El límite global sí es obligatorio.`); sin
  validación nueva sobre ellos; no intervienen en `_apply_voiceover_repair`,
  `_candidate_rank`, PASS ni best candidate.
- **Contratos preservados:** `MAX_SCRIPT_ATTEMPTS == 3`; `47/52/52`; `balanced`;
  repair shape-only; candidato canónico; ranking/best/anti-regresión intactos.
  Repair/ranking/scene-targets sin cambios semánticos. Metadata sin ampliación
  (el target operativo se deriva del budget y no se persiste).
- **Cobertura:** tests C1–C11 añadidos en `tests/test_generate_script_v2.py`
  (target operativo, prompt inicial, system prompt compression, temperatura
  hermética, primer/segundo compression prompt, placeholders, temperatura initial,
  convergencia `69→63→52`, anti-regresión `69→70→52`, invariantes de contrato).
- **Componentes protegidos intactos:** `bin/visual_plan_v2.py`, `bin/run_job.py`,
  `bin/duration_profiles.py`, `tests/test_generate_script.py`,
  `tests/test_duration_profiles.py`, `tests/test_run_job.py`.
- **Baseline funcional nueva:** **`1181 passed, 0 failed`** (anterior `1165`; +16
  tests). `test_generate_script_v2.py` = 156 passed; combinada generación = 202
  passed; `test_run_job.py` = 91 passed.
- **Review read-only del hardening:** `SLICE_6B_LENGTH_CONTROL_HARDENING_REVIEW_CHANGES_REQUIRED`.
  Compression system/user prompt, temperatura (0.8/0.2), attempt wiring (1 y 2),
  escalado del segundo intento, candidato canónico, repair shape-only, ranking,
  best candidate, anti-regresión y operational target como no-gate quedaron
  aprobados. Cero HIGH. **F1 MEDIUM:** la generación inicial presentaba el doble
  target `preferredWords≈52` (formulado como objetivo) junto al operational target
  `50`. **F2 LOW** aceptado y no corregido (branch defensivo del helper). **F3 LOW**
  asociado (documentación sobreafirmaba el presupuesto inicial como inequívoco).
- **Fix F1 (follow-up):** la generación inicial ya no expone `preferredWords` como
  target accionable. `preferredWords=52` queda como dato del perfil
  (`preferredWords del perfil: 52`) y `maximumWords=52` como hard boundary; el único
  target accionable de generación es `operationalWordTarget=50`. C2 reforzado contra
  el doble target (`aproximadamente 52 palabras objetivo` ausente). `calculate_word_budget`
  y `duration_profiles.py` sin cambios.
- **Pendiente:** reaprobación read-only focalizada del length-control hardening,
  commit del hardening y quinto E2E V2 canónico. Cero PASS todavía; Slice 6B abierto;
  change abierto.

### Slice 6B — Quinto E2E V2 canónico (ejecutado 2026-08-14)

- **HEAD de ejecución:** `4683313589dd2be3e97277c8ff06429b5a3ffd9b`; working tree limpio (solo warning permisos `data/postgres/`).
- **Preflight focalizado (sin suite completa, ya validada por el cierre):** C2 `1 passed`; length-control C1–C11 `16 passed`; dry-run V2 `22 passed`.
- **Providers:** LLM `openai` (`gpt-4o-mini`); Wikimedia activo + Pixabay activo (con key); Pexels/FreeAI/Pollinations deshabilitados; TTS `edge_tts` (sí alcanzado). Docker client/server `29.1.3`; imagen `linuxserver/ffmpeg:latest` presente.
- **Comando exacto:** `python3 bin/run_job.py --topic "Cómo se forma un arcoíris" --duration 30`.
- **Una única invocación top-level;** inicio `2026-08-14T17:35:09+02:00` (epoch `1786721709`); fin `2026-08-14T17:36:12+02:00` (epoch `1786721772`); duración 63 s; exit code 0.
- **Job ID:** `cmo-2026-08-14-153529`; path `data/videos/cmo-2026-08-14-153529`; tamaño 50 M; artefactos: `metadata.json`, `assets/` (10 jpg), `scenes/` (5 mp3).
- **Resultado: script PASS** (primera vez en la serie de cinco E2E); **assets ASSETS_READY** (10/10 resueltos, cero fallidos); **bloqueo posterior en `audio`** con `REVIEW_REQUIRED` por `AUDIO_DURATION_MISSING`.
- **Length-control hardening validado mediante E2E real:** initial `55` (menor overshoot de la serie; `+3` sobre 52, frente a `+22/+8/+4/+17` de E2Es 1–4) → compression `52` (in-range). `durationContract.status=PASS`; `structureValid=true`; contratos `47/52/52` y `operationalWordTarget=50` vigentes.
- **Contrato visual y estructura válidos:** `schemaVersion==2`, `allowGeneratedImages=false`, `structureValid=true`, `structureIssues==[]`, 5 escenas con `visualPlan._schemaVersion==2`, `sceneNumber` secuencial 1–5, cero campos V1, enums válidos (`photograph`/`diagram`/`stock`), `imageGenerationPrompt`/`negativePrompt` en `null`.
- **Contrato temporal final:** `wordCount=52`, `sceneWordCounts=[9,12,12,10,9]`, `spokenDurationSec=28.4`, `pauseDurationSec=1.4`, `estimatedDurationSec=29.8`; `minimumWords=47`/`preferredWords=52`/`maximumWords=52`; `status=PASS`; `retries=1`; `bestAttempt=1`; `bestAttemptWordCount=52`; `lastAttemptDiscardedAsRegression=false`.
- **Retry history:** attempt 0 initial `55` (`above_maximum_words`, exceso +3, `structureValid=true`, rank `[3,3]`, `becameBestCandidate=true`) → attempt 1 compression `52` (`in_range`, `durationStatus=PASS`, rank `[0,0]`, `wordCountSource=repaired_candidate`, `acceptedAsBest=true`). Targets por escena `[10,11,11,10,10]` como guidance (`repairSceneTargetsMet=false` aceptado); presupuesto global como único contrato (`repairGlobalBudgetValid=true`). Sin compression attempt 2 (ya en rango). Temperatura compression `0.2` / resto `0.8`.
- **Blocker posterior (independiente del length-control):** audio — los 5 mp3 existen y son válidos, pero `durationSec`/`durationSource`/`activeAudioDurationSec` = `null` durante el run y `duration_estimated=true`, produciendo `AUDIO_DURATION_MISSING: scenes [1..5] lack valid measured duration`. No hay `ffprobe` host; el fallback Docker (`--entrypoint ffprobe`, mount `parents[3]:/workspace`, `DOCKER_API_VERSION=1.43`) devolvió duración válida al verificar manualmente el mismo mount (`5.184s` para scene-01), sugiriendo un fallo transitorio de medida, no un problema del archivo. Cero modificación; no se relanza audio manualmente.
- **Etapas posteriores no alcanzadas:** prepare/render/validate no ejecutadas; `outputVideoPath=null`; `validationStatus=null`; `qualityGate` no ejecutado.
- **Verdict:** `SLICE_6B_FIFTH_E2E_LENGTH_CONTROL_VALIDATED_PIPELINE_BLOCKED`.
- **Cero cambios productivos** (`bin tests src` intactos; hashes idénticos al snapshot inicial); cero segunda invocación; cero MCP; cero reindexado; cero commit/push; staging vacío; jobs históricos (`cmo-2026-08-02-192443`, `cmo-2026-08-02-204451`, `cmo-2026-08-04-195654`, `cmo-2026-08-11-185926`) intactos. Solo `data/cache/pixabay-v2/` creado como caché automática del provider durante el run real (artefacto runtime untracked, no manual).
- **Comparativa E2E 1–5:** initial `74`/`60`/`56`/`69`/`55` → final `54`/`69`/`56`/`62`/`52`; structure inválida/válida/válida/válida/válida; script `REVIEW_REQUIRED`×4 → **PASS**.
- Slice 6B y el change `retire-legacy-visual-v1` continúan abiertos; pendiente: diagnóstico del bloqueo de audio y auditoría read-only final.

### Slice 1 completado (2026-07-17)

- `generate_script.py`: default de `--visual-schema-version` cambiado de 1 a 2; choices [1, 2] conservados; V1 explícito directo sigue soportado sin reinterpretación
- `run_job.py`: `build_script_command()` añade `--visual-schema-version 2`
- Tests focalizados: 13 passed, 0 failed
- Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES` — único finding: descripción stale en session log (corregido)
- No se ha implementado rechazo de jobs V1 ni eliminación de código V1

### Slice 2 completado (2026-07-22)

- `run_job.py`: clasificador `_classify_visual_schema()` fail-closed con 5 categorías
- `run_job.py`: `_schema_error_for_category()` mapea categorías a errores del contrato
- `run_job.py`: validación en bloque común post-script; V1 puro → `UNSUPPORTED_LEGACY_SCHEMA`; mixed → `MIXED_VISUAL_PLAN_SCHEMA_VERSIONS`; inválido → `INVALID_VISUAL_SCHEMA`
- `run_job.py`: `build_stage_command()` siempre devuelve `fetch_images_v2.py` para assets desde el pipeline canónico
- `fetch_images.py` sigue existiendo físicamente (retirada aplazada a Slice 4)
- La rama V1 de `_verify_stage_contract` permanece en el archivo, pero es inalcanzable desde el pipeline canónico tras el guard. Su limpieza queda aplazada a Slice 4.
- Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES` — sin findings funcionales bloqueantes
- Tests focalizados confirmados: 62 passed, 0 failed
- Slice 2 cerrado mediante commit de cierre

### Slice 3A cerrado (2026-07-22)

- `generate_script.py`: `--visual-schema-version` choices restringido a `[2]`; `--visual-schema-version 1` produce `SystemExit(2)` vía argparse
- `generate_script.py`: `call_llm` default cambiado de `SYSTEM_PROMPT` a `SYSTEM_PROMPT_V2`
- `generate_script.py`: `main()` aplanado a V2-only — sin ramas productivas V1
- `generate_script.py`: `visuals_request["schemaVersion"]` siempre 2; `visualSchemaVersion` stdout siempre 2
- Sin flag y con flag `--visual-schema-version 2`, `generate_script.py` usa V2
- Retry, validación y canonicalización son exclusivamente V2 en runtime
- `run_job.py` continúa pasando `--visual-schema-version 2` (sin cambios)
- SYSTEM_PROMPT y helpers V1 siguen físicamente presentes, sin callers productivos desde main()
- Eliminación física de V1 pertenece a Slice 3B
- Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES` — sin findings funcionales bloqueantes
- Tests focalizados confirmados: 138 passed, 0 failed
- Slice 3A cerrado mediante el commit de esta iteración

### Slice 3B1 implementado, revisado y cerrado mediante `5a4e7f2` (2026-07-22)

- `generate_script.py`: cuatro símbolos V1 de prompts eliminados (`SYSTEM_PROMPT`, `_build_duration_prompt_instruction`, `_build_retry_instruction`, `_build_user_prompt`)
- `tests/test_generate_script.py`: 17 tests V1 eliminados; 35 tests permanecen (validator, retry-loop V2, asset-side, segment-count)
- `tests/test_duration_profiles.py`: migrados a equivalentes V2 vía aliases locales; 36 tests pasan
- Fixture `_GOOD_3_SCENE_SCRIPT`, `PROMPT_PATH` eliminados sin impacto; `import re` eliminado de tests/test_generate_script.py (conservado en bin/generate_script.py)
- runtime continúa V2-only
- `_validate_script_structure` continúa temporalmente presente (Slice 3B2)
- Tests del validator V1 siguen presentes (Slice 3B2)
- Resultados tests focalizados:
  - `test_duration_profiles.py`: 36 passed
  - `test_generate_script.py`: 35 passed
  - `test_generate_script_v2.py`: 77 passed
  - `test_v2_only_generation_contract.py`: 7 passed
  - `test_run_job.py -k build_script_command`: 2 passed
- Slice 3B2 es el siguiente trabajo
- Slice 4 no ha comenzado

### Slice 3B2 implementado, revisado y cerrado mediante el commit de esta iteración (2026-07-24)

- `_validate_script_structure` eliminado
- imports editoriales eliminados de generate_script.py
- import re conservado
- tres re.sub productivos conservados
- 25 tests dependientes del validator V1 eliminados
- tests/test_generate_script.py queda con diez tests
- _build_scene_script eliminado
- _seg_script eliminado
- test_shared_contract_used_by_fetch_and_generate transformado en test_fetch_images_imports_editorial_contract
- reglas neutrales de estructura siguen cubiertas por _validate_and_canonicalize_script_v2 y tests/test_generate_script_v2.py
- validación histórica V1 eliminada sin migración
- reglas editorialRole, visualTemporalIntent y assetType V1 eliminadas de generate_script sin migración
- segment-count V1 eliminado sin migración
- editorial_asset_contract continúa utilizado por fetch_images.py hasta Slice 4
- Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES`.
- Cero findings bloqueantes.
- Dos notas cosméticas dentro del slice corregidas antes del commit:
  - separación de líneas top-level en generate_script.py;
  - newline final en tests/test_generate_script.py.
- Comentario stale de fetch_images.py aplazado a Slice 4.
- tests focalizados:
  - test_generate_script.py: 10 passed
  - test_generate_script_v2.py: 77 passed
  - test_duration_profiles.py: 36 passed
  - test_v2_only_generation_contract.py: 7 passed
  - test_run_job.py -k build_script_command: 2 passed
  - total: 132 passed, 0 failed
- Slice 3B3 es el siguiente trabajo
- Slice 4 no ha comenzado

### Slice 3B3 implementado, revisado y cerrado mediante el commit de esta iteración (2026-07-25)

- `generate_script.py`: argumento `--visual-schema-version` eliminado del parser
- `generate_script.py`: variable `args.visual_schema_version` eliminada
- `generate_script.py`: `request.visuals.schemaVersion=2` conservado
- `generate_script.py`: `visualSchemaVersion=2` conservado en salidas diagnósticas (dry-run, normal, JSON)
- `generate_script.py`: exactamente tres `re.sub` conservados
- `run_job.py`: `build_script_command()` ya no pasa el selector
- `run_job.py`: validación de schema V1/mixed/invalid permanece intacta
- Tests del selector transformados, no eliminados
- `test_generate_script_v2.py` continúa con 77 tests
- `test_v2_only_generation_contract.py` continúa con 7 tests
- `test_generate_script.py`: 10 tests (sin cambios)
- `test_duration_profiles.py`: 36 tests (sin cambios)
- `test_run_job.py -k build_script_command`: 2 tests (sin cambios)
- Total focalizado: 132 passed, 0 failed
- Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES`.
- Cero findings bloqueantes.
- El selector CLI fue eliminado del parser y del caller productivo.
- El contrato persistido `request.visuals.schemaVersion=2` permanece.
- Los diagnósticos `visualSchemaVersion=2` permanecen.
- Los tests fueron transformados sin reducción de conteo.
- Tests focalizados finales: 132 passed, 0 failed.
- Slice 4A es el siguiente trabajo.
- Slice 4A implementado pendiente de review y commit.
- Slice 4B no ha comenzado.

### Slice 4A implementado, revisado y cerrado mediante el commit de esta iteración (2026-07-25)

- `run_job.py`: `STAGE_SCRIPTS` ya no referencia `fetch_images.py`
- `run_job.py`: retirados `_collect_visual_plan_schema_versions`, `_uses_v2_visual_assets`, `_check_mixed_schema_versions`
- `run_job.py`: `_verify_stage_contract` para assets simplificado a contrato V2-only (`assets/`, `V2_IMAGE_EXTENSIONS`)
- `run_job.py`: clasificación y rechazo de V1/mixed/invalid conservado (`_classify_visual_schema`, `_schema_error_for_category`, `V1_POSITIVE_FIELDS`)
- `tests/test_run_job_v2_assets.py`: retiradas 4 clases legacy (25 tests). Quedan 20 tests V2-only
- `tests/test_generate_script_v2.py`: `test_run_job_modules_unchanged` transformado a contrato V2 vigente (77 tests)
- `tests/test_run_job.py`: `test_assets_ready_with_images_passes` migrado a contrato V2 (`assets/`, schemaVersion=2)
- `fetch_images.py` sigue existiendo hasta Slice 4B
- `editorial_asset_contract.py` sigue existiendo hasta Slice 4B
- Conteos AST finales: test_run_job_v2_assets.py=20, test_generate_script_v2.py=77, test_run_job.py=91
- Tests focalizados:
  - test_run_job_v2_assets.py: 20 passed, 0 failed
  - test_run_job.py (5 clases focalizadas): 48 passed, 0 failed
  - test_generate_script_v2.py: 77 passed, 0 failed
  - test_fetch_images_v2.py: 39 passed, 0 failed
- Total focalizado de Slice 4A: 184 passed, 0 failed.
- El fallo de `test_v2_metadata_reaches_assets` se debía a reutilización de metadata mutable en el test y quedó corregido.
- Cero regresiones focalizadas detectadas.
- Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES`.
- Cero findings bloqueantes.
- Review confirmó que no existen callers productivos a `fetch_images.py` desde el runner.
- Review confirmó que la clasificación y rechazo V1/mixed/invalid permanece intacta.
- Review confirmó el contrato V2-only de assets.
- Review confirmó los conteos AST:
  - test_run_job_v2_assets.py: 20;
  - test_generate_script_v2.py: 77;
  - test_run_job.py: 91.
- Tests focalizados finales: 184 passed, 0 failed.
- Slice 4B no iniciado

### Slice 4B1 implementado, revisado y cerrado mediante el commit de esta iteración (2026-07-25)

- `fetch_images.py` eliminado físicamente
- `editorial_asset_contract.py` eliminado físicamente
- stack V2 intacto
- cero imports residuales desde `bin/` y `tests/`
- `test_semantic_asset_validation.py`: 76 tests → 8 tests
- `test_no_topic_specific_contamination.py`: 26 tests → 4 tests
- `test_generate_script.py`: 10 tests → 3 tests
- 97 tests legacy eliminados
- 15 tests neutrales conservados en esos tres archivos
- configuración Pexels no modificada
- Slice 4B2 no iniciado
- tests focalizados: 292 passed, 0 failed
- Review final: `APPROVE_WITH_NON_BLOCKING_NOTES`.
- Cero findings bloqueantes.
- Dos módulos legacy eliminados físicamente:

  - `bin/fetch_images.py`;
  - `bin/editorial_asset_contract.py`.
- Cero imports o callers productivos residuales.
- Stack V2 intacto.
- Clasificación y rechazo V1/mixed/invalid del runner intactos.
- 97 tests exclusivamente legacy eliminados.
- 15 tests neutrales conservados.
- Conteos finales:

  - `test_semantic_asset_validation.py`: 8;
  - `test_no_topic_specific_contamination.py`: 4;
  - `test_generate_script.py`: 3.
- Total focalizado final: 292 passed, 0 failed.
- README y runbook primario utilizan CLI V2 válido.
- Runbook primario documenta:

  - script → assets → audio → prepare → render;
  - assets visuales bajo `assets/`.
- Configuración Pexels no modificada (hasta Slice 4B2).
- Slice 4B2 no iniciado.

### Slice 4B2 implementado, revisado y cerrado mediante el commit de esta iteración (2026-07-25)

- `PEXELS_API_KEY` eliminado de `.env.example`
- passthrough de `PEXELS_API_KEY` eliminado de `docker-compose.yml`
- cero consumidores productivos o workflows de `PEXELS_API_KEY`
- entrada `pexels` conservada como proveedor V2 planificado
- Pexels continúa `disabled` y `not implemented`
- Pixabay continúa activo con `PIXABAY_API_KEY`
- Wikimedia continúa activo sin API key
- FreeAI y Pollinations no modificados
- routing y executor no modificados
- tests focalizados ejecutados: todos pasados
- Review final: `APPROVE_WITH_NON_BLOCKING_NOTES`.
- Cero findings bloqueantes.
- `PEXELS_API_KEY` eliminado de `.env.example`.
- Passthrough eliminado de `docker-compose.yml`.
- Cero consumidores productivos o workflows n8n.
- Entrada `pexels` conservada como provider planificado.
- Pexels continúa disabled y not implemented.
- `requiresApiKey=True` representa una capacidad futura, no un contrato activo de variable.
- Pixabay continúa activo con `PIXABAY_API_KEY`.
- Wikimedia continúa activo sin API key.
- FreeAI y Pollinations permanecen sin cambios.
- Router, executor, bridge y fetcher V2 intactos.
- Tests sin modificaciones.
- Conteos focalizados:

  - test_visual_provider_config_v2.py: 13;
  - test_visual_asset_executor_v2.py: 102;
  - test_visual_asset_router_v2.py: 102;
  - test_visual_asset_bridge_v2.py: 34;
  - test_fetch_images_v2.py: 39;
  - test_visual_v2_dry_run_e2e.py: 22;
  - test_failure_no_env_vars_in_metadata: 1.
- Total focalizado final: 313 passed, 0 failed.
- Slice 4 completo.
- Slice 5 pendiente.

## Slice 5A implementado, revisado, corregido, reaprobado y cerrado (2026-07-30)

- README.md reestructurado con identidad centrada en un generador genérico y configurable, independiente de la temática
- `bin/run_job.py` documentado como orquestador canónico
- n8n documentado como infraestructura legacy o alternativa, no como orquestador
- Providers documentados según su estado real (Wikimedia+Pixabay activos, Pexels planificado/deshabilitado, FreeAI+Pollinations deshabilitados)
- Arquitectura actual separada del roadmap futuro
- `docs/project/architecture.md` actualizado con arquitectura actual y futura; referencias legacy retiradas; sección de modelo de configuración añadida
- `docs/architecture/modular-v2-transformation-roadmap.md` actualizado con estado real del progreso
- `openspec/changes/retire-legacy-visual-v1/tasks.md` reestructurado en Slice 5A/5B
- Ocho archivos modificados (corrección de identidad previa al review), un session log actualizado
- Commit de cierre: `f2a8078` (`docs(product): align V2 identity and current architecture`). Cero push, cero reindexados y cero llamadas MCP.

### Limpieza de residuos de identidad runtime (post-implementación, previa al review)

- `bin/run_job.py`: ejemplo del docstring cambiado de "La batalla de Stalingrado" a "Cómo se forma un arcoíris"
- `bin/validate_job.py`: docstring del módulo cambiado de "Validación automatizada de jobs de shorts-históricos" a "Validación automatizada de jobs de vídeos cortos"
- `bin/validate_job.py`: descripción CLI cambiada de "Validate a shorts-historicos job" a "Validate a shorts-creator job"
- `bin/prepare_job.py`: cabecera ASS neutralizada de "shorts-historicos" a "generated by shorts-creator"
- Todos los cambios son exclusivamente textuales, sin efecto funcional
- `visual_normalize.py` permanece presente físicamente; `validate_job.py` importa `normalize_scene_visual` pero nunca lo invoca (import muerto). Es deuda técnica fuera del alcance de `retire-legacy-visual-v1` y debe tratarse en una limpieza de código posterior.
- Ocho archivos modificados (README.md, bin/run_job.py, bin/validate_job.py, bin/prepare_job.py, docs/architecture/modular-v2-transformation-roadmap.md, docs/project/architecture.md, docs/project/current-state.md, openspec/changes/retire-legacy-visual-v1/tasks.md), un session log actualizado
- Cero staging, cero commits, cero reindexados
- Review read-only formal: CHANGES_REQUIRED por una fila Markdown mal formada en la tabla de variables obligatorias del README (F1 MEDIUM).
- F1 corregido mediante una sustitución documental mínima (fila `LLM_PROVIDER` normalizada a dos celdas).
- Reaprobación read-only focalizada: APPROVED_FOR_COMMIT; F2 preservado como LOW no bloqueante.
- Tests focalizados ya ejecutados; los cambios son exclusivamente textuales, sin efecto funcional.
- Cierre mediante el commit de esta sesión con el mensaje `docs(product): align V2 identity and current architecture`.
- Commit de cierre: `f2a8078`, con nueve archivos incluidos; working tree final limpio.
- Cero push, cero reindexados, cero llamadas MCP.

## Slice 5B implementado, auditado con CHANGES_REQUIRED, corregido y reaprobado (2026-08-01)

Slice 5B del change `retire-legacy-visual-v1` implementado. Cambios exclusivamente documentales y de configuración de plantilla; sin cambios de código productivo.

Archivos modificados (implementación):

- `.env.example`: identidad genérica; `PROJECT_ROOT` corregido a `/home/javi/projects/shorts-creator` (solo plantilla); `POSTGRES_DB` conservado; documentado `SUBTITLE_GLOBAL_OFFSET_MS` y variables sin consumidor
- `AGENTS.md`, `Makefile`, `openspec/project.md`: identidad genérica
- `docs/project/environment.md`: componentes (CLI canónico / n8n·Postgres legacy / render worker) y requisitos de variables actualizados
- `docs/project/integrations.md`: estado de providers alineado con runtime
- `docs/project/vision.md`: producto genérico configurable; historia como caso de uso posible
- `docs/runbooks/n8n-operations.md`: n8n como infraestructura legacy
- `.opencode/agents/*.md` (5): identidad genérica
- `openspec/changes/retire-legacy-visual-v1/tasks.md`: estado de implementación de Slice 5B
- `docs/sessions/20260801-000000-retire-legacy-visual-v1-slice-5b-build.md`: session log de implementación

Decisiones de compatibilidad:

- `PROJECT_ROOT` corregido solo en `.env.example` (plantilla); no se toca ningún `.env` real.
- `POSTGRES_DB=shorts_history` conservado por compatibilidad con infraestructura n8n/PostgreSQL y datos persistidos existentes.
- Workflows n8n JSON y `HANDOVER.md` preservados intactos (legacy / contexto legacy frío).
- Código productivo (`bin/`, `tests/`, `docker-compose.yml`) no modificado.

### Auditoría read-only y correcciones (2026-08-01)

La auditoría read-only terminó con `SLICE_5B_REVIEW_CHANGES_REQUIRED`.

Findings corregidos:

- **F1 MEDIUM:** `.env.example` afirmaba soporte nativo `openai | anthropic | google`; se corrigió a "openai, mediante cliente OpenAI-compatible" y se eliminó el bloque alternativo Anthropic. Runtime (`bin/generate_script.py`) solo implementa `provider == "openai"`.
- **F2 MEDIUM:** `docs/project/environment.md` conservaba el layout plano legacy de datos; se sustituyó por el layout canónico `data/videos/{jobId}/`. Python pasó a dependencia obligatoria (3.10+); Faster-Whisper queda opcional.
- **F3 MEDIUM:** `docs/runbooks/n8n-operations.md` omitía `validate`, no presentaba `bin/run_job.py` como vía canónica y referenciaba `bin/review_job.py`; se añadió la etapa de validación, `bin/run_job.py` como orquestador canónico y se corrigió la ruta a `review_job.py`.
- **F4 MEDIUM:** `docs/project/current-state.md` con metadata y próximos pasos obsoletos; se actualizó fecha, resumen, bloque de Slice 5B y próximos pasos.
- **F5 LOW:** `docs/project/integrations.md` describía Edge TTS como síntesis "local"; se reformuló como cliente Python del servicio Microsoft Edge TTS (sin API key, requiere red, no es offline).
- **F6 LOW:** `docs/project/vision.md` afirmaba que cada vídeo tiene una bitácora y un change OpenSpec; se distinguió trazabilidad del job de la trazabilidad de cambios de desarrollo.

Nota no bloqueante:

- **F7 NOTE:** el session log conserva el timestamp `000000`. No existe una hora real verificable del Build y no se inventa un timestamp.

### Reaprobación read-only focalizada (2026-08-01)

La reaprobación read-only focalizada terminó con `SLICE_5B_REAPPROVED_FOR_CLOSURE`.

- F1–F6 confirmados como resueltos.
- Un LOW no bloqueante aceptado en `docs/project/integrations.md`: la frase `Anthropic/Google como opciones declaradas pero no verificadas como clientes implementados`, desambiguada por la línea siguiente que indica que solo existe un cliente OpenAI-compatible.
- F7 aceptado como NOTE no bloqueante (timestamp `000000`; sin hora real verificable; no se renombra ni se inventa una hora).
- Slice 5B aprobado para cierre.
- Repositorio sin cambios durante la reaprobación.
- Commit de cierre todavía pendiente en este punto.
- Slice 6 no iniciado.

### Cierre de Slice 5B (2026-08-01)

- Slice 5B cerrado mediante el commit `1d9fe37` (`docs(project): align Slice 5B environment and integrations`).
- Cero push, cero MCP, cero reindexado.
- Slice 6 es el siguiente trabajo.

## Slice 6A — Baseline y corrección (2026-08-01)

Estado: `SLICE_6A_REAPPROVED_FOR_COMMIT`; Slice 6A cerrado mediante el commit
`86170d3`. Slice 6A implementado, auditado, corregido, reaprobado y cerrado.
La corrección focalizada de tests (11 neutrales, C2) está completa y verde, el
bloqueo de `test_timing_regression.py` fue resuelto hermetizando sus cuatro
tests (Estrategia A, C5), y el fallo C4 de aislamiento de
`test_fetch_images_v2.py::TestSourceIsolation::test_no_v1_runtime_imports`
fue corregido con restauración gestionada de `sys.modules`. La suite completa
queda verde: **baseline funcional `1102 passed, 0 failed`**. Los cambios
funcionales están validados; la auditoría read-only terminó con CHANGES_REQUIRED
exclusivamente documental y las correcciones documentales F4–F9 están aplicadas.
La reaprobación read-only focalizada finalizó con `SLICE_6A_REAPPROVED_FOR_COMMIT`
con cero findings bloqueantes; F1/F2 LOW y F3 NOTE fueron aceptados como no
bloqueantes y no se corrigieron. Los tres tests (`test_run_job.py`,
`test_timing_regression.py`, `test_fetch_images_v2.py`) no cambiaron durante las
correcciones documentales ni durante la reaprobación. Slice 6A cerrado mediante
el commit `86170d3` (`test(v2): establish clean Slice 6A baseline`). En el
momento del cierre de Slice 6A, Slice 6B todavía no se había iniciado.
Posteriormente se ejecutó el primer E2E; consultar la sección Slice 6B.

### HEAD inicial

- Rama `main`; HEAD `3866cc6a547545cad70cc1c5fbbacb08ef216713`.
- Últimos commits: `3866cc6` (record Slice 5B closure), `1d9fe37` (align Slice 5B).
- Working tree limpio; staging 0; `git diff --check` limpio.

### Causa de los 11 fallos

- `tests/test_run_job.py` presentaba 11 tests neutrales (pipeline multi-etapa)
  cuyas fixtures/metadata inline no satisfacían el contrato de schema V2.
- El clasificador fail-closed `_classify_visual_schema` de `bin/run_job.py`
  devolvía `SCHEMA_NOT_AVAILABLE_YET`/`INVALID_SCHEMA` (sin `script.scenes` o
  sin `visualPlan._schemaVersion=2`), por lo que el runner abortaba en la etapa
  `assets` con `INVALID_VISUAL_SCHEMA` y los tests no alcanzaban su etapa prevista.
- No se restauró compatibilidad V1 ni se debilitó `INVALID_VISUAL_SCHEMA`.

### Archivos modificados

- `tests/test_run_job.py` (único archivo de código de 6A; +85/−46 aprox.)
- `tests/test_timing_regression.py` (hermetización en 6A2)
- `tests/test_fetch_images_v2.py` (corrección de aislamiento C4 en 6A3)
- `openspec/changes/retire-legacy-visual-v1/tasks.md`
- `docs/project/current-state.md`
- `docs/sessions/20260801-000000-retire-legacy-visual-v1-slice-6a-baseline.md` (session log 6A + follow-up 6A2 + follow-up 6A3)

### Corrección aplicada (6A)

- Se añadió el helper `_v2_meta(meta)` que enriquece una metadata neutral con el
  contrato V2 mínimo (`script.scenes[].visualPlan._schemaVersion == 2`) sin mutar
  objetos compartidos y sin inventar campos.
- Se aplicó `_v2_meta` a las metadata inline de los 11 tests neutrales.
- Se añadió una imagen en `assets/` (p. ej. `seg_001.jpg`) en los tests
  multi-etapa que necesitan que la etapa `assets` pase su contrato de salida.
- Se corrigió la coincidencia de comando `"fetch_images.py"` → `"fetch_images_v2.py"`
  en dos tests (el runner canónico usa `fetch_images_v2.py`); cambio justificado
  porque impedía corregir esos tests directamente.
- Solo se migraron fixtures neutrales a V2. Los tests de rechazo V1, mixed e
  invalid quedaron intactos. No se cambiaron expected statuses ni aserciones.

### Hermetización de `test_timing_regression.py` (6A2)

- Los 4 tests de timing (`test_sentence_boundary_crossing`,
  `test_punctuation_restoration`, `test_no_cross_scene_leakage`,
  `test_no_single_word_by_boundary`) se reescribieron bajo Estrategia A: importan
  las funciones puras de `bin/generate_audio.py` (`build_full_narration`,
  `_build_canonical_tokens`, `_match_words_to_canonical`, `group_words_into_cues`,
  `_strip_punct`) y usan WordBoundary/cues sintéticos deterministas.
- No se ejecuta `generate_audio.py` como subprocess; no se contacta Edge TTS; no
  se crea audio real; no se usa red, Docker, `.venv`, ni
  `data/videos/la-2026-07-01-173458`.
- Se añadió el fixture `hermetic_guard` que falla de inmediato ante
  `subprocess.run`/`Popen`, `socket.create_connection`, `socket.socket` o un
  provider TTS real (`generate_audio.get_provider`).
- Resultado focalizado: `4 passed`.
- Clasificación del bloqueo heredado: C5 — dependencia de entorno/integración
  externa no hermética (Edge TTS).

### Resultados de `tests/test_run_job.py`

- Antes: `11 failed, 80 passed`.
- Después (aislado): `91 passed, 0 failed`.

### Grupos focalizados

- `test_run_job.py` + `test_semantic_asset_validation.py`: `99 passed`.
- `test_run_job.py` + `test_timing_regression.py` + `test_semantic_asset_validation.py`: `103 passed`.
- Generación/runner V2 (`test_generate_script.py`, `test_generate_script_v2.py`,
  `test_v2_only_generation_contract.py`, `test_run_job_v2_assets.py`): `107 passed`.
- Assets V2 (`test_fetch_images_v2.py`, `test_visual_provider_config_v2.py`,
  `test_visual_asset_executor_v2.py`, `test_visual_asset_router_v2.py`,
  `test_visual_asset_bridge_v2.py`): `290 passed`.
- Dry-run E2E (`test_visual_v2_dry_run_e2e.py`): `22 passed`.

### Preflight de suite y ejecución completa

- `--collect-only tests/`: `1102 tests collected`, cero errores de colección, no
  recorre `data/postgres/`.
- Preflight de efectos externos: subprocess/urllib/socket/edge_tts aparecen en la
  suite, pero todos están mockeados o son imports sin red. `test_continuous_audio.py`
  usa docker/subprocess reales pero solo tiene `main()` (sin funciones `test_`),
  por lo que no se recopila.
- `python3 -m pytest -q tests/ --tb=short`:
  `20 failed, 1082 passed in 12.25s`.

### Fallo adicional de suite (Caso B, resuelto en 6A3)

- Los 20 fallos eran de `tests/test_run_job.py`, **preexistentes** (reproducibles
  con `--ignore=tests/test_timing_regression.py`).
- Causa raíz C4: `tests/test_fetch_images_v2.py::test_no_v1_runtime_imports` hacía
  `sys.modules.pop("run_job", None)` (y otros módulos) sin restauración; el
  `monkeypatch.setattr(sys, "modules", sys.modules)` es un no-op y no registra
  ninguna entrada. Por el orden alfabético de pytest (`fetch_images_v2` <
  `run_job`), `test_run_job.py` corre después y sus `patch("run_job.*")` quedan
  rotos: `patch` reimporta un módulo `run_job` nuevo, distinto del objeto que el
  `main()` ya importado por `test_run_job.py` referencia.
- Clasificación: C4 — test demasiado acoplado por mutar estado global sin restaurar.
- Corrección (6A3): las eliminaciones de `sys.modules` se movieron a
  `with monkeypatch.context() as scoped:` usando `scoped.delitem(sys.modules, mod, raising=False)`,
  que registra y restaura el valor original al salir del bloque. Se añadió
  verificación de identidad post-contexto (objeto original restaurado, o ausencia
  conservada). El propósito del test (comprobar que `fetch_images_v2.main()` no
  reimporta los módulos legacy retirados — `fetch_images`, `asset_validation`,
  `editorial_asset_contract` — ni los módulos productivos vigentes cuya importación
  se bloquea por aislamiento de capas — `generate_script`, `prepare_job`,
  `render_job`, `run_job`) se conserva intacto. La variable de test continúa
  llamándose `v1_modules`, pero su nombre es impreciso y no implica que los siete
  módulos sean legacy.
- Archivo corregido: `tests/test_fetch_images_v2.py` (único archivo de 6A3).
- No se modifica producción.

### Reproducción mínima del C4 (6A3)

- `test_no_v1_runtime_imports` aislado: `1 passed`.
- Orden contaminante (`test_no_v1_runtime_imports` → `test_script_stage_extracts_job_id`):
  antes de la corrección `1 failed, 1 passed`; después `2 passed`.
- Orden inverso: `2 passed`.
- Prueba mínima de 4 tests (contaminante + 3 del runner): `4 passed`.

### Baseline

- Suite completa: **`1102 passed, 0 failed`** — baseline vigente de Slice 6A para el
  HEAD actual, establecida.
- `20 failed, 1082 passed` queda únicamente como resultado intermedio histórico
  de 6A2, no como baseline vigente.
- Baseline focalizada de 6A2: `test_run_job.py` = 91, `test_timing_regression.py` = 4,
  combinado = 103, V2 = 107/290/22.
- La baseline histórica `1215 passed, 16 failed` (Phase A) se conserva únicamente
  como cifra de referencia histórica, no como baseline de suite vigente.

### Estado

- Auditoría read-only completada con `SLICE_6A_REVIEW_CHANGES_REQUIRED`
  (F4–F6 MEDIUM documentales; F1/F2 LOW y F3 NOTE no bloqueantes preservados).
- Correcciones documentales F4–F9 aplicadas.
- Reaprobación read-only focalizada finalizada con `SLICE_6A_REAPPROVED_FOR_COMMIT`
  con cero findings bloqueantes; F1/F2 LOW y F3 NOTE aceptados como no bloqueantes.
- Los tres tests (`test_run_job.py`, `test_timing_regression.py`,
  `test_fetch_images_v2.py`) no cambiaron durante las correcciones documentales
  ni durante la reaprobación.
- Baseline funcional vigente: `1102 passed, 0 failed`.
- Slice 6A implementado, auditado, corregido, reaprobado y cerrado mediante el
  commit `86170d3` (`test(v2): establish clean Slice 6A baseline`).
- Slice 6B se ejecutó posteriormente (E2E V2 canónico) y su corrección de
  prompt/retry está implementada; ver sección «Slice 6B» más abajo.
- Commit A (Slice 6A) incluyó los seis archivos del slice; cero push, cero MCP,
  cero reindexado, cero E2E real.
- F1/F2 LOW y F3 NOTE conservados como no bloqueantes.
- Cero E2E real.
- Cero push, cero MCP, cero reindexado.

## Slice 6B — E2E V2 canónico (ejecutado 2026-08-02)

- HEAD inicial: `496dd33abd07acb7dda5534613a882adf81ac84e`
- Working tree inicial limpio (solo el warning de permisos ignorado de `data/postgres/`)
- Timestamp de inicio: `2026-08-02T21:23:48+02:00` (epoch 1785698628); duración total 55s
- Tema: `Cómo se forma un arcoíris`; duración solicitada: 30s (perfil `short_25_30`)
- Comando exacto: `python3 bin/run_job.py --topic "Cómo se forma un arcoíris" --duration 30`
- Una única invocación top-level de `bin/run_job.py`
- Job ID: `cmo-2026-08-02-192443`; path `data/videos/cmo-2026-08-02-192443`
- Providers: LLM `openai` (cliente OpenAI-compatible), modelo `gpt-4o-mini`; visuales Wikimedia activo + Pixabay activo (con key), Pexels/FreeAI/Pollinations deshabilitados; TTS `edge_tts` (no alcanzado)
- Exit code: 0; el runner terminó de forma controlada, pero con estado final `REVIEW_REQUIRED`
- `lastCompletedStage`: `script`; `outputVideoPath`: null; `validationStatus`: null

### Estados por etapa

| Etapa | Estado |
|-------|--------|
| script | `REVIEW_REQUIRED` (detenido por contrato) |
| assets | no ejecutada |
| audio | no ejecutada |
| prepare | no ejecutada |
| render | no ejecutada |
| validate | no ejecutada |

### Auditoría de contrato V2 del job (metadata.json)

- `request.visuals.schemaVersion == 2`
- `script.scenes` = 5, todas con `visualPlan._schemaVersion == 2`; sin mezcla V1/V2
- Campos V1 residuales (`editorialRole`, `strategy`, `primaryAssetType`, `secondaryAssetType`, `visualTemporalIntent`): 0 apariciones
- `durationContract`: targetSec=30, minSec=27, maxSec=30, strictness=balanced, spokenWordsPerMinute=110

### Causa del bloqueo (documentada, sin corrección de código)

- `VISUAL_PLAN_V2_INVALID: v2 plan validation failed after 3 attempts`
  - `V2_STRUCTURE_INVALID_ENUM_VALUE:assetPreferences[0]: scene 3: got 'animation'`
  - `V2_STRUCTURE_INVALID_ENUM_VALUE:visualSequence[0].assetPreference: scene 3: got 'animation'`
  - `V2_STRUCTURE_INVALID_ENUM_VALUE:assetPreferences[0]: scene 5: got 'infographic'`
  - `V2_STRUCTURE_INVALID_ENUM_VALUE:visualSequence[0].assetPreference: scene 5: got 'infographic'`
  - Enums permitidos: archive, diagram, document, generated, illustration, map, painting, photograph, stock
- `DURATION_OUT_OF_RANGE: estimated=30.9s (spoken=29.5s + pauses=1.4s), target=30s, min=27s, max=30s, words=54, scenes=5`
- Retry history: retry 0 = 74 palabras (reduce_content); retry 1 = 59 palabras (reduce_content); retry 2 = 54 palabras + enums inválidos (fix_v2_structure_then_duration). Tras 3 intentos el plan V2 siguió inválido → `REVIEW_REQUIRED`.
- El orquestador respetó el contrato y terminó de forma controlada en `script` (BLOCKED válido por contrato, no PASS).

### Artefactos

- Único artefacto producido: `metadata.json` en el job (el pipeline se detuvo antes de assets/audio/prepare/render/validate)
- Sin vídeo final; sin `qualityGate` (etapa validate no alcanzada)

### Resultado

- Resultado: **BLOCKED** (`REVIEW_REQUIRED` controlado por contrato en `script`)
- Verdict: `SLICE_6B_E2E_NEEDS_FOLLOWUP`
- Cero cambios productivos (bin/tests/src intactos)
- Cero MCP, cero reindexado, cero staging, cero commit, cero push
- Slice 6B pendiente de auditoría read-only y de una sesión de corrección
- Change completo `retire-legacy-visual-v1` todavía abierto

### Auditoría read-only del primer intento — `SLICE_6B_REVIEW_CHANGES_REQUIRED` (2026-08-02)

- El job `cmo-2026-08-02-192443` quedó **BLOCKED** de forma controlada por contrato en `script` (`REVIEW_REQUIRED`, exit code top-level 0). Correcto.
- Diagnóstico aprobado:
  - **E1 — Prompt drift:** causa principal. El prompt mantenía una lista manual de `assetPreferences` independiente del contrato y la rama de retry `reduce_content` no re-declaraba el enum.
  - **E2 — Retry feedback incompleto:** causa contribuyente. Los retries de duración no recordaban el contrato visual.
  - **E5 — Incumplimiento estocástico del modelo:** contribuyente.
  - **E6 — Cobertura insuficiente:** confirmado (faltaban tests de enum/retry).
  - **E3 — Canonicalización insuficiente:** parcial.
  - **E4 — Validator incorrecto:** descartado.
- Decisiones: no modificar `bin/visual_plan_v2.py`; no relajar el contrato temporal; no aumentar `MAX_SCRIPT_ATTEMPTS` (sigue en 3); no ejecutar otro E2E en esta sesión.

### Corrección de prompt/retry (Slice 6B fix, Build)

- `bin/generate_script.py`:
  - El enum de `assetPreferences` del prompt se deriva ahora de `ALLOWED_ASSET_PREFERENCES` (fuente contractual en `visual_plan_v2.py`) vía `_build_asset_preferences_section()`. Lista cerrada estable y ordenada: archive, diagram, document, generated, illustration, map, painting, photograph, stock. Sin listas manuales divergentes.
  - El prompt condiciona `generated` a `allowGeneratedImage`, define `diagram` como valor exacto y añade regla de enum cerrado y términos prohibidos (animation, animated, infographic, photo, image, video).
  - `_build_retry_instruction_v2` ahora es siempre contractual: toda rama (incluida `reduce_content`) re-declara el enum cerrado, prohíbe sinónimos, ordena preservar campos válidos del `visualPlan`, fija el límite absoluto de palabras («como máximo N / No superes N») y pide revalidar estructura y duración antes de responder.
  - **Alias `infographic → diagram`: NO implementado.** La canonicalización contractual vive dentro de `canonicalize_visual_plan_v2` (en `bin/visual_plan_v2.py`, fuera de alcance) y no existe un punto pre-validator seguro en el flujo de `generate_script.py`; aplicar el alias exigiría una segunda arquitectura de canonicalización. Se documenta como mejora futura no bloqueante. `infographic` y `animation` continúan inválidos.
- `tests/test_generate_script_v2.py`: 8 tests añadidos (T1 enum-parity, T2 prompt inequívoco, T3 retry de duración, T4 retry combinado, T5 regresión `animation`/`infographic`, T6 preservación en `reduce_content`, T7 `MAX_SCRIPT_ATTEMPTS==3`).
- Tests focalizados: `test_generate_script_v2.py` = 85 passed; generación combinada = 131 passed; `test_run_job.py` = 91 passed.
- Suite completa: **`1110 passed, 0 failed`** (baseline anterior `1102`; +8 tests). Cero skips, cero xfail, cero warnings.
- Validator (`visual_plan_v2.py`), runner (`run_job.py`), perfiles (`duration_profiles.py`) y contrato temporal intactos.
- Slice 6B quedó pendiente de review read-only y de un nuevo E2E al cierre del Build; el review read-only se ejecutó posteriormente (ver sección «Review del Build y correcciones F1–F6»). Cero providers reales durante el Build; cero commit.
- No se declara PASS ni cierre.

### Review del Build y correcciones F1–F6 (Slice 6B fix review)

- La auditoría read-only de la corrección de prompt/retry terminó con `SLICE_6B_FIX_REVIEW_CHANGES_REQUIRED`.
- **F1 MEDIUM:** el primer prompt no transmitía de forma request-scoped que `allowGeneratedImages=false`.
- **F2 MEDIUM:** `tasks.md` presentaba el E2E simultáneamente completado y pendiente dentro de Slice 6A.
- **F3 LOW:** la prohibición `animation/infographic/photo/image/video` no estaba explícitamente limitada a valores del enum.
- **F4 LOW:** el retry no imprimía `issue["path"]` explícitamente.
- **F5 LOW:** faltaba una prueba integrada del flujo real `reduce_content`.
- **F6 LOW:** T1, T4 y T5 tenían comprobaciones insuficientemente precisas.
- Decisiones mantenidas: no modificar `visual_plan_v2.py`; no modificar `run_job.py`; no modificar `duration_profiles.py`; no relajar el contrato temporal; no aumentar `MAX_SCRIPT_ATTEMPTS`; no normalizar `animation`; no implementar `infographic → diagram` en esta sesión.

Correcciones F1–F6 aplicadas (Build del review fixes):
- F1: `allow_generated_images` se define antes de construir `base_prompt` y es la única fuente del gate. Gobierna el primer user prompt (bloque `## Restricción visual de esta request`), el retry, la validación y `request.visuals.allowGeneratedImages` (mismo booleano, sin duplicación). `_build_user_prompt_v2` recibe `allow_generated_images` keyword-only y admite el caso futuro true.
- F2: Slice 6A en `tasks.md` ya no lista el E2E (pertenece a 6B); se añadió nota y se eliminó la sección `Pendientes` que re-listaba E2E/cierre.
- F3: los términos prohibidos se limitan explícitamente a valores del enum en `_build_asset_preferences_section` y `_build_asset_preference_constraint_block`, con aclaración de que pueden aparecer en `searchQueries`/`subjects`.
- F4: `_build_retry_instruction_v2` transmite `issue["path"]` explícitamente (código, path y mensaje separados), sin duplicar `scenes[x].visualPlan` cuando el path ya está cualificado, y también para issues sin `sceneNumber`.
- F5: test integrado hermético del flujo real `reduce_content` vía `main()`.
- F6: T1 (asserts de slice), T2 (gate real false/true), T4 (paths explícitos en issues independientes) y T5 (parametrizado; valida ambos paths) reforzados.

Estado vigente:
- Primer E2E V2 canónico BLOCKED controlado por contrato en `script`.
- Auditoría inicial del E2E: `SLICE_6B_REVIEW_CHANGES_REQUIRED`.
- Primer Build (prompt/retry) implementado (baseline funcional `1110 passed, 0 failed`).
- Review del Build: `SLICE_6B_FIX_REVIEW_CHANGES_REQUIRED` por F1/F2 (MEDIUM); F3–F6 aceptados para corrección conjunta.
- Correcciones F1–F6 aplicadas.
- Tests focalizados tras las correcciones: `test_generate_script_v2.py` = 92 passed; generación combinada = 138 passed; `test_run_job.py` = 91 passed.
- Collect-only: `1117 tests collected`, cero errores de colección.
- Suite completa: **`1117 passed, 0 failed`**. Cero skips, cero xfail, cero warnings.

Reaprobación read-only focalizada:
- Las correcciones F1–F6 del contrato de prompt/retry han sido reaprobadas read-only con `SLICE_6B_REVIEW_FIXES_REAPPROVED_FOR_COMMIT`.
- Cero findings MEDIUM o superiores; un NOTE futuro no bloqueante sobre la rama `allow_generated_images=True`.
- Código y tests inmutables durante la reaprobación; suite completa reejecutada.
- Baseline vigente: **`1117 passed, 0 failed`**.
- La corrección está pendiente exclusivamente de cierre y commit.
- No se ha ejecutado un nuevo E2E.
- Ningún PASS; ningún vídeo nuevo.
- Slice 6B y el change completo continúan abiertos.

Cierre de la corrección:
- La corrección de prompt/retry de Slice 6B fue implementada, auditada, corregida,
  reaprobada y cerrada mediante `f48f98f`.
- Subject: `fix(script): harden V2 prompt and retry contract`.
- Siete archivos incluidos.
- Validator (`visual_plan_v2.py`), runner (`run_job.py`) y perfiles de duración
  (`duration_profiles.py`) intactos.
- F1–F6 resueltos; un NOTE futuro no bloqueante sobre la rama `allow_generated_images=True`.
- Baseline vigente: **`1117 passed, 0 failed`**.
- Cero push; cero MCP; cero reindexado; cero E2E durante el cierre.
- Slice 6B continúa abierto hasta obtener un E2E V2 canónico PASS.
- Change completo `retire-legacy-visual-v1` continúa abierto.

Próximos pasos:
1. ejecutar nuevo E2E V2 canónico;
2. si obtiene PASS, realizar auditoría read-only;
3. cerrar formalmente el change.

### Nuevo E2E V2 canónico (segundo intento, ejecutado 2026-08-02)

Segundo E2E V2 canónico ejecutado tras la corrección de prompt/retry, en la
sesión `docs/sessions/20260802-224326-retire-legacy-visual-v1-slice-6b-canonical-e2e-rerun.md`.

- HEAD inicial: `e5e2a4eb25746bf10645e0c1c2fe458482bedc48`; working tree limpio.
- Inicio: `2026-08-02T22:44:02+02:00`; fin: `2026-08-02T22:44:51+02:00`; duración 49s.
- Tema: `Cómo se forma un arcoíris`; duración 30s (perfil `short_25_30`).
- Comando exacto: `python3 bin/run_job.py --topic "Cómo se forma un arcoíris" --duration 30`.
- Una única invocación top-level de `bin/run_job.py`.
- Job ID: `cmo-2026-08-02-204451`; path `data/videos/cmo-2026-08-02-204451`.
- Providers: LLM `openai` (`gpt-4o-mini`); Wikimedia activo + Pixabay activo (con key); Pexels/FreeAI/Pollinations deshabilitados; TTS `edge_tts` (no alcanzado).
- Exit code: 0; el runner terminó de forma controlada, pero con estado final `REVIEW_REQUIRED`.
- `lastCompletedStage`: `script`; `outputVideoPath`: null; `validationStatus`: null.
- Vídeo: ninguno; `qualityGate`: no ejecutado.

### Resultado del contrato visual de la corrección (segundo E2E)

La corrección de prompt/retry funcionó para el contrato visual:

- `request.visuals.schemaVersion == 2`
- `request.visuals.allowGeneratedImages == false`
- `structureValid == true`; `structureIssues == []`
- 5 escenas, todas con `visualPlan._schemaVersion == 2`; `sceneNumber` secuencial 1–5
- Cero campos V1 (`editorialRole`, `strategy`, `primaryAssetType`, `secondaryAssetType`, `visualTemporalIntent`)
- Cero enums inválidos en `assetPreferences` y `visualSequence`; todos dentro de `ALLOWED_ASSET_PREFERENCES`
- Cero `animation`, `animated`, `infographic`, `photo`, `image`, `video`, `generated` como enum
- Cero `imageGenerationPrompt`; cero `negativePrompt`

Comparado con el primer E2E `cmo-2026-08-02-192443`, desaparecieron los enums
inválidos (`animation`, `infographic`). No desapareció el exceso de palabras.

### Persistencia del exceso de palabras (segundo E2E)

- `durationContract`: targetSec=30, minSec=27, maxSec=30, strictness=balanced, spokenWordsPerMinute=110
- `wordCount`=69, `sceneCount`=5, `spokenDurationSec`=37.6, `pauseDurationSec`=1.4, `estimatedDurationSec`=39.0
- `minimumWords`=47, `preferredWords`=52, `maximumWords`=52
- `status`=FAIL; retries=3; `retryHistory`: retry 0 = 60 palabras (reduce_content); retry 1 = 56 palabras (reduce_content); retry 2 = 69 palabras (reduce_content; empeoró).
- `reviewReasons`: `DURATION_OUT_OF_RANGE: estimated=39.0s (spoken=37.6s + pauses=1.4s), target=30s, min=27s, max=30s, words=69, scenes=5`
- El modelo volvió a superar `maximumWords` (52) en el tercer intento, incluso tras dos retries de reducción. A diferencia del primer E2E, esta vez la estructura y los enums son válidos; el único bloqueo es el contrato de duración.

### Estado de etapas (segundo E2E)

| Etapa | Estado |
|-------|--------|
| script | `REVIEW_REQUIRED` (detenido por contrato de duración) |
| assets | no ejecutada |
| audio | no ejecutada |
| prepare | no ejecutada |
| render | no ejecutada |
| validate | no ejecutada |

### Resultado del segundo E2E

- Resultado: **BLOCKED** (`REVIEW_REQUIRED` controlado por contrato en `script`), por `DURATION_OUT_OF_RANGE` (69 > 52 palabras).
- Verdict: `SLICE_6B_E2E_RERUN_NEEDS_FOLLOWUP`
- Cero cambios productivos (bin/tests/src intactos).
- Cero MCP, cero reindexado, cero staging, cero commit, cero push.
- No se ejecutó una segunda invocación.
- Slice 6B pendiente de auditoría read-only y de una sesión de corrección (exceso de palabras).
- Change completo `retire-legacy-visual-v1` continúa abierto.

Estado vigente:
- Primer E2E V2 canónico BLOCKED controlado por contrato en `script`.
- Auditoría inicial del E2E: `SLICE_6B_REVIEW_CHANGES_REQUIRED`.
- Primer Build (prompt/retry) implementado (baseline funcional `1110 passed, 0 failed`).
- Review del Build: `SLICE_6B_FIX_REVIEW_CHANGES_REQUIRED` por F1/F2 (MEDIUM); F3–F6 aceptados para corrección conjunta.
- Correcciones F1–F6 aplicadas, reaprobadas read-only y cerradas mediante `f48f98f`.
- Segundo E2E V2 canónico ejecutado en esta sesión: **BLOCKED** (`REVIEW_REQUIRED`) en `script` por `DURATION_OUT_OF_RANGE`; contrato visual corregido (cero enums inválidos, `structureValid=true`, `allowGeneratedImages=false`); persiste exceso de palabras (69 > 52).
- Change `retire-legacy-visual-v1` continúa abierto.

## Slice 6B — Retry temporal de duración (Build, ejecutado 2026-08-04)

Sesión: `retire-legacy-visual-v1-slice-6b-duration-retry-fix`.

### Diagnóstico

Auditoría read-only del segundo E2E: `SLICE_6B_DURATION_REVIEW_CHANGES_REQUIRED`.

- El segundo E2E V2 canónico quedó BLOCKED únicamente por duración
  (`DURATION_OUT_OF_RANGE`, 69 > 52 palabras); el contrato visual era válido.
- Causas confirmadas: D1 (regeneración completa estocástica), D2 (el retry no
  recibía el texto anterior que debe comprimir), D3 (sin reparto estricto del
  budget por escena), D4 (se pedía preservar campos que no se proporcionan),
  D6 (sin protección anti-regresión), D7 (cobertura insuficiente). D8
  (incumplimiento del modelo) se mantiene como factor contribuyente.
- Decisiones: no modificar `visual_plan_v2.py`; no modificar `run_job.py`; no
  modificar `duration_profiles.py`; no aumentar `MAX_SCRIPT_ATTEMPTS` (sigue 3);
  no relajar `minimumWords`/`preferredWords`/`maximumWords`; no implementar
  truncado ciego; no ejecutar otro E2E en esta sesión.

### Corrección implementada (Build)

- `bin/generate_script.py`: separación del retry estructural (regeneración
  completa contractual) y del retry temporal (compresión de voiceovers).
  Cuando `v2_valid == true` y `wordCount > maximumWords`, se usa un prompt
  especializado que comprime exclusivamente los voiceovers anteriores.
- `_allocate_scene_word_caps(maximum_words, scene_count)`: reparto determinista
  del máximo global por escena (suma exacta, `max - min <= 1`). Ejemplo:
  52/5 → `[11, 11, 10, 10, 10]`. Caps: 52/4 → `[13,13,13,13]`; 52/6 →
  `[9,9,9,9,8,8]`.
- `_build_voiceover_compression_prompt(...)`: contexto del intento anterior
  (`sceneNumber`, `currentVoiceover`, `maximumWords`), contador `str.split()`,
  mínimo/máximo global, caps exactos, formato de salida reducido
  (`{"scenes":[{"sceneNumber":1,"voiceover":"..."}]}`) y prohibición de campos
  adicionales.
- `_apply_voiceover_repair(base_script, payload, expected_scene_numbers=...)`:
  merge local sobre `copy.deepcopy`, que sustituye únicamente
  `scenes[i].voiceover` y rechaza escenas faltantes/extra/duplicadas, orden
  incorrecto, voiceover vacío/no string y campos adicionales.
- Best attempt: solo participan scripts `structureValid == true`; métrica de
  distancia al rango global (`_distance_to_allowed_range`), con empate por
  cercanía a `preferredWords` y conservación del anterior ante empate completo.
  La protección solo aplica al agotamiento sin PASS; el bucle termina de forma
  inmediata al encontrar PASS.
- `retryHistory` ampliado con: `attempt`, `strategy`, `wordCount`,
  `structureValid`, `durationStatus`, `sceneWordCounts`, `sceneWordCaps`,
  `distanceToAllowedRange`, `acceptedAsBest`, `repairPayloadValid`. Se añaden a
  `durationContract`: `bestAttempt`, `bestAttemptWordCount`,
  `lastAttemptDiscardedAsRegression`.
- Validator (`visual_plan_v2.py`), runner (`run_job.py`) y perfiles
  (`duration_profiles.py`) intactos. `MAX_SCRIPT_ATTEMPTS == 3`.

### Tests

- `tests/test_generate_script_v2.py`: 92 → 113 tests (T1 caps deterministas,
  T2 prompt de compresión, T3 merge solo voiceover, T4 payloads inválidos,
  T5/T6 flujos integrados 60→50 y 60→56→69, T7 no perder PASS, T8 visual plan
  inmutable ante payload hostil, T9 caps por escena, T10 estructura inválida
  mantiene retry completo, T12 agotamiento sin candidato válido; T11 cubierto
  por el test existente `MAX_SCRIPT_ATTEMPTS == 3`).
- `tests/test_generate_script.py`: el test legacy
  `test_main_retry_loop_3_attempts_3rd_succeeds` codificaba el comportamiento
  antiguo de regeneración completa en exceso de palabras; se actualizó al nuevo
  flujo de compresión (desviación de alcance documentada en el session log).

### Resultados

- `test_generate_script_v2.py`: 113 passed.
- Generación combinada: 159 passed.
- `test_run_job.py`: 91 passed.
- Collect-only: `1138 tests collected`, cero errores.
- Suite completa: **`1138 passed, 0 failed`** (baseline anterior `1117`; +21).
  Cero skips, cero xfail, cero warnings.
- Pendiente: review read-only de la corrección, commit de la corrección y un
  siguiente E2E V2 canónico.
- No se ejecutó otro E2E; ningún PASS; sin vídeo nuevo; change abierto.

## Slice 6B — Review fixes del retry temporal (ejecutado 2026-08-04)

Sesión: `retire-legacy-visual-v1-slice-6b-duration-retry-review-fixes`.

### Review read-only de la corrección temporal

La auditoría read-only de la corrección temporal terminó con
`SLICE_6B_DURATION_FIX_REVIEW_CHANGES_REQUIRED`. Findings:

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

### Correcciones aplicadas (esta sesión)

- **F1** — constant `VOICEOVER_COMPRESSION_SYSTEM_PROMPT`; selección del system
  prompt por estrategia (`compression` → prompt dedicado; inicial / estructural /
  expansión → `SYSTEM_PROMPT_V2`). La llamada usa `system_prompt=attempt_system_prompt`.
- **F2** — `{expected}` interpolado a la secuencia real de `sceneNumber`
  (p. ej. `[1, 2, 3, 4, 5]`).
- **F3** — enforcement real de caps: `_apply_voiceover_repair` recibe
  `scene_word_caps` y valida `MIN_WORDS_PER_SCENE <= wordCount <= sceneWordCap`
  con `REPAIR_SCENE_WORD_MINIMUM_NOT_MET`, `REPAIR_SCENE_WORD_CAP_EXCEEDED` y
  `REPAIR_INVALID_SCENE_CAPS`. Sin merge parcial: si falla cualquier condición,
  no se modifica `script_data` y el intento se consume dentro de
  `MAX_SCRIPT_ATTEMPTS`.
- **F3/F6** — semántica `repairShapeValid` (shape/estructura) + `repairBudgetValid`
  (budget por escena) + `repairPayloadValid = repairShapeValid and repairBudgetValid`.
- **F4** — `lastAttemptDiscardedAsRegression` corregido: solo `true` cuando el
  último intento produjo un nuevo candidato estructuralmente válido con ranking
  estrictamente peor que el best final. Ranking centralizado en
  `_candidate_rank(word_count, budget)`.
- **F5** — la representación canónica participa siempre (best candidate, siguiente
  retry, compresión, persistencia) aunque falle la duración; se persiste canónico
  si la estructura es válida.
- **F6** — telemetría de payload rechazado: `candidateUpdated`, `candidateReused`,
  `wordCountSource` (`previous_candidate` / `repaired_candidate` /
  `generated_candidate`), `candidateRank`.
- **F7** — `acceptedAsBest` final inequívoco (uno solo cuando existe best;
  `becameBestCandidate` queda como telemetría durante el bucle).

### Escenarios históricos 56/69

Con enforcement de caps, los payloads de 56 y 69 palabras son shape-valid pero no
budget-valid para caps `[11,11,10,10,10]`; no entran como nuevos best candidates
y el candidato persistido sigue siendo el inicial. La regresión real solo se
evalúa entre candidatos cap-valid.

### Resultados

- `test_generate_script_v2.py`: 130 passed (113 → 130).
- Generación combinada (`test_generate_script.py` + `test_generate_script_v2.py` +
  `test_duration_profiles.py` + `test_v2_only_generation_contract.py`): 176 passed.
- `test_run_job.py`: 91 passed.
- Collect-only: `1155 tests collected`, cero errores.
- Suite completa: **`1155 passed, 0 failed`** (baseline anterior `1138`; +17
  tests). Cero skips, cero xfail, cero warnings.
- Validator (`visual_plan_v2.py`), runner (`run_job.py`) y perfiles
  (`duration_profiles.py`) intactos. `MAX_SCRIPT_ATTEMPTS == 3`.
- Pendiente: reaprobación read-only focalizada, commit de la corrección y un
  siguiente E2E V2 canónico.
- Cero tercer E2E; ningún PASS; sin vídeo nuevo; sin commit; sin cierre. Slice 6B
  y el change completo continúan abiertos.

## Slice 6B — Follow-up canónico F8 (ejecutado 2026-08-04)

Sesión: `retire-legacy-visual-v1-slice-6b-duration-canonical-followup`.

### Primera reaprobación (read-only)

- La primera reaprobación read-only focalizada de la corrección temporal terminó
  con `SLICE_6B_DURATION_REVIEW_FIXES_REAPPROVAL_CHANGES_REQUIRED`.
- **F1–F4 y F6–F7 resueltos.**
- **F8 MEDIUM bloqueante:** `_build_voiceover_compression_prompt` y
  `_apply_voiceover_repair` recibían la representación raw en lugar de la
  canónica, pese a que `canonical` ya estaba disponible cuando `v2_valid == true`.
- **F9–F11 LOW no bloqueantes:**
  - F9: aceptado como LOW pendiente; posible normalización futura de
    `repairShapeValid`/`repairBudgetValid`/`repairPayloadValid` a null/N/A para
    estrategias `initial`, `structural` y `duration`. No afecta al retry, al
    PASS ni al best candidate. Sin ampliación del schema.
  - F10: gaps de cobertura (atendidos con la cobertura canónica de esta sesión).
  - F11: tracking documental de los logs corregido (`??` UNTRACKED).

### Corrección F8 — candidato canónico activo

- Cuando `v2_valid is True` y `canonical is not None`, se define
  `candidate_script = canonical`. La representación raw deja de participar en el
  flujo de un candidato estructuralmente válido.
- `candidate_script` alimenta: `_count_voiceover_words`, `_scene_word_counts`,
  `scene_count`, el best candidate, `_build_voiceover_compression_prompt`,
  `_apply_voiceover_repair` (base del merge), la construcción del siguiente retry
  y la persistencia al agotar sin PASS.
- Tras un repair válido, el resultado parte de una copia profunda del candidato
  canónico, modifica únicamente `voiceover`, continúa siendo la representación
  activa y vuelve a pasar por validación/canonicalización; no recupera campos raw.
- Rama estructural inválida intacta: no se inventa candidato canónico, se
  conserva el retry estructural y la respuesta raw se usa solo como evidencia.

### Tests y resultados

- `tests/test_generate_script_v2.py`: 130 → 133 (compression prompt recibe
  candidato canónico; base del merge canonicalizada; seis escenas en el prompt).
- `test_generate_script_v2.py`: 133 passed.
- Generación combinada (con `test_generate_script.py`, `test_duration_profiles.py`,
  `test_v2_only_generation_contract.py`): 179 passed.
- `test_run_job.py`: 91 passed.
- Collect-only: `1158 tests collected`, cero errores.
- Suite completa: **`1158 passed, 0 failed`** (baseline anterior `1155`; +3
  tests). Cero skips, cero xfail, cero warnings.
- Validator (`visual_plan_v2.py`), runner (`run_job.py`) y perfiles
  (`duration_profiles.py`) intactos. `MAX_SCRIPT_ATTEMPTS == 3`.

### Reaprobación final y cierre (2026-08-04)

- Verdict final de reaprobación: `SLICE_6B_DURATION_CANONICAL_FOLLOWUP_REAPPROVED_FOR_COMMIT`.
- Cero findings bloqueantes; F9 aceptado como LOW no bloqueante.
- F1–F8 resueltos.
- Baseline vigente: **`1158 passed, 0 failed`**.
- La corrección temporal está reaprobada, cerrada y versionada mediante el Commit A
  `9eb1f13` (`fix(script): harden canonical duration retries`).
- Pendiente del tercer E2E V2 canónico.
- Cero PASS todavía; sin vídeo nuevo.
- Cero push; cero reindexado; cero MCP.
- Slice 6B abierto.
- Change completo `retire-legacy-visual-v1` abierto.

### Tercer E2E V2 canónico (ejecutado 2026-08-04)

Sesión: `docs/sessions/20260804-215808-retire-legacy-visual-v1-slice-6b-third-canonical-e2e.md`.

- HEAD inicial: `ad86834b414ab5973ffee0d4701fa86ce7b30b47`; working tree limpio.
- Inicio: `2026-08-04T21:56:29+02:00`; fin: `2026-08-04T21:56:54+02:00`; duración 25s.
- Tema: `Cómo se forma un arcoíris`; duración 30s (perfil `short_25_30`).
- Comando exacto: `python3 bin/run_job.py --topic "Cómo se forma un arcoíris" --duration 30`.
- Una única invocación top-level de `bin/run_job.py`.
- Job ID: `cmo-2026-08-04-195654`; path `data/videos/cmo-2026-08-04-195654`.
- Providers: LLM `openai` (`gpt-4o-mini`); Wikimedia activo + Pixabay activo (con key); Pexels/FreeAI/Pollinations deshabilitados; TTS `edge_tts` (no alcanzado).
- Exit code: 0; el runner terminó de forma controlada, pero con estado final `REVIEW_REQUIRED`.
- `lastCompletedStage`: `script`; `outputVideoPath`: null; `validationStatus`: null.

### Resultado del contrato visual (tercer E2E)

- `request.visuals.schemaVersion == 2`
- `request.visuals.allowGeneratedImages == false`
- `durationContract.structureValid == true`; `structureIssues == []`
- 5 escenas, todas con `visualPlan._schemaVersion == 2`; `sceneNumber` secuencial 1–5
- Cero campos V1 residuales (`editorialRole`, `strategy`, `primaryAssetType`, `secondaryAssetType`, `visualTemporalIntent`)
- Cero enums inválidos; usados: `diagram`, `illustration`, `photograph`, `stock`
- `imageGenerationPrompt` y `negativePrompt` presentes (V2 permitido)

### Contrato temporal (tercer E2E)

- `targetSec=30`, `minSec=27`, `maxSec=30`, `strictness=balanced`, `spokenWordsPerMinute=110`
- `wordCount`=56, `sceneCount`=5, `sceneWordCounts`=[14,13,9,7,13]
- `spokenDurationSec`=30.5, `pauseDurationSec`=1.4, `estimatedDurationSec`=31.9
- `minimumWords`=47, `preferredWords`=52, `maximumWords`=52
- `status`=FAIL; `retries`=3; `bestAttempt`=0; `bestAttemptWordCount`=56; `lastAttemptDiscardedAsRegression=false`
- `reviewReasons`: `DURATION_OUT_OF_RANGE: estimated=31.9s (spoken=30.5s + pauses=1.4s), target=30s, min=27s, max=30s, words=56, scenes=5`

### Retry history (tercer E2E)

| attempt | strategy | wordCount | structureValid | durationStatus | repairShape | repairBudget | repairPayload | acceptedAsBest |
|---------|----------|-----------|----------------|----------------|-------------|--------------|---------------|----------------|
| 0 | initial | 56 | true | FAIL | true | true | true | true |
| 1 | compression | 56 (reused) | true | FAIL | true | false | false | false |
| 2 | compression | 56 (reused) | true | FAIL | true | false | false | false |

- Attempt 1: `REPAIR_SCENE_WORD_CAP_EXCEEDED` escenas 1 (13>11) y 2 (12>11); payload rechazado, candidato anterior conservado.
- Attempt 2: `REPAIR_SCENE_WORD_MINIMUM_NOT_MET` escena 4 (6<7); payload rechazado, candidato anterior conservado.
- La compresión no logró ningún payload budget-valid; el candidato inicial de 56 palabras se conservó como best attempt.
- Cero payloads válidos descartados como regresión; `lastAttemptDiscardedAsRegression=false`.

### Estado de etapas (tercer E2E)

| Etapa | Estado |
|-------|--------|
| script | `REVIEW_REQUIRED` (detenido por contrato de duración) |
| assets | no ejecutada |
| audio | no ejecutada |
| prepare | no ejecutada |
| render | no ejecutada |
| validate | no ejecutada |

### Resultado del tercer E2E

- Resultado: **BLOCKED** (`REVIEW_REQUIRED` controlado por contrato en `script`), por `DURATION_OUT_OF_RANGE` (56 > 52 palabras).
- Verdict: `SLICE_6B_THIRD_E2E_SCRIPT_BLOCKED_NEEDS_FOLLOWUP`
- El contrato visual y la estructura ya son válidos; el único bloqueo es la duración.
- Cero cambios productivos (bin/tests/src intactos).
- Cero MCP, cero reindexado, cero staging, cero commit, cero push.
- Slice 6B y el change `retire-legacy-visual-v1` continúan abiertos.
- Pendiente exclusivamente de una corrección del exceso de palabras y de un cuarto E2E V2 canónico; sin auditoría ni cierre formal en esta sesión.

## Resumen

- Slice 3B1: 157 tests focalizados pasados, 0 fallidos
- Slice 3B2: 132 tests focalizados pasados, 0 fallidos
- Slice 3B3: 132 tests focalizados pasados, 0 fallidos
- Slice 4A: implementado, revisado y cerrado mediante el commit de esta iteración
- Slice 4B1: implementado, revisado y cerrado mediante el commit de esta iteración
- Slice 4B2: implementado, revisado y cerrado mediante el commit de esta iteración
- Slice 4: completado
- Slice 5A: implementado, revisado, corregido, reaprobado y cerrado mediante el commit `f2a8078`
- Slice 5B: implementado, auditado, corregido, reaprobado y cerrado mediante el commit `1d9fe37`
- Slice 6A: implementado, auditado, corregido, reaprobado y cerrado mediante el commit `86170d3`; baseline funcional `1102 passed, 0 failed`
- Slice 6B: ejecutado con E2E V2 canónico BLOCKED (controlado por contrato en `script`); auditado read-only con `SLICE_6B_REVIEW_CHANGES_REQUIRED`; corrección de prompt/retry implementada (baseline funcional `1110 passed, 0 failed`); auditado read-only con `SLICE_6B_FIX_REVIEW_CHANGES_REQUIRED` y correcciones F1–F6 aplicadas (baseline funcional `1117 passed, 0 failed`); reaprobada read-only con `SLICE_6B_REVIEW_FIXES_REAPPROVED_FOR_COMMIT`; corrección cerrada mediante el commit `f48f98f`; nuevo E2E V2 canónico ejecutado en esta sesión BLOCKED (`REVIEW_REQUIRED`) en `script` por `DURATION_OUT_OF_RANGE` (contrato visual corregido; persiste exceso de palabras 69 > 52); auditado read-only con `SLICE_6B_DURATION_REVIEW_CHANGES_REQUIRED`; corrección del retry temporal de duración implementada (baseline funcional `1138 passed, 0 failed`); auditado read-only de la corrección con `SLICE_6B_DURATION_FIX_REVIEW_CHANGES_REQUIRED` y correcciones F1–F7 aplicadas (baseline funcional `1155 passed, 0 failed`); primera reaprobación read-only con `SLICE_6B_DURATION_REVIEW_FIXES_REAPPROVAL_CHANGES_REQUIRED`; F8 MEDIUM corregido en el follow-up canónico (candidato canónico en compression prompt y merge; baseline funcional `1158 passed, 0 failed`); corrección temporal reaprobada (`SLICE_6B_DURATION_CANONICAL_FOLLOWUP_REAPPROVED_FOR_COMMIT`), cerrada y versionada mediante `9eb1f13`; F1–F8 resueltos; F9 LOW aceptado; tercer E2E V2 canónico ejecutado (job `cmo-2026-08-04-195654`) BLOCKED (`REVIEW_REQUIRED`) en `script` por `DURATION_OUT_OF_RANGE` (56 > 52 palabras); contrato visual y estructura ya válidos (`structureValid=true`, cero enums inválidos, `allowGeneratedImages=false`); compresión temporal no logró payload budget-valid, se conservó el candidato inicial de 56 palabras como best attempt; auditoría de política temporal del tercer E2E con `SLICE_6B_DURATION_POLICY_AUDIT_RECOMMENDS_CHANGES`; corrección de política temporal implementada (targets por escena como guidance + presupuesto global como único contracto duro + convergencia monotónica; baseline funcional `1165 passed, 0 failed`); review read-only de la corrección de política con `SLICE_6B_DURATION_POLICY_FIX_REVIEW_CHANGES_REQUIRED` (arquitectura aprobada; único blocker MEDIUM `{min_w}/{max_w}` literal corregido a f-string; test de regresión ampliado); pendiente reaprobación read-only, commit y cuarto E2E V2 canónico; corrección de política temporal reaprobada (`SLICE_6B_DURATION_POLICY_FINAL_REAPPROVED_FOR_COMMIT`), cerrada y versionada mediante `d377932`; cuarto E2E V2 canónico ejecutado (job `cmo-2026-08-11-185926`) BLOCKED (`REVIEW_REQUIRED`) en `script` por `DURATION_OUT_OF_RANGE` (62 > 52 palabras); política temporal validada en comportamiento (convergencia monotónica 69→63→62, targets orientativos, sin hard caps, anti-regresión) pero no resolvió el bloqueo (modelo terminó en 62); `SLICE_6B_FOURTH_E2E_SCRIPT_BLOCKED_NEEDS_FOLLOWUP`; auditoría read-only del cuarto E2E con `SLICE_6B_COMPRESSION_CONTROL_AUDIT_RECOMMENDS_CHANGES`; hardening de control de longitud implementado (target operativo interior `_compute_operational_word_target` = 50 para 30s, presupuesto global en generación inicial, compression system prompt con primacía del presupuesto global, compression prompt imperativo con reducción mínima/deseada y escalado del segundo intento, temperatura de compression 0.2 / resto 0.8; contratos 47/52/52 y `MAX_SCRIPT_ATTEMPTS==3` intactos; baseline funcional `1181 passed, 0 failed`); review read-only del hardening con `SLICE_6B_LENGTH_CONTROL_HARDENING_REVIEW_CHANGES_REQUIRED` (F1 MEDIUM doble target `≈52` vs `50`; F2 LOW aceptado; compression/temperatura/ranking/repair aprobados); F1 corregido (`preferredWords=52` dato del perfil, `maximumWords=52` hard boundary, `operationalWordTarget=50` único target accionable) y C2 reforzado; length-control hardening re-aprobado read-only (`SLICE_6B_LENGTH_CONTROL_TARGET_FIX_REAPPROVED_FOR_COMMIT`, cero HIGH/MEDIUM, F1 resuelto, F2 LOW aceptado), cerrado y versionado mediante Commit A `bafb2d5` (`fix(script): harden V2 word-budget control`); baseline funcional vigente `1181 passed, 0 failed`; quinto E2E V2 canónico ejecutado (job `cmo-2026-08-14-153529`): **script PASS** por primera vez en la serie y **length-control hardening validado mediante E2E real** (`55 → 52` palabras, `durationContract.status=PASS`, `structureValid=true`); assets completos (`ASSETS_READY`, 10/10); **pipeline bloqueado posteriormente en `audio`** por `AUDIO_DURATION_MISSING` (medida de duración de los 5 mp3 no devuelta durante el run; `duration_estimated=true`; fallback Docker devuelve duración válida manualmente, sugiriendo fallo transitorio); verdict `SLICE_6B_FIFTH_E2E_LENGTH_CONTROL_VALIDATED_PIPELINE_BLOCKED`; pendiente diagnóstico del bloqueo de audio y auditoría read-only final

## Plan de transformación modular

El proyecto se transformará progresivamente hacia una arquitectura modular con V2 como único contrato visual soportado. No se reescribe desde cero.

Roadmap completo: `docs/architecture/modular-v2-transformation-roadmap.md`

### Orden de fases

1. Retirar V1 y enfoque histórico → `retire-legacy-visual-v1` (planificación)
2. Estabilizar pipeline V2, baseline clara
3. Crear `pyproject.toml` y `src/shorts_creator/`
4. Extraer `contracts/` e `infrastructure/`
5. Migrar `script/`
6. Reanudar audio pacing (Phase B)
7. Migrar `audio/`
8. Migrar `assets/`
9. Migrar `rendering/`
10. Migrar `validation/`
11. Reducir `bin/` a adaptadores, limpieza final

## Benchmark y routing de modelos

- Benchmark R1 cerrado en commit `4d1715f`
- Routing gratuito documentado en `docs/research/opencode-free-models-benchmark-r1.md`
- Modelos gratuitos aptos para planificación y código confirmados

## Próximos pasos

1. Ejecutado Slice 6B: E2E V2 canónico BLOCKED en `script` (enums V2 inválidos + duración fuera de rango); auditado read-only con `SLICE_6B_REVIEW_CHANGES_REQUIRED`.
2. Implementada la corrección de prompt/retry (baseline `1110 passed, 0 failed`); auditado read-only de la corrección con `SLICE_6B_FIX_REVIEW_CHANGES_REQUIRED`; correcciones F1–F6 aplicadas (baseline `1117 passed, 0 failed`); reaprobada read-only con `SLICE_6B_REVIEW_FIXES_REAPPROVED_FOR_COMMIT`; corrección cerrada mediante `f48f98f`.
3. Ejecutado nuevo E2E V2 canónico (job `cmo-2026-08-02-204451`): BLOCKED (`REVIEW_REQUIRED`) en `script` por `DURATION_OUT_OF_RANGE` (69 > 52 palabras). Contrato visual corregido (cero enums inválidos, `structureValid=true`, `allowGeneratedImages=false`); persiste exceso de palabras.
4. Auditado read-only del segundo E2E con `SLICE_6B_DURATION_REVIEW_CHANGES_REQUIRED` (diagnóstico D1/D2/D3/D4/D6/D7 confirmado; D8 como factor contribuyente).
5. Implementada la corrección del retry temporal (compresión de voiceovers + caps deterministas + best attempt). Suite completa vigente `1138 passed, 0 failed`. Validator, runner y perfiles intactos.
6. Auditado read-only de la corrección temporal con `SLICE_6B_DURATION_FIX_REVIEW_CHANGES_REQUIRED` (F1 HIGH, F2/F3/F4 MEDIUM, F5–F7 LOW). Aplicadas las correcciones F1–F7 (system prompt dedicado, interpolación de `{expected}`, enforcement de caps, flag de regresión corregido, candidato canónico, telemetría aclarada, `acceptedAsBest` inequívoco). Suite completa vigente `1155 passed, 0 failed`.
7. Primera reaprobación read-only con `SLICE_6B_DURATION_REVIEW_FIXES_REAPPROVAL_CHANGES_REQUIRED`: F1–F4 y F6–F7 resueltos; **F8 MEDIUM** (compression prompt y merge usaban la representación raw) corregido en el follow-up canónico mediante candidato canónico activo (`candidate_script = canonical`). Suite completa vigente `1158 passed, 0 failed`. F9 aceptado como LOW pendiente; F11 tracking documental corregido.
8. Reaprobación final read-only de la corrección temporal con `SLICE_6B_DURATION_CANONICAL_FOLLOWUP_REAPPROVED_FOR_COMMIT`; commit de la corrección temporal `9eb1f13` (`fix(script): harden canonical duration retries`). Ambos cerrados y versionados.
9. Ejecutado el tercer E2E V2 canónico (job `cmo-2026-08-04-195654`): BLOCKED (`REVIEW_REQUIRED`) en `script` por `DURATION_OUT_OF_RANGE` (56 > 52 palabras). Contrato visual y estructura ya válidos (`structureValid=true`, cero enums inválidos, `allowGeneratedImages=false`); la compresión temporal no logró un payload budget-valid, conservando el candidato inicial de 56 palabras como best attempt. Slice 6B y el change permanecen abiertos.
10. Auditado read-only la política temporal del tercer E2E con `SLICE_6B_DURATION_POLICY_AUDIT_RECOMMENDS_CHANGES`: falso negativo global confirmado (caps estáticos por escena + mínimo duro de siete palabras exigían una reducción de 8 cuando solo hacían falta 4, y rechazaban retries válidos globalmente).
11. Implementada la corrección de política temporal: targets dinámicos por escena como guidance, presupuesto global como único contracto duro, convergencia monotónica de candidatos y protección anti-regresión. Suite completa vigente `1165 passed, 0 failed`. Validator, runner y perfiles intactos. Pendiente review read-only, commit y cuarto E2E V2 canónico.
12. Review read-only de la corrección de política con `SLICE_6B_DURATION_POLICY_FIX_REVIEW_CHANGES_REQUIRED`: arquitectura aprobada; único blocker MEDIUM `{min_w}/{max_w}` literal en el compression prompt corregido a f-string; test de regresión ampliado. Baseline vigente `1165 passed, 0 failed`. Pendiente reaprobación read-only, commit y cuarto E2E V2 canónico.
12b. Reaprobación read-only final de la corrección de política con `SLICE_6B_DURATION_POLICY_FINAL_REAPPROVED_FOR_COMMIT` (cero findings HIGH/MEDIUM; LOWs aceptados); corrección de política temporal cerrada y versionada mediante `d377932` (`fix(script): refine V2 duration compression policy`). Baseline vigente `1165 passed, 0 failed`. Pendiente únicamente el cuarto E2E V2 canónico.
12c. Ejecutado el cuarto E2E V2 canónico (job `cmo-2026-08-11-185926`): BLOCKED (`REVIEW_REQUIRED`) en `script` por `DURATION_OUT_OF_RANGE` (62 > 52 palabras). Contrato visual y estructura válidos; política temporal validada en comportamiento (convergencia 69→63→62, targets orientativos, sin hard caps, anti-regresión) pero el modelo no comprimió hasta 47–52. Verdict `SLICE_6B_FOURTH_E2E_SCRIPT_BLOCKED_NEEDS_FOLLOWUP`. Pendiente nueva corrección del exceso de palabras y un quinto E2E V2 canónico.
12d. Auditado read-only el cuarto E2E con `SLICE_6B_COMPRESSION_CONTROL_AUDIT_RECOMMENDS_CHANGES`: la política de candidatos funcionó; el problema es control de generación/compliance del LLM. Implementado el hardening de control de longitud (Build 2026-08-11): target operativo interior `_compute_operational_word_target` (para 30s = 50), presupuesto global inequívoco en generación inicial, compression system prompt con primacía del presupuesto global, compression prompt imperativo con reducción mínima/deseada y escalado del segundo intento, temperatura de compression 0.2 / resto 0.8. Contratos 47/52/52 y `MAX_SCRIPT_ATTEMPTS==3` intactos. Baseline funcional `1181 passed, 0 failed`. Pendiente review read-only, commit y quinto E2E V2 canónico.
12e. Reaprobación read-only final del length-control hardening con `SLICE_6B_LENGTH_CONTROL_TARGET_FIX_REAPPROVED_FOR_COMMIT` (cero HIGH/MEDIUM; F1 resuelto; F2 LOW aceptado). Length-control hardening cerrado y versionado mediante Commit A `bafb2d5` (`fix(script): harden V2 word-budget control`). Contratos vigentes: `preferredWords=52` dato del perfil, `maximumWords=52` hard boundary, `operationalWordTarget=50` único target accionable. Baseline funcional vigente `1181 passed, 0 failed`. Pendiente únicamente el quinto E2E V2 canónico; cero PASS completo todavía. Slice 6B abierto; change abierto; cero push; cero MCP; cero reindexado.
12f. Ejecutado el quinto E2E V2 canónico (job `cmo-2026-08-14-153529`): **script PASS** por primera vez en la serie. Length-control hardening validado en E2E real (`55 → 52` palabras; `durationContract.status=PASS`; `structureValid=true`; contrato visual V2 válido). Assets completos (`ASSETS_READY`, 10/10, cero fallidos). Pipeline bloqueado posteriormente en `audio` por `AUDIO_DURATION_MISSING` (duración de los 5 mp3 no medida durante el run; `duration_estimated=true`; el fallback Docker devolvió duración válida al verificar manualmente, sugiriendo fallo transitorio). Etapas posteriores no alcanzadas; `outputVideoPath=null`; `qualityGate` no ejecutado. Verdict `SLICE_6B_FIFTH_E2E_LENGTH_CONTROL_VALIDATED_PIPELINE_BLOCKED`. Length-control hardening validado mediante E2E real. Pendiente: diagnóstico del bloqueo de audio y auditoría read-only final. Slice 6B y change abiertos; cero push; cero MCP; cero reindexado.
13. Tras un E2E V2 canónico PASS, realizar auditoría y cierre formal del change.
14. Phase B de audio pacing tras migrar script/
15. Crear `pyproject.toml` y estructura `src/`
16. Investigar instalación de ffprobe en el host
17. Registrar FreeAI para imágenes de calidad gratuitas
18. Integrar pipeline v2 con n8n

## Audio pacing v2 — Phase A (completada 2026-07-14)

### Causa raíz del silencio

- Docker client (v1.52) incompatible con Docker daemon (API v1.43).
- `_get_mp3_duration()` fallaba silenciosamente → `durationSec = None` en todas las escenas.
- `prepare_job` usaba `targetDurationSec = 6` como fallback.
- `render_job` aplicaba `apad` + `atrim` para rellenar cada escena hasta 6s.
- Resultado: 50.9% silencio con 48 palabras en 30s.

### Correcciones implementadas

| Archivo | Cambio |
|---------|--------|
| `bin/generate_audio.py` | `_get_mp3_duration()` añade `DOCKER_API_VERSION=1.43`; retorna `(dur, source)`; `duration_estimated` y `durationSource` en metadata; `activeAudioDurationSec` desde último cue + guard |
| `bin/prepare_job.py` | Bloquea cuando `duration_estimated=true` o sin `durationSource`; nueva fórmula `sceneWindowSec = activeAudioDur + tailPause` |
| `bin/render_job.py` | `_docker_ffmpeg()` añade `DOCKER_API_VERSION=1.43`; `build_per_scene_audio_filter` acepta `active_audio_sec` para trim de room tone; pacing validation en quality gate |
| **NUEVO** `bin/pacing_validation.py` | Métricas: silenceRatio, maxInterSceneSilenceSec (con scene boundaries), narrationCoverageRatio, timelineWPM, effectiveSpeechWPM |
| `bin/validate_job.py` | Nuevo check `_check_pacing`; Docker env en `_run_docker_ffprobe` |

### Nuevo contrato temporal

```
activeAudioDurationSec = min(physicalDuration, lastCueEndSec + 0.10s)
sceneWindowSec = activeAudioDurationSec + sceneTailPauseSec (0.25s)
```

`targetDurationSec` es solo informativo. La ventana se deriva del audio activo medido.

### Resultados E2E (job `cmo-2026-07-14-180923`)

| Métrica | Antes (Phase A) | Después (Phase A.1) |
|---------|-------|---------|
| Duración | 22.640s | 18.30s |
| Silencio | 8.74s (38.7%) | ~4.4s (24.2%) |
| Narración coverage | 61.3% | 75.8% |
| maxInterSceneSilence | 1.618s | 0.775s |
| timelineWPM | — | 157.8 |
| effectiveSpeechWPM | — | 208.1 |
| qualityGate | FAIL | PASS |

La reducción de duración a ~18s se debe al word budget de Phase A (48 palabras).
Phase B expandirá a 27–30s con WPM calibrado.

### Baseline de tests

```text
1215 passed, 16 failed (preexistentes en test_run_job.py + test_semantic_asset_validation.py), 0 regresiones
```

> **Nota histórica:** `1215 passed, 16 failed` fue la baseline de Phase A.
> Durante 6A2 se obtuvo temporalmente `20 failed, 1082 passed` por contaminación
> de `sys.modules`. Tras corregir C4 en 6A3, la baseline vigente para el HEAD
> actual es `1102 passed, 0 failed`.
