# Troubleshooting de render

## FFmpeg no encontrado

```bash
# Instalar en Ubuntu/Debian
sudo apt install ffmpeg

# Usar contenedor Docker
docker run --rm -v $(pwd):/data linuxserver/ffmpeg -i /data/input.mp4 ...
```

## Render lento

- FFmpeg por defecto usa CPU. Para aceleración hardware en WSL2:
  - Instalar drivers NVIDIA dentro de WSL2
  - Usar `-hwaccel cuda -c:v h264_nvenc`
- Reducir resolución o FPS si es necesario.

## Error de sincronización audio-subtítulos

- Verificar que el SRT usa timestamps correctos (formato `HH:MM:SS,mmm`).
- Si el audio se genera más corto de lo esperado, ajustar la velocidad de narración en ElevenLabs.

## Sin conexión a APIs externas

- Verificar `.env` con claves correctas.
- Verificar conectividad: `curl -I https://api.elevenlabs.io`
- El pipeline falla con estado `FAILED` y log visible en n8n.

## Zoompan produce vídeo demasiado largo (multiplicación de frames)

**Problema:** `zoompan d=N` procesa N frames POR CADA frame de entrada. Con `-loop 1 -t 5` generando 125 frames de entrada y `d=125`, la salida es 125×125 = 15625 frames.

**Solución:**
- Usar `-loop 1` sin `-t` para inputs de imagen (stream infinito de 1 frame).
- Antes de zoompan, aplicar `trim=end_frame=1` para asegurar exactamente 1 frame de entrada.
- `d=round(durationSec * FPS)` produce exactamente N frames de salida.
- Para no-zoompan: `trim=duration=X` en lugar de depender de duración de entrada.

## Validación post-render: ffprobe no soporta -show_entries

El Docker `linuxserver/ffmpeg:latest` compila ffprobe SIN soporte para `-show_entries`, `-print_format`, o `-show_format`.

**Solución:** Usar `ffmpeg -i archivo.mp4 2>&1 | grep Duration` y parsear el formato `HH:MM:SS.msec`.

## Pan filters fallan con "Invalid size" en imágenes pequeñas

**Problema:** `crop=1080:1920:expr:0` falla si la imagen fuente mide menos de 1920px de alto (por ejemplo, landscape 1920x1080).

**Solución:** Aplicar `scale=1080:1920:force_original_aspect_ratio=increase` ANTES del crop animado, no después.

## Preflight validation: total timeline vs expected total mismatch

**Problema:** La duración del renderTimeline (basada en cues de subtítulos reales) puede diferir de la suma de `targetDurationSec` de las escenas (planificación del script).

**Solución:** Tolerancia de 3.0s entre timeline total y expected total. La validación por escena contra duración de audio es más precisa.

## Asset validation: placeholder o imagen inválida en render final

**Problema:** El render contiene placeholders, imágenes modernas irrelevantes o assets sin metadata, pero las validaciones técnicas (duración, black/freeze frames) pasan.

**Solución:** Implementar `validate_job_for_render(metadata)` antes del render. Verifica:
- Archivo existe, es decodificable, tiene dimensiones mínimas
- No contiene texto de depuración (heuristic sobre metadata y filename)
- Tiene provider, query, score registrados
- assetType es compatible con editorialRole
- period/location/entities son coherentes con el tema histórico
- Provider está en lista permitida (Pollinations → flagged)

Si falla → status=ASSET_FAILED, no se renderiza.

## Estado ASSET_FAILED: qué hacer

1. Revisar `assetValidation.failures` en metadata.json para ver qué segmentos fallaron.
2. Ejecutar `fetch_images` de nuevo con queries mejoradas o providers alternativos.
3. Si el fallo es por provider, revisar `.env` para APIs keys.
4. Si el fallo es por placeholder, el asset no se descargó → revisar conectividad o cambiar search query.
5. Si el fallo es editorial, revisar `visualPlan.period` / `entities` / `editorialRole` en el script.
6. Volver a ejecutar `prepare_job` y luego `render_job`.
