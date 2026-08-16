#!/usr/bin/env python3
"""CLI adapter for render preparation."""

import argparse

from _package_bootstrap import ensure_src_on_path

ensure_src_on_path()

from shorts_creator.rendering import preparer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata_path")
    parser.add_argument(
        "--subtitle-style",
        choices=list(preparer.ASS_STYLES.keys()),
        default=None,
        help=(
            "ASS style for subtitles "
            "(default: from request.subtitles.style or shorts_upper_dynamic)"
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return preparer.prepare_job(
        metadata_path=args.metadata_path,
        subtitle_style=args.subtitle_style,
    )


if __name__ == "__main__":
    raise SystemExit(main())
