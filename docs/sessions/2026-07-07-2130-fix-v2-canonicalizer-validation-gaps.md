# Session: Fix v2 canonicalizer validation gaps

**Started:** 2026-07-07 21:30 UTC
**Type:** Module fix (Level 1)
**OpenSpec change:** None

## Objective

Correct four validation gaps in the VisualPlan v2 canonicalizer:

1. Cross-field validation compared raw (non-canonical) enum values
2. Segment fields lacked strict type validation (non-string assetPreference, searchQuery, transition silently passed)
3. List-item strings had no per-item length limits
4. Legacy v1 fields were treated as unknown extensions instead of hard errors

## Changes

### 1. Legacy v1 field rejection

Added `LEGACY_V1_FIELDS` constant (editorialRole, visualTemporalIntent, strategy, primaryAssetType, secondaryAssetType, mood, style, licenseRequired, visualImportance).

`_collect_field_errors` now emits `LEGACY_FIELD_NOT_ALLOWED:<field>` as a hard error (not a warning) when any legacy field is present. Legacy fields are removed from the `unknown` set — they are not listed as ordinary unknowns.

`_canonicalize_plan` skips legacy fields when copying unknown fields into the canonical output. They never appear in `canonicalPlan`.

Genuine future extensions (not in LEGACY_V1_FIELDS, not in ALL_KNOWN_FIELDS) remain preserved with `UNKNOWN_FIELD` warnings.

### 2. Cross-field canonical normalization

`_validate_cross_field` now normalizes scene-level `assetPreferences` and segment `assetPreference` values using `.strip().lower()` before comparison. A scene with `assetPreferences=["DIAGRAM"]` correctly matches a segment with `assetPreference="diagram"`. Same for generated preference detection.

No input mutation — comparisons use a local normalization expression only.

### 3. Strict segment field type validation

In `_validate_visual_sequence`, added explicit type checks after the existing segmentIndex and durationFraction checks:

| Field | Expected type | Error code |
|-------|--------------|------------|
| assetPreference | str | INVALID_FIELD_TYPE |
| searchQuery | str or null | INVALID_FIELD_TYPE |
| transition | str | INVALID_FIELD_TYPE |

Also added length validation: assetPreference max 100, searchQuery max 200, transition max 20 (FIELD_TOO_LONG).

The segmentIndex and durationFraction checks already rejected booleans (isinstance with `not isinstance(x, bool)` guard).

### 4. List-item string length limits

In `_validate_plan_types`, after the existing list-item type check (must be str), added a length check using `STRING_FIELD_MAX[field]`:
- subjects[*] max 500
- searchQueries[*] max 200
- assetPreferences[*] max 100
- preferredProviders[*] max 100

### Cleanup

Removed unused `_validate_enum` helper function (never called).

## Tests added

27 new tests in 6 classes (104 total in test file):

| Class | Tests | Coverage |
|-------|-------|----------|
| TestCaseInsensitiveCrossField | 2 | Uppercase scene prefs match lowercase segment; uppercase GENERATED with flag |
| TestSegmentTypeValidation | 6 | Non-string assetPreference, searchQuery, transition; bool segmentIndex/durationFraction; null searchQuery accepted |
| TestSegmentLengthValidation | 3 | assetPreference >100, searchQuery >200, transition >20 |
| TestListItemLengthLimits | 5 | subject >500, searchQuery item >200, assetPreference item >100, provider >100, at-limit acceptance |
| TestLegacyFieldRejection | 5 | All 9 legacy fields individually rejected; canonicalPlan null on rejection; unknown field still preserved; multiple legacy errors; legacy not counted as unknown |
| TestRegressionSixFixtures | 6 | All 6 domain fixtures still canonicalize cleanly |

## Validation

```bash
python3 -m pytest tests/test_visual_plan_v2.py -v  # 104 passed
python3 -m pytest tests/ -v                          # 438 passed, 0 failed
git diff --check                                      # clean
```

## Files changed

- `bin/visual_plan_v2.py` — LEGACY_V1_FIELDS constant, updated _collect_field_errors, updated _validate_cross_field, added segment type/length checks, added list-item length limits, updated _canonicalize_plan to skip legacy fields
- `tests/test_visual_plan_v2.py` — 6 new test classes with 27 new tests
- `docs/sessions/2026-07-07-2130-fix-v2-canonicalizer-validation-gaps.md` — this log

## Files NOT changed

generate_script.py, fetch_images.py, editorial_asset_contract.py, asset_validation.py, prepare_job.py, render_job.py, run_job.py
