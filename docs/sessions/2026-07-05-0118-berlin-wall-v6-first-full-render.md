# Sesión: v6 First full render attempt — Berlin Wall

- Fecha: 2026-07-05
- Objetivo: Render controlado end-to-end del job v6 de Berlin Wall.
- Estado inicial: `ASSETS_READY` con 5/5 assets validados. Sin narración ni subtítulos generados para v6.
- Estado final: `SUBTITLES_READY`. Render BLOQUEADO por dimensiones insuficientes del asset de Escena 1.
- Agente responsable: opencode
- Cambio OpenSpec relacionado: improve-historical-visual-pipeline (Fase 17 + v6 correction)

## Commands executed

```bash
# 1. Verify all five assets exist and decode
python3 -c "..."  # 5/5 OK, all decode successfully

# 2. Generate audio (narration did not exist for v6)
python3 bin/generate_audio.py .../metadata.json --continuous --voice es-ES-AlvaroNeural --subtitle-timing-provider edge_tts
# Result: audioDurationSec=25.32, 9 cues, source=edge_tts_word_boundary, AUDIO_READY

# 3. prepare_job.py
python3 bin/prepare_job.py .../metadata.json
# Result: SUBTITLES_READY, 5 timeline segments, 9 subtitle cues

# 4. render_job.py
python3 bin/render_job.py .../metadata.json
# Result: BLOCKED — Scene 1 asset 550x463 below min 720x720
```

## Render path

`/home/javi/projects/shorts-creator/data/videos/validation-realistic-berlin-wall-v6-assets-20260705-011402/video.mp4` — NOT GENERATED (blocked).

## Audio/video durations and drift

| Metric | Value |
|--------|-------|
| Total narration duration | 25.32 s |
| Scene 1 start → end | 0.10 → 5.675 |
| Scene 2 start → end | 6.537 → 11.05 |
| Scene 3 start → end | 11.912 → 15.525 |
| Scene 4 start → end | 16.387 → 20.025 |
| Scene 5 start → end | 20.887 → 24.438 |
| Timing source | edge_tts_word_boundary |
| Timing confidence | high |
| Cues | 9 |
| Canonical matching | present |

Duration is 25.32s — within 25-30s contract ✓.

## Validation-gate summary

| Gate | Status | Detail |
|------|--------|--------|
| Asset existence | PASS | 5/5 exist and decode |
| Subtitle style | PASS | shorts_upper_dynamic, Alignment=8, MarginV=430, Outline=4, Shadow=2, no opaque box |
| Edge timing | PASS | edge_tts_word_boundary |
| Duration contract | PASS | 25.32s (25-30 range) |
| Asset dimensions | **BLOCKED** | Scene 1: 550x463 < min 720x720 |
| Scene 2 dimensions | PASS | 1800x1200 |
| Scene 3 dimensions | PASS | 1616x1275 |
| Scene 4 dimensions | PASS | 1179x1743 |
| Scene 5 dimensions | PASS | 1179x1743 (reuse Scene 4) |

## Frame paths

Not extracted — render blocked before frame extraction.

## OpenSpec/task update

Updated `openspec/changes/improve-historical-visual-pipeline/tasks.md` Phase 17 validation section with v6 render attempt results.

## Remaining editorial limitations

1. **Scene 1 map resolution**: The selected `Germany_divided_Berlin_West.png` is 550x463 — a blank location-map template. It is a valid map (passes asset type and role evidence checks) but is too small for render (min 720x720) and visually uninformative (blank template, no labels or historical detail).

2. **Options to resolve**:
   - Lower the minimum resolution threshold for maps (maps often have lower DPI than photos).
   - Force a different map candidate — queries like "map berlin occupation zones" returned better maps (August 1961 Newsweek map, Map of French occupation zone) but these either scored lower or failed other gates.
   - Allow lower resolution for `historical_map` asset types specifically, down to e.g. min 400px on the shorter dimension.
   - Accept that Berlin-Wall blank templates are historically accurate but visually weak.

3. **Query improvement**: The Scene 1 visual plan uses queries like "Berlin divided map", "Berlín map", "Berlín cartography" — these return low-resolution templates. Better query: "August 1961 Berlin occupation zones map Newsweek" which returned the actual Newsweek map.

4. **No other blockers**: Scenes 2-5 are ready with correct dimensions, good historical matches, and proper temporal validation.
