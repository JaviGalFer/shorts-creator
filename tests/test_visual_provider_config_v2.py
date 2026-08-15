"""Tests for Visual Provider Config v2.

Run: python3 -m pytest tests/test_visual_provider_config_v2.py -v
"""

import sys
from pathlib import Path

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))

from shorts_creator.assets.provider_config import load_provider_config_v2


SECRET_LIKE_KEYS = frozenset({"api_key", "apiKey", "token", "secret"})


def _has_secret_like_fields(obj, path: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(obj, dict):
        for key in obj:
            if key in SECRET_LIKE_KEYS:
                violations.append(f"{path}.{key}")
            if isinstance(obj[key], (dict, list)):
                violations.extend(_has_secret_like_fields(obj[key], f"{path}.{key}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, (dict, list)):
                violations.extend(_has_secret_like_fields(item, f"{path}[{i}]"))
    return violations


def test_default_config_wikimedia_enabled_implemented():
    cfg = load_provider_config_v2()
    wc = cfg["wikimedia_commons"]
    assert wc["enabled"] is True
    assert wc["implemented"] is True
    assert wc["requiresApiKey"] is False
    assert wc["live"] is True


def test_wikimedia_live_false():
    cfg = load_provider_config_v2(wikimedia_live=False)
    assert cfg["wikimedia_commons"]["live"] is False


def test_wikimedia_live_true_default():
    cfg = load_provider_config_v2()
    assert cfg["wikimedia_commons"]["live"] is True


def test_user_agent_propagates():
    cfg = load_provider_config_v2(user_agent="my-bot/1.0")
    assert cfg["wikimedia_commons"]["userAgent"] == "my-bot/1.0"


def test_user_agent_none_by_default():
    cfg = load_provider_config_v2()
    assert cfg["wikimedia_commons"]["userAgent"] is None


def test_pexels_disabled_not_implemented():
    cfg = load_provider_config_v2()
    p = cfg["pexels"]
    assert p["enabled"] is False
    assert p["implemented"] is False
    assert p["requiresApiKey"] is True


def test_pixabay_disabled_not_implemented():
    cfg = load_provider_config_v2()
    p = cfg["pixabay"]
    assert p["enabled"] is True
    assert p["implemented"] is True
    assert p["requiresApiKey"] is True
    assert p["apiKeyPresent"] is False


def test_freeai_disabled_not_implemented():
    cfg = load_provider_config_v2()
    p = cfg["freeai"]
    assert p["enabled"] is False
    assert p["implemented"] is False
    assert p["requiresApiKey"] is True


def test_pollinations_disabled_not_implemented():
    cfg = load_provider_config_v2()
    p = cfg["pollinations"]
    assert p["enabled"] is False
    assert p["implemented"] is False
    assert p["requiresApiKey"] is False


def test_no_secret_like_fields():
    cfg = load_provider_config_v2()
    violations = _has_secret_like_fields(cfg)
    assert violations == [], f"found secret-like fields: {violations}"


def test_no_secret_like_fields_with_user_agent():
    cfg = load_provider_config_v2(user_agent="my-bot/2.0")
    violations = _has_secret_like_fields(cfg)
    assert violations == [], f"found secret-like fields: {violations}"


def test_all_expected_providers_present():
    cfg = load_provider_config_v2()
    expected = {"wikimedia_commons", "pexels", "pixabay", "freeai", "pollinations"}
    assert set(cfg.keys()) == expected


def test_api_key_present_fields_exist_where_expected():
    cfg = load_provider_config_v2()
    assert cfg["pexels"]["apiKeyPresent"] is False
    assert cfg["pixabay"]["apiKeyPresent"] is False
    assert cfg["freeai"]["apiKeyPresent"] is False
    assert "apiKeyPresent" not in cfg["wikimedia_commons"]
    assert "apiKeyPresent" not in cfg["pollinations"]
