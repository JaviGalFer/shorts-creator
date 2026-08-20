# Proposal: pexels-video-runtime-mvp

## Status

**COMPLETED / VERIFIED / CLOSED.** Product change, four commits on the branch,
merge pending authorization.

## Objective

Deliver the first real canonical shorts-creator E2E using Pexels Video clips:
`script -> assets -> audio -> prepare -> render -> validate`.

**FIRST REAL VIDEO E2E BEFORE FURTHER VIDEO RESEARCH.**

## Scope

- Slice 1: Pexels Video asset runtime through public `metadata.assets`, with
  explicit media policy, RAW ordering, provider provenance and mocked/offline
  verification.
- Slice 2: prepare/render VIDEO support and the bounded real provider, renderer
  and canonical E2E smokes required before capability availability is flipped.
- Pexels remains explicit opt-in and never becomes a default provider.

## Out Of Scope

- New benchmarks, evidence extension, query adaptation, diversity/dedup,
  smart temporal clip selection, multiple clips per segment, Pexels audio,
  generated media, UI and pagination.
- OpenCLIP, BLIP or VLM processing of MP4 assets.
- VIDEO rendering in Slice 1.

## Success Criteria

1. `VIDEOS_ONLY` with explicit Pexels policy can produce a VIDEO resolved asset
   through the existing lifecycle in mocked/offline tests.
2. Pexels Video uses only RAW page-1 ordering and a deterministic portrait MP4
   file selection rule.
3. VIDEO provenance, `mediaKind`, source duration and FPS reach public asset
   metadata without using filename extensions as a media contract.
4. `pexels.video.stock` remains PLANNED until Slice 2 validation, smokes and
   renderer support are complete.

## Outcome

All success criteria met. Pexels Video is `AVAILABLE` through explicit
`--asset-providers pexels --visual-mode videos-only`. The first real Video E2E
`la-2026-08-19-235138` reached `VALIDATED`. See `results.md`.
