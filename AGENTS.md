# AGENTS.md — Shorts Históricos

## Objetivo

Este archivo define las reglas de trabajo para cualquier agente (IA o humano asistido) que opere sobre este repositorio. El proyecto genera vídeos cortos verticales (Shorts/TikTok/Reels) de temática histórica de forma automatizada mediante n8n, APIs externas y render local con FFmpeg.

## Arranque de sesión

1. Cargar este `AGENTS.md`.
2. Cargar la skill `project-session-management`.
3. Revisar `docs/sessions/` para contexto de sesiones previas.
4. Revisar `openspec/changes/` para cambios activos.
5. Si hay un cambio OpenSpec activo, cargarlo como contexto principal.
6. Si no hay bitácora de la fecha, crearla al finalizar la sesión.

## Principios no negociables

1. Ningún secreto se escribe en archivos versionados.
2. Todo cambio relevante pasa por OpenSpec + bitácora.
3. No implementar sin diseño previo documentado.
4. No marcar tareas como completadas sin validación.
5. No automatizar publicación sin revisión humana.
6. Preferir herramientas locales cuando sea viable.
7. Mantener trazabilidad completa (specs, tasks, summary, decisions).
8. No asumir que una integración funciona sin validarla.
9. Verificar licencias de recursos visuales antes de incluirlos.
10. No usar scraping que incumpla términos de servicio.
11. No escribir NUNCA valores reales de API keys, tokens o contraseñas en documentación, bitácoras, handovers, OpenSpec, logs ni metadatos. Usar `***` en su lugar.
12. Si se detecta un secreto en un archivo versionado, reportarlo inmediatamente y no comitearlo.

## Flujo obligatorio de cambio

1. Revisar contexto existente (bitácoras, cambios OpenSpec, ADRs).
2. Crear o actualizar una bitácora en `docs/sessions/`.
3. Crear o actualizar un cambio OpenSpec en `openspec/changes/`.
4. Diseñar antes de implementar.
5. Implementar de forma incremental.
6. Ejecutar validaciones.
7. Documentar resultado real.
8. Actualizar tareas.
9. Crear ADR solo si existe una decisión duradera.
10. No ocultar bloqueos ni suponer éxito.

## Skills disponibles

Ver `.opencode/skills/` para skills específicas del proyecto.

| Skill | Propósito |
|-------|-----------|
| `project-session-management` | Iniciar/cerrar sesiones, crear bitácoras |
| `openspec-change-management` | Crear, revisar y cerrar cambios OpenSpec |
| `integration-validation` | Investigar servicios externos y registrar evidencia |
| `n8n-workflow-design` | Diseñar workflows n8n robustos |
| `video-rendering-ffmpeg` | Diseñar renders verticales con FFmpeg |
| `media-rights-and-safety` | Verificar licencias y atribuciones |
| `secrets-and-environment` | Gestionar .env, secretos y configuración |

## Agentes del proyecto

Ver `.opencode/agents/` para agentes especializados.

| Agente | Rol |
|--------|-----|
| `@project-architect` | Arquitectura, ADRs, documentación técnica |
| `@n8n-workflow-engineer` | Diseño y validación de workflows n8n |
| `@video-pipeline-engineer` | Pipeline FFmpeg, formatos, assets |
| `@integration-researcher` | Investigación de APIs y servicios externos |
| `@quality-and-ops-reviewer` | Revisión de estructura, secretos y trazabilidad |

## Modelo de datos

Ver `docs/project/architecture.md` para el JSON canónico de "video job" y máquina de estados.

## Enlaces rápidos

- Visión del proyecto: `docs/project/vision.md`
- Arquitectura: `docs/project/architecture.md`
- Roadmap: `docs/project/roadmap.md`
- Integraciones: `docs/project/integrations.md`
- Entorno: `docs/project/environment.md`
- Cambio activo: `openspec/changes/improve-historical-visual-pipeline/`
- Estrategia visual: `docs/project/visual-asset-strategy.md`
- Seguridad: `docs/project/security.md`
