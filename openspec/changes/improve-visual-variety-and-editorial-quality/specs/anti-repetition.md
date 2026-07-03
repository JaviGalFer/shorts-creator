# Spec: Anti-Repetition System

## Reglas obligatorias

1. Un asset (URL) no puede aparecer más de una vez en el mismo vídeo.
2. Un mismo author+provider no puede aparecer en escenas consecutivas si existen alternativas.
3. Una misma searchQuery no puede usarse en dos segmentos distintos.
4. Un mismo assetType no puede repetirse en >2 escenas consecutivas.
5. generated_reconstruction no puede aparecer en escenas consecutivas.

## Penalizaciones en scoring

| Condición | Penalización |
|-----------|-------------|
| Misma URL ya descargada en otra escena | -50, `duplicateRisk=high` |
| Mismo author+provider que escena anterior | -40, `duplicateRisk=medium` |
| Misma query que segmento anterior (<3 escenas) | -30, `duplicateRisk=medium` |
| Mismo assetType que escena anterior | -20, `duplicateRisk=low` |
| Mismo assetType que segmento anterior | -20, `duplicateRisk=low` |

## Metadata por segmento

```python
{
    "duplicateRisk": "none|low|medium|high",
    "previousSimilarAssets": ["path/to/asset.jpg"],
    "reuseAllowed": False,
    "reuseReason": "",
}
```

## Pool de contexto

- `used_urls`: set de URLs ya descargadas en el vídeo
- `used_authors`: dict {author: set(escenas)} — para detectar repetición consecutiva
- `used_queries`: list de queries usadas (con escena) para proximity check
- `used_asset_types`: list de assetTypes por escena para racha check
- `used_entities`: set de entidades históricas ya cubiertas

## Consideraciones

- La primera escena no tiene penalización histórica.
- Si `reuseAllowed=True` debe tener `reuseReason` obligatorio.
- duplicateRisk se usa en el informe final para justificar cada asset.
