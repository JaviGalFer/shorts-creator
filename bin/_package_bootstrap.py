"""Temporary import bootstrap for bin compatibility adapters."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_src_on_path() -> None:
    """Make the repository's src package importable for direct bin execution."""
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
