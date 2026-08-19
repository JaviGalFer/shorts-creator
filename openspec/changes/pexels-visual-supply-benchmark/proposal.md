# Propuesta: pexels-visual-supply-benchmark

**Status: COMPLETED / VERIFIED / CLOSED** — investigación benchmark-first del
SUPPLY visual de Pexels (Video + Photos) frente al stack actual
Wikimedia/Pixabay, cerrada tras la revisión humana externa de los 3 contact
sheets. **Sin integración de runtime.** Decisión:
**`PEXELS_CONDITIONAL_PROVIDER_PROMISING`**.

## Contexto

El pipeline actual obtiene assets visuales **estáticos** (imagen) desde
Wikimedia Commons y Pixabay (vía `deterministic_anchor_coverage_v2` +
`visual-fidelity-runtime` OpenCLIP cuando está activado). `generic-content-
pipeline-evaluation` (CLOSED) mostró fallos de SUPPLY para conceptos difíciles
de stockear (no corrupción de arquitectura): 16 CLEARLY_RELEVANT /
14 COARSE_BUT_USABLE / 8 FALSE_POSITIVE_OR_UNUSABLE en los 38 canónicos.

`pexels-video-supply-benchmark` (anterior, renombrado aquí) ya midió el SUPPLY
de **Pexels Video**: cobertura 56/56 y HIGH_SUPPLY (>=720x1280 y >=1080x1920 =
1.0). Este cambio **amplía** la investigación a **Pexels Photos** y añade una
comparación visual directa contra el asset actual (Wikimedia/Pixabay).

Preguntas que queremos responder (sin decidir todavía):

1. ¿Pexels Video ofrece mejor supply/relevancia?
2. ¿Pexels Photos ofrece mejores candidatos que las imágenes
   Wikimedia/Pixabay actualmente seleccionadas?
3. ¿Pexels merece convertirse posteriormente en provider de producción?

## Objetivo

Medir, benchmark-first y sin juzgar píxeles, el resultado RAW de Pexels
(Photos + Video) para las mismas `queryUsed` que el pipeline ya usa, separando
fallo de SUPPLY de "contenido existe pero no portrait", y dejando evidencia de
revisión directa (CURRENT vs PEXELS) para la decisión semántica humana.

## Alcance

- **Pexels Video** (previo): `GET /v1/videos/search`, `orientation=portrait`,
  `locale=en-US`, `per_page=15`. Resultado: cobertura 56/56, HIGH_SUPPLY.
- **Pexels Photos** (nuevo): `GET /v1/search`, mismos parámetros.
  - Sin filtrar por `size`; se inspeccionan las resoluciones en `src`.
  - Sin reescritura de queries, sin LLM, sin OpenCLIP/BLIP/VLM, sin reranking.
- **Diagnóstico** (Photos): una request adicional sin `orientation` solo si una
  query da 0 portrait o ningún original portrait >=720x1280; clasifica
  `NO_CONTENT` / `CONTENT_EXISTS_BUT_NOT_PORTRAIT` / `PORTRAIT_SUPPLY_OK`.
  Presupuesto: **56 principales + máx 14 diagnósticos = 70** requests nuevas.
- **Revisión humana**: mismas 12 queries focales que Video (7 dev-bad + 4
  buenos que BLIP falso-rechazaba + 1 CLEARLY_RELEVANT control). Rank #1 raw.
  Downloads máx 12 originales rank#1; ranks 2/3 con variantes grandes (no
  originales) para el contact sheet.

## Dataset (NO modificado)

- `tests/fixtures/asset_visual_fidelity/labels.json` → 38 canónicos
- `tests/fixtures/asset_visual_fidelity/holdout_labels.json` → 20 development
- Total lógico 58 rows → 56 queryUsed únicas (dedup exacto). Se conserva el
  mapping query → dataset/job/scene/segment/current asset (`assetPath`).

## Comparación directa (03)

`03-pexels-photo-vs-current-contact-sheet.png`: para cada una de las 12 queries,
una fila de 4 columnas: CURRENT (assetPath registrado, Wikimedia/Pixabay) vs
PEXELS #1 / #2 / #3 (ranking raw). Aspect ratio preservado, sin crop
destructivo, sin solapamiento, imagen completa visible, labels legibles. Esto
permite revisar si Pexels Photos habría dado una opción mejor que el asset
actual.

## NO hacer juicio semántico

OpenCode NO clasifica imágenes: no se generan CLEARLY_RELEVANT /
COARSE_BUT_USABLE / FALSE_POSITIVE. Aunque el supply sea alto, **NO se afirma
`PEXELS_PHOTOS_BETTER`**. La revisión es externa.

## Clasificación técnica (provisional)

Mide solo disponibilidad técnica, no relevancia:

- `HIGH_SUPPLY`: >= 90 % queries con candidato portrait >=720x1280
- `MEDIUM_SUPPLY`: >= 70 %
- `LOW_SUPPLY`: < 70 %

## Invariante de producto

- NO integra Pexels en producción (ni Photos ni Video).
- NO modifica rendering, OpenCLIP/BLIP/VLM, VisualPlan, ni relablea datasets.
- NO borra evidencia existente del benchmark de vídeo.
- Harness evaluation-only + tests offline, sin llamadas reales en pytest.
- No merge, no push, no reindex.

Ver `design.md`, `tasks.md` y `results.md`.
