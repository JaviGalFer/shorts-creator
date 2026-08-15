#!/usr/bin/env python3
"""CLI adapter for the Visual Assets V2 domain."""

import argparse

from _package_bootstrap import ensure_src_on_path

ensure_src_on_path()

from shorts_creator.assets import fetcher


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="fetch_images_v2 — standalone v2 image-fetching stage"
    )
    parser.add_argument("metadata_path", help="Path to metadata.json")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Disable live Wikimedia calls/downloads",
    )
    parser.add_argument(
        "--user-agent",
        default=None,
        help="User-Agent header for HTTP requests",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return fetcher.fetch_assets(
        metadata_path=args.metadata_path,
        dry_run=args.dry_run,
        user_agent=args.user_agent,
    )


if __name__ == "__main__":
    raise SystemExit(main())
