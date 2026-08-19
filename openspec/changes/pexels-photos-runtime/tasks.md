# Tasks: pexels-photos-runtime

**Status: COMPLETED / VERIFIED / CLOSED. Two functional slices maximum.**

## Preconditions

- [x] Opened from `main` at `d145a7c` with a clean worktree.
- [x] Branch `change/pexels-photos-runtime` created.

## Slice 1: Pexels Shared Infra + Photos Candidate Adapter

- [x] Add shared credential/GET JSON/error/telemetry support.
- [x] Add Pexels Photos page-1 mapping and provenance wrapper.
- [x] Add pure provisional A2-equivalent BM25 ordering.
- [x] Add mocked/offline tests with no secret or evaluation dependency.
- [x] Run focused tests (`99 passed`), full `tests` suite (`1751 passed`) and `git diff --check`.

## Slice 2: Pexels Photos Runtime Integration

- [x] Add capability/provider-fit routing and explicit `sourceProviders` opt-in.
- [x] Wire the existing lifecycle, downloader, semantic gate and pixel gate.
- [x] Persist bridge provenance and preserve provider failover/order.
- [x] Flip `pexels.photos.stock` from PLANNED to AVAILABLE atomically after all requirements pass.
- [x] Add mocked integration tests and bounded real Photos smokes: Smoke A one request/resolved; Smoke B `ASSETS_PARTIAL`, five of seven segments resolved, with request count conservatively UNKNOWN.

## Closure

- [x] Review scope, test evidence, bounded smoke evidence and docs.
- [x] Full suite and `git diff --check`.
- [ ] Merge only in a separate authorized session.

## Out Of Scope

Pexels Video, VIDEO contracts/rendering, query adaptation, pagination, benchmark
or evidence extension, diversity/dedup, generated images, UI, defaults and a
third functional slice.
