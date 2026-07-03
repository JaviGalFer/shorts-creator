# Session: E2E whisper test + manifest with --skip-render + path verification

**Date:** 2026-07-02 21:00
**Goal:** Prove full pipeline: whisper integration, manifest with relative paths, validation without Docker

## Commands executed

### 1. ffprobe check
```
$ which ffprobe || true
ffprobe not found
```
Result: NOT installed locally. All ffprobe-dependent checks will use WARNING/skipped.

### 2. Create isolated test job
```
JOB_ID=la-whisper-e2e-2026-07-02-2000
mkdir -p data/videos/$JOB_ID/scenes
cp data/videos/la-2026-07-01-173458/metadata.json → modify jobId, clear validation/review
cp data/videos/la-2026-07-01-173458/scenes/*.jpg data/videos/$JOB_ID/scenes/
cp data/videos/la-2026-07-01-173458/scenes/narration.mp3 data/videos/$JOB_ID/scenes/
```
Result: 12 JPG assets + narration.mp3 copied. jobId rewritten. Status=PREPARED.

### 3. Run generate_audio.py with whisper
```
WHISPER_MODEL=tiny .venv/bin/python3 bin/generate_audio.py \
  data/videos/la-whisper-e2e-2026-07-02-2000/metadata.json \
  --continuous --tts-provider edge_tts --subtitle-provider whisper
```
Result: **13 cues**, **whisper_word_timestamps**, **confidence=high**, no fallback.
All 6 scenes have `timingSource=whisper_word_timestamps`.

### 4. Generate subtitle.ass
```
.venv/bin/python3 bin/prepare_job.py \
  data/videos/la-whisper-e2e-2026-07-02-2000/metadata.json
```
Result: subtitle.ass with 13 Dialogue lines.

### 5. Generate manifest with --skip-render
```
.venv/bin/python3 bin/render_job.py \
  data/videos/la-whisper-e2e-2026-07-02-2000/metadata.json \
  --skip-validation --skip-asset-validation --skip-render
```
Result: manifest generated at `job-manifest.json`. No Docker/FFmpeg required.

### 6. Verify paths programmatically
```
subtitles.provider=whisper_word_timestamps       ← CORRECT
outputVideoPath=relative OK                        ← CORRECT
subtitles.path=relative OK                          ← CORRECT
scene 1 visualPath=relative OK                      ← CORRECT (was absolute before fix)
scene 1 audioPath=relative OK                       ← CORRECT
scenes in manifest=6, in metadata=6                 ← MATCH
```
ALL CHECKS PASSED. No absolute paths.

### 7. Run validate_job.py
```
.venv/bin/python3 bin/validate_job.py metadata.json --verbose
.venv/bin/python3 bin/validate_job.py metadata.json --json
```
Results:
- 12 assets OK
- subtitle.ass: 13 Dialogue lines, non-overlapping
- Audio: WARNING (ffprobe unavailable, skipped)
- Video resolution: WARNING (video.mp4 not found, expected --skip-render)
- Manifest: valid structure
- 1 ERROR: "Continuous audio duration is 0" (metadata config, not a tool bug)
- 0 Docker-related errors
- 0 path-related errors

## Technical changes in this session

### `--skip-render` flag added to `render_job.py`
New CLI flag that skips FFmpeg render, post-render validation, audio validation, and coverage validation. Sets safe defaults for all render-dependent fields. Manifest generation runs unconditionally.

### `_resolve_relative()` in `_get_scene_visual_info()` (re-verified)
Previously the fix existed but was unverified against a fresh manifest. This session confirmed: all visualPath values in the generated manifest are relative to `project_root`.

## OpenSpec updated
- `tasks.md`: Phase 8 updated with e2e evidence, --skip-render, path verification
- `design.md`: Added --skip-render flag docs under Decisions
- Proposal stays `awaiting review` (render + visual review still blocked)

## Still blocked
1. Docker render — `sudo dockerd` requires interactive password (non-interactive terminal)
2. Visual review of rendered subtitles — depends on Docker render
3. `audioDurationSec` / `video resolution` verification with ffprobe — depends on Docker

## Job location
`data/videos/la-whisper-e2e-2026-07-02-2000/` — safe copy, original untouched.
