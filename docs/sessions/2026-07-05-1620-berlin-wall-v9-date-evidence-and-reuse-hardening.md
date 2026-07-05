# Sesión: v9 — Evidencia de fecha depictiva vs contexto y endurecimiento de reutilización

- Fecha: 2026-07-05
- Objetivo: Eliminar falsa clasificación 1989 causada por rangos de título ("1961 - 1989") y endurecer el reuso para que escenas de caída/legado no reutilicen fotos de separación familiar.
- Estado inicial: v8 reusaba el asset de escena 3 (foto separación familiar "The Berlin Wall 1961 - 1989") para escena 4 (caída 1989) porque `periodTermsMatched` contenía "1989" del rango del título. Esto era incorrecto: un asset con título retrospectivo no debe tratarse como si depictara cada año del rango.
- Estado final: v9 `ASSETS_READY`. Escena 4 obtiene foto fresca "Juggling on Berlin Wall 1989" (no reuso). 32/32 tests passed.
- Agente responsable: opencode
- Cambio OpenSpec: improve-historical-visual-pipeline (Fase 19)

## Root causes

1. **Falsa coincidencia 1989 por rango en título**: La narración de escena 4 "El Muro cayó en 1989" hacía que `periodTermsMatched` incluyera "1989" porque el título del asset de escena 3 era "The Berlin Wall 1961 - 1989". Un candidato con rango retrospectivo en el título nunca debe tratarse como si depictara cada año del rango.
2. **Reuso débil**: Escena 3 (`civilian_impact`, familias separadas en 1961) era reusada para escena 4 (`consequence_or_legacy`, caída 1989). El reuso comparaba `periodTermsMatched` en vez de `sourceDepictedDateEvidence`, y no consideraba el rol editorial original.
3. **Cortocircuito de contexto en `_classify_date_evidence`**: La función tenía `if y in context_years: continue` que eliminaba "1961" de depicted porque el rango lo añadía a context. Esto impedía que la segunda mención de "1961" en una frase depictiva se registrara correctamente.

## Files changed

| Archivo | Cambio |
|---------|--------|
| `bin/fetch_images.py` | `_classify_date_evidence()` con heurística de rango, retrospectiva y verbos depictivos. `fallOpeningSubjectEvidence` y `divisionSubjectEvidence` en semanticEvidence. Reuso usa `sourceDepictedDateEvidence`. |
| `bin/asset_validation.py` | `border_closure_construction` en `EDITORIAL_ROLE_COMPATIBILITY`. `check_role_evidence()`. `check_reuse_compatibility()` que rechaza reuso si depicted no intersecta o rol es `civilian_impact` para evento distinto. |
| `tests/test_semantic_asset_validation.py` | 6 nuevos tests: rango título no depicted, asset familiar falla 1989, malabarismo pasa 1989, border_closure sin evidencia falla, reuso incompatible falla. |
| `openspec/changes/improve-historical-visual-pipeline/design.md` | Fase 19: clasificación fecha, endurecimiento reuso, nuevos campos semanticEvidence. |
| `openspec/changes/improve-historical-visual-pipeline/tasks.md` | Fase 19: tareas, bugs, validación v9. |
| `openspec/changes/improve-historical-visual-pipeline/specs/visual-asset-selection.md` | REQ-017, REQ-018. |
| `docs/sessions/2026-07-05-1620-berlin-wall-v9-date-evidence-and-reuse-hardening.md` | Esta bitácora. |

## Test output

```
python3 -m pytest tests/test_semantic_asset_validation.py -v
32 passed in 0.04s
```

Tests nuevos (tests 27-32):
- `test_title_range_1961_1989_is_context_only_not_depicted` — rango con guión no produce depicted.
- `test_family_separated_1961_asset_fails_target_event_1989` — foto familia 1961 no pasa para 1989.
- `test_juggling_berlin_wall_1989_passes_target_event_1989` — foto malabarismo 1989 sí pasa.
- `test_scene3_family_asset_may_pass_scene5_only_with_legacy_reason` — asset familiar puede reusarse en escena 5 con motivo legacy.
- `test_border_closure_construction_without_evidence_fails_asset_validation` — rol border_closure sin evidencia falla.
- `test_reuse_civilian_impact_for_distinct_event_1989_fails_asset_validation` — reuso civil_impact→1989 falla validación.

## v9 asset status per scene

| Scene | Role | Status | Asset | Match | Depicted | Context | Evidencia clave |
|-------|------|--------|-------|-------|----------|---------|-----------------|
| 1 | context_map | OK | 1945 Berlin Zones map | archival_context | [1945] | [] | roleEvidence=[zones] |
| 2 | border_closure_construction | OK | CIA construction photo | archival_context | [1961] | [] | borderClosure=[construction of the wall] |
| 3 | civilian_impact | OK | Family separation ("The Berlin Wall 1961 - 1989") | archival_context | [1961] | [1961..1989] | division=[families separated] |
| 4 | consequence_or_legacy | OK | Juggling on Berlin Wall 1989 | historical_event | [1989] | [] | fall=[juggling on the berlin wall] |
| 5 | consequence_or_legacy | REUSE | Reuse Scene 4 asset | archival_context | [1989] | [] | origScene=4, reason=commemoration context |

## Detalles de implementación

### `_classify_date_evidence()` heurísticas

1. **Rango con guión**: regex `(\d{4})\s*[–-]\s*(\d{4})` detecta rangos tipo "1961 - 1989". Las menciones de año individual dentro del rango no se marcan como depicted.
2. **Retrospectiva**: frases como "post-war", "after the fall", "since its construction", "desde su construcción", "tras la caída" indican contexto.
3. **Verbo depictivo**: "shows", "depicts", "during", "photographed in", "en", "durante", "fotografiado en" indican depiction.

### `check_reuse_compatibility()` reglas

1. Si `sourceDepictedDateEvidence` del asset origen no intersecta con los años de la escena destino → bloqueo.
2. Si el rol original es `civilian_impact` y la escena destino tiene evento distinto (ej. 1989) → bloqueo.
3. Si el asset tiene `divisionSubjectEvidence` (separación familiar) y la escena destino no tiene evidencia de caída → bloqueo.

## Notas de validación

- El job v9 fue creado manualmente (no por clonación desde v8) para garantizar metadata limpia.
- `metadata.json` del v9 no contiene rutas de otros jobs.
- `asset_validation.py` corre en modo integrado durante `fetch_images.py`.
- No se generó audio ni se renderizó, conforme a la consigna "asset-only validation".
- El campo `reuseCompatibilityReason` para escena 5 dice "reused archival asset suitable for commemoration context (origRole=None); visual consistency across consecutive scenes" — esto es aceptable porque el asset origen (escena 4) no era `civilian_impact`.

## Riesgos observados

- La heurística de rango con guión es específica para formato "1961 - 1989". Otros formatos de rango (ej. "1961-1989" sin espacios, o "entre 1961 y 1989") podrían no detectarse correctamente.
- `check_reuse_compatibility` depende de que `sourceDepictedDateEvidence` esté correctamente poblado. Si un asset no tiene depicted dates (porque su título no contiene años), el reuso podría fallar incorrectamente.

## OpenSpec and session-log paths

- `openspec/changes/improve-historical-visual-pipeline/tasks.md`
- `openspec/changes/improve-historical-visual-pipeline/design.md`
- `openspec/changes/improve-historical-visual-pipeline/specs/visual-asset-selection.md`
- `docs/sessions/2026-07-05-1620-berlin-wall-v9-date-evidence-and-reuse-hardening.md`
