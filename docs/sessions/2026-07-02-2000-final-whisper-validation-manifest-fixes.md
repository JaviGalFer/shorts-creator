# Session: Final whisper validation + manifest fixes + ffprobe independence

**Date:** 2026-07-02 20:00
**Goal:** Resolve remaining blockers on OpenSpec `improve-tts-subtitle-alignment-and-job-validation`

## Tasks completed

### 1. Fixed absolute paths in `_get_scene_visual_info()` (render_job.py:749-752)

Added `_resolve_relative()` helper that converts any absolute path to relative-to-`project_root`. This ensures `visualPath` in `job-manifest.json` is always portable.

Relevant code: `render_job.py` lines 741-758 (post-fix).

### 2. Made `validate_job.py` independent of Docker for ffprobe

Replaced `_docker_ffprobe_duration()` and `_docker_ffprobe_resolution()` with:

- `_run_local_ffprobe()` — tries `shutil.which("ffprobe")`, calls directly
- `_run_docker_ffprobe()` — fallback to `linuxserver/ffmpeg:latest`
- `_get_ffprobe_duration()` → returns `float | None`
- `_get_ffprobe_resolution()` → returns `tuple[int,int] | None`

Callers emit WARNING and skip the check when both local and Docker ffprobe are unavailable.

### 3. Installed and tested faster-whisper

```bash
.venv/bin/pip install faster-whisper
→ Success (v1.2.1)
```

Test: transcribed `scene-01.mp3` (copied from `la-2026-07-01-173458`) using `WHISPER_MODEL=tiny`:
- Source: `whisper_word_timestamps`
- Confidence: `high`
- 2 cues produced with accurate timestamps

### 4. Docker attempt (blocked)

`sudo dockerd` requires interactive password — non-interactive terminal, cannot proceed. Docker-based render and visual review remain blocked.

## Updated OpenSpec

- `tasks.md`: Marked whisper real test as ✅, added entries for path fix and ffprobe independence
- `design.md`: Added "Decisions (Jul 2 2026)" section documenting path format and ffprobe strategy

## Remaining blockers

1. **Docker render**: blocked by sudo password requirement
2. **Visual review**: depends on render being complete
3. **audioDurationSec/video resolution with Docker**: blocked

**Proposal cannot be closed.** Keep "awaiting review" until Docker render + visual review are completed.
