# fetch-images-v2-standalone

**Date:** 2026-07-10-2042
**Type:** Build

## Objective

Create `bin/fetch_images_v2.py` as a standalone CLI stage that chains the existing v2 visual stack. No runtime integration with `run_job.py`.

## Files created

| File | Purpose |
|------|---------|
| `bin/visual_provider_config_v2.py` | Provider capability descriptor helper |
| `bin/fetch_images_v2.py` | Standalone v2 image-fetching CLI stage |
| `tests/test_visual_provider_config_v2.py` | Provider config tests (13 tests) |
| `tests/test_fetch_images_v2.py` | CLI stage tests (27 tests) |

## CLI contract

```bash
python3 bin/fetch_images_v2.py <metadata_path>
python3 bin/fetch_images_v2.py <metadata_path> --dry-run
python3 bin/fetch_images_v2.py <metadata_path> --user-agent "my-bot/1.0"
```

## Status / exit-code contract

| Status | Exit Code |
|--------|-----------|
| `ASSETS_READY` | 0 |
| `ASSETS_PARTIAL` | 0 |
| `ASSET_UNRESOLVED` | 1 |
| `ASSET_FAILED` | 1 |

Derivation: `segments == 0` → `ASSET_FAILED`, `resolved == segments` → `ASSETS_READY`, `resolved > 0 and failed > 0` → `ASSETS_PARTIAL`, `resolved == 0 and failed > 0` → `ASSET_UNRESOLVED`, otherwise `ASSET_FAILED`.

## Dry-run vs live behavior

- Default: `dry_run=False`, `wikimedia_live=True` — performs live Wikimedia searches and downloads.
- `--dry-run`: `dry_run=True`, `wikimedia_live=False` — no live HTTP, returns dry-run attempts only.

## No runtime integration

- Not wired into `run_job.py`.
- `metadata["assets"]` uses `assets/...` paths from the v2 executor.
- No modifications to existing pipeline files.

## Known assets/ vs scenes/ limitation

The v2 executor writes paths like `assets/seg_001.jpg`. The existing pipeline (`run_job.py`, `render_job.py`) has assumptions around `scenes/`. This CLI produces `assets/...` paths in metadata, which is acceptable for this Build. Future integration into `run_job.py` will need to handle this difference.

## Per-scene execution and synthetic unresolved

Each v2 scene is processed through:
1. `canonicalize_visual_plan_v2`
2. `build_visual_sourcing_plan_v2`
3. `execute_visual_sourcing_plan_v2`

If any step fails for a scene, synthetic unresolved results are produced for every expected `visualSequence` segment:
- **Canonicalizer fails:** `PROVIDER_ERROR` with "canonicalizer failed: ..."
- **Router fails:** `PROVIDER_ERROR` with "router failed: ..."
- **Executor raises:** `PROVIDER_ERROR` with "executor failed: ..."
- **Executor returns no result for segment:** `PROVIDER_UNAVAILABLE` with "no executor result for expected segment"

This ensures the bridge's FIFO matching by `segmentIndex` is deterministic.

## Provider config helper

`load_provider_config_v2(wikimedia_live=True, user_agent=None)` returns a dict with five providers. Only `wikimedia_commons` is enabled/implemented. No `.env` reads, no API key discovery, no secret-like fields.

## Validation results

```
python3 -m pytest tests/test_visual_provider_config_v2.py -v  # 13 passed
python3 -m pytest tests/test_fetch_images_v2.py -v             # 27 passed
```

Full test suite: 711 passed, 16 pre-existing failures unrelated to this change.

## Remaining dependencies before run_job.py integration

1. Handle `assets/` vs `scenes/` path prefix mismatch in `run_job.py` and `render_job.py`
2. Decide whether `ASSETS_PARTIAL` should block or allow pipeline continuation in `run_job.py`
3. Wire `fetch_images_v2.py` into `run_job.py` as an alternative to `fetch_images.py`
4. Register FreeAI or other providers for image generation capability
