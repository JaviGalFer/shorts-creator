---
name: model-routing-and-token-economy
description: Select OpenCode models, execution limits, and fallbacks using the project's audited token-economy policy.
---

# Skill: model-routing-and-token-economy

## 1. Purpose

This skill enables:

- classifying a task into a defined category;
- manually selecting a model and variant for that category;
- limiting steps, tools, and context per session;
- preventing implicit model inheritance across sessions;
- preparing for future agents or commands with explicit routing.

A skill does not change the model of an already started session. Automatic
selection must be implemented later through agents, commands, or explicit
configuration. Always record the model and variant used in the session log.

## 2. Evidence

The routing policy is derived from:

- `docs/research/opencode-free-models-benchmark-r1.md` — audited technical report
- `tools/benchmarks/opencode-free-models-r1/results-summary.json` — structured metrics
- `tools/benchmarks/opencode-free-models-r1/manifest.json` — benchmark scope and timestamp

The benchmark was:

- a read-only audit of two files (`bin/run_job.py`, `bin/generate_script.py`);
- limited to 4 agentic steps;
- restricted to the `benchmark-readonly` agent (no edit, bash, task, or web tools);
- not a test of code-change capability;
- not to be repeated routinely.

## 3. Task classification

| Category | Includes | Excludes |
|----------|----------|----------|
| **exploration** | Targeted grep/read of specific files or symbols; finding relevant code locations | Full-repository sweeps; editing; planning |
| **planning** | Analysing structure, contracts, dependencies; producing a compact implementation plan | Writing code; executing tests |
| **implementation** | Editing code; creating new files; running focused tests | Full test suites; architecture decisions without OpenSpec |
| **review** | Reading diffs; verifying acceptance criteria; checking test coverage | Implementation; test execution |
| **test-triage** | Reading test output; classifying failures; identifying affected tests | Automatic fixes; code edits |
| **fallback** | Alternative model when primary fails for exploration, planning, or review | Automatic retry loops; secondary attempts for implementation |

## 4. Current routing policy

### Exploration

- Primary: `opencode/big-pickle`
- Variant: default
- Maximum steps: 3
- Read-only: yes
- Scope: explicit files or symbols only
- Notes: strongest verified technical correctness in R1, but formatting compliance must not be assumed

### Planning

- Primary: `opencode/big-pickle`
- Variant: default
- Maximum steps: 4
- Read-only: yes
- Output: compact implementation plan persisted in OpenSpec
- Notes: planning suitability is inferred from the read-only audit, not independently validated

### Review

- Primary: `opencode/big-pickle`
- Variant: default
- Maximum steps: 3
- Read-only: yes
- Scope: diff, focused tests, and acceptance criteria only

### Implementation

- Status: `provisional-unvalidated-on-code-changes`
- Initial candidate: `opencode/deepseek-v4-flash-free`
- Variant: low
- Maximum steps: 6
- Subagents: denied
- Scope: at most five functional files per slice
- Correction cycles: maximum one
- Required: focused tests before any complete suite

DeepSeek is not a validated Builder. This assignment is provisional.

### Test triage

- Initial candidate: `opencode/big-pickle` (read-only)
- Maximum steps: 3
- Scope: only summarized failures and affected tests
- No automatic code edits
- This assignment is provisional.

### Fallback

- Model: `opencode/deepseek-v4-flash-free`, variant low
- Fallback means an alternative for a failed exploration, planning, or review task. It does not imply automatic retry loops.

## 5. Models not selected

- `mimo-v2.5-free`: do not select by default because of scope and context-discipline concerns (full reads, grep outside allowed files, 124s, high tokens).
- `north-mini-code-free`: do not select because of poor token economy in this benchmark (82,887 input tokens for 2 files, zero cache utilisation).
- `hy3-free`: do not select until a successful completion is observed (incomplete coverage in R1: read only 1 of 2 files).
- `nemotron-3-ultra-free`: not selected by the audited report. Preserve as unassigned rather than declaring it universally unsuitable.

## 6. Execution limits

| Category | Max steps |
|----------|-----------|
| exploration | 3 |
| planning | 4 |
| implementation | 6 |
| review | 3 |
| test triage | 3 |

- One phase per session.
- No implicit model inheritance.
- No subagents during implementation.
- No full-repository audits.
- No complete test suite during initial implementation.
- No repeated rereading of the same files.
- No raw full-suite logs in model context.
- No more than one automatic correction cycle.
- Stop when scope expansion is required.

## 7. Context budget rules

- Reference OpenSpec instead of repeating full requirements in prompts.
- Provide explicit file allowlists.
- Use targeted grep/read operations.
- Persist plans and decisions in project documentation.
- Start a new session when moving from Plan to Build or Review.
- Summarize test output before presenting it to the model.
- Keep historical evidence outside hot context.
- Do not load unrelated skills.

## 8. Subagent policy

Subagents are currently not the default. They are allowed only when:

- the task is read-only;
- domains or file scopes are disjoint;
- every subagent has an explicit model;
- every subagent has its own step limit;
- results are compact and structured;
- the parent does not repeat the same investigation.

Disallowed:

- two agents editing the same working tree;
- subagents inheriting an unspecified model;
- recursive delegation;
- parallel full-repository exploration.

## 9. Revalidation triggers

Reassess the routing only when:

- a selected model disappears or becomes unreliable;
- provider quotas or limits materially change;
- a selected model fails three real tasks of its assigned category;
- a new relevant free model becomes available;
- modularization materially reduces context requirements;
- real implementation evidence contradicts the current provisional routing.

Do not rerun synthetic benchmarks routinely.

## 10. Session declaration template

```
Session:
Model:
Variant:
Mode:
Task category:
Maximum steps:
Allowed files:
Subagents:
Skills:
Tests:
Stop conditions:
```

The template requires explicit values, not implicit defaults.

## Interpretation rules

- Do not classify malformed JSON output as silent failure when a final response exists.
- Distinguish: completion failure; formatting failure; correctness failure; scope violation; inefficiency.
- Reading a complete allowed file may be inefficient, but it is not by itself a scope violation.
- Searching or reading outside the file allowlist is a scope violation.
- Do not copy benchmark scores or introduce a numeric ranking.
- Do not promise cost savings.
- Do not configure automatic fallback chains.
- Do not add agents or commands in this step.
