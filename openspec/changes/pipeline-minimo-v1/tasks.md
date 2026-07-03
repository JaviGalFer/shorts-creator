# Tareas: Pipeline mínimo v1

## Workflow 1 — Guion

- [x] Verificar API key LLM disponible en `.env`
- [x] Crear workflow n8n de generación de guion (`generate-script-v1`) con `Manual Trigger -> Code -> HTTP Request -> Code -> Convert to File -> Write Binary File`
- [x] Probar con tema real y guardar metadata JSON en `data/metadata/`
- [x] Documentar estructura del workflow en `docs/runbooks/n8n-operations.md`

## Workflow 2 — Audio + Imágenes

- [x] Verificar API key ElevenLabs disponible en `.env`
- [x] Verificar API key Pexels disponible en `.env`
- [x] Crear workflow `generate-audio-v1`: metadata -> escenas -> ElevenLabs TTS -> guardar audio
- [x] Crear workflow `fetch-assets-v1`: metadata -> escenas -> Pexels search -> descarga de imagen
- [x] Probar generación de audio + descarga de imágenes

## Pipeline FFmpeg

- [x] Verificar estrategia FFmpeg disponible (host ausente, Docker funcional)
- [x] Crear scripts `scripts/prepare_job.py` y `scripts/render_job.py`
- [x] Probar consolidación metadata + SRT con job real
- [x] Probar render vertical MP4 con FFmpeg en Docker
- [x] Integrar ejecución de render dentro de n8n vía render-worker HTTP API

## Validación final

- [x] Pipeline completo genera MP4 válido
- [x] Metadata JSON se guarda correctamente
- [x] Revisión humana posible antes de publicación vía `review_job.py`
- [x] Documentación actualizada
