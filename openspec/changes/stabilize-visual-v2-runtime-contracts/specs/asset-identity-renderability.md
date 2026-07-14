# Specs: stabilize-visual-v2-runtime-contracts

## REQ-001: Asset renderability dimension contract v2

El sistema DEBE definir un contrato canónico de dimensiones mínimas para assets v2.

- MIN_V2_ASSET_WIDTH = 720
- MIN_V2_ASSET_HEIGHT = 720
- Un asset es renderizable si width >= 720 AND height >= 720
- La función `is_v2_asset_dimension_renderable(width, height)` DEBE devolver False sin excepción para: None, NaN, +Infinity, -Infinity, bool, str, list, dict, negativos y cero.
- La función DEBE usar `math.isfinite()` para detectar NaN e infinito.

## REQ-002: Asset namespace en executor

El executor DEBE aceptar un parámetro opcional `asset_namespace: str | None = None`.

- Si es None: formato `assets/seg_{:03d}{ext}` (sin cambios)
- Si tiene valor: formato `assets/{namespace}_seg_{:03d}{ext}`
- El namespace DEBE validarse: solo `[a-zA-Z0-9_-]+`
- Valores peligrosos (`/`, `\`, `..`, espacios, paths absolutos) DEBEN rechazarse con INVALID_INPUT
- Bridge, prepare, render DEBEN seguir tratando assetPath como string opaco

## REQ-003: Propagación de sceneNumber desde fetch_images_v2

fetch_images_v2 DEBE:

- Validar que todos los sceneNumber v2 sean enteros positivos únicos antes de ejecutar
- Duplicados → fail fast con ASSET_FAILED, sin llamar al executor
- Invalid sceneNumber → synthetic unresolved, sin descargas
- Añadir `sceneNumber` a cada resultado (resolved y unresolved) mediante `_tag_results_with_scene_number()`
- No añadir sceneNumber al VisualPlan ni al sourcing plan
- Formato namespace: `f"scene_{scene_number:03d}"`

## REQ-004: Bridge — asociación por clave compuesta

El bridge DEBE:

- Si un resultado tiene `sceneNumber` entero positivo: usar `_get_explicit_slot()` para mapear directamente por `(sceneNumber, segmentIndex)`
- Validar que sceneNumber existe en scene_index y segmentIndex existe en esa escena
- Rechazar pares ya reclamados → orphanedResults
- Nunca asignar un resultado con sceneNumber a una escena distinta mediante fallback
- Si un resultado NO tiene `sceneNumber`: usar fallback FIFO `_claim_segment()` (compatibilidad backward)
- NO parsear assetPath, namespace ni filename para determinar la escena

## REQ-005: Wikimedia provider — single source of truth

El provider Wikimedia DEBE:

- Importar `MIN_V2_ASSET_WIDTH` y `MIN_V2_ASSET_HEIGHT` de `visual_asset_renderability_v2`
- Usarlas como defaults de `min_width` y `min_height`
- Permitir overrides explícitos para tests o callers especializados
- No duplicar literales 720
- No importar `asset_validation.py`

## REQ-006: Asset validation — dimensiones v2 vs v1 (sin cambios)

- v2: `dimensions_too_small` si width < 720 OR height < 720 → BLOCKED
- v1: `dimensions_too_small` si width < 720 AND height < 720 (sin cambios)

## REQ-007: Identidad v2 (sceneNumber, segmentIndex)

La identidad canónica de un resultado v2 es el par `(sceneNumber, segmentIndex)`.

Esta identidad DEBE provenir de `sceneNumber` explícito en el resultado. NO DEBE inferirse de:
- Orden de arrays (resolvedAssets, unresolvedSegments, scenes)
- assetPath
- filename
- namespace
- topic o provider

## REQ-008: sceneNumber único y positivo

fetch_images_v2 DEBE exigir sceneNumber entero positivo y único para cada escena v2.
