# Spec: Motion Filters for FFmpeg

## Tipos de movimiento

### slow_zoom_in

```filter
zoompan=z='if(lte(on,1),1,min(1.15,zoom+0.002))':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920
```

Efecto: zoom de 1.0 a 1.15 sobre N segundos (N = duración). Centrado.

### slow_zoom_out

```filter
zoompan=z='if(lte(on,1),1.15,max(1.0,zoom-0.002))':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920
```

Efecto: zoom de 1.15 a 1.0 sobre N segundos.

### pan_left

```filter
crop=1080:1920:'floor((iw-1080)*(1-t/T))':0,scale=1080:1920:force_original_aspect_ratio=increase
```

Efecto: paneo horizontal de derecha a izquierda. T = duración total.

### pan_right

```filter
crop=1080:1920:'floor((iw-1080)*t/T)':0,scale=1080:1920:force_original_aspect_ratio=increase
```

Efecto: paneo horizontal de izquierda a derecha.

### pan_up

```filter
crop=1080:1920:0:'floor((ih-1920)*(1-t/T))',scale=1080:1920:force_original_aspect_ratio=increase
```

Efecto: paneo vertical de abajo arriba.

### pan_down

```filter
crop=1080:1920:0:'floor((ih-1920)*t/T)',scale=1080:1920:force_original_aspect_ratio=increase
```

Efecto: paneo vertical de arriba abajo.

### static

```filter
scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920
```

Sin movimiento.

### detail_crop

```filter
scale=2000:3556:force_original_aspect_ratio=increase,crop=1080:1920,scale=1080:1920
```

Crop a detalle ampliado.

## Reglas de renderizado

- El motion filter se aplica DESPUÉS del tratamiento por assetType.
- zoompan reemplaza scale+crop porque zoompan escala internamente.
- Para pan, usar crop sobre imagen ya escalada.
- Si el motionType no es soportado o está ausente, usar static.
- zoompan requiere que la imagen de entrada sea >= resolución de salida.
- Si la imagen es más pequeña que 1080x1920, zoompan puede dar artifacts.
