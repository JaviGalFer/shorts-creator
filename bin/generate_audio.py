#!/usr/bin/env python3
"""CLI adapter for the audio generation domain."""

import argparse
import asyncio

from _package_bootstrap import ensure_src_on_path

ensure_src_on_path()

from shorts_creator.audio import generator


def build_parser() -> argparse.ArgumentParser:
    defaults = generator.get_audio_defaults()
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata_path")
    parser.add_argument("--voice", default=defaults["voice"])
    parser.add_argument(
        "--tts-provider",
        default=defaults["tts_provider"],
        choices=["edge_tts", "elevenlabs"],
        help=(
            f"TTS provider (default: {defaults['tts_provider']}, "
            "from TTS_PROVIDER env)"
        ),
    )
    parser.add_argument(
        "--force-regenerate",
        action="store_true",
        help="Regenerate per-scene TTS and subtitle timing instead of reusing existing MP3 files",
    )
    parser.add_argument(
        "--subtitle-timing-provider",
        default=defaults["subtitle_timing_provider"],
        choices=["auto", "edge_tts", "whisper", "estimated"],
        help=(
            "Subtitle timing source "
            f"(default: {defaults['subtitle_timing_provider']}, from "
            "SUBTITLE_TIMING_PROVIDER or SUBTITLE_PROVIDER env). auto = prefer "
            "native provider timing, then configured fallback/estimated timing"
        ),
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Generate single narration MP3 for the whole job",
    )
    parser.add_argument(
        "--join-style",
        choices=["period", "semicolon", "comma"],
        default="period",
        help=(
            "Punctuation between scenes. Only 'period' works with "
            "SentenceBoundary detection. semicolon/comma break SentenceBoundary "
            "matching (edge-tts behavior). Use scene.joinToNext for custom connectors."
        ),
    )
    return parser


async def main_async() -> int:
    args = build_parser().parse_args()
    return await generator.generate_audio(
        metadata_path=args.metadata_path,
        voice=args.voice,
        tts_provider=args.tts_provider,
        subtitle_timing_provider=args.subtitle_timing_provider,
        continuous=args.continuous,
        join_style=args.join_style,
        force_regenerate=args.force_regenerate,
    )


def main() -> int:
    try:
        return asyncio.run(main_async())
    except ImportError:
        print("ERROR: edge-tts not installed. Run: pip install edge-tts")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
