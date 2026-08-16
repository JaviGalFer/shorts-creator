#!/usr/bin/env python3
"""CLI adapter for job validation."""

import argparse

from _package_bootstrap import ensure_src_on_path

ensure_src_on_path()

from shorts_creator.validation import job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a shorts-creator job")
    parser.add_argument("metadata_path", help="Path to metadata.json")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all checks")
    parser.add_argument(
        "--update-manifest",
        action="store_true",
        help="Re-run coverage validation and update manifest gates",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return job.validate_job(
        metadata_path=args.metadata_path,
        json_output=args.json,
        verbose=args.verbose,
        update_manifest=args.update_manifest,
    )


if __name__ == "__main__":
    raise SystemExit(main())
