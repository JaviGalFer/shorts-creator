# Estado actual del proyecto

**Última actualización:** 2026-08-14

## Estado global

Pipeline funcional de vídeos cortos verticales con duración configurable. Scripts en `bin/` operativos. n8n como orquestador legacy. Docker para render. V2 es el único contrato visual soportado.

**Último change completado:** `retire-legacy-visual-v1` (2026-08-14) — retirada completa del contrato visual V1. Baseline funcional **`1181 passed, 0 failed`**.

**Change pausado:** `improve-short-form-audio-pacing-v2` — Phase A completada, Phase B pendiente (se reanudará tras migrar dominio script).

**Siguiente prioridad:** modularización (`src/shorts_creator/`, `pyproject.toml`). No iniciada todavía.

## Arquitectura runtime

- Pipeline **V2-only** orquestado por `bin/run_job.py`: `script → assets → audio → prepare → render → validate`.
- n8n: infraestructura legacy o alternativa, no el orquestador canónico.
- Providers: LLM `openai` (`gpt-4o-mini`); Wikimedia activo + Pixabay activo (con key); Pexels/FreeAI/Pollinations deshabilitados; TTS `edge_tts`; render vía Docker FFmpeg.
- Modelo de configuración: `.env` + perfiles de duración (`bin/duration_profiles.py`); identidad de producto genérica y configurable.

## Baseline funcional

- Suite completa: **`1181 passed, 0 failed`**.
- `MAX_SCRIPT_ATTEMPTS == 3`.
- Contrato de duración (30s): `minimumWords=47 / preferredWords=52 / maximumWords=52 / operationalWordTarget=50`; `spokenWordsPerMinute=110`; `strictness=balanced`.
- Validator (`bin/visual_plan_v2.py`), runner (`bin/run_job.py`) y perfiles (`bin/duration_profiles.py`) intactos.

## Estado de changes

### `retire-legacy-visual-v1` — completado

Retirada del contrato visual V1. Visual Plan V2 es el único contrato visual soportado. Slices 1–6 cerrados (commits `f2a8078`, `1d9fe37`, `86170d3`, `f48f98f`, `9eb1f13`, `d377932`, `bafb2d5`).

Hitos relevantes del cierre:
- **Quinto E2E V2 canónico** (job `cmo-2026-08-14-153529`): validó **script V2 PASS** (`55 → 52`, `status=PASS`, `structureValid=true`) y **assets V2 completos** (10/10) en E2E real.
- Criterio full-E2E registrado como **DEFERRED/WAIVED**: pipeline bloqueado en `audio` por `AUDIO_DURATION_MISSING`, fuera del scope de retirada V1.
- Length-control hardening validado en E2E real (`55 → 52`; `operationalWordTarget=50` como único target accionable; temperatura de compression `0.2` / resto `0.8`).

### `improve-short-form-audio-pacing-v2` — pausado (Phase A hecha)

Phase A completada (medición real de duración de audio, política `activeAudioDurationSec`, pacing validation). Phase B (WPM calibrado a 27–30s) pendiente; se reanudará tras migrar el dominio script a `src/`.

## Deudas técnicas

- **Audio blocker:** `AUDIO_DURATION_MISSING` — medida de duración de escenas no devuelta durante el run (`duration_estimated=true`); el fallback Docker devuelve duración válida al verificar manualmente, sugiriendo un fallo transitorio. Pospuesto como trabajo independiente.
- **`ffprobe`** no presente en el host; la duración depende del fallback Docker.
- **`visual_normalize.py`** permanece físicamente presente; `validate_job.py` importa `normalize_scene_visual` pero nunca lo invoca (import muerto). Deuda de código fuera del alcance de `retire-legacy-visual-v1`.
- **Recurse de contexto:** historial detallado de Slices migrado a `docs/sessions/` y Git; `current-state.md` conserva solo estado vigente. Contexto caliente de agentes en `docs/project/agent-context.md`.

## Workflow Git

- `main` = estable; implementación nunca directamente en `main`.
- Cada trabajo/change en rama dedicada `change/<slug>`.
- Merge a `main` solo tras validación/cierre.
- Ver política completa en `AGENTS.md` y los lifecycles de las skills.

## Próximos pasos

1. Migrar a `pyproject.toml` y estructura `src/shorts_creator/`.
2. Extraer `contracts/` e `infrastructure/`.
3. Migrar dominio `script/`.
4. Reanudar audio pacing Phase B.
5. Migrar `audio/`, `assets/`, `rendering/`, `validation/`; reducir `bin/` a adaptadores.
6. Investigar instalación de `ffprobe` en el host.