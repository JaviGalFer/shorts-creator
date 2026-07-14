# Diseño: stabilize-visual-v2-runtime-contracts

## Phase A — Asset identity and renderability contract

### A.1 Contrato canónico de dimensiones v2

Módulo neutral: `bin/visual_asset_renderability_v2.py`

```python
MIN_V2_ASSET_WIDTH = 720
MIN_V2_ASSET_HEIGHT = 720

def is_v2_asset_dimension_renderable(width, height) -> bool:
    # width >= 720 AND height >= 720
```

Política:
- 700x435 → False
- 720x720 → True
- 721x902 → True
- 1200x600 → False
- 600x1200 → False
- 3872x2592 → True
- None/NaN → False (sin excepción)

Sin dependencias de dominio, topic o provider.

### A.2 Asset namespace en executor

```python
def execute_visual_sourcing_plan_v2(
    sourcing_plan, provider_config,
    request_visuals=None, dry_run=True, job_dir=None,
    asset_namespace=None,  # NUEVO
) -> dict:
```

#### Validación de seguridad

`asset_namespace` debe ser:
- None (conserva formato actual) o
- Cadena no vacía compuesta solo por `[a-zA-Z0-9_-]`

Rechaza: `/`, `\`, `..`, espacios, paths absolutos.

Namespace inválido → `INVALID_INPUT` error diagnóstico.

#### Formato de filenames

| Namespace | Formato | Ejemplo |
|-----------|---------|---------|
| None | `assets/seg_{:03d}{ext}` | `assets/seg_001.jpg` |
| `"scene_001"` | `assets/scene_001_seg_{:03d}{ext}` | `assets/scene_001_seg_001.jpg` |
| `"scene_002"` | `assets/scene_002_seg_{:03d}{ext}` | `assets/scene_002_seg_001.jpg` |

Sin directorios anidados. Bridge, prepare, render tratan `assetPath` como string opaco.

#### Propagación interna

`asset_namespace` se pasa a:
- `_try_live_resolution()` → `_compute_asset_paths()`
- `_compute_asset_paths()` usa namespace en el filename

### A.3 Propagación desde fetch_images_v2

`_process_scene()` recibe ahora el dict `scene` completo:

```python
def _process_scene(scene_index, scene, vp, provider_config, dry_run, job_dir):
    scene_number = scene.get("sceneNumber")
    # Validar sceneNumber es entero positivo
    if not isinstance(scene_number, int) or scene_number <= 0:
        # Generar synthetic unresolved, no descargar
        ...
    asset_namespace = f"scene_{scene_number:03d}"
    # Pasar al executor
    execute_visual_sourcing_plan_v2(..., asset_namespace=asset_namespace)
```

No se añade sceneNumber al VisualPlan canonical ni al sourcing plan.

### A.4 Wikimedia provider — filtro de dimensiones v2

```python
def resolve_wikimedia_candidate_v2(
    queries, max_results=5,
    min_width=720,   # era 400
    min_height=720,  # era 400
    user_agent=None, timeout=30,
) -> dict | None:
```

Semántica: rechazar si `width < min_width OR height < min_height`.

Importa `visual_asset_renderability_v2` (no asset_validation).

### A.5 Asset validation — dimensiones v2 vs v1

```python
def validate_asset_file(asset_path, project_root, video_dir=None, is_v2=False):
```

- **v1**: `w < MIN_ASSET_WIDTH and h < MIN_ASSET_HEIGHT` (sin cambios)
- **v2**: `w < 720 or h < 720` (cualquiera por debajo → BLOCKED dimensions_too_small)

Usa `is_v2_asset_dimension_renderable()` del módulo canónico.

### A.6 Contratos no modificados

- VisualPlan canonical (sin sceneNumber)
- Visual Asset Bridge v2 (assetPath opaco)
- Prepare job (assetPath relativo)
- Render job (assetPath en renderTimeline)
- generate_audio, review_job
- Código v1 completo

### A.7 Correcciones post-revisión — Identidad compuesta de resultados

#### A.7.1 sceneNumber explícito en resultados agregados

fetch_images_v2 añade `sceneNumber` a cada resultado (resolved y unresolved) antes de combinarlos. La función `_tag_results_with_scene_number()` crea copias superficiales de cada item y asigna `sceneNumber`. Los resultados sintéticos (de fallos de canonicalizer, router o executor) también incluyen `sceneNumber`.

#### A.7.2 Bridge: asociación por clave compuesta

`_get_explicit_slot(scene_index, claimed, sceneNumber, segmentIndex)` valida y reserva el slot `(sn, si)` directamente, sin depender del orden de las listas.

Solo cuando un resultado no tiene `sceneNumber` (compatibilidad con llamadas directas del executor), el bridge usa el fallback FIFO `_claim_segment(match_queue, si, claimed)` existente.

#### A.7.3 Validación de unicidad

fetch_images_v2 verifica que todos los `sceneNumber` v2 sean enteros positivos únicos antes de ejecutar cualquier canonicalizer, router, executor o provider. Duplicados → fail fast con `ASSET_FAILED`.

#### A.7.4 Contrato finito de dimensiones

`is_v2_asset_dimension_renderable()` usa `math.isfinite()` para rechazar NaN, +Inf, -Inf sin lanzar excepción. También rechaza bool, str, list, dict, negativos y cero.

#### A.7.5 Single source of truth

Wikimedia provider importa `MIN_V2_ASSET_WIDTH` y `MIN_V2_ASSET_HEIGHT` de `visual_asset_renderability_v2` y las usa como defaults. No duplica literales.

## Phase B — Per-scene audio, subtitle and duration contract

### B.1 Duración real persistida en audio.scenes

`generate_audio.py` añade `_get_mp3_duration()` como helper reusable para obtener la duración real de un MP3 vía ffprobe (local o Docker).

En modo per-scene, cada entrada de `data["audio"]["scenes"]` incluye `durationSec` extraída del archivo real:

```json
{
  "sceneNumber": 1,
  "path": ".../scene-01.mp3",
  "exists": true,
  "durationSec": 6.576
}
```

Audio continuo: conserva contrato existente sin cambios.

### B.2 Contrato canonical de ventana de escena

`resolve_scene_window_duration()` en `prepare_job.py`:

```python
def resolve_scene_window_duration(
    target_duration_sec: float,
    actual_audio_duration_sec: float,
) -> float:
    # sceneWindowSec = max(targetDurationSec, actualAudioDurationSec)
```

Validación estricta: rechaza NaN, infinito, booleanos, strings, negativos. Ambos valores deben ser finitos y positivos.

Ejemplos:
- target 8.0, audio 6.576 → 8.0
- target 5.0, audio 6.936 → 6.936
- target 12.0, audio 7.536 → 12.0

### B.3 Timeline visual basado en sceneWindowSec

`build_render_timeline()` acepta `scene_audio_durations: dict[int, float] | None`. En modo no continuo:
1. Lee `scene_audio_durations[sceneNumber]`
2. Calcula `scene_duration = resolve_scene_window_duration(target, actual_audio_dur)`
3. Distribuye segmentos por `durationFraction` sobre `scene_duration`
4. Las entradas son contiguas y monotónicas
5. `startSec` de cada escena = `accumulated_time`

### B.4 Offsets de subtítulos desde renderTimeline

`generate_ass_from_cues()` acepta `scene_offsets: dict[int, float] | None` opcional:

- None → comportamiento anterior (backward-compatible)
- Con offsets → suma offset a `startSec` y `endSec` local de cada cue
- Los cues originales no se mutan
- Si falta offset para una escena con cues, lanza ValueError
- Escena sin cues → no verifica offset

Los offsets se derivan del `renderTimeline`: `min(startSec)` de cada escena.

Para audio continuo: no se aplican offsets (cues ya son globales).

### B.5 Padding del audio en render_job

En modo no continuo, la cadena FFmpeg del audio usa la ventana completa de la escena:

```text
aresample=44100,asetpts=PTS-STARTPTS,apad,atrim=duration={sceneWindowSec}
```

Donde `sceneWindowSec` se calcula desde `renderTimeline`: `max(endSec) - min(startSec)` de las entradas de la escena.

No se usa la duración del primer segmento. `apad` añade silencio al final cuando el audio es más corto. `atrim=duration=sceneWindowSec` garantiza duración exacta.

### B.6 Preflight agregado por escena

`preflight_validate()` agrupa entradas del `renderTimeline` por `sceneNumber`:

- Segmentos contiguos (gap ≤ 0.05s)
- Audio paths consistentes dentro de la escena
- `audio_duration ≤ scene_window + tolerance` (0.10s)
- Ventana visual > audio → OK (se añade padding)
- Audio > ventana → error bloqueante

Audio continuo: conserva comportamiento anterior sin cambios.

### B.7 expected_duration

No continuo: `max(renderTimeline.endSec)`.
No se usa suma de MP3 sin padding ni duración del primer segmento.

### B.8 Backward compatibility

- V1: sin cambios
- Audio continuo: sin cambios en offsets, padding, división por escena, cadena de audio
- `scene_offsets=None` preserva comportamiento original de `generate_ass_from_cues`
- Sin campos legacy ni modos de dominio
