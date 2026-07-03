# Spec: Subtitle Timing from edge-tts

## Captura de WordBoundary events

```python
import edge_tts

async def generate_audio_with_timestamps(text, voice, output_path):
    communicate = edge_tts.Communicate(text, voice)
    submaker = edge_tts.SubMaker()
    
    with open(output_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)
    
    # Access cues from SubMaker internal API
    cues = []
    for start, end, word in submaker._subs:
        cues.append({"startSec": start, "endSec": end, "text": word})
    
    # Group words into semantic phrases (2-6 words)
    return group_cues(cues)
```

## Agrupación de cues

- Palabras individuales se agrupan en frases de 2-6 palabras.
- Se respeta puntuación: punto, coma, interrogación → fin de grupo.
- Cada grupo mantiene startSec de primera palabra y endSec de última.
- Timestamp confidence: "high" si source=edge_tts_word_boundary.

## Formato de salida

```json
{
  "subtitleTiming": {
    "timingSource": "edge_tts_word_boundary",
    "timingConfidence": "high",
    "cues": [
      {"startSec": 0.0, "endSec": 1.8, "text": "En 1453, Constantinopla"}
    ]
  }
}
```

## Fallback

Si edge_tts no produce WordBoundary events o el audio ya existe:

```json
{
  "subtitleTiming": {
    "timingSource": "estimated",
    "timingConfidence": "low",
    "cues": [...]
  }
}
```

Cálculo: duración_total / num_palabras * índice_palabra para cada palabra, luego agrupación igual.
