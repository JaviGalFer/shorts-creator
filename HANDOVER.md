> **Este documento es contexto legacy frío. Para el estado técnico actual, consultar `docs/project/current-state.md`.**

# Handover — Shorts Históricos

## Estructura del proyecto

```
shorts-creator/
├── bin/               <- Scripts activos del pipeline
│   ├── generate_audio.py
│   ├── fetch_images.py
│   ├── prepare_job.py
│   └── render_job.py
├── scripts/           <- Legacy (root, no modificar)
├── data/videos/{jobId}/
├── docs/
│   ├── project/       <- Arquitectura, estado, integraciones
│   ├── sessions/      <- Bitácoras históricas (frío)
│   └── decisions/     <- ADRs
├── openspec/
│   ├── project.md
│   └── changes/       <- Cambios activos/cerrados
├── docker-compose.yml
├── render_server.py
└── review_job.py
```

## Logros

- Scripts Python pipeline funcionales
- ASS subtitles profesionales (Arial Bold 65px, caja semitransparente)
- Render FFmpeg Docker con `ass=` filter validado (libass 0.17.5)
- Edge TTS español España operativo (AlvaroNeural)
- Migración legacy completada (14 jobs a nuevo formato)
- Pipeline validado con perfil de duración y contratos

## Problemas conocidos

| Problema | Detalle |
|----------|---------|
| Imágenes calidad baja | Pollinations rate-limited (429) |
| FreeAI sin configurar | Falta `FREEAI_API_KEY` en .env |
| Voz mejorable | Edge TTS AlvaroNeural, usuario discrepa |
| n8n desconectado | Workflows no integrados con pipeline CLI |
| Sin generate_script.py | Guion generado solo por n8n |
| ASS en jobs legacy | Solo franco6 tiene ASS, resto SRT |

## Dónde continuar

1. Registrar FreeAI y configurar `FREEAI_API_KEY`
2. Crear `bin/generate_script.py` para generar metadata.json desde LLM
3. Validar pipeline end-to-end con vídeo nuevo
4. Mejorar prompts de imagen en generación LLM

## APIs y credenciales

Ver `.env.example` y `docs/project/environment.md`. No incluir valores reales en archivos versionados.

## Referencias

- Contexto actual: `docs/project/current-state.md`
- Arquitectura: `docs/project/architecture.md`
- Integraciones: `docs/project/integrations.md`
