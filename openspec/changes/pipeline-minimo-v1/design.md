# Diseño: Pipeline mínimo v1

## Workflow 1 — Generación de guion (n8n)

**Trigger**: Webhook manual (POST con `{ "topic": "La caída de Constantinopla" }`)

**Nodos**:
1. Webhook — recibe topic
2. HTTP Request — llama a LLM API (OpenAI/Anthropic) con prompt estructurado
3. Code — valida JSON de respuesta (campos obligatorios, duración estimada)
4. Code — genera jobId (`hist-YYYY-MM-DD-NNN`) y metadata inicial
5. Wait / Respond — devuelve guion aprobado al usuario

**Prompt LLM**: Solicitar JSON con estructura: `{ title, hook, narration, scenes: [{ imagePrompt, text, durationSec }] }`

## Workflow 2 — Assets (n8n)

**Trigger**: Webhook (recibe jobId + guion aprobado)

**Nodos**:
1. HTTP Request — ElevenLabs TTS por cada escena
2. HTTP Request — Pexels search por cada `imagePrompt`
3. Code — asocia audio + imágenes por escena
4. Code — genera SRT de subtítulos
5. Wait — guarda rutas en metadata

## Pipeline FFmpeg (script ejecutado por n8n)

**Input**: imágenes por escena + audio completo + SRT

**Comando**:

```bash
ffmpeg -i audio.mp3 \
  -loop 1 -t 5 -i scene1.jpg \
  -loop 1 -t 7 -i scene2.jpg \
  ...
  -filter_complex "[1:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[v0];[2:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[v1];[v0][0:a][v1]concat=n=2:v=1:a=1[v][a]" \
  -map "[v]" -map "[a]" \
  -vf "subtitles=subtitles.srt:force_style='FontSize=24,Alignment=2'" \
  -c:v libx264 -c:a aac -pix_fmt yuv420p output.mp4
```

## Gestión de archivos

Cada trabajo crea:
```
data/audio/hist-2026-06-29-001/
  scene-1.mp3
  scene-2.mp3
  narration-full.mp3
data/assets/hist-2026-06-29-001/
  scene-1.jpg
  scene-2.jpg
data/subtitles/hist-2026-06-29-001/
  subtitles.srt
data/renders/hist-2026-06-29-001/
  final.mp4
data/metadata/hist-2026-06-29-001.json
```
