# Session: Neutralize generic visual query defaults

**Started:** 2026-07-07 23:30 UTC
**Type:** Decontamination refactor (Level 1)
**OpenSpec change:** `improve-historical-visual-pipeline` (task note updated)

## Objective

Remove all hardcoded historical/medieval/war visual templates and genre fallbacks from query-generation paths in `bin/fetch_images.py`. The provider-query resolver must derive queries exclusively from scene metadata (searchQueries, entities, location, period, visualPrompt, imagePrompt). Strategy names must remain routing-only and never become search-query text.

## What was changed

### `bin/fetch_images.py`

1. **`STRATEGY_VISUAL_QUERIES`**: Replaced all 4 strategy dicts (~50 hardcoded visual templates) with empty lists `[]`. Provider queries for Pexels/Pixabay now derive purely from scene metadata (searchQueries + visualPrompt + imagePrompt). No more "old historical photograph", "medieval castle storm", "ancient manuscript illustration", "historical siege scene", "vintage war photograph", etc.

2. **`resolve_queries_for_provider`**:
   - Removed `"historical scene"` universal fallback → returns `[]` when metadata is insufficient
   - Removed `f"historical {strategy.replace('_', ' ')}"` Wikimedia fallback
   - Removed `f"historical {sq}"[:200]` Pexels/Pixabay prefix
   - Removed `f"historical {strategy} scene"` FreeAI and Pollinations fallbacks
   - Strategy name is **never** interpolated into a query string
   - Returns `[]` for all providers when visualPlan is empty or has no searchQueries/prompts

3. **`_fetch_one_asset`**:
   - Added `MISSING_VISUAL_METADATA` check: after `resolve_queries_for_provider` returns `[]`, appends a provider failure with diagnostic reason "MISSING_VISUAL_METADATA (empty visualPlan or no searchQueries/prompts)" and skips to the next provider without attempting any download
   - Removed `f"historical {strategy} scene"` from Pollinations last-resort prompt fallback → uses `q or visual_prompt or image_prompt` only; when all are empty, sets failure reason `"pollinations: MISSING_VISUAL_METADATA (no prompt available)"`

4. **`build_historical_queries`**:
   - Removed `"historical scene"` no-visualPlan fallback → returns `[]`
   - Removed `"historical"` prefix from entity-level fallback queries (`f"historical {ent} illustration"` → `f"{ent} illustration"`)

5. **`main()`**: Removed `"historical scene"` fallback from no-visualPlan path → uses `""` (empty string)

6. **`ASSET_TYPE_QUERY_TERMS`**: Replaced `"walls"` and `"fortress"` with `"view"`, `"scene"`, `"atmosphere"` in `atmospheric_broll` terms

## What was NOT changed

- Editorial role definitions (`HARD_HISTORICAL_ROLES`, `ROLE_ALLOWED_TYPES`, etc.) — left unchanged
- Provider ordering, credential handling, metadata shape
- Asset validation gates, renderability checks, scoring weights
- LLM system prompt, audio, subtitles, render pipeline, runner
- Strategy naming, production modes, web/API endpoints
- `editorial_asset_contract.py`, `asset_validation.py`, `generate_script.py`
- The existing role-specific vocabulary in `_build_scene_query_variants` role_terms (e.g., "occupation zones", "barbed wire") — these are role-level evidence only active when the planner assigns that editorial role, not global defaults

## Tests added (6 new)

In `tests/test_no_topic_specific_contamination.py`:

1. **`test_photosynthesis_queries_no_historical_defaults`** — Enhanced version: queries derive from scene/topic metadata; no medieval/castle/war/battle/fortress/siege defaults via `_collect_all_queries` helper across all provider types

2. **`test_technology_queries_no_historical_defaults`** — Blockchain topic: queries derive from blockchain/distributed-ledger/transaction metadata; no historical defaults. Editorial role is a compatibility fixture, not presented as generic vocabulary.

3. **`test_animals_queries_no_historical_defaults`** — Octopus camouflage topic: queries derive from octopus/camouflage/ocean metadata; no historical defaults. Editorial role is a compatibility fixture, not presented as generic vocabulary.

4. **`test_historical_event_queries_only_metadata_derived`** — French Revolution scene: historical terms (1789, Bastille, Paris) appear ONLY because metadata contains them; no injected medieval/castle/fortress defaults beyond metadata; `resolve_queries_for_provider` for pexels verifies no template injection

5. **`test_weak_metadata_no_historical_fallback`** — Empty visualPlan returns `[]` for all 6 provider types; never emits "historical scene", strategy names, or genre words

6. **`test_query_generation_functions_no_hidden_historical_defaults`** — Source-level scan of 5 functions (`resolve_queries_for_provider`, `_resolve_query_for_segment`, `build_historical_queries`, `_fetch_one_asset` Pollinations branch, `STRATEGY_VISUAL_QUERIES`) verifies no "historical scene" literal, no `f"historical` pattern, no strategy-name-as-query interpolation, all strategy template dicts are empty

## Weak-metadata execution path

1. Scene has `visualPlan = {}` or `visualPlan = {"searchQueries": []}`, `visualPrompt = ""`, `imagePrompt = ""`
2. `resolve_queries_for_provider` returns `[]` for all provider types
3. `_fetch_one_asset` detects empty query list, adds `MISSING_VISUAL_METADATA` failure reason, skips to next provider
4. After all providers exhausted → `failure_classification = "resolution_exhausted"`
5. Returns `{"ok": False, "selected_candidate": null}` with diagnostic failure reasons
6. **No download is attempted. No query is generated. No historical/genre phrase is emitted.**

## Result

- **334 tests passed**, 0 failed
- `git diff --check` clean
- Zero "historical scene" strings remain in production code
- Zero `f"historical` patterns remain in query-generation paths
- Strategy names are routing-only; they never become search-query text
- No production modes, policy layers, live provider runs, or video jobs created
- Current role contracts, provider ordering, metadata shape, and validation gates preserved

## Remaining work before configurable production modes

1. **LLM prompt generalization**: `generate_script.py` SYSTEM_PROMPT contains Berlin/Constantinople teaching examples; replacing with generic placeholders would remove LLM prompt bias (Level 2 work)
2. **Editorial role contract separation**: Current roles (`battle_or_assault`, `border_closure_construction`, etc.) are historical-domain vocabulary; a per-mode role contract system should map domain-specific roles to reusable contract constraints
3. **Strategy naming**: Strategy names (`historical_archive`, `map_or_document`, etc.) imply historical domain; mode-aware strategy routing could map domain-agnostic strategies to provider chains
4. **Domain-agnostic role terms**: `_build_scene_query_variants` role_terms are domain-specific but role-gated; per-mode role contracts would let non-historical modes define different term sets
5. **Multilingual equivalence expansion**: `period_equivalents`/`location_equivalents`/`entity_equivalents` are minimal; per-mode expansion needed for science/technology/animals topics
6. **`LEGACY_KEYWORDS` in `asset_validation.py`**: Spanish-specific legacy keywords; a dynamic topic/trigger approach should trigger per-content-domain keywords
