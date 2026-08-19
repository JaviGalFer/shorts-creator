# Tasks: pexels-video-runtime-mvp

**Status: ACTIVE. PRODUCT CHANGE. Two functional slices maximum.**

## Preconditions

- [x] Opened from `main` at `5b340db` with a clean worktree.
- [x] Branch `change/pexels-video-runtime-mvp` created.

## Slice 1: Pexels Video Asset Runtime

- [x] Add CLI/request and minimal script context for visual mode policy.
- [x] Wire capability-aware routing while keeping Video PLANNED in production.
- [x] Add Pexels Video adapter, RAW ordering and deterministic MP4 selection.
- [x] Add VIDEO lifecycle handling, semantic degradation, pixel bypass and safe downloader.
- [x] Transport VIDEO public metadata through bridge and assets-stage contract.
- [x] Add mocked/offline tests; run focused tests and full `tests` suite (`1768 passed`).

## Slice 2: VIDEO Render And First Real E2E

- [ ] Transport VIDEO facts through prepare/renderTimeline.
- [ ] Add VIDEO FFmpeg inputs, mute, crop, trim/loop and media-aware validation.
- [ ] Run mocked regressions and local renderer Smoke B.
- [ ] Run real Pexels provider Smoke A and canonical full E2E C.
- [ ] Flip `pexels.video.stock` to AVAILABLE only after all Slice 2 requirements pass.

## Out Of Scope

No benchmark, evidence extension, query adaptation, diversity/dedup, smart clip
selection, Pexels audio, OpenCLIP-on-video, generated media, UI, defaults,
pagination or a ritual third slice.
