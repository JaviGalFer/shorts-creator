# Spec: job-api (PLANNED — no implementado)

Superficie HTTP mínima planificada. NO se implementan endpoints todavía.

## Endpoints

```text
GET  /api/v1/health
GET  /api/v1/capabilities

POST /api/v1/jobs
GET  /api/v1/jobs
GET  /api/v1/jobs/{jobId}

GET  /api/v1/jobs/{jobId}/video
GET  /api/v1/jobs/{jobId}/download
```

## Requisitos

- `POST /api/v1/jobs` devuelve **`202 Accepted`**.
- El backend genera **UUID4**.
- El **request DTO** contiene SOLO entradas de producto: topic, duration, tts provider,
  voice, visual mode, asset providers.
- **Sin** campos output/path/directory (`output`, `outputDir`, `filename`, ...).
- **Solo** response DTOs explícitos (allowlist); nunca raw `metadata.json`.
- `ASSETS_PARTIAL` y `REVIEW_REQUIRED` son **resultados de dominio normales**, no fallos de
  infraestructura HTTP.
- Preview/download resuelven el MP4 interno **solo** a partir de la identidad del job.

## Compatibilidad con el pipeline canónico

- La validación del request reutiliza los enums/contratos canónicos
  (`contracts/visual_media`, `audio.get_audio_defaults`, `assets/router.ALLOWED_PROVIDERS`,
  `contracts/duration.resolve_requested_duration`) en lugar de duplicar constraints de dominio.

## RFC de estado (proyección)

- `state` = estado de ejecución web (`QUEUED|RUNNING|FINISHED|INTERRUPTED|FAILED`).
- `pipelineStatus` = `metadata["status"]` canónico.
- `currentStage` / `lastCompletedStage` (derivado de `orchestration.statusHistory`).
- `createdAt` / `updatedAt` (normalizados).
- `hasMp4` (existencia de `video.mp4`).
- `warnings` / `reviewReasons` para `ASSETS_PARTIAL` / `REVIEW_REQUIRED`.

## No implementar

- No instalar FastAPI todavía.
- No crear archivos backend web.
- No exponer `--output` CLI ni `_final_summary` (jobPath/outputVideoPath) en ninguna
  proyección HTTP.
