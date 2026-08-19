# Results: pexels-provider-fit-benchmark

**Status: COMPLETED / VERIFIED / CLOSED** — investigación benchmark-first del
provider fit de Pexels Photos/Video, cerrada tras la revisión humana externa de
los 3 contact sheets. **Sin integración de runtime.** Decisiones:
**`PEXELS_PROVIDER_FIT_VALIDATED`**, **`QUERY_ADAPTATION_COMPLEMENTARY_NOT_DEFAULT`**
y **`PEXELS_TOPN_SELECTION_REQUIRED`**.

No se afirma que Pexels sustituya Wikimedia/Pixabay, que `photograph` garantice
fidelidad, ni que ADAPTED sea el default de Video.

---

## Evidencia y trazabilidad

- Base `main` al abrir: `cf391c5`; commits de benchmark `6b18d01` y hardening
  `d948300`.
- Datasets reutilizados sin relabel: canonical 38 + development 20 = 58 rows →
  56 queryUsed únicas.
- RAW Photos: `data/evaluations/pexels-visual-supply-benchmark/photo-supply-benchmark.json`.
- RAW Video: `data/evaluations/pexels-video-supply-benchmark/supply-benchmark.json`.
- Solo hubo 39/40 requests Pexels Video adaptadas durante el benchmark. Hubo
  **0 requests** durante hardening y cierre; no hubo descargas ni regeneración
  de contact sheets durante estas fases.

## Contrato y política de elegibilidad

Resolución persistida 58/58 por `(jobId, sceneNumber, segmentIndex)`:
`missingRows=0`; 4 `searchQueryMismatch` por regeneración de fitting posterior
al fetch. Distribución assetPreference: photograph 39, diagram 14,
illustration 5. Distribución intent: explain 27, show 10, contextualize 9,

La política `provider-fit-policy-v1`, definida antes de los resultados nuevos,
`ELIGIBLE_CANDIDATE`, y 16 exactform como `INELIGIBLE_EXACT_FORM` para ambos.

### `PEXELS_PROVIDER_FIT_VALIDATED`

Significado exacto:

- `diagram` / `infographic` / `illustration` / `painting`: Pexels Photos y
  Video **NO** son satisfacción directa de la forma solicitada.
- `photograph`: Pexels Photos puede participar como provider; Pexels Video
  puede participar como provider candidate.
- `ELIGIBLE` **no** significa candidate accepted. `photograph` determina
  provider eligibility; **no garantiza fidelidad del resultado**.
- No se crea ahora una matriz intent×assetPreference más compleja.

## Resultados técnicos previos al juicio humano

`query-adapt-v1` eliminó solo photograph/photo/photography: 39 adaptaciones
únicas, sin colisiones en el corpus real. RAW vs ADAPTED tuvo 39 comparaciones:
ADAPTED devolvió menos `total_results` en 29/39, igual en 9/39 y más en 1/39
(mediana 6439→6026). Esto demuestra cambio/restricción del conjunto recuperado,

El supply portrait se mantuvo: RAW y ADAPTED, 39/39 queries con >=720x1280 y

## Revisión humana externa

Muestra determinista: 10 queries, 5 mandatory y 5 por round-robin de topics.
Los labels siguientes proceden exclusivamente de la revisión humana de:

- `01-provider-fit-photo-current-top3.png`
- `02-provider-fit-video-raw-vs-adapted-top3.png`
- `03-provider-fit-video-temporal.png`

### Photos: CURRENT vs PEXELS

| Query | Label humano | Nota |
|-------|--------------|------|
| four stroke engine automobile photograph | CURRENT_BETTER | |
| completed medieval castle photograph | PEXELS_BETTER | |
| medieval castle construction photograph | TIE | Ninguno satisface realmente construction. |
| medieval castle historical significance photograph | PEXELS_BETTER | |
| four stroke engine parts photograph | TIE | Current es bueno; Pexels top3 contiene alternativa mecánica útil. |
| blue ringed octopus venom photograph | CURRENT_BETTER | Current muestra el sujeto específico; Pexels cae en pulpo genérico. |
| PlayStation Nintendo 64 comparison photograph | PEXELS_BETTER | Pexels #3 muestra N64 + PlayStation controller. |
| Java code snippet photograph | TIE | Coding B-roll; sin evidencia visual suficiente para confirmar Java. |
| engine explosion in piston photograph | CURRENT_BETTER | |
| amortization chart graph photograph | PEXELS_BETTER | |

Agregado: **PEXELS_BETTER=4**, **CURRENT_BETTER=3**, **TIE=3**. Es evidencia

### Video: RAW vs ADAPTED

| Query | Label humano | Nota |
|-------|--------------|------|
| four stroke engine automobile photograph | ADAPTED_BETTER | |
| completed medieval castle photograph | RAW_BETTER | |
| medieval castle construction photograph | BOTH_UNUSABLE | |
| medieval castle historical significance photograph | TIE | |
| four stroke engine parts photograph | TIE | |
| blue ringed octopus venom photograph | BOTH_UNUSABLE | Sin evidencia visual suficiente de blue-ringed/venom. |
| PlayStation Nintendo 64 comparison photograph | BOTH_UNUSABLE | |
| Java code snippet photograph | TIE | |
| engine explosion in piston photograph | BOTH_UNUSABLE | |
| amortization chart graph photograph | ADAPTED_BETTER | |

Agregado: **ADAPTED_BETTER=2**, **RAW_BETTER=1**, **TIE=3**,
**BOTH_UNUSABLE=4**.

### `QUERY_ADAPTATION_COMPLEMENTARY_NOT_DEFAULT`

`query-adapt-v1` cambia materialmente el candidate set y diversifica

Dirección futura de Video: `RAW + ADAPTED → candidate pool conjunto → selección

### `PEXELS_TOPN_SELECTION_REQUIRED`

La revisión confirma que API rank #1 no equivale al asset final:

- Caso canónico Photos: `PlayStation Nintendo 64 comparison photograph`;
  Pexels Photo #3 es claramente mejor que rank #1.
- Caso previo conservado: `four stroke engine automobile photograph`; Video
  top-N puede contener material mejor que rank #1.

Productización futura debe seleccionar top-N; no debe asumir rank #1 ciego.

### Diversity

Exact duplicate/overlap persiste, especialmente dentro del mismo job/topic.
La selección futura de candidatos debe contemplar diversity/dedup.

## Roadmap inmediato (fuera de este change)

1. `pexels-photos-runtime`: integración image-only de bajo riesgo, Pexels como
   provider adicional y no sustituto; routing que respete provider fit y
   selección top-N, no rank #1 ciego.
2. Cambio separado de contrato: `VisualAsset kind = IMAGE | VIDEO`.
3. `pexels-video-runtime`: pool RAW+adapted, selección de clips, rendering y
   normalización de vídeo.
4. Candidate-selection/diversity.

Generación de imágenes y manual uploads permanecen como roadmap posterior y no
se implementan aquí.

## Validación y cierre

- Hardening: `raw_1080` corregido; typo
  `newIdsInt21ByAdaptation` → `newIdsIntroducedByAdaptation`; una adaptedQuery
  con N sourceQueries produce N comparaciones/mappings y conserva una request.
- Tests de cierre: 100 tests de las tres suites Pexels; suite completa
  **1626 passed, 0 failed**; `git diff --check` limpio.
- Sin runtime Pexels, sin nuevas requests, sin nuevas descargas y sin nueva
  evidencia visual durante hardening/cierre.
