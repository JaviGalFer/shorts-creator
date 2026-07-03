# Spec: Narrative Beats

## Contrato

Cada escena puede tener `narrativeBeats[]` en el script.

```json
{
  "narrativeBeats": [
    {
      "beatIndex": 1,
      "text": "Mehmed II reunió un ejército enorme",
      "startCueIndex": 0,
      "endCueIndex": 1,
      "visualIntent": "character_and_army",
      "preferredAssetType": "portrait_or_historical_art"
    }
  ]
}
```

## Reglas de segmentación

| Duración | Beats mínimos |
|----------|--------------|
| ≤4s | 1 (opcional) |
| 5-7s | 2 |
| ≥8s | 2-3 |

## Visual Intent

| intent | assetType recomendado |
|--------|----------------------|
| character_and_army | portrait, painting, historical_photograph |
| siege_technology | historical_photograph, document |
| city_view | historical_photograph, map |
| battle_action | painting, historical_photograph, broll |
| document_evidence | document, map |
| consequence | historical_photograph, atmospheric_broll |
| context_map | map, historical_map |
| portrait_focus | portrait, painting |

## Generación por LLM

El system prompt en generate_script.py debe pedir narrativeBeats con:
- Segmentación según duración (reglas arriba).
- Cada beat apunta a cues de subtitleTiming por startCueIndex/endCueIndex.
- visualIntent alineado con el contenido del beat.
- No crear beats arbitrarios sin cambio semántico en el texto.
