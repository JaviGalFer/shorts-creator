# Tasks: pexels-photo-selection-benchmark

## Slice 1: Phase A Preparation

- [x] Freeze evaluation-only scope, strategies, metrics, thresholds, and outcomes.
- [x] Add deterministic metadata-only A0/A1/A2 harness with no network/secrets.
- [x] Add tracked blind manifest and explicitly unlabeled preference template.
- [x] Generate git-ignored blinded contact sheets and review instructions.
- [x] Add offline focused tests for scoring, ordering, artifacts, and review inputs.
- [x] Validate focused tests and full test suite.

## Human Review

- [ ] Reviewer fills only `preferredAliases`, `allUnusable`, and optional `notes`.
- [ ] Validate preference schema and run the frozen Phase A evaluation.

## Conditional Slice 2: Pixel Ranking

- [ ] Run only if Phase A is not validated and candidate-level labels are sufficient.

## Slice 3: Decision And Closure

- [ ] Record final evidence and decision without modifying Pexels runtime.
