# Sesión: Deterministic assets, audio, prepare verification

- Fecha: 2026-07-06
- Objetivo: Verificación real de fetch_images → generate_audio → prepare_job sin depender del LLM. Usando fixture manual con contrato estructural válido.
- Cambio OpenSpec: `improve-historical-visual-pipeline`

## Fixture

Job: `fixture-berlin-wall-current-contract-20260706-203702`
Path: `data/videos/fixture-berlin-wall-current-contract-20260706-203702`

4 scenes, ~28s estimados. Structural validator: `valid=True`, sin issues.

| Scene | Role | Intent | Types | Segments |
|-------|------|--------|-------|----------|
| 1 | context_map | event_depiction | historical_map + document | 2 |
| 2 | border_closure_construction | event_depiction | historical_photograph + historical_art | 2 |
| 3 | civilian_impact | event_depiction | historical_photograph + historical_art | 2 |
| 4 | consequence_or_legacy | legacy_or_commemoration | historical_photograph + atmospheric_broll | 2 |

## Stage results

### Assets

| Scene | Seg | Requested | Effective | Provider | Status | Error |
|-------|-----|-----------|-----------|----------|--------|-------|
| 1 | 1 | historical_map | historical_map | wikimedia_commons | PASS | — |
| 1 | 2 | document | historical_map | wikimedia_commons | PASS | — |
| 2 | 1 | historical_photograph | historical_photograph | wikimedia_commons | PASS | — |
| 2 | 2 | historical_art | None | None | REJECTED | ASSET_UNRESOLVED |
| 3 | 1 | historical_photograph | historical_photograph | wikimedia_commons | PASS | — |
| 3 | 2 | historical_art | None | None | REJECTED | ASSET_UNRESOLVED |
| 4 | 1 | historical_photograph | historical_photograph | wikimedia_commons | PASS | — |
| 4 | 2 | atmospheric_broll | None | None | REJECTED | Download failed |

**Scene selection:** Scene 1 selected=true, scenes 2-4 selected=false (missing segments).

**Fallback behavior:**
- Scenes 2-3 (border_closure_construction, civilian_impact): hard roles with "resolution_exhausted" → fallback attempted via Pexels/Pixabay. No matching candidates found → ASSET_UNRESOLVED.
- Scene 4 (consequence_or_legacy): soft role → no fallback. Seg 2 atmospheric_broll failed to download from wikimedia_commons → "Download failed".

### Audio

4/4 scenes generated via Edge TTS (es-ES-AlvaroNeural, word boundary timing).

### Prepare

- `subtitle.ass` created (1629 bytes)
- `renderTimeline`: 8 entries
- `video.mp4` does NOT exist
- Narration duration: ~28.0s

### RenderTimeline verification

| Entry | Scene | Beat | Start | End | Dur | Asset | Overlap? |
|-------|-------|------|-------|-----|-----|-------|----------|
| 0 | 1 | 1 | 0.0 | 3.5 | 3.5 | scene-01-01.jpg | No |
| 1 | 1 | 2 | 3.5 | 7.0 | 3.5 | scene-01-02.jpg | No |
| 2 | 2 | 1 | 7.0 | 10.5 | 3.5 | scene-02-01.jpg | No |
| 3 | 2 | 2 | 10.5 | 14.0 | 3.5 | (empty—no asset) | No |
| 4 | 3 | 1 | 14.0 | 17.5 | 3.5 | scene-03-01.jpg | No |
| 5 | 3 | 2 | 17.5 | 21.1 | 3.6 | (empty—no asset) | No |
| 6 | 4 | 1 | 21.1 | 24.638 | 3.538 | scene-04-01.jpg | **Yes: overlap with entry 7** |
| 7 | 4 | 2 | 22.725 | 28.0 | 5.275 | (empty—no asset) | Overlap 1.913s with entry 6 |

The overlap in scene 4 occurs because seg 2 has no image asset (beat 2 starts at 22.725s while beat 1 ends at 24.638s). This is a consequence of the timeline being beat-driven (audio-synchronized) while visualSequence uses static durationFraction. When a segment has no image, its beat still occupies audio time.

**Programmatic checks:**
- First entry startSec=0.0 ✓
- Entries are ordered ✓
- Scene 4 overlap: 1.913s (entry 6 ends 24.638, entry 7 starts 22.725)
- No material gaps ✓
- Final end (28.0s) matches narration duration ✓
- All generated paths resolve inside job directory ✓
- video.mp4 does not exist ✓

## Bug found: SCENE_PAUSE_SEC missing

During execution, `fetch_images.py` crashed with `NameError: name 'SCENE_PAUSE_SEC' is not defined`. This was accidentally removed when the EDITORIAL_ROLE_PREFERENCES dict was extracted to editorial_asset_contract.py. Restored to line ~153. Tests (291) still pass after fix.

## Verification status

- **Assets:** Verified. Shared validator, failure classification, hard-role fallback all exercised. Fallback correctly attempted when Wikimedia exhausted for hard roles. Fallback correctly not attempted for soft role (scene 4). Anti-repetition not fully exercised (only scene 1 had 2 successful adjacent segments).
- **Audio:** Verified. Edge TTS worked for all 4 scenes.
- **Prepare:** Verified. subtitle.ass, timeline, renderTimeline generated. Beat-driven timeline has expected overlap for scenes with missing segments.

## Remaining unverified

- Render (video.mp4 assembly)
- Validate
- Review
- Full pipeline E2E with all segments successful

## Prepare asset-completion gate (misma sesión)

### Root cause

`prepare_job.py` comprobaba `all_assets` con una expresión `all(p and Path(p).exists() for p in seg_paths if p)` que filtraba paths nulos (`if p`). Segmentos con `path: null` no se reportaban como fallos. Además no verificaba `segmentValidationStatus`, `error`, escenas `selected=false`, ni que los paths estuvieran dentro del directorio del job.

### Corrección

Añadida `_validate_asset_completion()` que se ejecuta antes de cualquier generación de artefactos. Verifica:

1. El segmento existe en assets.
2. No tiene `error`.
3. `segmentValidationStatus == "PASS"`.
4. `path` no es null/vacío.
5. Path resuelve dentro del job directory.
6. Archivo existe en disco.

Si falla: `status = ASSET_UNRESOLVED`, `assetFailures` persistidos, retorna 1, no genera subtitle.ass/timeline/renderTimeline.

### Tests (8)

`test_all_valid_passes`, `test_unresolved_segment_error_rejected`, `test_null_path_rejected`, `test_empty_path_rejected`, `test_file_missing_rejected`, `test_validation_not_pass_rejected`, `test_path_outside_job_rejected`, `test_segment_missing_from_assets`.

Suite: 299/299 passed. El fixture `fixture-berlin-wall-current-contract-20260706-203702` ahora es rechazado correctamente con 3 fallos estructurados y exit code 1.

### Nota

La verificación anterior de prepare NO fue válida — se aceptaron segmentos sin resolver. Esta corrección cierra ese gap.

## Prepare gate completion (misma sesión)

### Defecto A: SCENE_NOT_SELECTED no aplicado

`_validate_asset_completion` inspeccionaba `selected=False` pero no añadía fallo (solo un bucle `pass`). Corregido: `SCENE_NOT_SELECTED` para escenas con `selected=False` y visualSequence entries.

### Defecto B: sin limpieza de artefactos stale

Prepare fallido no eliminaba `subtitle.ass`, ni borraba `timeline`/`renderTimeline`/`subtitles`/`render`/`review` del metadata. Corregido: `_invalidate_derived_artifacts()` elimina todo artefacto derivado y metadata stale.

### Tests (+5)

4 integration tests via `main()` + 1 helper: `test_main_rejects_unresolved_segment`, `test_main_rejects_selected_false`, `test_main_cleans_stale_artifacts`, `test_main_accepts_valid_job`, `test_scene_not_selected_fails`. Suite: 304/304.

## Prepare selected fail-closed + runner integration (misma sesión)

### Defecto A: selected fail-closed

`_validate_asset_completion` solo rechazaba `selected is False`, dejando pasar `selected=None` o campo ausente. Corregido a `if selected is not True`.

### Tests adicionales

- `test_selected_none_fails_closed` / `test_selected_omitted_fails_closed` — fail-closed para None/ausente
- `test_prepare_exit1_fails_pipeline` — runner integración: `failedStage=prepare`, `exitCode=1`, `childCommand`
- `test_prepare_exit1_no_render_no_validate` — render/validate no invocados tras prepare failure

Suite: 308/308.
