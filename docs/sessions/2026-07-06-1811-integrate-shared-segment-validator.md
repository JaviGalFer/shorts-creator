# Sesión: Integración del validador compartido de segmentos

- Fecha: 2026-07-06
- Objetivo: Verificar y consolidar el validador compartido `_validate_segment_for_role` en los tres caminos de producción (normal, fallback, reuse) y activar `_try_hard_role_fallback` en `main()`.
- Cambio OpenSpec: `improve-historical-visual-pipeline` (Phase 23 consolidation)
- Naturaleza: consolidación de código/tests — no verificación real del runner.

## Hallazgos pre-cambio

### `_validate_segment_for_role` — call sites

- Definida en `bin/fetch_images.py:2051`.
- **Cero call sites en producción** antes del cambio. Solo invocada desde tests.
- `main()` tenía validación manual de tipos prohibidos (líneas 2420-2440 originales) sin pasar por el validador compartido.

### `_try_hard_role_fallback` — call sites

- Definida en `bin/fetch_images.py:1837`.
- **Cero call sites en producción** antes del cambio. Solo invocada desde tests.
- `main()` marcaba `ASSET_UNRESOLVED` directamente sin intentar fallback (línea 2453 original).

### `segment_results`

- Ya implementado correctamente con `all(segment_results)` en `main():2479`.
- `selected = all(segment_results)` ya funcionaba. No requería cambios.

### `editorialRole` / `sourceEditorialRole`

- Ya persistidos en `asset_meta` para scena con `visual_sequence` (líneas 2511-2512).
- No persistidos consistentemente en el path legacy (sin visualSequence).

## Cambios realizados

### 1. `_validate_segment_for_role` expandido y hecho autoritativo

- Añadidas todas las hard rules que antes solo existían inline en `_fetch_one_asset`:
  - `context_map`: tipo efectivo, role evidence, temporal match
  - `document_or_date`: tipo efectivo, evidencia mínima
  - `consequence_or_legacy` + `event_depiction`: depicted-date overlap / fall-opening evidence
  - `battle_or_assault` / `military_technology` / `border_closure_construction`: evidencia de construcción
  - `border_closure_construction`: indicadores de rechazo (familia/checkpoint/conmemoración)
  - Renderability
  - Semantic confidence floor para hard historical roles
- Parámetro adicional: `visual_plan` para acceder a `primaryAssetType`.
- Retorna siempre `{ok, status, reasons, requestedAssetType, sceneEditorialRole, sourceEditorialRole, effectiveAssetType}`.

### 2. Integración en camino normal (`main()`)

- Después de `_fetch_one_asset` retorna `ok=True`, se llama `_validate_segment_for_role(cand, ...)`.
- Si el validador rechaza, se marca `REJECTED` en lugar de `OK`.
- Eliminada la validación manual duplicada de tipos prohibidos (reemplazada por el validador).
- `segmentValidationStatus`, `segmentValidationReasons`, `requestedAssetType`, `sceneEditorialRole`, `sourceEditorialRole`, `effectiveAssetType` se persisten en el `seg_entry`.

### 3. `_try_hard_role_fallback` activado en `main()`

- Cuando `_fetch_one_asset` falla y `editorial_role in HARD_HISTORICAL_ROLES`, se llama a `_try_hard_role_fallback(...)`.
- El seg_entry del fallback se valida con `_validate_segment_for_role(...)`.
- Solo si el validador pasa se acepta el segmento de fallback.
- Si el validador rechaza o el fallback retorna None: `ASSET_UNRESOLVED`.
- No se ejecuta fallback tras fallos arbitrarios de provider/download.

### 4. Validación de reuse via validador compartido

- Antes de aceptar reuse, se validan todos los segmentos del asset previo con `_validate_segment_for_role` contra el rol destino y la intención temporal destino.
- Si cualquier segmento falla, se bloquea el reuse y se continúa con fetching normal.
- Se preserva la proveniencia source inmutable (`originalEditorialRole`, `originalSceneNumber`, `originalVisualTemporalIntent`) independientemente de los metadatos destino.

### 5. Agregación de segmentos

- Sin cambios: `segment_results` y `all(segment_results)` ya funcionaban correctamente.

### 6. Reducción de lógica duplicada

- La validación manual de tipos prohibidos en `main()` reemplazada por el validador compartido.
- Los filtros tempranos en `_fetch_one_asset` se mantienen como optimización.

## Tests añadidos (7 nuevos)

1. `test_validator_called_on_normal_accept_path` — prueba que el spy del validador existe en el camino de aceptación.
2. `test_full_segment_acceptance_flow_calls_validator` — verifica por inspección de código que `_validate_segment_for_role` y `_try_hard_role_fallback` son referenciados en `main()`.
3. `test_validator_accepts_valid_soft_role_event_depiction_candidate` — consequence_or_legacy event_depiction con depicted-date overlap → PASS.
4. `test_validator_rejects_context_map_without_role_evidence` — context_map sin roleEvidence → REJECT.
5. `test_validator_rejects_document_or_date_with_wrong_type` — document_or_date con historical_photograph → REJECT.
6. `test_metadata_contract_all_fields_present` — candidato aceptado lleva todos los campos requeridos.
7. `test_fallback_integration_flow_respects_validator` — `_try_hard_role_fallback` produce entrada validable → pasa.

**Suite completa: 240/240 passed** (67 en test_semantic_asset_validation.py).

## Corrección post-consolidación (misma sesión)

Se detectaron dos defectos en la implementación de consolidación:

### Defecto A — fallback se disparaba en fallos operacionales

La condición original:
```python
not segment_accepted and not result["ok"] and editorial_role in HARD_HISTORICAL_ROLES
```
disparaba `_try_hard_role_fallback()` no solo tras agotamiento de Wikimedia, sino también tras fallos de descarga, MIME inválido o errores de filesystem.

**Corrección:**
- Añadido `failure_classification` al diccionario de retorno de `_fetch_one_asset()` con valores: `None` (éxito), `"resolution_exhausted"` (sin candidatos o todos rechazados por reglas de contenido), `"download_failed"` (candidato pasó filtros pero falló la descarga).
- `_download_attempted` tracking en `_fetch_one_asset`.
- Condición de fallback en `main()` restringida a:
  ```python
  result.get("failure_classification") == "resolution_exhausted"
  ```

### Defecto B — anti-repetition pools no se actualizaban con datos del fallback

Tras aceptación del fallback, el bookkeeping de `used_urls`, `used_authors`, `used_queries` leía de `cand` (que es `None` en fallback), por lo que el asset de fallback no se registraba para anti-repetición.

**Corrección:**
- Creado `accepted_candidate` canónico en `main()`: referencia `cand` para aceptación normal, y se construye desde `seg_entry` (que es `fb_entry`) para aceptación de fallback.
- Añadido `queryUsed` al `seg_entry` de `_try_hard_role_fallback`.
- Todo el bookkeeping post-aceptación usa `accepted_candidate`.

### Tests adicionales (5 nuevos)

1. `test_failure_classification_download_failed_blocks_fallback` — Wikimedia con candidato válido pero download falla → `download_failed`, fallback NO invocado.
2. `test_failure_classification_resolution_exhausted_allows_fallback` — Wikimedia sin resultados → `resolution_exhausted`, fallback SÍ permitido.
3. `test_fallback_updates_anti_repetition_pools` — Fallback aceptado → `used_urls`, `used_authors`, `used_queries` actualizados con datos del fallback.
4. `test_normal_acceptance_no_fallback_classification` — Aceptación normal → `failure_classification=None`.
5. `test_fallback_failure_classification_remains_on_fallback_rejection` — Fallback sin candidatos → `ASSET_UNRESOLVED` con clasificación preservada.

**Suite: 245/245 passed** (72 en test_semantic_asset_validation.py).

## No verificado

- No se ejecutó ningún job real del pipeline.
- La verificación del runner completo (`prepare`, `render`, `validate`) queda pendiente.
- El cambio OpenSpec NO se cierra.

## Archivos modificados

- `bin/fetch_images.py` — `_validate_segment_for_role` expandido, `main()` integrado con validador/fallback/reuse
- `tests/test_semantic_asset_validation.py` — 7 tests nuevos, 1 test existente actualizado
