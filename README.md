# shorts-creator

<div align="center">

![stack](https://img.shields.io/badge/stack-Python%20%2B%20FFmpeg%20%2B%20Docker-1f6feb?style=for-the-badge)
![mode](https://img.shields.io/badge/mode-local%20%7C%20Docker-0e8a16?style=for-the-badge)
![tts](https://img.shields.io/badge/TTS-Edge%20voz%20natural-2ea44f?style=for-the-badge)
![llm](https://img.shields.io/badge/LLM-OpenAI--compatible-f0883e?style=for-the-badge)

</div>

shorts-creator es un generador automatizado y configurable de vídeos cortos.

A partir de un tema y de una configuración de producción, coordina la generación del guion, la obtención de recursos visuales, la narración, los subtítulos, el render y la validación final.

El núcleo del pipeline es independiente de la temática. El proyecto está diseñado para adaptarse progresivamente a diferentes duraciones, voces, estilos visuales y formatos de contenido.

Visual Plan V2 es el único contrato visual canónico. La arquitectura modular V2 está completa: los dominios viven en `src/shorts_creator/` y `bin/` mantiene adaptadores CLI delgados.

## Estado del proyecto

Pipeline V2 funcional y E2E técnico demostrado. Docker se utiliza para render y servicios auxiliares; `bin/run_job.py` es el orquestador canónico.

El primer E2E técnico real solicitó 30s y generó un MP4 de aproximadamente 20.88s: el pipeline técnico pasó, pero incumplió el rango solicitado. El fitting post-TTS bounded y la comprobación final de cumplimiento de duración del MP4 están implementados; aún requieren una nueva validación E2E real.

La estimación WPM del guion es bootstrap no bloqueante; tras TTS, la duración medida y el fitting bounded son la autoridad. Suite completa más reciente en la rama activa: **`1198 passed, 51 skipped, 0 failed`**.

Referencias:
- `docs/project/current-state.md` — estado detallado
- `docs/architecture/modular-v2-transformation-roadmap.md` — roadmap de transformación modular

## Qué puedes configurar

### Disponible actualmente

| Control | Superficie | Descripción |
|---------|-----------|-------------|
| Tema o instrucción | `--topic` | Tema del vídeo |
| Duración | `--duration`, `--duration-profile`, `--duration-target`, `--duration-min`, `--duration-max`, `--strictness` | Duración exacta, perfil predefinido o rango con nivel de tolerancia |
| Modelo LLM | `--model` | Modelo del proveedor LLM (OpenAI-compatible) |
| Proveedor TTS | `--tts-provider`, `TTS_PROVIDER` | Edge TTS es el provider canónico operativo; el registry contempla alternativas, pero ElevenLabs no está confirmado como path E2E per-scene |
| Voz | `--voice`, `TTS_VOICE` | Voz para la narración (default: `es-ES-AlvaroNeural`) |
| Timing de subtítulos | `--subtitle-timing-provider`, `SUBTITLE_TIMING_PROVIDER` | `auto`, `edge_tts`, `whisper` o `estimated` |
| Estilo de subtítulos | `--subtitle-style` | `documentary_safe`, `shorts_dynamic`, `shorts_upper_dynamic` |
| Providers visuales | Wikimedia Commons, Pixabay | Imágenes de Wikimedia (sin API key) y Pixabay (requiere `PIXABAY_API_KEY`) |
| Ejecución parcial | `--stop-after` | Detener tras `script`, `assets`, `audio`, `prepare`, `render` o `validate` |
| Planificación | `--dry-run` | Mostrar plan de ejecución sin ejecutar |

### Dirección del producto

La arquitectura está evolucionando para ofrecer una configuración unificada que en el futuro podrá incluir:

- **Duración, idioma y voz** configurables
- **Subtítulos** activables/desactivables con estilo y posición ajustables
- **Música** de fondo seleccionable
- **Imágenes o clips** de fondo configurables
- **Estrategia visual** seleccionable
- **Calidad** de render ajustable
- **Políticas de revisión** configurables
- **Publicación** automatizada en destino

Estos controles son dirección del producto, no capacidades actuales. La futura interfaz web podrá exponerlos cuando estén implementados.

## Pipeline canónico

```
script → assets → audio → prepare → render → validate
```

| Etapa | Script | Entrada | Salida |
|-------|--------|---------|--------|
| Script | `bin/generate_script.py` | Tema, duración, perfil | `metadata.json` con guion V2 |
| Assets | `bin/fetch_images_v2.py` | `metadata.json` | Imágenes en `assets/` |
| Audio | `bin/generate_audio.py` | `metadata.json` | Narración MP3 por escena |
| Prepare | `bin/prepare_job.py` | `metadata.json` | Subtítulos ASS, timeline de render |
| Render | `bin/render_job.py` | `metadata.json` | `video.mp4` |
| Validate | `bin/validate_job.py` | `metadata.json` | Validación PASS/FAIL |

Assets visuales V2 se almacenan bajo `assets/` en el directorio del job.

### Orquestador unificado

```bash
python bin/run_job.py --topic "Tema del vídeo" --duration 42
```

Ejecuta las seis etapas en orden, verifica contratos post-etapa y produce metadata trazable con historial de orquestación. Soporta `--stop-after` para ejecución parcial y `--dry-run` para planificación.

## Inicio rápido

### Requisitos

- Docker 24+
- Python 3.10+
- API key de LLM (OpenAI-compatible)

### Instalación

```bash
cp .env.example .env
# Editar .env con LLM_API_KEY y demás variables
pip install -r requirements.txt
```

### Uso básico

```bash
python bin/run_job.py --topic "Cómo se forma un arcoíris" --duration 42
```

Ver plan sin ejecutar:

```bash
python bin/run_job.py --topic "Prueba" --duration 35 --dry-run
```

Ejecutar solo hasta una etapa:

```bash
python bin/run_job.py --topic "Prueba" --duration 35 --stop-after script
```

### Perfiles de duración

| Preset | Rango | Uso |
|--------|-------|-----|
| `quick_30` | 27-33s | Rápido ~30 s |
| `standard_45` | 41-49s | Estándar ~45 s |
| `deep_60` | 55-65s | Detallado ~60 s |

```bash
python bin/run_job.py --topic "Tema" --duration-preset standard_45
python bin/run_job.py --topic "Tema" --duration 37 --duration-tolerance 2
```

Los presets son atajos de configuración: `--duration N` usa una tolerancia simétrica automática y no queda limitado por ningún preset. La arquitectura admite nuevos presets sin cambiar el fitting.

La planificación inicial también escala con la duración, con una referencia de aproximadamente seis segundos por escena: 30s prefiere 5 escenas y 60s prefiere 10. El fitting posterior conserva la estructura y ajusta solo los voiceovers.

## Configuración

Las variables de entorno se configuran en `.env`. Ver `.env.example` para la lista completa.

### Obligatorias

| Variable | Descripción |
|----------|-------------|
| `LLM_API_KEY` | API key del proveedor LLM |
| `LLM_PROVIDER` | `openai` — Proveedor LLM; actualmente solo se implementa un cliente OpenAI-compatible |

### TTS (narración)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `TTS_PROVIDER` | `edge_tts` | Proveedor TTS (`edge_tts` o `elevenlabs`) |
| `TTS_VOICE` | `es-ES-AlvaroNeural` | Voz TTS |
| `SPOKEN_WORDS_PER_MINUTE` | `110` | Ritmo de habla estimado |

### Subtítulos

| Variable | Default | Descripción |
|----------|---------|-------------|
| `SUBTITLE_TIMING_PROVIDER` | `auto` | `auto`, `edge_tts`, `whisper` o `estimated` |
| `WHISPER_MODEL` | `tiny` | Modelo Whisper (`tiny`, `base`, `small`, etc.) |

## Providers visuales

| Provider | Estado | API key |
|----------|--------|---------|
| Wikimedia Commons | Activo, implementado | No necesita |
| Pixabay | Activo, implementado | `PIXABAY_API_KEY` |
| Pexels | Planificado, deshabilitado, no implementado | — |
| FreeAI | Deshabilitado, no implementado | — |
| Pollinations | Deshabilitado, no implementado | — |

## Arquitectura actual

```
src/shorts_creator/     # Dominios modulares V2
  contracts/            # Contratos compartidos
  pipeline/             # Orquestación
  script/ audio/ assets/ rendering/ validation/ infrastructure/
bin/                    # Adaptadores CLI y compatibilidad fina
  run_job.py            # Orquestador canónico
  generate_script.py    # Generación de guion
  fetch_images_v2.py    # Obtención de imágenes (V2)
  generate_audio.py     # Narración TTS
  prepare_job.py        # Subtítulos y timeline
  render_job.py         # Render FFmpeg
  validate_job.py       # Validación post-render
data/
  videos/{jobId}/       # Un directorio por job: metadata.json, assets/, scenes/, video.mp4
docker-compose.yml      # n8n, Postgres, render-worker (infraestructura auxiliar)
```

## Docker y n8n

El stack Docker Compose incluye:

- **n8n** (`shorts-n8n`): servicio disponible para automatizaciones. Los workflows exportados (`workflow-*.json` en la raíz) son legacy o alternativos. `bin/run_job.py` es el orquestador canónico del pipeline V2.
- **Postgres** (`shorts-postgres`): base de datos para n8n.
- **render-worker**: worker para render remoto (opcional).

n8n no es el orquestador canónico del pipeline V2.

## Limitaciones conocidas

- `ffprobe` no está instalado en el host; la medición de duración de audio usa Docker como fallback.
- La aceleración GPU no está implementada; el render usa CPU.
- La estimación bootstrap WPM es telemetría no bloqueante; la duración real del audio TTS y el fitting post-TTS son autoritativos. El fitting se validó en E2E reales (`quick_30` y `deep_60`).
- No hay publicación automática ni integración con redes sociales.

## Documentación adicional

| Documento | Descripción |
|-----------|-------------|
| `docs/project/architecture.md` | Arquitectura actual y futura |
| `docs/project/integrations.md` | Integraciones validadas |
| `docs/project/environment.md` | Entorno de desarrollo |
| `docs/project/current-state.md` | Estado actual detallado |
| `docs/architecture/modular-v2-transformation-roadmap.md` | Roadmap de transformación modular |
| `docs/runbooks/local-development.md` | Runbook de desarrollo local |
| `docs/decisions/` | ADRs (Architecture Decision Records) |
| `openspec/changes/` | Cambios activos y cerrados |

## Uso responsable, licencias y atribuciones

- El contenido generado es responsabilidad del usuario.
- Las imágenes obtenidas de Wikimedia Commons y Pixabay están sujetas a sus respectivas licencias.
- Edge TTS es gratuito pero sujeto a los términos de Microsoft.
- Los modelos LLM tienen sus propios términos de uso y costes asociados.
- Este proyecto no afilia ni representa a ningún proveedor externo.
