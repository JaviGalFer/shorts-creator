# Session: Shorts Upper Dynamic Subtitle Style

**Date**: 2026-07-01 23:50
**Job**: `la-2026-07-01-173458` (La caída de Constantinopla)
**OpenSpec**: `fix-subtitle-timing-and-legibility`

## Goal
Implement `shorts_upper_dynamic` style: central-superior position, no background box, strong contrast (outline+shadow).

## Changes
- Updated `bin/prepare_job.py`:
  - Added `shorts_upper_dynamic` style to `ASS_STYLES`.
  - Refactored `_ass_style_line` to dynamically handle margins.
- Regenerated `subtitle.ass` using `--subtitle-style shorts_upper_dynamic`.
- Re-rendered `video.mp4` with new styles.

## Validation Results
- **Subtitle Style**: `shorts_upper_dynamic` (DejaVu Sans Bold, Fontsize 64, Alignment 8, MarginV 430, Outline 4, Shadow 2, No Box).
- **Consistency**:
  - Cues: Unchanged (15).
  - Timestamps: Unchanged.
  - Duration: Unchanged (27.1s).
  - Audio/Assets: Unchanged.
- **Visual**: Screenshots at 20%/50%/80% (`validation/`) confirm placement and legibility.

## Next steps
- Awaiting human review of screenshots for final contrast approval.
