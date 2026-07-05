# Sesión: Duration contract under-30 + canonical token ownership

- Fecha: 2026-07-04
- Objetivo: Change duration contract to 25-30s, implement canonical token ownership, run Pompeya under-30 validation
- Estado inicial: Previously 35s (target) / 30-40s (range). Cross-scene leakage blocked at cue level but not verified semantically.
- Estado final: (pending validation)
- Agente responsable: opencode
- Cambio OpenSpec relacionado: configurable-job-contract-duration-and-quality-gates
- Validaciones realizadas: 44/44 tests passing

## Cambios realizados

### Duration contract

| Campo | Antes | Después |
|-------|-------|---------|
| targetSec | 35 | 28 |
| minSec | 30 | 25 |
| maxSec | 40 | 30 |
| strictness | balanced | balanced |

Word budget at 145 WPM:
- target: 28 * 145/60 ≈ 68 words
- min: 25 * 145/60 ≈ 60 words
- max: 30 * 145/60 ≈ 73 words

### Per-scene word guidance (prompt)

| Context | Antes | Después |
|---------|-------|---------|
| Initial prompt | 12-18 words/scene | 5-7 words/scene |
| Retry prompt | 18-25 words/scene | 6-10 words/scene |

### Canonical token ownership

New functions in `bin/generate_audio.py`:
- `_build_canonical_tokens(narration_units)` — builds ordered list of {text, sceneNumber, narrationUnitIndex}
- `_match_words_to_canonical(words, canonical_tokens)` — sequential alignment of Edge WordBoundary to canonical tokens; assigns sceneNumber and narrationUnitIndex BEFORE cue grouping

Modified:
- `group_words_into_cues()` — flushes on sceneNumber OR narrationUnitIndex change
- `generate_audio_with_timestamps()` — accepts narration_units param, uses canonical matching when available

### Semantic validation

New in `bin/coverage_validation.py`:
- `validate_canonical_cue_integrity()` — checks each cue's words against canonical per-scene vocabulary; returns exact offending token with source/target scene

### Updated defaults

| File | Change |
|------|--------|
| `bin/generate_script.py` | duration CLI defaults: 28/25/30; request schema duration; prompt word guidance |
| `bin/generate_audio.py` | DEFAULT_DURATION_CONTRACT: 28/25/30 |
| `tests/test_duration_contract_and_scene_boundary.py` | All test helpers and assertions updated to 28/25/30; 4 new canonical ownership tests |

## Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `bin/generate_audio.py` | DEFAULT_DURATION_CONTRACT, _build_canonical_tokens, _match_words_to_canonical, group_words_into_cues flush logic, generate_audio_with_timestamps narration_units param, main_continuous passes narration_units |
| `bin/generate_script.py` | CLI defaults 28/25/30, prompt per-scene guidance 5-7 words, request schema duration, retry prompt 6-10 words |
| `bin/coverage_validation.py` | validate_canonical_cue_integrity(), run_coverage_validation includes canonicalValidation |
| `tests/test_duration_contract_and_scene_boundary.py` | Updated all test defaults 28/25/30, added 4 canonical token tests |
| `openspec/changes/.../proposal.md` | Updated duration contract JSON |
| `openspec/changes/.../design.md` | Updated duration contract example |
| `openspec/changes/.../tasks.md` | Added Phase 15 (canonical), Phase 16 (validation); updated acceptance criteria |
| `docs/sessions/2026-07-04-0100-duration-contract-under-30-and-canonical-tokens.md` | This file |

## Próximos pasos

1. Run Pompeya under-30 full pipeline
2. Run Wright script+audio only
3. Verify acceptance criteria
4. Update tasks.md with validation results