#!/usr/bin/env python3
"""CLI adapter for the script generation domain."""

import argparse

from _package_bootstrap import ensure_src_on_path

ensure_src_on_path()

from duration_profiles import add_duration_profile_args
from shorts_creator.script import generator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True, help="Topic for the video")
    parser.add_argument(
        "--output",
        help="Output path for metadata.json (default: data/videos/{jobId}/metadata.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print prompt and exit without calling API",
    )
    parser.add_argument("--model", help="LLM model override")
    parser.add_argument(
        "--tts-provider",
        choices=["edge_tts", "elevenlabs"],
        default=None,
        help="TTS provider for the persisted job request",
    )
    parser.add_argument("--voice", default=None, help="Voice ID for the persisted job request")
    parser.add_argument(
        "--subtitle-timing-provider",
        choices=["auto", "edge_tts", "whisper", "estimated"],
        default=None,
        help="Subtitle timing provider for the persisted job request",
    )
    add_duration_profile_args(parser)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return generator.generate_script(
        topic=args.topic,
        output=args.output,
        dry_run=args.dry_run,
        model=args.model,
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
    )


if __name__ == "__main__":
    raise SystemExit(main())
