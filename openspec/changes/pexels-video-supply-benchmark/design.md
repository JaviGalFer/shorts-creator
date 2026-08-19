# Design: pexels-video-supply-benchmark

**Status: READY_FOR_HUMAN_REVIEW** — investigación benchmark-first, sin cambios
de runtime. La decisión semántica queda en manos de la revisión humana externa.

## Arquitectura de evaluación (sin cambios de runtime)

```
tests/fixtures/asset_visual_fidelity/labels.json          ← 38 canónicos (NO tocados)
tests/fixtures/asset_visual_fidelity/holdout_labels.json  ← 20 development (NO tocados)
        │  (58 rows lógicos; dedup por queryUsed exacto = 56 requests)
        ▼
tools/pexels_video_supply_benchmark.py  ← evaluation-only, stdlib urllib
        │   REST GET /v1/videos/search · Authorization header · UA header
        │   orientation=portrait · locale=en-US · per_page=15 · page=1
        ▼
data/evaluations/pexels-video-supply-benchmark/*.json     ← git-ignored
        │   supply-benchmark.json · landscape-diagnostic.json · review-clips.json
        ▼
clips/ (12 MP4 rank#1) + frames/ + previews/
        ▼
01-pexels-video-temporal-contact-sheet.png  (Docker ffmpeg: frames 20/50/80%)
02-pexels-top3-search-results.png           (previews rank 1/2/3)
        ▼
openspec/changes/pexels-video-supply-benchmark/results.md  ← informe
```

## API / contrato

- Endpoint: `GET https://api.pexels.com/v1/videos/search`
- Header `Authorization: <PEXELS_API_KEY>` + `User-Agent` (sin UA da 403).
- Búsqueda principal: `query`=raw `queryUsed`, `orientation=portrait`,
  `locale=en-US`, `per_page=15`, `page=1`. NO se filtra por `size`.
- Diagnóstico landscape: segunda request SIN `orientation`, solo para queries
  sin supply portrait O sin MP4 portrait >=720x1280.
- Cap duro de requests: **100** (contador `RequestBudget`).

### Clave (no leak)

- Resolución: proceso (env) primero, luego `.env` del proyecto
  (`PEXELS_API_KEY`).
- La clave **nunca** se imprime ni se persiste en ningún artefacto de salida.

## Parsing / normalización

`parse_video_search_response` devuelve por vídeo: `id`, `width`/`height`
(origen), `url`, `image` (preview), `duration`, `user`, `video_files`
(`quality`, `file_type`, `width`, `height`, `fps`, `link`, `size`) y
`video_pictures`.

Métricas técnicas por query:
`total_results`, `candidatos`, y conteos de candidatos portrait con MP4
>=540x960 / >=720x1280 / >=1080x1920, + `hasAtLeastOne720x1280Candidate` /
`hasAtLeastOne1080x1920Candidate`. Agregadas: medianTotalResults,
candidatesReturned, portraitMp4Count, durationDistribution, coverages por
dataset y clasificación HIGH/MEDIUM/LOW_SUPPLY.

## Selección MP4 de review

`select_review_mp4` elige el MP4 portrait de playback del rank #1:
1. variante >=720x1280 más pequeña (ahorro de transferencia);
2. si no, >=540x960;
3. si no, cualquier MP4 portrait.
Sin HLS/m3u8. Es una elección técnica, no una decisión de relevancia.

## Revisión humana

- Downloads máx 12, reutilizando el rank #1 raw persistido (`rawResults`) → 0
  requests de búsqueda extra.
- Contact sheets con PIL + Docker `linuxserver/ffmpeg:latest`:
  - entrada ffmpeg por defecto (no prefijar `ffmpeg`);
  - ffprobe vía `--entrypoint ffprobe` (patrón de `validation/job.py`);
  - frames `-ss <20/50/80 %>` extraídos sin crop destructivo.
- Sin juicio automático de píxeles: OpenCode reporta solo hechos técnicos.

## Fuera de alcance

- NO integra Pexels; NO toca rendering, OpenCLIP/BLIP/VLM, VisualPlan, ni
  providers de producción.
- NO reescribe queries ni usa LLM para adaptarlas; NO reranking ML.
- No merge, no push, no reindex.
