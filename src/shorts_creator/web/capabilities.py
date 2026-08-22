"""Derivation of /capabilities from canonical runtime sources.

Never hardcodes provider lists, visual modes, or presets. Values come from
the canonical enums, contracts, capability registry, and audio defaults.
No API keys, secrets, env values, or provider diagnostics are exposed.
"""

from __future__ import annotations

from shorts_creator.assets.capabilities import (
    PROVIDER_CAPABILITIES,
    ProviderCapability,
)
from shorts_creator.assets.router import ALLOWED_ASSET_PREFERENCES
from shorts_creator.audio.generator import get_audio_defaults
from shorts_creator.audio.tts_provider import get_all_providers
from shorts_creator.contracts.duration import (
    DEFAULT_DURATION_PRESET,
    DURATION_PRESETS,
    SUPPORTED_DURATION_MAX,
    SUPPORTED_DURATION_MIN,
)
from shorts_creator.contracts.visual_media import (
    ALLOWED_MEDIA_PREFERENCES,
    ALLOWED_VISUAL_MODES,
)
from shorts_creator.web.dto import (
    CapabilitiesResponse,
    DurationCapabilitiesResponse,
    DurationPresetResponse,
    ProviderCapabilityResponse,
    TtsProviderCapabilityResponse,
    VoiceCapabilitiesResponse,
)


def build_capabilities() -> CapabilitiesResponse:
    defaults = get_audio_defaults()
    default_tts = defaults.get("tts_provider", "edge_tts")

    providers = [
        ProviderCapabilityResponse(
            id=cap.capability_id,
            provider=cap.provider,
            media_kind=cap.media_kind,
            source_type=cap.source_type,
            query_strategy=cap.query_strategy,
            runtime_status=cap.runtime_status,
            requires_api_key=cap.requires_api_key,
        )
        for cap in PROVIDER_CAPABILITIES
    ]

    presets = [
        DurationPresetResponse(id=preset_id, target_sec=spec["targetSec"])
        for preset_id, spec in sorted(DURATION_PRESETS.items())
    ]

    available_tts = set(get_all_providers().keys())
    tts_providers = [
        TtsProviderCapabilityResponse(
            id=pid,
            default=pid == default_tts,
            available=pid in available_tts,
        )
        for pid in sorted(available_tts | {default_tts})
    ]

    elevenlabs_from_env = _elevenlabs_configured()

    return CapabilitiesResponse(
        visual_modes=sorted(ALLOWED_VISUAL_MODES),
        media_preferences=sorted(ALLOWED_MEDIA_PREFERENCES),
        asset_preferences=sorted(ALLOWED_ASSET_PREFERENCES),
        providers=providers,
        duration=DurationCapabilitiesResponse(
            presets=presets,
            min_sec=SUPPORTED_DURATION_MIN,
            max_sec=SUPPORTED_DURATION_MAX,
            default=DEFAULT_DURATION_PRESET,
        ),
        tts_providers=tts_providers,
        voices=VoiceCapabilitiesResponse(
            note="No canonical voice catalog exists; only defaults are advertised.",
            default=defaults.get("voice", "es-ES-AlvaroNeural"),
            elevenlabs_from_env=elevenlabs_from_env,
        ),
    )


def _elevenlabs_configured() -> bool:
    try:
        from shorts_creator.script.generator import load_env

        env = load_env()
        value = env.get("ELEVENLABS_API_KEY") or __import__("os").environ.get("ELEVENLABS_API_KEY")
        return bool(value)
    except Exception:  # noqa: BLE001
        return False