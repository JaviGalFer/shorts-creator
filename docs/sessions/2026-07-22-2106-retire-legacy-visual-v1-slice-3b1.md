# Session: retire-legacy-visual-v1 Slice 3B1 — Remove dead V1 prompts

**Date:** 2026-07-22
**Model:** opencode/deepseek-v4-flash-free (low, Build)
**Category:** implementation

## Objective

Remove four dead V1 prompt symbols from `generate_script.py` and their tests:

- `SYSTEM_PROMPT`
- `_build_duration_prompt_instruction`
- `_build_retry_instruction`
- `_build_user_prompt`

## Changes

### `bin/generate_script.py`

- Removed `SYSTEM_PROMPT` constant (V1 historical prompt, ~256 lines)
- Removed `_build_duration_prompt_instruction` (V1 duration builder)
- Removed `_build_retry_instruction` (V1 retry builder)
- Removed `_build_user_prompt` (V1 user prompt builder)
- Preserved `SYSTEM_PROMPT_V2`, `_build_duration_prompt_instruction_v2`, `_build_retry_instruction_v2`, `_build_user_prompt_v2`
- Preserved `_validate_script_structure` (deferred to Slice 3B2)
- Preserved `_validate_and_canonicalize_script_v2`, `call_llm` (default `SYSTEM_PROMPT_V2`)
- Preserved all `editorial_asset_contract` imports (still needed by validator)
- CLI `choices=[2]`, `default=2`, `SystemExit(2)` for flag 1 unchanged

### `tests/test_generate_script.py`

Removed 13 tests:
- 10 SYSTEM_PROMPT content tests (decision tree, roles, exclusion rules, portraits, etc.)
- `test_system_prompt_json_example_no_context_map_atmospheric_broll`
- `test_prompt_prose_no_broll_for_portrait`
- `test_system_prompt_schema_no_generic_broll`

Removed 4 V1 builder tests:
- `test_retry_prompt_preserves_full_contract` (called `_build_retry_instruction` and `_build_user_prompt`)
- `test_build_user_prompt_contains_historical_requirements` (called `_build_user_prompt`)
- `test_retry_instruction_has_replacement_types` (called `_build_retry_instruction`)
- `test_retry_instruction_explicit_two_segments_rule` (called `_build_retry_instruction`)

Removed fixtures/imports without callers:
- `_GOOD_3_SCENE_SCRIPT` (unused by remaining tests)
- `PROMPT_PATH` and regex extraction (used only by SYSTEM_PROMPT tests)
- `import re` (no remaining usage)

Preserved:
- 35 tests: structural validator, retry-loop V2 integration, asset-side contracts, segment-count, allow-list
- `_build_scene_script`, `_seg_script`, `_v2_vp`, `_v2_scene`, `_V2_VALID_4_SCENE`, `_V2_ABOVE_MAX_WORDS`, `_V2_SINGLE_SCENE_CTA`

### `tests/test_duration_profiles.py`

Migrated 8 test functions to V2 equivalents via local aliases:
- `_build_duration_prompt_instruction` → `_build_duration_prompt_instruction_v2 as _build_duration_prompt_instruction` (6 tests)
- `_build_retry_instruction` → `_build_retry_instruction_v2 as _build_retry_instruction` (1 test, added `structural_issues=[]` and `allow_generated_images=False`)
- `SYSTEM_PROMPT` → `SYSTEM_PROMPT_V2 as SYSTEM_PROMPT` (2 tests)

All assertions preserved unchanged.

## Test results

| Test file | Result |
|-----------|--------|
| `test_duration_profiles.py` | 36 passed |
| `test_generate_script.py` | 35 passed |
| `test_generate_script_v2.py` | 77 passed |
| `test_v2_only_generation_contract.py` | 7 passed |
| `test_run_job.py -k build_script_command` | 2 passed |

## Negative import check

```
PASS: V1 prompt symbols removed
```

## Review read-only

- Review result: `APPROVE_WITH_NON_BLOCKING_NOTES`
- No functional blocking findings
- Fixed current-state.md: 13→17 V1 tests eliminated (13 SYSTEM_PROMPT + 4 builder tests)
- Fixed tasks.md: marked V1 → V2 reinterpretation as superseded (Slice 1 task closed, referenced in Slice 3A)
- Current contract: --visual-schema-version 1 produces SystemExit(2)
- `editorial_asset_contract` imports preserved only because `_validate_script_structure` still present
- Editorial imports are not used by canonical V2 runtime
- `_validate_script_structure` and its coverage deferred to Slice 3B2
- Confirmed tests focalized: 157 passed, 0 failed
- Slice 3B1 closed by this commit
- Next action: Slice 3B2

## Reindex

```text
6263 nodes, 15539 edges, mode=fast, persistence=false
```
