# Slice 6B — Tercer E2E V2 canónico

- **Sesión:** `retire-legacy-visual-v1-slice-6b-third-canonical-e2e`
- **Modelo:** `opencode/deepseek-v4-flash-free` (variante `default`)
- **Modo:** Build
- **Fecha:** 2026-08-04

## Configuración

- Máximo de pasos agentic: 26; subagentes: ninguno.
- Codebase Memory MCP: DESACTIVADO; 0 llamadas MCP.
- Reindexado: no.
- No se implementaron correcciones de código, no se hizo commit y no se cerró
  formalmente el change.

## HEAD y estado Git inicial

- Rama: `main`
- HEAD: `ad86834b414ab5973ffee0d4701fa86ce7b30b47`
- Historial:
  ```
  ad86834 docs(project): record Slice 6B duration fix closure
  9eb1f13 fix(script): harden canonical duration retries
  e5e2a4e docs(project): record Slice 6B script fix commit
  f48f98f fix(script): harden V2 prompt and retry contract
  496dd33 docs(project): record Slice 6A closure commit
  ```
- Working tree limpio; staging vacío; untracked cero.
- `git diff --check` limpio (único warning no bloqueante de permisos de
  `data/postgres/`).

## Baseline heredada

```text
1158 passed, 0 failed
```

Constantes contractuales vigentes: `MAX_SCRIPT_ATTEMPTS == 3`,
`MIN_WORDS_PER_SCENE == 7`. Validator, runner y perfiles intactos.

## Preflight

### Tests F8 (focalizados)

```
python3 -m pytest -q tests/test_generate_script_v2.py \
  -k 'test_f8_canonical_flows_to_compression_prompt or test_f8_canonical_base_used_by_merge or test_f2_expected_interpolated_six_scenes'
```

Resultado: `3 passed, 130 deselected`.

### Dry-run E2E

```
python3 -m pytest -q tests/test_visual_v2_dry_run_e2e.py
```

Resultado: `22 passed`.

### Constantes contractuales

El script de preflight de la sesión referenciaba `get_duration_budget`, que no
existe. Se usó la ruta real de runtime
(`resolve_requested_duration` + `calculate_word_budget` con
`PROVISIONAL_SCENE_COUNT`) y se reprodujeron exactamente los valores esperados:

```text
MAX_SCRIPT_ATTEMPTS 3
MIN_WORDS_PER_SCENE 7
minimumWords 47
preferredWords 52
maximumWords 52
compression_system_prompt True
```

La resolución de runtime confirma `profile short_25_30`, `minSec=27`,
`maxSec=30`, `strictness=balanced`.

## Variables SET/UNSET

Variables de entorno del shell: todas `UNSET` (la pipeline las carga desde
`.env`). Cargadas vía `load_env()`:

| Variable | Estado | Valor efectivo |
|----------|--------|----------------|
| LLM_PROVIDER | SET | openai |
| LLM_MODEL | SET | gpt-4o-mini |
| LLM_API_KEY | SET | (no expuesto) |
| PIXABAY_API_KEY | SET | (no expuesto) |
| TTS_PROVIDER | SET | (valor no expuesto) |
| ELEVENLABS_API_KEY | SET | (no expuesto) |

## Providers efectivos

| Provider | enabled | implemented | requiresApiKey |
|----------|---------|-------------|----------------|
| wikimedia_commons | True | True | False |
| pixabay | True | True | True |
| pexels | False | False | True |
| freeai | False | False | True |
| pollinations | False | False | False |

TTS efectivo (request.voice): `edge_tts`, voz `es-ES-AlvaroNeural`.

## Docker y recursos

- Docker client/server: `29.1.3` / `29.1.3`.
- Imagen `linuxserver/ffmpeg:latest` presente (`id=sha256:9872c5f1f36d...a297e`).
- `df -h .`: `/dev/sdc` 1007G, 943G disponibles, 2% usados.
- `data/videos` escribible.

## Snapshot anterior

- Directorios previos capturados en
  `/tmp/shorts-creator-third-e2e-before.txt` (89 jobs).
- Jobs históricos presentes e intactos:
  `cmo-2026-08-02-192443`, `cmo-2026-08-02-204451`.
- Timestamp snapshot: `2026-08-04T21:56:22+02:00`; epoch `1785873382`.

## Comando exacto

Ayuda comprobada sin ejecutar el pipeline (`python3 bin/run_job.py --help`).

```
python3 bin/run_job.py --topic "Cómo se forma un arcoíris" --duration 30
```

Una única invocación top-level.

## Confirmación de una sola invocación

Una sola ejecución. No se repitió el comando ni se varió tema/duración. No se
ejecutaron scripts de etapas manualmente. No se editó metadata. No se relanzó
tras el resultado.

## Timestamps y duración

- Inicio: `2026-08-04T21:56:29+02:00` (epoch `1785873389`)
- Fin: `2026-08-04T21:56:54+02:00` (epoch `1785873414`)
- Duración: 25s

## Exit code

```text
0
```

## stdout (resumido)

```
REVIEW_REQUIRED: job cmo-2026-08-04-195654 needs human review
{"jobId": "cmo-2026-08-04-195654", "jobPath": ".../data/videos/cmo-2026-08-04-195654", "status": "REVIEW_REQUIRED", "lastCompletedStage": "script", "outputVideoPath": null, "validationStatus": null}
```

## stderr (resumido)

Vacío.

## Job ID y path

- Job ID: `cmo-2026-08-04-195654`
- Path: `data/videos/cmo-2026-08-04-195654`
- Un solo directorio nuevo tras la ejecución (confirmado por `comm -13`).

## Archivos producidos

```
metadata.json
```

(`du -sh` = 20K; solo metadata, el pipeline se detuvo en `script`).

## Request

- topic: `Cómo se forma un arcoíris`
- duración: target 30s, min 27s, max 30s, strictness balanced, wpm 110
- `request.visuals.schemaVersion`: 2
- `request.visuals.allowGeneratedImages`: false
- provider LLM: `openai` (`gpt-4o-mini`); TTS `edge_tts`.

## Contrato V2 / escenas

- 5 escenas, `sceneNumber` secuencial 1–5.
- `visualPlan._schemaVersion` = 2 en todas.
- Cero campos V1 residuales (`editorialRole`, `strategy`, `primaryAssetType`,
  `secondaryAssetType`, `visualTemporalIntent`).
- Enums usados en `assetPreferences` y `visualSequence[].assetPreference`:
  `diagram`, `illustration`, `photograph`, `stock`. Cero enums inválidos.
- `imageGenerationPrompt` y `negativePrompt` presentes (V2 permitido).
- `durationContract.structureValid` = true; `structureIssues` = [].

## Contrato temporal

```text
targetSec=30, minSec=27, maxSec=30, strictness=balanced, spokenWordsPerMinute=110
wordCount=56, sceneCount=5, sceneWordCounts=[14,13,9,7,13]
spokenDurationSec=30.5, pauseDurationSec=1.4, estimatedDurationSec=31.9
minimumWords=47, preferredWords=52, maximumWords=52
status=FAIL, retries=3, bestAttempt=0, bestAttemptWordCount=56
lastAttemptDiscardedAsRegression=false
reviewReasons: DURATION_OUT_OF_RANGE: estimated=31.9s (spoken=30.5s + pauses=1.4s), target=30s, min=27s, max=30s, words=56, scenes=5
```

## Retry history

| attempt | strategy | wordCount | structureValid | durationStatus | repairShape | repairBudget | repairPayload | candidateUpdated | candidateReused | wordCountSource | candidateRank | becameBestCandidate | acceptedAsBest |
|---------|----------|-----------|----------------|----------------|-------------|--------------|---------------|------------------|-----------------|-----------------|---------------|---------------------|----------------|
| 0 | initial | 56 | true | FAIL | true | true | true | true | false | generated_candidate | [4,4] | true | true |
| 1 | compression | 56 (reused) | true | FAIL | true | false | false | false | true | previous_candidate | [4,4] | false | false |
| 2 | compression | 56 (reused) | true | FAIL | true | false | false | false | true | previous_candidate | [4,4] | false | false |

Repair errors:
- Attempt 1: `REPAIR_SCENE_WORD_CAP_EXCEEDED` escenas 1 (13>11) y 2 (12>11).
- Attempt 2: `REPAIR_SCENE_WORD_MINIMUM_NOT_MET` escena 4 (6<7).

## Caps por escena

Caps para compresión (escenas 1–5): `[11, 11, 10, 10, 10]` (suma 52).
El candidato inicial de 56 palabras excede caps en escenas 1 (14>11), 2 (13>11)
y 5 (13>10); ninguna escena queda por debajo de 7 palabras.

## Best attempt

- `bestAttempt=0`, `bestAttemptWordCount=56`.
- Solo el intento 0 tiene `acceptedAsBest=true`.
- El candidato persistido es el inicial de 56 palabras (la compresión no logró
  un payload budget-valid).
- Cero payloads válidos descartados como regresión
  (`lastAttemptDiscardedAsRegression=false`).

## Telemetría de repair

- Intentos 1 y 2: `repairShapeValid=true` pero `repairBudgetValid=false`,
  `repairPayloadValid=false`; `candidateUpdated=false`,
  `candidateReused=true`, `wordCountSource=previous_candidate`.
- `candidateRank=[4,4]` estable en los tres intentos.

## Comparación con los dos E2E anteriores

| Job | status | etapa final | structureValid | wordCount | maximumWords | retry sequence | causa bloqueo | vídeo |
|-----|--------|-------------|----------------|-----------|--------------|----------------|---------------|-------|
| `cmo-2026-08-02-192443` | REVIEW_REQUIRED | script | false | 54 | 52 | (3, sin telemetría) | enums V2 inválidos (`animation`, `infographic`) + duración | no |
| `cmo-2026-08-02-204451` | REVIEW_REQUIRED | script | true | 69 | 52 | (3, sin telemetría) | duración (69 > 52) | no |
| `cmo-2026-08-04-195654` | REVIEW_REQUIRED | script | true | 56 | 52 | initial→compression→compression | duración (56 > 52) | no |

Progreso: contrato visual y estructura ya válidos en el tercer E2E; la única
causa de bloqueo restante es el exceso de palabras (56 > 52).

## Estado de script

`REVIEW_REQUIRED`, detenido por contrato en `script` por
`DURATION_OUT_OF_RANGE`. `durationContract.structureValid=true`.

## Estado de assets / audio / prepare / render / validate

Ninguna ejecutada (el pipeline se detuvo en `script`). Sin artefactos ni
contratos en esas etapas.

## Quality gate

No ejecutado (etapa `validate` no alcanzada).

## Vídeo final

Ninguno. `outputVideoPath=null`. ffprobe no aplica.

## Resultado

- **BLOCKED** (`REVIEW_REQUIRED` controlado por contrato en `script`), por
  `DURATION_OUT_OF_RANGE` (56 > 52 palabras).
- Verdict: `SLICE_6B_THIRD_E2E_SCRIPT_BLOCKED_NEEDS_FOLLOWUP`
- El contrato visual y la estructura ya son válidos; el único bloqueo es la
  duración.

## Causa exacta de bloqueo

`DURATION_OUT_OF_RANGE: estimated=31.9s (spoken=30.5s + pauses=1.4s), target=30s, min=27s, max=30s, words=56, scenes=5`. El candidato inicial superó
`maximumWords` (52); los dos retries de compresión no lograron un payload
budget-valid, por lo que se conservó el candidato inicial como best attempt.

## Estado Git final

- Working tree con modificaciones únicamente documentales.
- Cero staging, cero commit, cero push, cero amend/reset/rebase.
- Cero cambios productivos (bin/tests/src intactos).
- Cero MCP, cero reindexado.

## Cero segunda invocación

No se ejecutó una segunda invocación.

## Próximo paso

Corregir el exceso de palabras (56 > 52) y ejecutar un cuarto E2E V2 canónico.
Tras un PASS completo, realizar auditoría y cierre formal del change.

## Auditoría de política temporal (read-only, post-E2E)

- Verdict: `SLICE_6B_DURATION_POLICY_AUDIT_RECOMMENDS_CHANGES`.
- La política anterior (caps estáticos por escena + `MIN_WORDS_PER_SCENE == 7` +
  rechazo completo antes del ranking) producía un **falso negativo global**.
- El tercer E2E necesitaba reducir **4** palabras (56 → 52), pero los caps por
  escena (`[11,11,10,10,10]`) exigían una reducción de **8** y rechazaban
  retries con alguna escena por debajo de siete palabras aunque el total global
  fuese válido. Los caps y el mínimo siete se clasificaron como mecanismos del
  repair, no como contracto.
- Recomendación: targets por escena como guidance, presupuesto global como único
  contracto duro y convergencia monotónica de candidatos.

## Corrección de política temporal (Build)

- Sesión: `retire-legacy-visual-v1-slice-6b-duration-policy-fix`.
- Implementado en `bin/generate_script.py` y `tests/test_generate_script_v2.py`.
- Detalles, decisiones y baselines en el session log de la corrección
  (`docs/sessions/20260804-224050-retire-legacy-visual-v1-slice-6b-duration-policy-fix.md`).
- Baseline funcional: **`1165 passed, 0 failed`**.

## Nota histórica de follow-up

La corrección de política fue auditada posteriormente.
El único blocker restante fue un placeholder de prompt sin interpolar.
No se ejecutó un cuarto E2E.

La corrección de política derivada de este E2E fue posteriormente reaprobada y
versionada mediante `d377932`. El cuarto E2E sigue pendiente.
