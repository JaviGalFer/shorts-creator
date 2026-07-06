"""Duration profile system for shorts-creator.

Provides reusable duration presets and a resolution function
that merges profile defaults with explicit CLI overrides.
"""

DURATION_PROFILES = {
    "short_25_30": {
        "targetSec": 28,
        "minSec": 25,
        "maxSec": 30,
        "strictness": "balanced",
    },
    "standard_32_38": {
        "targetSec": 35,
        "minSec": 32,
        "maxSec": 38,
        "strictness": "balanced",
    },
    "extended_50_60": {
        "targetSec": 55,
        "minSec": 50,
        "maxSec": 60,
        "strictness": "balanced",
    },
}

DEFAULT_PROFILE = "short_25_30"


def calculate_word_budget(
    target_sec: int,
    min_sec: int,
    max_sec: int,
    spoken_words_per_minute: int = 110,
    scene_count: int = 5,
    estimated_scene_pause_ms: int = 350,
) -> dict:
    """Calculate word budget from resolved numeric duration values.

    The formula accounts for inter-scene pauses so that the spoken-only
    portion of the narration fits within the target/min/max window:

        pauseSec = (sceneCount - 1) * estimatedScenePauseMs / 1000

        minimumWords   = ceil(max(0, minSec - pauseSec) / 60 * WPM)
        preferredWords = round(max(0, targetSec - pauseSec) / 60 * WPM)
        maximumWords   = floor(max(0, maxSec - pauseSec) / 60 * WPM)

    Works with any numeric values — profile names, explicit overrides, or
    future --duration / requestedSec resolutions.
    """
    pause_sec = max(0, scene_count - 1) * estimated_scene_pause_ms / 1000.0
    import math
    minimum_words = math.ceil(max(0, min_sec - pause_sec) / 60.0 * spoken_words_per_minute)
    preferred_words = round(max(0, target_sec - pause_sec) / 60.0 * spoken_words_per_minute)
    maximum_words = math.floor(max(0, max_sec - pause_sec) / 60.0 * spoken_words_per_minute)
    return {
        "targetSec": target_sec,
        "minSec": min_sec,
        "maxSec": max_sec,
        "sceneCount": scene_count,
        "pauseSec": round(pause_sec, 2),
        "minimumWords": max(0, minimum_words),
        "preferredWords": max(0, preferred_words),
        "maximumWords": max(0, maximum_words),
        "spokenWordsPerMinute": spoken_words_per_minute,
        "estimatedScenePauseMs": estimated_scene_pause_ms,
    }


SUPPORTED_DURATION_MIN = 20
SUPPORTED_DURATION_MAX = 60


def resolve_requested_duration(
    requested_sec: int | None = None,
    requested_profile: str | None = None,
    explicit_target: int | None = None,
    explicit_min: int | None = None,
    explicit_max: int | None = None,
    explicit_strictness: str | None = None,
) -> dict:
    """Resolve a full duration config from approximate --duration and/or profile.

    Priority order:
      1. Explicit exact overrides (--duration-target, --duration-min, --duration-max, --strictness)
      2. Approximate --duration value
      3. Explicit --duration-profile name
      4. Default: short_25_30

    Returns dict with keys:
      profile_name, targetSec, minSec, maxSec, strictness,
      requestedSec (or None), requestedProfile (or None),
      spokenWordsPerMinute, estimatedScenePauseMs.
    """
    result = {
        "requestedSec": requested_sec,
        "requestedProfile": requested_profile or ("auto" if requested_sec else None),
        "spokenWordsPerMinute": 110,
        "estimatedScenePauseMs": 350,
    }

    # --- Step 0: validate requested_sec bounds ---
    if requested_sec is not None:
        if requested_sec < SUPPORTED_DURATION_MIN:
            raise ValueError(
                f"--duration {requested_sec} is below the minimum supported duration "
                f"of {SUPPORTED_DURATION_MIN}s. Choose a value between "
                f"{SUPPORTED_DURATION_MIN} and {SUPPORTED_DURATION_MAX}s."
            )
        if requested_sec > SUPPORTED_DURATION_MAX:
            raise ValueError(
                f"--duration {requested_sec} exceeds the maximum supported duration "
                f"of {SUPPORTED_DURATION_MAX}s. Choose a value between "
                f"{SUPPORTED_DURATION_MIN} and {SUPPORTED_DURATION_MAX}s."
            )

    # --- Step 1: determine profile ---
    profile_name = requested_profile or DEFAULT_PROFILE

    # If --duration is given without explicit profile, auto-select
    if requested_sec is not None and requested_profile is None:
        profile_name = _auto_select_profile(requested_sec)

    # Validate profile exists
    profile = DURATION_PROFILES.get(profile_name)
    if profile is None:
        raise ValueError(
            f"Unknown duration profile '{profile_name}'. "
            f"Available: {', '.join(DURATION_PROFILES.keys())}"
        )
    result["profile_name"] = profile_name

    # --- Step 2: resolve numeric values ---
    if requested_sec is not None:
        # Tolerance-based range from --duration
        tolerance = max(2, min(5, round(requested_sec * 0.10)))
        target_sec = requested_sec
        min_sec = requested_sec - tolerance
        max_sec = requested_sec + tolerance
        # Clamp to profile bounds when the result stays valid
        if requested_profile:
            # Explicit profile: always constrain
            min_sec = max(min_sec, profile["minSec"])
            max_sec = min(max_sec, profile["maxSec"])
        else:
            # Auto-selected: constrain only if valid (min <= target <= max)
            clamped_min = max(min_sec, profile["minSec"])
            clamped_max = min(max_sec, profile["maxSec"])
            if clamped_min <= target_sec <= clamped_max:
                min_sec, max_sec = clamped_min, clamped_max
    else:
        # No --duration: use profile defaults
        target_sec = profile["targetSec"]
        min_sec = profile["minSec"]
        max_sec = profile["maxSec"]

    # Explicit overrides take highest priority
    if explicit_target is not None:
        target_sec = explicit_target
    if explicit_min is not None:
        min_sec = explicit_min
    if explicit_max is not None:
        max_sec = explicit_max

    # --- Step 3: validate consistency ---
    if min_sec > target_sec:
        raise ValueError(
            f"Invalid duration: minSec={min_sec} > targetSec={target_sec}. "
            f"Minimum must not exceed target."
        )
    if target_sec > max_sec:
        raise ValueError(
            f"Invalid duration: targetSec={target_sec} > maxSec={max_sec}. "
            f"Target must not exceed maximum."
        )
    if requested_sec is not None and requested_profile:
        if requested_sec < profile["minSec"] or requested_sec > profile["maxSec"]:
            raise ValueError(
                f"--duration {requested_sec}s is outside the range of profile "
                f"'{requested_profile}' ({profile['minSec']}-{profile['maxSec']}s). "
                f"Use --duration-auto or a different profile."
            )

    strictness = explicit_strictness or profile.get("strictness", "balanced")

    result.update({
        "targetSec": target_sec,
        "minSec": min_sec,
        "maxSec": max_sec,
        "strictness": strictness,
    })
    return result


def _auto_select_profile(requested_sec: int) -> str:
    """Map an approximate duration to the best profile automatically."""
    if 20 <= requested_sec <= 30:
        return "short_25_30"
    elif 31 <= requested_sec <= 45:
        return "standard_32_38"
    elif 46 <= requested_sec <= 60:
        return "extended_50_60"
    raise ValueError(
        f"Requested duration {requested_sec}s is outside the supported range "
        f"({SUPPORTED_DURATION_MIN}-{SUPPORTED_DURATION_MAX}s)."
    )


def resolve_duration_config(
    profile_name: str | None = None,
    target: int | None = None,
    min_sec: int | None = None,
    max_sec: int | None = None,
    strictness: str | None = None,
) -> tuple[str, dict]:
    """Legacy resolver — kept for backward compatibility with existing tests.

    Use resolve_requested_duration() for new code.
    """
    profile_name = profile_name or DEFAULT_PROFILE
    profile = DURATION_PROFILES.get(profile_name)
    if profile is None:
        profile_name = DEFAULT_PROFILE
        profile = DURATION_PROFILES[profile_name]

    resolved = dict(profile)
    if target is not None:
        resolved["targetSec"] = target
    if min_sec is not None:
        resolved["minSec"] = min_sec
    if max_sec is not None:
        resolved["maxSec"] = max_sec
    if strictness is not None:
        resolved["strictness"] = strictness

    return profile_name, resolved


def add_duration_profile_args(parser) -> None:
    """Add --duration, --duration-profile and explicit duration args to argparse."""
    parser.add_argument(
        "--duration", type=int, default=None,
        help="Approximate target duration in seconds (e.g. 42). Auto-selects profile.",
    )
    parser.add_argument(
        "--duration-profile",
        default=None,
        choices=list(DURATION_PROFILES.keys()),
        help=f"Duration profile (default: {DEFAULT_PROFILE})",
    )
    parser.add_argument(
        "--duration-target", type=int, default=None,
        help="Exact target duration in seconds (overrides profile and --duration)",
    )
    parser.add_argument(
        "--duration-min", type=int, default=None,
        help="Minimum duration in seconds (overrides profile and --duration)",
    )
    parser.add_argument(
        "--duration-max", type=int, default=None,
        help="Maximum duration in seconds (overrides profile and --duration)",
    )
    parser.add_argument(
        "--strictness", default=None,
        choices=["strict", "balanced", "relaxed"],
        help="Duration strictness level (overrides profile)",
    )
