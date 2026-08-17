#!/usr/bin/env python3
"""CLI adapter for the V2 pipeline orchestrator."""

import argparse

from _package_bootstrap import ensure_src_on_path

ensure_src_on_path()

from duration_profiles import add_duration_profile_args
from shorts_creator.pipeline import orchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified job runner for shorts-creator pipeline")
    parser.add_argument("--topic", required=True, help="Topic or instruction for the video")
    parser.add_argument("--model", help="LLM model override")
    parser.add_argument("--dry-run", action="store_true", help="Print execution plan without running")
    parser.add_argument(
        "--stop-after",
        choices=orchestrator.STAGES,
        default="validate",
        help="Stop after completing this stage (default: validate = full pipeline)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print child command output during execution",
    )
    add_duration_profile_args(parser)
    parser.add_argument(
        "--tts-provider",
        choices=["edge_tts", "elevenlabs"],
        default=None,
        help="TTS provider (default: edge_tts or TTS_PROVIDER env)",
    )
    parser.add_argument(
        "--voice",
        default=None,
        help="Voice ID; wins over env voice; provider default when omitted",
    )
    parser.add_argument(
        "--subtitle-timing-provider",
        choices=["auto", "edge_tts", "whisper", "estimated"],
        default=None,
        help="Subtitle timing provider (default: auto or env)",
    )
    parser.add_argument(
        "--asset-providers",
        default=None,
        help="Comma-separated visual source providers to restrict to, in priority "
             "order (e.g. wikimedia_commons,pixabay). Omitted -> default fallback.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return orchestrator.run_pipeline(
        topic=args.topic,
        model=args.model,
        dry_run_mode=args.dry_run,
        stop_after=args.stop_after,
        verbose=args.verbose,
        duration=args.duration,
        duration_profile=args.duration_profile,
        duration_preset=args.duration_preset,
        duration_tolerance=args.duration_tolerance,
        duration_target=args.duration_target,
        duration_min=args.duration_min,
        duration_max=args.duration_max,
        strictness=args.strictness,
        tts_provider=args.tts_provider,
        voice=args.voice,
        subtitle_timing_provider=args.subtitle_timing_provider,
        asset_providers=args.asset_providers,
    )


if __name__ == "__main__":
    raise SystemExit(main())
