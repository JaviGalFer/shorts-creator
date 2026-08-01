# OpenSpec — Shorts Creator

## ¿Qué es OpenSpec?

Sistema de especificación de cambios basado en archivos. Cada cambio significativo se documenta como un "cambio OpenSpec" en `openspec/changes/<nombre-del-cambio>/`.

## Estructura

```
openspec/
  project.md                          <- Este archivo (descripción del proyecto)
  changes/
    <nombre-del-cambio>/
      proposal.md                     <- Qué se quiere hacer y por qué
      design.md                       <- Cómo se va a hacer
      tasks.md                        <- Tareas verificables
      specs/
        <especificacion>.md           <- Requisitos verificables detallados
```

## Ciclo de vida de un cambio

1. **Propuesta** — Se crea `proposal.md` describiendo el problema y alcance.
2. **Diseño** — Se crea `design.md` con la solución técnica.
3. **Especificación** — Se detallan requisitos en `specs/`.
4. **Tareas** — Se crea `tasks.md` con ítems verificables.
5. **Implementación** — Se ejecutan las tareas una a una.
6. **Cierre** — Tasks marcadas, resultado documentado, decisión sobre si crear ADR.
