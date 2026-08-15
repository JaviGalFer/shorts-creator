"""Visual Asset Renderability v2 — canonical dimension and MIME contracts.

Neutral module. No v1 imports. Stdlib only. No domain/topic dependency.

Defines the single source of truth for minimum renderable dimensions and
supported MIME types in v2.
"""

from __future__ import annotations

import math

MIN_V2_ASSET_WIDTH: int = 720
MIN_V2_ASSET_HEIGHT: int = 720

SUPPORTED_WIKIMEDIA_MIME_TYPES: frozenset[str] = frozenset({
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
})


def is_v2_asset_dimension_renderable(width: int | None, height: int | None) -> bool:
    """Check whether asset dimensions satisfy the v2 renderability contract.

    Policy:
        width >= 720 AND height >= 720

    Returns False without raising for None, NaN, Infinity, booleans,
    strings, lists, negatives, zero, or any non-numeric value.
    Finite floats are accepted (e.g. 720.0 → True).
    """
    if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
        return False
    if isinstance(width, bool) or isinstance(height, bool):
        return False
    if not math.isfinite(width) or not math.isfinite(height):
        return False
    w = int(width)
    h = int(height)
    return w >= MIN_V2_ASSET_WIDTH and h >= MIN_V2_ASSET_HEIGHT
