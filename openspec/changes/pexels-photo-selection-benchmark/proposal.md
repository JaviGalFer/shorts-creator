# Proposal: pexels-photo-selection-benchmark

## Status

IN PROGRESS. Phase A strategy and implementation are frozen; human review is pending.

## Problem

Pexels Photos returns an ordered top-15 result set, but the existing semantic
scorer is an acceptance classifier, not a validated relative ranker. The
`pexels-photos-runtime` change must not use a top-N ordering rule until it is
benchmarked against candidate-level human preferences.

## Goal

Evaluate a small, deterministic set of metadata-only candidate-ordering
strategies against a blinded, candidate-level human review of the already
persisted Pexels Photo top-3 results. This is evaluation-only and performs no
Pexels requests or downloads.

## Scope

- Freeze A0 RAW, A1 exact lexical recall, and A2 BM25 before preferences exist.
- Create deterministic blinded review materials for the ten persisted review queries.
- Add an offline stdlib harness, fixtures, and tests.
- Evaluate only after the preference fixture is explicitly labeled.

## Out Of Scope

- Pexels runtime integration, routing, provider config, candidate contracts, or UI.
- Changes to the semantic gate or visual-fidelity runtime.
- New network requests, downloads, labels inferred from historical aggregate review,
  aliases, query-specific tuning, hybrid selectors, or an A3 strategy.

## Success Criteria

- Strategies, metrics, decision criteria, and blind mapping are committed before
  human preferences are entered.
- The harness is deterministic, offline, import-safe, and does not accept labels
  in its scoring API.
- A final outcome is only computed from explicit candidate-level labels.
