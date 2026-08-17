# Tasks

Slice 1 (this change):
- [x] Thread `tts_provider` through `generate_audio_with_timestamps()` and `main_per_scene()`; remove hardcoded Edge selection.
- [x] Validate provider availability uniformly; fail explicitly on missing credentials / unknown provider.
- [x] Guard continuous mode: reject non-Edge providers before synthesis or metadata mutation.
- [x] Correct metadata: Edge `timing_support="word"`, ElevenLabs `timing_support="none"`.
- [x] Rename `activeDurationSource` to provider-neutral `subtitle_timing_last_cue_plus_guard`.
- [x] Update subtitle-timing CLI help text (auto = prefer native provider timing).
- [x] Add focused mocked tests in `tests/test_generic_tts_provider_runtime.py`.
- [x] Edge continuous path unchanged; non-Edge continuous fails explicitly.

Slice 2 (this change):
- [x] ElevenLabs native `/with-timestamps` via `synthesize_with_timing_async()`.
- [x] Character-to-word boundary normalization into canonical `word_boundaries`.
- [x] Advertise `timing_support="word"` only after real normalization is implemented.
- [x] Pure normalizer + validation; normalized>raw alignment priority.
- [x] Remove Edge fallback-label leak in the generic generator.
- [x] ElevenLabs `__init__` env precedence fix.
- [x] Runtime config hardening: resolve provider-specific voice/secrets/model from project `.env` then process env; provider voice wins over implicit Edge default; consistent provider construction across availability check and synthesis; non-string alignment chars and malformed base64 guarded.

Slice 3:
- [x] Run real ElevenLabs smoke: PASSED (`ELEVENLABS_REAL_SMOKE_OK`, voice `Xb7hH8MSUJpSbSDYk0k2`, 3.84s, `elevenlabs_normalized_alignment`, 10 word boundaries).
- [ ] Full real E2E through the canonical `run_job.py` pipeline (pending; requires plumbing of TTS job config into the orchestrator command surface).
- [x] `cmo-2026-08-17-142952` reclassified as an Edge regression E2E (not ElevenLabs validation): history records `--tts-provider edge_tts --voice es-ES-AlvaroNeural` in fitting regeneration; root cause was the missing `run_job` surface + hardcoded `request.voice`, fixed by this change.