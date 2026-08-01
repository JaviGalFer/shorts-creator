# Runbook: Pipeline CLI (primario)

## A. Ejecución canónica

El orquestador canónico es `bin/run_job.py`. Ejecuta el pipeline completo en orden:

```
script → assets → audio → prepare → render → validate
```

Ejemplo:

```bash
python3 bin/run_job.py --topic "<tema>" --duration 42
```

Opciones útiles:

```bash
python3 bin/run_job.py --topic "<tema>" --duration 42 --dry-run   # muestra el plan sin ejecutar
python3 bin/run_job.py --topic "<tema>" --duration 42 --stop-after script  # detener tras una etapa
python3 bin/run_job.py --topic "<tema>" --duration-profile standard_32_38  # perfil de duración
```

Cada vídeo vive en `data/videos/{jobId}/`.

## B. Ejecución manual por etapas

Los comandos por etapa pueden usarse para diagnóstico o ejecución manual. No sustituyen al orquestador canónico (`bin/run_job.py`).

```bash
# 1. Generar guion
python3 bin/generate_script.py --topic "<tema>" --duration 30 --output data/videos/{jobId}/metadata.json

# 2. Descargar assets visuales
python3 bin/fetch_images_v2.py data/videos/{jobId}/metadata.json

# 3. Generar audio (Edge TTS)
python3 bin/generate_audio.py data/videos/{jobId}/metadata.json

# 4. Preparar subtítulos y timeline
python3 bin/prepare_job.py data/videos/{jobId}/metadata.json

# 5. Renderizar vídeo
python3 bin/render_job.py data/videos/{jobId}/metadata.json

# 6. Validar (quality gate)
python3 bin/validate_job.py data/videos/{jobId}/metadata.json
```

## Estructura de datos

```
data/videos/{jobId}/
  video.mp4           <- Render final
  metadata.json       <- Job metadata
  subtitle.ass        <- Subtítulos (ASS o SRT)
  assets/
    seg_001.jpg
    ...
  scenes/
    narration.mp3
    ...
```

## Scripts disponibles

| Script | Función |
|--------|---------|
| `bin/run_job.py` | Orquestador canónico: script → assets → audio → prepare → render → validate |
| `bin/generate_script.py` | Genera guion mediante LLM con plan visual V2 |
| `bin/fetch_images_v2.py` | Descarga assets visuales mediante el pipeline V2 y los proveedores configurados. |
| `bin/generate_audio.py` | Genera MP3 por escena vía Edge TTS |
| `bin/prepare_job.py` | Genera subtítulos ASS + consolida metadata |
| `bin/render_job.py` | Renderiza MP4 final con FFmpeg Docker |
| `bin/validate_job.py` | Quality gate automatizado de validación PASS/FAIL post-render |
| `review_job.py` | Decisión humana manual de aprobar/rechazar un vídeo renderizado (`approve`/`reject`). No sustituye al quality gate automatizado de `validate_job.py`. |

## n8n workflows (legacy / alternativa)

Los workflows n8n quedan como alternativa manual. Son infraestructura **legacy**:
no forman parte del pipeline canónico (`bin/run_job.py`) y usan el formato plano
antiguo, anterior a los contratos V2 y al layout `data/videos/{jobId}/`. No
deben considerarse como soporte de los proveedores o contratos del pipeline CLI
vigente (por ejemplo, los proveedores visuales V2 Wikimedia/Pixabay y el plan
visual V2).

- `generate-script-v1`: genera `data/metadata/{jobId}.json`
- `generate-audio-v1`: genera `data/audio/{jobId}-scene-XX.mp3`
- `fetch-assets-v1`: genera `data/assets/{jobId}-scene-XX.jpg`

## render-worker

```bash
curl -X POST http://localhost:8580/render -H 'Content-Type: application/json' -d '{"jobId":"..."}'
```
