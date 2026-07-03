# Tareas: Restructuración de directorios por vídeo

## Documentación

- [ ] Crear openspec change (proposal, design, tasks)
- [ ] Crear sesión en docs/sessions/
- [ ] Actualizar docs/project/architecture.md
- [ ] Actualizar docs/project/current-state.md

## Scripts

- [ ] Crear bin/generate_audio.py (Edge TTS, rutas nuevas)
- [ ] Actualizar bin/fetch_images.py (rutas nuevas)
- [ ] Actualizar bin/prepare_job.py (rutas nuevas, metadata en video dir)
- [ ] Actualizar bin/render_job.py (rutas nuevas, ass filter)
- [ ] Actualizar render_server.py (SCRIPTS_DIR → bin/)

## Configuración

- [ ] Actualizar .env (nuevas rutas)
- [ ] Actualizar .gitignore (data/videos/)

## Validación

- [ ] generate_audio.py crea scenes/scene-*.mp3 correctamente
- [ ] fetch_images.py crea scenes/scene-*.jpg correctamente
- [ ] prepare_job.py genera subtitle.ass + metadata.json en video dir
- [ ] render_job.py produce video.mp4 válido
- [ ] Pipeline completo genera vídeo desde cero
