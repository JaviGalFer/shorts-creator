# Design

`pipeline.orchestrator` coordinates bounded attempts after the initial audio stage. `rendering.preparer.project_render_duration()` is the shared source for `activeAudioDurationSec` (falling back to `durationSec`) plus scene tail policy. `contracts.duration` decides PASS, EXPAND, or COMPRESS without provider inputs.

On repair, the script domain requests only scene voiceovers and validates the resulting V2 script. The audio domain receives explicit `force_regenerate=True`, replacing per-scene MP3s and subtitle timing. Assets are never re-fetched. Exhaustion after two repairs records `REVIEW_REQUIRED` and `DURATION_FITTING_EXHAUSTED`; prepare is not run.

Runtime hardening reuses the script domain's LLM resolution (including `.env`) and passes the previous audio provider, voice, and timing configuration explicitly to regeneration. This preserves configuration without expanding the existing per-scene multi-provider synthesis runtime.

The post-TTS word target is operational guidance. Actual regenerated audio is re-measured on every attempt.

Bootstrap WPM and the word budget remain initial prompt guidance and telemetry. A structurally valid V2 script is persisted as `SCRIPT_DRAFT` even when its estimated duration is out of range; the subsequent audio stage supplies the authoritative measurement.

Duration presets are a product convenience only. The canonical contract resolves to target/min/max/tolerance and the fitting/final MP4 contracts consume only those numbers. Custom durations use a deterministic symmetric approximately-10% tolerance, without selecting or clamping to a legacy profile.

Initial scene planning is also duration-derived: preferred count is target seconds divided by six with half-up rounding, and the accepted range is preferred minus/plus one with an absolute minimum of four. Repairs remain voiceover-only and never alter this initial scene structure.

Runtime hardening carries the persisted scene plan into retry instructions and post-TTS repair validation. For existing metadata the orchestrator uses `resolvedConfig.scenePlan`, then `request.scenePlan`, and finally the historical validator fallback.
