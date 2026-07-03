# Session: TTS refactor, Whisper subtitles, manifest, and validation

**Date**: 2026-07-02 12:00
**OpenSpec**: `improve-tts-subtitle-alignment-and-job-validation`

## Objective

Implement 5 technical improvements:
1. TTS configurable with TTSProvider abstraction (no direct edge_tts in pipeline)
2. Whisper subtitle alignment with word-level grouping
3. Standardized job-manifest.json
4. Standalone validate_job.py
5. Visual type normalization (image|video) with backward compatibility

## Initial state

- `tts_provider.py` existed with `TTSProvider` ABC, EdgeTTSProvider, ElevenLabsProvider (+ 3 adapters)
- `generate_audio.py` still imported `edge_tts` directly in `generate_audio_with_timestamps()`
- `whisper_subtitles.py` existed with basic whisper integration
- `render_job.py` had basic manifest generation at end
- No standalone validator script
- No visual.type normalization
- No env var configuration for TTS/Whisper

## Files inspected

| File | Lines | Purpose |
|------|-------|---------|
| `bin/generate_audio.py` | 573 | Audio generation with edge_tts coupling |
| `bin/tts_provider.py` | 368 | TTSProvider abstraction (existing) |
| `bin/whisper_subtitles.py` | 135 | Whisper subtitle alignment (existing) |
| `bin/prepare_job.py` | 551 | ASS subtitle generation |
| `bin/render_job.py` | 801 | FFmpeg render + manifest generation |
| `bin/generate_script.py` | 352 | LLM script generation |
| `bin/asset_validation.py` | 379 | Asset quality gate |
| `docs/project/architecture.md` | 128 | Architecture docs |
| `docs/project/environment.md` | 54 | Environment docs |
| `.env.example` | 57 | Env template |
| `requirements.txt` | 14 | Python deps |
| `openspec/changes/improve-historical-visual-pipeline/tasks.md` | 127 | Previous OpenSpec |

## Changes made

### 1. `bin/tts_provider.py` — synthesize_with_timing()

- Added `synthesize_with_timing()` to `TTSProvider` base class (default: calls `synthesize()`)
- Implemented `EdgeTTSProvider.synthesize_with_timing()` with streaming WordBoundary/SentenceBoundary capture
- Moved the streaming logic from `generate_audio.py` into the provider

### 2. `bin/generate_audio.py` — Refactored to use TTSProvider

- Removed direct `import edge_tts` and `SubMaker`
- `generate_audio_with_timestamps()` now calls `provider.synthesize_with_timing()`
- Added env var loading for `TTS_PROVIDER`, `TTS_VOICE`, `SUBTITLE_PROVIDER`
- `main_async()` now uses env defaults for CLI `--voice`, `--tts-provider`, `--subtitle-provider`
- Removed `async` from `main_async()` (no more `asyncio.run()` needed inside)
- No longer imports `asyncio` in the main flow (edge_tts streaming is inside `tts_provider.py`)

### 3. `bin/whisper_subtitles.py` — Refined word grouping

- Improved `_group_words_into_cues()` with:
  - 2-7 words per cue (flush at end-of-sentence, pause >0.4s, 7 words max)
  - Merge very short cues (<0.7s) into previous
  - Split very long cues (>4.0s) into two
- Added `WHISPER_MODEL` env var support (default: `tiny`)
- Added file existence check before whisper transcription
- Better blank audio filtering

### 4. `bin/render_job.py` — Improved manifest generation

- Added helper functions `_get_subtitle_provider()`, `_get_scene_audio_info()`, `_get_scene_visual_info()`
- Manifest now includes proper scene-level audio/visual info
- Uses relative paths throughout
- Handles continuous and per-scene audio correctly

### 5. `bin/validate_job.py` — New standalone validator

Created comprehensive validation script checking:
- Assets exist per scene (handles segments and flat assets)
- Audio exists per scene (continuous and per-scene)
- Zero-size file detection
- Duration validation (per-scene and total)
- ASS subtitle validity (headers, dialogue lines)
- Subtitle cue overlap detection
- Subtitle coverage percentage
- job-manifest.json structure
- Video resolution via ffprobe (1080x1920)
- Human-readable report + JSON output
- Non-zero exit code on errors

### 6. `bin/visual_normalize.py` — New module

- `normalize_scene_visual()`: adds visual.type, path, fit, motion
- Backward compatible with legacy fields (`visualPath`, `motionType`, no `visual` field)
- `asset_path_for_scene()`: resolves asset path for any scene format
- `normalize_all_scenes()`: batch normalization

### 7. `requirements.txt` — Whisper dependency documented

- Added comment section for optional `faster-whisper`

### 8. `.env.example` — New variables

- Added `TTS_PROVIDER`, `TTS_VOICE`, `SUBTITLE_PROVIDER`, `WHISPER_MODEL`

### 9. `docs/project/environment.md` — Updated

- Added TTS configuration table
- Added Whisper configuration table
- Added installation instructions for faster-whisper
- Documented fallback behavior

### 10. `docs/project/architecture.md` — Updated

- Added job-manifest.json schema
- Added visual.type normalization section
- Added validation section
- Added TTS config section
- Added Whisper section

### 11. OpenSpec — Created

- `openspec/changes/improve-tts-subtitle-alignment-and-job-validation/`
- `proposal.md`, `design.md`, `tasks.md`

## Decisions

1. **synthesize_with_timing() as optional**: Not all TTS providers support word-level timing. The base class provides a default that calls `synthesize()` without timing data. Providers that support timing override.

2. **Env vars as defaults, CLI as override**: `TTS_VOICE` and `TTS_PROVIDER` from `.env` set the CLI defaults. `--voice` and `--tts-provider` on command line override.

3. **Whisper fallback is silent recovery**: If whisper is not installed, a clear warning is printed and the pipeline continues with `estimated`. No pipeline breakage.

4. **validate_job.py is standalone**: Does not depend on render pipeline code. Uses ffprobe via Docker for resolution checks.

5. **visual.type normalization is non-destructive**: The normalization function reads legacy fields and produces modern structure, but does not modify the original metadata unless explicitly called.

## Dependencies

| Dependency | Status | Install |
|-----------|--------|---------|
| `edge-tts` | Required | `pip install edge-tts` |
| `faster-whisper` | Optional | `pip install faster-whisper` |

## Commands executed

None (all changes are code modifications, no runtime execution needed for validation)

## Pending

1. Run `validate_job.py` against an existing RENDERED job to verify all checks pass
2. Manual visual review of job-manifest.json and subtitles
3. Verify `--subtitle-provider whisper` end-to-end when faster-whisper is installed
4. Verify backward compatibility with jobs without visual.type

## OpenSpec status

**awaiting review** — `openspec/changes/improve-tts-subtitle-alignment-and-job-validation/`
- proposal.md: created
- design.md: created
- tasks.md: in progress (most tasks completed, pending validation)

---

## Correction (2026-07-02 19:00)

This session log initially stated "None (all changes are code modifications, no runtime execution
needed for validation)" which was inaccurate — actual runtime execution IS needed for validation.

See `docs/sessions/2026-07-02-1900-verify-tts-whisper-validation.md` for the actual verification with
real command output and evidence.
