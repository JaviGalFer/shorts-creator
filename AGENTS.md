# AGENTS.md — Shorts Históricos

Reglas de trabajo para agentes que operan sobre este repositorio.

## Contexto inicial

- AGENTS.md se aplica automáticamente como regla de proyecto.
- `docs/project/current-state.md` es la única fuente de contexto operativo caliente.
- Leer un OpenSpec concreto solo cuando current-state.md indique explícitamente un cambio activo y la tarea esté relacionada.
- No cargar `docs/sessions/`, `openspec/changes/` ni skills por defecto al iniciar.

## Exploración

- Prohibida la exploración masiva del repositorio.
- Leer solo archivos necesarios para la tarea.
- Prohibido inspeccionar `data/`, `logs/`, renders, assets generados, audio, vídeo, imágenes o metadata de jobs salvo necesidad directa.
- No ejecutar el pipeline completo salvo petición explícita.

## Niveles de cambio

| Nivel | Ámbito | OpenSpec | Sesión |
|-------|--------|----------|--------|
| 0 | Corrección local o documental pequeña | No | No |
| 1 | Cambio acotado dentro de una parte existente | No requerido | Opcional si deja decisión útil |
| 2 | Arquitectura, contratos entre etapas, persistencia, integración externa, formato de datos, cambio entre componentes | Requerido | Requerida (cierre) |

## Trazabilidad

- Solo cambios Nivel 2 requieren OpenSpec y sesión obligatorios.
- Las sesiones son historial frío. No crear sesiones por cada cambio pequeño.
- OpenSpec no se usa para microcambios.

## Skills y agentes

- Skills solo bajo demanda. No cargar skills al iniciar.
- Agentes especializados solo se invocan cuando su dominio es directamente relevante.
- No lanzar subagentes para tareas pequeñas.

### Agentes disponibles

| Agente | Rol |
|--------|-----|
| `@project-architect` | Arquitectura, ADRs, documentación técnica |
| `@n8n-workflow-engineer` | Diseño y validación de workflows n8n |
| `@video-pipeline-engineer` | Pipeline FFmpeg, formatos, assets |
| `@integration-researcher` | Investigación de APIs y servicios externos |
| `@quality-and-ops-reviewer` | Revisión de estructura, secretos y trazabilidad |

### Skills disponibles

| Skill | Propósito |
|-------|-----------|
| `project-session-management` | Iniciar/cerrar sesiones, crear bitácoras |
| `openspec-change-management` | Crear, revisar y cerrar cambios OpenSpec |
| `integration-validation` | Investigar servicios externos y registrar evidencia |
| `n8n-workflow-design` | Diseñar workflows n8n robustos |
| `video-rendering-ffmpeg` | Diseñar renders verticales con FFmpeg |
| `media-rights-and-safety` | Verificar licencias y atribuciones |
| `secrets-and-environment` | Gestionar .env, secretos y configuración |

## Enlaces

- Contexto operativo: `docs/project/current-state.md`
- Contexto legacy: `HANDOVER.md`
- Arquitectura: `docs/project/architecture.md`
- Integraciones: `docs/project/integrations.md`
- Cambio activo si aplica: indicado en `current-state.md`
