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

### Slice 5B — Environment, integrations and operational references (implementado, corregido, reaprobado y cerrado)

- [x] Actualizar `docs/project/environment.md`: distinguir pipeline CLI canónico / infraestructura n8n·Postgres legacy / render worker; corregir requisitos de `ELEVENLABS_API_KEY`; documentar `SUBTITLE_GLOBAL_OFFSET_MS`; clasificar variables sin consumidor
- [x] Actualizar `docs/project/integrations.md`: estado de providers (Wikimedia+Pixabay activos; Pexels/FreeAI/Pollinations deshabilitados); orquestador canónico `bin/run_job.py`; n8n legacy; edge_tts default; ElevenLabs alternativa opcional
- [x] Actualizar `docs/runbooks/n8n-operations.md`: n8n como infraestructura legacy; workflows `*-v1` identificados como legacy y sin soporte de contratos/providers V2
- [x] Actualizar `AGENTS.md`: identidad genérica y contexto V2-only
- [x] Actualizar `docs/project/vision.md`: producto genérico configurable; historia como caso de uso posible
- [x] Actualizar `openspec/project.md` y `Makefile`: identidad genérica (texto cosmético)
- [x] Actualizar `.env.example`: identidad genérica; `PROJECT_ROOT` → `shorts-creator` (solo plantilla); `POSTGRES_DB` conservado con nota de compatibilidad; documentar `SUBTITLE_GLOBAL_OFFSET_MS` y variables sin consumidor
- [x] Actualizar `.opencode/agents/*.md` (5 agentes): identidad genérica
- [x] Revisar `HANDOVER.md`: preservado intacto (ya marcado como contexto legacy frío)
- [x] Revisar workflows n8n documentados: JSON preservados intactos (legacy, revisión documental)
- [x] Auditoría read-only de Slice 5B (terminó con `CHANGES_REQUIRED`)
- [x] Correcciones derivadas del review (F1–F6)
- [x] Reaprobación read-only focalizada de Slice 5B
- [x] Cierre de Slice 5B
- [x] Commit de cierre de Slice 5B

Reaprobación: SLICE_5B_REAPPROVED_FOR_CLOSURE; cero findings bloqueantes.

Slice 5B cerrado mediante el commit `1d9fe37` (`docs(project): align Slice 5B environment and integrations`).

## Slice 6 — Baseline and closure

### Slice 6A — baseline y corrección focalizada de tests

Estado: la corrección de los 11 tests neutrales (C2), la hermetización de
`test_timing_regression.py` (C5) y la corrección del aislamiento de
`test_fetch_images_v2.py::TestSourceIsolation::test_no_v1_runtime_imports`
(C4) están completas. La suite completa queda verde: baseline limpia
`1102 passed, 0 failed`. La auditoría read-only terminó con
`CHANGES_REQUIRED` exclusivamente documental; las correcciones documentales
F4–F9 están aplicadas; la reaprobación read-only focalizada terminó con
`SLICE_6A_REAPPROVED_FOR_COMMIT`. Slice 6A cerrado mediante el commit `86170d3`
(`test(v2): establish clean Slice 6A baseline`). Slice 6B no iniciado.

- [x] Ejecutar tests focalizados por slice
- [x] Ejecutar suite completa — `1102 passed, 0 failed`
- [x] Clasificar fallos ligados a V1
- [x] Resolver o documentar fallos V1
- [x] Obtener baseline limpia — `1102 passed, 0 failed`
- [ ] Ejecutar E2E V2 canónico
- [x] Actualizar `docs/project/current-state.md` (progreso de 6A; la actualización final de cierre queda en el cierre)
- [x] Actualizar session document (session log 6A; la actualización de cierre queda en el cierre)
- [ ] Cierre formal del change
- [x] Auditoría read-only de Slice 6A — CHANGES_REQUIRED
- [x] Correcciones documentales F4–F9
- [x] Reaprobación read-only focalizada de Slice 6A

Reaprobación: SLICE_6A_REAPPROVED_FOR_COMMIT.
Cero findings bloqueantes.
F1/F2 LOW y F3 NOTE aceptados como no bloqueantes.

- [x] Cierre de Slice 6A
- [x] Commit de Slice 6A

Commit de Slice 6A:
`86170d3` test(v2): establish clean Slice 6A baseline

Pendientes:

- [ ] Ejecutar E2E V2 canónico
- [ ] Cierre formal del change

### Nota sobre la hermetización de `test_timing_regression.py` (6A2)

- Los 4 tests de timing se reescribieron bajo Estrategia A: importan las funciones
  puras de `bin/generate_audio.py` (`build_full_narration`, `_build_canonical_tokens`,
  `_match_words_to_canonical`, `group_words_into_cues`, `_strip_punct`) y usan
  WordBoundary/cues sintéticos deterministas. No se contacta Edge TTS en la suite
  normal. Resultado focalizado: `4 passed`.
- Resultado focalizado combinado (`test_run_job.py` + `test_timing_regression.py` +
  `test_semantic_asset_validation.py`): `103 passed`.

### Corrección de aislamiento de imports (6A3)

- Causa raíz C4: `tests/test_fetch_images_v2.py::TestSourceIsolation::test_no_v1_runtime_imports`
  hacía `sys.modules.pop("run_job", None)` (y otros módulos) sin restauración; el
  `monkeypatch.setattr(sys, "modules", sys.modules)` era un no-op. Por orden
  alfabético, `test_run_job.py` corría después y sus `patch("run_job.*")`
  reimportaban un módulo `run_job` nuevo, distinto del objeto que `main()` usaba
  ya importado. Resultado: `20 failed, 1082 passed` en la suite completa.
- Corrección: las eliminaciones de `sys.modules` se movieron a
  `with monkeypatch.context() as scoped:` usando `scoped.delitem(sys.modules, mod, raising=False)`,
  que registra y restaura el valor original al salir del bloque. Se añadió
  verificación de identidad post-contexto (objeto original restaurado, o ausencia
  conservada).
- Contrato conservado: durante el contexto, el test sigue comprobando que
  `fetch_images_v2.main()` no reimporta los módulos legacy retirados
  (`fetch_images`, `asset_validation`, `editorial_asset_contract`) ni los módulos
  productivos vigentes bloqueados por aislamiento de capas (`generate_script`,
  `prepare_job`, `render_job`, `run_job`). La variable de test continúa llamándose
  `v1_modules`, aunque su nombre es impreciso y no implica que los siete módulos
  sean legacy. Sin debilitar la lista prohibida ni eliminar assertions.
- Ambos órdenes del par contaminante/inverso: `2 passed` cada uno; prueba mínima
  de 4 tests: `4 passed`; archivos `test_fetch_images_v2.py` + `test_run_job.py`
  en ambos órdenes: `130 passed` cada uno.
- Slice 6A cerrado mediante el commit `86170d3`. Slice 6B no iniciado.

### Fallo adicional de suite (Caso B, resuelto en 6A3)

Resultado intermedio histórico de 6A2: suite completa `20 failed, 1082 passed`.
Resuelto en 6A3. C4 ya no está pendiente.

- `test_run_job.py`: `91 passed` en aislamiento.
- Los 20 fallos eran de `test_run_job.py`, preexistentes (reproducibles con
  `--ignore=tests/test_timing_regression.py`).
- Causa C4: `tests/test_fetch_images_v2.py::test_no_v1_runtime_imports` hacía
  `sys.modules.pop("run_job", None)` sin restauración (el `monkeypatch.setattr(sys,
  "modules", sys.modules)` es un no-op). Por orden alfabético, `test_run_job.py`
  corría después y sus `patch("run_job.*")` quedaban rotos.
- Clasificación: C4 — test demasiado acoplado por mutar estado global sin restaurar.
- Corrección (6A3): las eliminaciones de `sys.modules` se movieron a
  `with monkeypatch.context() as scoped:` usando
  `scoped.delitem(sys.modules, mod, raising=False)`.
- Baseline posterior: `1102 passed, 0 failed`. C4 ya no está pendiente.
