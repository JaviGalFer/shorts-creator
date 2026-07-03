# Session: Edge vs Whisper Timing Comparison — Decision

**Date**: 2026-07-03 20:30 UTC
**Duration**: ~25 min
**Goal**: Compare rendered videos to decide default subtitle timing mode

## Summary

Re-rendered both comparison jobs, extracted 12 validation frames (6 pairs), validated both, and compared. **Decision: Option A (Edge TTS native timing as default)**

## What was done

1. Ran `prepare_job.py` for both edge and whisper jobs separately (no glob support)
2. Ran `render_job.py` for both jobs via Docker FFmpeg
3. Extracted comparison frames at key cue transitions using docker ffmpeg
4. Ran `validate_job.py --verbose` on both jobs
5. Updated tasks.md with comparison evidence
6. Updated design.md with architectural decision

## Key findings

- Edge: 14 cues, 78% coverage, 0 errors, 1 warning
- Whisper: 13 cues, 69% coverage, 0 errors, 1 warning
- Scene 1 gap: Edge 0.21s vs Whisper 0.90s
- Scene 1 grouping: Edge splits "imperio"/"milenario." reflecting TTS pacing; Whisper combines
- Edge missing leading ¡/¿ in Scene 6 CTA (known cosmetic issue)
- Both share identical text in Scene 4 ("El 29 de mayo,", "las murallas cedieron.", "Constantinopla estaba perdida.")

## Decision

**Option A: Edge TTS native timing as default**.

Coverage (78% > 69%), native timing accuracy, and smaller gaps outweigh the cosmetic leading punctuation loss. --subtitle-timing-provider defaults to edge_tts in auto mode.

## Edge default accepted (Jul 3 2026 — final maintenance)

### Confirmed config
- `SUBTITLE_TIMING_PROVIDER=auto` in `.env.example`
- CLI help: `--subtitle-timing-provider` defaults to `auto`
- Design doc: Edge default documented

### Files modified (final maintenance pass)

| File | Change |
|------|--------|
| `.env.example` | Added `SUBTITLE_TIMING_PROVIDER=auto` with docs |
| `openspec/.../proposal.md` | Added Estado section (pending review, deferred follow-ups noted); added acceptance criteria 13-14 |
| `openspec/.../design.md` | Added regression tests reference |
| `openspec/.../tasks.md` | Added deferred follow-up tasks (¡/¿ restoration, regression fixtures) |
| `tests/test_timing_regression.py` | New: 4 regression test fixtures (boundary crossing, punctuation, leakage, single-word) |
| `docs/sessions/2026-07-03-2030-edge-vs-whisper-comparison-and-decision.md` | Final state summary |

### OpenSpec state
- **proposal.md**: Pendiente de revisión (awaiting review). All scope items implemented. Deferred items noted.
- **design.md**: Contains full architecture, decision record, regression test reference.
- **tasks.md**: All 9 phases complete + comparison evidence + deferred follow-ups.

### Deferred follow-up tasks
1. **Spanish leading punctuation (¡, ¿) restoration** — extend `_annotate_word_punctuation()` to detect and prepend leading punctuation from canonical text.
2. **Regression test fixtures** — `tests/test_timing_regression.py` created with 4 test cases. Run with `python3 -m pytest tests/test_timing_regression.py -v`.

### Default configuration
```
SUBTITLE_TIMING_PROVIDER=auto  # edge_tts → whisper → estimated
```
