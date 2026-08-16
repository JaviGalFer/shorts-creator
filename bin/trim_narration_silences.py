#!/usr/bin/env python3
"""CLI adapter for continuous narration trimming."""

import argparse

from _package_bootstrap import ensure_src_on_path

ensure_src_on_path()

from shorts_creator.audio import trimming


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata_path", type=str)
    parser.add_argument(
        "--target-chapter-break",
        type=float,
        default=trimming.TARGET_CHAPTER_BREAK_SEC,
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return trimming.trim_narration(
        metadata_path=args.metadata_path,
        target_chapter_break=args.target_chapter_break,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
