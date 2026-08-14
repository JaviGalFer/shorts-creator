# Session — Quinto E2E V2 canónico (Slice 6B, length-control)

**Sesión:** `retire-legacy-visual-v1-slice-6b-fifth-canonical-e2e`
**Fecha:** 2026-08-14T17:35:02+02:00 (inicio)
**Modo:** Build
**Modelo:** `opencode/deepseek-v4-flash-free` / `default`
**Subagentes:** ninguno
**MCP:** desactivado; cero llamadas
**Reindexado:** no

---

## 1. Configuración efectiva

- Sesión: `retire-legacy-visual-v1-slice-6b-fifth-canonical-e2e`
- Modelo: `opencode/deepseek-v4-flash-free` (variante `default`)
- Modo: Build
- Máximo pasos agentic: 30
- Subagentes: ninguno
- Se ejecutó exactamente **una** invocación de `bin/run_job.py`.

## 2. HEAD inicial

```
4683313589dd2be3e97277c8ff06429b5a3ffd9b
```

## 3. Estado Git inicial

- Rama: `main`
- Working tree: limpio (`git diff --check` limpio; única advertencia conocida de permisos `data/postgres/`).
- Staging: vacío.
- Untracked: cero.

## 4. Historial (8 más recientes)

```
4683313 docs(project): record Slice 6B length-control closure
bafb2d5 fix(script): harden V2 word-budget control
d62c76a docs(project): record Slice 6B duration policy closure
d377932 fix(script): refine V2 duration compression policy
ad86834 docs(project): record Slice 6B duration fix closure
9eb1f13 fix(script): harden canonical duration retries
e5e2a4e docs(project): record Slice 6B script fix commit
f48f98f fix(script): harden V2 prompt and retry contract
```

## 5. Commits heredados

### Commit funcional `bafb2d5` — exactamente

```
bin/generate_script.py
tests/test_generate_script_v2.py
```

### Commit documental `4683313` — exactamente seis archivos

```
M  docs/project/current-state.md
M  openspec/changes/retire-legacy-visual-v1/tasks.md
A  docs/sessions/20260811-205950-...fourth-canonical-e2e.md
A  docs/sessions/20260811-213354-...length-control-hardening.md
A  docs/sessions/20260811-220445-...length-control-target-fix.md
A  docs/sessions/20260814-172125-...length-control-closure.md
```

No se repite ninguna operación de closure.

## 6. Baseline heredada

```
1181 passed, 0 failed
```

## 7. Hashes iniciales (snapshot de integridad)

```
bin/generate_script.py          dd26abce66af4422d326003235f50e1ada2ba5849ee6d02f41aa9a238c27efbc
bin/run_job.py                  6240606ba8ea1b5a07c56e0d0dcf25fc30a4b4eed58a82a2dffbaeecb7f67d0f
bin/visual_plan_v2.py           37c5c463d2a9069627705fa26c4b7b94b3fd3121fcc02d6ca5d6dad77cad66ff
bin/duration_profiles.py        41e12bcafd30c79d122fa93d23fda7a02f64ac25ee88e544d45df18311a5f45d
tests/test_generate_script_v2.py 3dd1b091cccc9534074fe5d1089239cb4bbc7b78ea5931bcc809fde93b6807d0
```

## 8. Preflight focalizado

- C2 (`test_c2_initial_prompt_contract`): `1 passed`.
- Length-control hardening (16 node IDs C1–C11): `16 passed`.
- Dry-run V2 (`test_visual_v2_dry_run_e2e.py`): `22 passed`.

Todos verificados antes de la ejecución real.

## 9. Runtime budget (contrato 30 s)

```
MAX_SCRIPT_ATTEMPTS            = 3
strictness                     = balanced
targetSec/minSec/maxSec        = 30 / 27 / 30
spokenWordsPerMinute           = 110
estimatedScenePauseMs          = 350
minimumWords                   = 47
preferredWords                 = 52
maximumWords                   = 52
operationalWordTarget          = 50
```

Semántica vigente:
- `preferredWords=52` — referencia del perfil.
- `maximumWords=52` — hard acceptance boundary.
- `operationalWordTarget=50` — único target accionable de generación.

## 10. Prompt inicial renderizado (30 s)

Verificado en el código y renderizado efectivo:

```
- El total de palabras habladas debe estar entre 47 y 52 (preferredWords del perfil: 52; pausas entre escenas de ~350ms cada una)
- Rango válido final: 47-52 palabras habladas en total.
- LÍMITE ABSOLUTO: no superes 52 palabras de voiceover en total.
- Objetivo operativo: apunta a 50 palabras de voiceover en total.
```

Ausentes (comprobados):
- `aproximadamente 52 palabras objetivo`
- `con aproximadamente`
- `apunta a 52`

## 11. Temperaturas

```
initial/structural/duration = 0.8
compression                 = 0.2
```

## 12. Attempt wiring

```
initial          (attempt 0)
compression 1    (attempt 1)
compression 2    (attempt 2)
total llamadas LLM <= 3
```

## 13. Providers

- LLM: `openai` (`gpt-4o-mini`), cliente OpenAI-compatible.
- Wikimedia Commons: enabled + implemented, sin API key.
- Pixabay: enabled + implemented, key presente (`yes`).
- Pexels: enabled=`false`, implemented=`false`, `requiresApiKey=true`.
- FreeAI: enabled=`false`, implemented=`false`.
- Pollinations: enabled=`false`, implemented=`false`.
- TTS: `edge_tts` (`es-ES-AlvaroNeural`).

## 14. Docker

```
client=29.1.3 server=29.1.3
imagen linuxserver/ffmpeg:latest presente (id 9872c5f1f36d...)
df -h . = 943G avail (2% used)
data/videos writable
```

No se descargó ninguna imagen Docker nueva.

## 15. Snapshot jobs

Snapshot previo registrado en `/tmp/shorts-creator-fifth-e2e-before.txt` (88 dirs job totales).
Los cuatro jobs canónicos anteriores confirmados presentes:

```
cmo-2026-08-02-192443
cmo-2026-08-02-204451
cmo-2026-08-04-195654
cmo-2026-08-11-185926
```

Ninguno modificado.

---

## 16. Comando exacto (única invocación)

```bash
python3 bin/run_job.py \
  --topic "Cómo se forma un arcoíris" \
  --duration 30
```

- timestamp inicio: `2026-08-14T17:35:09+02:00`
- epoch inicio: `1786721709`
- timestamp fin: `2026-08-14T17:36:12+02:00`
- epoch fin: `1786721772`
- wall-clock: 63 s
- exit code top-level: `0`

### stdout

```
[script] Job cmo-2026-08-14-153529 ready at .../cmo-2026-08-14-153529/metadata.json
[assets] Completed: ASSETS_READY
[audio] Blocked: REVIEW_REQUIRED
{"jobId": "cmo-2026-08-14-153529", ..., "status": "REVIEW_REQUIRED", "lastCompletedStage": "audio", "outputVideoPath": null, "validationStatus": null}
```

### stderr

Vacío.

## 17. Unica invocación

Confirmada. Una única top-level invocation de `bin/run_job.py`. No se repitió, no se reintentó, no se varió tema/duración, no se ejecutaron stages manualmente.

---

## 18. Job ID / paths

- Job ID: `cmo-2026-08-14-153529`
- Path: `data/videos/cmo-2026-08-14-153529`
- Metadata: `data/videos/cmo-2026-08-14-153529/metadata.json`
- Tamaño: `50M`

Job nuevo detectado por diff de snapshots (exactamente uno nuevo).

## 19. Archivos producidos

```
assets/scene_001_seg_001.jpg   (144772 b)
assets/scene_001_seg_002.jpg   (16188200 b)
assets/scene_002_seg_001.jpg   (658277 b)
assets/scene_002_seg_002.jpg   (23049673 b)
assets/scene_003_seg_001.jpg   (119006 b)
assets/scene_003_seg_002.jpg   (6729070 b)
assets/scene_004_seg_001.jpg   (317347 b)
assets/scene_004_seg_002.jpg   (4169756 b)
assets/scene_005_seg_001.jpg   (198360 b)
assets/scene_005_seg_002.jpg   (157922 b)
metadata.json                  (30204 b)
scenes/scene-01.mp3 ... scene-05.mp3 (10 segmentos jpg + 5 mp3)
```

Además se creó `data/cache/pixabay-v2/` como caché automática del provider durante la ejecución real (artefacto runtime, fuera de los archivos manuales).

---

## 20. Contrato visual

La etapa `script` superó el contrato visual y estructural completo (primera vez en los cinco E2E):

- `request.visuals.schemaVersion == 2`
- `request.visuals.allowGeneratedImages == false`
- `sceneCount == 5`
- `sceneNumber` secuencial 1–5
- `visualPlan._schemaVersion == 2` en las 5 escenas
- `structureValid == true`
- `structureIssues == []`
- Cero campos V1 residuales (`editorialRole`, `strategy`, `primaryAssetType`, `secondaryAssetType`, `visualTemporalIntent`)
- Enums usados válidos: `photograph`, `diagram`, `stock` (todos dentro de `ALLOWED_ASSET_PREFERENCES`); cero enums inválidos
- `imageGenerationPrompt`/`negativePrompt` en `null` (coherente con `allowGeneratedImages=false`)

## 21. Contrato temporal

```
targetSec=30 minSec=27 maxSec=30 strictness=balanced spokenWordsPerMinute=110
wordCount = 52 (final)
sceneCount = 5
spokenDurationSec = 28.4
pauseDurationSec = 1.4
estimatedDurationSec = 29.8
minimumWords=47 preferredWords=52 maximumWords=52
status = PASS
retries = 1
bestAttempt = 1
bestAttemptWordCount = 52
lastAttemptDiscardedAsRegression = false
```

## 22. Initial word count

- attempt 0 (initial): **55** palabras → `above_maximum_words` (exceso +3 sobre 52).

## 23. Initial vs operational target

- operationalWordTarget = 50
- initialWordCount = 55 (I0-B: overshoot sobre 52, aunque muy contenido: solo +3, frente a los +22/+8/+4/+17 de E2Es 1-4)
- El primer intento no logró 47–52 de entrada, pero quedó cerca y la compresión lo llevó a rango.

## 24. Retry history

| retry | attempt | strategy   | reason              | wordCount | durationStatus | structureValid | instructionType |
|-------|---------|------------|---------------------|-----------|----------------|----------------|-----------------|
| 0     | 0       | initial    | above_maximum_words | 55        | FAIL           | true           | reduce_content  |
| 1     | 1       | compression| in_range            | 52        | PASS           | true           | none_needed     |

- attempt 0: `sceneWordCounts=[10,13,12,10,10]`, `distanceToAllowedRange=3`, rank `[3,3]`, `candidateUpdated=true`, `becameBestCandidate=true`, `acceptedAsBest=false`.
- attempt 1: `sceneWordCounts=[9,12,12,10,9]`, `distanceToAllowedRange=0`, rank `[0,0]`, `candidateUpdated=true`, `becameBestCandidate=true`, `acceptedAsBest=true`.
- No hubo compression attempt 2: el attempt 1 ya obtuvo PASS (in-range).

## 25. Compression attempt 1 (detalle)

- `compression` system prompt dedicado + temperatura `0.2`.
- `compressionAttempt = 1` (internamente attempt 1).
- `sceneWordTargets = [10,11,11,10,10]`
- `targetReductionWords = 3`
- `repairShapeValid=true`, `repairPayloadEligible=true`, `repairGlobalBudgetValid=true`, `repairSceneTargetsMet=false` (guidance), `repairPayloadValid=true`, `repairBudgetValid=true`
- `repairProposedWordCount=52`, `repairProposedSceneWordCounts=[9,12,12,10,9]`, `repairProposedCandidateRank=[0,0]`
- `candidateRank=[0,0]`, `candidateUpdated=true`, `candidateReused=false`, `becameBestCandidate=true`, `acceptedAsBest=true`, `wordCountSource=repaired_candidate`
- `sceneWordCapsEnforced=false`, `sceneWordCapsDeprecated=true` (orientativos como guidance; presupuesto global como único contrato)
- `lastAttemptDiscardedAsRegression=false` (el último intento fue best).

## 26. Candidate evolution

```
initial 55 → compression 52
```

Convergencia monotónica en un solo paso de compresión hasta within-range.

## 27. Best attempt / anti-regresión

- `bestAttempt=1`, `bestAttemptWordCount=52`.
- El candidato 52 entró en rango y fue aceptado como best/PASS.
- `lastAttemptDiscardedAsRegression=false` (el último intento no fue regresión).

## 28. Resultado length-control

Se declara:

```
LENGTH_CONTROL_VALIDATED
```

El script terminó con `47 <= finalWordCount(52) <= 52`, `durationContract.status == PASS` y `structureValid == true`. El overshoot inicial se redujo drásticamente (55 vs rutas históricas 74/69/56) y la compresión de un solo intento logró el rango. Es el **primer E2E V2 canónico con script PASS** en los cinco intentos.

---

## 29. Comparativa E2E 1–5

| E2E | Job                     | Initial words | Final words | Retry           | Structure | Script          |
| --- | ----------------------- | ------------: | ----------: | --------------- | --------- | --------------- |
| 1   | `cmo-2026-08-02-192443` |          74 |          54 | full regen      | inválida  | REVIEW_REQUIRED |
| 2   | `cmo-2026-08-02-204451` |          60 |          69 | full regen      | válida    | REVIEW_REQUIRED |
| 3   | `cmo-2026-08-04-195654` |          56 |          56 | old compression | válida    | REVIEW_REQUIRED |
| 4   | `cmo-2026-08-11-185926` |          69 |          62 | new policy      | válida    | REVIEW_REQUIRED |
| 5   | `cmo-2026-08-14-153529` |          55 |          52 | compression     | válida    | **PASS**        |

Análisis:
1. **Initial overshoot mejoró:** 55 es el menor initial (74→60→56→69→55) y, frente a los E2Es 2/4, se mantuvo un único ajuste de compresión (`reduce_content`, no regresión completa).
2. **Script entró en 47–52:** sí, `final=52` con `status=PASS`, `structureValid=true`. Primera vez.
3. **Parte del hardening utilizada:** presupuesto global + operationalWordTarget en generación inicial (guidance), compression system prompt dedicado con temperatura 0.2, compression prompt imperativo con reducción mínima/deseada, targets por escena como guidance pura (`repairSceneTargetsMet=false` aceptado), presupuesto global como único contrato duro, convergencia monotónica.
4. **Bloqueo histórico de duración en `script` resuelto:** sí, la etapa `script` pasó por primera vez. El bloqueo actual se movió a la etapa `audio`.

---

## 30. Etapas

| Etapa   | Status          | Detalle                                                     |
|---------|-----------------|--------------------------------------------------------------|
| script  | **PASS**        | wordCount 52 in-range; visual V2 válido; structureValid      |
| assets  | **ASSETS_READY**| 10/10 segmentos resueltos (0 fallidos, 0 huérfanos)          |
| audio   | **REVIEW_REQUIRED** | BLOCKED: `AUDIO_DURATION_MISSING`                         |
| prepare | no ejecutada    | —                                                            |
| render  | no ejecutada    | —                                                            |
| validate| no ejecutada    | —                                                            |

- `lastCompletedStage`: `audio`
- `outputVideoPath`: `null`
- `validationStatus`: `null`

### Assets (detalle)

- Total segmentos: 10, resueltos: 10, fallidos: 0, huérfanos: 0.
- Providers usados: `pixabay` (photographs y stock) + `wikimedia_commons` (diagrams).
- Todos `segmentValidationStatus=PASS`; rutas bajo `assets/`; cero paths V1; ningún `generated` (request lo prohíbe).
- Licencias: Pixabay Content License (pixabay) y Public domain / CC BY-SA (wikimedia).

### Audio (bloqueo)

- Provider `edge-tts`, voz `es-ES-AlvaroNeural`, `continuous=false`.
- Los 5 archivos `scenes/scene-0N.mp3` **existen** (`exists=true`) y son válidos.
- `durationSec`, `durationSource`, `activeAudioDurationSec` = `null` en los 5 → el proceso de medida de duración no devolvió duración el primer intento.
- `duration_estimated = true`.
- `reviewReasons = ["AUDIO_DURATION_MISSING: scenes [1, 2, 3, 4, 5] lack valid measured duration"]`.
- Este bloqueo es posterior a script y es **independiente del length-control**.

Nota técnica (read-only, sin modificación): no hay `ffprobe` host; el fallback Docker usa `docker run --entrypoint ffprobe` con mount `parents[3]:/workspace` y `DOCKER_API_VERSION=1.43`. Verificación manual inmediata post-run con el mismo mount devolvió una duración válida (`5.184s` para scene-01), lo que sugiere un fallo transitorio de medida durante la ejecución, no un problema del archivo. No se relanza audio manualmente.

---

## 31. ffprobe

No aplica (no hay vídeo final; `outputVideoPath=null`).

## 32. Resultado global

- Exit code top-level: `0`.
- Estado final: `REVIEW_REQUIRED` (bloqueo controlado en `audio`).
- **Length-control validado en E2E real (script PASS primero de la serie).**
- Pipeline bloqueado posteriormente en la etapa `audio`.

## 33. Criterios PASS (1–15)

Cumplidos:
1. exit code top-level = 0 ✅
3. VisualPlan V2 válido ✅
4. `structureValid=true` ✅
5. `47 <= wordCount(52) <= 52` ✅
6. `durationContract.status = PASS` ✅
7. assets completos (10/10, ASSETS_READY) ✅

Incumplidos:
- 2. status final no `REVIEW_REQUIRED` ❌ (está `REVIEW_REQUIRED`)
- 8. audio completo ❌ (`AUDIO_DURATION_MISSING`)
- 9. prepare ❌ (no alcanzada)
- 10. render ❌
- 11. validate ❌
- 12. vídeo final existe ❌
- 13. `validationStatus=PASS` ❌ (`null`)
- 14. `qualityGate=PASS` ❌ (no ejecutado)
- 15. cero blocker ❌

No se declara `E2E V2 CANÓNICO PASS`. No se cierra formalmente el change.

---

## 34. Integrity source tree

`git diff --name-only -- bin tests src` → vacía.

## 35. Hashes finales

Idénticos al snapshot inicial:

```
bin/generate_script.py          dd26abce66af4422d326003235f50e1ada2ba5849ee6d02f41aa9a238c27efbc
bin/run_job.py                  6240606ba8ea1b5a07c56e0d0dcf25fc30a4b4eed58a82a2dffbaeecb7f67d0f
bin/visual_plan_v2.py           37c5c463d2a9069627705fa26c4b7b94b3fd3121fcc02d6ca5d6dad77cad66ff
bin/duration_profiles.py        41e12bcafd30c79d122fa93d23fda7a02f64ac25ee88e544d45df18311a5f45d
tests/test_generate_script_v2.py 3dd1b091cccc9534074fe5d1089239cb4bbc7b78ea5931bcc809fde93b6807d0
```

## 36. Git final

- `git diff --check`: limpio (solo warning permisos `data/postgres/`).
- `git status --short`:
  - `?? data/cache/` (caché automática del provider creada durante el run real; artefacto runtime, no manual).
  - `M  docs/project/current-state.md`
  - `M  openspec/changes/retire-legacy-visual-v1/tasks.md`
  - `?? docs/sessions/20260814-173710-...fifth-canonical-e2e.md`
- `git diff --name-status`: `M docs/project/current-state.md`, `M openspec/changes/retire-legacy-visual-v1/tasks.md`.
- `git diff --cached --name-status`: vacío (staging vacío).
- Jobs históricos intactos (cuatro jobs canónicos confirmados presentes tras el run).

## 37. Restricciones cumplidas

- Una única invocación ✅
- Cero segunda ejecución ✅
- Cero sexto E2E ✅
- Cero cambios de código/tests ✅
- Cero staging, commit, push, amend, reset, rebase ✅
- Cero MCP, cero reindexado ✅
- No modificar `.env` ✅ (solo lectura de nombres/estados, sin secretos)
- No stages manuales para rescatar el job ✅
- no se muestra ningún secreto ✅

## 38. Próximo paso

1. Auditoría read-only final del quinto E2E (por hacer, fuera de esta sesión).
2. Diagnosticar el bloqueo de `audio` (`AUDIO_DURATION_MISSING`): la medida de duración de los mp3 no devolvió valor durante el run pese a que el fallback Docker funciona manualmente; evaluar causa (transitoria vs contracto) en una sesión de corrección/sesión de audio.
3. Si se resuelve el bloqueo de audio, re-ejecutar pipeline desde la etapa correspondiente para intentar E2E PASS completo.
4. Cierre formal del change solo tras auditoría final read-only.

---

## Resultado de la sesión

```
SLICE_6B_FIFTH_E2E_LENGTH_CONTROL_VALIDATED_PIPELINE_BLOCKED
```