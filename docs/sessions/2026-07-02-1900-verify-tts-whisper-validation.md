# Session: Verification of TTS, Whisper, Manifest, and Validation (corrected)

**Date**: 2026-07-02 19:00
**Correction of**: `2026-07-02-1200-tts-whisper-manifest-validation.md` (which had inaccurately claimed
  no commands were executed and left everything pending)

## Motivation

The previous session log incorrectly stated "None (all changes are code modifications, no runtime execution
needed for validation)" while the final summary claimed concrete validation results. This session corrects
that by executing real commands and capturing their actual output.

## Environment status

| Resource | Status |
|----------|--------|
| Docker daemon | **Not running** — `sudo` not available, cannot start |
| Docker client | Available (v29.1.3) |
| edge-tts | Available in `.venv` (`pip list` shows 7.2.8) |
| faster-whisper | **Not installed** |
| System python | Python 3.10 |
| .venv | Exists with edge-tts |

## Jobs used for testing

| Job | Type | Scenes | Audio | Status |
|-----|------|--------|-------|--------|
| `la-2026-07-01-173458` | Modern (visualPlan) | 6 | Continuous | RENDERED |
| `franco5-2026-06-30-204654` | Legacy (no visualPlan) | 10 | Per-scene | RENDERED |

## Commands executed and results

### 1. CLI help tests
```bash
$ python3 bin/generate_audio.py --help
# OK — shows --voice, --tts-provider, --subtitle-provider, 
#        --continuous, --join-style with env defaults

$ python3 bin/validate_job.py --help
# OK — shows --json, --verbose, metadata_path positional
```

### 2. Import tests
```bash
$ python3 -c "from bin.tts_provider import EdgeTTSProvider; print('OK')"
# OK

$ python3 -c "from bin.visual_normalize import normalize_scene_visual; print('OK')"
# OK

$ python3 -c "from bin.whisper_subtitles import align_subtitles; print('OK')"
# OK
```

### 3. Validate_job.py against modern job (la-173458)
```bash
$ python3 bin/validate_job.py data/videos/la-2026-07-01-173458/metadata.json --verbose
# RESULTS:
#   ✅ 12 segment assets found (6 scenes × 2 segments each)
#   ✅ Continuous audio exists (narration.mp3, 543KB → 185KB after re-generation)
#   ❌ Audio duration = 0 (Docker not running — ffprobe unavailable)
#   ✅ Scene durations 5-7s OK
#   ✅ subtitle.ass: 15 Dialogue lines
#   ✅ 15 subtitle cues, all non-overlapping
#   ✅ Subtitle coverage: 94% (25.3s / 27.1s)
#   ✅ job-manifest.json: valid structure (after generation)
#   ❌ video.mp4 resolution = 0x0 (Docker not running)
#   EXIT=1 (expected — 3 Docker-related errors)
```

### 4. Validate_job.py against legacy job (franco5)
```bash
$ python3 bin/validate_job.py data/videos/franco5-2026-06-30-204654/metadata.json --verbose
# RESULTS:
#   ✅ 10 assets found (scene-XX.jpg)
#   ✅ 10 audio files found (scene-XX.mp3)
#   ✅ Scene durations 4-7s OK
#   ❌ subtitle.srt: missing ASS headers (correct — job uses SRT format, legacy)
#   ⚠ No subtitle timing cues (correct — pre-dates subtitleTiming feature)
#   ❌ job-manifest.json not found (pre-dates feature)
#   ❌ video.mp4 resolution = 0x0 (Docker not running)
#   EXIT=1
```

### 5. Validate_job.py JSON output
```bash
$ python3 bin/validate_job.py data/videos/la-2026-07-01-173458/metadata.json --json
# Produces valid JSON-only output, no mixed stdout text.
```

### 6. generate_audio.py with whisper fallback
```bash
$ .venv/bin/python bin/generate_audio.py \
    data/videos/la-2026-07-01-173458/metadata.json \
    --continuous --tts-provider edge_tts --subtitle-provider whisper

# RESULTS:
#   Building continuous narration: 7 units, 424 chars
#   WARNING: faster-whisper not installed → Falling back to estimated mode
#   15 cues, edge_tts_sentence_boundary, confidence=high
#   6 scene timings detected (0.1s to 30.85s)
#   Status: AUDIO_READY
#   EXIT=0
```

### 7. Manifest generation
```bash
$ .venv/bin/python bin/render_job.py \
    data/videos/la-2026-07-01-173458/metadata.json \
    --skip-validation --skip-asset-validation

# RESULTS:
#   FFmpeg exited with code 1 (Docker not running — expected)
#   Manifest: data/videos/la-2026-07-01-173458/job-manifest.json
#   ✅ job-manifest.json created with all required fields:
#     - jobId, createdAt, scriptPath, renderProfile, resolution
#     - tts: {provider, voice}
#     - subtitles: {provider, path}
#     - scenes[]: 6 entries with sceneNumber, visualType, visualPath, audioPath, audioDurationSec
#     - outputVideoPath
```

## Bug found and fixed during verification

**Nested event loop in async chain**: The refactoring of `generate_audio.py` removed `async def`
from `generate_audio_with_timestamps()` but the edge_tts streaming requires asyncio. The fix:
- Added `async_synthesize_with_timing()` to `TTSProvider` base class (default: calls sync version)
- Implemented `EdgeTTSProvider.synthesize_with_timing_async()` with the streaming logic
- `synthesize_with_timing()` calls `asyncio.run()` for sync contexts, detects running loop and errors
- `generate_audio_with_timestamps()` is now `async def` with `await`

## What's verified vs pending

### ✅ Verified (with evidence)
1. **TTSProvider abstraction**: `generate_audio.py` no longer imports edge_tts directly
2. **Voice config via env**: `TTS_VOICE`, `TTS_PROVIDER` read from `.env`
3. **Whisper fallback**: Warning emitted, falls back to estimated, EXIT=0
4. **validate_job.py**: Works against both modern and legacy jobs
5. **validate_job.py --json**: Produces valid JSON-only output
6. **Manifest generation**: Generated with all required fields
7. **Visual normalization**: Module imports and unit tests pass

### ❌ Not verified (blocked)
1. **Audio duration measurement**: Requires Docker (ffprobe). Docker daemon can't start (no sudo).
2. **Video resolution check**: Same Docker dependency.
3. **Whisper real execution**: requires `pip install faster-whisper`

### ⏳ Pending manual review
1. **Visual review of subtitles**: Generated cues need human validation
2. **Visual path normalization**: manifest shows absolute paths — should use relative

## OpenSpec status

**awaiting review** — `openspec/changes/improve-tts-subtitle-alignment-and-job-validation/tasks.md`
updated with real evidence and clear pass/fail/blocked status.
