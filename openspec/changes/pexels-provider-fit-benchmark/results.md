# Results: pexels-provider-fit-benchmark

**Status: IN_PROGRESS — READY_FOR_HUMAN_REVIEW** — investigación benchmark-first
del PROVIDER FIT de Pexels Photos/Video y de la adaptación determinista de query
para Pexels Video. **Sin integración de runtime.** NO se afirma
`PROVIDER_FIT_VALIDATED`, `ADAPTED_BETTER` ni "Pexels por defecto" hasta la
revisión humana externa de los 3 contact sheets.

---

## Contexto de evidencia (reutilizado, NO reconstruido)

- Datasets reutilizados sin relabel: canonical 38 + development 20 = 58 rows →
  56 queryUsed únicas.
- RAW Photos: `data/evaluations/pexels-visual-supply-benchmark/photo-supply-benchmark.json`
- RAW Video: `data/evaluations/pexels-video-supply-benchmark/supply-benchmark.json`
- Clips RAW rank#1 y previews Photos: caches del benchmark anterior.

## Resolución real desde contrato persistido (58/58, MISSING 0)

`metadata-report.json` · resuelto por `(jobId, sceneNumber, segmentIndex)` desde
`data/videos/<jobId>/metadata.json` (visualPlan persistido) + fixtures.

### Distribución assetPreference (persistida)

| assetPreference | rows |
|-----------------|------|
| photograph | 39 |
| diagram | 14 |
| illustration | 5 |
| **total** | **58** |

No hay painting ni otros valores del enum cerrado (`archive`, `map`,
`document`, `stock`, `generated`) en el corpus.

### Distribución visualIntent (persistida)

| visualIntent | rows |
|--------------|------|
| explain | 27 |
| show | 10 |
| contextualize | 9 |
| emphasize | 9 |
| compare | 2 |
| immerse | 1 |

### Combinaciones intent × assetPreference (reales)

| intent × assetPreference | rows |
|--------------------------|------|
| explain × photograph | 16 |
| explain × diagram | 8 |
| explain × illustration | 3 |
| show × photograph | 8 |
| show × diagram | 2 |
| emphasize × photograph | 8 |
| emphasize × diagram | 1 |
| contextualize × photograph | 4 |
| contextualize × diagram | 3 |
| contextualize × illustration | 2 |
| compare × photograph | 2 |
| immerse × photograph | 1 |

### Distribución forma de query (queryUsed real)

| forma | rows | queries únicas |
|-------|------|----------------|
| photograph (photograph/photo/photography) | 41 | 39 |
| exactform (diagram/illustration) | 16 | 16 |
| none | 1 | 1 |

Nota: 4 rows presentan `searchQueryMismatch=True` (el plan visual fue regenerado
por fitting tras el fetch del asset; el query REAL enviado difiere del
`searchQuery` persistido final). La política usa la FORMA DEL QUERY REAL;
la assetPreference persistida se reporta como señal cruzada y la discrepancia
queda registrada.

## Política provisional de provider-fit (`policy-report.json`)

Regla definida ANTES de ver resultados nuevos. Verdicts por row (58):

| Categoría efectiva | rows | Photos | Video |
|-------------------|------|--------|-------|
| photograph | 42 | ELIGIBLE | ELIGIBLE_CANDIDATE |
| exactform | 16 | INELIGIBLE_EXACT_FORM | INELIGIBLE_EXACT_FORM |
| undecided | 0 | — | — |

Totales: **Photos ELIGIBLE = 42 rows**, **Video ELIGIBLE_CANDIDATE = 42 rows**,
**INELIGIBLE_EXACT_FORM = 16 rows**, **UNDECIDED = 0**. La row sin forma en
query (`Roman Empire historical scenes`) cae en photograph por fallback a su
assetPreference persistida (photograph).

## Adaptación de query (`adapt-report.json`)

`query-adapt-v1` elimina solo `photograph`/`photo`/`photography`, preserva
sujeto/variante/acción, normaliza espacios.

- 40 queries photograph-form efectivas; **39 adaptaciones** con `changed=True`
  (todas) y sin colisiones (`adapted` únicas, ninguna igual a una queryUsed RAW;
  por tanto no se reusa evidencia RAW por coincidencia).
- Ejemplos: `four stroke engine automobile photograph` →
  `four stroke engine automobile`; `completed medieval castle photograph` →
  `completed medieval castle`.

## Requests nuevas (`adapted-video-supply.json`)

- **39/40** requests usadas (cap 40), Pexels Video
  `GET /v1/videos/search` con `orientation=portrait`, `locale=en-US`,
  `per_page=15`, page=1. Rate limit final `remaining=24849/25000`. 0 errores.
- Clave resuelta env → `.env`; nunca impresa ni persistida.

## RAW vs ADAPTED supply (`raw-vs-adapted.json`)

Por query (39 comparaciones; hechos técnicos, sin juicio de relevancia):

- `total_results` RAW vs ADAPTED: `adapted_raw > adapted` en **29/39**, igual en
  **9/39**, mayor en **1/39**. Mediana totales RAW=6439 vs ADAPTED=6026 (la
  adaptación reduce el ruido del sufijo estático, esperado).
- Portrait supply: RAW **39/39** con >=720x1280 y **39/39** con >=1080x1920;
  ADAPTADO **39/39** y **39/39** (indistinguibles en supply).
- Overlap top15 RAW↔ADAPTED: media 9.0/15, rango 3–14; overlap top3 media 1.67
  (dist: 0→5, 1→10, 2→17, 3→7). La adaptación conserva parte del ranking pero
  introduce candidatos nuevos (IDs nuevos por query: media ~6).

## Overlap / duplicados exactos (top15, sin ML)

`exact_id_overlap_stats` + within-job (exact IDs):

| Set | queries | unique IDs | IDs repetidos | pairs c/overlap | Jaccard medio | Jaccard máx |
|-----|--------:|-----------:|--------------:|----------------:|--------------:|------------:|
| Photos RAW | 56 | 587 | 145 | 104 | 0.193 | 0.579 |
| Video RAW (todas) | 56 | 580 | 159 | 121 | — | — |
| Video RAW (fotográficas, 39) | 39 | 456 | 92 | 56 | 0.124 | 0.579 |
| **Video ADAPTADO (39)** | 39 | **461** | **88** | **50** | 0.138 | 0.5 |

Lectura técnica (pre-juicio humano): la adaptación **diversifica ligeramente**
el conjunto: +5 unique IDs, −4 IDs repetidos, −6 pares con overlap, y baja el
Jaccard máximo (0.579→0.5) sobre la misma base de 39 queries. Los duplicados
within-job/topic **persisten** tras la adaptación (total de IDs repetidos
within-topic: 156 → 154; en castillos 9→10, data center 2→4, Porsche 11→15)
— la adaptación NO elimina el problema de overlap entre escenas del mismo job.
Photos mantiene el mayor overlap within-job (278 IDs repetidos within-topic,
p. ej. 25 en castillos, 21 en centro de datos).

## Review sample (`review-sample.json`) — determinista, 10 queries

Algoritmo: 5 mandatory (fijas, todas photograph-form y presentes en el REVIEW_12
del benchmark anterior) + round-robin por topic sobre las restantes.

1. `four stroke engine automobile photograph` (M)
2. `completed medieval castle photograph` (M)
3. `medieval castle construction photograph` (M)
4. `medieval castle historical significance photograph` (M)
5. `four stroke engine parts photograph` (M)
6. `blue ringed octopus venom photograph` (pulpos)
7. `PlayStation Nintendo 64 comparison photograph` (videojuegos 3D)
8. `Java code snippet photograph` (Spring Boot)
9. `engine explosion in piston photograph` (motor, mismo topic que M1/M5)
10. `amortization chart graph photograph` (hipoteca)

Topics cubiertos: 6 (motor, castillos, pulpos, videojuegos, Spring Boot,
hipoteca). Evita llenar la muestra de un único job/topic.

## Evidencia visual generada

| Contact sheet | Path | Contenido |
|---------------|------|-----------|
| 01 fotos | `data/evaluations/pexels-provider-fit-benchmark/01-provider-fit-photo-current-top3.png` | CURRENT | PEXELS PHOTO #1 | #2 | #3 (reusa evidencia RAW; sin requests Photos nuevas) |
| 02 vídeo top3 | `data/evaluations/pexels-provider-fit-benchmark/02-provider-fit-video-raw-vs-adapted-top3.png` | por query RAW #1-3 / ADAPTED #1-3 (previews) |
| 03 vídeo temporal | `data/evaluations/pexels-provider-fit-benchmark/03-provider-fit-video-temporal.png` | por query RAW rank#1 vs ADAPTED rank#1, frames 20/50/80 %, aspect ratio preservado, sin crop, sin solapamiento |

Clips: 20/20 descargados (0 fallos): 10 RAW (5 OK_CACHED del cache previo) + 10
ADAPTED. Docker `linuxserver/ffmpeg` para extracción de frames y ffprobe.

## Qué debe decidir el humano (NO se produce aquí)

Por query:

- **Photos**: CURRENT better / PEXELS better / TIE.
- **Video**: RAW better / ADAPTED better / TIE / BOTH_UNUSABLE.

Y además: si rank#1 es útil o el top3 contiene un candidato mejor; si
`assetPreference=photograph` (forma de query) fue suficiente para decidir el
provider fit; si algún intent requiere una regla adicional.

## Estado

**READY_FOR_HUMAN_REVIEW** — pendiente la revisión externa de los 3 contact
sheets. No se produce juicio semántico desde OpenCode. No commit de cierre.