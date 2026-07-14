# Session: Visual Asset Executor v2 — dry-run only

**Started:** 2026-07-09 19:40 UTC
**Type:** New module (Level 1)
**OpenSpec change:** None (Level 1 bounded new module)

## Objective

Implement the dry-run contract for Visual Asset Executor v2. This module consumes the `sourcingPlan` from `build_visual_sourcing_plan_v2`, evaluates provider availability deterministically, and returns what would be attempted in a live execution. No HTTP, no provider calls, no file writes, no environment reads. Stdlib only. No imports from runtime pipeline modules.

## What was built

### `bin/visual_asset_executor_v2.py`

Pure module with zero pipeline imports. One public function:

- `execute_visual_sourcing_plan_v2(sourcing_plan, provider_config, request_visuals=None, dry_run=True, job_dir=None)` — dry-run execution of a v2 sourcing plan, returns `{ok, dryRun, resolvedAssets, unresolvedSegments, dryRunAttempts, diagnostics}`

#### Provider availability evaluation

Deterministic, pure function `_evaluate_provider_availability(provider, config)`:

| Condition | Result |
|-----------|--------|
| Provider not in config | `UNKNOWN_PROVIDER` |
| `enabled` is `false` | `DISABLED_BY_REQUEST` |
| `implemented` is `false` | `NOT_IMPLEMENTED` |
| `requiresApiKey=true` + `apiKeyPresent=false` | `MISSING_API_KEY` |
| Otherwise | `AVAILABLE` |

#### Secret field detection

Fields named `api_key`, `apiKey`, `token`, or `secret` in provider config produce `SECRET_FIELD_IGNORED` warnings. Real API key strings are never accepted or logged.

#### Provider config shape

```json
{
  "wikimedia_commons": {"enabled": true, "implemented": false, "requiresApiKey": false},
  "pexels": {"enabled": true, "implemented": false, "requiresApiKey": true, "apiKeyPresent": false},
  ...
}
```

Boolean `apiKeyPresent`, never `api_key` string.

#### Dry-run segment processing

For each segment in `sourcingPlan.segments`:

1. `routingStatus == "UNROUTABLE"` → `UNRESOLVED` with unsupported reasons
2. Iterate `providerCandidates` in priority order (skip `excluded`)
3. First candidate with `AVAILABLE` → `SKIPPED_DRY_RUN` with full attempt details
4. All candidates unavailable → `PROVIDER_UNAVAILABLE` with per-provider availability reasons

#### Query/prompt dispatch

| `queryStrategy` | Uses |
|-----------------|------|
| `"search"` | `segment.searchQueries` |
| `"generate"` | `segment.generationPrompts` |

`_dispatch_inputs(candidate, segment)` returns `(selectedInputType, selectedInputs)`.

#### Live execution guard

`dry_run=False` returns `ok=false` with error code `LIVE_EXECUTION_NOT_IMPLEMENTED`.

#### Allowed executor statuses (this Build only)

`SKIPPED_DRY_RUN`, `PROVIDER_UNAVAILABLE`, `UNRESOLVED`, `LIVE_EXECUTION_NOT_IMPLEMENTED`, `INVALID_INPUT`

Not used yet: `RESOLVED`, `NO_RESULTS`, `DOWNLOAD_FAILED`, `GENERATION_FAILED`.

### `tests/test_visual_asset_executor_v2.py`

45 tests in 14 classes:

| Category | Tests | Key assertions |
|----------|-------|---------------|
| Input/output contract | 9 | valid shape → ok=true; non-dict → INVALID_INPUT; missing keys → errors; summary counts correct; jobDir/requestVisualsProvided traced |
| Provider availability (unit) | 7 | All statuses verified at `_evaluate_provider_availability` level |
| Secret field ignored | 4 | `api_key`, `apiKey`, `token`, `secret` → SECRET_FIELD_IGNORED warning |
| Candidate priority | 3 | Priority order respected; unavailable skipped; excluded never attempted |
| Query/prompt separation | 4 | Search → searchQueries; generate → generationPrompts; cross-contamination prevented |
| Segment behavior | 3 | SKIPPED_DRY_RUN, PROVIDER_UNAVAILABLE, UNRESOLVED |
| Live mode guard | 2 | dry_run=False → ok=false + LIVE_EXECUTION_NOT_IMPLEMENTED |
| No legacy fields | 1 | Recursive check: 9 legacy v1 fields absent from all output |
| Provider availability map | 2 | Full map in diagnostics; candidates not in config added as UNKNOWN_PROVIDER |
| Multiple segments | 1 | Mixed segment statuses produce correct output counts |
| Invalid segment shapes | 2 | Non-dict segment → warning; missing keys → errors |
| Dispatch inputs (unit) | 4 | `_dispatch_inputs` tested directly for all strategies and edge cases |
| Diagnostics builder | 3 | Empty diagnostics structure, jobDir, requestVisualsProvided |

## What was NOT changed

- `generate_script.py` — no changes
- `fetch_images.py` — no changes
- `visual_plan_v2.py` — no changes
- `visual_asset_router_v2.py` — no changes
- `asset_validation.py` — no changes
- `editorial_asset_contract.py` — no changes
- `prepare_job.py`, `render_job.py`, `run_job.py` — no changes
- n8n workflows — no changes
- README.md, OpenSpec files — no changes
- No imports from runtime pipeline modules
- No HTTP, provider SDK calls, API key reads, .env reads
- No image downloads, image generation, file writes
- No jobs, no videos, no runtime integration

## Validation

```bash
python3 -m pytest tests/test_visual_asset_executor_v2.py -v  # 45 passed
python3 -m pytest tests/ -v                                  # 576 passed
git diff --check                                              # clean
```

## Key design decisions

1. **Dry-run only for this Build**: Even though the `_evaluate_provider_availability` function can return `AVAILABLE`, no provider is ever called. The executor only says "I would call this provider." Actual execution belongs to a future build.

2. **Provider config is passed in, never loaded from env**: The function accepts `provider_config` as a dict. A future convenience loader (`load_provider_config_from_env`) can populate this from environment, but the executor itself is pure and testable.

3. **Boolean `apiKeyPresent`, not `api_key` string**: The config uses a boolean to signal "key is present" without storing the actual secret. Fields named `api_key`, `apiKey`, `token`, or `secret` are explicitly warned about. This makes the module safe for logs and tests.

4. **No imports from runtime modules**: The executor imports only stdlib. It does not reuse `fetch_images.py` provider functions, scoring logic, or any v1 pipeline code. Provider reuse can be designed later once the dry-run contract is stable.

5. **Router trust model**: The executor does not redesign routing, re-apply `blockedProviders`, or re-evaluate `excludedProviders`. It trusts the Router's output. The Router already accounts for all 5 providers per segment via `providerCandidates` + `excludedProviders`.

## Remaining dependency before live asset download/generation

1. A future build must implement actual provider calls (Wikimedia search, Pollinations generation, etc.)
2. Provider functions from `fetch_images.py` may be reused or rewritten as clean v2 provider clients
3. The live executor must handle HTTP errors, rate limiting, download failures, and generation failures with explicit status codes
4. `RESOLVED`, `NO_RESULTS`, `DOWNLOAD_FAILED`, `GENERATION_FAILED` statuses must be added
5. A `load_provider_config_from_env` helper should populate the `provider_config` dict from environment variables
6. File system writes (downloading assets to `job_dir/assets/`) must be implemented
7. Integration with `run_job.py` via schema version dispatch
