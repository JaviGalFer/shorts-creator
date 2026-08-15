"""Temporary compatibility facade for canonical audio TTS providers."""

from _package_bootstrap import ensure_src_on_path

ensure_src_on_path()

from shorts_creator.audio.tts_provider import (
    EdgeTTSProvider,
    ProviderMetadata,
    TTSOptions,
    TTSProvider,
    TTSResult,
    _measure_audio,
    get_all_providers,
    get_available_providers,
    get_provider,
)

__all__ = [
    "EdgeTTSProvider",
    "ProviderMetadata",
    "TTSOptions",
    "TTSProvider",
    "TTSResult",
    "_measure_audio",
    "get_all_providers",
    "get_available_providers",
    "get_provider",
]
