# Session: Subtitle Timing Precision and Legibility

**Date**: 2026-07-01 23:45
**Job**: `la-2026-07-01-173458` (La caída de Constantinopla)
**OpenSpec**: `fix-subtitle-timing-and-legibility`

## Goal

Replace proportional cue remapping with exact cumulative_offset warping, improve ASS subtitle styles for contrast/legibility, and add cue validation — without modifying audio, assets, or visual pipeline.

## Baseline

Current render at `data/videos/la-2026-07-01-173458/video.mp4` (27.098s, RENDERED status):
- 15 cues remapped proportionally per-scene after silence trimming
- 5 chapter_break trims of ~1.1s → 0.35s each
- ASS style: Arial Bold 65, white, full opacity, no background box
- Remap strategy: proportional within each scene

## Plan

1. Replace proportional remap → cumulative_offset in `trim_narration_silences.py`
2. Save `originalCues`, `trimOperations`, `remappedCues` in metadata
3. Add cue validation (no overlap, within audio, text match, drift explainable)
4. Create two ASS styles: `documentary_safe` (default) and `shorts_dynamic`
5. Document ASR provider interface (edge_tts_sentence_boundary + optional google_stt_word_offsets)
6. Regenerate subtitle.ass and re-render with validations
7. Generate before/after cue comparison and contrast screenshots

## Validation criteria

- Cue start < cue end for all
- No overlaps (endSec <= next startSec)
- Text matches narration
- All cues within audio duration
- Max drift ≤ cumulative trim offset per scene
- Screenshots at 20%/50%/80% show readable subtitles on both light and dark backgrounds

## Files to modify

- `bin/trim_narration_silences.py` — cumulative_offset remapping, metadata save
- `bin/prepare_job.py` — ASS style generation
- `bin/coverage_validation.py` — updated cue validation

## Results

- **remapStrategy**: `cumulative_offset` — implemented via `adjust_cues_cumulative()` + `build_trim_operations()` + `cumulative_offset()`
- **5 trim operations**: 0.001-0.005s removed each (original audio already had chapter breaks near target)
- **15 cues remapped**: zero drift (0.0ms all), zero crossed boundaries, zero overlap
- **ASS style**: `documentary_safe` (Arial Bold 55, BorderStyle=3, BackColour=&H80000000, MarginV=50)
- **Validation**: coverage 100%, cue integrity PASS, remap validation PASS, cue text PASS
- **Render**: RENDERED with all validations PASS (27.087s, 10 segments, FFmpeg exit 0)
- **Screenshots**: extracted at 20%/50%/80% — saved to `validation/` dir
- **Cue comparison**: written to `validation/cue_comparison.txt`

## What cannot be auto-validated

- Subtitle contrast against actual scene backgrounds (human visual check of screenshots needed)
- Font rendering of accented characters (Arial Bold → DejaVuSans-Bold fallback used)
- Line break quality (wrap_line at ~20 chars)
- Perceptible timing naturalness (shifts ≤5ms, should be imperceptible)
- Audio quality of chapter breaks (expected REVIEW_REQUIRED due to 4.74s silence by design)

## Not modified

- `bin/generate_audio.py`
- `bin/render_job.py` (visual pipeline, asset validation)
- `bin/audio_validation.py`
- `bin/asset_validation.py`
- Any image/audio asset
