# Propuesta: pexels-video-supply-benchmark

**Status: READY_FOR_HUMAN_REVIEW** — investigación benchmark-first del SUPPLY de
Pexels Video frente al stack actual Wikimedia/Pixabay. Sin integración de
runtime; la decisión semántica queda pendiente de revisión humana externa con
los contact sheets.

## Contexto

El pipeline actual obtiene assets visuales **estáticos** (imagen) desde
Wikimedia Commons y Pixabay (vía `deterministic_anchor_coverage_v2` +
`visual-fidelity-runtime` OpenCLIP cuando está activado). `generic-content-
pipeline-evaluation` (CLOSED) mostró fallos de cobertura para conceptos difíciles
de stockear (SUPPLY, no corrupción de arquitectura): 16 CLEARLY_RELEVANT /
14 COARSE_BUT_USABLE / 8 FALSE_POSITIVE_OR_UNUSABLE en los 38 canónicos.

Pexels Video es una fuente de **vídeo** stock con API REST. Este cambio mide si
añade cobertura/supply, antes de decidir nada sobre integrarla. NO se toca el
runtime ni el rendering ni los judges visuales.

## Objetivo

Medir, benchmark-first y sin juzgar píxeles, si el resultado RAW de la búsqueda
de vídeo de Pexels mejora el supply disponible para las mismas `queryUsed` que
el pipeline ya usa, separando:

- fallo de SUPPLY (no hay contenido)
- contenido existe pero no portrait
- buen supply (con o sin buen ranking #1)

## Alcance

- Usar la API REST oficial `GET https://api.pexels.com/v1/videos/search` con
  header `Authorization` (nunca impreso ni persistido).
- Búsqueda principal: `query = queryUsed` (raw), `orientation = portrait`,
  `locale = en-US`, `per_page = 15`, `page = 1`. **Sin** filtrar por `size`;
  se inspeccionan las resoluciones disponibles en `video_files`.
- **No** reescribir queries, **no** LLM para adaptarlas, **no**
  OpenCLIP/BLIP/VLM para ordenar. Prioridad: el resultado RAW de Pexels.
- Diagnóstico landscape fallback (una request extra sin `orientation`) solo
  para queries sin supply portrait o sin MP4 portrait >=720x1280, distinguiendo
  `NO_CONTENT` vs `CONTENT_EXISTS_BUT_NOT_PORTRAIT`.
- Máximo absoluto de requests: **100**.

## Dataset (NO modificado)

- `tests/fixtures/asset_visual_fidelity/labels.json` → 38 canónicos
- `tests/fixtures/asset_visual_fidelity/holdout_labels.json` → 20 development
- Total lógico 58 rows. Dedup por `queryUsed` exacto (56 únicas), conservando
  el mapping query → rows/jobs/scenes.

## Revisión humana (sin juicio automático)

- 12 clips centrados: 7 bad del dev-20 + 4 buenos que BLIP falso-rechazó +
  1 CLEARLY_RELEVANT de control. Rank #1 RAW, MP4 portrait, prefer >=720x1280
  (fallback 540x960), sin HLS, máx 12 downloads.
- Contact sheets PNG bajo `data/evaluations/pexels-video-supply-benchmark/`
  (git-ignored): `01-...-temporal-...` (frames 20/50/80 %) y
  `02-...-top3-...` (previews rank 1/2/3).
- Este cambio NO etiqueta clips como buenos/malos. Solo hechos técnicos y
  metadata. La revisión humana externa se hará sobre los PNG.

## Clasificación técnica (provisional)

Mide disponibilidad técnica, NO relevancia semántica:

- `HIGH_SUPPLY`: >= 90 % queries con candidato portrait >=720x1280
- `MEDIUM_SUPPLY`: >= 70 %
- `LOW_SUPPLY`: < 70 %

## Comparación preliminar

Comparar solo cobertura/supply con la evidencia existente (Wikimedia/Pixabay
resolved/unresolved vs cobertura de búsqueda Pexels). **NO afirmar aún
`PEXELS_BETTER`**; la decisión queda pendiente de revisión humana.

## Invariante de producto

- NO integra Pexels en producción.
- NO modifica rendering, OpenCLIP/BLIP/VLM, VisualPlan, ni relablea datasets.
- Harness evaluation-only + tests offline, sin llamadas reales en pytest.
- No merge, no push, no reindex.

Ver `design.md`, `tasks.md` y `results.md`.
