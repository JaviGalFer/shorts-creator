# Session: Asset Validation v2 Neutral Metadata

**Created:** 2026-07-10 23:20

## Objective

Adapt `asset_validation.py` quality gate to support v2 neutral metadata produced by Visual Asset Bridge v2, enabling v2 jobs to achieve PASS without requiring v1 legacy fields (`editorialRole`, `strategy`, etc.).

Second iteration: fix gaps found in post-review — skip legacy semantic rules for v2, make pexels/pixabay non-low-confidence in v2, add `segment_validation_fail` and `renderability_fail` blocking, implement v2-specific clean status derivation.

## Files changed

| File | Change |
|------|--------|
| `bin/asset_validation.py` | V2 detection via `_visualAssetBridgeV2`; `is_v2` parameter on `detect_placeholder_content`, `validate_metadata_completeness`, `check_provider_allowed`; skip legacy semantic rules for v2; `segment_validation_fail` rule; `V2_LOW_CONFIDENCE_PROVIDERS`; v2-specific status derivation |
| `tests/test_asset_validation_v2_neutral_metadata.py` | 22 tests: 8 v2 pass/blocks/review, legacy-rule absence, segment-validation, renderability, pexels/pixabay/pollinations v2, no-mutation check, v1 regression suite |

**Not modified:** `visual_asset_bridge_v2.py`, `prepare_job.py`, `render_job.py`, `fetch_images_v2.py`, `run_job.py`, any provider modules, OpenSpec.

## Detection of v2 metadata

```python
is_v2 = bool(metadata.get("_visualAssetBridgeV2"))
```

Single boolean propagated as `is_v2=False` default parameter to affected functions. No domain/topic/provider heuristics.

## V1 rules skipped for v2

The following legacy semantic validations are NOT executed for v2 metadata:

| Function | Reason |
|---|---|
| `check_editorial_coherence` | Depends on `editorialRole` compatibility matrix |
| `check_role_evidence` | Validates v1-specific role evidence (border_closure, consequence_or_legacy) |
| `check_reuse_compatibility` | Depends on `originalEditorialRole`, `reuseReason`, legacy year extraction |
| `check_modern_asset_context` | Depends on `editorialRole` vs `SOFT_ROLES`, `LEGACY_KEYWORDS` |

For v1, these continue executing exactly as before.

## V2 rule adaptations (first iteration)

| Rule | V2 behavior | V1 behavior |
|---|---|---|
| `editorialRole` | Not required (`missing_editorialRole` never fires) | Required as before |
| `score == 0.0` | Neutral sentinel (no `score_below_minimum`) | Triggers `score_below_minimum` |
| `score > 0 and < 30` | Triggers `score_below_minimum` normally | Unchanged |
| `queryUsed` | Recognized as provenance alongside `searchQuery` | Ignored (only `searchQuery`) |
| `score == 0.0` provenance | 0.0 does NOT count as real score; need `queryUsed` or `searchQuery` | Any non-None score counts |
| Per-segment diagnostic `query` | Reads `queryUsed` || `searchQuery` | Reads `searchQuery` |
| `ai_generated_misuse` | Never fires for v2 (editorialRole absent) | Fires as before |

## V2 rule adaptations (second iteration — corrective)

| Rule | V2 behavior | V1 behavior |
|---|---|---|
| Legacy semantic rules | All skipped (coherence, role evidence, reuse, modern context) | All executed |
| `segment_validation_fail` | New rule: blocks when `segmentValidationStatus == "FAIL"` even with valid file | Not applicable |
| `renderability_fail` | Always BLOCKS (in v2 blocking set) | Contributes to failures, not explicitly blocking |
| Pexels provider | NOT low confidence in v2 | Low confidence (in `LOW_CONFIDENCE_PROVIDERS`) |
| Pixabay provider | NOT low confidence in v2 | Not in `LOW_CONFIDENCE_PROVIDERS` |
| Pollinations provider | Low confidence in v2 (`V2_LOW_CONFIDENCE_PROVIDERS`) | Low confidence + ai_generated_misuse |
| `negative_score` | BLOCKED | Unchanged (informational) |

## V2 status derivation

Clean v2 status logic with explicit rule categories:

**BLOCKED** rules:
`segment_validation_fail`, `renderability_fail`, `negative_score`, `file_not_found`, `not_decodable`, `dimensions_too_small`, `placeholder_provider`, `placeholder_filename`, `no_asset_metadata`, `missing_provider`, `no_provenance`

**REVIEW_REQUIRED** rules:
`low_confidence_provider`, `score_below_minimum`

**Fallback:** any other unclassified failure → `REVIEW_REQUIRED`

**PASS:** zero failures.

V1 status derivation unchanged (full legacy branching preserved).

## Confirmation: no legacy fields added

- `visual_asset_bridge_v2.py` untouched — no `editorialRole`, `searchQuery`, or fake scores added
- `asset_validation.py` only skips/relaxes v1-specific rules for v2; never injects fields into metadata
- Test `test_v2_no_legacy_fields_added` verifies deep equality of metadata before/after validation

## Confirmation: no domain modes added

- No `historical`, `science`, `general`, `documentary`, `legacy` modes
- `is_v2` detection is purely mechanical: single `bool()` on bridge marker
- No topic-specific configuration or branching

## Tests executed

| Suite | Result |
|---|---|
| `test_asset_validation_v2_neutral_metadata.py` | 22 passed |
| All v2 suites (6 files) | 158 passed |
| Full suite (`--ignore=data`) | 820 passed, 16 failed |

### Baseline of pre-existing v1 failures

All 16 failures are pre-existing, unrelated to asset_validation changes:

- 15 in `tests/test_run_job.py` — v1 contract verification failures (assets stage checking for ASSETS_FETCHING status)
- 1 in `tests/test_semantic_asset_validation.py` — `test_hard_role_fallback_to_pexels_with_acceptable_candidate`

Pass rate went from 814 to 820 (+6 new tests), zero regressions.

## Decision: E2E readiness

**Ready for first v2 live E2E.**

A v2 pipeline job with Wikimedia, Pexels, or Pixabay provider and valid files will achieve PASS through asset validation. Pollinations v2 assets will achieve REVIEW_REQUIRED (not BLOCKED). Unresolved segments (segmentValidationStatus=FAIL) correctly BLOCK. All v1 behavior is preserved with zero semantic changes.

## Non-goals

- No E2E jobs executed
- No providers, downloads, or renders
- No bridge changes (`visual_asset_bridge_v2.py` untouched)
- No OpenSpec modifications
- No commit made
- No new semantic v2 validators designed
- No `editorialRole`/`searchQuery`/fake scores added to v2 metadata
