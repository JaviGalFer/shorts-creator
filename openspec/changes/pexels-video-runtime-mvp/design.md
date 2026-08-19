# Design: pexels-video-runtime-mvp

**Status: ACTIVE. PRODUCT CHANGE. Two functional slices maximum.**

## Boundaries

The existing `IMAGE`, `VIDEO`, `MEDIA_KINDS`, visual modes, media preferences
and `CandidateEnvelope.media_kind` are authoritative. The new public transport
field is `mediaKind`. Historical persisted assets without it mean IMAGE.

Pexels Video is explicit opt-in, RAW-query only, page 1 only, and never a
default provider. No benchmark precedes this product MVP; prior supply and
provider-fit evidence is reused without new requests.

## Slice 1: Asset Runtime

`pexels_videos.py` reuses the shared Pexels GET client with
`/v1/videos/search`, `orientation=portrait`, `locale=en-US`, `page=1` and
`per_page=15`. Its adapter maps raw API videos to generic envelopes plus a
Pexels-specific provenance wrapper.

Only valid portrait MP4 variants are eligible. The selected variant is the
smallest pixel area meeting 1080x1920; otherwise the smallest meeting 720x1280;
raw variant order then file id resolve ties. Lower-resolution, HLS and non-MP4
variants are rejected. Candidate video ordering remains raw API order.

Router decisions are capability-aware, not provider-name-only. The pure media
strategy remains the policy authority. `pexels.video.stock` stays PLANNED, so
normal production routing does not make it available in Slice 1; mocked wiring
tests inject runtime availability.

Video metadata uses Pexels tags and a descriptive URL slug only. `queryUsed`
never supplies candidate evidence. RELEVANT video candidates proceed; IRRELEVANT
candidates reject. UNSCORABLE proceeds only when structured `anchorTerms` is
non-empty, and records `semanticDegradation=PROVIDER_METADATA_INSUFFICIENT`.
IMAGE remains strict. The pixel gate is explicitly NOT_APPLICABLE for VIDEO;
there is no MP4 frame extraction or OpenCLIP call.

The video downloader validates MP4 MIME/body, writes safely inside the job and
cleans partial files. `resolvedAssets` and bridge transport `mediaKind`,
`sourceDurationSec`, optional `fps`, and Pexels video/file provenance.

## Slice 2: Render And E2E

Prepare will retain `mediaKind` and source clip facts in `renderTimeline` while
keeping editorial `durationSec` independent. Renderer will preserve IMAGE
behavior and normalize VIDEO inputs, mute their audio, crop to 1080x1920 and
loop short clips. It will then run bounded real Smoke A, renderer Smoke B and a
canonical real E2E. Only then may Pexels Video become AVAILABLE.

## Explicit Non-Goals

No query adaptation, reranking, diversity/dedup, smart clip start selection,
Video audio, pagination, new research or VIDEO rendering in Slice 1.
