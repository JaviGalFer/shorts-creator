# Sesión: Implement retire V1 Slice 4A runtime assets

- Fecha: 2026-07-25
- Objetivo: Retirar ramas runtime legacy de assets del runner (Slice 4A)
- Estado inicial: HEAD b09c082, working tree limpio (slot conocido: permisos en data/postgres/)
- Estado final: cambios implementados, revisados y cerrados mediante commit; fetch_images.py y editorial_asset_contract.py intactos
- Agente responsable: opencode/deepseek-v4-flash-free (default), modo Build
- Cambio OpenSpec relacionado: retire-legacy-visual-v1 (Slice 4A)
- Codebase Memory MCP: DESACTIVADO — sin llamadas MCP, sin reindexado
- Riesgo asumido: Ninguno — pipeline canónico ya usaba fetch_images_v2.py; solo se retira código muerto

## Validaciones realizadas

### Preflight AST
- test_run_job_v2_assets.py inicial: 45 tests
- TestUsesV2VisualAssets: 6 tests
- TestCollectVisualPlanSchemaVersions: 5 tests
- TestCheckMixedSchemaVersions: 8 tests
- TestV1AssetsContractUnchanged: 6 tests
- Tests a eliminar: 25
- Tests esperados finales: 20

### Símbolos productivos eliminados
- `_collect_visual_plan_schema_versions` (run_job.py)
- `_uses_v2_visual_assets` (run_job.py)
- `_check_mixed_schema_versions` (run_job.py)
- `"assets": "fetch_images.py"` de STAGE_SCRIPTS

### Símbolos de rechazo V1 conservados
- `V1_POSITIVE_FIELDS`
- `_classify_visual_schema`
- `_schema_error_for_category`

### STAGE_SCRIPTS actualizado
- Solo: audio, prepare, render, validate (assets eliminado)
- `build_stage_command("assets")` sigue devolviendo fetch_images_v2.py

### _verify_stage_contract simplificado
- assets: V2-only (assets/, V2_IMAGE_EXTENSIONS)
- ASSETS_READY + imágenes → éxito
- ASSET_UNRESOLVED, ASSETS_PARTIAL, REVIEW_REQUIRED → graceful block (error None)
- Unknown status → contract error

### Clases de tests eliminadas
- `TestUsesV2VisualAssets`
- `TestCollectVisualPlanSchemaVersions`
- `TestCheckMixedSchemaVersions`
- `TestV1AssetsContractUnchanged`

### Tests transformados
- `test_generate_script_v2.py::test_run_job_modules_unchanged`: ahora usa `_classify_visual_schema` + `build_stage_command` (77 tests)
- `test_run_job.py::test_assets_ready_with_images_passes`: migrado a assets/ + schemaVersion=2
- `test_run_job.py::test_assets_partial_fails_contract` → `test_assets_partial_graceful_block`: adaptado a V2 graceful block

### AST final
- test_run_job_v2_assets.py: 20 tests (45 - 25)
- test_generate_script_v2.py: 77 tests
- test_run_job.py: 91 tests

### Postcondition grep
- zero `_collect_visual_plan_schema_versions` en bin/ tests/
- zero `_uses_v2_visual_assets` en bin/ tests/
- zero `_check_mixed_schema_versions` en bin/ tests/
- zero `"assets": "fetch_images.py"` en bin/ tests/
- zero `fetch_images.py` en bin/run_job.py tests/test_run_job_v2_assets.py

### Tests focalizados
- test_run_job_v2_assets.py: 20 passed, 0 failed
- test_run_job.py (5 clases: TestVerifyStageContract, TestBuildStageCommandDispatch, TestClassifyVisualSchema, TestSchemaErrorForCategory, TestMainSchemaRejection): 48 passed, 0 failed
- test_generate_script_v2.py: 77 passed, 0 failed
- test_fetch_images_v2.py: 39 passed, 0 failed
- Total: 184 passed, 0 failed

## Archivos modificados
- bin/run_job.py
- tests/test_run_job_v2_assets.py
- tests/test_generate_script_v2.py
- tests/test_run_job.py
- openspec/changes/retire-legacy-visual-v1/tasks.md
- docs/project/current-state.md
- docs/sessions/20260725-163459-retire-legacy-visual-v1-slice-4a.md (nuevo)

## Archivos NO modificados
- bin/fetch_images.py (intacto para Slice 4B)
- bin/editorial_asset_contract.py (intacto para Slice 4B)
- bin/fetch_images_v2.py
- tests/test_semantic_asset_validation.py
- tests/test_no_topic_specific_contamination.py
- tests/test_generate_script.py
- .env.example, docker-compose.yml, README.md, docs/runbooks/
- assets/, audio/, rendering/, src/, pyproject.toml

## Comandos ejecutados
- Preflight AST
- git grep de referencias
- python3 -m pytest tests/test_run_job_v2_assets.py -q → 20 passed
- Resultado inicial previo a la corrección:
  python3 -m pytest {5 clases focalizadas test_run_job.py} -q → 47 passed, 1 failed
- python3 -m pytest tests/test_generate_script_v2.py -q → 77 passed
- python3 -m pytest tests/test_fetch_images_v2.py -q → 39 passed

## Resultado
Slice 4A implementado. Ramas runtime legacy de assets eliminadas del runner. `fetch_images.py` y `editorial_asset_contract.py` intactos. Clasificación y rechazo de V1/mixed/invalid conservados.

## Próximos pasos
- Slice 4B — retirada física del stack legacy de assets

## Corrección posterior a implementación

- `test_v2_metadata_reaches_assets` no representaba correctamente el ciclo de lecturas del runner.
- El test reutilizaba un diccionario mutable y proporcionaba tres lecturas en lugar de cuatro.
- Se corrigió usando instancias independientes:
  - SCRIPT_DRAFT tras script;
  - SCRIPT_DRAFT antes de assets;
  - ASSETS_READY tras assets;
  - ASSETS_READY para resumen final.
- El test individual pasa.
- Cinco clases focalizadas de test_run_job.py: 48 passed, 0 failed.
- Imports muertos de test_run_job_v2_assets.py eliminados.
- Mensaje diagnóstico de statuses de assets corregido para incluir REVIEW_REQUIRED.
- Resultado focalizado final: 184 passed, 0 failed.
- Ningún commit.
- Ningún push.
- Ninguna llamada MCP.
- Ningún reindexado.
- Siguiente acción única: review read-only de Slice 4A.

## Archivos modificados (corrección)
- bin/run_job.py
- tests/test_run_job_v2_assets.py
- tests/test_run_job.py
- openspec/changes/retire-legacy-visual-v1/tasks.md
- docs/project/current-state.md
- docs/sessions/20260725-163459-retire-legacy-visual-v1-slice-4a.md (esta sección)

## Review y cierre

- Verdict: `APPROVE_WITH_NON_BLOCKING_NOTES`.
- Cero findings bloqueantes.
- Review confirmó la eliminación de:
  - `_collect_visual_plan_schema_versions`;
  - `_uses_v2_visual_assets`;
  - `_check_mixed_schema_versions`;
  - `STAGE_SCRIPTS["assets"]`.
- Review confirmó que `build_stage_command("assets")` usa `fetch_images_v2.py`.
- Review confirmó contrato de assets V2-only mediante `assets/`.
- Review confirmó rechazo de metadata V1, mixed e invalid.
- Review confirmó 25 tests legacy eliminados.
- Review confirmó 20 tests en test_run_job_v2_assets.py.
- Review confirmó 77 tests en test_generate_script_v2.py.
- Review confirmó 91 tests en test_run_job.py.
- Review confirmó 184 passed, 0 failed.
- Formato Markdown de tasks.md corregido.
- Espaciado cosmético de test_run_job_v2_assets.py corregido.
- `fetch_images.py` permanece intacto para Slice 4B.
- `editorial_asset_contract.py` permanece intacto para Slice 4B.
- Commit previsto:
  `refactor(assets): remove legacy runner branches`
- Ningún push.
- Próxima acción:
  Slice 4B — retirada física del stack legacy de assets.
