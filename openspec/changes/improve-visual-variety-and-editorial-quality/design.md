# Design: Visual Variety & Editorial Quality

## 1. Editorial Roles

### 1.1 Contrato `editorialRole`

Cada escena debe tener un `editorialRole` en `visualPlan`:

| Role | Cuándo usarlo | assetType preferido | Prohibido |
|------|---------------|---------------------|-----------|
| `context_map` | El guion menciona geografía, territorio, fronteras | map, document | atmospheric_broll |
| `character_portrait` | El guion menciona una persona específica | portrait, historical_photograph | broll genérico |
| `military_technology` | El guion menciona armas, fortificaciones, barcos | historical_photograph, painting | generated_reconstruction |
| `civilian_impact` | El guion describe sufrimiento, vida cotidiana, refugiados | historical_photograph | atmospheric_broll |
| `battle_or_assault` | El guion describe combate, asedio, ataque | painting, historical_photograph | atmospheric_broll |
| `document_or_date` | El guion menciona un tratado, fecha, ley, carta | document, map | generated_reconstruction |
| `consequence_or_legacy` | El guion describe impacto histórico duradero | historical_photograph, painting | atmospheric_broll |
| `atmospheric_transition` | Escena puente sin contenido narrativo denso | atmospheric_broll | generated_reconstruction |

### 1.2 Límites

- `atmospheric_transition`: máximo **20% de escenas** por vídeo (2 en vídeo de 10-12 escenas).
- `generated_reconstruction`: no en escenas consecutivas, no si existe archivo histórico apropiado.
- `historical_archive`, `map_or_document`, `portrait` tienen prioridad si el guion menciona persona, fecha, ciudad, batalla, imperio o documento real.

## 2. Anti-repetición

### 2.1 Reglas obligatorias

1. **Mismo asset**: no puede usarse más de una vez por vídeo salvo `reuseAllowed=true` con `reuseReason` explícito.
2. **Mismo assetType**: no repetir en >2 escenas consecutivas.
3. **Mismo provider+author**: penalizar si aparece en escenas consecutivas.
4. **Misma query**: no usar misma `searchQuery` en dos segmentos distintos.

### 2.2 Penalizaciones en scoring

| Condición | Penalización |
|-----------|-------------|
| Mismo author+provider en escenas consecutivas | -40 |
| Misma query usada < 3 escenas antes | -30 |
| Mismo assetType que escena anterior | -20 |
| Mismo assetType que segmento anterior (misma escena) | -20 |
| Duplicate de URL ya descargada | -50 |

### 2.3 Metadata

```json
{
  "duplicateRisk": "none|low|medium|high",
  "previousSimilarAssets": ["scene-02-01.jpg"],
  "reuseAllowed": false,
  "reuseReason": ""
}
```

## 3. Tratamiento de mapas

### 3.1 Reglas de selección

- Rechazar mapas con width < 800 o height < 800 (ilegibles en 9:16).
- Preferir mapas con aspect ratio cercano a 9:16 o cuadrados.
- Si el mapa es horizontal (width > height), aplicar crop automático.

### 3.2 Tratamiento en render

Para `historical_map`, `map` horizontal:

1. Escalar imagen completa a 1080 de ancho (fondo).
2. Aplicar `gblur=40` al fondo.
3. Escalar manteniendo aspect ratio a altura máxima 1920, centrar.
4. Hacer `crop` a la región relevante (tercio central si no se especifica).
5. Reservar 15% inferior para subtítulos: overlay negro semitransparente.
6. Overlay opcional de fecha/lugar.

### 3.3 Metadata

```json
{
  "focalRegion": "center|north|south|east|west",
  "cropMode": "full_map|region_zoom|detail",
  "overlayText": "Constantinopla, 1453",
  "mapReadabilityScore": 0.8
}
```

## 4. Tratamiento de retratos

- Si un retrato se repite en dos segmentos, debe haber cambio visual: crop distinto, zoom a rostro, overlay de nombre/fecha, o transición a documento.
- No usar retrato como relleno atmosférico.
- Si `character_portrait` y no hay retrato real, preferir grabado/pintura antes que IA.

## 5. Reconstrucciones IA

### 5.1 Prompt obligatorio

```text
historically accurate, documentary reconstruction, no fantasy,
no video game art, no cinematic poster, no exaggerated armor,
no modern objects, no text, no watermark
```

### 5.2 Metadata

```json
{
  "visualAuthenticityRisk": "low|medium|high",
  "aiPromptUsed": "...",
  "aiNegativePrompt": "..."
}
```

### 5.3 Reglas

- `generated_reconstruction` solo cuando no exista archivo histórico apropiado.
- Si escena clave y sin archivo: preferir mezcla de grabado + mapa + documento antes que IA genérica.

## 6. Rotación de queries B-roll

### 6.1 Pool alternativo por strategy

Ampliar `STRATEGY_VISUAL_QUERIES` con pools más diversos:

```python
STRATEGY_VISUAL_QUERIES = {
    "atmospheric_broll": [
        "old ruins dramatic sky",
        "candlelight dark room",
        "ancient stone texture",
        "smoke fog atmosphere",
        "medieval castle storm",
        "ancient military camp",
        "old fortress walls",
        "historical siege scene",
        "battlefield mist morning",
        "medieval armor weapon display",
        "ancient city gate",
        "old harbor medieval",
        "cathedral interior dark",
    ],
    "historical_archive": [
        "old historical photograph",
        "vintage documentary photo",
        "archival historical image",
        "retro black and white scene",
        "historical event photography",
        "19th century engraving",
        "old military portrait",
        "vintage war photograph",
        "historical battle scene",
        "ancient manuscript illustration",
    ],
}
```

### 6.2 Author diversity

- Track authors usados por vídeo.
- Si un author ya apareció, penalizar en scoring.
- Forzar rotación de queries en escenas consecutivas.

## 7. Contratos de datos actualizados

### visualPlan (nuevos campos)

```json
{
  "editorialRole": "context_map",
  "visualSequence": [
    {
      "segmentIndex": 1,
      "assetType": "historical_map",
      "searchQuery": "...",
      "durationFraction": 0.6,
      "transition": "cut",
      "focalRegion": "center",
      "cropMode": "region_zoom",
      "overlayText": "Constantinopla",
      "editorialReason": "..."
    }
  ]
}
```

### assets[].segments[] (nuevos campos)

```json
{
  "duplicateRisk": "none",
  "previousSimilarAssets": [],
  "reuseAllowed": false,
  "reuseReason": "",
  "focalRegion": "center",
  "cropMode": "full_map",
  "overlayText": "",
  "mapReadabilityScore": null,
  "visualAuthenticityRisk": null,
  "authorDiversityScore": 1.0
}
```
