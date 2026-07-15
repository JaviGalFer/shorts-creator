---
name: video-rendering-ffmpeg
description: Diseñar y validar renders de vídeo vertical con FFmpeg
---

# Skill: video-rendering-ffmpeg

## Cuándo usarla
Para diseñar o validar un render de vídeo vertical con FFmpeg.

## Entradas
- Lista de imágenes de fondo (rutas, duración por escena).
- Archivo de audio (narración).
- Archivo de subtítulos (SRT).
- Dimensiones de salida (1080x1920 por defecto).

## Salidas
- Comando FFmpeg listo para ejecutar.
- Descripción del pipeline de filtros.

## Procedimiento
1. Construir filter_complex para overlay de imágenes secuenciales.
2. Añadir filtro de subtítulos (burn-in o metadata).
3. Mezclar audio con el vídeo.
4. Ajustar duración total.
5. Generar comando comprobable.

## Validaciones
- El comando se ejecuta sin errores (dry-run con -f null).
- La duración del vídeo coincide con la del audio.
- Los subtítulos son legibles y están sincronizados.

## Límites
- No renderizar vídeos reales sin aprobación (coste de tiempo/recursos).
- No asumir aceleración GPU disponible.
