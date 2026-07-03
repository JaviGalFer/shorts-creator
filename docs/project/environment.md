# Entorno de desarrollo

## Dependencias obligatorias

| Herramienta | Versión mínima | Validación |
|------------|---------------|------------|
| Docker | 24+ | `docker --version` |
| Docker Compose | 2.x | `docker compose version` |
| FFmpeg | 5.x | `ffmpeg -version` o `docker run --rm linuxserver/ffmpeg:latest -version` |
| Git | 2.x | `git --version` |

## Dependencias opcionales

| Herramienta | Para qué | Validación |
|------------|----------|------------|
| Python 3.10+ | Whisper/Faster-Whisper (subtítulos local) | `python --version` |
| OpenCode | Desarrollo asistido por IA | `opencode --version` |

## Stack local

```
n8n:      http://localhost:5679
Postgres: localhost:5433
```

## Variables de entorno

Ver `.env.example`. Las variables requeridas por fase:

- **Fundación**: Ninguna
- **Fase 1**: `LLM_API_KEY`, `ELEVENLABS_API_KEY`, `PEXELS_API_KEY` (o Pixabay)
- **Fase 2**: Las mismas + opcionales de configuración
- **Fase 3**: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

### Variables TTS

| Variable | Default | Descripción |
|----------|---------|-------------|
| `TTS_PROVIDER` | `edge_tts` | Proveedor TTS para narración |
| `TTS_VOICE` | `es-ES-AlvaroNeural` | Voz TTS (ej: `es-ES-AlvaroNeural`) |

Ejemplo:
```bash
TTS_PROVIDER=edge_tts
TTS_VOICE=es-ES-AlvaroNeural
```

### Variables de subtítulos (Whisper)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `SUBTITLE_PROVIDER` | `estimated` | Modo de alineación: `estimated` o `whisper` |
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

```
data/assets/      -> imágenes de fondo
data/audio/       -> narraciones .mp3/.wav
data/subtitles/   -> archivos .srt
data/renders/     -> vídeos .mp4 finales
data/metadata/    -> JSON de cada trabajo
logs/             -> logs de ejecución
```

## Windows (WSL)

El proyecto se ejecuta desde WSL. El render con FFmpeg usa CPU. La GPU GTX 1650 SUPER no es requisito del pipeline. Para aceleración hardware, instalar drivers NVIDIA dentro de WSL2.

## Observaciones reales del entorno

- `ffmpeg` no está instalado en el host WSL actual.
- El render validado se ejecuta con `linuxserver/ffmpeg:latest` vía Docker.
- Para este proyecto, Docker es actualmente la vía principal de render reproducible.
