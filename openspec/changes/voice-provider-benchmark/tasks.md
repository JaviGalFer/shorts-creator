# Tasks: Voice Provider Benchmark

## Phase 1 — Interface & Specification
- [x] Create `TTSProvider` interface in `openspec/changes/voice-provider-benchmark/specs/tts-provider-interface.md`
- [x] Document provider metadata fields, timing support levels, commercial status enum

## Phase 2 — Provider Adapters
- [x] Implement `EdgeTTSProvider` (baseline, `es-ES-AlvaroNeural`)
- [x] Implement `ElevenLabsProvider` (check `ELEVENLABS_API_KEY`, verify commercial license)
- [x] Implement `GoogleTTSProvider` (adapter only, mark `PENDIENTE_DE_VALIDAR`)
- [x] Implement `AzureSpeechProvider` (adapter only, mark `PENDIENTE_DE_VALIDAR`)
- [x] Implement `PiperProvider` (adapter only, mark `PENDIENTE_DE_VALIDAR`)

## Phase 3 — Benchmark Script
- [x] Create `bin/benchmark_voice_providers.py`
  - Load benchmark text from Constantinopla job
  - Iterate available providers
  - Synthesize audio files
  - Measure: duration, silence, sample rate, file size
  - Save `benchmark_results.json` + `comparison_table.md`

## Phase 4 — Execution & Measurement
- [x] Run benchmark for all **available** providers
- [ ] Verify commercial usage status for ElevenLabs (check plan via API or docs)
- [x] Generate comparison table

## Phase 5 — Documentation & Decision
- [x] Update `openspec/changes/voice-provider-benchmark/tasks.md` with results
- [x] Update session log with findings
- [x] Recommend primary voice + fallback
- [x] **Do not** change production voice until human review of audio samples

## Out of Scope (not in this change)
- [ ] Production voice switch in `generate_audio.py`
- [ ] Pipeline integration
- [ ] Timing data integration with subtitle system

## Benchmark Results

| Provider | Voice | Duration | SRate | Size(KB) | Timing | Cost/1k | Commercial | Priority |
|----------|-------|----------|-------|----------|--------|---------|------------|----------|
| edge_tts | Alvaro Neural | 30.86s | 24000 | 180.8 | sentence | $0.000 | allowed | 1 |
| elevenlabs | Multilingual v2 | 31.43s | 44100 | 491.5 | word | $0.300 | **unknown** | 2 |
| google_tts | Neural2 A | — | — | — | word | $0.016 | allowed | 3 (PENDIENTE) |
| azure_speech | Alvaro Neural | — | — | — | word | $0.016 | allowed | 4 (PENDIENTE) |
| piper | Carlfm x-low | — | — | — | none | $0.000 | allowed | 5 (PENDIENTE) |

## Recommendation
- **Primary**: edge_tts (es-ES-AlvaroNeural) — free, reliable, commercial use allowed, 30.86s duration
- **Fallback**: ElevenLabs (if commercial license confirmed) → Google TTS → Azure → Piper
- **Note**: ElevenLabs duration 31.43s vs 30.86s for edge_tts → ElevenLabs speaks slightly slower. Quality comparison requires human listening.
- **Note**: Silence detection requires ffmpeg locally (not available in this environment). Human review should verify leading/trailing silence.