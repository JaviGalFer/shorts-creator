# Runtime v2 Assets — Phase 1

**Session:** 2026-07-10-2101-runtime-v2-assets-phase1
**Type:** Build
**Change:** Phase 1 runtime integration for v2 assets

## Objective

Wire the standalone v2 image stage into `run_job.py` only for the assets stage.
Phase 1 enables `--stop-after assets` to use the v2 stack transparently.

## Files changed

- `bin/run_job.py` — v2 detection helpers, script resolution, contract verification, mixed-schema fail-fast, Phase 1 guard
- `tests/test_run_job_v2_assets.py` — 44 new tests
- `docs/sessions/2026-07-10-2101-runtime-v2-assets-phase1.md` — this doc

## Dispatch behavior

Three new helper functions added to `run_job.py`:

- `_collect_visual_plan_schema_versions(metadata)` — returns `set[int]` of `_schemaVersion` values
- `_uses_v2_visual_assets(metadata)` — returns `True` if any scene has `_schemaVersion == 2`
- `_check_mixed_schema_versions(metadata)` — returns `"MIXED_VISUAL_PLAN_SCHEMA_VERSIONS"` or `None`

Detection rules:
- If any scene has `_schemaVersion == 2`, use v2
- If all visual plans are absent or non-v2, use v1
- Scenes without `visualPlan` are ignored
- If v2 exists, every scene with a `visualPlan` must have `_schemaVersion == 2`; otherwise fail fast

`build_stage_command` now accepts optional `metadata` parameter. When `stage == "assets"` and metadata contains v2 visual plans, returns `fetch_images_v2.py` instead of `fetch_images.py`.

## Mixed schema fail-fast

Before running the assets stage, `_check_mixed_schema_versions` is called. If mixed v1/v2 visual plans are detected:
- Metadata status set to `FAILED`
- Failure code: `MIXED_VISUAL_PLAN_SCHEMA_VERSIONS`
- Returns non-zero
- `fetch_images.py` and `fetch_images_v2.py` are NOT executed

## v2 assets contract

Updated `_verify_stage_contract` for stage `"assets"`:

| Status | v1 behavior | v2 behavior |
|--------|------------|-------------|
| `ASSETS_READY` + images | Checks `scenes/scene-*.jpg` | Checks `assets/*{.jpg,.jpeg,.png,.webp,.gif}` |
| `ASSET_UNRESOLVED` | Graceful block | Graceful block (same) |
| `ASSETS_PARTIAL` | **Hard contract failure** | **Graceful block** |
| `REVIEW_REQUIRED` | Graceful block | Graceful block |
| Unknown status | Contract failure | Contract failure |

V1 behavior is fully preserved. V2 behavior is selected when `_uses_v2_visual_assets(data)` returns `True`.

### ASSETS_PARTIAL decision

V1 `ASSETS_PARTIAL` remains a hard contract failure (unchanged).  
V2 `ASSETS_PARTIAL` becomes a graceful block because the bridge (`_visualAssetBridgeV2.summary`) explicitly tracks resolved/failed segments per scene.

## No render integration

If v2 assets succeed and `--stop-after` is NOT `assets`, the runner blocks with status `V2_RUNTIME_INTEGRATION_PENDING`:

```
V2_RUNTIME_INTEGRATION_PENDING: full v2 pipeline rendering not yet
implemented. Use --stop-after assets.
```

Phase 2 will remove this guard once `prepare_job.py` and `render_job.py` support v2 `assets/` paths.

## Known limitation

- `prepare_job.py` expects `scenes/` directory structure (v1)
- `render_job.py` expects `scenes/` directory structure (v1)
- V2 images live in `assets/` (e.g. `assets/seg_001.jpg`)
- Full pipeline rendering beyond assets is blocked until Phase 2

## Validation results

```
tests/test_run_job_v2_assets.py .............. 44 passed
tests/test_fetch_images_v2.py .............. 27 passed
tests/test_visual_provider_config_v2.py ... 13 passed
All v2 tests (8 files) .................. 393 passed

Full suite ................ 755 passed, 16 failed
```

The 16 failures are the known pre-existing v1 test failures (15 in `test_run_job.py`, 1 in `test_semantic_asset_validation.py`). None were introduced by this change.

## Confirmation

- No provider calls
- No real jobs executed
- No video generated
- No images downloaded
- Only `bin/run_job.py` and `tests/test_run_job_v2_assets.py` modified
- No v2 module imports in run_job.py (verified by structural test)

## Remaining Phase 2 tasks

1. `prepare_job.py` — support `assets/` relative paths alongside `scenes/`
2. `render_job.py` — support `assets/` relative paths alongside `scenes/`
3. Remove `V2_RUNTIME_INTEGRATION_PENDING` guard from `run_job.py`
4. End-to-end v2 pipeline render validation
