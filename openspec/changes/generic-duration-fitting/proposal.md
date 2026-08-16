# Generic Duration Fitting

## Problem
The first technical E2E (`cmo-2026-08-16-172847`) completed through `VALIDATED`, but a request for 30s (range 27-30) produced a 20.813s timeline and an approximately 20.88s MP4. Bootstrap WPM is not authoritative after TTS has measured real audio.

## Objective
Fit duration generically across provider, voice, language, and future TTS implementations using measured audio, bounded voiceover-only repair, and no provider-specific policy.

## Scope
- Slice 1: post-TTS PASS/EXPAND/COMPRESS contract, 0.70-1.50 ratio policy, per-scene distribution, generic repair. **Completed.**
- Slice 2: projected-duration loop, maximum two repairs, forced TTS regeneration, retained assets. **Completed; focal simulated tests passed.**
- Slice 2 runtime hardening: script `.env` LLM reuse and preservation of audio provider/voice/timing configuration. **Completed.**
- Slice 3: MP4 `requestedDurationCompliance`, separate from render integrity, manifest/status gates. **Completed; full suite passed.**

## Out of scope
Provider calibration history, perceptual pacing, asset semantics, music, UI, n8n, and a real E2E validation of the completed fitting loop.
