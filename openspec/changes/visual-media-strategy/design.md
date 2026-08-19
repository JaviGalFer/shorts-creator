# Design: visual-media-strategy

**Status: COMPLETED / VERIFIED / CLOSED**

## Contratos

`assetPreference` sigue expresando forma visual. El campo nuevo, por segmento,
es ortogonal:

```text
mediaPreference = IMAGE_PREFERRED | VIDEO_PREFERRED | EITHER
```

Es opcional para compatibilidad. Al canonicalizar, su ausencia significa
`IMAGE_PREFERRED`. No se incrementa `_schemaVersion`: VisualPlan v2 ya admite
campos opcionales con defaults y los lectores históricos no se reescriben.

La policy de job se normaliza de forma pura:

| visualMode | allowedKinds | Semántica |
|---|---|---|
| AUTO | IMAGE, VIDEO | Ambos permitidos; sin objetivo de mezcla. |
| IMAGES_ONLY | IMAGE | Restricción dura. |
| VIDEOS_ONLY | VIDEO | Restricción dura. |
| MIXED | IMAGE, VIDEO | Diversidad best-effort; nunca reduce calidad para usar ambos. |

Compatibilidad: `visualMode` explícito gana; sin él, `mode: images` implica
`IMAGES_ONLY`; ambos ausentes también implican `IMAGES_ONLY`. `mode: images` y
un `visualMode` no equivalente son un error explícito.

## MediaStrategy

`MediaStrategyDecision` es inmutable y solo recibe policy normalizada,
preferencia editorial y los medios que una forma/capability permite. No consulta
providers ni runtime. La futura capa routing suministrará esa intersección.

Degradaciones iniciales:

- `MEDIA_PREFERENCE_OVERRIDDEN_BY_USER`
- `MEDIA_PREFERENCE_UNAVAILABLE`
- `MEDIA_PREFERENCE_UNSATISFIABLE_FOR_VISUAL_FORM`
- `VISUAL_FORM_UNSUPPORTED_FOR_ALLOWED_MEDIA`

Si no existe medio compatible con la restricción de usuario, la decisión queda
unresolved. Nunca convierte una forma exacta, como `diagram`, en B-roll de
forma silenciosa.

## Provider capabilities

`ProviderCapability` distingue una capability técnica por id, aunque comparta
provider comercial. Sus campos Python son `capability_id`, `provider`,
`media_kind`, `source_type`, `query_strategy`, `runtime_status`,
`requires_api_key`, `visual_form_fit` y `evidence_version`.

El registry es estático, puro y sin secretos. Disponibilidad de key, rate limits
e implementación efectiva permanecen dinámicos y fuera del registry.

| capability id | Medio | Estado | Fit photograph |
|---|---|---|---|
| wikimedia_commons.image.stock | IMAGE | AVAILABLE | no afirmado por este registry |
| pixabay.image.stock | IMAGE | AVAILABLE | no afirmado por este registry |
| pexels.photos.stock | IMAGE | PLANNED | DIRECT |
| pexels.video.stock | VIDEO | PLANNED | CONDITIONAL |

Pexels Video queda `CONDITIONAL` para `photograph` porque el benchmark lo
clasificó `ELIGIBLE_CANDIDATE`, no satisfacción garantizada. Para Pexels Photos
y Video, diagram/infographic/illustration/painting son `UNSUPPORTED` como
formas exactas, conforme a `pexels-provider-fit-benchmark`.

## Límites del slice

El registry no cambia `assets/router.py`: no existe routing productivo por
capability todavía. Tampoco se añaden `providerHint`, `provider` ni
`preferredProvider` al VisualPlan. `sourceProviders` seguirá siendo la policy
explícita que un slice posterior intersectará con capabilities.

## Slice 2A: candidate contracts and hardening

`resolve_media_strategy` now receives independent `form_supported_kinds` and
`runtime_available_kinds`. This makes `MEDIA_PREFERENCE_UNAVAILABLE` reachable
without conflating a form mismatch with runtime availability. Both sets are
persisted in the pure decision; routing still does not consume it.

`contracts.visual_media` is the authoritative source for media kind and media
preference enums. `visual.py` and `capabilities.py` import those constants.

Capability fit adds `UNDECLARED`: absent evidence is neither a positive fit nor
an exclusion. Only `UNSUPPORTED` is a hard exclusion. Existing Wikimedia and
Pixabay empty fit maps therefore preserve legacy eligibility. Capability fit
mappings are immutable.

`assets.candidates` defines pure, immutable pre-selection contracts:

- `CandidateEnvelope` contains discovered provider metadata, provenance URLs,
  optional rank/score, dimensions and attribution. It is not a `VisualAsset`.
- `CandidateAttempt` records a later gate/download outcome separately.
- `CandidateSelectionResult` enforces `SELECTED`/`EXHAUSTED` invariants.
- `take_top_n` preserves discovery order and never ranks by provider score.

No runtime wires these contracts in Slice 2A. A future Pexels Photos runtime
may choose `N=3` from its own policy, but no global limit belongs in this
contract.

## Slice 2B: first-accepted lifecycle parity

`select_first_accepted` is callback-driven and owns no provider or filesystem
I/O. It consumes envelopes lazily in discovery order, applies metadata before
download, applies pixel fidelity after download, cleans only pixel-rejected
files, stops at the first accepted candidate and returns ordered attempts. The
downloader cleans partial files on failure; a pixel-rejected attempt path may no
longer exist after lifecycle cleanup.
`take_top_n` now accepts an iterable and consumes no item after its limit.

The executor adapts provider-native candidates after the router has already
chosen a provider. No capability routing, provider fit routing or Pexels runtime
is introduced. Immutable attempts are never serialized or persisted; legacy
`resolvedAssets` and bridge shapes remain unchanged.

Parity intentionally retained:

- Wikimedia keeps its lazy resolver calls, ordered query progression, cache and
  exclusion mutation before semantic evaluation, and the historical limit of
  20 candidate attempts. Its batch response does not guarantee rank, so
  `provider_rank=None`.
- Pixabay keeps its provider-returned candidate order, first-query-with-valid-
  candidates behavior and historical limit of 20 attempts. Its envelope
  `provider_rank` is the 1-based final discovery-stream position delivered to
  the lifecycle, not a remote API/subquery rank. No likes/downloads scoring is
  used. Wikimedia batch ordering is not guaranteed, so `provider_rank=None`.
- Provider/source policy order, provider failover, semantic postcondition,
  filename generation, status/reason semantics and visual-fidelity bypasses are
  unchanged.

Evidence is a parity-preserving refactor backed by existing regression tests
plus focused provider wiring and lifecycle invariants; it is not formal
before-vs-after equivalence proof. This is first accepted, not human-best
candidate selection. It does not resolve
the Pexels Photo PlayStation/N64 rank-3 evidence: no reranking, multi-download,
cross-provider pool or diversity policy is present.
