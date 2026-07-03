# Diseño: Restructuración de directorios por vídeo

## Nuevo layout

```
data/
  videos/
    {jobId}/
      video.mp4           <- Render final
      metadata.json       <- Job metadata (canónico)
      subtitle.ass        <- Subtítulos (ASS o SRT)
      scenes/
        scene-01.jpg      <- Imagen escena 1
        scene-01.mp3      <- Audio escena 1
        scene-02.jpg
        scene-02.mp3
        ...
```

Los directorios planos antiguos (`data/assets/`, `data/audio/`, etc.) se mantienen para jobs legacy pero no se usan para nuevos vídeos.

## Cambios en scripts

### `bin/generate_audio.py` (NUEVO)
```python
# Input:  metadata.json in videos/{jobId}/
# Output: scenes/scene-{N}.mp3 via Edge TTS
```

### `bin/fetch_images.py` (ACTUALIZADO)
```python
# Input:  metadata.json in videos/{jobId}/
# Output: scenes/scene-{N}.jpg
# Provider: pollinations | freeai | wikimedia
```

### `bin/prepare_job.py` (ACTUALIZADO)
```python
# Input:  metadata.json in videos/{jobId}/
# Output: scenes/ exist, subtitle.ass/srt generated
#         metadata.json updated in-place in videos/{jobId}/
```

### `bin/render_job.py` (ACTUALIZADO)
```python
# Input:  metadata.json in videos/{jobId}/
# Reads:  scenes/scene-{N}.jpg, scenes/scene-{N}.mp3, subtitle.ass
# Output: video.mp4
```

### `render_server.py` (ACTUALIZADO)
Actualizado para usar SCRIPTS_DIR = PROJECT_ROOT / 'bin'

## Flujo completo (nuevo)

```bash
# 1. Generar guion
python3 bin/generate_script.py data/videos/{jobId}/metadata.json

# 2. Generar audio
python3 bin/generate_audio.py data/videos/{jobId}/metadata.json

# 3. Descargar imágenes
python3 bin/fetch_images.py data/videos/{jobId}/metadata.json

# 4. Preparar subtítulos
python3 bin/prepare_job.py data/videos/{jobId}/metadata.json

# 5. Renderizar
python3 bin/render_job.py data/videos/{jobId}/metadata.json
```

## Migración

No se migran datos legacy. Los jobs existentes en el formato plano se dejan intactos. Nuevos jobs usarán el nuevo formato.
