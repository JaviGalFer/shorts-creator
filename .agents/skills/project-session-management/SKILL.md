---
name: project-session-management
description: Iniciar y cerrar sesiones, crear bitácoras de trabajo en docs/sessions/
---

# Skill: project-session-management

## Cuándo usarla
Bajo demanda, para iniciar o cerrar una sesión de trabajo.

## Entradas
- Fecha y hora actual.
- Objetivo de la sesión.
- Estado del proyecto al inicio.
- Cambio OpenSpec activo (si aplica).

## Salidas
- Bitácora en `docs/sessions/` si la sesión es relevante.
- Resumen de próximos pasos.

## Procedimiento
1. Al iniciar: usar AGENTS.md y `docs/project/agent-context.md` ya auto-inyectados como contexto base. No releerlos salvo necesidad concreta.
2. Abrir una sesión previa en `docs/sessions/` o un OpenSpec solo cuando la tarea lo requiera.
3. Durante la sesión: mantener enfoque en el objetivo.
4. Al cerrar: crear/actualizar bitácora con estado final, archivos modificados y próximos pasos.

## Validaciones
- La bitácora sigue el formato definido en `docs/sessions/README.md`.
- No crear bitácoras para acciones triviales.

## Límites
- No es un reemplazo de OpenSpec. Las decisiones duraderas van en ADRs.
