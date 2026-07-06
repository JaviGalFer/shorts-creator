---
name: integration-validation
description: Investigar y documentar servicios externos antes de integrarlos
---

# Skill: integration-validation

## Cuándo usarla
Para investigar y documentar un servicio externo antes de integrarlo.

## Entradas
- Nombre del servicio/API.
- URL de documentación.

## Salidas
- Entrada actualizada en `docs/project/integrations.md`.

## Procedimiento
1. Consultar documentación oficial (no blogs, no resúmenes).
2. Identificar: método de autenticación, endpoints, límites, plan gratuito.
3. Registrar estado: VALIDADO, PENDIENTE_DE_VALIDAR, DESCARTADO.
4. Documentar alternativas locales si existen.
5. No realizar llamadas reales a la API sin aprobación.

## Validaciones
- La fuente es la documentación oficial.
- El estado refleja el nivel de certeza real.

## Límites
- No configurar credenciales ni hacer llamadas reales sin permiso explícito.
