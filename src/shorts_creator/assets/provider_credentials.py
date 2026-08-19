"""Shared visual-provider credential resolution without secret persistence."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def resolve_api_key(name: str) -> str | None:
    """Resolve one key from process environment, then project ``.env``."""
    value = os.environ.get(name, "").strip()
    if value:
        return value

    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == name:
            value = value.strip().strip('"').strip("'")
            return value or None
    return None
