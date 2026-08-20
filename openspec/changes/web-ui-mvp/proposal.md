# Propuesta: web-ui-mvp

**Clasificación AGENTS.md: Level 2** — cambio de arquitectura (nuevo componente,
integración Web + entidad de ejecución de job), requiere OpenSpec y sesión de cierre.

> **Historial de regularización (importante):** el cambio `web-ui-mvp` es un cambio
> **significativo** y debía tener su OpenSpec desde el inicio. Se regularizó su OpenSpec
> **después** de la implementación de Slice 1 y **antes** del Review formal de Slice 1,
> sobre la base del Plan arquitectónico previamente aprobado. Estos archivos NO preceden
> a la implementación de Slice 1.

**Estado general: IN PROGRESS — Slice 1 implementado, pending formal Review.**
Slice 2/3/4 pendientes.

## Problema

`shorts-creator` tiene un pipeline canónico Python maduro
(`script → assets → audio → prepare → render → validate`), orquestado por
`src/shorts_creator/pipeline/orchestrator.py::run_pipeline(...)`, expuesto hoy solo por CLI
(`bin/run_job.py`). No existe una aplicación web utilizable.

El objetivo es exponer el producto existente a través de una pequeña Web UI escalable,
**sin duplicar lógica de pipeline** y sin romper la CLI.

## Target MVP

- Topic
- Duration
- TTS provider
- Voice
- Visual mode:

  - AUTO
  - MIXED
  - IMAGES_ONLY
  - VIDEOS_ONLY
- Asset providers
- Generate
- progreso por stage:

  - script
  - assets
  - audio
  - prepare
  - render
  - validate
- estado canónico de job
- `ASSETS_PARTIAL` comprensible
- `REVIEW_REQUIRED` comprensible
- fallos comprensibles
- preview MP4
- descarga MP4

## Límite de reutilización

```text
CLI ─────┐
         ├──> run_pipeline()   (runner canónico reutilizable)
Web ─────┘
```

El backend Web invoca el **mismo** `run_pipeline` en proceso. Nunca ejecuta
`bin/run_job.py` como API interna.

## Exclusions explícitas

- generated-image fallback
- engagement configurable
- publishing (publicación automática)
- producto de autenticación/login
- pagos
- multi-tenancy SaaS
- base de datos
- Redis/Celery
- Kubernetes
- orquestación n8n
- microservicios innecesarios
- SSE/WebSockets para MVP
- cancelación para MVP
- gran refactor de pipeline

## Fuera de alcance invariante

No reabrir trabajo cerrado: `script-watchability-v1`, `auto-mixed-visual-runtime`,
comportamiento AUTO/MIXED, generated-image fallback, engagement configurable.
No refactor del comportamiento de `script/assets/audio/rendering/validation`.
