# Sesión: v7 — Unification of renderability + construction evidence

- Fecha: 2026-07-05
- Objetivo: Unificar la validación de renderabilidad entre fetch_images, asset_validation y render_job. Añadir filtro de construcción directa para battle_or_assault.
- Estado inicial: v6 ASSETS_READY pero bloqueado por dimensiones del mapa Scene 1 (550x463). Scene 2 selecciona foto de familias separadas como imagen de construcción.
- Estado final: v7 con Scene 1 OK (mapa real 1762x1330). Scene 2 ASSET_UNRESOLVED (sin foto real de construcción). 18/18 tests passed.
- Agente responsable: opencode
- Cambio OpenSpec: improve-historical-visual-pipeline (v7 correction)

## Root causes

1. **Renderability gap**: fetch_images usaba MIN_WIDTH=400 para scoring pero render_job bloqueaba a 720x720. La misma candidata que pasaba scoring fallaba en render.
2. **Blank template map**: Scene 1 seleccionaba `Germany_divided_Berlin_West.png` (550x463, blank template) porque pasaba las reglas anteriores.
3. **Construction misclassification**: Scene 2 (battle_or_assault) aceptaba cualquier foto con `roleEvidence` genérico ("military", "soldiers") sin verificar construcción directa.
4. **Map readability zero for portrait**: La fórmula de readability solo funcionaba para landscape (w > h).
5. **Low semantic confidence for maps**: "1945 Berlin Zones" tenía semConf=low porque solo coincidía con palabras genéricas ("berlin"), aunque tenía roleEvidence ("zones").
6. **Timeline gaps**: El render timeline tenía gaps entre escenas y no cubría el final del audio.

## Files changed

| Archivo | Cambio |
|---------|--------|
| `bin/fetch_images.py` | `RENDER_MIN_WIDTH/HEIGHT=720`, `MIN_MAP_READABILITY=0.40`, `_BLANK_MAP_REJECT_TERMS`, `_check_renderability()`, `constructionSubjectEvidence`, `_construction_subject_indicators`, semConf boost for context_map, hard rule construction filter |
| `bin/prepare_job.py` | `_fill_timeline_gaps()` |
| `bin/asset_validation.py` | `renderabilityStatus` check in validation loop |
| `tests/test_semantic_asset_validation.py` | 6 new tests (18 total) |
| `openspec/.../tasks.md` | v7 correction section |
| `docs/sessions/2026-07-05-1658-berlin-wall-v7-renderability-and-role-evidence.md` | This file |

## Test output

```
python3 -m pytest tests/test_semantic_asset_validation.py -v
18 passed
```

```
python3 -m pytest tests/test_duration_contract_and_scene_boundary.py -v
45 passed
```

## Scene 1 candidate comparison

| Candidate | Eff Type | RoleEv | Readability | Dims | Render | Selected |
|-----------|----------|--------|-------------|------|--------|----------|
| 1945 Berlin Zones | historical_map | [zones] | 0.43 | 1762x1330 | PASS | YES |
| Germany divided Berlin West (blank) | historical_map | [map,divided] | 0.17 | 550x463 | FAIL | NO |
| August 1961 Newsweek map | document | [map,zones,occupation] | 0.00 | 478x591 | FAIL | NO |

## Scene 2 direct-subject evidence result

- Family separation photo: `constructionSubjectEvidence=[]` → REJECTED ✓
- JFK checkpoint photo: `constructionSubjectEvidence=[]` → REJECTED ✓
- East German construction workers (500x352): `constructionSubjectEvidence=['construction workers','workers building']` but score=-50 and render=FAIL (too small)
- Result: **ASSET_UNRESOLVED** — no construction photo meets all gates

## Timeline coverage validation result

With audioDuration=25.32s and native scene windows (0.1-5.675, 6.537-11.05, 11.912-15.525, 16.387-20.025, 20.887-24.438):
- Pre-fill gaps: 5 gaps total (0.1s start + 4 inter-scene gaps + 0.882s end)
- Post-fill: start=0.0, all gaps <= 0.0, end=25.32
- Test: `_fill_timeline_gaps` correctly extends entries to fill all gaps ✓

## v7 asset status per scene

| Scene | Status | Asset | Match |
|-------|--------|-------|-------|
| 1 | OK | 1945 Berlin Zones (1762x1330) | archival_context |
| 2 | ASSET_UNRESOLVED | — | — |
| 3 | OK | Family separated at Wall (1616x1275) | archival_context |
| 4 | OK | Juggling on Berlin Wall 1989 (1179x1743) | historical_event |
| 5 | REUSE | Reuse Scene 4 | archival_context |

## Whether render is allowed

**Not yet.** Scene 2 is unresolved. Scene 1 has a valid map.

## OpenSpec and session-log paths

- `openspec/changes/improve-historical-visual-pipeline/tasks.md`
- `docs/sessions/2026-07-05-1658-berlin-wall-v7-renderability-and-role-evidence.md`
