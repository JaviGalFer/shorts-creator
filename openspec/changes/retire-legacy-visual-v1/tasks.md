# Tareas: retire-legacy-visual-v1

## Slice 1 — V2-only generation contract

- [x] `generate_script.py`: cambiar default `--visual-schema-version` a `2`
- [x] ~~`generate_script.py`: deprecar `--visual-schema-version 1` con warning + tratar como V2~~ — superseded por Slice 3A: V1 se rechaza mediante argparse con `SystemExit(2)`
- [x] Tests focalizados de generación (V2 only)

## Slice 2 — V2-only asset runtime

- [x] `run_job.py`: validar `request.visuals.schemaVersion` al inicio del pipeline
- [x] `run_job.py`: rechazar metadata V1 pura → `UNSUPPORTED_LEGACY_SCHEMA`
- [x] `run_job.py`: rechazar metadata mixta → `MIXED_VISUAL_PLAN_SCHEMA_VERSIONS`
- [x] `run_job.py`: rechazar metadata visual inválida → `INVALID_VISUAL_SCHEMA`
- [x] `run_job.py`: eliminar bifurcación fetch_images vs fetch_images_v2
- [x] `run_job.py`: invocar siempre `fetch_images_v2.py`
- [x] Tests focalizados de assets (V2 only)
- [x] Tests focalizados de contratos runtime
- [x] Tests focalizados de runner (rechazo V1)
- [x] Actualizar `current-state.md`
- [x] Crear session log

## Slice 3 — Remove V1 generation logic

### Slice 3A — Disable V1 generation runtime (cerrado 2026-07-22)

- [x] `generate_script.py`: `--visual-schema-version` choices restringido a `[2]`; V1 produce `SystemExit(2)`
- [x] `generate_script.py`: `call_llm` default cambiado de `SYSTEM_PROMPT` a `SYSTEM_PROMPT_V2`
- [x] `generate_script.py`: `main()` aplanado a V2-only (sin ramas productivas V1)
- [x] `generate_script.py`: `visuals_request["schemaVersion"]` siempre 2
- [x] `generate_script.py`: `visualSchemaVersion` stdout siempre 2
- [x] Tests de retry migrados a fixtures V2 (`test_generate_script.py`)
- [x] Tests CLI invertidos para rechazo V1 (`test_generate_script_v2.py`, `test_v2_only_generation_contract.py`)
- [x] Tests focalizados: 138 passed, 0 failed

### Slice 3B1 — Eliminar V1 prompts y builders (completado, revisado y cerrado mediante el commit de esta iteración 2026-07-22)

- [x] `generate_script.py`: retirar `SYSTEM_PROMPT` V1
- [x] `generate_script.py`: retirar `_build_duration_prompt_instruction()`
- [x] `generate_script.py`: retirar `_build_retry_instruction()`
- [x] `generate_script.py`: retirar `_build_user_prompt()`
- [x] Conservar `SYSTEM_PROMPT_V2` y funciones `_v2`
- [x] Retirar tests exclusivamente V1 (17 tests: 13 tests de contenido de SYSTEM_PROMPT + 4 tests de builders V1)
- [x] Conservar tests compartidos V1/V2
- [x] Migrar tests neutrales de duración a equivalentes V2 (`test_duration_profiles.py`)
- [x] Eliminar fixture `_GOOD_3_SCENE_SCRIPT` sin callers
- [x] Eliminar `import re` y `PROMPT_PATH` sin uso residual

### Slice 3B2 — Eliminar validator V1 (completado, revisado y cerrado mediante el commit de esta iteración)

- [x] Revisar y trasladar cobertura útil del validator V1
- [x] `generate_script.py`: retirar `_validate_script_structure()`
- [x] Eliminar imports editoriales muertos
- [x] Eliminar fixtures y helpers V1 restantes
- [x] Convertir test compartido a test funcional real
- [x] Mantener `import re`, tres re.sub productivos intactos
- [x] Conservar `editorial_asset_contract.py` para fetch_images hasta Slice 4
- [x] **Conservar runtime, retry y validación V2-only**
- [x] Ejecutar tests focalizados: 132 passed, 0 failed
- [x] Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES`, sin findings bloqueantes.

### Slice 3B3 — Eliminar `--visual-schema-version` CLI (completado, revisado y cerrado mediante el commit de esta iteración)

- [x] `generate_script.py`: retirar `--visual-schema-version` CLI arg (ya no es necesario)
- [x] `run_job.py`: retirar paso de `--visual-schema-version` en `build_script_command`
- [x] Transformar tests del selector (no eliminar)
- [x] Conservar `request.visuals.schemaVersion=2`
- [x] Conservar diagnósticos `visualSchemaVersion=2`
- [x] Tests focalizados: 132 passed, 0 failed
  - test_generate_script_v2.py: 77 passed
  - test_v2_only_generation_contract.py: 7 passed
  - test_run_job.py -k build_script_command: 2 passed
  - test_generate_script.py: 10 passed
  - test_duration_profiles.py: 36 passed
- [x] Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES`, sin findings bloqueantes.

Slice 4 completado: Slice 4A, Slice 4B1 y Slice 4B2 fueron implementados, revisados y cerrados.

## Slice 4 — Remove legacy asset implementation

### Slice 4A — Retirar ramas runtime legacy de assets (completado, revisado y cerrado mediante el commit de esta iteración)

- [x] entrada assets legacy eliminada de STAGE_SCRIPTS
- [x] helpers muertos eliminados (_collect_visual_plan_schema_versions, _uses_v2_visual_assets, _check_mixed_schema_versions)
- [x] `_verify_stage_contract` simplificado a contrato V2-only
- [x] clasificación y rechazo de V1/mixed/invalid conservados
- [x] tests legacy del runner retirados (4 clases, 25 tests)
- [x] compatibilidad V2 de generación transformada
- [x] test assets-ready del runner migrado a assets/
- [x] Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES`, sin findings bloqueantes.
- [x] Tests focalizados: 184 passed, 0 failed
  - `test_run_job_v2_assets.py`: 20 passed
  - cinco clases focalizadas de `test_run_job.py`: 48 passed
  - `test_generate_script_v2.py`: 77 passed
  - `test_fetch_images_v2.py`: 39 passed

### Slice 4B1 — Retirada física del código legacy y migración de cobertura (completado, revisado y cerrado mediante el commit de esta iteración)

- [x] `bin/fetch_images.py` eliminado
- [x] `bin/editorial_asset_contract.py` eliminado
- [x] cero imports productivos o de tests hacia ambos módulos
- [x] `test_semantic_asset_validation.py` reducido de 76 a 8 tests neutrales
- [x] `test_no_topic_specific_contamination.py` reducido de 26 a 4 tests de asset_validation
- [x] `test_generate_script.py` reducido de 10 a 3 tests de retry V2
- [x] comentario stale de `asset_validation.py` corregido
- [x] README actualizado con comando V2 válido
- [x] runbook n8n actualizado sin flags V1 incompatibles
- [x] tests focalizados ejecutados
- [x] Review read-only final: `APPROVE_WITH_NON_BLOCKING_NOTES`, sin findings bloqueantes.
- [x] Tests focalizados finales: 292 passed, 0 failed.

### Slice 4B2 — Limpieza de configuración residual (completado, revisado y cerrado mediante el commit de esta iteración)

- [x] `PEXELS_API_KEY` eliminado de `.env.example`
- [x] passthrough de `PEXELS_API_KEY` eliminado de `docker-compose.yml`
- [x] cero consumidores productivos o workflows n8n de `PEXELS_API_KEY`
- [x] entrada `pexels` conservada como proveedor V2 planificado, disabled y not implemented
- [x] documentación de entorno actualizada para Pixabay y Wikimedia
- [x] FreeAI y Pollinations conservados sin cambios
- [x] Pixabay y Wikimedia conservados como proveedores activos
- [x] tests focalizados ejecutados
- [x] Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES`, sin findings bloqueantes.
- [x] Tests focalizados finales: 313 passed, 0 failed.

## Slice 5 — Product and documentation cleanup

### Slice 5A — Product identity and architecture (completado, revisado, corregido, reaprobado y cerrado mediante el commit de esta sesión)

- [x] README.md: reestructurar con identidad de generador genérico y configurable, personalización como propuesta principal, separación entre capacidades actuales y dirección futura, apertura sin referencia histórica, quick start no histórico, duración no fijada a ~1 min
- [x] `docs/project/architecture.md`: distinguir arquitectura actual de futura; retirar referencias a n8n como orquestador, `bin/fetch_images.py`, Pexels como provider activo, ElevenLabs como TTS canónico; actualizar paths de assets a `assets/`; documentar Visual Plan V2 como canónico
- [x] `docs/architecture/modular-v2-transformation-roadmap.md`: actualizar estado de partida (V1 ya no es runtime ejecutable); reflejar progreso real (Slices 1-4 completados, Slice 5 en ejecución, Slice 6 pendiente)
- [x] `openspec/changes/retire-legacy-visual-v1/tasks.md`: estructurar Slice 5 en 5A y 5B; marcar tareas de implementación 5A como completadas
- [x] `docs/project/current-state.md`: añadir bloque factual de Slice 5A implementado
- [x] `docs/sessions/20260730-214000-retire-legacy-visual-v1-slice-5a.md`: session log de implementación
- [x] Neutralizar identidad histórica residual en textos expuestos y docstrings del runtime sin alterar comportamiento
- [x] Review read-only de Slice 5A
- [x] Correcciones derivadas del review
- [x] Reaprobación read-only focalizada de Slice 5A
- [x] Cierre y commit de Slice 5A

Review formal: CHANGES_REQUIRED por F1 MEDIUM en tabla Markdown del README (fila `LLM_PROVIDER` con tres celdas en tabla de dos columnas); F1 corregido con sustitución de celda única; reaprobación read-only focalizada: APPROVED_FOR_COMMIT; Slice 5A cerrado mediante el commit de esta sesión.

### Slice 5B — Environment, integrations and operational references (pendiente)

- [ ] Actualizar `docs/project/environment.md`: contexto actualizado
- [ ] Actualizar `docs/project/integrations.md`: estado de providers
- [ ] Actualizar `docs/runbooks/n8n-operations.md`: n8n como infraestructura legacy
- [ ] Actualizar `AGENTS.md`: contexto actualizado
- [ ] Revisar `HANDOVER.md`: contexto actualizado
- [ ] Revisar workflows n8n documentados

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
