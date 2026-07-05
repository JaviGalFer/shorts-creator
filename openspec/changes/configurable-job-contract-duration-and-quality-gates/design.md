# Design: Configurable Job Contract, Duration Enforcement, and Quality Gates

## Architecture

### Scene boundary enforcement in cue grouping

```
WordBoundary events (no scene info)
  → Annotate with punctuation
  → Assign sceneNumber per word (sequential match against narration_units)
  → group_words_into_cues() with scene-aware flush
  → _assign_scene_numbers() per cue (still based on timing, but words already scoped)
  → Null check: no cue text contains words from multiple scenes
```

### Duration contract flow

```
request.duration {targetSec, minSec, maxSec, strictness, wordsPerMinute}
  → generate_script.py: budget words = targetSec * wordsPerMinute / 60 (default: 110)
  → LLM prompt includes word budget hint
  → Post-generation: estimate duration from script word count
  → If outside range, regenerate or mark WARNING
  → generate_audio.py: synthesize, measure real duration
  → If outside range, set REVIEW_REQUIRED with structured reason
```

### Validation state model

```python
class ValidationState(str, enum.Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"

# Gates:
# technicalValidation: ffmpeg OK, duration matches, no black/freeze frames
# subtitleCoverageValidation: coverage >= threshold
# assetValidation: asset checks
# qualityGate: aggregate of all gates
```

### Job request schema

Stored in metadata.json as `request` field. Backward compatible: old metadata without `request` field uses defaults.

### Asset quality gate

When `--skip-asset-validation` is used:
- Asset validation still runs (cannot be truly skipped)
- Results are recorded as warnings
- If any asset is invalid/BLOCKED, status becomes `RENDERED_WITH_ASSET_WARNINGS`
- Plain `RENDERED` requires clean asset validation

## Data flow

### metadata.json additions

```json
{
  "request": {
    "topic": "...",
    "language": "es-ES",
    "format": "shorts-9x16",
    "duration": {"targetSec": 28, "minSec": 25, "maxSec": 30, "strictness": "balanced"},
    "voice": {"provider": "edge_tts", "voiceId": "es-ES-AlvaroNeural"},
    "subtitles": {"enabled": true, "timingProvider": "auto", "style": "shorts_upper_dynamic"},
    "visuals": {"mode": "images", "allowGeneratedImages": false},
    "editorialOverlays": {"enabled": false}
  },
  "resolvedConfig": { ... same structure but with env/CLI overrides applied ... }
}
```

### job-manifest.json additions

```json
{
  "request": { ... },
  "resolvedConfig": { ... },
  "validation": {
    "technicalValidation": "PASS",
    "subtitleCoverageValidation": "PASS",
    "assetValidation": "PASS",
    "qualityGate": "PASS"
  }
}
```

## Files to modify

| File | Change |
|------|--------|
| `bin/generate_audio.py` | Add sceneNumber to words, enforce scene boundaries in group_words_into_cues(), add duration validation |
| `bin/generate_script.py` | Add word budget to prompt (NARRATION_WORDS_PER_MINUTE=110), validate script duration |
| `bin/render_job.py` | Add validation state model, asset gate status |
| `bin/validate_job.py` | Add validation state model, cross-scene text check |
| `bin/coverage_validation.py` | Add cross-scene text validation |
| `tests/` | New regression tests |

## Decisiones

1. Scene boundaries are enforced at the word level (pre-grouping), not at the cue level (post-grouping). This prevents any possibility of cross-scene text in a single cue.
2. The `request` field stores the original user intent. The `resolvedConfig` stores what was actually used after CLI/env overrides. This supports future web UI: the UI can submit a `request` and the pipeline resolves it.
3. Duration validation is a gate, not a hard stop. Jobs outside the target range enter REVIEW_REQUIRED status but are not deleted. This allows human review.
