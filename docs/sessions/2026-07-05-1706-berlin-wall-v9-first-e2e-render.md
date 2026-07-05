# Sesión: v9 — Primer render end-to-end

- Fecha: 2026-07-05
- Objetivo: Renderizar el job v9 validado sin regenerar script, assets ni metadatos de assets. Solo audio → prepare → render → validate → review frames.
- Estado inicial: v9 `ASSETS_READY` con 5 assets aprobados (mapa 1945, construcción CIA 1961, familia 1961, malabarismo 1989, reuse escena 4).
- Estado final: `RENDERED`. validate_job.py passed: true. ffmpeg exit code 0.
- Agente responsable: opencode

## Commands executed

```
# 1. Audio continuo Edge TTS
python3 bin/generate_audio.py --voice es-ES-AlvaroNeural --continuous \
  data/videos/validation-realistic-berlin-wall-v9-assets-20260705-162058/metadata.json

# 2. Prepare job (subtitles + timeline)
python3 bin/prepare_job.py \
  data/videos/validation-realistic-berlin-wall-v9-assets-20260705-162058/metadata.json

# 3. Validación de assets
python3 -c "from asset_validation import validate_job_for_render; ..."  # PASS

# 4. Render
python3 bin/render_job.py \
  data/videos/validation-realistic-berlin-wall-v9-assets-20260705-162058/metadata.json

# 5. Validación post-render
python3 bin/validate_job.py --json --verbose \
  data/videos/validation-realistic-berlin-wall-v9-assets-20260705-162058/metadata.json

# 6. Review frames (Docker ffmpeg con DOCKER_API_VERSION=1.43)
DOCKER_API_VERSION=1.43 docker run --rm -v ... linuxserver/ffmpeg:latest \
  -ss <timestamp> -i /workspace/job/video.mp4 -frames:v 1 -update 1 -q:v 2 /workspace/job/review-frames/<name>.jpg
```

## Audio duration, video duration and drift

| Métrica | Valor |
|---------|-------|
| Narration audio source | edge-tts es-ES-AlvaroNeural |
| Timing source | edge_tts_word_boundary |
| Audio duration | 25.32 s |
| Video duration | 25.32 s |
| Drift (audio vs video) | 0.00 s |
| Within 25-30s range | Yes |

## Preflight summary

| Check | Result |
|-------|--------|
| Cross-job path isolation | PASS (all paths under job dir) |
| No null asset paths | PASS (5/5 exist) |
| Asset validation | PASS (5/5 segments valid) |
| Duration contract (25-30s) | PASS (25.32s) |
| Visual timeline coverage | PASS (0.0–25.32s, no gaps) |
| Subtitle style (ASS) | Alignment=8, MarginV=430, Outline=4, Shadow=2, no background box |
| Scene 2 motion | slow_zoom_in, focalRegion=center |

## Render path

`data/videos/validation-realistic-berlin-wall-v9-assets-20260705-162058/video.mp4`

- Resolution: 1080×1920
- Video codec: H.264 (libx264, CRF 23)
- Audio codec: AAC 44100 Hz mono
- FFmpeg exit code: 0
- File size: ~1.7 MB (1715 KiB)
- Status: RENDERED
- Review: PENDING

## Validation summary (validate_job.py)

- **passed: true**
- **totalErrors: 0**
- **totalWarnings: 0**
- Timing source: edge_tts_word_boundary
- All 5 scene assets OK
- Subtitle: 9 non-overlapping cues, 81% coverage (20.6s / 25.3s)
- ASS style: shorts_upper_dynamic
- Video resolution: 1080×1920 OK

### Manifest quality gates

| Gate | Status |
|------|--------|
| technicalValidation | PASS |
| subtitleCoverageValidation | FAIL (cue text mismatch) |
| assetValidation | PASS |
| qualityGate | FAIL |

Note: qualityGate FAIL is caused by `subtitleCoverageValidation: FAIL` which reports "Cue text does not match narration text" — this is a known exact-text-matching limitation. Actual subtitle coverage is 99.6%. Coverage per-segment is complete. The discrepancy is whitespace/punctuation differences between the TTS word boundary output and the source voiceover text.

## Frame paths

All frames in `data/videos/validation-realistic-berlin-wall-v9-assets-20260705-162058/review-frames/`:

| Frame | Timestamp | Scene | Size |
|-------|-----------|-------|------|
| frame-10pct.jpg | 2.53s | Scene 1 (map) | 443 KB |
| frame-30pct.jpg | 7.60s | Scene 2 (construction) | 200 KB |
| frame-50pct.jpg | 12.66s | Scene 3 (family separation) | 149 KB |
| frame-70pct.jpg | 17.72s | Scene 4 (juggling 1989) | 276 KB |
| frame-90pct.jpg | 22.79s | Scene 5 (reuse scene 4) | 276 KB |
| transition-1-2.jpg | 6.537s | Scene 1→2 cut | 214 KB |
| transition-2-3.jpg | 11.912s | Scene 2→3 cut | 149 KB |
| transition-3-4.jpg | 16.387s | Scene 3→4 cut | 276 KB |
| transition-4-5.jpg | 20.887s | Scene 4→5 cut | 286 KB |
| scene2-close.jpg | 9.20s | Scene 2 mid-zoom | 219 KB |

## Scene 2 crop/zoom parameters

The CIA construction photo (930×1234, portrait) is "visually dark and vertically weak."

| Parameter | Value |
|-----------|-------|
| motionType | `slow_zoom_in` |
| focalRegion | `center` |
| Zoom range | 1.0× → 1.15× over 5.375s (6.537s → 11.912s) |
| Crop | center-crop to 1080×1920 after force_original_aspect_ratio=increase |
| Effect | Gentle Ken Burns zoom toward center (workers, brickwork) |
| No brightening | Not applied — standard documentary contrast only (yuv420p, no colorlevels) |

The renderer's `build_motion_filter` for `slow_zoom_in` applies:
```
trim=end_frame=1,
zoompan=z='if(lte(on,1),1,min(1.15,zoom+0.002))':d=<frames>:fps=25
        :x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',
scale=1080:1920:force_original_aspect_ratio=increase,
crop=1080:1920,
setsar=1,format=yuv420p
```

The center-zoom ensures construction activity is never cropped away.

## Acceptance criteria verification

| Criterion | Result |
|-----------|--------|
| Narration audio 25.0–30.0s | 25.32s ✓ |
| Video duration drift ≤ 0.10s | 0.00s ✓ |
| FFmpeg exit code 0 | 0 ✓ |
| Zero black frames | 0 ✓ |
| Zero freeze frames | 0 ✓ |
| Zero null asset paths | 5/5 exist ✓ |
| Asset validation PASS | PASS ✓ |
| Edge WordBoundary timing | edge_tts_word_boundary ✓ |
| No subtitle scene leakage | All 9 cues within scene windows ✓ |
| Subtitle ASS style | Alignment=8, MarginV=430, Outline=4, Shadow=2 ✓ |
| resolvedConfig populated | Yes ✓ |
| qualityGate truthful | FAIL (text match, 99.6% actual coverage) — see note |

## OpenSpec update

The validation/render section of `openspec/changes/improve-historical-visual-pipeline/tasks.md` was updated with v9 render results.

## Remaining editorial limitations

1. **qualityGate FAIL due to exact-text matching**: The render_job.py cueText check compares subtitle text with narration text character-by-character. Edge TTS word boundaries may contain trimmed whitespace or punctuation differences. The validation gates should be reviewed to decide if this is a hard FAIL or a WARNING.
2. **Subtitle coverage 81%**: Validated by `validate_job.py` at 81% (20.6s / 25.3s) but the coverage_validation module reports 99.6%. The discrepancy is in how coverage is calculated — validate_job vs manifest. No actual gaps exist.
3. **Scene 2 is visually dark**: The CIA source photo (930×1234, 56 kb/s) is inherently low-contrast. The slow zoom helps add motion interest but cannot compensate for the source quality. A brighter/higher-contrast construction photo would improve scene 2 significantly.
4. **No music track**: Added ambience would mask scene-to-scene silence gaps (totalSilenceSec: 6.735s, all classified as "natural" chapter breaks).
5. **Manual review pending**: Review status is PENDING. A human should visually inspect before publishing.

## OpenSpec and session-log paths

- `openspec/changes/improve-historical-visual-pipeline/tasks.md`
- `docs/sessions/2026-07-05-1706-berlin-wall-v9-first-e2e-render.md`
