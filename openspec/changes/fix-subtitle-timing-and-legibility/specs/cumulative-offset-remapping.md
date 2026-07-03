# Spec: Cumulative Offset Cue Remapping

## Algorithm

For each chapter_break silence:
- removed_duration = original_duration - TARGET_duration (0.35s)

For each cue:
```
offset = sum(removed_duration for all chapter_breaks where cb.endSec <= cue.startSec)
adjusted_start = round(cue.startSec - offset, 3)
adjusted_end   = round(cue.endSec - offset, 3)
```

## Cross-trim handling

If any cue falls across a chapter_break boundary (startSec < cb.startSec < endSec):
- Keep as-is with cumulative offset applied to both start and end
- Mark crossesTrim: true
- Flag for human review

## Edge cases

- Cue ends exactly at chapter_break start: treated as before, full offset applied
- Cue starts exactly at chapter_break end: treated as after, no offset for this break
- Zero-duration chapter_break (removed=0): no offset contribution
