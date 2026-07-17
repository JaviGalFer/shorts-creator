# Tareas: retire-legacy-visual-v1

## Slice 1 — V2-only generation contract

- [x] `generate_script.py`: cambiar default `--visual-schema-version` a `2`
- [ ] `generate_script.py`: deprecar `--visual-schema-version 1` con warning + tratar como V2
- [x] Tests focalizados de generación (V2 only)

## Slice 2 — V2-only asset runtime

- [ ] `run_job.py`: validar `request.visuals.schemaVersion` al inicio del pipeline
- [ ] `run_job.py`: rechazar metadata sin schemaVersion o con schemaVersion=1 → `UNSUPPORTED_LEGACY_SCHEMA`
- [ ] `run_job.py`: eliminar bifurcación fetch_images vs fetch_images_v2
- [ ] `run_job.py`: invocar siempre `fetch_images_v2.py`
- [ ] Tests focalizados de assets (V2 only)
- [ ] Tests focalizados de contratos runtime
- [ ] Tests focalizados de runner (rechazo V1)

## Slice 3 — Remove V1 generation logic

- [ ] `generate_script.py`: retirar `SYSTEM_PROMPT` V1
- [ ] `generate_script.py`: retirar `_build_duration_prompt_instruction()`
- [ ] `generate_script.py`: retirar `_validate_script_structure()`
- [ ] `generate_script.py`: retirar `_build_retry_instruction()`
- [ ] `generate_script.py`: retirar `_build_user_prompt()`
- [ ] `generate_script.py`: retirar `--visual-schema-version` CLI arg
- [ ] Conservar `SYSTEM_PROMPT_V2` y funciones `_v2`
- [ ] Retirar tests exclusivamente V1
- [ ] Conservar tests compartidos V1/V2

## Slice 4 — Remove legacy asset implementation

- [ ] Retirar `fetch_images.py` del runtime (mover a `tools/` o eliminar)
- [ ] Eliminar fixtures V1
- [ ] Eliminar configuración usada únicamente por V1
- [ ] No renombrar módulos `_v2` todavía

## Slice 5 — Product and documentation cleanup

- [ ] Actualizar README.md: producto genérico
- [ ] Actualizar AGENTS.md: contexto actualizado
- [ ] Actualizar documentación de arquitectura
- [ ] Mantener historia como caso de uso posible

## Slice 6 — Baseline and closure

- [ ] Ejecutar tests focalizados por slice
- [ ] Ejecutar suite completa
- [ ] Clasificar fallos ligados a V1
- [ ] Resolver o documentar fallos V1
- [ ] Obtener baseline limpia
- [ ] Ejecutar E2E V2 canónico
- [ ] Actualizar `docs/project/current-state.md`
- [ ] Actualizar session document
- [ ] Cierre formal del change
