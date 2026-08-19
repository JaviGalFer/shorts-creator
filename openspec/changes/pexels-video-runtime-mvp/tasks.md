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

- [x] Transport VIDEO facts through prepare/renderTimeline.
- [x] Add VIDEO FFmpeg inputs, mute, crop, trim/loop and media-aware validation.
- [x] Run mocked regressions and local renderer Smoke B.
- [x] Run real Pexels provider Smoke A (ASSETS_READY 1/1).
- [x] Fix selected-only cross-scene reservation for `pexels.video.stock` (a
      candidate is excluded from later scenes only after it is selected; local
      dedup avoids re-evaluating the same clip within one resolver).
- [x] Add VIDEO sparse-metadata partial-match policy
      (`PROVIDER_METADATA_PARTIAL_MATCH`) for photograph IRRELEVANT candidates
      with at least one matched discriminative anchor and empty tags.
- [x] Run canonical full E2E C (`la-2026-08-19-235138`, dolphins): 4/4 VIDEO
      segments resolved, `VALIDATED`, 1080x1920, one narration audio stream, no
      Pexels clip audio, duration compliant.
- [x] Flip `pexels.video.stock` to AVAILABLE (explicit opt-in only).

## Out Of Scope

No benchmark, evidence extension, query adaptation, diversity/dedup, smart clip
selection, Pexels audio, OpenCLIP-on-video, generated media, UI, defaults,
pagination or a ritual third slice.
