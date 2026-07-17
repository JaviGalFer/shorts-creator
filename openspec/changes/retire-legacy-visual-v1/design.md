# Diseño: retire-legacy-visual-v1

## Archivos afectados

### Generación de scripts

| Archivo | Cambio |
|---------|--------|
| `bin/generate_script.py` | Retirar `--visual-schema-version` CLI arg, default V1, `SYSTEM_PROMPT` V1, `_build_duration_prompt_instruction()`, `_validate_script_structure()`, `_build_retry_instruction()`, `_build_user_prompt()`. Conservar `SYSTEM_PROMPT_V2`, funciones `_v2` |
| `bin/run_job.py` | Retirar bifurcación de schema version. Siempre usar contrato V2. Detectar metadata V1 y rechazar con `UNSUPPORTED_LEGACY_SCHEMA` |

### Assets

| Archivo | Cambio |
|---------|--------|
| `bin/fetch_images.py` | Retirar del pipeline canónico. No se invoca desde run_job.py |
| `bin/fetch_images_v2.py` | Se mantiene como único asset stage |
| `bin/run_job.py` | Retirar lógica de elección entre fetch_images.py y fetch_images_v2.py |

### Validación

| Archivo | Cambio |
|---------|--------|
| `bin/validate_job.py` | Retirar checks V1-exclusivos. Mantener checks compartidos y V2 |

### Tests

| Archivo | Cambio |
|---------|--------|
| Tests exclusivos V1 | Retirar |
| Tests compartidos V1/V2 | Conservar |
| Tests V2 exclusivos | Conservar |

## Contrato de rechazo V1

```
UNSUPPORTED_LEGACY_SCHEMA
```

Cuando `run_job.py` detecte metadata con:
- `request.visuals.schemaVersion` ausente, o
- `request.visuals.schemaVersion = 1`, o
- `script.scenes[*].visualPlan._schemaVersion` ausente o distinto de 2

El pipeline se detiene con este estado antes de ejecutar ninguna etapa.

## Orden de ejecución por slice

### Slice 1 — V2-only generation contract

1. `generate_script.py`: default `--visual-schema-version` cambia a `2`
2. `generate_script.py`: si se pasa `--visual-schema-version 1`, emitir warning de deprecation y tratar como V2
3. Tests focalizados de generación y runner

### Slice 2 — V2-only asset runtime

1. `run_job.py`: validar `schemaVersion` al inicio; rechazar V1 con `UNSUPPORTED_LEGACY_SCHEMA`
2. `run_job.py`: eliminar bifurcación fetch_images vs fetch_images_v2
3. `run_job.py`: siempre invocar `fetch_images_v2.py`
4. Tests focalizados de assets, contratos runtime y rechazo V1

### Slice 3 — Remove V1 generation logic

1. `generate_script.py`: retirar `SYSTEM_PROMPT` V1, `_build_duration_prompt_instruction()`, `_validate_script_structure()`, `_build_retry_instruction()`, `_build_user_prompt()`
2. `generate_script.py`: retirar `--visual-schema-version` CLI arg (ya no es necesario)
3. Conservar `SYSTEM_PROMPT_V2` y funciones `_v2` como único camino
4. Tests: retirar tests V1 exclusivos, conservar compartidos

### Slice 4 — Remove legacy asset implementation

1. Retirar `fetch_images.py` del runtime (mover a `tools/` o eliminar)
2. Eliminar fixtures y configuración usados únicamente por V1
3. No renombrar todavía módulos con sufijo `_v2`

### Slice 5 — Product and documentation cleanup

1. Actualizar README: producto genérico, no exclusivamente histórico
2. Actualizar AGENTS.md: contexto de producto actualizado
3. Actualizar documentación de arquitectura
4. Mantener historia como caso de uso posible, no como producto

### Slice 6 — Baseline and closure

1. Tests focalizados por slice
2. Suite completa
3. Clasificar fallos ligados a V1 → resolver o documentar
4. Baseline limpia, preferentemente verde
5. E2E V2 canónico antes de cerrar

## Compatibilidad

- `bin/` mantiene compatibilidad temporal como adaptadores
- No se modifica `pyproject.toml` (aún no existe `src/shorts_creator/`)
- No se renombran archivos V2 (sufijo `_v2` se retira en change futuro)
- Jobs V1 existentes en `data/` se conservan sin migración

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Tests V1 compartidos con V2 se rompen al retirar código V1 | Revisar dependencias antes de cada slice |
| Algunos helpers V1 se usan implícitamente por V2 | Búsqueda de dependencias antes de retirar |
| E2E existente depende de V1 | Ejecutar E2E V2 canónico como validación final |
| Metadata V1 en data/ causa falsos positivos | Rechazo explícito con `UNSUPPORTED_LEGACY_SCHEMA` |
