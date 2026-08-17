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

Slice 3:
- [ ] Real provider validation (opt-in keyed) / closure.