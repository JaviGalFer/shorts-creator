# Tasks

- [x] Slice 1: implement pure post-TTS fitting and generic voiceover repair.
- [x] Slice 1: decouple repair from bootstrap WPM budget.
- [x] Slice 2: share prepare projection semantics with fitting.
- [x] Slice 2: add bounded orchestration loop and force audio regeneration.
- [x] Slice 2: add focused simulated loop tests.
- [x] Slice 2 hardening: preserve LLM and audio runtime configuration.
- [x] Slice 3: add MP4 requested-duration compliance and separate final gates.
- [x] Remove the bootstrap estimate as a canonical script-stage duration gate.
- [x] Add target-centered presets, custom tolerance, and final-stage status persistence.
- [x] Canonical E2Es already validate: quick_30 `cmo-2026-08-16-194012` (31.72s) and deep_60 `cmo-2026-08-16-203059` (60.37s, 9 scenes). No new E2E needed; existing evidence is authoritative.
