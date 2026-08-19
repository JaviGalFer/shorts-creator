# Design: pexels-photo-selection-benchmark

## Status

Phase A strategy/code: **FROZEN**. Human review: **PENDING**. Benchmark verdict:
**NOT YET EXECUTED**.

## Evidence And Unit

The immutable source is
`data/evaluations/pexels-visual-supply-benchmark/photo-supply-benchmark.json`:
56 RAW page-1 queries, 15 Photos per query. The review subset is the ten queries
persisted in `pexels-provider-fit-benchmark/review-sample.json`.

Candidate-level historical evidence is only one pairwise relation: for
`PlayStation Nintendo 64 comparison photograph`, raw #3 is better than raw #1.
`CURRENT_BETTER`, `PEXELS_BETTER`, and `TIE` labels are aggregate comparison
evidence and are never converted into candidate preferences.

The benchmark scores top-15 as diagnostics but evaluates human ranking only in
the persisted top-3 review window. Queries without explicit candidate-level
preferences are excluded from ranking accuracy.

## Frozen Strategies

### A0 RAW

Order by `pexelsQueryRank` ascending.

### A1 Exact Lexical Query Recall

Normalization is exactly: Unicode NFKC, `casefold()`, regex `[a-z0-9]+`, remove
existing `STOPWORDS` and `GENERIC_FILLER`, retain unique tokens. There is no
stemming, alias/entity expansion, letter-digit splitting, or query-specific rule.

`score = |queryTokens ∩ altTokens| / |queryTokens|`; empty query tokens score
`0.0`. Order by score descending, then raw rank ascending.

### A2 BM25

Uses the identical normalization and the 15 `alt` values in the same query/page
as corpus. Fixed constants: `k1=1.2`, `b=0.75`.

`IDF(t) = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))`.

Order by BM25 descending, then raw rank ascending. No tuning, hybrid, or A3 is
permitted.

## Gate Separation

The semantic gate remains conceptually downstream and unchanged. The benchmark
does not import `semantic.py`, reuse its score, alter its thresholds, or use its
verdict to rank candidates. `preferredCandidateGateSurvival` is a future
diagnostic only, computed after preferences exist.

## Blinded Review

For each query, a SHA-256-derived permutation independently maps raw top-3
candidates to aliases A/B/C. It is frozen in a tracked manifest before labels.
The reviewer receives one contact sheet per query with only the query and aliases.
The manifest contains ranks/IDs only for audit and must not be shown to the reviewer.

## Frozen Metrics

- `top1PreferredRate`
- `macroPairwiseAccuracy`
- `meanPreferredRank`
- `beneficialReorders`
- `harmfulReorders`
- `unchanged`
- `selectorTie`
- `allUnusable`
- `unknown`
- `playstationRank3BeforeRank1`
- `preferredCandidateGateSurvival`

`unknown` and `allUnusable` are not accuracy observations. A beneficial reorder
moves an explicitly preferred candidate to top-1 where RAW did not; harmful does
the reverse. Pairwise accuracy uses only explicitly comparable preferred versus
non-preferred candidates.

## Frozen Decisions

`METADATA_SELECTOR_VALIDATED` requires all: 10/10 labeled queries, at least 8
discriminating queries, at least 5 topics, PlayStation raw #3 strictly before raw
#1, top-1 preferred rate at least +0.20 over RAW, macro pairwise accuracy at least
+0.10 over RAW, at least two beneficial reorders, at most one harmful reorder,
and no contradiction of known pairwise evidence. If A1 and A2 both pass, A1 wins
by simplicity.

`METADATA_SELECTOR_NOT_USEFUL` requires sufficient labels and no alternative
improvement over RAW in both top-1 and pairwise accuracy, or harmful reorders
exceed beneficial reorders, or both alternatives fail PlayStation.

`METADATA_SELECTION_EVIDENCE_INSUFFICIENT` applies when labels are absent,
fewer than eight discriminating queries exist, or results are inconclusive. Until
then the only permitted status is `AWAITING_HUMAN_REVIEW`.

## Future Conditional Phase B

Only if Phase A is not validated: benchmark raw relative OpenCLIP ViT-B-32 /
`laion2b_s34b_b79k` cosine scores over the same labeled top-3 window. It must not
change threshold `0.2296`, runtime activation, or production code. Local pixels
exist for all 30 review candidates; top-15 pixels do not.

## Rank Terms

Future `pexelsQueryRank` means raw 1-based response position per query/page.
Future `CandidateEnvelope.provider_rank` means final 1-based lifecycle stream
position. This benchmark only uses evaluation-local equivalents.
