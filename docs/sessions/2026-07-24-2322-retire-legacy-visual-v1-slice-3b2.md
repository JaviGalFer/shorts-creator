# Session: Retire V1 Slice 3B2 — Remove legacy validator

**Date:** 2026-07-24 23:22  
**Change:** `retire-legacy-visual-v1`  
**Scope:** Slice 3B2 — eliminar el validator V1 de generación

## Estado inicial

- HEAD: `5a4e7f2 refactor(script): remove dead V1 prompt code`.
- Working tree limpio al iniciar la implementación.
- `tests/test_generate_script.py` contenía 35 tests.
- 25 tests dependían de `_validate_script_structure`.
- Diez tests debían permanecer.
- `_validate_script_structure` no tenía callers de runtime; sus callers eran exclusivamente tests.
- `generate_script.py` todavía importaba símbolos de `editorial_asset_contract` utilizados únicamente por el validator V1.

## Cambios en `bin/generate_script.py`

Se eliminó completamente:

- `_validate_script_structure`.
- `is_asset_type_allowed`.
- `is_temporal_intent_allowed`.
- `allowed_asset_types_for_role`.
- El import de módulo `editorial_asset_contract`.

Se conservaron sin cambios:

- `SYSTEM_PROMPT_V2`.
- `_validate_and_canonicalize_script_v2`.
- El retry V2.
- El contrato CLI V2-only.
- `import re`.
- Los dos `re.sub` de `call_llm`.
- El `re.sub` de `generate_job_id`.

Después de Slice 3B2, `generate_script.py` ya no consume `editorial_asset_contract`.

## Cambios en `tests/test_generate_script.py`

Se eliminaron 25 tests dependientes del validator V1 y los helpers:

- `_build_scene_script`.
- `_seg_script`.

El test:

- `test_shared_contract_used_by_fetch_and_generate`

se transformó en:

- `test_fetch_images_imports_editorial_contract`.

El test resultante comprueba únicamente el contrato temporal entre `fetch_images.py` y `editorial_asset_contract.py`.

## Diez tests preservados

### Generación y retry V2

- `test_max_script_attempts_is_three`
- `test_main_retry_loop_3_attempts_3rd_succeeds`
- `test_main_retry_loop_3_attempts_all_fail_review_required`

### Integración y contrato temporal de `fetch_images.py`

- `test_fetch_images_imports_editorial_contract`
- `test_validate_segment_for_role_uses_shared_helper`
- `test_fetch_images_no_duplicate_atmospheric_discard`

### Contrato directo de `editorial_asset_contract.py`

- `test_unknown_role_fails_closed`
- `test_unknown_asset_type_fails_closed`
- `test_aliases_map_or_document_accepted_for_context_map`
- `test_aliases_historical_map_or_document_accepted`

Los tests de `fetch_images.py` y `editorial_asset_contract.py` permanecen temporalmente hasta Slice 4.

## Cobertura tras la eliminación

- Las reglas neutrales de estructura continúan cubiertas por `_validate_and_canonicalize_script_v2` y `tests/test_generate_script_v2.py`.
- La validación histórica V1 se eliminó sin migración.
- Las reglas V1 de `editorialRole`, `visualTemporalIntent`, `primaryAssetType`, `secondaryAssetType` y `assetType` se eliminaron de `generate_script.py` sin migración.
- Las reglas V1 de número de segmentos según duración se eliminaron sin migración.
- `editorial_asset_contract.py` continúa utilizado por `fetch_images.py`; `fetch_images_v2.py` no lo consume.
- La retirada física de `fetch_images.py` y del contrato editorial legacy permanece aplazada a Slice 4.

## Tests focalizados

- `tests/test_generate_script.py`: 10 passed.
- `tests/test_generate_script_v2.py`: 77 passed.
- `tests/test_duration_profiles.py`: 36 passed.
- `tests/test_v2_only_generation_contract.py`: 7 passed.
- `tests/test_run_job.py -k build_script_command`: 2 passed, 89 deselected.

**Total:** 132 passed, 0 failed.

Los tests no realizaron llamadas reales al LLM ni utilizaron red, Docker, FFmpeg o assets reales.

## Comprobaciones negativas

Se confirmó:

- `_validate_script_structure` ausente de `bin/` y `tests/`.
- Imports editoriales ausentes de `generate_script.py`.
- `_build_scene_script` y `_seg_script` ausentes de `tests/test_generate_script.py`.
- `import re` presente en `generate_script.py`.
- Exactamente tres `re.sub` productivos presentes.
- Exactamente diez tests presentes en `tests/test_generate_script.py`.
- Sin cambios en `run_job.py`.
- Sin cambios en `editorial_asset_contract.py`.
- Sin cambios en `fetch_images.py`.
- Sin cambios en `fetch_images_v2.py`.
- Sin cambios en `visual_asset_bridge_v2.py`.

## Reindexado

Se ejecutó:

`/home/javi/.local/bin/codebase-memory-mcp cli index_repository --repo-path "/home/javi/projects/shorts-creator" --mode fast --persistence false`

Reindexado completado; la entrega original no conservó los totales exactos de nodos y aristas.

## Documentación

- `tasks.md`: Slice 3B2 marcado como implementado pendiente de review.
- `current-state.md`: Slice 3B1 reconciliado como cerrado mediante `5a4e7f2`.
- `current-state.md`: Slice 3B2 añadido como implementado pendiente de review y commit.
- Slice 3B3 continúa pendiente.
- Slice 4 continúa pendiente.
- Slice 3 no se considera cerrado porque Slice 3B3 sigue pendiente.

## Archivos del slice

1. `bin/generate_script.py`
2. `tests/test_generate_script.py`
3. `openspec/changes/retire-legacy-visual-v1/tasks.md`
4. `docs/project/current-state.md`
5. `docs/sessions/2026-07-24-2322-retire-legacy-visual-v1-slice-3b2.md`

## Riesgos

- No se detectaron riesgos funcionales en los tests focalizados.
- La retirada física de `fetch_images.py` y `editorial_asset_contract.py` permanece aplazada a Slice 4.
- Slice 3B2 continúa pendiente de review read-only y commit.

## Estado Git

- Ningún commit creado.
- Ningún push realizado.

## Review y cierre

- Verdict: `APPROVE_WITH_NON_BLOCKING_NOTES`.
- Cero findings bloqueantes.
- Review confirmó que no se eliminó código productivo V2.
- Review confirmó exactamente diez tests preservados.
- Review confirmó cobertura V2 equivalente para reglas neutrales.
- Review confirmó que `editorial_asset_contract.py` solo permanece por `fetch_images.py` hasta Slice 4.
- Nota cosmética de líneas vacías corregida.
- Newline final de tests/test_generate_script.py corregido.
- Comentario stale de fetch_images.py aplazado a Slice 4.
- Tests focalizados finales: 132 passed, 0 failed.
- Commit previsto: `refactor(script): remove legacy V1 validator`.
- Ningún push.
- Siguiente acción: Slice 3B3 — retirar `--visual-schema-version` del CLI.

## Siguiente acción

Slice 3B3 — retirar `--visual-schema-version` del CLI.
