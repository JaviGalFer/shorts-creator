# Session: VisualPlan v2 canonicalizer and validator MVP

**Started:** 2026-07-07 21:26 UTC
**Type:** New module (Level 1)
**OpenSpec change:** None (Level 1 refactor not requiring OpenSpec)

## Objective

Implement a pure, isolated VisualPlan v2 canonicalizer and validator module. Accepts only v2 plans, validates neutral fields and types, canonicalizes values, returns structured diagnostics. Preserves generic semantics. Never infers legacy v1 fields.

## What was built

### `bin/visual_plan_v2.py`

Pure module with zero pipeline imports. Two public functions:

- `canonicalize_visual_plan_v2(plan, scene=None)` — validate + canonicalize, returns `{ok, canonicalPlan, diagnostics}`
- `validate_visual_plan_v2(plan, scene=None)` — validate only, returns `{ok, diagnostics}`

#### v2 contract fields

**Required:** `_schemaVersion` (must be `2` as int), `visualIntent`, `subjects`, `searchQueries`, `assetPreferences`, `visualSequence`

**Optional with defaults:** `period` (null), `location` (null), `allowGeneratedImage` (false), `preferredProviders` ([]), `imageGenerationPrompt` (null), `negativePrompt` (null)

#### Allowed enums

**visualIntent:** explain, show, compare, contextualize, immerse, emphasize

**assetPreferences / assetPreference:** diagram, illustration, photograph, painting, archive, map, document, stock, generated

**transition:** cut, fade

**preferredProviders:** wikimedia_commons, pexels, pixabay, freeai, pollinations

#### Validation rules implemented

| Category | Examples |
|----------|----------|
| Schema version | `"2"` (string) → error; `1` → UNSUPPORTED_SCHEMA_VERSION |
| Required fields | missing → REQUIRED_FIELD_MISSING |
| Field types | subjects must be list[str]; allowGeneratedImage must be bool; no type coercion |
| Empty required | empty subjects/searchQueries/assetPreferences/visualSequence → error |
| Enum values | case-insensitive validation against allowed sets |
| Segment consistency | segmentIndex sequential 1..N, no duplicates, no zero; durationFraction sum = 1.0 ± 0.01 |
| Cross-field | segment assetPreference must be in scene assetPreferences; "generated" requires allowGeneratedImage=true |
| Provider warnings | unrecognized providers warn but don't fail |

#### Canonicalization operations

- Whitespace trim on all strings
- Empty strings → null for period/location/imageGenerationPrompt/negativePrompt
- Enum values lowercased
- Provider aliases normalized (wikimedia → wikimedia_commons)
- Duplicate assetPreferences removed (preserving first occurrence)
- Segments sorted by segmentIndex
- Optional defaults applied when field missing
- Unknown fields preserved in-place with UNKNOWN_FIELD warnings

### `tests/test_visual_plan_v2.py`

77 tests in 13 classes:

1. **Fixture canonicalization** (12 tests): photosynthesis, blockchain, octopus, French Revolution, Marie Curie, Pomodoro — each tested for valid output + no legacy fields inferred
2. **Invalid schema** (11 tests): string schema version, unsupported version, float version, missing required fields, non-dict input
3. **Invalid enums** (4 tests): invalid visualIntent, assetPreference, segment preference, transition
4. **Empty fields** (4 tests): empty subjects, searchQueries, assetPreferences, visualSequence
5. **Invalid types** (4 tests): subjects not list, non-string elements, allowGeneratedImage not bool, searchQueries not list
6. **Segment index** (3 tests): non-sequential, zero index, duplicate index
7. **Duration fraction** (4 tests): sum not 1.0, over 1.0, zero, negative
8. **Cross-field consistency** (7 tests): segment preference not in scene preferences, generated without flag, generated with flag, generated in segment only, image prompt warnings
9. **Canonicalization transformations** (10 tests): whitespace trim, empty-to-null, enum lowercasing, provider aliases, deduplication, defaults, unknown fields preserved, segment sorting, provider lowercasing, unrecognized provider warnings
10. **Validate function** (3 tests): valid plan, invalid plan, no canonicalization
11. **All enum values** (5 tests): every visualIntent, assetPreference, new preferences (painting/map/document), transition, provider accepted
12. **No legacy fields inferred** (6 tests): each of the 6 fixtures verified free from editorialRole, visualTemporalIntent, strategy, primaryAssetType, secondaryAssetType, mood, style, licenseRequired, visualImportance
13. **Field summary** (3 tests): present count, missing on error, unknown fields

## What was NOT changed

- `generate_script.py` — LLM continues to emit v1 visualPlan
- `fetch_images.py` — no changes to scoring, routing, validation
- `editorial_asset_contract.py` — roles frozen
- `asset_validation.py` — gates unchanged
- `prepare_job.py`, `render_job.py`, `run_job.py` — unchanged
- No provider calls, LLM calls, jobs, videos, OpenSpec refactor

## Validation

```bash
python3 -m pytest tests/test_visual_plan_v2.py -v  # 77 passed
python3 -m pytest tests/ -v                          # 411 passed, 0 failed
git diff --check                                      # clean
```

## Key design decisions

1. **Case-insensitive enum validation**: "EXPLAIN", "Diagram", "WIKIMEDIA" all accepted and lowercased during canonicalization. The raw form never reaches the canonicalPlan.

2. **Unknown fields preserved inline**: Not moved to an `extensions` object. They stay at their original location in `canonicalPlan` with `UNKNOWN_FIELD` warnings. This is simpler, deterministic, and lossless — future schema versions can pick them up.

3. **No type coercion**: `_schemaVersion: "2"` → hard error. `allowGeneratedImage: "yes"` → hard error. The canonicalizer only applies semantic-preserving normalizations.

4. **No v1 inference**: The module imports nothing from the pipeline. It has no concept of editorialRole, strategy, primaryAssetType, visualTemporalIntent, or any v1 contract field. The test suite explicitly asserts these are never present in any canonical plan.

## Remaining dependency before v2 can be consumed by the resolver

The v1 pipeline (`fetch_images.py`) expects v1 visualPlan fields (editorialRole, strategy, primaryAssetType, etc.). The v2 canonicalizer produces v2 plans. A future adapter or a native v2 resolver is needed before v2 plans can flow through asset sourcing.

The canonical design boundary is:

```
v2 canonicalizer (built)
    ↓ validated neutral v2 plan
    ↓
future generic v2 resolver OR future v2→v1 historical adapter
    ↓
current v1 pipeline (to be replaced or wrapped)
```
