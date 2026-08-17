# Generic TTS Provider Runtime

## Problem
The per-scene TTS runtime selects `edge_tts` unconditionally inside
`generate_audio_with_timestamps()`. The configured provider from the request,
CLI, or environment is persisted to metadata but never reaches synthesis, so
ElevenLabs and other providers cannot be used at runtime.

## Objective
Make the per-scene TTS runtime genuinely provider-agnostic: the selected
provider reaches synthesis, timing data flows through one canonical contract,
Edge remains the validated default, and ElevenLabs becomes the second real
provider.

## Scope
- **Slice 1 (this change):** provider pass-through + generic per-scene runtime selection.
  - Thread `tts_provider` through `generate_audio_with_timestamps()` and `main_per_scene()`.
  - Consistent availability validation for all providers; no silent Edge fallback.
  - Continuous mode rejects non-Edge providers explicitly (`CONTINUOUS_TTS_PROVIDER_UNSUPPORTED`).
  - Correct provider metadata: Edge `timing_support="word"`; ElevenLabs `timing_support="none"` until Slice 2.
  - Provider-neutral `activeDurationSource`.
  - Focused mocked tests.
- **Slice 2:** ElevenLabs native `/with-timestamps` + character-to-word normalization.
- **Slice 3:** real provider validation / closure.

## Out of scope
Google TTS, Azure Speech, Piper, voice cloning, voice browser/UI, music, assets,
semantic asset scoring, motion, publishing, n8n, API/web UI, duration algorithm
changes, scene planning changes, provider-specific WPM tuning. Continuous mode
remains Edge-specific in Slice 1.