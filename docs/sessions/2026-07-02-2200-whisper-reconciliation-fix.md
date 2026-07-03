# Session: Fix Whisper reconciliation bugs + scene alignment + skip-render state

**Date:** 2026-07-02 22:00
**Goal:** Fix functional bugs in whisper subtitle pipeline

## Bugs detected in `la-whisper-e2e-2026-07-02-2000`

1. **Scene assignment bug**: Cue at 0.00s ("Un día en 1453") assigned to scene 6 (fallback to last scene). Cue at 26.24s ("Si quieres saber...") assigned to scene 5 instead of 6.
2. **ASR errors in subtitles**: "Mehmet dos" instead of "Mehmed II", "tomano" instead of "otomano", "cederon" instead of "cedieron".
3. **Word duplication in alignment**: `_align_words_to_canonical()` had two sequential `if best_idx is not None` blocks causing each matched word to be appended twice.

## Fixes applied

### 1. Reconciliation (`whisper_subtitles.py`)

New function `align_with_canonical_text()` replaces the old `align_subtitles()`:
- Transcribes audio with Whisper (word-level timestamps)
- Per-scene word alignment: for each scene, matches Whisper words to canonical voiceover words using fuzzy greedy matching (exact → substring → interpolated)
- Returns `cues_by_scene` dict (per-scene cues with canonical text)
- Reports warnings for unmatched words (e.g. "Mehmed", "II", "cedieron" not found in Whisper transcript)

Old `align_subtitles()` kept as deprecated wrapper for backward compatibility.

### 2. Scene assignment (`generate_audio.py`)

Replaced the flat-cues-with-sceneNumber approach with per-scene `cues_by_scene` dict:
- Each scene's cues are assigned directly via reconciliation
- No more `cue["sceneNumber"] = scene_timings[-1]["sceneNumber"]` fallback
- Scene timing windows respected with 0.5s margin

### 3. Word alignment fix (`whisper_subtitles.py`)

Fixed double-append bug: two sequential `if best_idx is not None` blocks were calling `aligned.append()` twice per matched word, causing word duplication. Replaced with single `if/else` chain.

### 4. `--skip-render` state (`render_job.py`)

Changed `data["status"] = "RENDERED"` → `data["status"] = "RENDER_SKIPPED"` in the `--skip-render` block.

### 5. `tts.voice` in manifest (`generate_audio.py` + `render_job.py`)

- Added `"voice": voice` to `audio_entry` in `generate_audio.py`
- Changed manifest to read `audio_config.get("voice", "")` instead of hardcoded `""`

### 6. Asset path resolution (`render_job.py`)

`_get_scene_visual_info()` now prefers assets within the job's own `scenes/` directory before falling back to external paths. Makes jobs self-contained when assets are available locally.

### 7. New validation check (`validate_job.py`)

Added `_check_subtitle_alignment()` check that verifies:
- Each cue's timestamps are within its scene's time window (±0.5s margin)
- No duplicate cue text across scenes
- Text similarity between cue text and scene voiceover (WARNING if <30%)
- Global ordering of cues with cross-scene overlap detection

## E2E test job

`data/videos/la-whisper-reconciled-2026-07-02-2100/`

### Results

| Scene | Cues | Similarity | Time window respected |
|-------|------|-----------|----------------------|
| 1 | 2 | 100% | ✅ |
| 2 | 2 | 100% | ✅ |
| 3 | 2 | 100% | ✅ |
| 4 | 3 | 100% | ✅ |
| 5 | 2 | 100% | ✅ |
| 6 | 2 | 100% | ✅ |

- **No ASR errors** in displayed text ("Mehmed II", "otomano", "cedieron" all correct)
- **No misassigned cues** (scene 6 has only its own text)
- **No word duplication** (single-append per word)
- **Status: RENDER_SKIPPED** (not RENDERED)
- **tts.voice: es-ES-AlvaroNeural** (not empty)
- **subtitle.provider: whisper_reconciled**
- **validate_job.py**: alignment check PASSES, 13 cues within windows

## Remaining blockers

1. Docker render (sudo password) — for visual review + ffprobe validation
2. Visual review of subtitles
3. `audioDurationSec` / `video resolution` via Docker

## Files modified

- `bin/whisper_subtitles.py` — added `align_with_canonical_text()`, fixed word alignment double-append
- `bin/generate_audio.py` — uses new reconciliation, stores `voice` in audio entry
- `bin/render_job.py` — `RENDER_SKIPPED` for --skip-render, reads `tts.voice` from audio_config, self-contained asset paths
- `bin/validate_job.py` — new `subtitle-alignment` check

## OpenSpec

Proposal stays `awaiting review`.
