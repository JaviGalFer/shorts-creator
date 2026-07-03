# Sesión: Restructuración de directorios + ASS fix + subtítulos grandes

- Fecha: 2026-07-01 (Europe/Madrid)
- Objetivo: Organizar data/ por vídeo, arreglar render ASS, mejorar subtítulos
- Estado inicial: data/ plana, ASS subtitles rotos, subtítulos pequeños
- Estado final: data/videos/{jobId}/ autocontenido, ASS funcional, subtítulos grandes
- Agente responsable: opencode
- Cambio OpenSpec relacionado: `restructure-video-directories`

## Cambios realizados

### ASS subtitle render fix
- `scripts/render_job.py` hardcodeaba `.srt` y filter `subtitles=`
- Creados `bin/prepare_job.py` y `bin/render_job.py` con soporte ASS (`ass=` filter)
- Render `franco6` validado: 53s, ASS subtitles, 10 escenas

### Subtítulos más grandes
- FontSize: 38 → 65
- BorderStyle: 1 → 3 (caja semitransparente)
- BackColour: 50% → 63% opaco
- MarginV: 140 → 40
- Wrapping: 25 → 18 chars/line

### Imágenes
- Creado `bin/fetch_images.py` con multi-proveedor (pollinations, freeai, wikimedia)
- Pollinations rate-limited (429), requiere alternativa (Free.ai)

### Restructuración directorios
- Nuevo layout: `data/videos/{jobId}/{video.mp4, metadata.json, subtitle.ass, scenes/}`
- Scripts actualizados para rutas nuevas
- Openspec change creado

## Archivos modificados/creados

- `bin/prepare_job.py` (creado, ASS support + nuevas rutas)
- `bin/render_job.py` (creado, ASS filter + nuevas rutas)
- `bin/fetch_images.py` (creado, multi-provider)
- `bin/generate_audio.py` (creado, Edge TTS)
- `render_server.py` (modificado, apunta a bin/)
- `openspec/changes/restructure-video-directories/` (creado)
- `.env` (actualizado rutas)

## Próximos pasos

1. Validar pipeline completo con vídeo nuevo
2. Mejorar imágenes (registrar en Free.ai o FreeTheAi)
3. Conectar workflows n8n al pipeline CLI
