# Design: pexels-photo-selection-benchmark

## Status

Phase A strategy/code: **FROZEN**. Human review: **COMPLETED / SEALED**.
Benchmark verdict: **`METADATA_SELECTION_EVIDENCE_INSUFFICIENT`**.

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

## Phase A Result

The sealed review fixture (`humanPreferencesSha256`
`9ade45a5da70b1538a516c4100ce5bbbae4bf56d4dd625def9242b8fbaa5144f`)
was evaluated offline against A0/A1/A2. The ignored result artifact is
`data/evaluations/pexels-photo-selection-benchmark/phase-a.json`.

Evidence sufficiency is not met: 10/10 queries are labeled and six topics are
represented, but only two queries are discriminating (minimum is eight). The
frozen outcome is therefore `METADATA_SELECTION_EVIDENCE_INSUFFICIENT`; no
strategy is selected and no metadata selector is validated or rejected.

Metrics are reported in the artifact without changing any strategy: RAW
top-1 preferred rate `0.8571428571` / macro pairwise `0.5` / mean preferred
rank `1.2857142857`; A1 `1.0` / `1.0` / `1.0`; A2 `1.0` / `1.0` / `1.0`.
A1 does not move PlayStation raw #3 ahead of #1; A2 does.
The result cannot use these observations to bypass the frozen sufficiency gate.
`preferredCandidateGateSurvival` is `NOT_COMPUTED`: Phase A deliberately does
not import or alter the semantic runtime contract.

Evidence hardening corrected a metric-window bug: `selectorRank` remains the
global top-15 diagnostic rank, while every human top-3 metric now uses an
explicit local `reviewWindowRank` from 1..3. This affects preferred rank and
pairwise comparisons only; top-1, reorder counts, selector ties, sufficiency,
and verdict criteria are unchanged.

Phase B is not run and is not currently eligible: a pixel ranker cannot repair
insufficient candidate-level human discrimination.

## Preference Schema: FROZEN

The human preference contract is strictly binary and frozen before any reviewer
action. Two states are permitted:

### UNLABELED

- `status` = `"UNLABELED"` in `human_preferences.json`.
- Exactly 10 entries matching the canonical query list.
- Each entry has `preferredAliases = []`, `allUnusable = null`, and `notes = ""`.
- `preferences_status()` returns `"AWAITING_HUMAN_REVIEW"`.
- No human labels are present; scoring functions accept no labels.

### LABELED

- `status` = `"LABELED"` in `human_preferences.json`.
- Exactly 10 entries matching the canonical query list (same 10 as UNLABELED).
- Each entry is one of two forms:

  **A)** `preferredAliases` contains 1–3 unique aliases from `{A, B, C}`,
      `allUnusable = false`.

  **B)** `preferredAliases = []`, `allUnusable = true`.

- Rules:
  - Aliases are only A, B, C; no other strings.
  - No duplicate aliases within a single entry.
  - `allUnusable = false` requires at least 1 alias; `allUnusable = true` requires 0 aliases.
  - `allUnusable` is never `null` when `status = "LABELED"`.
  - `notes` must be a string (may be empty).
  - Queries cannot be missing, duplicated, or unknown (must be the 10 canonical queries).
  - Multiple aliases represent a genuine tie; they are not a ranking.

- `preferences_status()` returns `"HUMAN_REVIEW_READY"`.
- `validate_preferences()` validates both states and returns a status dict
  with a human-readable description. It does not modify `score_candidates`
  or any ranking logic.

`validate_preferences()` and `manifest_hash()` are pure functions added to
`tools/pexels_photo_selection_benchmark.py`. They are part of the frozen
contract and must not be altered after this change without a new OpenSpec
change.

## Future Conditional Phase B

Only if Phase A is not validated: benchmark raw relative OpenCLIP ViT-B-32 /
`laion2b_s34b_b79k` cosine scores over the same labeled top-3 window. It must not
change threshold `0.2296`, runtime activation, or production code. Local pixels
exist for all 30 review candidates; top-15 pixels do not.

## Rank Terms

Future `pexelsQueryRank` means raw 1-based response position per query/page.
Future `CandidateEnvelope.provider_rank` means final 1-based lifecycle stream
position. This benchmark only uses evaluation-local equivalents.
