# Agent Context

Contexto operativo mínimo para agentes. No es changelog. Detalle en `docs/project/current-state.md` y artefactos citados.

## Producto y arquitectura runtime

- Generador automatizado y configurable de vídeos cortos verticales, con duración configurable.
- Pipeline **V2-only** orquestado por `bin/run_job.py`: `script → assets → audio → prepare → render → validate`.
- n8n es infraestructura legacy o alternativa, no el orquestador canónico.
- Providers: LLM `openai` (`gpt-4o-mini`); Wikimedia + Pixabay activos; Pexels/FreeAI/Pollinations deshabilitados; TTS `edge_tts`; render vía Docker FFmpeg.

## Baseline funcional

- Suite completa: **`1181 passed, 0 failed`**.
- `MAX_SCRIPT_ATTEMPTS == 3`. Contratos de duración 30s: `minimumWords=47 / preferredWords=52 / maximumWords=52 / operationalWordTarget=50`.

## Estado Git / workflow

- `main` = estable. Implementación **nunca directamente en main**.
- Cada trabajo/change usa rama dedicada `change/<slug>`.
- Merge a `main` solo tras validación/cierre.
- Ver AGENTS.md y lifecycles de las skills para la política completa.

## Trabajo actual / próximo

- Change pausado: `improve-short-form-audio-pacing-v2` — Phase A completada; Phase B pendiente tras migrar dominio script.
- Siguiente prioridad infraestructura: modularización (`src/shorts_creator/`, `pyproject.toml`) — no iniciada.

## Blockers vigentes

- Audio: `AUDIO_DURATION_MISSING` — medida de duración de escenas no devuelta durante el run (`duration_estimated=true`; fallback Docker válido manualmente → probable fallo transitorio). Pospuesto como trabajo independiente.
- `ffprobe` no presente en host (depende de fallback Docker).

## Punteros a documentación

- Operativo detallado: `docs/project/current-state.md`
- Arquitectura: `docs/project/architecture.md`, `docs/architecture/modular-v2-transformation-roadmap.md`
- Integraciones: `docs/project/integrations.md`
- Routing/coste: `.agents/skills/model-routing-and-token-economy/SKILL.md`
- Sesiones (frío): `docs/sessions/` — abrir solo cuando la tarea lo requiera.