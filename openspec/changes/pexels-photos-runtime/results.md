# Results: pexels-photos-runtime

## Status

**COMPLETED / VERIFIED / CLOSED**

## Product Result

Pexels Photos is an `AVAILABLE` IMAGE/STOCK provider, exclusively through
explicit `request.visuals.sourceProviders` / `--asset-providers`. It is never a
default provider. Pexels Video remains `PLANNED`.

## Implementation

- Shared Pexels client with process environment first, `.env` fallback,
  configurable endpoint path, raw Authorization, explicit User-Agent and safe
  HTTP errors.
- Photos adapter for `/v1/search`, portrait, `en-US`, page 1 and `per_page=15`.
- `src.original` acquisition URL and public photographer/photo provenance.
- Fixed A2-equivalent BM25 ordering identified as `PROVISIONAL_BM25` and
  explicitly `NOT VALIDATED`; it only orders lifecycle attempts.
- Registry-backed photograph fit and exclusion of diagram, infographic,
  illustration and painting.
- Existing `CandidateEnvelope`, `select_first_accepted()`, semantic gate,
  downloader, visual-fidelity gate, fallback and bridge.
- Explicit User-Agent fix after the first real attempt received a 403 without
  one. The retry resolved successfully.

## Validation

- Slice 1 focused: `99 passed`.
- Slice 1 full suite: `1751 passed`.
- Slice 2 focused final: `333 passed`.
- Closure full suite: `1758 passed, 0 failed`.
- `git diff --check`: clean.

## Real Evidence

### Smoke A

- One integrated `bin/fetch_images_v2.py` request with one photographic segment
  and `sourceProviders=["pexels"]`.
- `ASSETS_READY`, 1/1 resolved.
- Semantic verdict: `RELEVANT`.
- Selected `pexelsQueryRank=15`, `providerRank=1`.
- Selector: `PROVISIONAL_BM25`.
- Sanitized rate-limit remaining: `24848`.
- Pixel gate: `DISABLED`; `VISUAL_FIDELITY_THRESHOLD` was not set.
- The preceding failed attempt was `AUTH_ERROR`/403 caused by the missing
  explicit User-Agent, recorded as `MISSING_EXPLICIT_USER_AGENT`.

### Smoke B

- Bounded `run_job --duration 20 --stop-after assets --asset-providers pexels`.
- Seven segments, five resolved, final status `ASSETS_PARTIAL`.
- Local metadata shows sanitized rate-limit remaining decreasing from `24847`
  to `24841`.
- Exact API request count is `UNKNOWN` from persisted artifacts; the rate-limit
  delta is not treated as a request count.

## Limitations And Scope

- BM25 remains `NOT VALIDATED`.
- OpenCLIP was not exercised in either smoke; its existing fail-soft contract
  recorded pixel-gate bypass.
- Direct provider-fit support is limited to `photograph`.
- No Video runtime, query adaptation, extra pagination, diversity/dedup or UI.
- Pexels is not a default provider.
- `pexels-photo-selection-evidence-extension` remains DEFERRED / OPTIONAL and
  is not the next change.

## Security And Provenance

The API key is transient and absent from metadata, bridge output, logs, errors,
URLs and stdout. Authorization and raw response headers/body are not persisted.
Resolved metadata preserves provider, capability, provider/photo IDs, source and
acquisition URLs, photographer/profile, query/index, raw query rank, lifecycle
provider rank, selector identity/score and sanitized rate-limit telemetry.

## Next Product Direction

`pexels-video-runtime-mvp` is the next product direction. It may introduce the
minimum generic `IMAGE | VIDEO` transport contract in its first slice and should
reuse this shared Pexels client. No Video change is opened here.
