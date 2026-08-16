# Proposal: modular-v2-migration

## Problem

The V2 runtime remains concentrated in `bin/`, coupling reusable contracts and
domain logic to direct-script imports.

## Solution

Migrate the V2 runtime progressively into `src/shorts_creator/` on the single
integration branch `change/modular-v2-migration`. `bin/` remains compatible as
temporary CLI adapters until the final merge to `main`.

## Scope

The migration order is contracts, low-coupling infrastructure, script, paused
audio pacing, audio/assets/rendering/validation, pipeline orchestration, and
adapter reduction. Slice 1 makes VisualPlan V2 canonical in `contracts/visual.py`.

## Success Criteria

- Each slice preserves public behavior and has focal verification.
- `bin/` remains a compatible CLI/adaptor layer throughout migration.
- Final merge requires all planned slices, green full suite, stable imports, no
  critical transitional hacks, and no worsening of `AUDIO_DURATION_MISSING`.
