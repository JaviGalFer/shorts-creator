# Sesión: Corrección v6 — Context map effective asset type

- Fecha: 2026-07-05
- Objetivo: Corregir que `context_map` validara solo `primaryAssetType` declarado, no el tipo real del candidato. Escena 1 de v5 usaba una foto del Muro de Berlín de 1986 declarada como `historical_map`.
- Estado inicial: v5 `ASSETS_READY` pero Escena 1 con asset equivocado (foto del Muro, no mapa).
- Estado final: v6 `ASSETS_READY`. Escena 1 obtiene un mapa real de Berlín dividido (`Germany_divided_Berlin_West.png`). 12/12 tests pasan.
- Agente responsable: opencode
- Cambio OpenSpec relacionado: improve-historical-visual-pipeline (Fase 17 + corrección v6)
- Validaciones realizadas: pipeline v6 exitoso, tests `test_semantic_asset_validation.py` 12/12 passing.

## Root cause

Escena 1 (`context_map`, `primaryAssetType=historical_map`) aceptaba cualquier candidato cuyo `primaryAssetType` del `visualPlan` fuera `historical_map`, sin verificar que el contenido del candidato fuera realmente un mapa/plano/documento. La foto del Muro de 1986 de Thierry Noir pasaba la validación porque el `visualPlan` declaraba `historical_map`, aunque el título de la imagen indicaba claramente que era una fotografía.

## Cambios realizados

### `_infer_effective_asset_type(candidate, declared_type)`

Nueva función que inspecciona título, descripción y URL del candidato para determinar su tipo real:

| Indicador detectado | Tipo inferido |
|---------------------|---------------|
| `document`, `treaty`, `newspaper`, `decree`, `Newsweek`, etc. | `document` |
| `map`, `karte`, `cartography`, `atlas`, `plan`, `diagram`, `occupation zones`, `sectors`, etc. | `historical_map` |
| `photo`, `photograph`, `image of the`, `taken in`, `families separated`, `construction workers`, etc. | `historical_photograph` |
| Ningún indicador | `declared_type` |

Los indicadores de documento se evalúan primero: un documento SOBRE un mapa es `document`.

### Hard rule context_map mejorada

```python
if editorial_role_str == "context_map":
    declared_type = visual_plan.get("primaryAssetType", "")
    effective_type = _infer_effective_asset_type(c, declared_type)
    role_ev = semantic_ev.get("roleEvidence", [])

    allowed = {"map", "historical_map", "document", "newspaper", ...}
    if effective_type not in allowed:  # reject
    if not role_ev:                      # reject
    if asset_match == "unknown":         # reject

    c["assetTypeValidationStatus"] = "PASS"
```

### Nuevos campos de metadata

Todo asset/segmento ahora registra:
- `declaredAssetType`: tipo solicitado por el `visualPlan`.
- `effectiveAssetType`: tipo inferido desde el contenido del candidato.
- `assetTypeValidationStatus`: `"PASS"` o `"FAIL"`.

### `_determine_asset_temporal_match` para mapas sin año

Mapas y documentos con match de entidad/ubicación ahora reciben `archival_context` aunque no mencionen un año explícito. Esto permite que mapas de zonas de ocupación de 1945 se acepten para contexto del Muro de Berlín de 1961.

## Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `bin/fetch_images.py` | `_infer_effective_asset_type()`, `_MAP_INDICATORS`, `_DOCUMENT_INDICATORS`, `_PHOTO_INDICATORS`, hard rule context_map con effectiveType+roleEvidence, temporal match para mapas sin año, campos `declaredAssetType`/`effectiveAssetType`/`assetTypeValidationStatus` en segmento y asset_meta, fix NoneType crash en semanticEvidence |
| `tests/test_semantic_asset_validation.py` | 4 nuevos tests de regresión para context_map (12 total) |
| `openspec/changes/.../tasks.md` | Bugs 10-11, sección corrección v6 |
| `openspec/changes/.../specs/visual-asset-selection.md` | REQ-009 actualizado, REQ-013 nuevo |
| `docs/sessions/2026-07-05-0114-berlin-wall-v6-context-map-effective-type.md` | Este archivo |

## Validaciones

### Pipeline v6

```bash
python3 bin/fetch_images.py data/videos/validation-realistic-berlin-wall-v6-assets-20260705-011402/metadata.json --max-candidates 5
```

Resultado: `{"jobId": "bw-v6-20260705-011402", "success": true}`

| Escena | Rol | EffectiveType | ValidationStatus | Match |
|--------|-----|---------------|------------------|-------|
| 1 | context_map | historical_map | PASS | archival_context |
| 2 | battle_or_assault | N/A | N/A | archival_context |
| 3 | civilian_impact | N/A | N/A | archival_context |
| 4 | consequence_or_legacy | N/A | N/A | historical_event |
| 5 | consequence_or_legacy (reuse) | N/A | N/A | archival_context |

Escena 1 seleccionó `Germany_divided_Berlin_West.png` — mapa real de división Berlín Oeste.

### Tests

```bash
python3 -m pytest tests/test_semantic_asset_validation.py -v
```

Resultado: `12 passed`.

## Render allowed?

Not yet — the user explicitly said not to render until Scene 1 passes. Scene 1 now passes but the user requested summary first. Status: `ASSETS_READY`, render decision pending.

## Próximos pasos

1. Revisar si el mapa de Berlín Oeste (blank template) es suficientemente informativo o si se prefiere un mapa con más detalle de ocupación.
2. Si se aprueba, proceder con `prepare_job.py` y `render_job.py`.
