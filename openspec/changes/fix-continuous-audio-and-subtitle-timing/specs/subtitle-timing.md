# Spec: Subtitle Timing from Real Audio

## Principios

1. Los subtítulos reflejan EXACTAMENTE el texto narrado.
2. No hay frases editoriales, resúmenes ni división por duración uniforme.
3. Timing derivado de WordBoundary → SentenceBoundary → estimación proporcional.
4. Los timings son ABSOLUTOS (no relativos por escena).

## WordBoundary → Cues

```python
def group_words_into_cues(words: list) -> list:
    cues = []
    buffer = []
    buffer_start = None

    def flush():
        nonlocal buffer, buffer_start
        if not buffer:
            return
        text = " ".join(w["text"] for w in buffer)
        text = re.sub(r'\s+([,.!?;:])', r'\1', text)
        text = text.strip()
        if not text:
            return
        cues.append({
            "startSec": round(buffer_start, 3),
            "endSec": round(buffer[-1]["endSec"], 3),
            "text": text,
        })
        buffer = []
        buffer_start = None

    for w in words:
        text = w["text"].strip()
        if not text:
            continue
        if buffer_start is None:
            buffer_start = w["startSec"]
        buffer.append(w)

        is_end_of_sentence = text[-1] in ".!?"
        is_pause = w["startSec"] - buffer[-2]["endSec"] > 0.5 if len(buffer) >= 2 else False
        is_long = len(buffer) >= 6
        is_medium_with_punct = len(buffer) >= 4 and text[-1] in ",;:"

        if is_end_of_sentence or is_pause or is_long or is_medium_with_punct:
            flush()

    flush()
    return cues
```

## Reglas de cue

| Regla | Valor |
|-------|-------|
| Duración mínima | 0.7s |
| Duración máxima | 2.5s |
| Texto vacío | Prohibido |
| Salto visual sin texto | Prohibido |
| División | Por puntuación y grupos semánticos |

## SentenceBoundary fallback

```python
def sentence_boundary_to_cues(sentences: list, full_text: str) -> list:
    """Distribuir palabras proporcionalmente dentro de cada sentence boundary."""
    all_words = []
    for sb in sentences:
        words = sb["text"].split()
        dur = sb["duration"] / 10000000  # ticks 100ns → segundos
        start = sb["offset"] / 10000000
        word_dur = dur / len(words) if words else 0
        for i, w in enumerate(words):
            all_words.append({
                "startSec": start + i * word_dur,
                "endSec": start + (i + 1) * word_dur,
                "text": w,
            })
    return group_words_into_cues(all_words)
```

## Verificación

- El texto concatenado de todos los cues DEBE ser igual al texto narrado original.
- Diferencia permitida: solo espacios y puntuación normalizada.
