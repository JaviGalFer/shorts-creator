# Diseño: Mejora del pipeline visual histórico

## Contrato visualPlan (nuevo)

```json
{
  "visualPlan": {
    "strategy": "historical_archive",
    "primaryAssetType": "historical_photograph",
    "secondaryAssetType": "map",
    "period": "Spanish Civil War, 1936",
    "location": "Spain",
    "entities": ["Spanish Civil War"],
    "searchQueries": ["Spanish Civil War 1936 photograph"],
    "imageGenerationPrompt": "...",
    "negativePrompt": "...",
    "style": "historical documentary",
    "mood": "tense and somber",
    "preferredSources": ["wikimedia_commons"],
    "allowGeneratedImage": true,
    "licenseRequired": "public_domain_or_cc",
    "visualImportance": "high"
  }
}
```

## Estrategias visuales

| Estrategia | Fuentes prioridad | Fallback |
|------------|-------------------|----------|
| `historical_archive` | Wikimedia → LoC → Openverse → Pexels → generado IA | visualPrompt |
| `map_or_document` | Wikimedia → LoC → Openverse | generado IA si permitido |
| `atmospheric_broll` | Pexels → Pixabay → FreeAI → Pollinations | visualPrompt |
| `generated_reconstruction` | FreeAI → proveedor IA existente → Pollinations | visualPrompt |

## Sistema de scoring

Pesos centralizados:

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

## Metadata de assets

```json
{
  "sceneNumber": 1,
  "selected": true,
  "path": "scenes/scene-01.jpg",
  "provider": "wikimedia_commons",
  "strategy": "historical_archive",
  "assetType": "historical_photograph",
  "sourceUrl": "https://...",
  "title": "...",
  "author": "Unknown",
  "license": "Public Domain",
  "attributionRequired": false,
  "queryUsed": "...",
  "width": 2000,
  "height": 1400,
  "score": 82,
  "scoreReasons": ["Entity match: Spanish Civil War", "..."],
  "downloadedAt": "ISO_DATE"
}
```

## Flujo actualizado de fetch_images.py

```
Por cada escena:
  1. Leer visualPlan (o fallback a visualPrompt)
  2. Determinar estrategia y proveedores
  3. Para cada proveedor:
     a. Ejecutar queries de búsqueda
     b. Obtener lista de candidatas (3-5)
     c. Evaluar cada candidata con scoring
  4. Ordenar todas las candidatas por score
  5. Seleccionar la mejor como primary
  6. Descargar primary
  7. Guardar metadata de todas las candidatas
  8. Si nada funciona: fallback a visualPrompt legacy
```

## Script bin/generate_script.py

```bash
python3 bin/generate_script.py --topic "La caída de Constantinopla" [--dry-run]
```

- Lee .env (LLM_API_KEY, LLM_PROVIDER, LLM_MODEL)
- Construye system prompt con instrucciones para visualPlan
- Llama a la API de OpenAI
- Genera metadata.json completo en data/videos/{jobId}/
- --dry-run imprime el prompt sin llamar a la API
