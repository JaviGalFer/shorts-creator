# Entorno de desarrollo

## Dependencias obligatorias

| Herramienta | Versión mínima | Validación |
|------------|---------------|------------|
| Python | 3.10+ | `python3 --version` |
| Docker | 24+ | `docker --version` |
| Docker Compose | 2.x | `docker compose version` |
| FFmpeg | 5.x | `ffmpeg -version` o `docker run --rm linuxserver/ffmpeg:latest -version` |
| Git | 2.x | `git --version` |

Python es obligatorio porque el pipeline CLI canónico está compuesto por scripts
Python (`bin/*.py`). Faster-Whisper es una capacidad opcional y no requiere instalar
ningún paquete de sistema.

## Dependencias opcionales

| Herramienta | Para qué | Validación |
|------------|----------|------------|
| Faster-Whisper | Alineación local de subtítulos (opcional) | `pip install faster-whisper` |
| OpenCode | Desarrollo asistido por IA | `opencode --version` |

## Componentes y stack local

El proyecto tiene tres componentes diferenciados:

- **Pipeline CLI canónico** (`bin/run_job.py`): `script → assets → audio → prepare → render → validate`. Es el orquestador y flujo de ejecución vigente. No requiere stack Docker n8n.
- **Infraestructura n8n/PostgreSQL (legacy o alternativa)**: workflows n8n `*-v1` y Postgres. No forma parte del pipeline canónico.
- **Render worker (opcional)**: servicio `render-worker` de `docker-compose.yml` que expone un servidor HTTP (`render_server.py`).

Stack local (solo si operas n8n/Postgres legacy):

```
n8n:      http://localhost:5679
Postgres: localhost:5433
```

## Variables de entorno

Ver `.env.example`. Las variables requeridas por el pipeline CLI canónico:

- **Guion (generación):** `LLM_API_KEY` (obligatoria para generar guion). `LLM_MODEL` y `LLM_PROVIDER` opcionales con defaults.
- **Assets (proveedores visuales):** `PIXABAY_API_KEY` solo es necesaria para utilizar Pixabay; `PEXELS_API_KEY` solo para solicitar explícitamente Pexels Photos. Wikimedia Commons no requiere API key.
- **Audio/TTS:** `edge_tts` es el TTS por defecto y no requiere API key. Las variables de ElevenLabs (`ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL_ID`) solo se necesitan cuando se selecciona ese provider (`TTS_PROVIDER=elevenlabs`).
- **Opcionales de configuración:** `TTS_PROVIDER`, `TTS_VOICE`, `SUBTITLE_TIMING_PROVIDER`, `SUBTITLE_GLOBAL_OFFSET_MS`, `WHISPER_MODEL`, `SUBTITLE_PROVIDER`.
- **Notificaciones (planificado):** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

Variables sin consumidor actual en el pipeline CLI canónico (se conservan en `.env.example` como referencia; el código no las lee):

- `PROJECT_ROOT` — solo usada por el servicio `render-worker` de `docker-compose.yml`.
- `N8N_BASE_URL`, `N8N_ENCRYPTION_KEY`, `POSTGRES_*` — infraestructura n8n/Postgres legacy.
- `SPOKEN_WORDS_PER_MINUTE` — el valor 110 está hardcodeado en `bin/generate_script.py`.
- `OUTPUT_DIR`, `VIDEOS_DIR` — las rutas de datos están hardcodeadas en `bin/`.

### Variables TTS

| Variable | Default | Descripción |
|----------|---------|-------------|
| `TTS_PROVIDER` | `edge_tts` | Proveedor TTS para narración (default canónico, sin API key). `elevenlabs` es alternativa opcional |
| `TTS_VOICE` | `es-ES-AlvaroNeural` | Voz TTS (ej: `es-ES-AlvaroNeural`) |

Ejemplo:
```bash
TTS_PROVIDER=edge_tts
TTS_VOICE=es-ES-AlvaroNeural
```

ElevenLabs es un proveedor secundario opcional. Requiere `ELEVENLABS_API_KEY`,
`ELEVENLABS_VOICE_ID` y `ELEVENLABS_MODEL_ID` únicamente cuando se selecciona
`TTS_PROVIDER=elevenlabs`. `edge_tts` no necesita credenciales.

### Variables de subtítulos

| Variable | Default | Descripción |
|----------|---------|-------------|
| `SUBTITLE_TIMING_PROVIDER` | `auto` | Fuente de timing: `auto` (default), `edge_tts`, `whisper` o `estimated` |
| `SUBTITLE_GLOBAL_OFFSET_MS` | `0` | Desplazamiento global (ms) aplicado a los timestamps. Consumida por `bin/generate_audio.py` |
| `SUBTITLE_PROVIDER` | `estimated` | Modo de alineación legacy: `estimated` o `whisper` (fallback si `SUBTITLE_TIMING_PROVIDER` no está definido) |
| `WHISPER_MODEL` | `tiny` | Modelo Whisper (`tiny`, `base`, `small`, `medium`, `large-v3`) |

Ejemplo:
```bash
SUBTITLE_PROVIDER=whisper
WHISPER_MODEL=tiny
```

### Instalación de dependencias Whisper (opcional)

```bash
pip install faster-whisper
```

El modelo `tiny` (~500MB RAM, rápido en CPU) se descarga automáticamente en la primera ejecución.

Si `faster-whisper` no está instalado:
- El flag `--subtitle-provider whisper` falla con warning
- Fallback automático a `estimated`
- El pipeline continúa normalmente

## Directorios de datos

Layout canónico del pipeline CLI (V2):

```
data/videos/{jobId}/
  metadata.json     -> metadata de cada trabajo
  video.mp4         -> render final
  subtitle.ass      -> subtítulos (ASS; se acepta SRT)
  assets/           -> imágenes de fondo (seg_XXX.jpg)
  scenes/           -> narración y escenas (narration.mp3, scene-XX.mp3, scene-XX.jpg)
```

- `data/postgres/` es la persistencia de la infraestructura legacy n8n/PostgreSQL (ver `docker-compose.yml`). No lo consume el pipeline CLI canónico.
- `logs/` contiene logs de ejecución.

El layout plano antiguo (`data/assets/`, `data/audio/`, `data/subtitles/`, `data/renders/`, `data/metadata/`) pertenece a los workflows n8n `*-v1` (legacy).

## Windows (WSL)

El proyecto se ejecuta desde WSL. El render con FFmpeg usa CPU. La GPU GTX 1650 SUPER no es requisito del pipeline. Para aceleración hardware, instalar drivers NVIDIA dentro de WSL2.

## Observaciones reales del entorno

- `ffmpeg` no está instalado en el host WSL actual.
- El render validado se ejecuta con `linuxserver/ffmpeg:latest` vía Docker.
- Para este proyecto, Docker es actualmente la vía principal de render reproducible.
