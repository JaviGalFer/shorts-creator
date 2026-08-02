# Sesión: Slice 6B — E2E V2 canónico controlado

Timestamp real capturado: `2026-08-02T21:23:05+02:00`
Timestamp de ejecución: `2026-08-02T21:23:48+02:00` (epoch 1785698628)

## 1. Configuración

- Sesión: `retire-legacy-visual-v1-slice-6b-canonical-e2e`
- Modelo: `opencode/deepseek-v4-flash-free`, variante `default`
- Modo: `Build`; máx. 24 pasos agentic; sin subagentes
- Codebase Memory MCP: desactivado; 0 llamadas MCP; sin reindexado
- Objetivo: E2E real del pipeline V2 canónico desde `bin/run_job.py`

## 2. Estado Git inicial

- Rama: `main`
- HEAD: `496dd33abd07acb7dda5534613a882adf81ac84e`
- Historial: `496dd33` (record 6A closure), `86170d3` (6A baseline), `3866cc6` (5B closure)
- Working tree limpio; staging 0; untracked 0; `git diff --check` limpio
- Único aviso: warning de permisos ignorado de `data/postgres/` (no bloqueante)

## 3. Preflight CLI

- `python3 bin/run_job.py --help` confirma: `--topic` (required), `--duration`, sin `--stop-after` por defecto (=validate, pipeline completo), sin dry-run por defecto
- Dry-run (`--duration 30 --dry-run`) confirma el plan de 6 etapas (script→assets→audio→prepare→render→validate) y los comandos hijos
- Comando real confirmado: `python3 bin/run_job.py --topic "Cómo se forma un arcoíris" --duration 30`

## 4. Preflight de variables (SET/UNSET)

- LLM_PROVIDER=SET (openai); LLM_API_KEY=SET; LLM_MODEL=SET (gpt-4o-mini)
- PIXABAY_API_KEY=SET
- TTS_PROVIDER=SET (edge_tts)
- ELEVENLABS_* presentes pero no seleccionados (TTS_PROVIDER=edge_tts)
- Sin base URL personalizada: `generate_script.call_llm` usa endpoint OpenAI `https://api.openai.com/v1/chat/completions`
- Ningún valor secreto expuesto

## 5. Preflight de providers

- LLM: `openai` (cliente OpenAI-compatible), modelo `gpt-4o-mini`
- Wikimedia Commons: activo, implementado, sin key
- Pixabay: activo, implementado, key presente
- Pexels: deshabilitado / no implementado (planned)
- FreeAI y Pollinations: deshabilitados / no implementados
- TTS esperado: `edge_tts`; ElevenLabs no seleccionado

## 6. Preflight Docker

- Daemon disponible; server version 29.1.3
- Imagen de render `linuxserver/ffmpeg:latest` presente localmente
- Render usa `DOCKER_API_VERSION=1.43` (mecanismo existente del proyecto)
- `docker compose` no disponible en el host (no requerido: pipeline usa `docker run` directo)
- Disco: 943G libres; `data/videos/` escribible
- No se requirieron `docker compose up` ni pulls arbitrarios

## 7. Snapshot previo de jobs

- Lista previa registrada (88 directorios bajo `data/videos/`, incluidos jobs históricos y de E2E previos)
- Job nuevo identificado por diferencia con el snapshot

## 8. Comando exacto

```
python3 bin/run_job.py --topic "Cómo se forma un arcoíris" --duration 30
```

## 9. Una única ejecución

- Única invocación top-level de `bin/run_job.py`
- stdout/stderr redirigidos a `/tmp/opencode/e2e_stdout.log` y `e2e_stderr.log`
- Sin `tee` que altere la detección de salida

## 10. Exit code y duración

- Exit code: `0` (terminación controlada, no un fallo por excepción)
- Duración total: 55s (inicio 21:23:48, fin 21:24:43)

## 11. Job ID

- `cmo-2026-08-02-192443`
- Path: `/home/javi/projects/shorts-creator/data/videos/cmo-2026-08-02-192443`
- Exactamente un job nuevo tras la ejecución

## 12. Estados por etapa

| Etapa | Estado |
|-------|--------|
| script | `REVIEW_REQUIRED` (detenido por contrato) |
| assets | no ejecutada |
| audio | no ejecutada |
| prepare | no ejecutada |
| render | no ejecutada |
| validate | no ejecutada |

## 13. Auditoría schema V2

- `request.visuals.schemaVersion == 2`
- `script.scenes` = 5, todas con `visualPlan._schemaVersion == 2`; sin mezcla V1/V2
- Campos V1 residuales (`editorialRole`, `strategy`, `primaryAssetType`, `secondaryAssetType`, `visualTemporalIntent`): 0 apariciones
- `durationContract`: targetSec=30, minSec=27, maxSec=30, strictness=balanced, spokenWordsPerMinute=110

## 14. Assets

- No ejecutada (se detuvo en `script`)
- No se resolvieron assets; no se produjo `assets/`; sin GIFs; sin providers visuales consultados

## 15. Audio y timing

- No ejecutada (se detuvo en `script`)
- Sin archivos de audio; `edge_tts` declarado pero no alcanzado; sin ElevenLabs

## 16. Prepare

- No ejecutada
- Sin timeline ni subtítulos

## 17. Render

- No ejecutada
- Sin vídeo final

## 18. Validate y quality gate

- No ejecutada
- `qualityGate`: N/D (etapa no alcanzada)

## 19. Métricas

- Word budget de la generación: retry 0 = 74 palabras, retry 1 = 59, retry 2 = 54
- `estimatedDurationSec` final estimado: 30.9s (spoken 29.5s + pauses 1.4s), fuera de rango [27,30]
- Sin métricas de pacing (validate no ejecutado)

## 20. Artefactos finales

- Único artefacto: `metadata.json` (11.9 KB) en el job
- Sin vídeo, audio, assets, subtítulos ni logs

## 21. Warnings y errores

- Errores contractuales (en `reviewReasons`):
  - `VISUAL_PLAN_V2_INVALID: v2 plan validation failed after 3 attempts`
  - `V2_STRUCTURE_INVALID_ENUM_VALUE:assetPreferences[0]: scene 3: got 'animation'`
  - `V2_STRUCTURE_INVALID_ENUM_VALUE:visualSequence[0].assetPreference: scene 3: got 'animation'`
  - `V2_STRUCTURE_INVALID_ENUM_VALUE:assetPreferences[0]: scene 5: got 'infographic'`
  - `V2_STRUCTURE_INVALID_ENUM_VALUE:visualSequence[0].assetPreference: scene 5: got 'infographic'`
  - `DURATION_OUT_OF_RANGE: estimated=30.9s, target=30s, min=27s, max=30s, words=54, scenes=5`
- Enums permitidos: archive, diagram, document, generated, illustration, map, painting, photograph, stock

## 22. Resultado

- **BLOCKED** por contrato (`REVIEW_REQUIRED` en `script`), no PASS
- Verdict: `SLICE_6B_E2E_NEEDS_FOLLOWUP`
- El orquestador respetó el contrato y terminó de forma controlada

## 23. Archivos documentales modificados

- `docs/project/current-state.md`
- `openspec/changes/retire-legacy-visual-v1/tasks.md`
- `docs/sessions/20260802-212305-retire-legacy-visual-v1-slice-6b-e2e.md` (este archivo)

## 24. Estado Git final

- Rama `main`; HEAD `496dd33abd07acb7dda5534613a882adf81ac84e` (sin cambios)
- Solo los tres archivos documentales sin stagear
- Job `cmo-2026-08-02-192443` preservado bajo `data/videos/` (ignorado)
- `git diff --check` limpio; staging vacío

## 25. Restricciones respetadas

- Sin staging, commit, push, amend ni cierre formal del change
- Sin cambios en `bin/`, `tests/`, `src/`, `.env`, `.env.example`, `docker-compose.yml`, `Makefile`, `README.md`, `AGENTS.md`, `openspec/project.md`, ni docs de project/architecture/integrations/environment
- Sin segunda invocación de `run_job.py`
- Sin ElevenLabs, Pexels, FreeAI, Pollinations
- Sin instalación de paquetes ni pulls Docker arbitrarios
- Sin MCP ni reindexado

## 26. Próximo paso

- Auditoría read-only de Slice 6B sobre los tres archivos documentales sin stagear
- Sesión de corrección para resolver `VISUAL_PLAN_V2_INVALID` (enums inválidos `animation`/`infographic` en `assetPreferences`) y `DURATION_OUT_OF_RANGE` (word budget), y después re-ejecutar el E2E
- Tras resolver el bloqueo, auditoría y cierre formal del change `retire-legacy-visual-v1`

# Auditoría read-only del primer intento

Añadido posteriormente (2026-08-02) tras la sesión de corrección del E2E. El
resultado histórico del job NO se ha reescrito.

- Verdict: `SLICE_6B_REVIEW_CHANGES_REQUIRED`
- Diagnóstico aprobado:
  - **E1 — Prompt drift:** causa principal. El prompt mantenía una lista manual de
    `assetPreferences` independiente del contrato y la rama de retry
    `reduce_content` no re-declaraba el enum.
  - **E2 — Retry feedback incompleto:** causa contribuyente. Los retries de
    duración no recordaban el contrato visual.
  - **E5 — Incumplimiento estocástico del modelo:** contribuyente.
  - **E6 — Cobertura insuficiente:** confirmado (faltaban tests de enum/retry).
  - **E3 — Canonicalización insuficiente:** parcial.
  - **E4 — Validator incorrecto:** descartado.
- No se modifica el validator V2 (`bin/visual_plan_v2.py`).
- No se relaja el contrato temporal; `MAX_SCRIPT_ATTEMPTS` permanece en 3.
- No se repite el E2E todavía; primero Build (corrección de prompt/retry), luego
  review read-only, luego commit de la corrección, luego un nuevo E2E.
- Findings funcionales: la corrección de prompt/retry se implementó en una sesión
  de Build posterior (ver `docs/sessions/20260802-214507-retire-legacy-visual-v1-slice-6b-script-contract-fix.md`).
- Findings documentales: actualizados en `current-state.md` y `tasks.md`.
- Orden establecido: Build → review → commit → E2E.

# Review del Build de la corrección

Añadido posteriormente (2026-08-02) tras la auditoría read-only de la corrección
de prompt/retry. El resultado histórico del job NO se ha reescrito.

- Verdict de la auditoría read-only de la corrección: `SLICE_6B_FIX_REVIEW_CHANGES_REQUIRED`.
- **F1 MEDIUM:** el primer prompt no transmitía de forma request-scoped que `allowGeneratedImages=false`.
- **F2 MEDIUM:** `tasks.md` presentaba el E2E simultáneamente completado y pendiente dentro de Slice 6A.
- **F3 LOW:** la prohibición `animation/infographic/photo/image/video` no estaba explícitamente limitada a valores del enum.
- **F4 LOW:** el retry no imprimía `issue["path"]` explícitamente.
- **F5 LOW:** faltaba una prueba integrada del flujo real `reduce_content`.
- **F6 LOW:** T1, T4 y T5 tenían comprobaciones insuficientemente precisas.
- No se ejecutó un nuevo E2E en esta auditoría.
- Las correcciones F1–F6 se aplicaron en una sesión de Build separada
  (ver `docs/sessions/20260802-221355-retire-legacy-visual-v1-slice-6b-script-contract-review-fixes.md`).
- El resultado histórico del job `cmo-2026-08-02-192443` permanece intacto
  (BLOCKED en `script`, no se re-escribe ni se re-ejecuta).
