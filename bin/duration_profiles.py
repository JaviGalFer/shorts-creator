"""Temporary CLI adapter for the canonical duration contract."""

from _package_bootstrap import ensure_src_on_path

ensure_src_on_path()

from shorts_creator.contracts.duration import (
    DEFAULT_PROFILE,
    DURATION_PROFILES,
    SUPPORTED_DURATION_MAX,
    SUPPORTED_DURATION_MIN,
    calculate_word_budget,
    resolve_duration_config,
    resolve_requested_duration,
)


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


__all__ = [
    "DEFAULT_PROFILE",
    "DURATION_PROFILES",
    "SUPPORTED_DURATION_MAX",
    "SUPPORTED_DURATION_MIN",
    "add_duration_profile_args",
    "calculate_word_budget",
    "resolve_duration_config",
    "resolve_requested_duration",
]
