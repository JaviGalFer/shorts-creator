# Sesión: v8 — Aislamiento de artefactos derivados y evidencia de cierre de frontera

- Fecha: 2026-07-05
- Objetivo: Evitar contaminación cruzada de artefactos entre jobs y resolver la escena 2 del Muro de Berlín con evidencia visual de cierre de frontera / construcción de barreras.
- Estado inicial: v7 tenía rutas del job v6 en `timeline`, `renderTimeline`, `subtitles`, `render` y `assetValidation`. Escena 2 estaba `ASSET_UNRESOLVED` porque `battle_or_assault` requería evidencia de construcción demasiado estrecha.
- Estado final: v8 `ASSETS_READY`, sin rutas cruzadas, escena 2 resuelta con foto de construcción del Muro. 71/71 tests passed.
- Agente responsable: opencode
- Cambio OpenSpec: improve-historical-visual-pipeline (Fase 18)

## Root causes

1. **Contaminación cruzada de jobs**: los clones de jobs copiaban todo el `metadata.json`, incluyendo secciones derivadas con rutas del job origen.
2. **Falta de validación en render**: `render_job.py` no comprobaba que todas las rutas locales pertenecieran al directorio del job actual.
3. **Rol demasiado estrecho para escena 2**: `battle_or_assault` solo aceptaba indicadores de construcción como `construction workers` o `building the wall`, pero las fotos reales del cierre de frontera de 1961 suelen describirse como `barbed wire`, `barricades`, `border closure`, `Stacheldraht`, `Mauerbau`, etc.
4. **Aceptación indebida de fotos de familia**: una foto de separación familiar que mencionaba "construction of the wall" en la descripción pasaba el filtro inicial.

## Files changed

| Archivo | Cambio |
|---------|--------|
| `bin/fetch_images.py` | Añadido rol `border_closure_construction` a hard roles, preferencias, event depiction. Nuevos indicadores de evidencia y rechazo. Queries en alemán/inglés. Hard rule para escenas de cierre de frontera. |
| `bin/clone_job.py` | Nuevo helper `clone_job()` que descarta artefactos derivados y aplica parches por escena. |
| `bin/render_job.py` | `validate_no_cross_job_paths()` + integración en `preflight_validate()`. Error `CROSS_JOB_ARTIFACT_REFERENCE`. |
| `tests/test_semantic_asset_validation.py` | 8 nuevos tests: evidencia de cierre, clon, regeneración de rutas, rechazo de referencias cruzadas. |
| `openspec/changes/improve-historical-visual-pipeline/design.md` | Fase 18: aislamiento de jobs, validación cruzada, rol border_closure_construction. |
| `openspec/changes/improve-historical-visual-pipeline/tasks.md` | Fase 18: tareas, bugs, validación y resultados del job v8. |
| `openspec/changes/improve-historical-visual-pipeline/specs/visual-asset-selection.md` | REQ-014, REQ-015, REQ-016. |
| `docs/sessions/2026-07-05-1540-berlin-wall-v8-job-isolation-and-border-closure.md` | Esta bitácora. |

## Test output

```
python3 -m pytest tests/test_semantic_asset_validation.py tests/test_duration_contract_and_scene_boundary.py -v
71 passed
```

```
python3 -m pytest tests/test_semantic_asset_validation.py -v
26 passed
```

## v8 asset status per scene

| Scene | Role | Status | Asset | Dims | Match | Evidence |
|-------|------|--------|-------|------|-------|----------|
| 1 | context_map | OK | 1945 Berlin Zones | 1762x1330 | archival_context | roleEvidence=[zones] |
| 2 | border_closure_construction | OK | Constructing Berlin Wall (CIA) | 930x1234 | archival_context | borderClosure=[construction of the wall] |
| 3 | civilian_impact | OK | The Berlin Wall 1961-1989 (family) | 930x1234 | archival_context | — |
| 4 | consequence_or_legacy | REUSE | Reuse Scene 3 | 930x1234 | historical_event | — |
| 5 | consequence_or_legacy | REUSE | Reuse Scene 3 | 930x1234 | archival_context | — |

## Notas de validación

- El job v8 fue clonado desde v7 con `bin/clone_job.py`, aplicando el parche `2:editorialRole=border_closure_construction`.
- `metadata.json` del v8 no contiene rutas del v6 ni del v7 tras ejecutar `prepare_job.py`.
- `validate_no_cross_job_paths()` confirmó cero referencias cruzadas.
- No se generó audio ni se renderizó, conforme a la consigna "asset-only validation".

## Riesgos observados

- La reutilización de assets entre escenas 3 (1961/1989) y 4/5 puede seleccionar una foto de separación familiar para una escena de caída/legado si la metadata del asset contiene el año 1989. El hard rule de `border_closure_construction` reduce este riesgo para escenas de construcción, pero el mecanismo general de reuso por años podría refinarse en una fase posterior.

## OpenSpec and session-log paths

- `openspec/changes/improve-historical-visual-pipeline/tasks.md`
- `openspec/changes/improve-historical-visual-pipeline/design.md`
- `openspec/changes/improve-historical-visual-pipeline/specs/visual-asset-selection.md`
- `docs/sessions/2026-07-05-1540-berlin-wall-v8-job-isolation-and-border-closure.md`
