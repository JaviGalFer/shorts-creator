# Design: pexels-photos-runtime

## Boundaries

Pexels Photos is IMAGE-only and opt-in. It remains outside defaults. Slice 1
contains no router, executor, bridge, fetcher-routing or capability-status
change. Slice 2 is the only remaining functional slice.

## Shared Client

`assets/providers/pexels.py` resolves `PEXELS_API_KEY` using the existing
process-environment-first, project-`.env` fallback helper. It sends GET JSON
requests with `Authorization: <key>`, an explicit timeout and explicit path and
parameters. It accepts any API path, so future Video can use
`/v1/videos/search`; this change implements only `/v1/search`.

The client exposes small normalized error codes: `CREDENTIAL_MISSING`,
`AUTH_ERROR`, `RATE_LIMITED`, `NETWORK_ERROR` and `MALFORMED_RESPONSE`. It
never includes an API key or response body in exceptions or telemetry.
Telemetry contains only selected, sanitized rate-limit headers.

## Photos Adapter And Ordering

`assets/providers/pexels_photos.py` requests one page with `query=queryUsed`,
`orientation=portrait`, `locale=en-US`, `page=1`, and `per_page=15`. It maps
valid photos to a Pexels-specific wrapper around the existing
`CandidateEnvelope`; no Pexels fields are added to the generic envelope.

`src.original` is the acquisition URL, `url` the source/photo URL and
`src.large2x` the preview URL. `CandidateAttribution.author_url` is the sole
generic contract extension, used for photographer profile URLs.

`pexelsQueryRank` is the raw 1-based API position. `providerRank` is assigned
only after the BM25 final stream ordering. The wrapper retains photo id, raw
rank, selector identity and selector score for Slice 2 serialization.

The pure ordering is A2-equivalent: NFKC, casefold, `[a-z0-9]+`, current
`STOPWORDS` and `GENERIC_FILLER`, unique tokens, BM25 `k1=1.2`, `b=0.75`, all
returned (up to 15) alts as corpus, score descending and raw rank ascending on
ties. Its identity is `PROVISIONAL_BM25`, NOT VALIDATED. It only orders attempts.

## Lifecycle And Availability

Slice 2 will pass the ordered stream to the existing lifecycle:

`Pexels search -> BM25 order -> semantic gate -> existing download path -> pixel gate -> first accepted -> provider fallback`.

Pexels availability does not depend on optional OpenCLIP being installed. The
pixel gate is fail-soft according to its existing runtime contract; a real smoke
with it active is additional evidence, not an intrinsic provider requirement.

## Slices

1. Shared client, credential helper reuse, Photos adapter, provenance wrapper,
   BM25 and offline tests. No runtime wiring.
2. Provider-fit routing, explicit opt-in, executor lifecycle/download reuse,
   bridge provenance, capability flip, mocked integration tests and small real smoke.
