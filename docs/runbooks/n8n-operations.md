# Runbook: Pipeline CLI (primario)

## Pipeline completo

```bash
# Cada vídeo vive en data/videos/{jobId}/
# 1. Generar guion (LLM)
python3 bin/generate_script.py data/videos/{jobId}/metadata.json

# 2. Generar audio (Edge TTS)
python3 bin/generate_audio.py data/videos/{jobId}/metadata.json

# 3. Descargar imágenes
python3 bin/fetch_images.py data/videos/{jobId}/metadata.json --provider pollinations

# 4. Preparar subtítulos
python3 bin/prepare_job.py data/videos/{jobId}/metadata.json

# 5. Renderizar vídeo
python3 bin/render_job.py data/videos/{jobId}/metadata.json
```

## Estructura de datos

```
data/videos/{jobId}/
  video.mp4           <- Render final
  metadata.json       <- Job metadata
  subtitle.ass        <- Subtítulos (ASS o SRT)
  scenes/
    scene-01.jpg      <- Imagen escena
    scene-01.mp3      <- Audio escena
    ...
```

## Scripts disponibles

| Script | Función |
|--------|---------|
| `bin/generate_audio.py` | Genera MP3 por escena vía Edge TTS |
| `bin/fetch_images.py` | Descarga imágenes (Pollinations/FreeAI/Wikimedia) |
| `bin/prepare_job.py` | Genera subtítulos ASS + consolida metadata |
| `bin/render_job.py` | Renderiza MP4 final con FFmpeg Docker |
| `review_job.py` | Aprueba/rechaza vídeo renderizado |

## n8n workflows (legacy)

Los workflows n8n quedan como alternativa manual. Usan el formato plano antiguo:

- `generate-script-v1`: genera `data/metadata/{jobId}.json`
- `generate-audio-v1`: genera `data/audio/{jobId}-scene-XX.mp3`
- `fetch-assets-v1`: genera `data/assets/{jobId}-scene-XX.jpg`

## render-worker

```bash
curl -X POST http://localhost:8580/render -H 'Content-Type: application/json' -d '{"jobId":"..."}'
```
