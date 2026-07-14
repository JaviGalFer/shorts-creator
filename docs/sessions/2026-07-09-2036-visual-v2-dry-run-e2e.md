# Session: v2 visual stack dry-run E2E validation

**Started:** 2026-07-09 20:36 UTC
**Type:** Validation tests (Level 1)
**OpenSpec change:** None (Level 1 validation only)

## Objective

Validate the generic v2 visual stack end-to-end in dry-run mode:

```
VisualPlan v2 canonicalizer → Visual Asset Router v2 → Visual Asset Executor v2 dry-run
```

Confirm that all three components compose correctly across multiple fixture types and provider config scenarios. No runtime integration.

## What was built

### `tests/test_visual_v2_dry_run_e2e.py`

22 tests in 6 classes exercising the full v2 chain.

#### Fixtures tested (5 generic types)

| Fixture | Asset preferences | Segments |
|---------|------------------|----------|
| Photosynthesis | diagram | 1 |
| Octopus | photograph, diagram | 2 |
| Generated (abstract) | generated | 1 |
| Pomodoro | diagram, illustration | 2 |
| French Revolution | painting, archive | 2 |

All fixtures use `_schemaVersion: 2` and neutral v2 field names only.

#### Provider config scenarios

| Config | Scenario | Key characteristic |
|--------|----------|-------------------|
| A | All providers `implemented: false` | Everything `PROVIDER_UNAVAILABLE` |
| B | Wikimedia `implemented: true`, rest `false` | Search segments get `SKIPPED_DRY_RUN` |
| C | Generated providers `implemented: true` + keys present; search disabled | Generated segments get `SKIPPED_DRY_RUN` with `generationPrompts` |

#### Test classes

| Class | Tests | Description |
|-------|-------|-------------|
| `TestConfigANoneImplemented` | 5 | All providers not implemented → all segments provider-unavailable |
| `TestConfigBWikimediaAvailable` | 5 | Wikimedia available → search segments dry-run, generated blocked without gates |
| `TestConfigCGeneratedAvailable` | 3 | Generated providers available → `generationPrompts` used, search blocked |
| `TestE2ENoLegacyFields` | 4 | Recursive legacy field check across canonicalizer, router, executor outputs for all 5 fixtures × 3 configs |
| `TestPipelineInvariants` | 4 | Segment count preserved; router uses searchQueries + generationPrompts; executor input types match strategy; generated inputs validated |
| `TestV2StackSourceIsolation` | 1 | Source-level check: v2 modules never import runtime pipeline modules |

#### Required assertions verified (per test)

1. Canonicalizer returns `ok=true`
2. Router returns `ok=true`
3. Executor returns `ok=true` (except intentional invalid cases)
4. Executor `dryRun=true`
5. Executor `resolvedAssets=[]`
6. No legacy v1 fields anywhere in any output
7. Router output uses `searchQueries`, `generationPrompts`, `providerCandidates`, `excludedProviders`
8. Executor `selectedInputType=searchQueries` for search providers
9. Executor `selectedInputType=generationPrompts` for generated providers
10. No test imports `fetch_images.py`

#### Source isolation check

The final test reads all three v2 source files (`visual_plan_v2.py`, `visual_asset_router_v2.py`, `visual_asset_executor_v2.py`) and asserts they contain no `import` or `from` statements referencing any of:

```
fetch_images, asset_validation, editorial_asset_contract,
generate_script, prepare_job, render_job, run_job
```

## What was NOT changed

- `generate_script.py` — no changes
- `fetch_images.py` — no changes
- `visual_plan_v2.py` — no changes
- `visual_asset_router_v2.py` — no changes
- `visual_asset_executor_v2.py` — no changes
- `asset_validation.py` — no changes
- `editorial_asset_contract.py` — no changes
- `prepare_job.py`, `render_job.py`, `run_job.py` — no changes
- n8n workflows, README, OpenSpec files — no changes
- No HTTP, provider calls, API key reads, .env reads
- No image download, generation, file writes
- No jobs, no videos, no runtime integration

## Validation

```bash
python3 -m pytest tests/test_visual_v2_dry_run_e2e.py -v  # 22 passed
python3 -m pytest tests/ -v                                # 598 passed
git diff --check                                            # clean
```

## Key observations

1. **Config A (none implemented)**: All 5 fixtures produce 0 `dryRunAttempts` and all segments become `PROVIDER_UNAVAILABLE`. This confirms the default config correctly simulates "nothing is ready yet."

2. **Config B (wikimedia available)**: Segments routed to wikimedia_commons produce `SKIPPED_DRY_RUN` with `selectedInputType=searchQueries`. The generated-only fixture remains `UNRESOLVED` when request gates are closed.

3. **Config C (generated available)**: Segments with `generated` preference produce `SKIPPED_DRY_RUN` with `selectedInputType=generationPrompts`. Search providers are disabled — only `freeai`/`pollinations` appear as candidates. The double gate (`allowGeneratedImage` from plan + `allowGeneratedImages` from request) is respected.

4. **Legacy field isolation**: Recursive checks across all 5 fixtures × 3 configs confirm zero v1 fields appear. The source-level isolation check confirms no v2 module imports runtime pipeline code.

5. **Segment count invariance**: All 5 fixtures show exact segment count preservation across canonicalizer → router → executor.

## Remaining dependency before live asset download/generation

Same as prior session: a future build must implement actual provider calls, HTTP error handling, file downloads to `job_dir/assets/`, and the `RESOLVED` / `NO_RESULTS` / `DOWNLOAD_FAILED` / `GENERATION_FAILED` statuses. The E2E chain is validated end-to-end in dry-run mode and is ready for a live executor build.
