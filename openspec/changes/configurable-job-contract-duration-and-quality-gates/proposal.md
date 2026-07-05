# OpenSpec: Configurable Job Contract, Duration Enforcement, and Quality Gates

## Problema actual

1. **Cross-scene subtitle leakage**: Cues can contain words from multiple scenes. Scene 2's "El" leaks into Scene 1 of Wright; Scene 2's "Una" leaks into Scene 1 of Pompeya. This is a blocking bug.
2. **Duration target ignored**: Wright targets 35s, actual ~25s. Pompeya targets 35s, actual ~25s. Magallanes targets 40s, actual ~30s. The requested duration is not enforced.
3. **No canonical job request schema**: Scripts, CLI, and future web UI cannot share a common contract.
4. **Validation states inconsistent**: `render_job.py` may report RENDERED while `validate_job.py` reports FAIL. Coverage status mismatch between manifest and standalone validator.
5. **Asset quality bypassed silently**: `--skip-asset-validation` produces RENDERED status without any indication of degraded asset quality.

## Objetivo

1. Fix cross-scene subtitle leakage at the cue grouping level.
2. Enforce duration target via word-count budgeting and post-synthesis validation.
3. Create a canonical job request schema with backward compatibility.
4. Unify validation states (PASS/WARNING/FAIL/NOT_APPLICABLE) across all tools.
5. Add asset quality gate that produces `RENDERED_WITH_ASSET_WARNINGS` instead of plain `RENDERED`.

## Alcance incluido

- Fix `group_words_into_cues()` to enforce scene boundaries as hard flush points.
- Add `NARRATION_WORDS_PER_MINUTE` config with a default of 110 (measured median of Edge TTS Spanish effective rate).
- Add `duration` config to metadata with `targetSec`, `minSec`, `maxSec`, `strictness`.
- Validate script word count against target duration before accepting LLM output.
- Validate actual audio duration against target after synthesis; set REVIEW_REQUIRED if outside range.
- Create/unify job request schema: `request` field in metadata for canonical input, `resolvedConfig` for effective configuration.
- Create validation state model: `technicalValidation`, `subtitleCoverageValidation`, `assetValidation`, `qualityGate` with states PASS/WARNING/FAIL/NOT_APPLICABLE.
- Add `RENDERED_WITH_ASSET_WARNINGS` status when assets are degraded but render proceeds.
- Add regression tests for all fixes.
- Create 2 new isolated validation jobs.

## Alcance excluido

- No redesign of the asset fetching/scoring system.
- No changes to subtitle visual style, Docker setup, Edge TTS voice quality, or editorial overlays.
- No stretching audio or manipulating subtitle timestamps after synthesis to fake duration.
- No web UI implementation.
- No modification of existing regression jobs (val-pompeya, val-wright, val-magallanes).

## Decisiones técnicas

### Scene boundary enforcement in cue grouping

Each word is assigned a `sceneNumber` by sequential matching against narration units before grouping. `group_words_into_cues()` flushes the current cue buffer when the next word belongs to a different scene, before any other grouping heuristics.

### Duration contract

```json
{
  "duration": {
    "targetSec": 28,
    "minSec": 25,
    "maxSec": 30,
    "strictness": "balanced"
  }
}
```

Strictness modes:
- `strict`: narration must remain within target ±10%
- `balanced`: narration must remain within min/max range (default for shorts)
- `relaxed`: target is advisory, actual duration reported

Word budget at 110 WPM: ~46 words (25s) to ~55 words (30s), target ~51 words (28s).
Measured effective rate (including inter-sentence pauses): 107-114 WPM across 3 runs.
110 WPM chosen as conservative median within the observed range.

Word budget: `word_count = int(targetSec * NARRATION_WORDS_PER_MINUTE / 60)`

### Validation state model

| Gate | States | Source |
|------|--------|--------|
| technicalValidation | PASS, WARNING, FAIL | ffmpeg exit, duration, black/freeze frames |
| subtitleCoverageValidation | PASS, WARNING, FAIL | coverage % checks |
| assetValidation | PASS, WARNING, FAIL, NOT_APPLICABLE | asset validation module |
| qualityGate | PASS, FAIL | aggregation of all gates |

### Asset quality gate

When `--skip-asset-validation` is used and any asset fails validation, final status is `RENDERED_WITH_ASSET_WARNINGS` instead of `RENDERED`.

## Riesgos y fallback

- Edge TTS timing edge cases: scene boundary may not perfectly align with word boundaries. Words are assigned to scenes based on canonical narration unit mapping, not timing.
- Duration enforcement may cause jobs to enter REVIEW_REQUIRED more often. This is intentional.
- Backward compatibility: existing jobs without `request` or `duration` fields continue to work with default values.

## Criterios de aceptación

1. No cue contains canonical words from another scene.
2. No cue exceeds its scene window by more than 0.05s (tolerance).
3. Wright-style "Kitty Hawk El" cross-scene leakage is detected and blocked.
4. Pompeya-style "cenizas Una" cross-scene leakage is detected and blocked.
5. Requested 28s with actual 24s in balanced mode is not accepted silently (below 25s min).
6. Requested 28s with actual 31s in balanced mode fails (above 30s max).
7. Requested 28s with actual 28s in balanced mode passes.
7. `render_job.py` and `validate_job.py` calculate matching coverage status.
8. Invalid assets produce `RENDERED_WITH_ASSET_WARNINGS` not `RENDERED`.
9. `request` and `resolvedConfig` are present in metadata and manifest.
10. Backward compatible with existing metadata.json without `request`/`duration` fields.

## Estado

**Estado**: Pendiente de revisión.

### Completado

- Proposal created.

### Diferido (follow-up, no bloqueante)

1. Spanish leading punctuation (¡, ¿) restoration in Edge TTS annotation.
2. Pompeya scene-window edge case from proportional timing.
