# Session: validate-job-duration-contract

**Timestamp:** 2026-07-14 17:10:57 UTC
**Type:** Build
**Scope:** `bin/validate_job.py._check_durations()`

## 1. Root cause

`validate_job.py._check_durations()` applied `MAX_SEGMENT_DURATION=8.0` to `scene.targetDurationSec`, conflating two distinct concepts:

- **`scene.targetDurationSec`**: total intended duration of a scene (can be 8, 10, 12, 30 seconds).
- **`renderTimeline[].durationSec`**: duration of a single visual beat/segment within a scene.

A scene can legitimately span 10+ seconds and be divided into multiple valid segments (e.g., 5+5, 6+6). The 8.0 limit caused false failures for scenes 2 (targetDurationSec=10) and 3 (targetDurationSec=12) in the E2E job.

Additionally, `MAX_SEGMENT_DURATION` in `validate_job.py` was 8.0, while `render_job.py` uses 20.0 — a contract mismatch.

## 2. Difference between scene and segment

| Concept | Source | Limit | Example |
|---------|--------|-------|---------|
| Scene target duration | `script.scenes[].targetDurationSec` | `MAX_TOTAL_DURATION` (120s) | 12s |
| Timeline segment | `renderTimeline[].durationSec` | `MAX_SEGMENT_DURATION` (20s) | 6s |
| Scene aggregate window | `max(endSec) - min(startSec)` per scene number | Warning only if diff vs target is large | 12s |

## 3. New canonical total duration source

Total duration is now derived from `renderTimeline`:

```text
totalDuration = max(renderTimeline[].endSec)
```

This is the value that corresponds to the actual rendered video duration, not the sum of scene targets (which may differ due to audio-driven expansion).

For legacy metadata without `renderTimeline`, the fallback remains `sum(scene.targetDurationSec)`.

## 4. Timeline entry duration policy

Each `renderTimeline` entry is validated with parity to `render_job.py`:

- Numeric, finite, not bool
- `startSec >= 0`
- `endSec > startSec`
- `durationSec > 0`
- `durationSec <= 20.0` (MAX_SEGMENT_DURATION)
- `abs(durationSec - (endSec - startSec)) <= 0.05`

The constant `MAX_SEGMENT_DURATION` is now 20.0 in `validate_job.py`, matching `render_job.py`.

## 5. Legacy compatibility

- Metadata without `renderTimeline` uses `sum(scene.targetDurationSec)` for total duration.
- Continuous audio jobs retain the existing audio duration check.
- Scene target validation was tightened (numeric, finite, not bool) but the MAX_SEGMENT limit was removed from targets.

## 6. Tests added

19 new tests in `tests/test_validate_job_duration_contract.py`:

| Test | Description |
|------|-------------|
| `test_scene_12s_two_segments_passes` | 12s scene, 2 valid segments (Case A) |
| `test_e2e_compatible_3_scene_passes` | 3 scenes matching E2E (Case B) |
| `test_segment_exceeds_max_segment_duration_fails` | 21s segment > 20s limit (Case C) |
| `test_long_scene_valid_segments_passes` | 30s scene, 3 segments of 10s each (Case D) |
| `test_duration_mismatch_fails` | durationSec != end-start (Case E) |
| `test_gap_between_segments_fails` | 1s gap between segments (Case F) |
| `test_overlap_between_segments_fails` | 1s overlap between segments (Case G) |
| `test_target_negative_fails` | targetDurationSec = -1 |
| `test_target_zero_fails` | targetDurationSec = 0 |
| `test_target_bool_fails` | targetDurationSec = True |
| `test_target_nan_fails` | targetDurationSec = NaN |
| `test_target_inf_fails` | targetDurationSec = inf |
| `test_target_string_fails` | targetDurationSec = "eight" (Case H) |
| `test_legacy_metadata_without_timeline_passes` | No renderTimeline (Case I) |
| `test_legacy_metadata_exceeds_total_fails` | Target sum > MAX_TOTAL_DURATION |
| `test_continuous_audio_passes` | Continuous audio (Case J) |
| `test_continuous_audio_zero_duration_fails` | Continuous audio duration=0 |
| `test_max_segment_duration_matches_render_job` | validate_job MAX_SEGMENT_DURATION == render_job MAX_SEGMENT_DURATION |
| `test_scene_target_above_old_max_passes` | Scene target 12s with valid segments |

## 7. Focused test result

```text
19 passed in 0.05s
```

## 8. Full suite result

```text
1132 passed, 16 failed, 0 regressions
```

The 16 failures are pre-existent in `test_run_job.py` and `test_semantic_asset_validation.py`. No new failures introduced.

## 9. E2E revalidation result

```bash
python3 bin/validate_job.py \
  data/videos/e2e-pixabay-20260714-184248/metadata.json \
  --verbose
```

```text
Validation result: PASS
  Job: e2e-pixabay-20260714-184248
  Errors: 0
  Warnings: 1 (ffprobe unavailable - pre-existing)
```

## 10. Video checksum before and after

```text
sha256: d32e3b4b2b00a0440bbafaffd76f70aca6ff4262ccf3e7ebf77ffe6f766dc99d
```

Identical. The video was not regenerated.

## 11. Confirmation of no regeneration

Only `bin/validate_job.py` was modified and new tests were created. No pipeline stages were executed. No assets, audio, subtitles, or video files were touched.

## 12. Decision on temporal contract closure

The duration contract is now stabilized. The `validate_job.py._check_durations()` method correctly distinguishes between scene targets and timeline segments. `MAX_SEGMENT_DURATION=20.0` is aligned with `render_job.py`. All E2E gates pass.

**Status: READY FOR CLOSURE**
