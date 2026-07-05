# Sesión: Validación semántica hard de assets históricos (Berlin Wall)

- Fecha: 2026-07-05
- Objetivo: Implementar y validar reglas duras de asset semántico para evitar errores temporales y de rol editorial en el pipeline visual.
- Estado inicial: Job `validation-realistic-berlin-wall-v4-assets-20260704-174757` con Escena 1 bloqueada por regla `context_map` y Escena 4 reusando incorrectamente un asset de 1961 para una escena de 1989.
- Estado final: Job `validation-realistic-berlin-wall-v5-assets-20260705-001121` en estado `ASSETS_READY`; 8/8 tests pasan.
- Agente responsable: opencode
- Cambio OpenSpec relacionado: improve-historical-visual-pipeline (Fase 17)
- Validaciones realizadas: pipeline v5 exitoso, tests `test_semantic_asset_validation.py` 8/8 passing.

## Cambios realizados

### Hard rules de filtrado

| Regla | Comportamiento | Archivo |
|-------|----------------|---------|
| `context_map` | Solo acepta `primaryAssetType` en `{map, historical_map, document, newspaper, map_or_document, historical_map_or_document}` | `bin/fetch_images.py` |
| `event_depiction` | Rechaza `assetTemporalMatch` `unknown` o `modern_legacy` | `bin/fetch_images.py` |

### Mejoras en `_determine_asset_temporal_match`

- Matching sin acentos (`_unaccent`).
- Equivalencias multilingües para periodo, entidad y ubicación (español ↔ inglés ↔ alemán).
- Extracción de año de evento desde `visualPlan.period`, `visualPlan.entities` y `scene.voiceover`.
- Nuevas equivalencias de periodo: `post-guerra fría` / `post-guerra fria`.
- Priorización de indicadores modernos (`anniversary`, `celebration`, `commemoration`) cuando no hay año de evento coincidente.

### Reutilización segura de assets

- Bloqueo de reúso para `event_depiction` si el asset reusado es `modern_legacy` o `unknown`.
- Extracción de años del `voiceover` destino además del `period` para detectar mismatch (ej. 1961 vs 1989).
- Re-evaluación de `assetTemporalMatch` en el contexto de la escena destino.
- Preservación de `title` y `description` en `asset_meta` para cadenas de reuso.
- Deep-copy de `segments` antes de mutar para evitar corrupción del VTI de escenas anteriores.

### Queries históricas para event_depiction

- `build_historical_queries` se invoca también para escenas cuyo `editorialRole` no esté en `HARD_HISTORICAL_ROLES` pero cuyo intent temporal sea `event_depiction`. Esto evitó que la Escena 4 (`consequence_or_legacy` + voiceover "cayó en 1989") se quedara con la query genérica "Berlin Wall fall celebrations" que solo devolvía fotos del 35º aniversario (2024).

### Metadata extendida

- Campos añadidos a segmentos y assets: `originalSceneNumber`, `originalEditorialRole`, `originalVisualTemporalIntent`, `reuseCompatibilityReason`.
- `semanticEvidence` ahora incluye `roleEvidence` y `assetTypeEvidence`.

### Bugs corregidos

| # | Archivo | Bug | Fix |
|---|---------|-----|-----|
| 1 | `bin/fetch_images.py` | Penalización `same_asset_type` demasiado agresiva (2 escenas consecutivas) | Umbral `>= 2` en lugar de `>= 1` |
| 2 | `bin/fetch_images.py` | Reuso mutaba VTI de escena anterior por shallow copy | Deep-copy de `segments` |
| 3 | `bin/fetch_images.py` | `context_map` leía `c["strategy"]` (siempre `historical_archive`) | Leer `visualPlan["primaryAssetType"]` |
| 4 | `bin/fetch_images.py` | Reuso 1961→1989 no se bloqueaba sin año en el periodo | Extraer años también del `voiceover` |
| 5 | `bin/fetch_images.py` | No matching de términos acentuados ni multilingües | `_unaccent()` + diccionarios de equivalencia |
| 6 | `bin/fetch_images.py` | "Post-Guerra Fría" no reconocido | Añadir a `period_equivalents` |
| 7 | `bin/fetch_images.py` | Fotos de aniversario reciente como `archival_context` | Priorizar `modern_indicator` sin año de evento |
| 8 | `bin/fetch_images.py` | Queries genéricas para escenas `event_depiction` de rol soft | Generar queries históricas para `event_depiction` |
| 9 | `bin/fetch_images.py` | `asset_meta` multi-segmento perdía `title`/`description` | Copiar desde `semanticEvidence` |

## Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `bin/fetch_images.py` | Hard rules, `_determine_asset_temporal_match`, `_classify_temporal_intent`, reuse compatibility, query generation, metadata fields, deep-copy fix, title/description preservation |
| `tests/test_semantic_asset_validation.py` | Nuevos tests unitarios para validación semántica (8 tests) |
| `openspec/changes/improve-historical-visual-pipeline/proposal.md` | Fase 17 añadida |
| `openspec/changes/improve-historical-visual-pipeline/design.md` | Sección de validación semántica hard añadida |
| `openspec/changes/improve-historical-visual-pipeline/tasks.md` | Fase 17: tareas, bugs corregidos y validación |
| `openspec/changes/improve-historical-visual-pipeline/specs/visual-asset-selection.md` | REQ-009 a REQ-012 |
| `docs/sessions/2026-07-05-0015-berlin-wall-asset-temporal-validation.md` | Este archivo |

## Validaciones

### Pipeline v5

```bash
python3 bin/fetch_images.py data/videos/validation-realistic-berlin-wall-v5-assets-20260705-001121/metadata.json --max-candidates 5
```

Resultado:
```json
{"jobId": "bw-v5-20260705-001121", "success": true}
```

Estado final del job: `ASSETS_READY`.

| Escena | Rol | Asset | Match temporal | Reuso |
|--------|-----|-------|----------------|-------|
| 1 | context_map | Mapa histórico | archival_context | No |
| 2 | battle_or_assault | Construcción del Muro 1961 | archival_context | No |
| 3 | civilian_impact | Familia separada 1961 | archival_context | No |
| 4 | consequence_or_legacy | Caída del Muro 1989 | historical_event | No (bloqueado reuso de 1961) |
| 5 | consequence_or_legacy | Caída del Muro 1989 (reuso) | archival_context | Sí, desde Escena 4 |

### Tests

```bash
python3 -m pytest tests/test_semantic_asset_validation.py -v
```

Resultado: `8 passed`.

## Próximos pasos

1. Validar que el job v5 pueda pasar por `prepare_job.py` y `render_job.py` si se decide renderizar (actualmente se detuvo en `ASSETS_READY` según instrucciones).
2. Revisar si hay más roles/editorialRoles que requieran validación semántica hard.
3. Considerar añadir un test de integración que ejecute `fetch_images.py` con un job de prueba pequeño y verifique `ASSETS_READY`.
