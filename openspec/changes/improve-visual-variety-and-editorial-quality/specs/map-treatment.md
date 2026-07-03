# Spec: Map Treatment in Render

## Filtros de selección

- Rechazar si width < 800 o height < 800 (mapReadabilityScore < 0.4)
- mapReadabilityScore = min(width/1080, height/1920) * (1 - abs(aspect_ratio - 9/16))
- Preferir cropMode="region_zoom" si el mapa es horizontal (width > height)

## Tratamiento en filter graph

Para assetType in ("historical_map", "map", "document") y landscape:

```
[input]split[bg][fg]

[bg]scale=1080:1920:force_original_aspect_ratio=fill,
     gblur=sigma=40,
     format=yuv420p[bg_blurred]

[fg]scale=1080:1920:force_original_aspect_ratio=increase,
     setsar=1,
     format=yuv420p[fg_scaled]

[dependiendo de focalRegion]:
  center:  crop=1080:1920 (desde el centro de fg_scaled)
  north:   crop=1080:1920 (desde la parte superior)
  south:   crop=1080:1920 (desde la parte inferior)
  east:    crop=1080:1920 (desde la derecha)
  west:    crop=1080:1920 (desde la izquierda)

[fg_cropped]format=rgba,
             drawbox=x=0:y=1632:w=1080:h=288:color=black@0.6:fill=black@0.6,
             format=yuv420p[fg_boxed]

[bg_blurred][fg_boxed]overlay=(W-w)/2:(H-h)/2[map_output]
```

## Overlay de fecha/lugar

- Posición: esquina superior izquierda, margen 40px
- Fuente: predeterminada, color blanco, sombra negra
- Usar drawtext si FFmpeg tiene libfontconfig
- Si no: omitir overlay (no crítico)

## Fallback para no-landscape

Si el mapa es vertical o cuadrado:
- Escalar manteniendo aspect ratio, crop centro 1080x1920
- No aplicar blur background
- Aplicar subtitle box igualmente

## Metadata

```json
{
    "focalRegion": "center|north|south|east|west",
    "cropMode": "full_map|region_zoom|detail",
    "overlayText": "string (fecha/lugar)",
    "mapReadabilityScore": 0.0-1.0
}
```
