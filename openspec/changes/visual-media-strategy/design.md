# Design: visual-media-strategy

**Status: IN PROGRESS — Slice 1 COMPLETED / VERIFIED / COMMITTED; Slice 2A COMPLETED / VERIFIED**

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
