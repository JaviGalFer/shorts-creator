# Design

`pipeline.orchestrator` coordinates bounded attempts after the initial audio stage. `rendering.preparer.project_render_duration()` is the shared source for `activeAudioDurationSec` (falling back to `durationSec`) plus scene tail policy. `contracts.duration` decides PASS, EXPAND, or COMPRESS without provider inputs.

On repair, the script domain requests only scene voiceovers and validates the resulting V2 script. The audio domain receives explicit `force_regenerate=True`, replacing per-scene MP3s and subtitle timing. Assets are never re-fetched. Exhaustion after two repairs records `REVIEW_REQUIRED` and `DURATION_FITTING_EXHAUSTED`; prepare is not run.

The post-TTS word target is operational guidance. Actual regenerated audio is re-measured on every attempt.
