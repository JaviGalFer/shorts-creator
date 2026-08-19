# Design: pexels-provider-fit-benchmark

**Status: COMPLETED / VERIFIED / CLOSED** — investigación benchmark-first, sin
cambios de runtime. La revisión humana externa cerró la elegibilidad de provider,
pero no integra Pexels todavía.

## Arquitectura de evaluación

```
tests/fixtures/asset_visual_fidelity/labels.json          ← 38 canónicos (NO tocados)
tests/fixtures/asset_visual_fidelity/holdout_labels.json  ← 20 development (NO tocados)
        │  (58 rows lógicos; dedup por queryUsed exacto = 56 queries)
        ▼
data/videos/<jobId>/metadata.json                         ← contrato persistido por job
        │  script.scenes[i].visualPlan.visualIntent
        │  script.scenes[i].visualPlan.visualSequence[j].assetPreference / searchQuery
        ▼
tools/pexels_provider_fit_benchmark.py
        │  resolución rows → política → adaptación → requests adaptadas → comparación
        │  → review sample → contact sheets (evaluation-only, stdlib urllib, lazy)
        ▼
data/evaluations/pexels-provider-fit-benchmark/          ← git-ignored
        │   metadata-report.json · policy-report.json · adapt-report.json
        │   review-sample.json · adapted-video-supply.json · raw-vs-adapted.json
        │   review-clips.json · contact-sheets.json
        │   + clips/ · frames/ · photo_prev/ · video_prev/
        ▼
01-provider-fit-photo-current-top3.png        (CURRENT | PEXELS PHOTO #1|#2|#3)
02-provider-fit-video-raw-vs-adapted-top3.png (RAW #1|#2|#3 / ADAPTED #1|#2|#3)
03-provider-fit-video-temporal.png            (RAW vs ADAPTED rank#1, frames 20/50/80 %)
        ▼
openspec/changes/pexels-provider-fit-benchmark/results.md  ← cierre humano / decisiones
```

Evidencia RAW reutilizada (sin nuevas request de búsqueda):

```
data/evaluations/pexels-visual-supply-benchmark/photo-supply-benchmark.json
data/evaluations/pexels-video-supply-benchmark/supply-benchmark.json
data/evaluations/pexels-video-supply-benchmark/clips/   ← cache de clips RAW rank#1
data/evaluations/pexels-visual-supply-benchmark/photos/  ← previews Photos rank 1/2/3
```

## Resolución por (jobId, sceneNumber, segmentIndex)

Cada label row se cruza contra el `metadata.json` del job persistido:

| Campo | Fuente |
|-------|--------|
| `queryUsed` | label fixture (la query REAL enviada a los providers) |
| `topic` / `provider` / `humanLabel` / `assetPath` | label fixture |
| `assetPreference` | `visualPlan.visualSequence[segmentIndex].assetPreference` |
| `visualIntent` | `visualPlan.visualIntent` |
| `persistedSearchQuery` | `visualPlan.visualSequence[segmentIndex].searchQuery` |

Reglas:

- Los campos ausentes (job sin metadata, escena/segmento inexistente, campo
  null) se registran como `MISSING` explícito; NO se inventan.
- `humanLabel` es SOLO contexto histórico; nunca participa en la política.
- Si `persistedSearchQuery != queryUsed` se registra `searchQueryMismatch=True`
  (la fitting regeneration cambió el plan visual tras fetchear el asset).
- La **forma efectiva** para la política la fuerza la F ORMA DEL QUERY REAL
  enviado (`queryForm` sobre `queryUsed`), porque es el hecho verificado de lo
  que el provider recibió. Cuando el query no tiene forma explícita se usa el
  `assetPreference` persistido como fallback.

## Política provisional de provider-fit (pura)

`classify_provider_fit(form_category)` devuelve, por provider:

| Categoría | Pexels Photos | Pexels Video |
|-----------|---------------|--------------|
| `exactform` (diagram/infographic/illustration/painting) | `INELIGIBLE_EXACT_FORM` | `INELIGIBLE_EXACT_FORM` |
| `photograph` (photograph/photo/photography) | `ELIGIBLE` | `ELIGIBLE_CANDIDATE` |
| cualquier otro / ausente | `UNDECIDED` | `UNDECIDED` |

Regla inicial definida ANTES de ver nuevos resultados. No se convierte un
`diagram` en vídeo B-roll ni se considera equivalente. Si aparecen otros
`assetPreference` reales (p. ej. archive/map/document/stock/generated) NO se
inventa política: se reportan y quedan `UNDECIDED` hasta revisión.

## Adaptación de query (solo Video, solo photograph)

`adapt_photograph_query(query)`:

- Elimina SOLO los tokens `photograph`/`photo`/`photography` (descriptores de
  imagen estática).
- Conserva sujeto, entidad, variante y acción (`four stroke`, `medieval`,
  `construction`, `historical`, `automobile`, `engine`, `data center`, ...).
- NO elimina en esta fase diagram/infographic/illustration/painting (esas rows
  son INELIGIBLE y no deben convertirse artificialmente en B-roll).
- Normaliza espacios. `changed = removed != [] and adapted != raw`.
- Si `adapted == raw` NO se hace request (no se repite la RAW ya persistida);
  si `adapted == otra queryUsed RAW` se reutiliza esa evidencia (no se
  re-requesta).
- Dedup por adaptedQuery exacto; hard cap **40 requests nuevas**.

## Requests nuevas (solo adaptadas)

`GET https://api.pexels.com/v1/videos/search` con `query=adaptedQuery`,
`orientation=portrait`, `locale=en-US`, `per_page=15`, `page=1`. Header
`Authorization` (env → `.env`), `User-Agent` explícito. La clave nunca se
imprime ni se persiste. Se persiste `rawQuery`, `adaptedQuery`,
`removedTokens`, `changed`, `policyVersion` y el plan dedup.

## Comparación RAW vs ADAPTED (por query)

Para cada query adaptada se comparan hechos técnicos: `total_results`, top15
count, portrait >=720x1280, >=1080x1920, IDs top15/top3, overlap RAW↔ADAPTED,
rank changes de IDs compartidos, IDs nuevos introducidos por la adaptación. NO
se decide relevancia automáticamente.

## Overlap / duplicados exactos (sin ML)

`exact_id_overlap_stats` sobre top15 de: Photos RAW, Video RAW (56), Video RAW
fotográfico (39, base justa), Video ADAPTADO (39): unique IDs, IDs repetidos
entre queries, pairs con overlap, Jaccard de IDs, y IDs repetidos within
job/topic. Sin perceptual hash, sin near-duplicate.

## Review sample (determinista, ≤10 queries)

Algoritmo registrado (reproducible):

1. Empezar con las 5 mandatory (fijo) si son photograph-form.
2. Pool = photograph-form queries restantes, orden `(sorted(topics), query)`.
3. Round-robin por topic: cada ronda añade una query por topic (en orden de
   topic) hasta 10 o agotar pool. Evita llenar la muestra de un único job/topic.

Las 5 mandatory son fotográficas y todas resultados `REVIEW_12` del benchmark
anterior. Los 5 restantes se eligen por diversidad de topic.

## Contact sheets (Docker ffmpeg + PIL)

- `01`: CURRENT (assetPath real) | PEXELS PHOTO #1 | #2 | #3, reutilizando
  previews RAW existentes (nueva descarga de imagen solo si falta preview).

  - `02`: por query, fila RAW #1|#2|#3 y fila ADAPTED #1|#2|#3 con previews.
  - `03`: por query, clip rank#1 RAW (reutiliza cache) y clip rank#1 ADAPTED
    (nuevo; máximo 20 clips), frames 20/50/80 % lado a lado. Aspect ratio
    preservado, sin crop, sin solapamiento (alturas de columna precomputadas).

Sin juicio semántico automático.
