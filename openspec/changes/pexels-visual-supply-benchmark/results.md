# Results: pexels-visual-supply-benchmark

**Status: READY_FOR_HUMAN_REVIEW** — investigación benchmark-first del SUPPLY
visual de Pexels (Video + Photos). **Sin integración de runtime.** No se afirma
`PEXELS_BETTER` ni `PEXELS_PHOTOS_BETTER`; la decisión semántica queda pendiente
de la revisión humana externa sobre los contact sheets.

Se presentan tres capas separadas (Current / Pexels Video / Pexels Photos), sin
mezclar **disponibilidad técnica** con **calidad semántica**.

---

## Capa 1 — Current images (histórico Wikimedia/Pixabay)

Evidencia histórica previa (`generic-content-pipeline-evaluation`, CLOSED):
38 canónicos con etiquetas 16 CLEARLY_RELEVANT / 14 COARSE_BUT_USABLE /
8 FALSE_POSITIVE_OR_UNUSABLE — etiquetas SEMÁNTICAS, reutilizadas sin relabel.
Estos son los assets actuales (imagen estática) que se comparan en el contact
sheet 03.

---

## Capa 2 — Pexels Video (obtenido en la fase previa)

Mide SUPPLY de **vídeo** (RAW `GET /v1/videos/search`, `orientation=portrait`).

### Results

- **Cobertura: 56/56** (`queriesWithZeroResults=0`, `requestsUsed=56/100`).
- **HIGH_SUPPLY**: fracción queries con portrait >=720x1280 = **1.0** y
  >=1080x1920 = **1.0**.
- `candidatesReturned=838`, `portraitMp4Count=838`, `medianTotalResults=6856.5`,
  duration mediana 12 s.
- Diagnóstico landscape: **0** (56/56 `PORTRAIT_SUPPLY_OK`), sin `NO_CONTENT`
  ni `CONTENT_EXISTS_BUT_NOT_PORTRAIT`.
- Review: 12 clips rank#1 descargados **12/12, 0 fallos** (720x1280).
- Rate-limit tras vídeo: `remaining=24944/25000`.
- Contact sheets: `01-pexels-video-temporal-contact-sheet.png` (corregido) y
  `02-pexels-top3-search-results.png`.

---

## Capa 3 — Pexels Photos (nuevo, este cambio)

Mide SUPPLY de **foto** (RAW `GET /v1/search`, `orientation=portrait`).

### 1. Requests / rate-limit

- **56 requests** principales + **0** de diagnóstico = **56/70** nuevas.
- Rate-limit final: `X-RateLimit-Limit=25000`, `X-RateLimit-Remaining` =
  **24888**, reset `1789743276`. Sin clave persistida; `User-Agent` explícito.

### 2. Cobertura 38 canonical (Photos)

- Queries únicas de canonical: **36**.
- `withAnyResult = 36/36` → **cobertura 1.0**

### 3. Cobertura 20 development (Photos)

- Queries únicas de development: **20**.
- `withAnyResult = 20/20` → **cobertura 1.0**

### 4. Cobertura global (Photos)

- `queriesWithAnyResult = 56/56`, `queriesWithZeroResults = 0`,
  `queriesWithRequestError = 0`.
- `medianTotalResults = 8000.0`, `candidatesReturned = 840`.
- `originalPortraitCount = 840/840` (todo candidato portrait).

### 5. Portrait >=720x1280 (Photos)

- Queries con al menos un candidato portrait >=720x1280: **56/56** → **1.0** →
  **HIGH_SUPPLY**. `originalPortraitAtLeast720x1280 = 840`.

### 6. Portrait >=1080x1920 (Photos)

- Queries con al menos un candidato portrait >=1080x1920: **56/56** → **1.0** →
  **HIGH_SUPPLY**. `originalPortraitAtLeast1080x1920 = 840`.

### 7. Diagnósticos (Photos)

- **0** requests de diagnóstico; **56/56 `PORTRAIT_SUPPLY_OK`**; **0**
  `NO_CONTENT`; **0** `CONTENT_EXISTS_BUT_NOT_PORTRAIT`. (Todas las queries
  tienen supply portrait >=720x1280.)

### 8. 12 imágenes rank#1 descargadas / fallos

**12/12 rank#1 originales descargados, 0 fallos**, todos portrait de alta
resolución.

| role | query | pid | original WxH | photographer |
|---|---|---|---|---|
| bad_dev | four stroke engine automobile photograph | 33480796 | 4000x6000 | Reinis Brūzītis |
| bad_dev | medieval castle construction photograph | 17163614 | 4160x6240 | Indo |
| bad_dev | medieval castle architectural plans illustration | 15315820 | 2240x4000 | Ayşegül Aytören |
| bad_dev | completed medieval castle photograph | 11542503 | 4000x6000 | Maria-Theodora Andrikopoulou |
| bad_dev | medieval castle construction time diagram | 34988559 | 2592x3872 | Valeria Drozdova |
| bad_dev | medieval castle historical significance photograph | 38550952 | 4000x6000 | Alex Hoces |
| bad_dev | data center infrastructure diagram | 4497197 | 3497x5245 | Brett Sayles |
| good_bad_rejected_by_blip | medieval workers building castle illustration | 15315820 | 2240x4000 | Ayşegül Aytören |
| good_bad_rejected_by_blip | application hosting architecture diagram | 8062366 | 4128x6192 | Nataliya Vaitkevich |
| good_bad_rejected_by_blip | data center security architecture diagram | 5408005 | 4024x6048 | Brett Sayles |
| good_bad_rejected_by_blip | data center technology diagram | 9301821 | 3773x5661 | Mikhail Nilov |
| clearly_relevant_control | four stroke engine parts photograph | 26928835 | 2376x3170 | Jorryn Morais |

Ranks #2/#3: variantes `large2x` (no originales) para el contact sheet, sin
transferir originales innecesarios.

### 9. Paths de contact sheets

`data/evaluations/pexels-visual-supply-benchmark/` (git-ignored):

- `01-pexels-video-temporal-contact-sheet.png` — **corregido** (866×6944):
  frames portrait 270×480, aspect ratio preservado, sin solapamiento, labels
  con wrap. Fase vídeo.
- `02-pexels-top3-search-results.png` — previews vídeo rank 1/2/3. Fase vídeo.
- `03-pexels-photo-vs-current-contact-sheet.png` — **nuevo** (1274×6320):
  CURRENT (Wikimedia/Pixabay) vs PEXELS #1/#2/#3 por query.

### 10. Comparación directa (03)

Cada fila: `CURRENT | PEXELS #1 | PEXELS #2 | PEXELS #3`. CURRENT usa el
`assetPath` registrado de la fixture (12/12 presentes). PEXELS usa el ranking
raw. Esto permite revisar si Pexels Photos habría dado una opción mejor que el
asset actual. Sin juicio automático.

---

## Comparación técnico agregada

| Capa | Cobertura | >=720x1280 | >=1080x1920 | Clasificación |
|---|---|---|---|---|
| Current images (histórico) | semántica 16/14/8 | — | — | YELLOW (semántica) |
| Pexels Video | 56/56 | 1.0 | 1.0 | HIGH_SUPPLY |
| Pexels Photos | 56/56 | 1.0 | 1.0 | HIGH_SUPPLY |

**Mide solo disponibilidad técnica, NO relevancia semántica.** No se afirma
`PEXELS_BETTER` ni `PEXELS_PHOTOS_BETTER`.

## Decisión

**Pendiente.** La evidencia técnica muestra que tanto Pexels Video como Pexels
Photos ofrecen cobertura completa y supply portrait de alta resolución para las
queries del corpus. La decisión semántica (¿mejor supply/relevancia?, ¿mejor
que Wikimedia/Pixabay?, ¿provider de producción?) queda en manos de la
**revisión humana externa** con los 3 contact sheets. No se integra hasta
entonces.

## Tests

- `tests/test_pexels_video_supply_benchmark.py`: **30 passed**.
- `tests/test_pexels_photo_supply_benchmark.py`: **30 passed**.
- Suite completa: ver `tasks.md` (baseline previa `1556 passed`; con 30 nuevos
  de Photos → ver estado final actualizado).
