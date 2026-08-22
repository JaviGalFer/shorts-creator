# Results: web-ui-mvp

## Status

**COMPLETED / VERIFIED / CLOSED** — pending authorized merge.

## Product Result

El MVP Web queda separado en dos repositorios independientes:

- `shorts-creator`: pipeline Python + backend FastAPI.
- `shorts-creator-web`: frontend Angular.
- La integración frontend ↔ backend se realiza exclusivamente mediante HTTP/API.
- El backend no sirve ni depende de archivos Angular/static.
- El frontend no conoce ni intercambia rutas locales del filesystem.

El frontend consume `/api/v1` mediante `ShortsApiClient` y en desarrollo local
usa `proxy.conf.json` para redirigir `/api` hacia FastAPI en `localhost:8000`.

Los recursos de vídeo permanecen job-scoped mediante UUID opaco:

- `/api/v1/jobs/{jobId}/video`
- `/api/v1/jobs/{jobId}/download`

## Capabilities contract

El contrato requerido por la UI expone explícitamente `provider` y `media_kind`.

Validado tanto directamente como a través del boundary HTTP:

- `wikimedia_commons` → IMAGE
- `pixabay` → IMAGE
- `pexels` → IMAGE + VIDEO

La respuesta HTTP de `/api/v1/capabilities` no expone API keys ni marcadores de
secretos runtime.

## Backend safety / runtime

Review final focalizada: **PASS — no actionable Slice 4 findings.**

Verificado:

- DTOs y respuestas HTTP mantienen allowlists explícitas.
- Los clientes no suministran rutas locales.
- Los IDs de job son UUID4 validados.
- Errores internos, subprocess details, metadata interna y secretos no se
  exponen por HTTP.
- El wiring del repository/service/executor ocurre durante el lifespan de la app.
- `LocalJobExecutor` permanece in-process y usa un único worker activo.
- Mientras esta arquitectura permanezca en memoria, el MVP requiere un único
  worker Uvicorn.

El runbook local documenta el arranque:

`PYTHONPATH=src python3 -m uvicorn shorts_creator.web.app:app --host 0.0.0.0 --port 8000 --workers 1`

## Backend suite

Suite final:

- `1974 passed, 0 failed`
- 1 warning conocido de deprecación Starlette/httpx, no relacionado con el change.
- `git diff --check` limpio.

Se añadió `testpaths = ["tests"]` a pytest para evitar discovery accidental sobre
directorios runtime como `data/postgres/`.

## Frontend validation

Repositorio `shorts-creator-web`:

- 8 test files passed.
- **54 tests passed, 0 failed**.
- `npm run build` PASS.
- Bundle inicial de producción: **302.34 kB**.
- Transferencia estimada: **78.73 kB**.

## Frontend ↔ API smoke

Smoke real de integración local:

1. FastAPI arrancado en `127.0.0.1:8000`.
2. Angular dev server arrancado en `localhost:4200`.
3. Peticiones realizadas contra `localhost:4200/api/...`, atravesando el proxy
   Angular hacia FastAPI.

Resultados:

- `GET /api/v1/health` → **HTTP 200**, respuesta servida por Uvicorn.
- `GET /api/v1/capabilities` → **HTTP 200**.
- La respuesta real contiene `provider` + `media_kind`.
- Pexels expone las capabilities IMAGE y VIDEO.

Este smoke valida el boundary HTTP y el proxy de desarrollo; no ejecuta un job
real ni dispara el pipeline/proveedores externos.

## Repository split

Durante Slice 4 se descartó antes de aprobación la topología WIP single-container
que servía Angular desde FastAPI.

Se retiraron del backend:

- `web/frontend/`
- serving estático Angular desde FastAPI
- Dockerfile single-container asociado
- test de integración estática asociado

El frontend fue preservado y validado en el repositorio independiente
`shorts-creator-web`.

## Limitaciones aceptadas / fuera de alcance

- Auth, payments y funcionalidades SaaS.
- DB / Redis / Celery para estado de jobs Web.
- Múltiples workers Uvicorn mientras `LocalJobExecutor` siga in-process.
- SSE / WebSockets.
- Cancelación de jobs.
- Publishing.
- generated-image fallback.
- Refactor del pipeline.
- Exponer rutas locales, `--output` CLI o `_final_summary` por HTTP.
- Topología de despliegue productiva definitiva (nginx/Caddy/CDN/containers separados).
