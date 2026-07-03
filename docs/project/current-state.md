# Estado actual

## Lo que ya funciona

- `n8n` local operativo en `http://localhost:5679`
- Scripts en `bin/` para pipeline completo:
  - `bin/generate_audio.py` — Edge TTS por escena
  - `bin/fetch_images.py` — descarga imágenes (Pollinations/FreeAI/Wikimedia)
  - `bin/prepare_job.py` — genera subtítulos (ASS/SRT) + consolida metadata
  - `bin/render_job.py` — render vertical MP4 con FFmpeg en Docker
- ASS subtitles con estilo profesional (fuente grande 65px, caja semitransparente)
- Render con `ass=` filter validado (libass 0.17.5)
- Script `review_job.py` para aprobar/rechazar videos desde terminal
- Servicio `render-worker` en docker-compose

## Estructura de datos

```
data/videos/{jobId}/
  video.mp4           <- Render final
  metadata.json       <- Job metadata
  subtitle.ass        <- Subtítulos
  scenes/
    scene-01.jpg      <- Imagen escena
    scene-01.mp3      <- Audio escena
    ...
```

## Pipeline completo (flujo actual)

```bash
python3 bin/generate_audio.py data/videos/{jobId}/metadata.json
python3 bin/fetch_images.py data/videos/{jobId}/metadata.json
python3 bin/prepare_job.py data/videos/{jobId}/metadata.json
python3 bin/render_job.py data/videos/{jobId}/metadata.json
```

## Limitaciones actuales

- Pollinations.ai rate-limited (429), imágenes de baja calidad
- Sin API key de Free.ai configurada (alternativa gratuita)
- Voz Edge TTS AlvaroNeural funcional pero usuario discrepa
- n8n workflows desconectados del pipeline CLI (usar Manual Trigger + JSON export)

## Próximos pasos

1. Registrar Free.ai para imágenes de calidad gratuitas
2. Validar pipeline completo con vídeo desde cero
