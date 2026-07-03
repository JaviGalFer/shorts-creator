# Propuesta: Restructuración de directorios por vídeo

## Problema

Los datos de cada vídeo (assets, audio, subtítulos, render, metadata) están dispersos en directorios planos:

```
data/assets/    -> 80+ imágenes sin orden
data/audio/     -> 90+ audios sin orden
data/subtitles/ -> 12+ archivos
data/renders/   -> 10+ vídeos
data/metadata/  -> 15+ JSONs
```

Esto genera:
- Imposibilidad de limpiar/resetear un vídeo sin afectar otros
- Dificultad para saber qué archivos pertenecen a qué job
- Caos al escalar a decenas de vídeos

## Solución propuesta

Cada vídeo es un directorio autocontenido en `data/videos/{jobId}/`:

```
data/videos/{jobId}/
  video.mp4
  metadata.json
  subtitle.ass (o .srt)
  scenes/
    scene-01.jpg
    scene-01.mp3
    ...
```

## Criterios de éxito

1. `bin/generate_audio.py` escribe escenas en `videos/{jobId}/scenes/`
2. `bin/fetch_images.py` escribe imágenes en `videos/{jobId}/scenes/`
3. `bin/prepare_job.py` genera metadata y subtítulos en `videos/{jobId}/`
4. `bin/render_job.py` lee de `videos/{jobId}/` y escribe `video.mp4`
5. Los 4 scripts funcionan sin modificar el entorno
6. docs/ actualizados (architecture.md, current-state.md)
