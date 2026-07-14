# Sesión: Visual v2 asset identity and renderability — Phase A

- **Fecha:** 2026-07-11
- **Objetivo:** Corregir los dos bloqueos del sourcing v2 detectados en el primer E2E: colisiones de filenames entre escenas y desalineación del contrato de dimensiones entre Wikimedia y asset_validation.
- **Estado inicial:** E2E_BLOCKED en `data/videos/e2e-v2-rainbow-20260710-213023/`
- **Estado final:** Phase A completada. Tests passing incrementados. Sin regresiones.
- **Agente responsable:** Build A
- **Cambio OpenSpec relacionado:** `stabilize-visual-v2-runtime-contracts` (creado en este Build)
- **Riesgo asumido:** Bajo (cambios acotados al pipeline v2, v1 aislado, sin cambios a bridge/prepare/render)
- **Validaciones realizadas:** Suite completa de tests (`--ignore=data`): 874 passed, 16 failed (mismos 16 que baseline)
- **Archivos creados:**
  - `bin/visual_asset_renderability_v2.py`
  - `tests/test_visual_asset_renderability_v2.py`
  - `openspec/changes/stabilize-visual-v2-runtime-contracts/proposal.md`
  - `openspec/changes/stabilize-visual-v2-runtime-contracts/design.md`
  - `openspec/changes/stabilize-visual-v2-runtime-contracts/tasks.md`
  - `openspec/changes/stabilize-visual-v2-runtime-contracts/specs/asset-identity-renderability.md`
- **Archivos modificados:**
  - `bin/visual_asset_executor_v2.py` — añadido `asset_namespace` con validación
  - `bin/fetch_images_v2.py` — propagación de sceneNumber como namespace
  - `bin/visual_provider_wikimedia_v2.py` — defaults 720x720, filtro OR
  - `bin/asset_validation.py` — dimensiones v2 (OR) vs v1 (AND)
  - `tests/test_visual_asset_executor_v2.py` — tests de namespace
  - `tests/test_fetch_images_v2.py` — tests de sceneNumber + namespace
  - `tests/test_visual_provider_wikimedia_v2.py` — tests de dimensiones v2
  - `tests/test_asset_validation_v2_neutral_metadata.py` — tests de dimensiones v2/v1
- **Comandos ejecutados:**
  - `python3 -m pytest tests/test_visual_asset_renderability_v2.py -v -q` — 17 passed
  - `python3 -m pytest tests/... (237 tests focalizados)` — 237 passed
  - `python3 -m pytest tests/... (all provider/executor/fetch/validation)` — 478 passed, 15 failed (preexistentes)
  - `python3 -m pytest -q --ignore=data` — 874 passed, 16 failed (mismos 16 preexistentes)
- **Resultado:** 874 passing (+54 respecto a baseline de 820), 16 failing (sin cambios). Sin regresiones.
- **Próximos pasos:** Phase B (duración por escena, padding de audio, offsets de subtítulos, preflight agregado).
- **Bloqueos o decisiones pendientes:** Phase B pendiente de diseño e implementación.

---

## 1. Causa raíz de la colisión

El executor generaba filenames usando únicamente `segmentIndex`:
```
assets/seg_001.jpg
```
Cada escena reinicia `segmentIndex` desde 1. Dos escenas con el mismo MIME (`image/jpeg`) producían:
```
assets/seg_001.jpg  (escena 1, segmento 1)
assets/seg_001.jpg  (escena 2, segmento 1)  ← colisión
```

Además, dos GIF de 700x435 pasaban el filtro de Wikimedia (min_width=400, min_height=400) pero asset_validation los bloqueaba luego por dimensiones insuficientes.

## 2. Por qué asset_namespace y no sceneNumber dentro del executor

El executor es agnóstico a la estructura de escenas. Recibe un `sourcing_plan` con `segments` planos (sin sceneNumber). Añadir `sceneNumber` al plan rompería el contrato del router y del canonicalizer. `asset_namespace` es un parámetro opcional que el caller (fetch_images_v2) provee sin que el executor necesite entender escenas. Bridge, prepare y render siguen tratando `assetPath` como string opaco.

## 3. Formato final de filenames

| Namespace | Formato | Ejemplo |
|-----------|---------|---------|
| None | `assets/seg_{:03d}{ext}` | `assets/seg_001.jpg` |
| `scene_001` | `assets/scene_001_seg_{:03d}{ext}` | `assets/scene_001_seg_001.jpg` |
| `scene_002` | `assets/scene_002_seg_{:03d}{ext}` | `assets/scene_002_seg_001.jpg` |

## 4. Compatibilidad cuando namespace=None

El comportamiento es idéntico al anterior. Las llamadas existentes sin `asset_namespace` siguen funcionando.

## 5. Validación de seguridad del namespace

Solo se permite `[a-zA-Z0-9_-]+`. Rechaza: `/`, `\`, `..`, espacios, paths absolutos. Valores inválidos producen error `INVALID_INPUT:asset_namespace` sin escribir archivos.

## 6. Contrato canonical de dimensiones v2

Módulo `bin/visual_asset_renderability_v2.py`:
- `MIN_V2_ASSET_WIDTH = 720`
- `MIN_V2_ASSET_HEIGHT = 720`
- `is_v2_asset_dimension_renderable(w, h)` → `w >= 720 AND h >= 720`

## 7. Diferencia deliberada respecto a v1

| Versión | Operador | Ejemplo 1200x600 |
|---------|----------|-------------------|
| v1 | AND (ambos por debajo) | PASS (1200 >= 720) |
| v2 | AND (ambos >= 720) | BLOCKED (600 < 720) |

## 8. Archivos modificados

(Ver lista arriba en "Archivos modificados")

## 9. Tests ejecutados

17 tests de renderability + 6 tests de dimensiones v2 en Wikimedia + 14 tests de namespace en executor + 5 tests de namespace en fetch_images + 6 tests de dimensiones v2 en asset_validation + 1 test v1 preservado. Total: ~50 tests nuevos.

## 10. Resultado full suite

874 passed (+54), 16 failed (mismos 16 preexistentes: 15 en test_run_job.py, 1 en test_semantic_asset_validation.py). Sin nuevos fallos.

## 11. OpenSpec change utilizado

`stabilize-visual-v2-runtime-contracts` — creado en este Build, Phase A completada.

## 12. Confirmación: bridge/prepare/render no cambiaron

No se modificaron `visual_asset_bridge_v2.py`, `prepare_job.py`, `render_job.py`. El bridge recibe `assetPath` como string opaco igual que antes.

## 13. Confirmación: no se añadieron campos legacy

No se añadió `editorialRole`, `strategy`, `primaryAssetType`, `secondaryAssetType`, `visualTemporalIntent` ni ningún campo v1 a ninguna estructura v2.

## 14. Confirmación: no se añadieron modos de dominio

No se crearon modos historical, science, documentary, general, legacy ni ningún otro. El contrato de dimensiones es neutral.

## 15. Estado pendiente de Phase B

- Duración por escena
- Padding de audio
- Offsets de subtítulos
- Preflight agregado

## 16. Confirmación: no se ejecutó E2E

No se realizaron descargas HTTP reales, audio ni render.
