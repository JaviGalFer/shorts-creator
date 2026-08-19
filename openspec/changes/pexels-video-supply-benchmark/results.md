# Results: pexels-video-supply-benchmark

**Status: READY_FOR_HUMAN_REVIEW** — investigación benchmark-first del SUPPLY
de Pexels Video. **Sin integración de runtime.** No se afirma `PEXELS_BETTER`;
la decisión semántica queda pendiente de la revisión humana externa sobre los
contact sheets.

## 1. Requests reales / rate-limit restante

- 56 queryUsed únicas (58 rows lógicos). Una request portrait por query.
- **Requests usadas: 56 / 100** en el run principal + **0** en el diagnóstico
  landscape (todas las queries ya tenían supply portrait) + **0** de búsqueda
  para el review (reutiliza el `rawResults` persistido).
- Rate-limit Pexels: `X-RateLimit-Limit = 25000`, `X-RateLimit-Remaining` final
  **24944**/25000, reset `1789743276`. Sin fugas de clave en ningún artefacto.
- Nota: una primera pasada (antes de añadir User-Agent) devolvió 403 y no
  consumió cuota de búsqueda real.

## 2. Cobertura 38 canonical

- Queries únicas de canonical: **36** (dos queryUsed duplicadas en el dataset).
- `withAnyResult = 36/36` → **cobertura 1.0**

## 3. Cobertura 20 development

- Queries únicas de development: **20**.
- `withAnyResult = 20/20` → **cobertura 1.0**

## 4. Cobertura global

- `queriesWithAnyResult = 56/56`, `queriesWithZeroResults = 0`,
  `queriesWithRequestError = 0`.
- `medianTotalResults = 6856.5` (rango 2602–8000). `candidatesReturned = 838`
  (per_page 15 × 56).
- `portraitMp4Count = 838` (todo candidato portrait devuelto trae MP4 portrait).

## 5. Portrait >=720x1280

- Queries con al menos un candidato portrait >=720x1280: **56/56** → fracción
  **1.0** → **HIGH_SUPPLY**.
- portraitMp4AtLeast720x1280 (candidatos): 836 / 838.

## 6. Portrait >=1080x1920

- Queries con al menos un candidato portrait >=1080x1920: **56/56** → fracción
  **1.0** → **HIGH_SUPPLY**.
- portraitMp4AtLeast1080x1920 (candidatos): 832 / 838.

## 7. Diagnósticos NO_CONTENT vs NOT_PORTRAIT

- Solo se dispara el diagnóstico landscape cuando una query no tiene supply
  portrait (0 resultados) o ningún MP4 portrait >=720x1280.
- En esta muestra **ninguna** query falló portrait → **56/56
  `PORTRAIT_SUPPLY_OK`**, **0** requests de diagnóstico, **0** `NO_CONTENT`,
  **0** `CONTENT_EXISTS_BUT_NOT_PORTRAIT`.
- Es decir, para estas 56 queries el suministro portrait de Pexels es completo;
  no hubo caso de "contenido solo landscape" ni de "sin contenido".

## 8. 12 clips descargados / fallos

12/12 descargados, **0 fallos**, todos MP4 portrait **720x1280**.

| role | query | Pexels ID | dur |
|---|---|---|---|
| bad_dev | four stroke engine automobile photograph | 36543604 | 11 s |
| bad_dev | medieval castle construction photograph | 37617738 | 15 s |
| bad_dev | medieval castle architectural plans illustration | 37617746 | 14 s |
| bad_dev | completed medieval castle photograph | 20462333 | 12 s |
| bad_dev | medieval castle construction time diagram | 28219854 | 9 s |
| bad_dev | medieval castle historical significance photograph | 37617748 | 18 s |
| bad_dev | data center infrastructure diagram | 7812414 | 12 s |
| good_bad_rejected_by_blip | medieval workers building castle illustration | 37461953 | 8 s |
| good_bad_rejected_by_blip | application hosting architecture diagram | 36825184 | 17 s |
| good_bad_rejected_by_blip | data center security architecture diagram | 5377775 | 14 s |
| good_bad_rejected_by_blip | data center technology diagram | 35544532 | 15 s |
| clearly_relevant_control | four stroke engine parts photograph | 34952824 | 15 s |

## 9. Paths de los 2 contact sheets

`data/evaluations/pexels-video-supply-benchmark/` (git-ignored):

- `01-pexels-video-temporal-contact-sheet.png` — 12 filas; por fila: query,
  job `scene.segment`, Pexels ID, rank 1, duration, resolución y 3 frames al
  20/50/80 % (Docker ffmpeg).
- `02-pexels-top3-search-results.png` — 12 filas; previews RAW de rank 1/2/3
  con query, ID, duration y resolución/orientación.

Además: `clips/` (12 MP4), `frames/` (36), `previews/` (36), y los JSON
`supply-benchmark.json`, `landscape-diagnostic.json`, `review-clips.json`.

## 10. Comparación preliminar (solo cobertura/supply)

- Wikimedia/Pixabay (evidencia existente): resolución parcial por query; los 38
  canónicos tuvieron 38 assets resueltos para review con etiquetas 16/14/8
  (relevancia SEMÁNTICA, no supply).
- Pexels Video search (RAW): **cobertura 56/56 y HIGH_SUPPLY** (>=720x1280 y
  >=1080x1920) — la API de vídeo devuelve candidates portrait para todas las
  queries del corpus con dos resoluciones altas.
- Esto mide **disponibilidad técnica de vídeo**, no relevancia semántica.
  **No se afirma `PEXELS_BETTER`.**
- Duración de candidates: min 2 s, mediana 12 s, media 15.9 s, max 111 s.

## 11. Clasificación técnica provisional

- `HIGH_SUPPLY` (>=90 % con portrait >=720x1280): **1.0**.
- `HIGH_SUPPLY` (>=1080x1920): **1.0**.
- Sin juicio semántico de los clips: pendiente de la revisión humana.

## 12. Tests

- `tests/test_pexels_video_supply_benchmark.py`: **30 passed** (parsing API,
  dedup queries, rate-limit metadata, selección MP4 portrait, request cap,
  landscape diagnostic, no API-key leakage, import-safe/offline, fixtures
  intactos). Sin llamadas reales en pytest.
- Suite completa: ver `tasks.md`.

## 13. Decisión

**README pendiente.** El benchmark demuestra que Pexels Video aporta cobbertura
y suministro portrait completo (HIGH_SUPPLY) para las queries del corpus, pero
la decisión de si es útil (y si mejora frente a Wikimedia/Pixabay en calidad)
queda en manos de la **revisión humana externa** con los contact sheets. No se
integra hasta entonces.
