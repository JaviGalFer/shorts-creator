"""Target-centered duration presets and canonical request resolution."""

DURATION_PRESETS = {
    "quick_30": {"targetSec": 30, "toleranceSec": 3},
    "standard_45": {"targetSec": 45, "toleranceSec": 4},
    "deep_60": {"targetSec": 60, "toleranceSec": 5},
}
DEFAULT_DURATION_PRESET = "quick_30"
TARGET_SCENE_DURATION_SEC = 6


def resolve_scene_plan(target_sec: int) -> dict:
    """Resolve a duration-derived scene plan with deterministic half-up rounding."""
    if isinstance(target_sec, bool) or not isinstance(target_sec, int) or target_sec <= 0:
        raise ValueError("target_sec must be a positive integer")
    preferred = (target_sec + TARGET_SCENE_DURATION_SEC // 2) // TARGET_SCENE_DURATION_SEC
    return {
        "targetSceneDurationSec": TARGET_SCENE_DURATION_SEC,
        "preferredSceneCount": preferred,
        "minSceneCount": max(4, preferred - 1),
        "maxSceneCount": preferred + 1,
    }

# Deprecated CLI aliases resolve through DURATION_PRESETS; they are not a
# second resolution engine and cannot reintroduce asymmetric ranges.
LEGACY_PROFILE_ALIASES = {
    "short_25_30": "quick_30",
    "standard_32_38": "standard_45",
    "extended_50_60": "deep_60",
}
DURATION_PROFILES = DURATION_PRESETS
DEFAULT_PROFILE = DEFAULT_DURATION_PRESET


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
    requested_preset: str | None = None,
    requested_tolerance: int | None = None,
    explicit_target: int | None = None,
    explicit_min: int | None = None,
    explicit_max: int | None = None,
    explicit_strictness: str | None = None,
 ) -> dict:
    """Resolve numeric target/range from preset, custom duration, and overrides."""
    if requested_sec is not None and requested_preset is not None:
        raise ValueError("--duration and --duration-preset cannot be used together")
    if requested_sec is not None and requested_profile is not None:
        raise ValueError("--duration and deprecated --duration-profile cannot be used together")
    if requested_sec is not None and (isinstance(requested_sec, bool) or not isinstance(requested_sec, int)):
        raise ValueError("--duration must be an integer")
    if requested_sec is not None and requested_sec < SUPPORTED_DURATION_MIN:
        raise ValueError(f"--duration {requested_sec} is below the minimum supported duration of {SUPPORTED_DURATION_MIN}s.")
    if requested_sec is not None and requested_sec > SUPPORTED_DURATION_MAX:
        raise ValueError(f"--duration {requested_sec} exceeds the maximum supported duration of {SUPPORTED_DURATION_MAX}s.")
    if requested_tolerance is not None and (isinstance(requested_tolerance, bool) or not isinstance(requested_tolerance, int) or requested_tolerance <= 0):
        raise ValueError("--duration-tolerance must be a positive integer")

    preset_id = requested_preset or LEGACY_PROFILE_ALIASES.get(requested_profile)
    if requested_profile and preset_id is None:
        raise ValueError(f"Unknown duration profile '{requested_profile}'")
    if requested_sec is not None:
        target_sec, source = requested_sec, "custom"
        tolerance = requested_tolerance if requested_tolerance is not None else max(2, (requested_sec + 5) // 10)
    else:
        preset_id = preset_id or DEFAULT_DURATION_PRESET
        preset = DURATION_PRESETS.get(preset_id)
        if preset is None:
            raise ValueError(f"Unknown duration preset '{preset_id}'. Available: {', '.join(DURATION_PRESETS)}")
        target_sec, source = preset["targetSec"], "preset"
        tolerance = requested_tolerance if requested_tolerance is not None else preset["toleranceSec"]
    min_sec, max_sec = target_sec - tolerance, target_sec + tolerance
    result = {
        "profile_name": preset_id,
        "presetId": preset_id if source == "preset" else None,
        "source": source,
        "requestedSec": requested_sec,
        "requestedProfile": requested_profile,
        "toleranceSec": tolerance,
        "spokenWordsPerMinute": 110,
        "estimatedScenePauseMs": 350,
    }

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
    strictness = explicit_strictness or "balanced"

    result.update({
        "targetSec": target_sec,
        "minSec": min_sec,
        "maxSec": max_sec,
        "strictness": strictness,
    })
    return result


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


# ── Post-TTS duration fitting (generic) ────────────────────────────────────
# These helpers decide PASS / EXPAND / COMPRESS from a *measured* (projected)
# duration and a *generic* per-attempt ratio policy. They intentionally know
# nothing about TTS providers, voices, or languages. spokenWordsPerMinute is
# left to calculate_word_budget() as pure bootstrap only.


DEFAULT_FITTING_RATIO_MIN = 0.70
DEFAULT_FITTING_RATIO_MAX = 1.50


def _validate_positive_number(value, label: str) -> float:
    """Return a finite positive float or raise ValueError.

    Booleans are rejected explicitly.
    """
    if isinstance(value, bool):
        raise ValueError(f"{label} must not be bool")
    if not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number, got {type(value).__name__}")
    import math
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite, got {value}")
    if value <= 0:
        raise ValueError(f"{label} must be positive, got {value}")
    return float(value)


def _validate_positive_int(value, label: str) -> int:
    """Return a positive int or raise ValueError (bool rejected)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be a positive int, got {value!r}")
    if value <= 0:
        raise ValueError(f"{label} must be positive, got {value}")
    return value


def evaluate_duration_fitting(
    *,
    current_word_count: int,
    projected_duration_sec: float,
    target_sec: int,
    min_sec: int,
    max_sec: int,
    ratio_min: float = DEFAULT_FITTING_RATIO_MIN,
    ratio_max: float = DEFAULT_FITTING_RATIO_MAX,
) -> dict:
    """Evaluate a real (projected) duration against the requested window.

    Supports PASS / EXPAND / COMPRESS purely, with a generic bounded ratio.

    Returns:
        decision           PASS | EXPAND | COMPRESS
        currentWords       int
        proposedWords      int (scaled by boundedRatio; equals current on PASS)
        projectedDurationSec float
        targetSec / minSec / maxSec  int
        rawRatio           float (desired / projected)
        boundedRatio       float (rawRatio clamped to [ratio_min, ratio_max])
        ratioPolicyMin     float
        ratioPolicyMax     float
        deltaToRangeSec    float (shortfall or overshoot vs the window; 0 on PASS)
    """
    cur = _validate_positive_int(current_word_count, "current_word_count")
    projected = _validate_positive_number(projected_duration_sec, "projected_duration_sec")
    target = _validate_positive_int(target_sec, "target_sec")
    min_sec_i = _validate_positive_int(min_sec, "min_sec")
    max_sec_i = _validate_positive_int(max_sec, "max_sec")

    if min_sec_i > target or target > max_sec_i:
        raise ValueError(
            f"Invalid duration window: minSec={min_sec_i}, "
            f"targetSec={target}, maxSec={max_sec_i}"
        )
    ratio_min_f = _validate_positive_number(ratio_min, "ratio_min")
    ratio_max_f = _validate_positive_number(ratio_max, "ratio_max")
    if ratio_min_f > ratio_max_f:
        raise ValueError(
            f"ratio_min={ratio_min_f} must not exceed ratio_max={ratio_max_f}"
        )

    if min_sec_i <= projected <= max_sec_i:
        decision = "PASS"
        proposed = cur
        delta = 0.0
    elif projected < min_sec_i:
        decision = "EXPAND"
        delta = min_sec_i - projected
    else:
        decision = "COMPRESS"
        delta = projected - max_sec_i

    # Desired duration derived from target, clamped to the window.
    desired = min(max(float(target), float(min_sec_i)), float(max_sec_i))
    raw_ratio = desired / projected
    bounded_ratio = min(max(raw_ratio, ratio_min_f), ratio_max_f)

    if decision != "PASS":
        proposed = int(round(cur * bounded_ratio))

    return {
        "decision": decision,
        "currentWords": cur,
        "proposedWords": proposed,
        "projectedDurationSec": round(projected, 3),
        "targetSec": target,
        "minSec": min_sec_i,
        "maxSec": max_sec_i,
        "rawRatio": raw_ratio,
        "boundedRatio": bounded_ratio,
        "ratioPolicyMin": ratio_min_f,
        "ratioPolicyMax": ratio_max_f,
        "deltaToRangeSec": round(delta, 3),
    }


def evaluate_requested_duration_compliance(
    *,
    actual_video_duration_sec: float,
    target_sec: int,
    min_sec: int,
    max_sec: int,
) -> dict:
    """Evaluate final MP4 duration against the requested product window."""
    actual = _validate_positive_number(actual_video_duration_sec, "actual_video_duration_sec")
    target = _validate_positive_int(target_sec, "target_sec")
    minimum = _validate_positive_int(min_sec, "min_sec")
    maximum = _validate_positive_int(max_sec, "max_sec")
    if minimum > target or target > maximum:
        raise ValueError(
            f"Invalid duration window: minSec={minimum}, targetSec={target}, maxSec={maximum}"
        )
    if minimum <= actual <= maximum:
        status, delta = "PASS", 0.0
    elif actual < minimum:
        status, delta = "FAIL", minimum - actual
    else:
        status, delta = "FAIL", actual - maximum
    return {
        "status": status,
        "actualVideoDurationSec": round(actual, 3),
        "targetSec": target,
        "minSec": minimum,
        "maxSec": maximum,
        "deltaToRangeSec": round(delta, 3),
    }


def distribute_words(
    *,
    current_counts: list[int],
    target_total: int,
    minimum_words_per_scene: int = 1,
) -> list[int]:
    """Deterministically distribute a new word total across scenes.

    - sum(result) == target_total
    - each scene target >= minimum_words_per_scene
    - roughly proportional to current_counts
    - remainder fixed by rounding (largest fractional part, index tie-break)
    - independent of provider/voice/language

    minimum_words_per_scene must be a positive int (bool rejected) and
    target_total must be >= scene_count * minimum_words_per_scene.

    Raises ValueError on invalid input.
    """
    if not isinstance(current_counts, list) or not current_counts:
        raise ValueError("current_counts must be a non-empty list")
    if any(isinstance(c, bool) or not isinstance(c, int) for c in current_counts):
        raise ValueError("current_counts must contain only integers")
    if any(c < 1 for c in current_counts):
        raise ValueError("current_counts must contain only positive integers")
    if isinstance(target_total, bool) or not isinstance(target_total, int):
        raise ValueError("target_total must be an int")
    if target_total <= 0:
        raise ValueError("target_total must be positive")
    if isinstance(minimum_words_per_scene, bool) or not isinstance(minimum_words_per_scene, int):
        raise ValueError("minimum_words_per_scene must be an int")
    if minimum_words_per_scene <= 0:
        raise ValueError("minimum_words_per_scene must be positive")

    n = len(current_counts)
    min_per_scene = minimum_words_per_scene
    if target_total < n * min_per_scene:
        raise ValueError(
            f"target_total ({target_total}) must be >= "
            f"scene_count * minimum_words_per_scene ({n} * {min_per_scene} = {n * min_per_scene})"
        )

    total = sum(current_counts)
    raw = [count / total * target_total for count in current_counts]
    floors = [int(f) for f in raw]
    fracs = [f - int(f) for f in raw]
    remaining = target_total - sum(floors)

    # Distribute the remainder: largest fractional part first, index tie-break.
    order = sorted(range(n), key=lambda i: (-fracs[i], i))
    for idx in order[:remaining]:
        floors[idx] += 1

    # Guarantee every scene has at least minimum_words_per_scene.
    for i in range(n):
        if floors[i] < min_per_scene:
            deficit = min_per_scene - floors[i]
            floors[i] = min_per_scene
            for _ in range(deficit):
                j = max(range(n), key=lambda k: floors[k] if k != i else -1)
                floors[j] -= 1

    assert sum(floors) == target_total
    return floors
