# Runbook: Pipeline CLI (primario)

## Pipeline completo

```bash
# Cada vídeo vive en data/videos/{jobId}/
# 1. Generar guion
python3 bin/generate_script.py --topic "<tema>" --duration 30 --output data/videos/{jobId}/metadata.json

# 2. Descargar assets visuales
python3 bin/fetch_images_v2.py data/videos/{jobId}/metadata.json

# 3. Generar audio (Edge TTS)
python3 bin/generate_audio.py data/videos/{jobId}/metadata.json

# 4. Preparar subtítulos y timeline
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
  assets/
    seg_001.jpg
    ...
  scenes/
    narration.mp3
    ...
```

## Scripts disponibles

| Script | Función |
|--------|---------|
| `bin/generate_script.py` | Genera guion mediante LLM con plan visual V2 |
| `bin/fetch_images_v2.py` | Descarga assets visuales mediante el pipeline V2 y los proveedores configurados. |
| `bin/generate_audio.py` | Genera MP3 por escena vía Edge TTS |
| `bin/prepare_job.py` | Genera subtítulos ASS + consolida metadata |
| `bin/render_job.py` | Renderiza MP4 final con FFmpeg Docker |
| `bin/review_job.py` | Aprueba/rechaza vídeo renderizado |

## n8n workflows (legacy)

Los workflows n8n quedan como alternativa manual. Usan el formato plano antiguo:

- `generate-script-v1`: genera `data/metadata/{jobId}.json`
- `generate-audio-v1`: genera `data/audio/{jobId}-scene-XX.mp3`
- `fetch-assets-v1`: genera `data/assets/{jobId}-scene-XX.jpg`

## render-worker

```bash
curl -X POST http://localhost:8580/render -H 'Content-Type: application/json' -d '{"jobId":"..."}'
```
