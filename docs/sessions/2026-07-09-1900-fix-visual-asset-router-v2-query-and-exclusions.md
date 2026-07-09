# Session: Fix visual asset router v2 — query separation and exclusion audit

**Started:** 2026-07-09 19:00 UTC
**Type:** Bounded correctness fix (Level 1)
**Parent session:** `2026-07-09-1849-visual-asset-router-v2.md`

## Objective

Two correctness fixes to the Visual Asset Router v2:

1. Separate search queries from generation prompts in the output contract. `imageGenerationPrompt` was incorrectly included in the generic `queries` list alongside search queries meant for search providers.

2. Complete the excluded-provider audit so every segment accounts for all 5 known providers across `providerCandidates` + `excludedProviders`.

## Fix 1 — Search/generation separation

### Before

`_derive_queries()` returned a single list mixing search queries and `imageGenerationPrompt`. Both search providers (pexsels, pixabay, wikimedia_commons) and generated providers (freeai, pollinations) saw the same query list, causing `imageGenerationPrompt` to leak into search provider queries.

### After

Split into two functions:

- `_derive_search_queries()` — returns `searchQueries` list. Contents: segment.searchQuery, scene.searchQueries[], subjects + assetPreference, subjects + location/period (budget permitting). **Never includes imageGenerationPrompt**.

- `_derive_generation_prompts()` — returns `generationPrompts` list. Contents: scene.imageGenerationPrompt. Falls back to segment.searchQuery or scene.searchQueries[0] if imageGenerationPrompt is missing (for generated providers only).

Segment output contract changed from:

```json
{
  "queries": [{ "text": "...", "source": "..." }]
}
```

To:

```json
{
  "searchQueries": [{ "text": "...", "source": "..." }],
  "generationPrompts": [{ "text": "...", "source": "..." }]
}
```

### Key behavioral change

- `imageGenerationPrompt` only appears in `generationPrompts`, never in `searchQueries`.
- Search providers (pexels, pixabay, wikimedia_commons) get `searchQueries` only.
- Generated providers (freeai, pollinations) can reference `generationPrompts` for prompt input.
- When `imageGenerationPrompt` is absent, generation prompts fall back to segment.searchQuery or scene.searchQueries[0] with fallback provenance markers.

## Fix 2 — Complete excluded provider audit

### Before

Only providers in the routing matrix row for the asset preference were represented. Providers not supporting that preference were silently absent from the output.

### After

After building the initial candidate list from the routing matrix row, the router adds exclusion entries for all providers NOT in the matrix. Example for `diagram`:

```json
{
  "provider": "pexels",
  "candidateStatus": "excluded",
  "availability": "conditional",
  "exclusionReason": "provider does not support assetPreference='diagram' in v2 routing matrix",
  "warnings": []
}
```

Every segment now has exactly 5 provider entries across `providerCandidates` + `excludedProviders`. No provider is silently omitted.

### Template exclusion messages

| Case | Exclusion reason template |
|---|---|
| Not in matrix row | `provider does not support assetPreference='{pref}' in v2 routing matrix` |
| Blocked by request | `blocked by request_visuals.blockedProviders` |
| Search disabled | `search providers disabled: request_visuals.allowSearchProviders=false` |
| Stock disabled | `stock assets disabled: request_visuals.allowStockAssets=false` |
| Archive disabled | `archive assets disabled for '{pref}': request_visuals.allowArchiveAssets=false` |
| Generated blocked | `generated images blocked: canonical_plan.allowGeneratedImage=false` or `...request_visuals.allowGeneratedImages=false` |

## Tests added (13 new, 93 total)

### Search/generation separation (6 tests)

| Test | Assertion |
|---|---|
| `test_image_generation_prompt_not_in_search_queries` | prompt text/source never in searchQueries |
| `test_generation_prompts_contains_image_generation_prompt` | prompt appears in generationPrompts |
| `test_generated_segment_generation_prompts_accessible` | generated pref with both gates: FreeAI/Pollinations included, generationPrompts present |
| `test_generated_segment_search_providers_excluded` | generated pref: pexels/pixabay/wikimedia all in excludedProviders |
| `test_photograph_segment_no_generation_prompt_in_search` | photograph + imageGenerationPrompt: prompt not in searchQueries |
| `test_generation_prompt_fallback_to_segment_query` | missing imageGenerationPrompt: falls back to segment.searchQuery with fallback marker |

### Excluded provider completeness (5 tests)

| Test | Assertion |
|---|---|
| `test_all_prefs_have_five_providers` | all 9 asset prefs: candidates + excluded = exactly 5 |
| `test_diagram_excludes_pexels_pixabay_as_unsuitable` | diagram: pexels/pixabay excluded with suitability reason containing "diagram" |
| `test_stock_excludes_wikimedia_as_unsuitable` | stock: wikimedia_commons excluded with suitability reason containing "stock" |
| `test_generated_both_gates_false_all_search_excluded` | generated with gates=false: all 5 providers excluded, UNROUTABLE, total=5 |
| `test_every_provider_appears_exactly_once_per_segment` | no duplicate providers across candidates + excluded |

### Regression (2 tests)

| Test | Assertion |
|---|---|
| `test_all_six_fixtures_still_conservative` | all 6 fixtures: ok, conservative statuses, 5 providers per segment, no legacy fields |
| `test_no_legacy_fields_anywhere` | recursive legacy field check on octopus fixture |

## What was NOT changed

- No runtime pipeline files
- No v1 legacy fields emitted (verified recursively)
- No provider calls, HTTP, file I/O, environment reads

## Validation

```bash
python3 -m pytest tests/test_visual_asset_router_v2.py -v  # 93 passed
python3 -m pytest tests/ -v                                  # 531 passed
git diff --check                                              # clean
```

## Remaining dependency before real download/generation

Same as parent session: a future v2 downloader/executor must consume the sourcing plan. The output now cleanly separates `searchQueries` (for search providers) from `generationPrompts` (for generated providers), and each segment accounts for all 5 known providers, making the contract unambiguous for any consumer.
