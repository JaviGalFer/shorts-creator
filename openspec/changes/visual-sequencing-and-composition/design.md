# Design: Visual Sequencing

## Contrato de datos

### visualSequence (en visualPlan dentro de script.scenes[].visualPlan)

```json
"visualSequence": [
  {
    "segmentIndex": 1,
    "assetType": "historical_map|historical_photograph|portrait|document|generated_reconstruction|atmospheric_broll",
    "searchQuery": "query for image search",
    "durationFraction": 0.5,
    "transition": "cut|fade",
    "imageGenerationPrompt": "solo si assetType=generated_reconstruction",
    "negativePrompt": "solo si assetType=generated_reconstruction",
    "editorialReason": "por qué este asset aquí"
  }
]
```

- `durationFraction`: proporción de targetDurationSec para este segmento (suma = 1.0)
- `transition`: cómo se entra a este segmento desde el anterior. "cut" por defecto. "fade" para crossfade de 0.5s.
- `editorialReason`: texto que explica la elección editorial

### assets (en metadata.json)

```json
"assets": [
  {
    "sceneNumber": 1,
    "path": "scenes/scene-01-01.jpg",
    "segments": [
      {
        "segmentIndex": 1,
        "path": "scenes/scene-01-01.jpg",
        "assetType": "historical_map",
        "durationSec": 3.0,
        "transition": "cut",
        "provider": "wikimedia_commons",
        "sourceUrl": "...",
        "license": "CC BY-SA 3.0",
        "author": "...",
        "score": 40,
        "width": 3200,
        "height": 2888,
        "editorialReason": "Mapa del asedio de Constantinopla"
      },
      {
        "segmentIndex": 2,
        "path": "scenes/scene-01-02.jpg",
        "assetType": "atmospheric_broll",
        "durationSec": 3.0,
        "transition": "fade",
        "provider": "pexels",
        "sourceUrl": "...",
        "license": "Pexels License",
        "author": "...",
        "score": 35,
        "width": 4000,
        "height": 6000,
        "editorialReason": "Ambiente de tensión previa al asalto"
      }
    ]
  }
]
```

### timeline (generado por prepare_job.py, consumido por render_job.py)

```json
"timeline": [
  {
    "index": 1,
    "sceneNumber": 1,
    "segmentIndex": 1,
    "imagePath": "scenes/scene-01-01.jpg",
    "audioPath": "scenes/scene-01.mp3",
    "startSec": 0.0,
    "durationSec": 3.0,
    "transition": "cut",
    "assetType": "historical_map"
  },
  {
    "index": 2,
    "sceneNumber": 1,
    "segmentIndex": 2,
    "imagePath": "scenes/scene-01-02.jpg",
    "audioPath": "scenes/scene-01.mp3",
    "startSec": 3.0,
    "durationSec": 3.0,
    "transition": "fade",
    "assetType": "atmospheric_broll"
  }
]
```

## Tratamiento por assetType

| assetType | Tratamiento visual (render) |
|-----------|---------------------------|
| historical_map | Escalar manteniendo aspecto, centrar, fondo borroso derivado del mapa |
| historical_photograph | Escalar a 1080x1920 crop centro |
| portrait | Escalar a 1080x1920 crop centro, puede permitir crop superior |
| document | Escalar manteniendo aspecto, centrar, fondo gris claro |
| generated_reconstruction | Escalar a 1080x1920 crop centro, reducir saturación 10% |
| atmospheric_broll | Escalar a 1080x1920 crop centro |

## Transiciones

- `cut`: concat directo entre segmentos
- `fade`: xfade crossfade 0.5s (la duración del segmento se reduce 0.25s al inicio para solapamiento)

## Reglas de secuenciación

1. Escenas de 4-7s: 2 segmentos recomendados
2. Escenas de 8+s: 2-3 segmentos
3. No repetir assetType en segmentos consecutivos de la misma escena
4. No repetir assetType principal en escenas consecutivas sin justificación
5. generated_reconstruction: máximo 1 por escena, no repetir en escenas consecutivas
6. historical_map: primer segmento ideal para contexto espacial
