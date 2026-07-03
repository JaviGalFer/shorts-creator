# Session: Docker unblocked + full render with whisper reconciliation + validation PASS

**Date:** 2026-07-03 19:30
**Goal:** Unblock Docker render, do full render with reconciled whisper, verify everything

## Discovery: Docker was running all along

Docker daemon was running (server v24.0.6) but `docker info` failed because the client sent
API version 1.52 while the server only supports up to 1.43 (due to Docker Desktop + WSL2).

The project code had `DOCKER_API_VERSION=1.44` hardcoded. Fix: changed to `1.43` and set
globally via `os.environ` at the start of `main()` in `render_job.py`, `generate_audio.py`,
and `validate_job.py`.

## Full render pipeline

Job: `la-whisper-reconciled-2026-07-02-2100`

1. **generate_audio.py --subtitle-provider whisper**
   - 13 cues, source=whisper_reconciled, confidence=high
   - 3 unmatched words (Mehmed, II, cedieron.) → interpolated
   - Text displayed is CANONICAL (no "tomano", "cederon", "Mehmet dos")
   - `audioDurationSec=30.864` via Docker ffprobe

2. **prepare_job.py** → subtitle.ass with 13 Dialogue lines

3. **render_job.py** (real Docker render)
   - 10 segments, 30.86s expected duration
   - FFmpeg exit 0
   - Black frame warnings: 0
   - Freeze frame warnings: 0
   - Audio validation technical: PASS
   - Coverage status: PASS
   - Status: RENDERED

4. **validate_job.py --verbose**
   - 12 assets OK
   - Audio: 30.9s (narration.mp3)
   - 13 non-overlapping subtitle cues
   - Cue alignment: all 13 cues within scene windows
   - Video resolution: 1080x1920 OK
   - **Result: PASS** (0 errors, 1 warning for coverage gap)

5. **Validation frames extracted** (5 frames at 0/25/50/75/95%)
   - frame_0pct.png: "Un día en 1453," (Scene 1)
   - frame_25pct.png: "La ciudad fue asediada por el sultán" (Scene 2)
   - frame_75pct.png: "La caída de Constantinopla cambió el curso" (Scene 5)
   - frame_95pct.png: "¡síguenos para más contenido!" (Scene 6)
   - All subtitles in correct scenes, no ASR errors

## Files modified (Docker fix)

- `bin/render_job.py`: Added `os.environ['DOCKER_API_VERSION'] = '1.43'` in main()
- `bin/generate_audio.py`: Added `os.environ['DOCKER_API_VERSION'] = '1.43'` in main_async()
- `bin/validate_job.py`: Added `os.environ['DOCKER_API_VERSION'] = '1.43'` in main()

## OpenSpec

All technical tasks completed. Proposal can be considered for closure after visual
review by a human (validation frames available for inspection).
