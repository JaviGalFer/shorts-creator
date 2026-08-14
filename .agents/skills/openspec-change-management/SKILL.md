---
name: openspec-change-management
description: Crear, revisar y cerrar cambios OpenSpec en openspec/changes/
---

# Skill: openspec-change-management

## Cuándo usarla
Para crear, revisar o cerrar un cambio OpenSpec.

## Entradas
- Tipo de acción: crear | revisar | cerrar.
- Nombre del cambio.
- Contexto (problema, objetivo).

## Salidas
- Archivos en `openspec/changes/<nombre>/`:
  - proposal.md
  - design.md
  - tasks.md
  - specs/ (opcional)

## Procedimiento
1. **Crear**: Escribir proposal describiendo problema y alcance. Luego diseño y tareas.
2. **Revisar**: Verificar que proposal alcance y fuera de alcance están claros. Diseño es técnicamente viable. Tasks son verificables.
3. **Cerrar**: Marcar tasks como completadas. Documentar resultado. Decidir si se necesita ADR.

## Validaciones
- Proposal tiene criterios de éxito medibles.
- Tasks son atómicas y verificables.
- No marcar completado sin validación.

## Lifecycle Git
- Iniciar un change desde `main` estable.
- Trabajar en rama dedicada `change/<slug>`.
- Validar (tests, review) antes del cierre.
- Merge a `main` solo al cerrar el change.
- No asumir que puede crear/mergear ramas: la tarea debe autorizarlo explícitamente.

## Límites
- No usar para cambios triviales (typos, refactors menores).
- ADRs son para decisiones duraderas, no para cada cambio.
