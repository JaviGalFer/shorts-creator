# Agent Context

## Runtime
- Modular V2 architecture is complete: `bin/run_job.py` orchestrates `script -> assets -> audio -> prepare -> render -> validate`; `bin/` are CLI adapters over `src/shorts_creator/` domains.
- n8n is legacy/alternative infrastructure, not the canonical orchestrator.
- TTS and visual providers are replaceable; Edge TTS is currently the default and Wikimedia/Pixabay are current visual providers.

## Verified State
- `main` base: `66ae15e`; active branch: `change/generic-duration-fitting`.
- `modular-v2-migration`: closed. `AUDIO_DURATION_MISSING`: resolved. Host `ffprobe` remains absent; Docker fallback is used.
- First complete technical E2E: `cmo-2026-08-16-172847`, through `VALIDATED`; request 30s, range 27-30, timeline 20.813s, MP4 approximately 20.88s.
- `generic-duration-fitting` Slice 1 and Slice 2 are completed with focal simulated validation. Slice 2 performs provider-neutral post-TTS bounded fitting (two repairs maximum), forced audio regeneration, and asset reuse. Slice 3, MP4 requested-duration compliance separate from render integrity, is next.
- Slice 2 runtime hardening reuses script-domain LLM `.env` resolution and preserves the prior audio provider/voice/timing configuration on regeneration. The per-scene multi-provider TTS runtime remains outside this change.
- Main baseline before this active change: `1215 passed, 0 failed`. This branch has focused tests only, not a full-suite run.
