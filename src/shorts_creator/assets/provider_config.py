"""Visual Provider Config v2 — provider capability descriptor.

Pure config helper.  No I/O, no .env reads, no API key discovery,
no secret-like fields.  Stdlib only.
"""

from __future__ import annotations


def load_provider_config_v2(
    *,
    wikimedia_live: bool = True,
    user_agent: str | None = None,
    pixabay_live: bool = True,
    pixabay_api_key_present: bool = False,
    pexels_enabled: bool = False,
    pexels_api_key_present: bool = False,
    pexels_live: bool = True,
) -> dict:
    return {
        "wikimedia_commons": {
            "enabled": True,
            "implemented": True,
            "requiresApiKey": False,
            "live": wikimedia_live,
            "userAgent": user_agent,
        },
        "pexels": {
            "enabled": pexels_enabled,
            "implemented": pexels_enabled,
            "requiresApiKey": True,
            "apiKeyPresent": pexels_api_key_present,
            "live": pexels_live,
        },
        "pixabay": {
            "enabled": True,
            "implemented": True,
            "requiresApiKey": True,
            "apiKeyPresent": pixabay_api_key_present,
            "live": pixabay_live,
        },
        "freeai": {
            "enabled": False,
            "implemented": False,
            "requiresApiKey": True,
            "apiKeyPresent": False,
        },
        "pollinations": {
            "enabled": False,
            "implemented": False,
            "requiresApiKey": False,
        },
    }
