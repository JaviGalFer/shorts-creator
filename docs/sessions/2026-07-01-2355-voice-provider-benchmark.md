# Session: Voice Provider Benchmark

**Date**: 2026-07-01 23:55
**Job**: `la-2026-07-01-173458` (La caída de Constantinopla) — used as reference narration
**OpenSpec**: `voice-provider-benchmark`

## Goal

Reproducibly compare multiple TTS providers using the exact same narration text (Constantinopla voiceover, ~27s) to select a primary voice for historical Shorts. Do not modify assets, render pipeline, subtitles, timing, or duration.

## Baseline

Current production voice: `edge_tts` → `es-ES-AlvaroNeural` (free, local, no API key).

## Providers to evaluate

| # | Provider | Status | Notes |
|---|----------|--------|-------|
| 1 | edge_tts (AlvaroNeural) | **Available** | Current baseline |
| 2 | ElevenLabs | **API key configured** | `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID=Xb7hH8MSUJpSbSDYk0k2`, model `eleven_multilingual_v2` — verify commercial license of plan |
| 3 | Google Cloud TTS | **Not configured** | Adapter prepared, marked `PENDIENTE_DE_VALIDAR` |
| 4 | Azure Speech | **Not configured** | Adapter prepared, marked `PENDIENTE_DE_VALIDAR` |
| 5 | Piper (local) | **Not installed** | Documented as optional offline fallback |

## Benchmark text (concatenated voiceover)

```
Un día en 1453, Constantinopla cayó y con ella un imperio milenario.
La ciudad fue asediada por el sultán Mehmed II y su ejército otomano.
Los habitantes de la ciudad enfrentaron un destino aterrador durante el asedio.
El 29 de mayo, las murallas cedieron. Constantinopla estaba perdida.
La caída de Constantinopla cambió el curso de la historia mundial.
Si quieres saber más sobre la historia, ¡síguenos para más contenido!
```

## What to measure per provider

- Audio file saved to `data/benchmarks/voice-provider-benchmark/`
- Duration (seconds)
- Silence detection (leading/trailing/internal) — requires ffmpeg for accurate decoding; noted as pending
- Sample rate, channels, bitrate
- File size
- Timing support (word-level, sentence-level, none)
- Cost estimate per 1k chars / monthly quota
- Commercial usage status (license)
- Fallback priority (lower = preferred)

## Deliverables

- Comparison table in `design.md` and session log
- Recommendation: primary voice + fallback
- No change to production voice until human review of samples

## Files created

- `openspec/changes/voice-provider-benchmark/proposal.md`
- `openspec/changes/voice-provider-benchmark/design.md`
- `openspec/changes/voice-provider-benchmark/tasks.md`
- `openspec/changes/voice-provider-benchmark/specs/tts-provider-interface.md`
- `bin/tts_provider.py` (interface + 5 implementations)
- `bin/benchmark_voice_providers.py` (benchmark runner)

## Benchmark Execution (2026-07-02)

**Available providers**: 2 (edge_tts + ElevenLabs)
**PENDIENTE_DE_VALIDAR**: 3 (Google TTS, Azure Speech, Piper)

### Results

| Provider | Voice | Duration | SRate | Size | Timing | Cost/1k | Commercial |
|----------|-------|----------|-------|------|--------|---------|------------|
| edge_tts | Alvaro Neural | 30.86s | 24000 | 180.8KB | sentence | $0 | allowed |
| elevenlabs | Multilingual v2 | 31.43s | 44100 | 491.5KB | word | $0.30 | **unknown** |

- ElevenLabs speaks ~0.57s slower on 424 chars
- ElevenLabs produces higher sample rate (44100 vs 24000) → larger files
- Word-level timing available in ElevenLabs vs sentence-level in edge_tts

### Recommendation
- **Primary**: edge_tts (es-ES-AlvaroNeural) — free, reliable, commercial cleared
- **Fallback**: ElevenLabs (if commercial license confirmed) → Google TTS (Neural2-A) → Azure Speech → Piper
- ElevenLabs commercial status needs human verification via ElevenLabs account plan page
- **Do not switch production voice** until human review

## Not modified

- Assets, render pipeline, subtitles, timing, image pipeline, duration
- Production metadata/job