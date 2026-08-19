# Results: pexels-visual-supply-benchmark

**Status: COMPLETED / VERIFIED / CLOSED** — investigación benchmark-first del
SUPPLY visual de Pexels (Video + Photos) cerrada con **revisión humana externa**
de los 3 contact sheets. **Sin integración de runtime.** Decisión:
**`PEXELS_CONDITIONAL_PROVIDER_PROMISING`**. NO se afirma `PEXELS_BETTER` ni
`PEXELS_PHOTOS_BETTER`.

El supply técnico se registró en la fase previa (READY_FOR_HUMAN_REVIEW) y **no
se cambia en esta fase de cierre**. Lo que se añade aquí es la evidencia
cualitativa de la revisión humana y la decisión/camino siguiente. Se presentan
tres capas separadas (Current / Pexels Video / Pexels Photos), sin mezclar
**disponibilidad técnica** con **calidad semántica**.

---

## Review humana — conclusiones cualitativa (evidencia)

(Renglones autoritativos del cierre; la revisión se hizo sobre `01-...-temporal-...`,
`02-...-top3-...` y `03-...-photo-vs-current-...`.)

1. **Pexels es especialmente prometedor para:** photographs, physical subjects,
   locations, people, objects, technology/server B-roll, y environmental/
   contextual footage.

2. **Pexels NO satisface de forma fiable visual forms explícitos:** `diagram`,
   `infographic`, `illustration`, `architectural plan`, `construction-time
   diagram`. El buscador tiende a recuperar el **SUBJECT** principal pero
   ignorar el **requested visual form**.

3. **Ejemplo importante de ranking** — `four stroke engine automobile
   photograph`:
   - Pexels Video rank #1: débil/no representativo del motor.
   - Pexels Video rank #3: mecánico/persona trabajando junto a un motor,
     claramente más apropiado.
   Conclusión: hay casos donde existe buen supply pero el **raw rank #1 no
   selecciona el mejor candidato** (top-N contiene mejor candidato).

4. **Casos de castillo** muestran otra limitación: queries diferentes sobre
   `construction`, `architectural plans`, `construction-time diagram`,
   `workers building` recuperan repetidamente castillos/ruinas similares, sin
   satisfacer la relación/forma requerida.

5. **Candidate overlap/repetición** entre queries relacionadas (especialmente
   castillos / data center). Registrado como riesgo futuro: **cross-scene
   visual diversity / duplicate avoidance**.

6. **Comparación Photos CURRENT vs Pexels:** NO existe evidencia para afirmar
   que Pexels Photos reemplace globalmente Wikimedia/Pixabay.
   - Current assets son frecuentemente mejores en: diagramas, ilustraciones,
     conceptos abstractos/explicativos.
   - Pexels es frecuentemente más útil en: fotografía real, objetos/lugares/
     personas, B-roll.
   Por tanto son **COMPLEMENTARIOS**.

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

**`PEXELS_CONDITIONAL_PROVIDER_PROMISING`**

- supply VALIDADO (Video y Photos: 56/56, HIGH_SUPPLY, >=720x1280 y >=1080x1920
  = 1.0).
- Pexels merece continuar hacia integración.
- **NO** es sustituto global del stack actual; **NO** es default.
- **No integrar todavía.**
- El routing debe ser sensible a **visual form / provider fit** (Pexels falla
  en visual forms explícitos: diagram/illustration/plan/infographic).
- Pexels Video necesita **provider-aware query adaptation** (ver dirección
  siguiente).
- **raw rank #1 no es selección suficiente** (top-N contiene mejor candidato).
- **diversity/dedup** debe considerarse antes o durante la productización
  (overlap entre queries relacionadas: castillos / data center).

NO se afirma: `PEXELS_BETTER`, `PEXELS_PHOTOS_BETTER`, "Pexels debe ser
default", "Pexels reemplaza Wikimedia/Pixabay".

## Dirección siguiente (separada, NO implementada todavía)

`pexels-provider-fit-benchmark` — objetivo futuro:

1. determinar elegibilidad del provider usando **visual intent +
   assetPreference**;
2. Pexels Photos: priorizar para intents photographic/stock-compatible;
3. Pexels Video: probar **query adaptation determinista** eliminando
   visual-form tokens incompatibles (`photograph`, `illustration`, `diagram`,
   `infographic`, `painting`) conservando sujeto/acción;
4. comparar RAW vs adapted query;
5. medir si el **top-N** contiene mejor candidato que rank #1;
6. estudiar overlap/duplicados entre escenas;
7. benchmark-first, sin runtime inicialmente.

Este siguiente change NO se implementa en esta fase.

## Paths de evidencia

- Video evidence permanece en `data/evaluations/pexels-video-supply-benchmark/`.
- Photos/comparison: `data/evaluations/pexels-visual-supply-benchmark/`.
- No se mueve evidencia git-ignored solo por estética.

## Tests

- `tests/test_pexels_video_supply_benchmark.py`: **30 passed**.
- `tests/test_pexels_photo_supply_benchmark.py`: **30 passed**.
- Suite completa en cierre: **1586 passed, 0 failed** (60 focales + resto).
