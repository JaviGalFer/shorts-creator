#!/usr/bin/env python3
"""CLI adapter for rendering."""

import argparse

from _package_bootstrap import ensure_src_on_path

ensure_src_on_path()

from shorts_creator.rendering import renderer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata_path")
    parser.add_argument("--skip-validation", action="store_true", help="Skip preflight validation")
    parser.add_argument("--skip-asset-validation", action="store_true", help="Skip asset validation quality gate")
    parser.add_argument(
        "--skip-render",
        action="store_true",
        help="Skip FFmpeg render and post-render validation (still generates manifest)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return renderer.render_job(
        metadata_path=args.metadata_path,
        skip_validation=args.skip_validation,
        skip_asset_validation=args.skip_asset_validation,
        skip_render=args.skip_render,
    )


if __name__ == "__main__":
    raise SystemExit(main())
