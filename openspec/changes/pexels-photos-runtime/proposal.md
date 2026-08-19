# Proposal: pexels-photos-runtime

## Status

COMPLETED / VERIFIED / CLOSED. This was a product change, not a benchmark or
research loop.

## Objective

Add Pexels Photos as an explicit opt-in IMAGE/STOCK provider to the V2 asset
pipeline. Pexels is never a default provider. The change has exactly two
functional slices: Photos infrastructure/adapter, then runtime wiring and a
small real smoke.

## Scope

- Pexels shared auth, HTTP error normalization and sanitized rate-limit telemetry.
- Pexels Photos page-1 portrait search and candidate mapping.
- A2-equivalent BM25 ordering as `PROVISIONAL_BM25`, explicitly NOT VALIDATED.
- Existing semantic and pixel gates remain the acceptance authority.
- Shared infrastructure is reusable by a future Pexels Video change without
  implementing Video here.

## Out Of Scope

- Pexels Video, VIDEO assets, rendering, query adaptation, pagination, default
  provider changes, diversity/dedup, UI, generated images and new research.

## Success Criteria

1. Photos candidates preserve Pexels provenance and raw query rank.
2. Pexels is selectable only through explicit `sourceProviders` in Slice 2.
3. Runtime ordering never accepts an asset; existing gates do.
4. Secrets never persist or appear in URLs, errors, logs or metadata.
5. `pexels.photos.stock` changes from PLANNED only atomically in Slice 2 after
   adapter, wiring, tests and real smoke complete.
