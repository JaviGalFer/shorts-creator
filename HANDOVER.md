# Shorts Históricos — Handover

Proyecto: pipeline automatizado de vídeos cortos verticales (~1 min, 9:16) de temática histórica, con guion IA, voz, imágenes y subtítulos profesionales.

---

## 1. Estructura del proyecto

```
shorts-historicos/
├── bin/                     <- Scripts del pipeline (los que se usan)
│   ├── generate_audio.py    # Edge TTS: genera MP3 por escena
│   ├── fetch_images.py      # Descarga imágenes (3 proveedores)
│   ├── prepare_job.py       # Genera subtítulos ASS + consolida metadata
│   └── render_job.py        # Renderiza MP4 final con FFmpeg en Docker
├── scripts/                 # (legacy, owned by root, no modificar)
│   ├── prepare_job.py
│   └── render_job.py
├── data/
│   ├── videos/{jobId}/      # <-- TODO ORGANIZADO AQUÍ
│   │   ├── video.mp4
│   │   ├── metadata.json
│   │   ├── subtitle.ass (o .srt)
│   │   └── scenes/
│   │       ├── scene-01.jpg
│   │       ├── scene-01.mp3
│   │       └── ...
│   ├── n8n/                 # Base de datos de n8n (Docker)
│   └── postgres/            # Postgres data (Docker)
├── docs/
│   ├── project/             # Arquitectura, estado, integraciones, roadmap...
│   ├── sessions/            # Bitácoras de sesiones
│   ├── decisions/           # ADRs
│   └── runbooks/            # Guías operativas
├── openspec/
│   ├── project.md           # Descripción del proyecto
│   └── changes/             # Cambios OpenSpec activos/cerrados
├── docker-compose.yml       # n8n + postgres + render-worker
├── render_server.py         # HTTP server para render-worker
├── review_job.py            # CLI para aprobar/rechazar renders
├── .env                     # API keys (NO versionado)
└── AGENTS.md                # Instrucciones para agentes IA
```

---

## 2. Pipeline completo

```
bin/generate_script.py  (NO CREADO aún, se hacía con n8n)
        │
        v
bin/generate_audio.py  (Edge TTS, español de España)
        │
        v
bin/fetch_images.py    (Pollinations/FreeAI/Wikimedia)
        │
        v
bin/prepare_job.py     (genera subtitle.ass + actualiza metadata)
        │
        v
bin/render_job.py      (FFmpeg Docker → video.mp4)
        │
        v
review_job.py          (aprueba/rechaza visualmente)
```

### Uso

```bash
# metadata.json debe existir en data/videos/{jobId}/
python3 bin/generate_audio.py data/videos/{jobId}/metadata.json
python3 bin/fetch_images.py data/videos/{jobId}/metadata.json --provider pollinations
python3 bin/prepare_job.py data/videos/{jobId}/metadata.json
python3 bin/render_job.py data/videos/{jobId}/metadata.json
```

---

## 3. Scripts del pipeline

### `bin/generate_audio.py`
- **Qué hace**: Genera un MP3 por escena usando Edge TTS (Microsoft, gratuito)
- **Voz**: `es-ES-AlvaroNeural` (español de España, neural)
- **Input**: metadata.json con `script.scenes[].voiceover`
- **Output**: `scenes/scene-{N}.mp3`
- **Dependencia**: `pip install edge-tts`
- **Nota**: Edge TTS requiere Alpine Python 3-slim + `pip install edge-tts` (no viene instalado en el host)

### `bin/fetch_images.py`
- **Qué hace**: Descarga una imagen por escena
- **Proveedores**:
  | Proveedor | API Key | Calidad | Límites |
  |-----------|---------|---------|---------|
  | `pollinations` (default) | No necesita | Baja | 1 req/sec, rate-limited |
  | `freeai` | `FREEAI_API_KEY` en .env | Buena (FLUX/SDXL) | 30K tokens/día gratis |
  | `wikimedia` | No necesita | Fotos reales | Rate-limited (429) |
- **Input**: `script.scenes[].imagePrompt` o `visualPrompt`
- **Output**: `scenes/scene-{N}.jpg` (576×1024)

### `bin/prepare_job.py`
- **Qué hace**: Escanea assets/audio, genera subtítulos, actualiza metadata
- **Subtítulos**: Genera ASS (por defecto) o SRT
- **Estilo ASS actual**: Arial Bold 65px, caja semitransparente, 18 chars/linea
- **Output**: `subtitle.ass` + `metadata.json` actualizado

### `bin/render_job.py`
- **Qué hace**: Renderiza el vídeo final con FFmpeg en Docker
- **Base**: `linuxserver/ffmpeg:latest`
- **Filter**: `ass=` para ASS, `subtitles=` para SRT
- **Resolución**: 1080×1920 (9:16 vertical)
- **Codec**: libx264 + AAC
- **Output**: `video.mp4`
- **Requiere**: Docker + `DOCKER_API_VERSION=1.43`

---

## 4. Infraestructura

### Docker Compose (`docker-compose.yml`)
| Servicio | Puerto | Imagen | Propósito |
|----------|--------|--------|-----------|
| `postgres` | 5433 | postgres:16-alpine | BD de n8n |
| `n8n` | 5679 | n8nio/n8n:latest | Orquestador (legacy) |
| `render-worker` | 8580 | python:3-alpine | HTTP server para render |

### n8n
- URL: `http://localhost:5679`
- Login: `admin@shorts.com` / `***`
- Workflows exportados en JSON en raíz del proyecto:
  - `workflow-generate-script.json`
  - `workflow-generate-audio-v1.json`
  - `workflow-fetch-assets.json`
  - `workflow-render-video.json`
- **Nota**: Los workflows n8n usan el formato plano antiguo (`data/metadata/`, `data/assets/`, etc.). Quedan como referencia/alternativa manual. El pipeline principal son los scripts de `bin/`.

### Render
- `render_server.py` sirve HTTP API en `:8580`
- `review_job.py` permite approve/reject desde CLI

---

## 5. APIs y credenciales (`.env`)

| Variable | Valor actual | Servicio | Plan |
|----------|-------------|----------|------|
| `LLM_API_KEY` | *** | OpenAI GPT-4o-mini | De pago (tiene crédito) |
| `ELEVENLABS_API_KEY` | *** | ElevenLabs TTS | Gratis (21 voces inglés) |
| `PEXELS_API_KEY` | *** | Pexels imágenes | Gratis (limitado) |
| `PIXABAY_API_KEY` | *** | Pixabay imágenes | Gratis (limitado) |
| `N8N_OWNER_EMAIL` | admin@shorts.com | n8n local | - |
| `N8N_OWNER_PASSWORD` | *** | n8n local | - |

**No configuradas aún** (necesarias para mejorar imágenes):
- `FREEAI_API_KEY` — Registrarse en free.ai para 30K tokens/día gratis

---

## 6. Estado de los jobs existentes

| JobID | Tema | Escenas | Estado |
|-------|------|---------|--------|
| franco-2026-06-30-194824 | La Toma de España por Franco | 6 | RENDERED |
| franco2-2026-06-30-195826 | La Toma de España por Franco | 9 | SCRIPT_DRAFT |
| franco3-2026-06-30-200538 | La Toma de España por Francisco Franco | 10 | RENDERED |
| franco4-2026-06-30-202436 | La Toma de España | 10 | RENDERED |
| franco5-2026-06-30-204654 | La Toma de España | 10 | ASSETS_READY |
| franco6-2026-06-30-211042 | La Toma de España | 10 | RENDERED (ASS) |
| hist-2026-06-30-175447 | La Caída de Constantinopla | 7 | SCRIPT_DRAFT |
| hist-2026-06-30-181103 | La Caída de Constantinopla | 6 | SCRIPT_DRAFT |
| hist-2026-06-30-181521 | La Caída de Constantinopla: El Fin... | 6 | RENDERED |
| hist-2026-06-30-211529 | El hombre que sobrevivió a dos bombas | 6 | RENDERED |
| hist-2026-06-30-212233 | Tsutomu Yamaguchi... | 6 | RENDERED |
| hist-2026-06-30-213105 | Tsutomu Yamaguchi... | 6 | RENDERED |
| hist-2026-06-30-213153 | Tsutomu Yamaguchi... | 6 | AUDIO_READY |
| hist-2026-06-30-213340 | Tsutomu Yamaguchi | 10 | RENDERED |

**Nota**: Los 11 jobs RENDERED usan subtítulos SRT (excepto franco6 que tiene ASS). Usan imágenes de diversas fuentes (Pexels original, Pollinations después).

---

## 7. Logros y problemas conocidos

### ✅ Logros

| Concepto | Estado |
|----------|--------|
| Scripts Python pipeline (bin/) | Funcionan |
| ASS subtitles profesionales | Font 65px, caja semitransparente, wrapping |
| Render con FFmpeg Docker | `ass=` filter validado con libass 0.17.5 |
| Edge TTS español España | Funciona, voz AlvaroNeural |
| Directorios por vídeo | `data/videos/{jobId}/` autocontenido |
| n8n operativo | 4 workflows exportados |
| Render server + review CLI | Operativos |
| Migración legacy completada | 14 jobs movidos a nuevo formato |

### ❌ Problemas

| Problema | Detalle | Solución propuesta |
|----------|---------|-------------------|
| **Imágenes** | Pollinations da calidad baja y rate-limited (429). Wikimedia rate-limited. | Registrarse en Free.ai (30K tokens/día gratis, sin tarjeta) y configurar `FREEAI_API_KEY` |
| **Voz** | Edge TTS AlvaroNeural poco natural según el usuario. ElevenLabs voces españolas requieren plan pago. | No hay alternativa gratuita mejor. Aceptar Edge TTS o pagar ElevenLabs. |
| **generate_script.py** | No existe como script CLI. El guion se genera con n8n (workflow generate-script). | Crear `bin/generate_script.py` que llame a OpenAI/Anthropic directamente. |
| **ASS en jobs legacy** | Todos los jobs menos franco6 tienen subtitle.srt (estilo básico). | No crítico, los ASS se generan automáticamente para nuevos jobs. |

---

## 8. ASS Subtitles — Estilo actual

```
Style: Subtitle,Arial Bold,65,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,3,0,0,2,60,60,40,1
```

| Propiedad | Valor |
|-----------|-------|
| Font | Arial Bold 65px |
| Color texto | Blanco (`&H00FFFFFF`) |
| Fondo | Caja negra semitransparente 63% (`&HA0000000`) |
| BorderStyle | 3 (opaque box) |
| Alineación | 2 (centrado abajo) |
| MarginV | 40px desde borde inferior |
| Wrapping | ~18 caracteres por línea |

---

## 9. Próximos pasos

1. **Crear `bin/generate_script.py`** — script que llame a la API de OpenAI con el prompt histórico para generar el metadata.json completo
2. **Registrar Free.ai** — obtener API key para imágenes de calidad
3. **Probar pipeline completo** con un vídeo nuevo desde cero:
   ```bash
   python3 bin/generate_script.py --topic "tema histórico" data/videos/{jobId}/metadata.json
   python3 bin/generate_audio.py data/videos/{jobId}/metadata.json
   python3 bin/fetch_images.py data/videos/{jobId}/metadata.json --provider freeai
   python3 bin/prepare_job.py data/videos/{jobId}/metadata.json
   python3 bin/render_job.py data/videos/{jobId}/metadata.json
   ```
4. **Instalar edge-tts** en el host (`pip install edge-tts`)
5. **Mejorar prompts de imagen** en el LLM para que genere imagePrompt más descriptivos en inglés
