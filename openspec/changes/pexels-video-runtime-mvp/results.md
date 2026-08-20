# Results: pexels-video-runtime-mvp

## Status

**COMPLETED / VERIFIED / CLOSED** — pending authorized merge.

## Product Result

Pexels Video (`pexels.video.stock`) is an `AVAILABLE` VIDEO/STOCK provider,
reachable only through explicit `--asset-providers pexels --visual-mode
videos-only` (request `request.visuals.visualMode=VIDEOS_ONLY`,
`sourceProviders=["pexels"]`). It is never a default provider. Pexels Photos
remains `AVAILABLE` without regression.

The first real canonical shorts-creator E2E using Pexels Video clips reached
`VALIDATED`, satisfying **FIRST REAL VIDEO E2E BEFORE FURTHER VIDEO RESEARCH**.

## Implementation (Slice 1 + Slice 2)

- CLI/request `--visual-mode` (auto/images-only/videos-only/mixed) with explicit
  mapping and capability-aware routing; `pexels.video.stock` vs
  `pexels.photos.stock` decided by capability, never by provider name alone.
- `pexels_videos.py` adapter: `/v1/videos/search`, portrait, `en-US`, page 1,
  `per_page=15`, RAW order, deterministic portrait MP4 variant selection
  (smallest >=1080x1920, fallback >=720x1280).
- Shared `CandidateEnvelope` lifecycle with RAW ordering, `pexelsQueryRank` and
  final-stream `providerRank`, provenance bridge, VIDEO pixel `NOT_APPLICABLE`.
- Selected-only cross-scene reservation: a clip is excluded from later scenes
  only after it is selected; local seen-sets dedup within one resolver.
- Bounded VIDEO semantic degradations: `PROVIDER_METADATA_INSUFFICIENT` for
  anchored UNSCORABLE, and narrow `PROVIDER_METADATA_PARTIAL_MATCH` for sparse
  photograph IRRELEVANT with >=1 matched anchor. Original verdicts preserved.
- prepare/renderTimeline transport (`mediaKind`, `mimeType`, `sourceDurationSec`,
  `fps`); editorial `durationSec` independent.
- Renderer VIDEO inputs `-stream_loop -1` (loop-from-start), mute, trim to
  timeline, scale/crop 1080x1920, setsar=1, yuv420p, explicit `-map` so clip
  audio is never mapped; IMAGE keeps `-loop 1` and its exact filters.
- Media-aware asset validation (ffprobe/JSON + Docker fallback for VIDEO;
  Pillow for IMAGE).
- Effective visual-mode metadata fix in `resolvedConfig.visuals`.

## Validation

- Offline full suite: `1809 passed, 0 failed`; `git diff --check` clean.

## Real Evidence

### Smoke A (provider)

One real Pexels Video photographic segment: `ASSETS_READY` 1/1; mediaKind
VIDEO; `pexels.video.stock`; `pexelsVideoId 31404155`; `pexelsVideoFileId
13398601`; rank 2; 1080x1920; 15.0s source; 25 fps; semantic RELEVANT; pixel
`NOT_APPLICABLE`; rate-limit remaining `24840`.

### Smoke B (renderer local)

Two synthetic portrait MP4 clips (one shorter than its editorial window)
through real `prepare_job` + `render_job`: `RENDERED` 1080x1920 MP4. The short
clip looped; exactly one audio stream (narration) — clip audio (440/880 Hz)
absent, narration (330/550 Hz) present.

### E2E C — first real Video E2E

Job `la-2026-08-19-235138`, topic "La vida de los delfines en el océano",
`--duration 20 --asset-providers pexels --visual-mode videos-only`.

- 4/4 VIDEO segments resolved; 4 unique Pexels video IDs.
- 1080x1920 H.264; one narration-only audio stream; no Pexels clip audio;
  subtitles present.
- Target 20s, allowed range 18–22s, projected 18.462s, actual 18.52s,
  duration **PASS / EXPECTED**.
- Result: **VALIDATED**.

## Accepted Limitations

- RAW page-1 ordering only; no query adaptation.
- No OpenCLIP/VLM on MP4 (VIDEO pixel gate is `NOT_APPLICABLE`).
- No smart clip start / temporal relevance selection.
- Bounded sparse-metadata semantic degradation; no global gate weakening.
- `LOOP_FROM_START` for clips shorter than their editorial window.
- No generated or manual Video; no Video UI.
- No additional diversity optimisation beyond the selected-only reservation.
- Duration fit is NOT a limitation (18.52s is within contract and PASS).
