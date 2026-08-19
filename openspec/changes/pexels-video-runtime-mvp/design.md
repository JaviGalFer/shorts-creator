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

### FFmpeg strategy (VIDEO)

Each VIDEO timeline input uses `-stream_loop -1 -i <clip>` (never `-loop 1`),
and a normalization chain `trim=duration=<timeline>,setpts=PTS-STARTPTS,fps=25,
scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,
format=yuv420p`. Short clips are looped from the start (`LOOP_FROM_START`); the
same construction trims longer clips. The final `-map` is explicit (`[vout]`
and `[aout]`), and the filter graph never references a VIDEO input's audio
stream, so Pexels clip audio is discarded. IMAGE keeps `-loop 1` and its exact
motion filters.

### Selected-only cross-scene reservation (Slice 2 hardening)

The shared `excluded_source_urls`/`excluded_file_urls` sets now represent only
clips already SELECTED by an earlier scene. `_resolve_pexels_videos` skips
candidates present in those global sets during discovery but reserves a clip
globally only after it is selected. Local `local_seen_*` sets avoid evaluating
the same clip twice within one resolver (across queries/pages). A semantically
rejected or download-failed candidate remains reusable by later scenes. Only
`pexels.video.stock` changed; Wikimedia/Pixabay/Pexels Photos are untouched.

### VIDEO sparse-metadata partial-match policy

The generic `deterministic_anchor_coverage_v2` scorer is unchanged. For
`pexels.video.stock` + photograph only, an IRRELEVANT candidate whose provider
metadata is sparse (empty `tags`, slug-only evidence) may degrade to
`semanticDegradation=PROVIDER_METADATA_PARTIAL_MATCH` when it matched at least
one discriminative anchor and `anchorTerms` is non-empty. The original
`IRRELEVANT` verdict is preserved (never falsified to RELEVANT), an internal
`allowSemanticDegradation` flag gates the lifecycle and is removed before
persisting. `_search_semantic_ok` admits it only for VIDEO + that degradation +
non-empty `matchedAnchors`. IMAGE is unaffected.

## Slice 2 Runtime Evidence

- Offline suite `1801 passed`; `git diff --check` clean.
- Smoke B (local, no network): two synthetic portrait MP4 clips (one with a
  source shorter than its editorial window) rendered through the real
  `prepare_job` + `render_job` path to a `RENDERED` 1080x1920 MP4. The short clip
  was looped; the final file had exactly one audio stream (pipeline narration),
  proving the clip's own audio was never mapped. Clip audio (440/880 Hz) was
  spectrally absent; narration (330/550 Hz) was present.
- Smoke A (real Pexels, one photographic segment): `ASSETS_READY` 1/1, mediaKind
  VIDEO, `pexels.video.stock`, `pexelsVideoId 31404155`, `pexelsVideoFileId
  13398601`, rank 2, `1080x1920`, 15.0s source, 25 fps, semantic RELEVANT, pixel
  gate `NOT_APPLICABLE`, rate-limit remaining `24840`. A missing User-Agent on
  the video CDN downloader (403) was found and fixed.
- Replay R1 (dolphins VisualPlan, same queries): the initial 2/4 `ASSETS_PARTIAL`
  became 4/4 `ASSETS_READY` after the selected-only reservation fix, confirming
  the reservation semantics (not provider supply) were the primary blocker.
- E2E C (`la-2026-08-19-235138`, dolphins, `--duration 20 --asset-providers pexels
  --visual-mode videos-only`): 4/4 VIDEO segments resolved (4 unique Pexels video
  IDs), `VALIDATED`, 1080x1920 H.264, 18.52s within the 18-22s contract, one
  narration audio stream, no Pexels clip audio, subtitles present. Scene 2 used
  the partial-match degradation; the other three resolved RELEVANT.

## Explicit Non-Goals

No query adaptation, reranking, diversity/dedup, smart clip start selection,
Video audio, pagination, new research or VIDEO rendering in Slice 1.
