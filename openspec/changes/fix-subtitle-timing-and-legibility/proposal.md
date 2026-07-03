# Proposal: Fix Subtitle Timing and Legibility

## Problem

1. Cue remapping after silence trimming uses proportional scaling within scenes, introducing millisecond drift
2. White subtitles lack contrast against light backgrounds (no outline/shadow/box)
3. No validation pipeline exists for cue timing integrity

## Scope

Strictly limited to subtitle timing and ASS styling. No changes to audio, assets, visual pipeline, or duration.

## Solution

1. Replace proportional remap with cumulative_offset (exact time-warp by trim operations)
2. Two ASS styles: `documentary_safe` (default, semitransparent box) and `shorts_dynamic` (outline+shadow)
3. Cue validation: no overlap, within audio, text match, drift explainable
4. ASR provider interface documented for future `google_stt_word_offsets`
