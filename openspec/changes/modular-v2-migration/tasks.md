# Tasks: modular-v2-migration

## Slice 1 — VisualPlan V2 contract
- [x] Move canonical VisualPlan V2 implementation to `contracts/visual.py`.
- [x] Add centralized `bin/` package bootstrap and a legacy reexport facade.
- [x] Verify canonical and legacy imports expose identical public objects.
- [x] Run VisualPlan V2 consumer tests and CLI smoke (`445 passed`).
- [x] Run full suite and scope checks (`1188 passed`); commit the validated slice.

## Slice 2 — Duration contract
- [x] Move pure duration profiles and resolution logic to `contracts/duration.py`.
- [x] Keep `add_duration_profile_args` as the sole CLI adaptation in `bin/`.
- [x] Verify canonical and legacy imports share the same duration objects.
- [x] Run duration tests (`38 passed`), CLI smokes, full suite (`1190 passed`), and scope checks; commit.

## Remaining slices
- [ ] Extract remaining pure contracts, then low-coupling infrastructure.
- [ ] Migrate script and reassess paused audio pacing Phase B.
- [ ] Migrate audio, assets, rendering, and validation in verified increments.
- [ ] Extract pipeline orchestration and reduce `bin/` to adapters.
- [ ] Complete final review and merge criteria before merging to `main`.
