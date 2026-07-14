# Sesión: Visual v2 Phase A — Correcciones post-revisión

- **Fecha:** 2026-07-11
- **Objetivo:** Cerrar los cuatro huecos detectados en Phase A del OpenSpec `stabilize-visual-v2-runtime-contracts` antes de poder marcarla como completada.
- **Estado inicial:** Phase A implementada (874 passed, 16 failed). Cuatro gaps identificados en revisión.
- **Estado final:** Phase A corregida. 899 passed, 16 failed (mismos preexistentes). Sin regresiones. Phase A puede cerrarse.
- **Agente responsable:** Build A (correcciones)
- **Cambio OpenSpec relacionado:** `stabilize-visual-v2-runtime-contracts` (actualizado)
- **Riesgo asumido:** Bajo. Cambios acotados a bridge, fetch_images, provider y renderability. Sin cambios a executor, prepare, render, v1.
- **Validaciones realizadas:** Suite completa: 899 passed, 16 failed (mismos 16 preexistentes).
- **Archivos modificados:**
  - `bin/visual_asset_renderability_v2.py` — NaN/Infinity fix con math.isfinite
  - `bin/visual_provider_wikimedia_v2.py` — importa constantes canónicas
  - `bin/fetch_images_v2.py` — sceneNumber en resultados + unicidad
  - `bin/visual_asset_bridge_v2.py` — asociación por (sceneNumber, segmentIndex)
  - `tests/test_visual_asset_renderability_v2.py` — tests NaN/Infinity/bool/list/dict
  - `tests/test_visual_provider_wikimedia_v2.py` — tests constantes canónicas
  - `tests/test_visual_asset_bridge_v2.py` — tests explicit sceneNumber (14 tests)
  - `tests/test_fetch_images_v2.py` — tests sceneNumber in results + duplicates
  - `openspec/changes/stabilize-visual-v2-runtime-contracts/design.md`
  - `openspec/changes/stabilize-visual-v2-runtime-contracts/tasks.md`
  - `openspec/changes/stabilize-visual-v2-runtime-contracts/specs/asset-identity-renderability.md`
- **Archivos creados:** Este session doc.
- **Archivos no modificados:** executor, router, plan, asset_validation, prepare, render, run_job, audio, v1, providers no-Wikimedia.
- **Comandos ejecutados:**
  - `python3 -m pytest ... (145 tests focalizados)` — 145 passed
  - `python3 -m pytest ... (349 tests) — 349 passed
  - `python3 -m pytest -q --ignore=data` — 899 passed, 16 failed
  - `git diff --check` — limpio
- **Resultado:** 899 passed (+25 respecto a post-Build-A, +79 respecto a baseline de 820). 16 failed (sin cambios).
- **Próximos pasos:** Phase B (duración por escena, padding de audio, offsets de subtítulos, preflight agregado).
- **Bloqueos o decisiones pendientes:** Ninguno. Phase A ready to close.

---

## 1. Fallo de asociación encontrado

El bridge original usa `_claim_segment(match_queue, si, claimed)` que busca el primer `(sn, si)` en `match_queue` donde `si` coincide. `match_queue` está ordenado por sceneNumber. Resultados sin sceneNumber de escenas distintas se asignaban por orden FIFO:

```
match_queue = [(1, 1), (2, 1)]
resolved (scene 2) → _claim_segment(..., 1, ...) → encuentra (1, 1) primero → INCORRECTO
```

## 2. Ejemplo scene 1 unresolved / scene 2 resolved

Con una metadata de dos escenas (ambas segmentIndex=1) y results:
- resolved: `[{segmentIndex: 1, sceneNumber: 2, path: "assets/scene_002_seg_001.jpg"}]`
- unresolved: `[{segmentIndex: 1, sceneNumber: 1, status: "NO_RESULTS"}]`

El bridge ahora asigna correctamente usando `_get_explicit_slot()`:
- sceneNumber=2, segmentIndex=1 → slot (2, 1) → scene 2 PASS
- sceneNumber=1, segmentIndex=1 → slot (1, 1) → scene 1 FAIL

## 3. Causa raíz en el bridge

`_claim_segment()` es un matcher FIFO por segmentIndex. No distingue escenas. La única forma de evitar inversiones es que los resultados lleven sceneNumber explícito.

## 4. Nuevo contrato de identidad compuesta

La identidad canónica de un resultado v2 es `(sceneNumber, segmentIndex)`.

`_get_explicit_slot(scene_index, claimed, sn, si)`:
1. Valida que `sn` existe en `scene_index`
2. Valida que `si` existe en `scene_index[sn]`
3. Verifica que `(sn, si)` no está en `claimed`
4. Si todo ok → devuelve el slot; si no → devuelve `(None, reason)`

## 5. Fallback compatible para resultados sin sceneNumber

Los resultados que no llevan `sceneNumber` (llamadas directas del executor, tests existentes) siguen usando `_claim_segment(match_queue, si, claimed)` con el comportamiento FIFO original.

## 6. Validación de sceneNumber positivo y único

fetch_images_v2 ahora valida antes de ejecutar:
- Todos los sceneNumber son enteros positivos
- No hay duplicados
- Duplicados → ASSET_FAILED, sin llamar al executor

## 7. Corrección NaN/infinito

`is_v2_asset_dimension_renderable()` usa `math.isfinite()` para rechazar NaN, +Inf, -Inf sin lanzar excepción. También rechaza bool, str, list, dict, negativos y cero.

```python
if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
    return False
if isinstance(width, bool) or isinstance(height, bool):
    return False
if not math.isfinite(width) or not math.isfinite(height):
    return False
```

## 8. Importación de constantes canónicas en Wikimedia

```python
from visual_asset_renderability_v2 import (
    MIN_V2_ASSET_WIDTH,
    MIN_V2_ASSET_HEIGHT,
)

def resolve_wikimedia_candidate_v2(
    queries, max_results=5,
    min_width=MIN_V2_ASSET_WIDTH,   # ya no es literal 720
    min_height=MIN_V2_ASSET_HEIGHT,  # ya no es literal 720
    ...
```

## 9. Archivos modificados

Ver lista arriba.

## 10. Tests añadidos

- renderability: 10 tests (NaN, Infinity, -Inf, bool, list, dict, negative, zero, both NaN)
- wikimedia: 4 tests (default width/height match canonical, explicit overrides)
- bridge: 7 tests explicit matching + 5 invalid sceneNumber + 2 backward compat = 14 tests
- fetch_images: 2 tests (sceneNumber in results, duplicate detection)

Total: ~30 tests nuevos.

## 11. Resultados focalizados

- 145/145 (renderability + wikimedia + bridge + fetch_images)
- 349/349 (suite completa de componentes v2)

## 12. Resultado de suite completa

899 passed (+25), 16 failed (mismos 16 preexistentes: 15 test_run_job.py + 1 test_semantic_asset_validation.py)

## 13. Comparación con baseline

| Métrica | Baseline | Build A | Correcciones |
|---------|----------|---------|-------------|
| Passed | 820 | 874 | 899 |
| Failed | 16 | 16 | 16 |
| New tests | 0 | ~54 | ~30 |

## 14. Confirmación de que Phase B no se inició

No se modificaron contratos de audio, subtítulos, duración, offsets ni preflight.

## 15. Confirmación de que no se ejecutó E2E

Sin HTTP real, sin audio, sin render.

## 16. Confirmación de ausencia de campos legacy

Sin editorialRole, strategy, primaryAssetType, secondaryAssetType, visualTemporalIntent en ninguna estructura v2.

## 17. Confirmación de ausencia de modos de dominio

Sin modos historical, science, documentary, general, legacy. Contratos neutrales.

## 18. Decisión final sobre cierre de Phase A

**Phase A puede marcarse como completada.** Los cinco gaps están corregidos:
1. Bridge asocia por (sceneNumber, segmentIndex) explícito ✓
2. fetch_images_v2 añade sceneNumber a todos los resultados ✓
3. Wikimedia importa constantes canónicas (single source of truth) ✓
4. renderability maneja NaN/Infinity sin excepción ✓
5. sceneNumber duplicados rechazados antes de ejecutar ✓

Phase B puede iniciarse.
