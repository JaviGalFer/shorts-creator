# Design: pexels-visual-supply-benchmark

**Status: COMPLETED / VERIFIED / CLOSED** — investigación benchmark-first, sin
cambios de runtime. Cerrado tras la revisión humana externa; decisión
**`PEXELS_CONDITIONAL_PROVIDER_PROMISING`**.

## Arquitectura de evaluación (sin cambios de runtime)

```
tests/fixtures/asset_visual_fidelity/labels.json          ← 38 canónicos (NO tocados)
tests/fixtures/asset_visual_fidelity/holdout_labels.json  ← 20 development (NO tocados)
        │  (58 rows lógicos; dedup por queryUsed exacto = 56 requests)
        ▼
tools/pexels_video_supply_benchmark.py  ← Pexels Video (evaluation-only, urllib)
        │   GET /v1/videos/search · orientation=portrait · per_page=15
        ▼
tools/pexels_photo_supply_benchmark.py  ← Pexels Photos (evaluation-only, urllib)
        │   GET /v1/search · orientation=portrait · per_page=15
        ▼
data/evaluations/pexels-visual-supply-benchmark/*.json    ← git-ignored
        │   photo-supply-benchmark.json · photo-review-images.json
        │   (+ video evidence reutilizado de pexels-video-supply-benchmark/)
        ▼
photos/ (12 rank#1 originales + previews 2/3) + clips/frames (vídeo, previo)
        ▼
01-pexels-video-temporal-contact-sheet.png  (Docker ffmpeg; frames 20/50/80%; corregido)
02-pexels-top3-search-results.png           (previews vídeo rank 1/2/3)
03-pexels-photo-vs-current-contact-sheet.png (CURRENT vs PEXELS #1/#2/#3)
        ▼
openspec/changes/pexels-visual-supply-benchmark/results.md  ← informe
```

## API / contrato (Photos)

- Endpoint: `GET https://api.pexels.com/v1/search`
- Header `Authorization: <PEXELS_API_KEY>` + `User-Agent` explícito (sin UA el
  API responde 403, igual que en vídeo).
- Búsqueda principal: `query`=raw `queryUsed`, `orientation=portrait`,
  `locale=en-US`, `per_page=15`, `page=1`. NO se filtra por `size`.
- Diagnóstico: segunda request SIN `orientation` solo si la query no tiene
  portrait o ningún original portrait >=720x1280.
- Presupuesto de requests nuevas: **56 principales + máx 14 diagnósticos = 70**
  (la pasada de vídeo ya consumió su propio presupuesto de 100).

### Clave (no leak)

- Resolución: proceso (env) primero, luego `.env` del proyecto
  (`PEXELS_API_KEY`).
- La clave **nunca** se imprime ni se persiste en ningún artefacto.

## Parsing / normalización (Photo)

`parse_photo_search_response` devuelve por foto: `id`, `width`/`height`
(origen), `url`, `photographer`, `photographer_url`, `photographer_id`,
`avg_color`, `alt` y `src` (`original`, `large2x`, `large`, `medium`, `small`,
`portrait`, `landscape`, `tiny`).

## Métricas de SUPPLY (Photo)

Por query: `total_results`, `candidatesReturned`, `originalPortraitCount`,
`originalPortraitAtLeast720x1280`, `originalPortraitAtLeast1080x1920`,
`hasAtLeastOnePortraitCandidate`, `hasAtLeastOne720x1280Candidate`,
`hasAtLeastOne1080x1920Candidate`.

Agregado: `queriesWithAnyResult`, `queriesWithZeroResults`,
`medianTotalResults`, `candidatesReturned`, cobertura canonical/development,
fracción >=720x1280, fracción >=1080x1920, rate-limit final.

Clasificación técnica: HIGH_SUPPLY >= 0.90, MEDIUM_SUPPLY >= 0.70,
LOW_SUPPLY < 0.70. Solo disponibilidad; NO relevancia semántica.

## Revisión humana (Photos)

- Mismas 12 queries focales: 7 dev-bad + 4 buenos que BLIP falso-rechazaba +
  1 CLEARLY_RELEVANT control.
- Reutiliza `rawResults` persistido → sin nuevas búsquedas para el review.
- Rank #1: descargar `src.original` (máx 12).
- Ranks #2/#3: usar `src.large2x` (o `large`) para el contact sheet, sin
  transferir originales innecesariamente.

## Comparación directa CURRENT vs PEXELS (03)

Por query, una fila de 4 columnas: CURRENT (`assetPath` del fixture,
Wikimedia/Pixabay) | PEXELS #1 | #2 | #3 (`_rank_path`). Se muestra provider,
Pexels ID, rank, WxH original y photographer. Layout: `compute_thumbnail_rect`
encaja cada imagen en su celda preservando aspect ratio (sin crop), centrada,
sin solapamiento; labels con wrap por línea (`_wrap`).

## Comparación final (results.md)

Tres capas separadas, sin mezclar availability con semantic quality:

### Current images
Evidencia histórica Wikimedia/Pixabay.

### Pexels Video
Supply técnico ya obtenido: cobertura 56/56, HIGH_SUPPLY (>=720x1280 y
>=1080x1920 = 1.0), 12 clips rank#1 720x1280.

### Pexels Photos
Nuevas métricas técnicas de este cambio (cobertura 56/56, HIGH_SUPPLY).

## Fuera de alcance

- NO integra Pexels; NO toca rendering, OpenCLIP/BLIP/VLM, VisualPlan, ni
  providers de producción.
- NO reescribe queries ni usa LLM; NO reranking ML; NO size filter.
- No merge, no push, no reindex.
