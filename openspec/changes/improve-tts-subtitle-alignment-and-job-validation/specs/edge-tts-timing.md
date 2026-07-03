# Edge TTS Timing Specification

## WordBoundary + SentenceBoundary events

Edge TTS emits two boundary events during synthesis:

- **WordBoundary**: Per-word timing with `offset` (start in 100ns ticks), `duration` (in ticks), `text` (word text, punctuation stripped).
- **SentenceBoundary**: Per-sentence timing with `offset` (sentence start in ticks), `duration` (sentence audio duration in ticks), `text` (full sentence text).

## Submaker

`edge_tts.SubMaker` processes WordBoundary events. It converts `offset` → `timedelta(microseconds=offset/10)` as start, `offset+duration` → `timedelta(microseconds=(offset+duration)/10)` as end. SentenceBoundary events are handled separately (not fed to SubMaker).

## Punctuation annotation from canonical text

Edge TTS strips punctuation from WordBoundary event text. To recover it:

1. Split `full_text` (the complete narration sent to Edge TTS) into canonical words.
2. For each WordBoundary word, find its matching canonical word by stripping punctuation from the canonical word.
3. If the canonical word has trailing punctuation (`,`, `.`, `!`, `?`, `;`, `:`), append it to the WordBoundary text.

This enables the `is_end_of_sentence` and `is_medium_with_punct` heuristics in `group_words_into_cues()`.

**Limitation**: Only trailing punctuation is recovered. Leading punctuation (e.g., `¡` in Spanish) is not restored.

## Sentence boundary split algorithm

Grouping WordBoundary words into cues must respect sentence boundaries:

1. Collect all SentenceBoundary events (offset, duration).
2. For sentence \(i\) where \(i < n-1\), compute split point as `sentence_boundaries[i+1]["offset"] / TICK` (the next sentence's start).
3. For the last sentence (\(i = n-1\)), compute split point as `(sb["offset"] + sb["duration"]) / TICK` (its own end).
4. During word iteration, silently consume (pop) any sentence boundaries where `word.startSec >= sb_end_times[0]`.
5. **Do NOT flush the buffer at sentence boundaries**. Cue breaks are determined by `is_end_of_sentence`, `is_medium_with_punct`, `is_long_enough` (7 words), and `is_pause` (>0.5s gap).
6. Short cues (<0.7s) whose `startSec` is within 0.1s of any sentence boundary break are prevented from merging backward in post-processing, preventing cross-sentence leaks.

**Why not `offset + duration`**: The SentenceBoundary's `offset + duration` (sentence end) can overestimate by ~50ms relative to where the next sentence's first WordBoundary starts. 

**Why not flush at boundary**: Flushing at sentence boundaries creates single-word cues at the start of new sentences (the first word that triggers the boundary). These short cues then merge backward via the <0.7s merge rule, re-crossing sentence boundaries. Silent consumption (pop only) avoids this entirely.

## Subtitle timing provider modes

### `edge_tts` mode

- Uses WordBoundary events directly from Edge TTS `SubMaker.cues`.
- Calls `group_words_into_cues(word_boundaries, sentence_boundaries)` with the `sentence_boundaries` parameter for sentence-aware splitting.
- Source string: `"edge_tts_word_boundary"`.
- Confidence: `"high"`.

### `whisper` mode

- Uses `whisper_subtitles.align_with_canonical_text()`.
- Whisper word timestamps reconciled to canonical script text.
- Assigns cues to scenes via `sceneTimings` overlap.
- Falls back to estimated if faster-whisper is not installed.
- Source string: `"whisper_reconciled"`.

### `auto` mode

- If Edge TTS returned WordBoundary events (`"word_boundary" in source.lower()`), use `edge_tts` mode.
- Else if faster-whisper is importable, use `whisper` mode.
- Else fall back to `estimated`.

### `estimated` mode

- Uniform word distribution: `word_duration = sentence_duration / len(words)`.
- No sentence boundary splitting.
- Source string: `"estimated"`, Confidence: `"low"`.

## `SUBTITLE_GLOBAL_OFFSET_MS`

- Applied in `main_continuous()` after cue generation and scene assignment.
- Offset is `offset_ms / 1000.0` seconds.
- Applied to all `startSec` and `endSec` values in all scenes.
- Clamped to `max(0, value)` to prevent negative times.
- Default: `0` (no offset).

## Timing data flow

```
Edge TTS stream
  ├── WordBoundary → SubMaker.cues → word_boundaries[{startSec, endSec, text}]
  └── SentenceBoundary → sentence_boundaries[{offset, duration, text}]
                              │
                              ▼
                  group_words_into_cues(word_boundaries, sentence_boundaries)
                              │
                              ▼
                           cues[]
                              │
                              ▼
                  _assign_scene_numbers(cues, scene_timings)
                              │
                              ▼
                  cues_by_scene[sceneNumber]
                              │
                              ▼
                  Apply SUBTITLE_GLOBAL_OFFSET_MS
                              │
                              ▼
                  Write to metadata.json
```
