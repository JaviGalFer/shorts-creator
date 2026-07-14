# Session: Visual Asset Executor v2 — Wikimedia live MVP

**Started:** 2026-07-10 17:46 UTC
**Type:** New module + modifications (Level 1)
**OpenSpec change:** None (Level 1 bounded implementation)

## Objective

Implement the first live provider execution path for the v2 visual asset executor. Wikimedia Commons only. No other providers live. No pipeline integration. No runtime changes to v1 modules.

## What was built

### `bin/visual_provider_wikimedia_v2.py` (NEW)

Standalone Wikimedia Commons provider client. Stdlib only. No v1 imports.

**Public API:**

- `resolve_wikimedia_candidate_v2(queries, max_results=5, min_width=400, min_height=400, user_agent=None, timeout=30)` — searches Wikimedia by query list, returns first acceptable candidate or `None`.
- `download_wikimedia_asset_v2(candidate, output_path, user_agent=None, timeout=30, min_size_bytes=1000)` — downloads candidate to disk, returns `{ok, path, size, mimeType, error}`.

**Key properties:**
- Accepts queries as strings or dicts with `text` key.
- Tries queries in order with 1s delay between queries.
- Excludes SVG at search level (`-filetype:svg`) and at imageinfo MIME check.
- Filters by minimum dimensions and MIME type.
- Safe extmetadata fallbacks: `license="unknown"`, `author="Unknown"`.
- User-Agent: `shorts-creator/0.1 (generic visual asset resolver; contact: configured)`.
- No module-level state. No cache. No rate limiter (retry-on-429 is left for future enhancement).
- All HTTP via stdlib `urllib.request`. JSON decode errors, HTTP errors, URLError, and socket timeouts caught.

### `bin/visual_asset_executor_v2.py` (MODIFIED)

**Removed:** Hard `LIVE_EXECUTION_NOT_IMPLEMENTED` guard at `dry_run=False`.

**Added:**

- `dry_run=False` + missing `job_dir` → `JOB_DIR_REQUIRED_FOR_LIVE_EXECUTION`.
- Live execution path for `wikimedia_commons` only.
- Non-Wikimedia providers in live mode → `PROVIDER_UNAVAILABLE` with "not implemented" reason.
- Four new statuses: `RESOLVED`, `NO_RESULTS`, `DOWNLOAD_FAILED`, `PROVIDER_ERROR`.
- Three new summary fields: `noResults`, `downloadFailed`, `providerError`.
- Helper functions: `_extension_from_mime`, `_extension_from_url`, `_determine_extension`, `_compute_asset_paths`, `_extract_query_texts`, `_try_live_resolution`, `_increment_live_unresolved`.
- Lazy import of `visual_provider_wikimedia_v2` inside `_try_live_resolution` (no import at module level, preserving dry-run isolation).
- `live=true` gate in provider config: wikimedia must have `live: true` to execute live.
- File naming: `assets/seg_{segmentIndex:03d}.{ext}` under `job_dir`.
- Extension from MIME type (`.jpg`, `.png`, `.webp`, `.gif`), fallback to URL extension, fallback to `.bin`.
- No overwrite: existing files return `DOWNLOAD_FAILED`.

**Preserved:** All dry-run behavior unchanged (`dry_run=True` path is identical).

### `tests/test_visual_provider_wikimedia_v2.py` (NEW)

34 tests in 10 classes. All use mocked HTTP (`unittest.mock.patch` on `urllib.request.urlopen`). No live network.

| Class | Tests | Coverage |
|-------|-------|----------|
| TestQueryTextExtraction | 7 | String, dict, empty, None, non-string, missing key, truncation |
| TestResolveHappyPath | 2 | Candidate returned from first query, first result query selection |
| TestResolveNoResults | 4 | Empty search, all queries empty, no queries, empty text |
| TestResolveRejectsSVG | 2 | SVG rejected, non-SVG accepted alongside SVG |
| TestResolveDimensionFilters | 3 | Below min width, below min height, zero dimensions |
| TestResolveMissingFileUrl | 1 | Empty file URL rejected |
| TestResolveMetadataFallbacks | 1 | No extmetadata → unknown/Unknown defaults |
| TestResolveErrorHandling | 4 | JSON decode error, HTTP 500, URLError, socket timeout |
| TestUserAgentHeader | 2 | Default UA, custom UA |
| TestDownloadHappyPath/Rejects/Errors | 8 | File write, parent dirs, non-image CT, SVG CT, too small, overwrite, no fileUrl, HTTP 404 |

### `tests/test_visual_asset_executor_v2.py` (MODIFIED)

Added 13 new tests:

- `TestExtensionHelpers` (10 tests): MIME-to-ext, URL-to-ext, path computation, query text extraction.
- `TestLiveModeWikimedia` (10 live tests):
  - RESOLVED with asset metadata and file path.
  - Asset path under job_dir.
  - NO_RESULTS when candidate is None.
  - DOWNLOAD_FAILED when download fails.
  - PROVIDER_ERROR on exception.
  - Non-wikimedia provider → PROVIDER_UNAVAILABLE.
  - Missing job_dir → JOB_DIR_REQUIRED.
  - dry_run=True preserved.
  - No legacy v1 fields in live output.
  - wikimedia with live=false → PROVIDER_UNAVAILABLE.
- `TestLiveModeGuard` updated: now tests `JOB_DIR_REQUIRED_FOR_LIVE_EXECUTION` instead of old `LIVE_EXECUTION_NOT_IMPLEMENTED`.

### `tests/test_visual_v2_dry_run_e2e.py` (MODIFIED)

- Added `visual_provider_wikimedia_v2.py` to `V2_MODULES` source isolation list.
- All 22 existing tests pass unchanged.

## What was NOT changed

- `generate_script.py`, `fetch_images.py`, `visual_plan_v2.py`, `visual_asset_router_v2.py` — no changes.
- `asset_validation.py`, `editorial_asset_contract.py`, `prepare_job.py`, `render_job.py`, `run_job.py` — no changes.
- n8n workflows, README, OpenSpec files, `.env.example`, `requirements.txt` — no changes.
- No imports from v1 runtime pipeline modules anywhere.
- No live HTTP calls in any test.
- No pipeline integration, no jobs, no videos.

## Validation

```bash
python3 -m pytest tests/test_visual_provider_wikimedia_v2.py -v  # 34 passed
python3 -m pytest tests/test_visual_asset_executor_v2.py -v       # 69 passed
python3 -m pytest tests/test_visual_v2_dry_run_e2e.py -v          # 22 passed
python3 -m pytest tests/ -v                                       # 656 passed
git diff --check                                                   # clean
```

## Key design decisions

1. **Separate provider module**: `visual_provider_wikimedia_v2.py` is independent of the executor, allowing unit testing with simple HTTP mocks. The executor lazy-imports it only in live mode.

2. **No reuse from `fetch_images.py`**: The v1 module carries `editorial_asset_contract` import and v1-specific scoring/query logic. Duplicating the validated Wikimedia API patterns (~80 lines) is safer and cleaner than extracting shared functions.

3. **`live=true` gate**: A new field in provider_config (`live`) controls whether a provider actually executes. Distinct from `implemented` (code exists) and `enabled` (provider allowed).

4. **Job_dir enforced in live mode**: Live execution without `job_dir` returns an error. Assets always go under `job_dir/assets/`.

5. **First acceptable candidate**: No complex scoring for MVP. First candidate meeting minimum criteria (dimensions, MIME, file URL) wins. This is acceptable for Wikimedia-only and can be enhanced later.

6. **Source isolation maintained**: `visual_provider_wikimedia_v2.py` verified via E2E test to not import any v1 runtime modules. Executor's dry-run path remains import-free.

## Remaining dependencies before pipeline integration

1. A thin entry point (e.g., `fetch_images_v2.py` or `run_job.py` dispatch) that populates `provider_config` and `job_dir`.
2. Bridge between v2 executor output and `prepare_job.py` expectations (asset paths, source metadata).
3. Pexels, Pixabay, FreeAI, Pollinations provider clients following the same pattern.
4. Optional rate limiter enhancement (retry-on-429, per-window limits).
5. Optional scoring/candidate ranking for better selection.
6. Optional `load_provider_config_from_env` helper.
7. Feature flag `VISUAL_PIPELINE_VERSION=v2` in `run_job.py`.
