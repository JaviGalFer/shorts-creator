# Visual Sequence Specification

## Resumen

Cada escena puede tener una secuencia de 1-3 segmentos visuales. Cada segmento tiene su propio asset, duración, transición y tratamiento.

## Contrato

### En script.scenes[].visualPlan.visualSequence[]

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| segmentIndex | int | sí | 1-based, orden en la escena |
| assetType | enum | sí | historical_map, historical_photograph, portrait, document, generated_reconstruction, atmospheric_broll |
| searchQuery | string | sí | Query para buscar imagen |
| durationFraction | float | sí | Proporción de targetDurationSec (suma = 1.0) |
| transition | enum | sí | "cut" o "fade" |
| imageGenerationPrompt | string | solo generated_reconstruction | Prompt para IA |
| negativePrompt | string | opcional | Lo que evitar en IA |
| editorialReason | string | sí | Explica la elección editorial |

### En metadata.json assets[].segments[]

| Campo | Tipo | Descripción |
|-------|------|-------------|
| segmentIndex | int | 1-based |
| path | string | Ruta al archivo descargado |
| assetType | string | Tipo de asset |
| durationSec | float | Duración en segundos |
| transition | string | "cut" o "fade" |
| provider | string | Proveedor |
| sourceUrl | string | URL original |
| license | string | Licencia |
| author | string | Autor |
| score | int | Puntuación |
| editorialReason | string | Razón editorial |
| width, height | int | Dimensiones |

### En metadata.json timeline[]

| Campo | Tipo | Descripción |
|-------|------|-------------|
| index | int | 1-based, orden global |
| sceneNumber | int | Escena a la que pertenece |
| segmentIndex | int | Segmento dentro de la escena |
| imagePath | string | Ruta a la imagen |
| audioPath | string | Ruta al audio (compartido por escena) |
| startSec | float | Tiempo absoluto de inicio |
| durationSec | float | Duración |
| transition | string | "cut" o "fade" |
| assetType | string | Tipo de asset |

## Reglas

1. Escenas ≤4s: 1 segmento (sin división)
2. Escenas 5-7s: 2 segmentos recomendados
3. Escenas ≥8s: 2-3 segmentos
4. No repetir assetType en segmentos consecutivos intra-escena
5. No repetir assetType dominante entre escenas consecutivas
6. generated_reconstruction: máx 1 por escena, no repetir
7. historical_map: ideal como segmento inicial para establecer contexto
