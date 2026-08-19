# Results: pexels-photo-selection-benchmark

## Status

COMPLETED / VERIFIED / CLOSED

## Frozen Methodology

Evaluation-only benchmark of candidate-level metadata selectors for Pexels
Photos top-3 ordering. Scope is frozen: no Pexels runtime, no providers, no
routing, no executor, no rendering, no semantic scoring, no OpenCLIP/BLIP/VLM.
Strategies A0 raw, A1 exact lexical recall, A2 fixed-parameter BM25 (k1=1.2,
b=0.75) are frozen and unmodified. No network, no new requests/downloads.
Material `data/evaluations/pexels-visual-supply-benchmark/photo-supply-benchmark.json`
and the ten persisted top-3 review sets from
`pexels-provider-fit-benchmark/review-sample.json`.

## Hashes

- sourceArtifactSha256: `c1ef6c898d589924f65c8a1eab6601ea47c8c66b6d5c78f6b01cac6d8268ef4c`
- reviewManifestSha256: `60610f583a652131789a86755c55585ae195d4375d44b6122252638e2d382d83`
- humanPreferencesSha256: `9ade45a5da70b1538a516c4100ce5bbbae4bf56d4dd625def9242b8fbaa5144f`

## Human Review Sealed

Human preferences are `LABELED` and sealed. The manifest maps the ten top-3
sets to deterministic A/B/C aliases. `preferences_status()` reached
`HUMAN_REVIEW_READY`.

## ReviewWindowRank Hardening

Human top-3 metrics now use an explicit local `reviewWindowRank` (1..3) instead
of the global top-15 `selectorRank`. `selectorRank` remains a global diagnostic.
The evidence field is `bestPreferredReviewWindowRank` (no
`bestPreferredSelectorRank` alias). This changed the field name only; no
material metric, sufficiency, or verdict changed.

## Final Metrics

RAW A0:

- top1PreferredRate = 0.8571428571
- macroPairwiseAccuracy = 0.5
- meanPreferredRank = 1.2857142857
- beneficialReorders = 0
- harmfulReorders = 0
- playstationRank3BeforeRank1 = false

A1:

- top1PreferredRate = 1.0
- macroPairwiseAccuracy = 1.0
- meanPreferredRank = 1.0
- beneficialReorders = 1
- harmfulReorders = 0
- playstationRank3BeforeRank1 = false

A2:

- top1PreferredRate = 1.0
- macroPairwiseAccuracy = 1.0
- meanPreferredRank = 1.0
- beneficialReorders = 1
- harmfulReorders = 0
- playstationRank3BeforeRank1 = true

## Insufficiency

- labeledQueries = 10
- topicCount = 6
- discriminatingQueries = 2 (minimum 8)
- sufficient = false

The 1.0 top-1 / 1.0 pairwise figures only describe the two discriminating
queries and are not reinterpreted as general accuracy.

## A1 Status

NOT VALIDATED. Also not declared NOT_USEFUL. Does not move PlayStation raw #3
ahead of raw #1.

## A2 Status

NOT VALIDATED. Also not declared NOT_USEFUL. Shows a promising PlayStation
signal (raw #3 before raw #1) but lacks sufficient discriminating evidence.

## Verdict / Selected Strategy

- Verdict: `METADATA_SELECTION_EVIDENCE_INSUFFICIENT`
- selectedStrategy: null
- phaseBRequired: false

## Phase B

NOT RUN / NOT ELIGIBLE. A pixel ranker cannot repair insufficient candidate-level
human discrimination. OpenCLIP Phase B must not run with this dataset.

## Runtime Untouched

No runtime change. Pexels Photos remains `PLANNED`. `pexels-photos-runtime`
remains blocked only with respect to a validated metadata top-N policy.

## Future Evidence Extension

Recorded as DEFERRED / OPTIONAL (not the next change) — only reconsidered if
real runtime evidence shows candidate ordering needs more investigation. It is a
separate pre-registered investigation `pexels-photo-selection-evidence-extension`
(not implemented here): obtain additional candidate-level evidence, preferably
reusing local top-3 Pexels and avoiding new requests; do not lower the 8-query
minimum, do not re-label the current 10 queries, do not introduce Phase B
without sufficient evidence.