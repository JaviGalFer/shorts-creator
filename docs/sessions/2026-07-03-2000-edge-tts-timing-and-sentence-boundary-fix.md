# Session: Edge TTS native WordBoundary + sentence boundary splitting fix

**Date:** 2026-07-03 20:00
**Goal:** Switch to Edge TTS WordBoundary as primary timing source, fix sentence boundary crossing

## Root cause

`group_words_into_cues()` used `current_sentence["offset"] + current_sentence["duration"]` (sentence end time) as the split point between sentences. But WordBoundary events for the FIRST word of the next sentence can start **before** this end time. The SentenceBoundary's `offset + duration` overestimates the sentence end by ~50ms compared to the next sentence's `offset`.

**Evidence from debug output**:
```
sb_end_times (old): [6.138, 10.925, 15.8, 19.387, 22.038, 26.35, 30.85]
scene 1 cue 2:      3.663-6.787 "con ella un imperio milenario La ciudad"  ← "La ciudad" es Scene 2
```

Sentence 1 `offset + duration` = 6.138s. Sentence 2 `offset` = 6.088s. First word of sentence 2 ("La") started at 6.112s. `6.112 >= 6.138` → False → no flush → "La" absorbed into Scene 1 cue.

## Files modified

| File | Change |
|------|--------|
| `bin/generate_audio.py:178` | Sentence boundary split point: usar `sentence_boundaries[i+1]["offset"]` en lugar de `sb["offset"] + sb["duration"]` |
| `bin/tts_provider.py:174` | Cambiar `Communicate()` a `boundary="WordBoundary"` |
| `bin/validate_job.py` | Añadido `_check_timing_info()` |
| `.venv/lib/python3.10/site-packages/edge_tts/communicate.py:426-440` | Patcheado `speech.config` para habilitar ambos boundaries |
| `openspec/changes/improve-tts-subtitle-alignment-and-job-validation/proposal.md` | Añadido alcance edge_tts timing, sentence boundary fix, SUBTITLE_GLOBAL_OFFSET_MS |
| `openspec/changes/improve-tts-subtitle-alignment-and-job-validation/design.md` | Añadida sección Edge TTS Native Timing con decisión técnica |
| `openspec/changes/improve-tts-subtitle-alignment-and-job-validation/specs/edge-tts-timing.md` | Especificación detallada del timing provider |
| `openspec/changes/improve-tts-subtitle-alignment-and-job-validation/tasks.md` | Añadidas Phase 9 tasks con verificación |

## Before / After

**EDGE job, Scene 1 + 2 cues**:

| Cue | Before (bug) | After (fix) |
|-----|-------------|-------------|
| Scene 1 cue 2 | `3.663-6.787 "con ella un imperio milenario La ciudad"` | `3.663-5.250 "con ella un imperio milenario"` |
| Scene 2 cue 1 | `6.800-8.725 "fue asediada por el sultán Mehmed II"` | `6.112-8.150 "La ciudad fue asediada por el sultán"` |

## Commands executed

```bash
# Debug run with sentence boundary logging
DOCKER_API_VERSION=1.43 .venv/bin/python3 bin/generate_audio.py \
  data/videos/la-timing-edge-20260703-182106/metadata.json \
  --voice es-ES-AlvaroNeural --continuous \
  --subtitle-timing-provider edge_tts --tts-provider edge_tts

# Verify whisper no regression
DOCKER_API_VERSION=1.43 .venv/bin/python3 bin/generate_audio.py \
  data/videos/la-timing-whisper-20260703-182106/metadata.json \
  --voice es-ES-AlvaroNeural --continuous \
  --subtitle-timing-provider whisper --tts-provider edge_tts

# Validate both
DOCKER_API_VERSION=1.43 .venv/bin/python3 bin/validate_job.py \
  data/videos/la-timing-*/metadata.json
```

## Validations performed

- Edge job generates 13 cues, source=`edge_tts_word_boundary`, confidence=high
- Whisper job generates 13 cues, source=`whisper_reconciled`, confidence=high
- Both jobs PASS validation (0 errors)
- Edge subtitle coverage: 79% (24.4s / 30.9s)
- Whisper subtitle coverage: 69% (21.3s / 30.9s)
- No sentence boundary crossing: "La ciudad" correctly starts Scene 2
- No regression in whisper path

## Improvement: Text grouping for edge mode (continuation, same session)

**Date:** 2026-07-03 20:20 (continuation)
**Goal:** Improve cue boundary naturalness for edge mode by recovering punctuation stripped by Edge TTS

### Problem

Edge TTS strips punctuation from WordBoundary text ("1453," → "1453", "milenario." → "milenario"). This defeats `is_end_of_sentence` and `is_medium_with_punct` heuristics, so cues were only split by `is_long_enough` (7 words) and `is_pause` (>0.5s gap).

### Solution

Three changes in `group_words_into_cues()`:

**1. Punctuation annotation** (`generate_audio.py:173`):
New function `_annotate_word_punctuation(words, full_text)` recovers trailing punctuation (`.,!?;:`) by cross-referencing each WordBoundary word with the canonical narration text (which has punctuation). For each WordBoundary word, finds the matching canonical word (stripped comparison) and appends any trailing punctuation.

**2. Silent boundary consumption** (`generate_audio.py:245`):
Sentence boundaries no longer trigger buffer flushes — only pop consumed split points. Cue breaks are driven entirely by heuristics (`is_end_of_sentence`, `is_medium_with_punct`, `is_long_enough`, `is_pause`). This prevents single-word cues at sentence boundaries.

**3. Merge prevention** (`generate_audio.py:271`):
Short cues (<0.7s) whose startSec is within 0.1s of a sentence boundary split point are NOT merged backward in post-processing, preventing cross-sentence leaks.

### Before / After comparison

```
BEFORE (edge, Scene 1):
  0.100-3.650 "Un día en 1453 Constantinopla cayó y"
  3.663-6.787 "con ella un imperio milenario La ciudad"  ← sentence boundary crossed

AFTER (edge, Scene 1):
  0.100-2.325 "Un día en 1453,"
  2.538-4.537 "Constantinopla cayó y con ella un imperio"
  4.550-5.250 "milenario."

AFTER (whisper, Scene 1):
  0.000-1.880 "Un día en 1453,"
  2.780-5.200 "Constantinopla cayó y con ella un imperio milenario."
```

### Edge vs Whisper final comparison

| Aspect | Edge (14 cues) | Whisper (13 cues) |
|--------|---------------|-------------------|
| Scene 1 | "Un día en 1453," / "Constantinopla cayó y con ella un imperio" / "milenario." | "Un día en 1453," / "Constantinopla cayó y con ella un imperio milenario." |
| Scene 2 | "La ciudad fue asediada por el sultán" / "Mehmed II y su ejército otomano." | "La ciudad fue asediada por el sultán" / "Mehmed II y su ejército otomano." |
| Scene 4 | "El 29 de mayo," / "las murallas cedieron." / "Constantinopla estaba perdida." | "El 29 de mayo," / "las murallas cedieron." / "Constantinopla estaba perdida." |
| Scene 6 | "Si quieres saber más sobre la historia," / "síguenos para más contenido!" | "Si quieres saber más sobre la historia," / "¡síguenos para más contenido!" |
| Sentence boundaries | ✅ Clean (no crossing) | ✅ Clean |
| Punctuation in cues | ✅ commas and periods restored | ✅ native |
| Validation | PASS (0 errors, 1 warning) | PASS (0 errors, 1 warning) |

Edge timing is now production-quality in terms of grouping and boundary correctness.

### Files additionally modified

- `bin/generate_audio.py:173` — Added `_annotate_word_punctuation()`
- `bin/generate_audio.py:245` — Changed boundary handling from flush+pop to silent pop only
- `bin/generate_audio.py:257-258` — Restored `is_end_of_sentence` single-word flush
- `bin/generate_audio.py:271-273` — Added `sb_breaks` merge prevention
- `openspec/.../design.md` — Added Punctuation Annotation section + design decisions
- `openspec/.../specs/edge-tts-timing.md` — Updated algorithm docs
- `openspec/.../tasks.md` — Added verification entries
- `docs/sessions/2026-07-03-2000-edge-tts...` — Updated with continuation

### Remaining

- Review comparison videos (no winner declared)
- Consider restoring leading punctuation (¡, ¿) — currently not recovered by trailing-only annotation
