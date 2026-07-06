"""Editorial role to asset-type compatibility contract.

Shared by generate_script.py and fetch_images.py so both stages use the
same authoritative rules.  No circular imports.

The contract uses EXPLICIT ALLOW-LISTS (not deny-lists).  Every role has
a finite set of permitted asset-type strings.  Unknown roles or unknown
asset types fail closed in validation contexts.
"""

# ── Allow-lists: every role maps to an explicit set of permitted types ────

ROLE_ALLOWED_TYPES: dict[str, set[str]] = {
    "context_map": {
        "map", "historical_map", "document", "newspaper",
        # LLM-produced aliases (mapped to real types by _infer_effective_asset_type)
        "map_or_document", "historical_map_or_document",
    },
    "document_or_date": {
        "document", "newspaper", "map", "historical_map",
        "map_or_document", "historical_map_or_document",
    },
    "character_portrait": {
        "portrait", "historical_photograph", "painting", "historical_art",
    },
    "military_technology": {
        "historical_photograph", "painting", "historical_art", "document",
    },
    "civilian_impact": {
        "historical_photograph", "historical_art", "painting",
    },
    "battle_or_assault": {
        "historical_photograph", "historical_art", "painting",
    },
    "border_closure_construction": {
        "historical_photograph", "historical_art", "painting",
    },
    "consequence_or_legacy_event_depiction": {
        "historical_photograph", "historical_art", "painting",
    },
    "consequence_or_legacy_legacy": {
        "historical_photograph", "historical_art", "painting",
        "atmospheric_broll", "broll",  # documented exception
    },
    "atmospheric_transition": {
        "atmospheric_broll", "broll",
        "historical_photograph", "painting",
    },
}

# ── Preferred types per role (for scoring only) ─────────────────────────────

ROLE_PREFERRED_TYPES: dict[str, set[str]] = {
    "context_map":                 {"map", "document", "historical_map"},
    "document_or_date":            {"document", "newspaper", "historical_map"},
    "character_portrait":          {"portrait", "historical_photograph", "painting"},
    "military_technology":         {"historical_photograph", "painting", "document"},
    "civilian_impact":             {"historical_photograph", "historical_art"},
    "battle_or_assault":           {"historical_photograph", "historical_art"},
    "border_closure_construction": {"historical_photograph", "historical_art"},
    "consequence_or_legacy":       {"historical_photograph", "historical_art"},
    "atmospheric_transition":      {"atmospheric_broll", "broll"},
}

# ── Editorial role → allowed visualTemporalIntent values ─────────────────────

ROLE_INTENT_RULES: dict[str, set[str]] = {
    "context_map":                 {"event_depiction"},
    "character_portrait":          {"event_depiction"},
    "battle_or_assault":           {"event_depiction"},
    "military_technology":         {"event_depiction"},
    "civilian_impact":             {"event_depiction"},
    "document_or_date":            {"event_depiction"},
    "border_closure_construction": {"event_depiction"},
    "consequence_or_legacy":       {"event_depiction", "legacy_or_commemoration"},
    "atmospheric_transition":      {"context_or_setup"},
}

# ── Segment count rules by scene duration ───────────────────────────────────

SEGMENT_COUNT_RULES: dict[str, tuple[int, int]] = {
    # key: duration type, value: (min, max) inclusive
    "short":  (1, 1),   # <= 4s
    "medium": (2, 2),   # > 4s and < 8s
    "long":   (2, 3),   # >= 8s
}


def _resolve_allowed_set(editorial_role: str, temporal_intent: str | None) -> set[str]:
    """Internal: return the correct allowed-set key for the role/intent."""
    if editorial_role == "consequence_or_legacy" and temporal_intent == "legacy_or_commemoration":
        return ROLE_ALLOWED_TYPES.get("consequence_or_legacy_legacy", set())
    if editorial_role == "consequence_or_legacy":
        return ROLE_ALLOWED_TYPES.get("consequence_or_legacy_event_depiction", set())
    return ROLE_ALLOWED_TYPES.get(editorial_role, set())


def is_asset_type_allowed(
    editorial_role: str,
    asset_type: str,
    temporal_intent: str | None = None,
) -> bool:
    """Return True when *asset_type* is in the explicit allow-list for *editorial_role*.

    Unknown role → fail closed (return False).
    Unknown asset type → fail closed (return False).
    """
    if not editorial_role or not asset_type:
        return False
    allowed = _resolve_allowed_set(editorial_role, temporal_intent)
    return asset_type in allowed


def is_temporal_intent_allowed(editorial_role: str, temporal_intent: str) -> bool:
    """Return True when *temporal_intent* is valid for *editorial_role*."""
    allowed = ROLE_INTENT_RULES.get(editorial_role)
    if allowed is None:
        return False  # unknown role → fail closed
    return temporal_intent in allowed


def allowed_asset_types_for_role(
    editorial_role: str,
    temporal_intent: str | None = None,
) -> set[str]:
    """Return the explicit set of asset-type names allowed for *editorial_role*."""
    return _resolve_allowed_set(editorial_role, temporal_intent).copy()


def suggest_replacement_types(
    editorial_role: str,
    forbidden_type: str,
    temporal_intent: str | None = None,
) -> list[str]:
    """Return a list of alternative asset-type names the LLM can use instead
    of *forbidden_type*, derived from the explicit allow-list."""
    allowed = _resolve_allowed_set(editorial_role, temporal_intent)
    preferred = ROLE_PREFERRED_TYPES.get(editorial_role, set())
    candidates = sorted(preferred & allowed)
    extras = sorted(allowed - set(candidates))
    return (candidates + extras)[:4]


def get_segment_count_range(scene_duration_sec: float) -> tuple[int, int]:
    """Return (min, max) segment count for a scene of *scene_duration_sec*."""
    if scene_duration_sec <= 4:
        return SEGMENT_COUNT_RULES["short"]
    if scene_duration_sec < 8:
        return SEGMENT_COUNT_RULES["medium"]
    return SEGMENT_COUNT_RULES["long"]


# ── Legacy alias for fetch_images.py backward compatibility ─────────────────
# fetch_images.py accesses EDITORIAL_ROLE_PREFERENCES["role"]["preferred"]
# and ["forbidden"] for scoring and display.

def _build_legacy_prefs() -> dict[str, dict[str, set[str]]]:
    """Build a backward-compatible EDITORIAL_ROLE_PREFERENCES dict that
    exposes ``preferred`` and ``forbidden`` sets so direct-readers in
    tests and transitional code still work.  New code must use the
    allow-list helpers instead."""
    from copy import deepcopy
    legacy: dict[str, dict[str, set[str]]] = {}
    # All possible asset types used anywhere in the system
    all_known: set[str] = set()
    for v in ROLE_ALLOWED_TYPES.values():
        all_known |= v
    for role_key, allowed in ROLE_ALLOWED_TYPES.items():
        role = role_key
        for suffix in ("_event_depiction", "_legacy"):
            if role_key.endswith(suffix):
                role = role_key[: -len(suffix)]
                break
        if role not in legacy:
            legacy[role] = {
                "preferred": ROLE_PREFERRED_TYPES.get(role, set()).copy(),
                "forbidden": set(),
            }
        # For consequence_or_legacy: merge ALL allowed from both sub-keys
        # then compute forbidden as complement
        if role == "consequence_or_legacy":
            merged = (ROLE_ALLOWED_TYPES.get("consequence_or_legacy_event_depiction", set())
                      | ROLE_ALLOWED_TYPES.get("consequence_or_legacy_legacy", set()))
            # Forbidden = all known types that the MOST PERMISSIVE sub-key does NOT allow
            legacy[role]["forbidden"] = all_known - merged
        else:
            legacy[role]["forbidden"] = all_known - allowed
    # consequence_or_legacy preferred is the shared base
    return legacy


EDITORIAL_ROLE_PREFERENCES = _build_legacy_prefs()
