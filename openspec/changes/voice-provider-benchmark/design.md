# Design: Voice Provider Benchmark

## 1. TTSProvider Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class TTSOptions:
    voice: str
    rate: Optional[str] = None      # e.g., "+0%", "-10%"
    pitch: Optional[str] = None     # e.g., "+0Hz", "-5Hz"
    volume: Optional[str] = None    # e.g., "+0dB"
    format: str = "wav"             # "wav" | "mp3"
    sample_rate: int = 24000

@dataclass
class TTSResult:
    audio_path: str
    duration_sec: float
    sample_rate: int
    channels: int
    bitrate_kbps: int
    file_size_bytes: int
    silence_leading_sec: float
    silence_trailing_sec: float
    silence_internal_sec: float
    timing_data: Optional[dict] = None  # word/sentence timestamps if supported

@dataclass
class ProviderMetadata:
    provider_name: str
    voice_id: str
    voice_name: str
    language: str
    timing_support: str          # "word" | "sentence" | "none"
    cost_per_1k_chars_usd: float
    monthly_quota_chars: int
    commercial_usage_status: str  # "allowed" | "restricted" | "unknown"
    fallback_priority: int        # lower = preferred (1 = primary)

class TTSProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        pass

    @abstractmethod
    def synthesize(self, text: str, output_path: str, options: TTSOptions) -> TTSResult:
        pass

    @abstractmethod
    def supported_voices(self) -> list[dict]:
        pass

    def is_available(self) -> bool:
        return True
```

## 2. Provider Implementations

### 2.1 edge_tts (baseline)
- **Voice**: `es-ES-AlvaroNeural` (configurable)
- **Timing**: sentence boundaries via `Communicate.stream_sync()`
- **Cost**: Free (local)
- **Commercial**: Allowed
- **Priority**: 1 (baseline)

### 2.2 ElevenLabs
- **Voice**: `ELEVENLABS_VOICE_ID` (default `Xb7hH8MSUJpSbSDYk0k2`)
- **Model**: `eleven_multilingual_v2`
- **Timing**: word-level via `enable_logging` or webhook
- **Cost**: ~$0.30/1k chars (Starter), ~$0.24/1k (Creator+)
- **Commercial**: **Verify plan** — Free tier = non-commercial only
- **Priority**: 2 (if commercial license confirmed)

### 2.3 Google Cloud TTS (adapter ready)
- **Voice**: `es-ES-Neural2-A` / `es-ES-Standard-A`
- **Timing**: word-level via `timepoint_type=SSML_MARK`
- **Cost**: ~$16/1M chars (Neural2), ~$4/1M (Standard)
- **Commercial**: Allowed with billing enabled
- **Priority**: 3
- **Status**: `PENDIENTE_DE_VALIDAR` — requires `GOOGLE_APPLICATION_CREDENTIALS`

### 2.4 Azure Speech (adapter ready)
- **Voice**: `es-ES-AlvaroNeural` / `es-ES-ElviraNeural`
- **Timing**: word-level via `SpeechSynthesizer` + `WordBoundary`
- **Cost**: ~$16/1M chars (Neural), ~$4/1M (Standard)
- **Commercial**: Allowed with subscription
- **Priority**: 4
- **Status**: `PENDIENTE_DE_VALIDAR` — requires `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION`

### 2.5 Piper (local, optional)
- **Voice**: `es_ES-carlfm-x_low` (or similar)
- **Timing**: none (sentence-level via Piper JSON output)
- **Cost**: Free (local, offline)
- **Commercial**: Allowed (MIT/Apache voices)
- **Priority**: 5
- **Status**: `PENDIENTE_DE_VALIDAR` — requires `piper` binary + voice model

## 3. Benchmark Text

Concatenated voiceover from Constantinopla job (6 scenes, ~400 chars, ~27s):

```
Un día en 1453, Constantinopla cayó y con ella un imperio milenario.
La ciudad fue asediada por el sultán Mehmed II y su ejército otomano.
Los habitantes de la ciudad enfrentaron un destino aterrador durante el asedio.
El 29 de mayo, las murallas cedieron. Constantinopla estaba perdida.
La caída de Constantinopla cambió el curso de la historia mundial.
Si quieres saber más sobre la historia, ¡síguenos para más contenido!
```

## 4. Benchmark Output

Directory: `data/benchmarks/voice-provider-benchmark/`
- `{provider}_{voice}.wav` — lossless reference
- `{provider}_{voice}.mp3` — compressed (192kbps)
- `benchmark_results.json` — structured metrics
- `comparison_table.md` — human-readable table

## 5. Comparison Table Schema

| Provider | Voice | Duration | Silence (L/T/I) | Sample Rate | Timing | Cost/1k | Quota | Commercial | Status | Priority |
|----------|-------|----------|-----------------|-------------|--------|---------|-------|------------|--------|----------|