# Roadmap

## Fase 0 — Fundación (esta fase)
- Estructura documental y de proyecto.
- AGENTS.md, skills, agentes.
- OpenSpec inicial.
- Docker Compose con n8n + Postgres.
- Documentación de integraciones.

## Fase 1 — Pipeline mínimo (MVP)
- Workflow n8n: entrada manual -> LLM -> validación JSON.
- Integración ElevenLabs funcional.
- Integración Pexels/Pixabay funcional.
- Pipeline FFmpeg: render básico con imágenes + audio + subtítulos.
- Vídeo completo generado con revisión humana.

## Fase 2 — Calidad y robustez
- Generación de subtítulos precisa.
- Múltiples voces/configuraciones TTS.
- Manejo de errores y reintentos en n8n.
- Metadata completa por trabajo.

## Fase 3 — Automatización y variedad
- Variaciones de guion (duración, tono, complejidad).
- Fuentes de imágenes múltiples con fallback.
- Música de fondo sincronizada.
- Notificaciones (Telegram) de vídeos listos.

## Fase 4 — Publicación (futuro)
- Integración con YouTube Shorts / TikTok API.
- Programador de publicaciones.
- Analítica básica.
