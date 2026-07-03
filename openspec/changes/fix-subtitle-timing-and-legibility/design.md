# Design: Subtitle Timing Precision and Legibility

## 1. Cumulative offset remapping

### 1.1 Current problem

`adjust_cues()` in `trim_narration_silences.py` uses proportional scaling within scenes after trim:
- cues before a chapter_break get correct cumulative offset
- cues starting inside a chapter_break get proportional remap
- no preservation of original cues

This causes millisecond drift for cues near trim boundaries.

### 1.2 New algorithm

Pure cumulative offset: for each chapter_break silence, compute the amount removed (`original_duration - TARGET`). For each cue, subtract all removed durations whose endSec is before the cue's startSec. This is exact — no scaling of cue durations.

```
for each cue:
    offset = sum(removed for all chapter_breaks ending <= cue.startSec)
    adjusted_start = cue.startSec - offset
    adjusted_end   = cue.endSec - offset
```

If a cue **crosses** a chapter_break boundary (start < cb.start and end > cb.start):
- Split into two cues: pre-trim and post-trim
- Post-trim part receives cumulative offset
- Flag for review

### 1.3 Metadata

```json
"subtitleTiming": {
  "remapStrategy": "cumulative_offset",
  "originalCues": [...],
  "trimOperations": [
    {"type": "chapter_break", "sceneNumber": 1, "originalStart": 5.191, "originalEnd": 5.541,
     "originalDuration": 0.350, "targetDuration": 0.350, "removed": 0.0}
  ],
  "remappedCues": [
    {"originalStart": 5.13, "originalEnd": 5.191, "adjustedStart": 5.13, "adjustedEnd": 5.191,
     "driftMs": 0.0, "crossesTrim": false, "text": "imperio milenario."}
  ],
  "cues": [...]  // final cues (same as remappedCues applied)
}
```

## 2. ASS styles

### 2.1 documentary_safe (default)

```
Style: documentary_safe,Arial Bold,55,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,
       -1,0,0,0,100,100,0,0,3,0,0,2,60,60,50,1
```

- White text (`&H00FFFFFF`)
- Semitransparent black box (`&H80000000`, BackColour alpha=128, BorderStyle=3)
- Outline=0, Shadow=0 (BorderStyle=3 does not render these — box alone provides contrast)
- Alignment=2 (bottom center)
- MarginV=50 (safe zone from bottom, ~9% of height)
- Font size 55 (fits 2 lines of ~20 chars in 1080x1920)

### 2.2 shorts_dynamic

```
Style: shorts_dynamic,Arial Bold,65,&H00FFFFFF,&H000000FF,&H00000000,&H40000000,
       -1,0,0,0,100,100,0,0,1,2,2,2,60,60,40,1
```

- White text
- Strong outline (Outline=2, BorderStyle=1)
- Soft shadow (Shadow=2, BackColour=&H40000000 alpha=64)
- No box — relies on outline+shadow for contrast
- Alignment=2, MarginV=40
- Font size 65 (more prominent)

### 2.3 shorts_upper_dynamic

```
Style: shorts_upper_dynamic,DejaVu Sans Bold,64,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,
       -1,0,0,0,100,100,0,0,1,4,2,8,140,140,430,1
```

- White text (`&H00FFFFFF`)
- No background box (`BorderStyle=1`, `BackColour=&H00000000`)
- Thick black outline (`Outline=4`) and black shadow (`Shadow=2`) for maximum contrast on light and dark backgrounds
- Alignment=8 (top center)
- MarginV=430 (positions the subtitle block approximately between 22% and 30% of height in 1080x1920 viewport, Y range 430-520px)
- MarginL=140, MarginR=140 (restricts text to ~70-75% width of viewport)
- Font: DejaVu Sans Bold (guarantees perfect rendering of Spanish accents/tildes)

## 3. Validation rules

Implemented in `coverage_validation.py`:

1. `validate_cue_integrity()`:
   - All cue.startSec < cue.endSec
   - No overlaps: cue[i].endSec <= cue[i+1].startSec (tolerance 0.01s)
   - All cues within audio duration: endSec <= totalDuration
   - Text joined matches narration text (normalized)

2. `validate_remapped_cues()`:  
   - For each remapped cue, drift = abs(adjustedDuration - originalDuration)
   - Drift > 10ms flagged as warning
   - CrossesTrim cues flagged for review

## 4. ASR provider interface

```python
class SubtitleTimingProvider(ABC):
    @abstractmethod
    def get_cues(self, audio_path: str, scene_texts: list[dict]) -> dict:
        """Return {cues: [...], timingSource: str, timingConfidence: str}"""
```

| Field | edge_tts_sentence_boundary | google_stt_word_offsets (future) |
|-------|---------------------------|--------------------------------|
| Source | EdgeTTS SentenceBoundary events | Google STT word-level timing |
| Input | narration.mp3 + scene voiceovers | narration.mp3 |
| Output | cues with startSec/endSec/text | cues with word-level offsets |
| Cost | Free (local) | Paid (API usage) |
| Status | Active | Documented, not implemented |

## 5. What cannot be auto-validated

The following require human visual review:

1. **Subtitle legibility on actual backgrounds**: The automated validation checks that subtitles exist with correct timing and no overlaps, but cannot assess whether the semi-transparent box or outline provides sufficient contrast against the specific image assets used in each scene. Screenshots at 20%/50%/80% of the video were generated for this purpose (`validation/screenshot-*.jpg`).

2. **Font rendering correctness**: ASS relies on the system's fontconfig for font fallback. The render used DejaVuSans-Bold as fallback for Arial Bold. A human must verify that accented characters (á, é, í, ó, ú, ü, ñ) render correctly in the final video.

3. **Line break quality**: The `wrap_line()` function splits at word boundaries at ~20 chars. A human should verify that semantic units are not broken awkwardly (e.g., "y\\Ncon ella un" in cue 1 is acceptable but suboptimal).

4. **Cue timing naturalness**: Cumulative offset ensures mathematical precision, but a human should verify that the 0.001-0.005s shifts per cue do not cause perceptible mistiming against the narration. Given the magnitude (≤5ms), this is unlikely to be noticeable.

5. **Audio quality**: The `audioValidationQuality` returned "REVIEW_REQUIRED" due to 4.74s of total silence (chapter breaks). This is expected by design but should be confirmed audibly.
