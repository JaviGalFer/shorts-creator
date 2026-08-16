# Agent Context

## Runtime
- Modular V2 architecture is complete: `bin/run_job.py` orchestrates `script -> assets -> audio -> prepare -> render -> validate`; `bin/` are CLI adapters over `src/shorts_creator/` domains.
- n8n is legacy/alternative infrastructure, not the canonical orchestrator.
- TTS and visual providers are replaceable; Edge TTS is currently the default and Wikimedia/Pixabay are current visual providers.

## Verified State
- `main` base: `66ae15e`; active branch: `change/generic-duration-fitting`.
- `modular-v2-migration`: closed. `AUDIO_DURATION_MISSING`: resolved. Host `ffprobe` remains absent; Docker fallback is used.
- First complete technical E2E: `cmo-2026-08-16-172847`, through `VALIDATED`; request 30s, range 27-30, timeline 20.813s, MP4 approximately 20.88s.
- Real E2E attempt `cmo-2026-08-16-184819` was blocked at script: a legacy bootstrap WPM hard gate rejected a V2-valid 67-word candidate (37.9s estimate) before TTS. The gate is now non-blocking; WPM remains bootstrap telemetry only.
- `generic-duration-fitting` Slices 1, 2, Slice 2 hardening, and Slice 3 are completed. Slice 3 separates render-duration integrity from final MP4 requested-duration compliance; an out-of-range technically valid MP4 ends `REVIEW_REQUIRED`. Full suite: `1267 passed, 0 failed`.
- Slice 2 runtime hardening reuses script-domain LLM `.env` resolution and preserves the prior audio provider/voice/timing configuration on regeneration. The per-scene multi-provider TTS runtime remains outside this change.
- Main baseline before this active change: `1215 passed, 0 failed`. Branch full suite after Slice 3: `1267 passed, 0 failed`.
- Branch full suite after bootstrap fix: `1216 passed, 51 skipped, 0 failed`. Next exact step: `python3 bin/run_job.py --topic "Cómo se forma un arcoíris" --duration 30 --verbose`.
