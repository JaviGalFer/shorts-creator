---
name: codebase-memory-analysis
description: Use Codebase Memory MCP for repository discovery, call tracing, dependency analysis, impact analysis, and architecture investigation. Apply a bounded MCP-first workflow, then verify findings with direct source reads and focused tests.
---

# Codebase Memory Analysis

Use this skill for read-only repository investigation involving:

- locating definitions or homonymous symbols;
- finding callers, callees, usages, imports, or tests;
- following data or contract propagation;
- understanding an unfamiliar module;
- estimating refactor impact;
- identifying files relevant to a bug;
- investigating cross-stage pipeline behavior.

Do not use it for simple edits where the target is already known, formatting changes, runtime validation, proving dead code, or inspecting generated jobs under `data/`.

## Core rule

Use Codebase Memory to discover and narrow the scope.

Use direct source reads to verify behavior.

Use tests to prove correctness.

The graph is evidence, not the source of truth.

## Workflow

1. Confirm the index only on first use, after repository changes, or when results appear incomplete.
2. Prefer `search_graph` to locate symbols.
3. Use qualified names to disambiguate homonymous symbols.
4. Prefer `trace_path` for callers, callees, tests, and data flow.
5. Use `search_code` only for concrete contracts, fields, statuses, and literals.
6. Use `get_code_snippet` only after locating the exact symbol.
7. Verify production branches and affected tests through direct source reads.
8. Run focused tests before making correctness claims.

## Limits

- Use no more than 8 to 12 MCP calls during initial discovery.
- Use no more than 2 code snippets.
- Do not request the schema or full architecture on every task.
- Do not treat grep matches as callers.
- Do not treat hop-based risk labels as engineering severity.
- Do not claim that code is safe to delete based only on graph evidence.

## Known limitations

Always verify directly when the task involves:

- broad code removal;
- complete test impact;
- conditional V1/V2 behavior;
- dynamic imports;
- subprocess or CLI dispatch;
- n8n workflows;
- data under `data/`;
- dead or unreachable code.

## Index refresh

After relevant code changes, refresh the index with:

    codebase-memory-mcp cli index_repository \
      --repo-path "/home/javi/projects/shorts-creator" \
      --mode fast \
      --persistence false

Keep automatic watching and shared persistence disabled unless explicitly requested.

## Reporting

Separate conclusions into:

- graph-confirmed facts;
- direct-source-confirmed facts;
- inferences;
- unresolved limitations.
