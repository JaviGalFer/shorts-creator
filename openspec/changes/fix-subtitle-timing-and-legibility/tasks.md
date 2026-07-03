# Tasks: Fix Subtitle Timing and Legibility

## Phase 1 — Cumulative offset remapping
- [x] Rewrite `adjust_cues()` in `trim_narration_silences.py` to use pure cumulative_offset
- [x] Handle cue crossing a trim boundary: split or flag for review
- [x] Save `subtitleTiming.originalCues`, `.trimOperations`, `.remappedCues`, `.remapStrategy = "cumulative_offset"` in metadata

## Phase 2 — Cue validation
- [x] Validate: cueStart < cueEnd
- [x] Validate: no overlaps (endSec <= next startSec)
- [x] Validate: text matches narration
- [x] Validate: all cues within audio duration
- [x] Validate: drift explainable by trimOperations

## Phase 3 — ASS style improvement
- [x] Create `documentary_safe` style (semittransparent box, white text)
- [x] Create `shorts_dynamic` style (strong outline + shadow)
- [x] Create `shorts_upper_dynamic` style (central-upper, no box, strong contrast)
- [x] Set `documentary_safe` as default (global), `shorts_upper_dynamic` used for Constantinopla
- [x] Ensure max 2 lines, safe bottom margin (MarginV=50 for documentary)
- [x] Ensure upper positioning (Alignment=8, MarginV=430 for upper)

## Phase 4 — ASR provider interface
- [x] Document `SubtitleTimingProvider` interface (in design.md table)
- [x] Document `edge_tts_sentence_boundary` provider
- [x] Document optional `google_stt_word_offsets` (not active, no credentials)

## Phase 5 — Regenerate and validate
- [x] Run `trim_narration_silences.py` with cumulative_offset to update metadata
- [x] Run `prepare_job.py` to regenerate subtitle.ass with `documentary_safe` style
- [x] Run `render_job.py` → RENDERED, all validations PASS
- [x] Generate before/after cue comparison (written to `validation/cue_comparison.txt`)
- [x] Generate screenshots at 20%/50%/80% (saved to `validation/`)
- [x] Verify: zero drift, zero crossed trim, coverage 100%, integrity PASS

## Phase 6 — Close
- [x] Update session log (this file)
- [x] Update design.md with actual implementation values
- [x] Mark tasks complete
- [x] Document what cannot be auto-validated (see design.md §5)
