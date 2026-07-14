# Proposal: improve-short-form-audio-pacing-v2

## Problem

Pipeline renders videos with ~50.9% silence because:
1. ffprobe (Docker) fails due to client/server version mismatch (`DOCKER_API_VERSION` not set)
2. When MP3 duration cannot be measured, `targetDurationSec=6` (LLM-invented) is used as scene window
3. `apad` + `atrim` pad each scene to 6s regardless of actual audio length
4. No pacing validation exists in qualityGate

## Solution

**Phase A (this build):**
- Fix Docker ffprobe by setting `DOCKER_API_VERSION=1.43`
- Store real measured MP3 durations with `durationSource` provenance
- Block pipeline when durations cannot be measured (never fall back to targetDurationSec)
- New scene window formula: `sceneWindowSec = actualAudioDurationSec + sceneTailPauseSec` (0.35s)
- Pacing validation with silence metrics
- Re-render existing job `cmo-2026-07-14-180923`

**Phase B (future):**
- Per-voice WPM calibration
- Word budget adjustment
- Edge TTS rate configuration
- Full E2E at 27–30s

## Status

- Phase A: In Progress
- Phase B: Pending
