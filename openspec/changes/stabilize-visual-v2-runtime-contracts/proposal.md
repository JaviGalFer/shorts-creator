# Propuesta: stabilize-visual-v2-runtime-contracts

## Problema actual

El primer E2E live del pipeline visual v2 reveló dos bloqueos estructurales:

1. **Colisiones de filenames entre escenas**: el executor genera paths `assets/seg_NNN.ext` usando solo `segmentIndex`. Como cada escena reinicia `segmentIndex` desde 1, dos escenas con el mismo MIME intentan escribir `assets/seg_001.jpg`, provocando colisiones.

2. **Desalineación del contrato de dimensiones**: Wikimedia acepta imágenes con dimensiones inconsistentes (ej. GIF de 700x435 pasa el filtro `min_width=400/min_height=400` pero asset_validation lo bloquea porque ambas dimensiones están por debajo de 720). El contrato de dimensiones no está unificado entre provider, executor y validation.

## Solución propuesta

### Phase A — Asset identity and renderability contract (este Build)

1. **Namespace de assets**: añadir `asset_namespace` opcional a `execute_visual_sourcing_plan_v2` para prefijar filenames, eliminando colisiones entre escenas sin romper el contrato opaco de `assetPath`.

2. **Contrato canónico de dimensiones v2**: módulo neutral `visual_asset_renderability_v2.py` como única fuente de verdad para dimensiones mínimas (720x720, política `width >= 720 AND height >= 720`). Wikimedia provider usa este contrato. Asset validation lo usa para v2 metadata.

3. **Propagación desde fetch_images_v2**: cada escena pasa su `sceneNumber` como `asset_namespace=f"scene_{scene_number:03d}"`.

### Phase B — Per-scene audio, subtitle and duration contract (Build B — completado)

Implementación del contrato temporal por escena para audio no continuo:

- **Duración real por escena**: `audio.scenes[].durationSec` desde ffprobe del MP3 real
- **Ventana canónica**: `sceneWindowSec = max(targetDurationSec, actualAudioDurationSec)`
- **Timeline distribuido**: segmentos sobre `sceneWindowSec`, no `targetDurationSec`
- **Offsets de subtítulos**: desde `renderTimeline`, cues locales → globales
- **Padding de audio**: cadena `aresample → asetpts=PTS-STARTPTS → apad → atrim=duration=sceneWindowSec`
- **Preflight agregado**: validación por escena, no por segmento individual
- **Continuous audio y V1**: sin regresiones
- **Resultado**: 947 passed / 16 failed (mismos preexistentes), +48 tests nuevos

## Alcance (Phase A)

- Nuevo módulo `visual_asset_renderability_v2.py`
- Nuevo parámetro `asset_namespace` en executor
- Namespace propagado desde fetch_images_v2 usando sceneNumber
- Validación de seguridad del namespace
- Wikimedia provider actualizado al contrato v2
- Asset validation actualizado para v2

## Fuera de alcance

- Audio, subtítulos, duración de escenas, FFmpeg
- Deduplicación por sourceUrl
- Ranking por área
- Validación semántica photograph/diagram
- Modos de dominio (historical, science, etc.)
- Campos legacy

## Criterios de éxito (Phase A)

1. Sin colisiones de filenames cuando dos escenas tienen segmentIndex=1 y mismo MIME
2. Wikimedia rechaza imágenes < 720 en cualquier dimensión
3. Asset validation bloquea v2 assets con dimensiones < 720 en cualquier dimensión
4. V1 behavior completamente preservado
5. Bridge, prepare, render sin cambios
6. Sin campos legacy ni modos de dominio
7. Tests passing count aumenta respecto a baseline (820/16)

## Riesgos

- Bajo: cambios acotados al pipeline v2, v1 aislado
- Compatibilidad hacia atrás: `asset_namespace=None` conserva formato actual

## Resultado final

### Change completado — E2E_PASS

**Job:** `e2e-pixabay-20260714-184248`

- ASSETS_READY 5/5 (Wikimedia + Pixabay multiproveedor)
- Render 30.0s, 1080x1920, audio presente
- validate_job PASS, 0 errors
- subtitleCoverageValidation PASS, assetValidation PASS, technicalValidation PASS, qualityGate PASS

**Baseline de tests:** 1132 passed, 16 failed (preexistentes en test_run_job.py y test_semantic_asset_validation.py), 0 regresiones

**Builds ejecutados:** A (asset identity), B (temporal contract), C (Docker API/Wikimedia batch), D (Pixabay/duration/subtitle validation)

### Contratos estabilizados

1. Wikimedia + Pixabay multiproveedor con failover real
2. Identidad de assets por `(sceneNumber, segmentIndex)`
3. Contrato de renderabilidad v2: `width >= 720 AND height >= 720`
4. Duración real de audio por escena (`audio.scenes[].durationSec`)
5. `sceneWindowSec = max(targetDurationSec, actualAudioDurationSec)`
6. Padding de audio: `apad + atrim=duration=sceneWindowSec`
7. Timeline multi-segmento distribuido sobre sceneWindowSec
8. Subtítulos per-scene con offsets globales desde renderTimeline
9. Validación ASS real (parse Dialogue + comparar tiempos/texto)
10. Validación de duración por cuatro niveles (segment, scene, timeline, total)

### Trabajos futuros

- Generación nativa de VisualPlan v2 desde `generate_script.py`
- Calidad y relevancia semántica de assets
- Mejora de voz (Edge TTS)
- Integración del pipeline v2 con n8n
