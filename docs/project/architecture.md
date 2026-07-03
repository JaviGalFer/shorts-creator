# Arquitectura del sistema

## Visión general

```
[Entrada manual] -> n8n -> LLM (guion) -> ElevenLabs (voz)
                            -> FFmpeg (render) -> [MP4 + metadata]
```

n8n actúa como orquestador. No hay backend permanente, ni base de datos obligatoria en el MVP.

## Flujo de datos

1. Usuario introduce un tema histórico en n8n (webhook manual o formulario simple).
2. n8n llama a un LLM externo para generar un guion estructurado en JSON.
3. n8n valida el JSON (duración, escenas, coherencia).
4. Script `bin/generate_audio.py` genera audio (Edge TTS) para cada escena.
5. Script `bin/fetch_images.py` descarga imágenes (AI o stock).
6. Script `bin/prepare_job.py` genera subtítulos (ASS) + consolida metadata.
7. Script `bin/render_job.py` ejecuta FFmpeg (Docker) para render MP4 9:16.
8. Metadata se actualiza con ruta del render.
9. Revisión humana con `review_job.py`.

## Gestión de archivos

Cada vídeo es un directorio autocontenido:

```
data/
  videos/
    {jobId}/
      video.mp4           <- Render final MP4
      metadata.json       <- Job metadata (canónico)
      subtitle.ass        <- Subtítulos (ASS o SRT)
      scenes/
        scene-01.jpg      <- Imagen escena 1
        scene-01.mp3      <- Audio escena 1
        scene-02.jpg
        scene-02.mp3
        ...
```

Cada trabajo tiene un `jobId` único con formato `{tema}-YYYY-MM-DD-HHMMSS`.

## Variables de entorno

Ver `.env.example`. Todas las APIs externas se configuran vía variables de entorno.

## Estrategia de errores

- n8n maneja reintentos con backoff exponencial.
- Fallos de API external se registran en logs y el trabajo pasa a estado `FAILED`.
- No hay colas distribuidas en el MVP.

## Seguridad de claves

- API keys solo en `.env` (excluido de Git).
- n8n almacena credenciales en su base de datos cifrada.
- Los workflows n8n referencian credenciales por ID, nunca por valor literal.

## Modelo de datos canónico (video job)

```json
{
  "jobId": "hist-2026-06-29-001",
  "status": "DRAFT",
  "topic": "Título del vídeo",
  "language": "es-ES",
  "format": "shorts-9x16",
  "targetDurationSeconds": 45,
  "script": {
    "title": "",
    "hook": "",
    "summary": "",
    "totalTargetDurationSec": 45,
    "scenes": [
      {
        "sceneNumber": 1,
        "purpose": "",
        "visualPrompt": "",
        "voiceover": "",
        "subtitle": "",
        "targetDurationSec": 8
      }
    ],
    "closingCta": ""
  },
  "audio": {
    "provider": "edge-tts",
    "scenes": [
      {"sceneNumber": 1, "path": "data/videos/{jobId}/scenes/scene-01.mp3", "exists": false}
    ]
  },
  "assets": [
    {"sceneNumber": 1, "path": "data/videos/{jobId}/scenes/scene-01.jpg", "exists": false}
  ],
  "subtitles": {
    "path": "data/videos/{jobId}/subtitle.ass",
    "format": "ass"
  },
  "render": {
    "path": "data/videos/{jobId}/video.mp4",
    "durationSeconds": 0
  },
  "review": {
    "status": "PENDING"
  },
  "createdAt": "",
  "updatedAt": ""
}
```

## Máquina de estados

```
IDEA
  -> SCRIPT_DRAFT
  -> SCRIPT_APPROVED
  -> AUDIO_READY
  -> ASSETS_READY
  -> SUBTITLES_READY
  -> RENDERING
  -> RENDERED
  -> REVIEW_PENDING
  -> APPROVED | REJECTED | FAILED
```

## Manifiesto de ejecución (job-manifest.json)

Cada job renderizado produce `data/videos/{jobId}/job-manifest.json` con:

```json
{
  "jobId": "la-2026-07-01-173458",
  "createdAt": "ISO-8601",
  "scriptPath": "data/videos/{jobId}/metadata.json",
  "renderProfile": "shorts_upper_dynamic",
  "resolution": "1080x1920",
  "tts": {
    "provider": "edge_tts",
    "voice": "es-ES-AlvaroNeural"
  },
  "subtitles": {
    "provider": "edge_tts_sentence_boundary|whisper_word_timestamps|estimated",
    "path": "data/videos/{jobId}/subtitle.ass"
  },
  "scenes": [
    {
      "sceneNumber": 1,
      "visualType": "image",
      "visualPath": "scenes/scene-01.jpg",
      "audioPath": "data/videos/{jobId}/scenes/narration.mp3",
      "audioDurationSec": 30.86
    }
  ],
  "outputVideoPath": "data/videos/{jobId}/video.mp4"
}
```

## Normalización visual.type

Para compatibilidad futura con vídeos, las escenas se normalizan a:

```json
{
  "visual": {
    "type": "image",
    "path": "scenes/scene-01.jpg",
    "fit": "cover",
    "motion": "slow_zoom_in"
  }
}
```

Formato futuro para clips de vídeo (documentado, no implementado):

```json
{
  "visual": {
    "type": "video",
    "path": "scenes/scene-01.mp4",
    "trimStartSec": 0,
    "trimDurationSec": 6.4,
    "fit": "cover"
  }
}
```

Los JSON legacy (sin campo `visual`) se normalizan automáticamente por `bin/visual_normalize.py`.

## Validación automatizada

```bash
python3 bin/validate_job.py data/videos/{jobId}/metadata.json
```

Comprueba: assets, audio, tamaños, duraciones, ASS, cues, cobertura, manifiesto, resolución.
Exit code 0 = PASS, != 0 = ERROR.

## TTS configurable

El proveedor y voz TTS se configuran vía entorno:

| Variable | Default | Descripción |
|----------|---------|-------------|
| `TTS_PROVIDER` | `edge_tts` | Proveedor |
| `TTS_VOICE` | `es-ES-AlvaroNeural` | Voz |

CLI override: `--tts-provider edge_tts --voice es-ES-AlvaroNeural`

## Subtítulos con Whisper

| Variable | Default | Descripción |
|----------|---------|-------------|
| `SUBTITLE_PROVIDER` | `estimated` | `estimated` o `whisper` |
| `WHISPER_MODEL` | `tiny` | Modelo Whisper |

`--subtitle-provider whisper` activa transcripción con faster-whisper.
Fallback automático a `estimated` si faster-whisper no está instalado.

No hay publicación automática en el MVP.
