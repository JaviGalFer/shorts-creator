# Design

`generate_audio_with_timestamps()` now accepts a keyword-only `tts_provider`
(default `edge_tts`) and builds the provider via the registry:
`provider = get_provider(tts_provider, voice=voice)`. No provider name is
hardcoded inside the generation function. `main_per_scene()` forwards its
received `tts_provider` to each per-scene call.

`generate_audio()` resolves the selected provider and validates availability
for every provider uniformly via `provider.is_available()`. Unknown providers
fail explicitly from the registry error. Missing ElevenLabs credentials resolve
to an unavailable provider and fail explicitly with no silent Edge fallback and
no secret persistence.

Continuous mode remains Edge-specific in the final design. At the `generate_audio()`
boundary, `continuous` with any non-Edge provider fails with
`CONTINUOUS_TTS_PROVIDER_UNSUPPORTED` before any synthesis or metadata
mutation, so no audio is ever generated with a provider different from the one
requested.

Timing metadata reflects actual capability: Edge emits native word boundaries
and reports `timing_support="word"`. ElevenLabs implements native timing via
the `/with-timestamps` endpoint and reports `timing_support="word"`; its
`normalized_alignment`/`alignment` output is normalized into the canonical
`timing_data["word_boundaries"]` (startSec/endSec/text) and
`timing_data["timing_source"]` contract. Both providers are validated per
scene.

`activeDurationSource` is renamed to the provider-neutral
`subtitle_timing_last_cue_plus_guard`; the algorithm (last cue end plus
`SPEECH_END_GUARD_SEC`, capped by physical duration) is unchanged.

Runtime config is resolved once at the `generate_audio()` boundary: effective
voice (`explicit --voice → provider-specific env → generic default`),
provider-specific secrets/model (project `.env` then process env), and the
same resolved config is passed to both the availability check and each
per-scene synthesis so initial and regenerated audio use identical provider and
voice. ElevenLabs voice config (`ELEVENLABS_VOICE_ID`) wins over the implicit
Edge default; the API key never reaches metadata.

Future providers normalize their native output into the same canonical form;
Edge baseline and measured-duration fitting are unaffected.