# Estrategia visual de assets

## Estrategias soportadas

### `historical_archive`
Fotografías históricas reales, retratos, pinturas, grabados, manuscritos, monumentos de la época.

Fuentes: Wikimedia Commons → Library of Congress → Openverse → (generated_reconstruction si permitido)

### `map_or_document`
Mapas históricos, carteles propagandísticos, portadas de periódicos, tratados, cartas, documentos oficiales.

Fuentes: Wikimedia Commons → Library of Congress → Openverse → (generated_reconstruction si permitido)

### `atmospheric_broll`
Transiciones, contexto emocional, escenas abstractas (fuego, humo, lluvia, ruinas, mapas sobre mesa).

Fuentes: Pexels → Pixabay → FreeAI → Pollinations

### `generated_reconstruction`
Reconstrucciones de ciudades desaparecidas, escenarios sin archivo disponible, planos atmosféricos.

Fuentes: FreeAI → Pollinations → visualPrompt fallback

## Cadena de fallback

```
Para cada escena:
  1. Si visualPlan existe:
     a. historical_archive → Wikimedia → LoC → Openverse → Pexels → (IA si allowGeneratedImage)
     b. map_or_document → Wikimedia → LoC → Openverse → (IA si allowGeneratedImage)
     c. atmospheric_broll → Pexels → Pixabay → FreeAI → Pollinations
     d. generated_reconstruction → FreeAI → Pollinations
  2. Fallback final: visualPrompt legacy
```

## Proveedores

| Proveedor | Tipo | API Key | Límites | Atribución |
|-----------|------|---------|---------|------------|
| Wikimedia Commons | Archivo histórico | No | Rate limit (429) | Variable por imagen |
| Pexels | Stock photography | Sí (gratis) | 200 req/hora gratis | No requerida |
| Pixabay | Stock photography | Sí (gratis) | 5000 req/hora gratis | No requerida |
| FreeAI | IA generativa (FLUX) | Sí (gratis) | 30K tokens/día | No requerida |
| Pollinations | IA generativa | No | 1 req/sec | No requerida |

## Scoring

```python
SCORING_WEIGHTS = {
    "entity_match": 30,
    "period_or_location_match": 20,
    "asset_type_match": 15,
    "sufficient_resolution": 15,
    "clear_license": 10,
    "preferred_source": 10,
    "modern_or_irrelevant": -30,
    "duplicate_entity": -30,
    "unknown_license": -40,
    "low_resolution": -50,
}
```

## Licencias

Preferencia por: Public Domain, CC0, CC-BY, CC-BY-SA.
Evitar: "All Rights Reserved", licencia desconocida.
Wikimedia Commons incluye metadata de licencia en la API.

## Formato de assets

```json
{
  "sceneNumber": 1,
  "selected": true,
  "path": "scenes/scene-01.jpg",
  "provider": "wikimedia_commons",
  "strategy": "historical_archive",
  "assetType": "historical_photograph",
  "sourceUrl": "...",
  "title": "...",
  "author": "...",
  "license": "Public Domain",
  "attributionRequired": false,
  "queryUsed": "...",
  "width": 2000,
  "height": 1400,
  "score": 82,
  "scoreReasons": ["Entity match: Spanish Civil War"],
  "downloadedAt": "ISO_DATE",
  "discardedCandidates": [
    {
      "provider": "wikimedia_commons",
      "sourceUrl": "...",
      "score": 45,
      "discardReason": "Baja resolución",
      "license": "CC-BY-SA"
    }
  ]
}
```
