# Spec: Editorial Roles

## Propósito

Cada escena debe tener un propósito visual claro alineado con la narrativa. El `editorialRole` determina qué tipo de asset es aceptable y cuál debe ser penalizado o rechazado.

## Roles

| Role | assetType preferidos | assetType prohibidos | Cuándo |
|------|---------------------|----------------------|--------|
| `context_map` | map, document, historical_map | atmospheric_broll, generated_reconstruction | El guion menciona geografía, fronteras, territorios |
| `character_portrait` | portrait, historical_photograph, painting | atmospheric_broll, broll | El guion menciona persona específica |
| `military_technology` | historical_photograph, painting, document | generated_reconstruction | El guion menciona armas, barcos, fortificaciones |
| `civilian_impact` | historical_photograph, document | atmospheric_broll, generated_reconstruction | El guion describe sufrimiento, vida cotidiana |
| `battle_or_assault` | painting, historical_photograph | atmospheric_broll | El guion describe combate, asedio |
| `document_or_date` | document, map | generated_reconstruction | El guion menciona tratado, fecha, documento |
| `consequence_or_legacy` | historical_photograph, painting | atmospheric_broll | El guion describe impacto duradero |
| `atmospheric_transition` | atmospheric_broll | generated_reconstruction | Escena puente sin contenido denso |

## Límites cuantitativos

- `atmospheric_transition`: máximo 20% de escenas (2 en vídeo de 10)
- `generated_reconstruction`: no en escenas consecutivas
- `historical_archive` como strategy: mínimo 50% de escenas si el tema lo permite
- `map_or_document`: al menos 1 por vídeo si el guion menciona geografía o fechas

## Scoring por editorialRole

Si el assetType del candidato NO está en "preferidos" del rol:
- Penalización: -20 si el assetType está en "prohibidos"
- Penalización: -10 si el assetType no está ni en preferidos ni prohibidos

Si el assetType SÍ está en "preferidos":
- Bonificación: +15

## Implementación en fetch_images.py

```python
EDITORIAL_ROLE_PREFERENCES = {
    "context_map": {
        "preferred": {"map", "document", "historical_map"},
        "forbidden": {"atmospheric_broll", "generated_reconstruction"},
    },
    "character_portrait": {
        "preferred": {"portrait", "historical_photograph", "painting"},
        "forbidden": {"atmospheric_broll"},
    },
    # ... etc
}

def score_editorial_role(asset_type, editorial_role):
    prefs = EDITORIAL_ROLE_PREFERENCES.get(editorial_role, {})
    if asset_type in prefs.get("forbidden", set()):
        return -20
    if asset_type in prefs.get("preferred", set()):
        return 15
    return -10
```
