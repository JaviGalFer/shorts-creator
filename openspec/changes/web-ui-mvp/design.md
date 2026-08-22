# Design: web-ui-mvp

> **Estado:** IN PROGRESS — Slices 1, 2 y 3 implementados, revisados y committed.
> Slice 4 en redefinición tras extraer el frontend Angular a un repositorio independiente.
> El backend Python/FastAPI permanece en este repositorio y el frontend se integra
> exclusivamente mediante el contrato HTTP.

## Arquitectura objetivo

```text
shorts-creator-web (repositorio independiente)
Angular
   ↓ HTTP / JSON
FastAPI (este repositorio)
   ↓
JobService
   ├── JobRepository
   └── JobExecutor
          ↓
     LocalJobExecutor         (PLANNED — max concurrency = 1)
          ↓
     run_pipeline()
          ↓
script → assets → audio → prepare → render → validate
```

### Límite de reutilización canónico

```text
CLI ─────┐
         ├── run_pipeline()
Web ─────┘
```

El backend Web **NUNCA** ejecuta `bin/run_job.py` como su API interna. La CLI
(`bin/run_job.py`) es un adaptador delgado sobre `run_pipeline` y NO es el límite
de reutilización web.

## Estado del límite de invocación (Slice 1 — implementado)

Slice 1 ha establecido soporte de **identidad de job explícita** en el runner canónico:

```text
run_pipeline(job_id=<id seguro explícito>)
→ build_script_command  (añade --job-id)
→ bin/generate_script.py --job-id
→ generate_script(job_id=...)
→ data/videos/<jobId>/metadata.json
→ metadata["jobId"] == jobId
```

- `job_id=None` → comportamiento CLI histórico (ID derivado de topic) intacto.
- NO se ha añadido ningún `output_dir`/`output` arbitrario a `run_pipeline`.
- Identidad única web: **API jobId == directorio jobId == metadata.jobId**.
- `validate_job_id` rechaza valores peligrosos (traversal, separadores, control).

## Abstracciones de escalabilidad (PLANNED, no implementadas)

Interfaces/límites conceptuales:

- `JobService` — orquesta ciclo de vida del job web.
- `JobRepository` — persistencia del estado de ejecución web.
- `JobExecutor` — ejecuta el pipeline; eliminable/inyectable.
- Límite de proyección/DTO — `metadata.json` → DTO de respuesta explícito.

Implementaciones iniciales permitidas (futuras):

- repositorio por archivo;
- ejecutor local en proceso;
- un worker Uvicorn;
- un job de vídeo concurrente.

Implementaciones futuras reemplazables sin cambiar las rutas HTTP:

- repositorio Postgres;
- ejecutor de cola durable/distribuido.

**NO implementar esos componentes futuros ahora.**

## Polling

- El MVP usa **polling**.
- Sin porcentajes falsos.
- Progreso por **stage**.
- SSE/WebSocket quedan como opciones futuras únicamente.

## Storage

- Los artefactos canónicos permanecen bajo `data/videos/<jobId>/`.
- Un sidecar futuro de estado de ejecución web debería ser **por job** en lugar de un
  registro global mutable cuando sea práctico, p. ej. `data/videos/<jobId>/web-job.json`.
- `metadata.json` canónico permanece propiedad del pipeline.
- **No implementar esto en esta tarea.**

## Seguridad — invariante arquitectónico (ALTA PRIORIDAD)

Ver `specs/web-security.md`. El API Web expone **recursos de dominio**, nunca
**recursos de filesystem**:
- IDs UUID4 opacos generados por el backend (identidad única jobId == dir == metadata.jobId).
- UUID es identificador, NO autorización.
- El frontend nunca envía ni recibe paths/directorios/nombres de archivo.
- `metadata.json` → proyección → DTO allowlist → frontend (nunca raw metadata).
- Errores centralizados: códigos estables + mensajes saneados.
- Sin paths, sin commands de subproceso, sin stdout/stderr crudo, sin secrets al frontend.
- `--output` CLI y `_final_summary` (jobPath/outputVideoPath) son SOLO CLI
  (ver `specs/job-api.md` y `specs/web-security.md`).
