# Tasks: web-ui-mvp

Cambio único `change/web-ui-mvp`, cuatro slices.

**Estado general: IN PROGRESS — Slice 1 aprobado y committed; Slice 2 IMPLEMENTED / TESTED /
APPROVED (commit autorizado); Slices 3/4 pending.**
No marcar el cambio global como completo.

> OpenSpec regularizado después de la implementación de Slice 1 y antes del Review formal
> de Slice 1, sobre el Plan arquitectónico aprobado. Los archivos no preceden a la
> implementación.

## Slice 1 — Límite de invocación de pipeline reutilizable

**Estado: IMPLEMENTED / TESTED / REVIEWED / APPROVED**

- [x] `run_pipeline(job_id=None)` preserva comportamiento CLI histórico.
- [x] ID de job explícito en `run_pipeline(job_id=<id seguro>)`.
- [x] Validación de ID en el límite (`validate_job_id`) — rechaza traversal/separadores/
      control/vacío.
- [x] Fail-fast: `job_id` explícito se valida en la entrada de `generate_script`, antes de
      LLM/red, retries y construcción de rutas (`INVALID_JOB_ID` sin `call_llm`).
- [x] `job_id` explícito + `--output` arbitrario incompatibles (`JOB_ID_OUTPUT_CONFLICT`,
      antes de LLM/red/filesystem); `--job-id`/`--output` mutuamente excluyentes en CLI.
- [x] Ruta canónica autoritativa en `run_pipeline` para ID explícito: se niega el
      `parsed["path"]` ajeno y el `jobId` discrepante
      (`SCRIPT_OUTPUT_CONTRACT_VIOLATION`); falla cerrado.
- [x] Identidad del metadata cargado: tras `load_metadata`, en ramas de éxito y de fallo,
      `_validate_explicit_metadata_identity` exige `metadata["jobId"] == job_id`
      (`SCRIPT_OUTPUT_CONTRACT_VIOLATION`) ANTES de mutar el archivo (sin
      `set_failure`/`append_orchestration`/cambio de `status`/`save_metadata`).
- [x] Legado intacto: `job_id=None` usa descubrimiento por stdout y `--output` sin
      `--job-id` sigue funcionando.
- [x] Propagación vía comando de script (`build_script_command` añade `--job-id`).
- [x] Adaptador CLI reenvía (`bin/generate_script.py --job-id`).
- [x] `generate_script(job_id=...)`: directorio/metadata canónicos;
      `jobId == directorio == metadata.jobId`.
- [x] Backward compatibility: `job_id=None` usa `generate_job_id(topic)`.
- [x] Sin `output_dir` arbitrario en `run_pipeline`.
- [x] 33 tests dirigidos (`tests/test_run_job_job_id.py`) incl. hardening fail-fast,
      `JOB_ID_OUTPUT_CONFLICT`, legado `--output`, autoridad de ruta canónica y validación
      de identidad del metadata cargado.
- [x] Suite completa `1913 passed, 0 failed`; `git diff --check` limpio.
- [x] Review formal (retry): `SLICE_1_APPROVED`; finding F1 (identidad metadata cargada)
      CLOSED.
- [x] Committed en `change/web-ui-mvp` tras Review aprobado. Triple invariante final:
      `requested jobId == directorio canónico == metadata.jobId`.

## Slice 2 — Backend / Job API

**Estado: IMPLEMENTED / TESTED / APPROVED** (commit autorizado: `feat(web): add backend job API`).

- [x] Shell FastAPI (`web/backend`) en `src/shorts_creator/web/` (`app`, `dependencies`,
      `routes/{health,jobs,media}`).
- [x] DTOs de request/respuesta (allowlist estricto, `extra="forbid"`).
- [x] `/api/v1/capabilities` (modos visuales/providers/voices desde enums canónicos).
- [x] `JobService`.
- [x] Límite `JobRepository` (implementación por archivo con sidecar atómico `web-job.json`).
- [x] `LocalJobExecutor` (max concurrency 1, admitencia 1 activo + 1 cola, reconciliación de
      stale QUEUED/RUNNING→INTERRUPTED).
- [x] Estado de ejecución web por job (`QUEUED|RUNNING|FINISHED|INTERRUPTED|FAILED`).
- [x] Proyección de polling (`currentStage`, `lastCompletedStage`, `pipelineStatus`,
      `has_video`, warnings, reviewReasons).
- [x] Mapeo centralizado de excepciones (códigos estables + mensajes saneados).
- [x] Preview/download MP4 seguros y job-scoped (con `Range` nativo → 206).
- [x] Sin exposición de paths (frontend nunca envía/recibe paths).
- [x] Wiring de producción dentro del lifespan (no en import): reconciliación de stale una
      vez al arrancar y `executor.shutdown()` en `finally` al apagar.
- [x] Tests: 60 (`tests/test_web_*` + `test_web_lifecycle`); suite completa
      `1971 passed, 0 failed`; `git diff --check` limpio.

## Slice 3 — UI Angular

Estado: PENDING.

- [ ] Formulario de generación (topic, duration, tts, voice, visual mode, asset providers).
- [ ] Progreso de job por stage.
- [ ] Estado final + presentación `ASSETS_PARTIAL` / `REVIEW_REQUIRED`.
- [ ] Preview MP4 + acción de descarga.
- [ ] Polling (~1s) hasta estado terminal.

## Slice 4 — Integración / hardening

Estado: PENDING.

- [ ] Build de producción Angular servido con/por FastAPI (topología single container).
- [ ] Volumen persistente `data/videos`.
- [ ] Documentación (un worker Uvicorn mientras executor en memoria).
- [ ] Revisión final de estructura/secretos/trazabilidad.
- [ ] Suite completa + `git diff --check` + smoke real.
- [ ] Cierre (results.md + docs + commit autorizado).

## Fuera de alcance (no implementar)

- generated-image fallback
- engagement configurable
- publishing
- auth/payments/SaaS
- DB / Redis / Celery
- Kubernetes / n8n / microservicios
- SSE/WebSockets MVP
- cancelación MVP
- refactor de pipeline
- exponer `--output` CLI por HTTP
- exponer `_final_summary` (jobPath/outputVideoPath) por HTTP
