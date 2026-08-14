# Proposal: retire-legacy-visual-v1

## Problem

El runtime conserva VisualPlan V1, defaults históricos y ramas de código que:

- Duplican contratos (V1 y V2 conviven en generate_script, run_job, fetch_images)
- Permiten crear jobs nuevos con el contrato antiguo por defecto
- Aumentan la superficie de ramificación y tests
- Incrementan el contexto requerido por agentes al operar sobre el repositorio
- Vinculan el producto al caso de uso exclusivamente histórico, contradiciendo el objetivo genérico

VisualPlan V1 se introdujo como iteración inicial del pipeline visual. V2 lo reemplaza con un contrato más robusto, neutral y extensible. Sin embargo, V1 sigue activo como default y no se ha retirado.

## Solution

Dejar VisualPlan V2 como **único contrato visual soportado** para nuevos jobs.

El cambio se implementa en 6 slices atómicos:

1. **V2-only generation contract** — nuevos jobs siempre V2, retirar default V1
2. **V2-only asset runtime** — fetch_images_v2 como único asset stage, rechazo de metadata V1
3. **Remove V1 generation logic** — retirar prompts, validadores y ramas exclusivas V1
4. **Remove legacy asset implementation** — retirar fetch_images.py del runtime
5. **Product and documentation cleanup** — eliminar lenguaje exclusivamente histórico
6. **Baseline and closure** — tests focalizados, suite completa, E2E V2 canónico

## Success Criteria

- [x] `generate_script.py` no acepta `--visual-schema-version 1` ni lo usa por defecto
- [x] `run_job.py` no bifurca entre fetch_images.py y fetch_images_v2.py
- [x] `fetch_images.py` no se invoca desde el pipeline canónico
- [x] Metadata V1 existente se rechaza con error explícito `UNSUPPORTED_LEGACY_SCHEMA`
- [x] Tests V1 exclusivos se retiran; tests compartidos se conservan
- [x] Documentación refleja producto genérico, no exclusivamente histórico
- [x] Baseline de tests limpia (sin regresiones nuevas) — `1181 passed, 0 failed`
- [x] E2E V2 canónico pasa completamente — **DEFERRED/WAIVED** (ver nota)

### Nota sobre el criterio full-E2E

El criterio «E2E V2 canónico pasa completamente» se registra como **DEFERRED/WAIVED**
para el cierre de este change. El quinto E2E V2 canónico (job `cmo-2026-08-14-153529`)
validó **script V2 PASS** (`55 → 52` palabras, `durationContract.status=PASS`,
`structureValid=true`) y **assets V2 completos** (10/10), pero el pipeline quedó
bloqueado posteriormente en `audio` por `AUDIO_DURATION_MISSING` (duración de los
5 mp3 no medida durante el run). Dicho bloqueo es un problema de la etapa de audio,
fuera del scope de retirada de Visual V1. La retirada de V1 ha quedado validada por
los contratos de `script` y `assets`; el bloqueo de audio se pospone como trabajo
independiente.

## Scope

### In scope

- Retirar defaults V1 en generate_script.py
- Retirar bifurcación V1/V2 en run_job.py
- Retirar fetch_images.py del pipeline canónico
- Retirar prompts, validadores y helpers exclusivos V1
- Rechazo explícito de metadata con `visualSchemaVersion=1` o sin schemaVersion
- Actualizar documentación (README, AGENTS.md, architecture docs)
- Tests focalizados por slice + suite completa al cierre

### Out of scope

- Creación de `src/shorts_creator/` (change separado)
- Modularización de audio, render o validation
- Mejora de pacing (pausado en improve-short-form-audio-pacing-v2)
- Cambio de voz, música, n8n, interfaz web, nuevos providers
- Mejora de relevancia visual
- Renombrado general de módulos `_v2`
- Migración automática de metadata V1
- Reescritura desde cero

## Policy for existing V1 jobs

- Los artefactos existentes se conservan en `data/`
- No se migran automáticamente
- No pueden re-ejecutarse por el pipeline canónico
- Se rechazan con estado o error equivalente a `UNSUPPORTED_LEGACY_SCHEMA`
- El identificador final del error se verificará contra convenciones actuales antes de implementarlo

## Notes

Este cambio es **exclusivamente de retirada y limpieza**. No introduce nuevas funcionalidades ni modifica el comportamiento de V2. El resultado es un pipeline más simple, más rápido de entender y más fácil de mantener.
