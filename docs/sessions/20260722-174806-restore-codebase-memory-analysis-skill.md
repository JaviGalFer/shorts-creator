# Session: Restore Codebase Memory Analysis skill

**Date:** 2026-07-22
**Model:** opencode/deepseek-v4-flash-free
**Variant:** low
**Mode:** Build
**Category:** tooling validation and closure

## Why restoration was needed

The directory `.agents/skills/codebase-memory-analysis/` did not exist. No
partial version was found. The skill had to be created from scratch.

Additionally, the `codebase_memory` MCP block had been accidentally removed
from `opencode.jsonc`. It has been restored.

## MCP status (initial)

`opencode mcp list` initially showed no MCP servers configured because the
`codebase_memory` MCP block had been removed from `opencode.jsonc`.

The `codebase-memory-mcp` binary was not accessible via the simple name
`codebase-memory-mcp` in PATH, but it was available at the absolute path
`/home/javi/.local/bin/codebase-memory-mcp` and was executable.

## MCP status (after restoration)

- `opencode mcp list` → `codebase_memory connected`
- Binary exists and is executable: `/home/javi/.local/bin/codebase-memory-mcp`
- `opencode.jsonc` contains the restored MCP configuration with absolute path
- MCP timeout: 15000ms
- Environment: `CBM_ALLOWED_ROOT=/home/javi/projects/shorts-creator`, `CBM_LOG_LEVEL=warn`

## Skill discovery validation

`opencode debug skill` shows `codebase-memory-analysis` in the skill list with
correct name, description, and location. Discovery: OK.

## Reindexado

Command:
```
/home/javi/.local/bin/codebase-memory-mcp cli index_repository \
  --repo-path "/home/javi/projects/shorts-creator" \
  --mode fast \
  --persistence false
```

Result:
- Project: `home-javi-projects-shorts-creator`
- Nodes: 6242
- Edges: 15487
- Status: indexed
- Persistence: false (no artifact written)

No warnings encountered.

## MCP calls made (4 read-only)

### Call 1 — `list_projects`
Confirmed project `home-javi-projects-shorts-creator` exists with 6242 nodes
and 15487 edges.

### Call 2 — `search_graph` for `build_script_command`
Located at `bin/run_job.py:111-129`. Qualified name:
`home-javi-projects-shorts-creator.bin.run_job.build_script_command`. Also
found three related test nodes.

### Call 3 — `trace_path` inbound from `build_script_command`
Callers:
- `dry_run` (hop 1)
- `main` (hop 1)
- Module `bin/run_job.py` (hop 2)

### Call 4 — `search_code` for `--visual-schema-version`
Found in:
- `bin/run_job.py:128` (builder adds `--visual-schema-version 2`)
- `bin/generate_script.py:1108` (argument parser)
- 31 matches in tests (slice 1 test files)

Total grep matches: 75 across bin/, tests/, docs/, openspec/

## Graph-confirmed

1. `build_script_command` defined at `bin/run_job.py:111-129`
2. The function adds `--visual-schema-version` to the command list
3. Callers: `dry_run`, `main` (both in `bin/run_job.py`)
4. Tests exist in `tests/test_run_job.py` and `tests/test_v2_only_generation_contract.py`

## Direct-code-confirmed

1. `build_script_command()` is at `bin/run_job.py:111-129`
2. Line 128: `cmd.extend(["--visual-schema-version", "2"])`
3. The flag appears exactly once in the built command
4. No other occurrence of `--visual-schema-version` in `bin/run_job.py`

## Test-confirmed

Tests in `tests/test_v2_only_generation_contract.py`:
- `test_adds_v2_flag` (line 73)
- `test_v2_flag_appears_exactly_once` (line 81)
- `test_explicit_v1_not_reinterpreted` (line 54)

These directly validate the Slice 1 contract.

## Inference

- The pipeline defaults to V2 for new jobs via `run_job.py`
- Explicit V1 is still supported via `generate_script.py --visual-schema-version 1`
- The index accurately reflects the post-Slice-1 state

## Index limitations

- The index was built in `fast` mode without similarity edges
- Some docs/ (5) and openspec/ (7) matches for `--visual-schema-version` may
  reference legacy or planning content, not current code
- The index does not represent dynamic dispatch or subprocess calls

## Runtime changes

None. No product code, tests, OpenSpec, or `current-state.md` was modified.

## Committed files

- `opencode.jsonc` — restored MCP configuration
- `.agents/skills/codebase-memory-analysis/SKILL.md` — new skill
- `docs/sessions/20260722-174806-restore-codebase-memory-analysis-skill.md` — updated session log

Commit: `chore(ai): configure codebase memory MCP analysis` (hash on HEAD at
time of writing: `83848bf`)

No push was made.
