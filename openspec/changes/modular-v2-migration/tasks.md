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

## Slice 3 — Metadata infrastructure
- [x] Move `run_job` JSON metadata persistence to `infrastructure/metadata_store.py`.
- [x] Preserve `run_job` module aliases for legacy monkeypatch targets.
- [x] Verify round-trip, JSON formatting, and canonical store use.
- [x] Run affected runner tests (`114 passed`), CLI smoke, full suite (`1193 passed`), scope checks, and commit.
- [x] Defer `contracts/job.py`, `contracts/states.py`, and `contracts/results.py` until script/pipeline consumers make their boundaries concrete; do not create speculative contracts.
- [x] Document `clone_job.py` and `generate_script.py` JSON persistence as future candidates without migrating them in this slice.

## Slice 4 — Metadata store adoption
- [x] Adopt the shared metadata store in equivalent `clone_job.py` persistence.
- [x] Adopt the shared metadata store in equivalent `generate_script.py` output persistence.
- [x] Retain local JSON operations unrelated to metadata persistence.
- [x] Run direct consumer tests and metadata-store tests (`170 passed`), CLI smokes, full suite (`1193 passed`), scope checks, and commit.

## Remaining slices
- [ ] Extract remaining pure contracts, then low-coupling infrastructure.
- [ ] Migrate script and reassess paused audio pacing Phase B.
- [ ] Migrate audio, assets, rendering, and validation in verified increments.
- [ ] Extract pipeline orchestration and reduce `bin/` to adapters.
- [ ] Complete final review and merge criteria before merging to `main`.
