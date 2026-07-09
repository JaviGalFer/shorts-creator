# Session: Visual Asset Router v2

**Started:** 2026-07-09 18:49 UTC
**Type:** New module (Level 1)
**OpenSpec change:** None (Level 1 bounded new module)

## Objective

Implement a pure Visual Asset Router v2 that sits between the canonicalizer (`visual_plan_v2.py`) and any future image downloader. The router produces a structured sourcing plan from a validated v2 VisualPlan, applying provider routing heuristics, query derivation, and request-level constraints. No I/O, no HTTP, no provider SDK calls, no file access, no environment reads.

## What was built

### `bin/visual_asset_router_v2.py`

Pure module with zero pipeline imports. One public function:

- `build_visual_sourcing_plan_v2(canonical_plan, scene=None, request_visuals=None)` — builds a visual sourcing plan from a canonical v2 VisualPlan, returns `{ok, sourcingPlan, diagnostics}`

#### Provider routing matrix

9 asset preferences → provider assignments with explicit support strength:

| Preference | Providers (support strength) |
|---|---|
| photograph | pexels (strong), pixabay (strong), wikimedia_commons (medium) |
| stock | pexels (strong), pixabay (strong) |
| archive | wikimedia_commons (medium) |
| map | wikimedia_commons (weak) |
| document | wikimedia_commons (weak) |
| painting | wikimedia_commons (medium) |
| diagram | wikimedia_commons (weak), freeai (conditional), pollinations (conditional) |
| illustration | pixabay (medium), pexels (medium), wikimedia_commons (weak), freeai (conditional), pollinations (conditional) |
| generated | freeai (conditional), pollinations (conditional) |

#### Provider availability assumptions

| Provider | Availability | Needs API Key | Query Strategy |
|---|---|---|---|
| wikimedia_commons | available | No | search |
| pexels | conditional | Yes | search |
| pixabay | conditional | Yes | search |
| freeai | conditional | Yes | generate |
| pollinations | conditional | No | generate |

#### Routing statuses (conservative)

- `ROUTABLE`: at least one provider with `supportStrength=strong` AND `availability=available`
- `ROUTABLE_WITH_WARNINGS`: at least one provider, but all are weak/conditional/medium
- `UNROUTABLE`: no provider remains after constraints

This means only a provider that is both `strong` and `available` (no API key needed, known reliable) can produce a clean `ROUTABLE` status. Since `pexels` and `pixabay` are strong but conditional (API key needed), and `wikimedia_commons` is available but medium-level, no current combination produces `ROUTABLE` for any asset preference. All segments produce `ROUTABLE_WITH_WARNINGS` or `UNROUTABLE`.

#### Request-level constraints

Default config:
```json
{
  "allowSearchProviders": true,
  "allowStockAssets": true,
  "allowArchiveAssets": true,
  "allowGeneratedImages": false,
  "preferredProviders": [],
  "blockedProviders": [],
  "maxQueriesPerSegment": 4,
  "providerPriorityPolicy": "balanced"
}
```

Applied in order: provider suitability → blockedProviders → allowSearchProviders → allowStockAssets → allowArchiveAssets → generated double gate → priority policy → final status.

#### Generated-image planning

Generated providers (freeai, pollinations) are planned as routing candidates only. Actual generation belongs to a future executor. Double gate: both `canonical_plan.allowGeneratedImage=true` AND `request_visuals.allowGeneratedImages=true` must be true for generated providers to appear.

#### Query derivation

Tiered, with provenance:
1. segment.searchQuery
2. scene.searchQueries[]
3. scene.imageGenerationPrompt
4. subjects[] + assetPreference (budget permitting)
5. subjects[] + location (budget permitting)
6. subjects[] + period (budget permitting)

Deduplication case-insensitive. Cap at maxQueriesPerSegment. No historical/genre/domain defaults.

#### Priority policies

- `balanced`: support-strength ranking, both plan and request prefs boost equally
- `request_first`: request prefs get strongest priority
- `plan_first`: plan prefs get strongest priority

Policies never promote blocked or gated providers.

### `tests/test_visual_asset_router_v2.py`

80 tests in 13 classes:

1. **Fixture routing** (11 tests): all 6 fixtures tested with conservative statuses
2. **All 9 asset preferences** (12 tests): each preference type tested
3. **Request constraints** (9 tests): blockedProviders, allow flags, double gate
4. **Priority policies** (6 tests): balanced, request_first, plan_first, blocking/gating protection
5. **Generated-image planning** (7 tests): conditional status, API key requirements, warnings, never-clean-Routable
6. **Query derivation** (10 tests): tier ordering, dedup, budget, provenance, no-domain-defaults
7. **Excluded providers** (3 tests): auditability of exclusion reasons
8. **Output contract** (8 tests): top-level keys, segment keys, candidate keys, summary counts
9. **Invalid request config** (4 tests): graceful handling of bad config values
10. **No legacy fields** (7 tests): all fixtures + all asset preferences verified
11. **Summary edge cases** (3 tests): unroutable segments, None request_visuals

## Routing status distribution across fixtures

| Fixture | Segment Pref | Status |
|---|---|---|
| Photosynthesis | diagram | ROUTABLE_WITH_WARNINGS |
| Blockchain | diagram | ROUTABLE_WITH_WARNINGS |
| Octopus | photograph | ROUTABLE_WITH_WARNINGS |
| Octopus | diagram | ROUTABLE_WITH_WARNINGS |
| French Revolution | painting | ROUTABLE_WITH_WARNINGS |
| French Revolution | archive | ROUTABLE_WITH_WARNINGS |
| Marie Curie | photograph | ROUTABLE_WITH_WARNINGS |
| Marie Curie | archive | ROUTABLE_WITH_WARNINGS |
| Pomodoro | diagram | ROUTABLE_WITH_WARNINGS |
| Pomodoro | illustration | ROUTABLE_WITH_WARNINGS |

No segment across all 9 asset preferences currently reaches clean `ROUTABLE`. This is by design: all providers either need an API key (pexels, pixabay, freeai) or have support that is only medium/weak for that preference (wikimedia_commons archive, pollinations).

## What was NOT changed

- `generate_script.py` — no changes
- `fetch_images.py` — no changes
- `visual_plan_v2.py` — no changes
- `editorial_asset_contract.py` — no changes
- `asset_validation.py` — no changes
- `prepare_job.py`, `render_job.py`, `run_job.py` — no changes
- n8n workflows — no changes
- README.md, OpenSpec files — no changes
- No provider calls, LLM calls, jobs, videos

## Validation

```bash
python3 -m pytest tests/test_visual_asset_router_v2.py -v  # 80 passed
python3 -m pytest tests/ -v                                  # 518 passed
git diff --check                                              # clean
```

## Key design decisions

1. **Conservative routing semantics**: `ROUTABLE` requires `strong + available`. Since pexels/pixabay are `strong + conditional` and wikimedia_commons is `medium + available`, no segment currently reaches clean ROUTABLE. A future availability-checker module could promote conditional providers to available once API keys are confirmed.

2. **Generated is planned, not executed**: FreeAI and Pollinations appear as candidates in the sourcing plan when both gates allow them. But they carry explicit warnings that generation requires a future executor. The router never implies it can generate images.

3. **No domain classification**: `period` and `location` are used only as text context in query composition. They never influence routing decisions or provider selection.

4. **Invalid config is non-fatal**: Invalid request_visuals values produce warnings and fall back to defaults. Only truly invalid input shapes (non-dict plan, non-dict request_visuals) cause `ok=false`.

## Remaining dependency before router can be consumed

The router produces a pure sourcing plan. Before it can be consumed:

1. A **future v2 downloader/executor** must consume the sourcing plan, check API keys, call providers, download assets, and persist metadata.
2. The downloader must handle the `ROUTABLE_WITH_WARNINGS` segments — decide what to do when routing is uncertain.
3. Generated image providers require an executor that can actually call FreeAI/Pollinations APIs.
4. An **availability checker** could promote `conditional` providers to `available` when API keys are confirmed, potentially upgrading segments to `ROUTABLE`.
