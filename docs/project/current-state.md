# Estado actual del proyecto

**Última actualización:** 2026-07-05

## Estado global

Pipeline funcional de vídeos cortos verticales históricos (9:16, ~1 min). Scripts en `bin/` operativos. n8n como orquestador legacy. Docker para render.

**Cambio OpenSpec activo:** `improve-historical-visual-pipeline` (mejora de pipeline visual histórico)

## Arquitectura del pipeline

```
generate_audio → fetch_images → prepare_job → render_job → review_job
```

### Scripts del pipeline

| Script | Responsabilidad |
|--------|----------------|
| `bin/generate_audio.py` | Edge TTS por escena, genera MP3 |
| `bin/fetch_images.py` | Descarga imágenes (Pollinations/FreeAI/Wikimedia) |
| `bin/prepare_job.py` | Subtítulos ASS/SRT + consolida metadata |
| `bin/render_job.py` | Render MP4 vertical con FFmpeg en Docker |

### Servicios Docker

| Servicio | Puerto | Imagen | Propósito |
|----------|--------|--------|-----------|
| `postgres` | 5433 | postgres:16-alpine | BD de n8n |
| `n8n` | 5679 | n8nio/n8n:latest | Orquestador (legacy) |
| `render-worker` | 8580 | python:3-alpine | Servidor HTTP para render |

## Flujo de ejecución

1. Guion generado por n8n → metadata.json en `data/videos/{jobId}/`
2. `generate_audio` produce MP3 por escena
3. `fetch_images` descarga imágenes (576×1024)
4. `prepare_job` genera subtítulos ASS estilo profesional (Arial Bold 65px)
5. `render_job` ensambla vídeo final con FFmpeg Docker
6. `review_job` para aprobación/rechazo

### Estructura de datos

```
data/videos/{jobId}/video.mp4, metadata.json, subtitle.ass, scenes/
```

## Última validación conocida

Pipeline validado con múltiples jobs históricos (~14 renders). Subtítulos ASS profesionales funcionales. Render con `ass=` filter (libass 0.17.5). Duración y contratos validados con perfiles configurables.

## Problemas actuales

- Pollinations.ai rate-limited (429), imágenes calidad baja
- FreeAI sin API key configurada
- Voz Edge TTS AlvaroNeural funcional pero calidad cuestionada por usuario
- n8n workflows desconectados del pipeline CLI

## Próximos pasos

1. Registrar FreeAI para imágenes de calidad gratuitas
2. Validar pipeline completo con vídeo desde cero
3. Mejorar prompts de imagen en generación LLM

## Contexto legacy

Para historial extenso, sesiones pasadas y decisiones previas, consultar `HANDOVER.md` (contexto frío, no cargar por defecto).
