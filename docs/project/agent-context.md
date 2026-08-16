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
- Real E2E `cmo-2026-08-16-190441`: old `--duration 30` resolved asymmetrically to 27-30. Fitting compressed 30.587s then accepted 27.314s; MP4 was 27.36s. Target-centered presets/custom duration now resolve `30` to 27-33, so 30.587s is PASS.
- `quick_30` E2E `cmo-2026-08-16-194012`: one repair, projected 31.587s, MP4 31.72s, requested-duration PASS, `VALIDATED`. `deep_60` E2E `cmo-2026-08-16-194540` exhausted fitting after 5 fixed scenes; adaptive scene planning now resolves 60s to 9-11 scenes (prefer 10).
- Adaptive scene planning runtime hardening passes the persisted plan to retry prompts and voiceover repairs; deep_60 repairs can validate the 9-11 scene structure. Minimum supported 20s resolves coherently to preferred/min 4, max 5.
- `generic-duration-fitting` Slices 1, 2, Slice 2 hardening, and Slice 3 are completed. Slice 3 separates render-duration integrity from final MP4 requested-duration compliance; an out-of-range technically valid MP4 ends `REVIEW_REQUIRED`. Full suite: `1267 passed, 0 failed`.
- Slice 2 runtime hardening reuses script-domain LLM `.env` resolution and preserves the prior audio provider/voice/timing configuration on regeneration. The per-scene multi-provider TTS runtime remains outside this change.
- Main baseline before this active change: `1215 passed, 0 failed`. Branch full suite after Slice 3: `1267 passed, 0 failed`.
- Branch full suite after adaptive runtime hardening: `1213 passed, 51 skipped, 0 failed`. The skips were legacy bootstrap-compression convergence tests.
- Canonical deep_60 E2E `cmo-2026-08-16-203059`: 60.37s MP4, 9 scenes (adaptive plan 9-11, prefer 10), 2 voiceover repairs, requested-duration PASS, `VALIDATED`. The failed 5-scene `cmo-2026-08-16-194540` stays as historical context for adaptive scene planning.
- generic-duration-fitting: COMPLETED / VERIFIED / CLOSED. Obsolete bootstrap-compression tests retired (23 deleted, 28 unskipped); `resolvedConfig.scenePlan` is preserved from the request; the CLI `durationContractStatus` line now reports the persisted bootstrap contract. Full suite on close: `1243 passed, 0 skipped, 0 failed`.
