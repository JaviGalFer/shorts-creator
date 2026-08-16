"""Temporary CLI adapter for the canonical duration contract."""

from _package_bootstrap import ensure_src_on_path

ensure_src_on_path()

from shorts_creator.contracts.duration import (
    DEFAULT_PROFILE,
    DEFAULT_DURATION_PRESET,
    DURATION_PRESETS,
    DURATION_PROFILES,
    SUPPORTED_DURATION_MAX,
    SUPPORTED_DURATION_MIN,
    calculate_word_budget,
    resolve_duration_config,
    resolve_requested_duration,
)


def add_duration_profile_args(parser) -> None:
    """Add canonical preset/custom duration options and legacy aliases."""
    duration_group = parser.add_mutually_exclusive_group()
    duration_group.add_argument(
        "--duration", type=int, default=None,
        help="Custom target duration in seconds with symmetric tolerance.",
    )
    duration_group.add_argument(
        "--duration-preset", default=None, choices=list(DURATION_PRESETS),
        help=f"Duration preset (default: {DEFAULT_DURATION_PRESET})",
    )
    parser.add_argument("--duration-tolerance", type=int, default=None,
                        help="Symmetric tolerance in seconds around the target")
    parser.add_argument(
        "--duration-profile",
        default=None,
        choices=["short_25_30", "standard_32_38", "extended_50_60"],
        help="Deprecated alias for --duration-preset",
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


__all__ = [
    "DEFAULT_PROFILE",
    "DEFAULT_DURATION_PRESET",
    "DURATION_PRESETS",
    "DURATION_PROFILES",
    "SUPPORTED_DURATION_MAX",
    "SUPPORTED_DURATION_MIN",
    "add_duration_profile_args",
    "calculate_word_budget",
    "resolve_duration_config",
    "resolve_requested_duration",
]
