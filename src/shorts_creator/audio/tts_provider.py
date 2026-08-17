#!/usr/bin/env python3
"""TTSProvider interface — production-ready abstraction over TTS engines.

Usage:
    from shorts_creator.audio.tts_provider import get_provider, TTSOptions
    provider = get_provider("edge_tts", voice="es-ES-AlvaroNeural")
    result = provider.synthesize("Hola mundo", "output.mp3", TTSOptions())
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
from abc import ABC, abstractmethod
import wave
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Callable


@dataclass
class TTSOptions:
    voice: str = ""
    rate: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+0dB"
    format: str = "wav"
    sample_rate: int = 24000


@dataclass
class TTSResult:
    audio_path: str
    duration_sec: float
    sample_rate: int
    channels: int
    bitrate_kbps: int
    file_size_bytes: int
    silence_leading_sec: float = 0.0
    silence_trailing_sec: float = 0.0
    silence_internal_sec: float = 0.0
    timing_data: Optional[dict] = None
    provider: str = ""
    voice: str = ""


@dataclass
class ProviderMetadata:
    provider_name: str
    voice_id: str
    voice_name: str
    language: str
    timing_support: str
    cost_per_1k_chars_usd: float
    monthly_quota_chars: int
    commercial_usage_status: str
    fallback_priority: int


class TTSProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        pass

    @abstractmethod
    def synthesize(self, text: str, output_path: str, options: TTSOptions) -> TTSResult:
        pass

    def synthesize_with_timing(self, text: str, output_path: str,
                                options: TTSOptions) -> TTSResult:
        result = self.synthesize(text, output_path, options)
        return result

    async def synthesize_with_timing_async(self, text: str, output_path: str,
                                            options: TTSOptions) -> TTSResult:
        return self.synthesize_with_timing(text, output_path, options)

    @abstractmethod
    def supported_voices(self) -> list[dict]:
        pass

    def is_available(self) -> bool:
        return True


def _measure_audio(audio_path: str, provider: str, voice: str) -> TTSResult:
    from mutagen.mp3 import MP3
    from mutagen.wave import WAVE
    from mutagen import File as MutagenFile
    path = Path(audio_path)
    size = path.stat().st_size

    sr = 24000
    ch = 1
    dur = 0
    bitrate = 128

    try:
        mf = MutagenFile(str(path))
        if mf is not None:
            if hasattr(mf, 'info'):
                dur = mf.info.length if hasattr(mf.info, 'length') and mf.info.length else 0
                sr = getattr(mf.info, 'sample_rate', 24000)
                ch = getattr(mf.info, 'channels', 1)
                br = getattr(mf.info, 'bitrate', 128000)
                bitrate = br // 1000
    except Exception:
        try:
            with wave.open(str(path), 'r') as wf:
                sr = wf.getframerate()
                ch = wf.getnchannels()
                frames = wf.getnframes()
                dur = frames / sr if sr > 0 else 0
                bitrate = (sr * ch * wf.getsampwidth() * 8) // 1000
        except Exception:
            pass

    return TTSResult(
        audio_path=audio_path,
        duration_sec=round(dur, 3),
        sample_rate=sr,
        channels=ch,
        bitrate_kbps=max(bitrate, 1),
        file_size_bytes=size,
        provider=provider,
        voice=voice,
    )


# ──────────────────────────────────────────────
# 1. edge_tts — baseline (available)
# ──────────────────────────────────────────────

TICK = 10_000_000  # edge-tts ticks per second (100ns units)


class EdgeTTSProvider(TTSProvider):
    def __init__(self, voice: str = "es-ES-AlvaroNeural"):
        self._voice = voice

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_name="edge_tts",
            voice_id=self._voice,
            voice_name="Alvaro Neural",
            language="es-ES",
            timing_support="word",
            cost_per_1k_chars_usd=0.0,
            monthly_quota_chars=0,
            commercial_usage_status="allowed",
            fallback_priority=1,
        )

    def supported_voices(self) -> list[dict]:
        return [{"voice": self._voice, "language": "es-ES", "name": "Alvaro Neural"}]

    def is_available(self) -> bool:
        try:
            import edge_tts
            return True
        except ImportError:
            return False

    def synthesize(self, text: str, output_path: str, options: TTSOptions) -> TTSResult:
        import edge_tts
        voice = options.voice or self._voice
        rate = options.rate

        async def _run():
            communicate = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
            await communicate.save(output_path)

        asyncio.run(_run())
        result = _measure_audio(output_path, "edge_tts", voice)
        return result

    def synthesize_with_timing(self, text: str, output_path: str,
                                options: TTSOptions) -> TTSResult:
        try:
            asyncio.get_running_loop()
            in_async = True
        except RuntimeError:
            in_async = False
        if in_async:
            raise RuntimeError(
                "synthesize_with_timing() called from async context. "
                "Use await provider.synthesize_with_timing_async() instead."
            )
        return asyncio.run(self.synthesize_with_timing_async(text, output_path, options))

    async def synthesize_with_timing_async(self, text: str, output_path: str,
                                            options: TTSOptions) -> TTSResult:
        import edge_tts
        from edge_tts import SubMaker
        voice = options.voice or self._voice
        rate = options.rate

        sentence_boundaries = []
        submaker = SubMaker()

        communicate = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
        with open(output_path, "wb") as f:
            async for chunk in communicate.stream():
                ctype = chunk.get("type")
                if ctype == "audio":
                    data = chunk.get("data")
                    if data:
                        f.write(data)
                elif ctype == "WordBoundary":
                    submaker.feed(chunk)
                elif ctype == "SentenceBoundary":
                    sentence_boundaries.append({
                        "offset": chunk.get("offset", 0),
                        "duration": chunk.get("duration", 0),
                        "text": chunk.get("text", ""),
                    })

        word_boundaries = []
        if submaker.cues:
            for cue in submaker.cues:
                word_boundaries.append({
                    "startSec": cue.start.total_seconds(),
                    "endSec": cue.end.total_seconds(),
                    "text": cue.content,
                })

        result = _measure_audio(output_path, "edge_tts", voice)
        result.timing_data = {
            "word_boundaries": word_boundaries,
            "sentence_boundaries": sentence_boundaries,
            "timing_source": "edge_tts_word_boundary" if word_boundaries
                             else "edge_tts_sentence_boundary",
        }
        return result


# ──────────────────────────────────────────────
# 2. ElevenLabs — available if API key present
# ──────────────────────────────────────────────

class ElevenLabsProvider(TTSProvider):
    def __init__(self, api_key: str | None = None,
                 voice_id: str = "Xb7hH8MSUJpSbSDYk0k2",
                 model_id: str = "eleven_multilingual_v2"):
        self._api_key = api_key or os.getenv("ELEVENLABS_API_KEY", "")
        self._voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID", "Xb7hH8MSUJpSbSDYk0k2")
        self._model_id = model_id or os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_name="elevenlabs",
            voice_id=self._voice_id,
            voice_name="ElevenLabs Multilingual v2",
            language="es-ES",
            timing_support="none",
            cost_per_1k_chars_usd=0.30,
            monthly_quota_chars=10000,
            commercial_usage_status="unknown",
            fallback_priority=2,
        )

    def supported_voices(self) -> list[dict]:
        return [{"voice": self._voice_id, "model": self._model_id, "name": "ElevenMultilingual v2"}]

    def is_available(self) -> bool:
        return bool(self._api_key)

    def synthesize(self, text: str, output_path: str, options: TTSOptions) -> TTSResult:
        import requests
        if not output_path.endswith(".mp3"):
            output_path += ".mp3"
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self._voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self._api_key,
        }
        payload = {
            "text": text,
            "model_id": self._model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }
        r = requests.post(url, json=payload, headers=headers, timeout=120)
        r.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(r.content)

        result = _measure_audio(output_path, "elevenlabs", self._voice_id)
        return result


# ──────────────────────────────────────────────
# 3. Google Cloud TTS — adapter only (PENDIENTE)
# ──────────────────────────────────────────────

class GoogleTTSProvider(TTSProvider):
    ADAPTER_ONLY = True

    def __init__(self):
        self._creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_name="google_tts",
            voice_id="es-ES-Neural2-A",
            voice_name="Neural2 A",
            language="es-ES",
            timing_support="word",
            cost_per_1k_chars_usd=0.016,
            monthly_quota_chars=1000000,
            commercial_usage_status="allowed",
            fallback_priority=3,
        )

    def supported_voices(self) -> list[dict]:
        return [
            {"voice": "es-ES-Neural2-A", "language": "es-ES", "name": "Neural2 A"},
            {"voice": "es-ES-Standard-A", "language": "es-ES", "name": "Standard A"},
        ]

    def is_available(self) -> bool:
        return False

    def synthesize(self, text: str, output_path: str, options: TTSOptions) -> TTSResult:
        raise NotImplementedError("GoogleTTSProvider: PENDIENTE_DE_VALIDAR — requires GOOGLE_APPLICATION_CREDENTIALS")


# ──────────────────────────────────────────────
# 4. Azure Speech — adapter only (PENDIENTE)
# ──────────────────────────────────────────────

class AzureSpeechProvider(TTSProvider):
    ADAPTER_ONLY = True

    def __init__(self):
        self._key = os.getenv("AZURE_SPEECH_KEY", "")
        self._region = os.getenv("AZURE_SPEECH_REGION", "")

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_name="azure_speech",
            voice_id="es-ES-AlvaroNeural",
            voice_name="Alvaro Neural",
            language="es-ES",
            timing_support="word",
            cost_per_1k_chars_usd=0.016,
            monthly_quota_chars=500000,
            commercial_usage_status="allowed",
            fallback_priority=4,
        )

    def supported_voices(self) -> list[dict]:
        return [
            {"voice": "es-ES-AlvaroNeural", "language": "es-ES", "name": "Alvaro Neural"},
            {"voice": "es-ES-ElviraNeural", "language": "es-ES", "name": "Elvira Neural"},
        ]

    def is_available(self) -> bool:
        return False

    def synthesize(self, text: str, output_path: str, options: TTSOptions) -> TTSResult:
        raise NotImplementedError("AzureSpeechProvider: PENDIENTE_DE_VALIDAR — requires AZURE_SPEECH_KEY + AZURE_SPEECH_REGION")


# ──────────────────────────────────────────────
# 5. Piper — adapter only (PENDIENTE)
# ──────────────────────────────────────────────

class PiperProvider(TTSProvider):
    ADAPTER_ONLY = True

    def __init__(self):
        self._binary = os.getenv("PIPER_BINARY", "piper")
        self._model = os.getenv("PIPER_MODEL", "es_ES-carlfm-x_low")

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_name="piper",
            voice_id="es_ES-carlfm-x_low",
            voice_name="Carlfm x-low",
            language="es-ES",
            timing_support="none",
            cost_per_1k_chars_usd=0.0,
            monthly_quota_chars=0,
            commercial_usage_status="allowed",
            fallback_priority=5,
        )

    def supported_voices(self) -> list[dict]:
        return [{"voice": "es_ES-carlfm-x_low", "language": "es-ES", "name": "Carlfm x-low"}]

    def is_available(self) -> bool:
        try:
            subprocess.run([self._binary, "--help"], capture_output=True, timeout=5)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def synthesize(self, text: str, output_path: str, options: TTSOptions) -> TTSResult:
        raise NotImplementedError("PiperProvider: PENDIENTE_DE_VALIDAR — requires piper binary + voice model")


# ──────────────────────────────────────────────
# Provider registry
# ──────────────────────────────────────────────

def get_all_providers() -> dict[str, TTSProvider]:
    return {
        "edge_tts": EdgeTTSProvider(),
        "elevenlabs": ElevenLabsProvider(),
        "google_tts": GoogleTTSProvider(),
        "azure_speech": AzureSpeechProvider(),
        "piper": PiperProvider(),
    }


def get_available_providers() -> dict[str, TTSProvider]:
    return {k: v for k, v in get_all_providers().items() if v.is_available()}


def get_provider(name: str = "edge_tts", voice: str = "es-ES-AlvaroNeural",
                 **kwargs) -> TTSProvider:
    providers = {
        "edge_tts": lambda: EdgeTTSProvider(voice=voice),
        "elevenlabs": lambda: ElevenLabsProvider(voice_id=voice, **kwargs),
    }
    if name not in providers:
        raise ValueError(f"Unknown TTS provider: {name}. Available: {list(providers.keys())}")
    return providers[name]()
