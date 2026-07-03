# TTS Provider Interface Specification

## Abstract Base

```python
class TTSProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        """Provider identity and capabilities."""

    @abstractmethod
    def synthesize(self, text: str, output_path: str, options: TTSOptions) -> TTSResult:
        """Generate audio from text. Returns path and metrics."""

    @abstractmethod
    def supported_voices(self) -> list[dict]:
        """List of available voices for this provider."""

    def is_available(self) -> bool:
        """Whether credentials/config are present. Override for API-bound providers."""
        return True
```

## Data Classes

### ProviderMetadata

| Field | Type | Description |
|-------|------|-------------|
| `provider_name` | str | Unique key, e.g. `elevenlabs` |
| `voice_id` | str | Voice identifier for synthesis calls |
| `voice_name` | str | Human-readable voice name |
| `language` | str | BCP-47 tag, e.g. `es-ES` |
| `timing_support` | str | `"word"`, `"sentence"`, or `"none"` |
| `cost_per_1k_chars_usd` | float | Estimated cost per 1000 characters |
| `monthly_quota_chars` | int | Free/included monthly quota |
| `commercial_usage_status` | str | `"allowed"`, `"restricted"`, or `"unknown"` |
| `fallback_priority` | int | Lower = preferred (1 = primary) |

### TTSOptions

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `voice` | str | required | Voice ID/name |
| `rate` | str | `"+0%"` | Speaking rate adjustment |
| `pitch` | str | `"+0Hz"` | Pitch adjustment |
| `volume` | str | `"+0dB"` | Volume adjustment |
| `format` | str | `"wav"` | `"wav"` or `"mp3"` |
| `sample_rate` | int | `24000` | Audio sample rate |

### TTSResult

| Field | Type | Description |
|-------|------|-------------|
| `audio_path` | str | Final output path |
| `duration_sec` | float | Audio duration |
| `sample_rate` | int | Sample rate |
| `channels` | int | Number of channels |
| `bitrate_kbps` | int | Bitrate |
| `file_size_bytes` | int | File size |
| `silence_leading_sec` | float | Initial silence before speech |
| `silence_trailing_sec` | float | Post-speech silence |
| `silence_internal_sec` | float | Total silence between sentences |
| `timing_data` | dict or None | Word/sentence timestamps if available |

## Timing Support Levels

| Level | Meaning | Example Providers |
|-------|---------|-------------------|
| `word` | Each word has start/end timestamp | ElevenLabs, Google TTS, Azure Speech |
| `sentence` | Sentence-level boundary events only | edge_tts (SentenceBoundary) |
| `none` | No timing data, duration only | Piper |

## Commercial Status Enum

| Status | Meaning |
|--------|---------|
| `allowed` | License permits commercial use (check specific plan) |
| `restricted` | Non-commercial only, attribution required, or limited |
| `unknown` | Not verified — requires human legal review |

## Fallback Priority

| Priority | Meaning |
|----------|---------|
| 1 | Primary (most natural, best commercial terms) |
| 2 | Secondary (good quality, different provider) |
| 3+ | Tertiary (free fallback, offline, emergency) |
