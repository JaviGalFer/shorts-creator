# Arquitectura del sistema

## Arquitectura actual

### Orquestador

`bin/run_job.py` es el orquestador canónico. Ejecuta las seis etapas del pipeline en orden de dependencia, verifica contratos de salida post-etapa y produce metadata trazable con historial de orquestación.

No hay backend permanente, base de datos obligatoria ni dependencia de n8n para el pipeline.

### Pipeline

```
script → assets → audio → prepare → render → validate
```

| Etapa | Script | Contrato de salida | Artefacto |
|-------|--------|-------------------|-----------|
| Script | `bin/generate_script.py` | `SCRIPT_DRAFT` | `metadata.json` con guion V2 |
| Assets | `bin/fetch_images_v2.py` | `ASSETS_READY` | Imágenes en `assets/` |
| Audio | `bin/generate_audio.py` | `AUDIO_READY` | `scenes/narration.mp3` o `scene-*.mp3` |
| Prepare | `bin/prepare_job.py` | `SUBTITLES_READY` | Subtítulos ASS, timeline de render |
| Render | `bin/render_job.py` | `RENDERED` | `video.mp4` |
| Validate | `bin/validate_job.py` | `VALIDATED` o `VALIDATION_FAILED` | Métricas de pacing y calidad |

### Visual Plan V2

El único contrato visual canónico es Visual Plan V2. Cada escena contiene un `visualPlan` con `_schemaVersion: 2`. El pipeline clasifica y rechaza metadata V1 o mixta.

Assets visuales V2 se almacenan bajo `assets/` en el directorio del job.

### Gestión de archivos

Cada vídeo es un directorio autocontenido:

```
data/
  videos/
    {jobId}/
      video.mp4           <- Render final MP4
      metadata.json       <- Job metadata (canónico)
      subtitle.ass        <- Subtítulos (ASS)
      scenes/
        narration.mp3     <- Narración completa
        scene-01.mp3      <- Audio por escena (alternativo)
      assets/
        scene-01.jpg      <- Imagen escena 1
        scene-02.jpg      <- Imagen escena 2
```

Cada trabajo tiene un `jobId` único con formato `{tema}-YYYY-MM-DD-HHMMSS`.

### TTS

| Variable | Default | Descripción |
|----------|---------|-------------|
| `TTS_PROVIDER` | `edge_tts` | Proveedor canónico (`edge_tts` u `elevenlabs`) |
| `TTS_VOICE` | `es-ES-AlvaroNeural` | Voz TTS |

Edge TTS es el proveedor canónico (gratuito, sin API key, voz natural). ElevenLabs es un proveedor secundario opcional.

### Providers visuales

| Provider | Estado | API key |
|----------|--------|---------|
| Wikimedia Commons | Activo, implementado | No necesita |
| Pixabay | Activo, implementado | `PIXABAY_API_KEY` |
| Pexels | Planificado, deshabilitado | — |
| FreeAI | Deshabilitado, no implementado | — |
| Pollinations | Deshabilitado, no implementado | — |

### Render

FFmpeg ejecutado en Docker (`linuxserver/ffmpeg:latest`) genera vídeo MP4 9:16 (1080×1920) con transiciones, fundidos y room tone.

### Validación

```bash
python3 bin/validate_job.py data/videos/{jobId}/metadata.json
```

Comprueba: assets, audio, duraciones, ASS, cues, cobertura de narración, pacing, manifiesto. Exit code 0 = PASS.

### Docker y servicios auxiliares

`docker-compose.yml` ofrece:
- **n8n**: servicio disponible para automatizaciones (no es orquestador canónico)
- **Postgres**: base de datos para n8n
- **render-worker**: worker de render remoto (opcional)

### Máquina de estados

```
SCRIPT_DRAFT
  -> ASSETS_READY
  -> AUDIO_READY
  -> SUBTITLES_READY
  -> RENDERED | RENDERED_WITH_WARNINGS
  -> VALIDATED
```

Estados de fallo: `FAILED`, `REVIEW_REQUIRED`, `ASSET_UNRESOLVED`, `ASSETS_PARTIAL`.

### Variables de entorno

Ver `.env.example`. Las API externas se configuran vía variables de entorno. No hay secretos versionados.

### Subtítulos

| Variable | Default | Descripción |
|----------|---------|-------------|
| `SUBTITLE_TIMING_PROVIDER` | `auto` | `auto`, `edge_tts`, `whisper` o `estimated` |
| `WHISPER_MODEL` | `tiny` | Modelo Whisper |

El proveedor de timing se resuelve en orden: Edge TTS WordBoundary → Whisper → estimado.

## Modelo de configuración del producto

### Contrato disponible actualmente

Los controles actualmente expuestos por CLI, variables de entorno o metadata son:

| Control | Superficie |
|---------|-----------|
| Tema | `--topic` |
| Duración | `--duration`, `--duration-profile`, `--duration-target`, `--duration-min`, `--duration-max`, `--strictness` |
| Modelo LLM | `--model` |
| Proveedor TTS | `--tts-provider`, `TTS_PROVIDER` |
| Voz | `--voice`, `TTS_VOICE` |
| Timing de subtítulos | `--subtitle-timing-provider`, `SUBTITLE_TIMING_PROVIDER` |
| Estilo de subtítulos | `--subtitle-style` |
| Providers visuales | Wikimedia Commons, Pixabay |
| Ejecución parcial | `--stop-after` |
| Planificación | `--dry-run` |

### Contrato objetivo

La arquitectura futura podrá aceptar un request o perfil unificado que incluya estos campos conceptuales:

```
topic
format
duration
language
voice
subtitles
music
visuals
quality
reviewPolicy
publication
```

Este contrato objetivo no está implementado. Es dirección del producto y guiará el diseño de la configuración centralizada cuando se desarrolle.

## Arquitectura futura (roadmap)

El proyecto se transformará hacia una arquitectura modular:

```
shorts-creator/
├── pyproject.toml          (pendiente)
├── src/shorts_creator/      (pendiente)
│   ├── contracts/
│   ├── pipeline/
│   ├── script/
│   ├── audio/
│   ├── assets/
│   ├── rendering/
│   ├── validation/
│   └── infrastructure/
├── bin/                     (futura capa de adaptadores CLI)
├── tools/                   (benchmarks y utilidades de desarrollo)
└── tests/
```

- `src/shorts_creator/` y `pyproject.toml` no existen aún.
- `bin/` se reducirá progresivamente de scripts monolíticos a adaptadores delgados.
- Cada dominio (script, audio, assets, rendering, validation) migrará individualmente.
- `tools/` albergará benchmarks y utilidades no pertenecientes al runtime.

Ver `docs/architecture/modular-v2-transformation-roadmap.md` para el plan detallado.
