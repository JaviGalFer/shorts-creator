# Session: retire-legacy-visual-v1 Slice 2

**Date:** 2026-07-22
**Model:** opencode/deepseek-v4-flash-free (low)
**Mode:** Build / implementation

## Change active

`openspec/changes/retire-legacy-visual-v1/` — Slice 2: V2-only asset runtime

## Classifier decisions

- `_classify_visual_schema(metadata)` classifies into 5 categories:
  - `SUPPORTED_V2` — all scenes V2, no V1 evidence
  - `UNSUPPORTED_LEGACY_V1` — all scenes have positive V1 markers, no V2
  - `MIXED_SCHEMA` — at least one V2 and at least one V1-positive scene
  - `INVALID_SCHEMA` — malformed, missing fields, contradictory version values
  - `SCHEMA_NOT_AVAILABLE_YET` — metadata not yet produced by script stage
- V1 positive markers: `editorialRole` and/or `strategy` present in visualPlan, no `_schemaVersion`
- `request.visuals.schemaVersion` must be absent or exactly int 2; otherwise INVALID_SCHEMA
- `_schemaVersion` must be exactly int 2; bool, string, other ints, or None (without V1 markers) are INVALID

## Validation point

- Placed in the `else` block of `main()` (post-script stages), after `load_metadata()` and before `REVIEW_REQUIRED` check
- Removed the old `_check_mixed_schema_versions()` call from the `stage == "assets"` guard
- SCHEMA_NOT_AVAILABLE_YET mapped to INVALID_VISUAL_SCHEMA in the validation block (since we are past script)

## Error contract

| Classifier category | failure.error literal |
|---------------------|----------------------|
| UNSUPPORTED_LEGACY_V1 | `UNSUPPORTED_LEGACY_SCHEMA` |
| MIXED_SCHEMA | `MIXED_VISUAL_PLAN_SCHEMA_VERSIONS` |
| INVALID_SCHEMA | `INVALID_VISUAL_SCHEMA` |
| SCHEMA_NOT_AVAILABLE_YET | `INVALID_VISUAL_SCHEMA` (at runtime) |
| SUPPORTED_V2 | no error |

## Dispatch V2-only

- `build_stage_command("assets", ...)` always returns `[sys.executable, bin/fetch_images_v2.py, metadata_path]`
- No longer consults `_uses_v2_visual_assets()` or metadata to decide the script
- `STAGE_SCRIPTS["assets"]` and `bin/fetch_images.py` preserved (Slice 4)

## Legacy code preserved

- `_uses_v2_visual_assets()` — still used by `_verify_stage_contract()`
- `_collect_visual_plan_schema_versions()` — still used by preserved helpers
- `_check_mixed_schema_versions()` — preserved but no longer called in main()
- V1 branch of `_verify_stage_contract()` — effectively unreachable from the canonical pipeline after the schema guard; retained temporarily and deferred to Slice 4 cleanup.
- `_v1_scene` fixture — kept for test compatibility
- `STAGE_SCRIPTS["assets"]` — kept until Slice 4
- `bin/fetch_images.py` — not physically removed

## Tests executed

| Suite | Result |
|-------|--------|
| `tests/test_run_job_v2_assets.py` (45 tests) | 45 passed |
| `tests/test_run_job.py -k "build_stage_command or dry_run"` (10 tests) | 10 passed |
| `tests/test_v2_only_generation_contract.py` (7 tests) | 7 passed |
| **Total: 62 focused tests passed, 0 failed** | |

## Review

- Result: **APPROVE_WITH_NON_BLOCKING_NOTES**
- No functional blocking findings
- The only documentary finding was the incorrect description of the V1 branch (corrected above)
- The positive V1 criterion based on `editorialRole` or `strategy` was considered a non-blocking theoretical note
- The V1 branch remains physically present but is unreachable from the canonical pipeline after the schema guard

## Reindex

- `codebase-memory-mcp index_repository --mode fast` completed

## Deferred to Slice 3

- Remove V1 prompts, validators, helpers from `generate_script.py`
- Remove `--visual-schema-version` CLI arg
- Remove V1-only tests

## Deferred to Slice 4

- Physical removal of `bin/fetch_images.py`
- Clean up `STAGE_SCRIPTS["assets"]`
- Remove `_v1_scene` fixture and V1 branch of `_verify_stage_contract()`
