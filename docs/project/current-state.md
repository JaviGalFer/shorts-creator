# Estado actual del proyecto

**Última actualización:** 2026-08-20

## Cambio activo: `web-ui-mvp` — IN PROGRESS (Slice 1 APPROVED/committed; Slice 2 APPROVED/committed `f0d2efa`; Slice 3 IMPLEMENTED / TESTED / REVIEWED / APPROVED / COMMITTED; Slice 4 pendiente)

- Objetivo: exponer el pipeline canónico (`run_pipeline`) a través de una pequeña Web UI
  (FastAPI + Angular) sin duplicar lógica de pipeline y sin romper la CLI.
- Rama `change/web-ui-mvp`; baseline `main` `059552d`; Slice 1 committed (`caa33c5`).
- **Slice 1 (COMPLETED / TESTED / REVIEWED / APPROVED):** límite de invocación reutilizable
  con identidad de job explícita.
  - `run_pipeline(job_id=<id seguro>)` → `build_script_command` → `bin/generate_script.py
    --job-id` → `generate_script(job_id=...)` → `data/videos/<jobId>/metadata.json` →
    `metadata["jobId"] == jobId`.
  - Identidad única: `API jobId == directorio jobId == metadata.jobId`.
  - `job_id=None` → comportamiento CLI histórico (ID derivado de topic) intacto.
  - **Sin** `output_dir` arbitrario añadido a `run_pipeline`.
  - `validate_job_id` rechaza traversal/separadores/control/vacío.
  - Hardening pre-Review:
    - Fail-fast: `job_id` explícito se valida en la entrada de `generate_script`, antes de
      LLM/red/retries/rutas (`INVALID_JOB_ID` sin `call_llm`).
    - `job_id` explícito + `--output` arbitrario: `JOB_ID_OUTPUT_CONFLICT` (antes de
      LLM/red/filesystem); `--job-id`/`--output` mutuamente excluyentes en CLI; `--output`
      sin `--job-id` sigue intacto.
    - Ruta canónica autoritativa en `run_pipeline` para ID explícito: se rechaza el
      `parsed["path"]` ajeno y el `jobId` discrepante (`SCRIPT_OUTPUT_CONTRACT_VIOLATION`);
      `job_id=None` conserva descubrimiento por stdout.
    - Identidad del metadata cargado: `_validate_explicit_metadata_identity` exige
      `metadata["jobId"] == job_id` en ramas de éxito y de fallo, ANTES de mutar el archivo
      (`SCRIPT_OUTPUT_CONTRACT_VIOLATION`).
  - Tests: 33 dirigidos (`tests/test_run_job_job_id.py`); suite completa
    `1913 passed, 0 failed`; `git diff --check` limpio.
  - Review formal (retry): **`SLICE_1_APPROVED`**; finding previo de identidad del
    metadata cargado CLOSED; triple invariante final `requested jobId == directorio
    canónico == metadata.jobId`.
- **Slice 2 (IMPLEMENTED / TESTED / APPROVED, committed `f0d2efa`):** backend FastAPI en
  `src/shorts_creator/web/` (`exceptions`, `dto`, `repository`, `projection`, `executor`,
  `service`, `capabilities`, `dependencies`, `routes/{health,jobs,media}` y `app`).
  - DTO allowlist estricto (`extra="forbid"`); errores centralizados con códigos estables
    (`INVALID_JOB_REQUEST`, `INVALID_JOB_ID`, `JOB_NOT_FOUND`, `JOB_VIDEO_UNAVAILABLE`,
    `JOB_EXECUTION_BUSY`, `INTERNAL_ERROR`); sin stderr/traceback/raw al navegador.
  - `JobService` como autoridad "jobs visibles al caller" (UUID4 estricto backend-generated;
    el API expone recursos de dominio, nunca filesystem — no acepta ni devuelve paths).
  - Repo filesystem con sidecar atómico `web-job.json` (`os.replace` + fsync); SOLO jobs
    Web-managed (dir con sidecar); `metadata.json` canónico no se expone crudo.
  - `LocalJobExecutor` invoca el MISMO `run_pipeline` en proceso (max_workers=1, admitencia
    1 activo + 1 cola; busy→`409` con sidecar INTERRUPTED; reconciliación de stale
    QUEUED/RUNNING→INTERRUPTED; `run_pipeline()==0`→FINISHED, `!=0`/excepción→FAILED;
    REVIEW_REQUIRED/ASSETS_PARTIAL con rc==0 quedan FINISHED).
  - Proyección allowlist `metadata.json`→`JobResponse` con sanitización de
    warnings/reviewReasons (`_UNSAFE_FRAGMENTS`), sin `childCommand`/`failure`/paths;
    `pipelineStatus` = `metadata["status"]` (None hasta que el pipeline persiste metadata).
  - Endpoints: `POST /api/v1/jobs` (202), `GET /jobs`, `GET /jobs/{id}`, `GET
    /jobs/{id}/video` (inline), `GET /jobs/{id}/download`, `GET /health`, `GET
    /capabilities` (derivado de enums/contratos canónicos — visual_media, router, duration,
    audio — nunca hardcoded; sin leak de claves).
  - `Range` iniciado por Starlette nativo en `/video`: `Range: bytes=0-99` → `206` con
    `Content-Range` y ventana exacta.
  - Lifecycle/lifespan: wiring de producción (repo+executor+service) se construye DENTRO del
    lifespan (no en import de módulo → sin pool sin cleanup); reconciliación de stale una
    vez al arrancar; `executor.shutdown()` en `finally` al apagar (garantizado ante salida
    excepcional).
  - requirements.txt: +fastapi/uvicorn/httpx. 60 tests web (`tests/test_web_*` +
    `test_web_lifecycle`); suite completa `1971 passed, 0 failed`; `git diff --check` limpio.
  - Smoke production lifespan PASSED (wiring en startup, reconcile 1 vez, `_shutdown=True`
    al salir). Ver `openspec/changes/web-ui-mvp/specs/job-api.md`.
- **Slice 3 (IMPLEMENTED / TESTED / REVIEWED / APPROVED / COMMITTED):** rebuild arquitectónico
  de la UI Angular bajo `web/frontend/` (el spike anterior en `frontend/` fue descartado y
  eliminado). Angular 21.2.x standalone (sin `AppModule`), feature-first, según la skill
  `angular-architecture`. Review formal: **`SLICE_3_APPROVED`**.
  - Workspace Angular standalone mínimo (`@angular/build:application` + tests Vitest
    `@angular/build:unit-test`); Node 20.20.0, npm 10.8.2. Checkpoint `npm install` y
    `npm run build` OK sobre el shell limpio.
  - Estructura feature-first: `features/generator/{model,data-access,application,
    generator-page,generator-form,job-progress,job-result}`; sin `core/`/`shared` vacíos.
  - Dependencias: UI → `GeneratorFacade` → `ShortsApiClient` → FastAPI; transport DTO
    (snake_case) → mapper → modelo de aplicación (camelCase).
  - `GeneratorPage` = composición; `GeneratorForm` Reactive Form (sin HTTP); `JobProgress`
    y `JobResult` presentacionales (sin polling ni `HttpClient`); `ShortsApiClient` solo
    transporte HTTP; `GeneratorFacade` orquestación/estado (signals + computed).
  - Polling lifecycle-safe: `timer(0, 1000)` + `exhaustMap` (sin solapamiento) +
    `takeWhile(..., true)` (incluye resultado terminal) + `takeUntilDestroyed`; sin
    `setInterval`; sin NgRx/Nx/event bus.
  - Capacidades desde `GET /api/v1/capabilities` (nunca duplicadas); preview/download vía
    `/api/v1/jobs/{id}/video` y `/api/v1/jobs/{id}/download`; sin paths de filesystem.
  - Errores API mapeados a `{code, message, status}` saneado (nunca raw/traceback).
  - Tests: 49 (`*.spec.ts` co-located). `npm test -- --watch=false`: 49 passed.
    `npm run build`: OK (producción, 76.88 kB transfer). Backend
    `python3 -m pytest -q tests`: `1971 passed, 0 failed`. `git diff --check` limpio.
- **NO implementado todavía:** executor/servidor Uvicorn de despliegue (Slice 4), build de
  producción servido por FastAPI, volumen persistente, autenticación, persitencia avanzada,
  Docker/UI.
- **Seguridad/API de diseño planificada y especificada, NO desplegada:** API nunca acepta/
  devuelve paths; recursos job-scoped por UUID; DTO allowlist; errores centralizados
  saneados; UUID no es autorización. Ver `openspec/changes/web-ui-mvp/specs/web-security.md`.
- No describir componentes web planificados como runtime existente.

## Cambio cerrado: `script-watchability-v1` — COMPLETED / VERIFIED / CLOSED / MERGED (merge `745db7f`, no-ff)

- Mejora watchability de guiones: contrato editorial en prompts (hook escena 1,
  desarrollo/progresión, cierre, factualidad) y CTA no obligatorio; políticas de repair
  EXPAND/COMPRESS con límites. Hardening final hook/cierre (pregunta tópica genérica
  desaconsejada, cierre sin resumen adjetival).
- Ramas `change/script-watchability-v1`; tests `test_script_watchability.py` (31); suite
  `1880 passed, 0 failed`; `git diff --check` limpio. Commits `9acbf58` + `cb2d9f7` + `9fadc10`.
- E2E final `cmo-2026-08-20-164453` (delfines) **VALIDATED** — `VIDEOS_ONLY` + Pexels,
  27.92s in-range (27-33), 2 repairs EXPAND→COMPRESS→PASS, hook contenido-primero, sin CTA
  promocional, cierre con consecuencia/payoff. Runs AUTO previos quedaron `ASSETS_PARTIAL` por
  supply de ilustración/diagrama (limitación preexistente, ajena al change), conservados como
  evidencia histórica; no se afirma que los E2E AUTO fueran VALIDATED. Engagement configurable
  sigue DEFERRED.
- Ver `openspec/changes/script-watchability-v1/results.md`. Merged no-ff a `main` `745db7f`.

## Cambio cerrado: `auto-mixed-visual-runtime` — COMPLETED / VERIFIED / CLOSED / MERGED (merge `0ea44e1`, no-ff)

- AUTO y MIXED usan la preferencia editorial real del LLM (`mediaPreference`
  explícito por segmento) con routing multi-kind y fallback compatible, sin
  debilitar IMAGES_ONLY/VIDEOS_ONLY.
- Prompt V2 emite mediaPreference + guard `MEDIA_PREFERENCE_MISSING` estricto.
  Router multi-kind con reconciliación de `mediaDecision` frente a los media
  kinds supervivientes a constraints/source policy; `mediaFallback`/
  `PREFERRED_MEDIA_EXHAUSTED` distinguen fallback runtime de degradación.
  MIXED diversity best-effort EITHER-only (selected-only counts).
  Queries VIDEO medium-neutrales (`medium_neutral_query`).
- Suite: baseline `1809` → Slice 1 `1843` → final `1849 passed, 0 failed`;
  `git diff --check` limpio.
- Mixed local smoke PASS (`mixed-local-smoke`: IMAGE/VIDEO/IMAGE, 1080x1920,
  19.08s, validate PASS). AUTO E2E `cmo-2026-08-20-152730` VALIDATED
  (8 IMAGE + 1 VIDEO, sin fallback). Real MIXED runtime run `por-2026-08-20-153502`
  ASSETS_PARTIAL (9/10, mezcla editorial 5 IMAGE + 4 VIDEO). Modos duros sin
  regresión. Limitación aceptada: supply de ilustración/diagrama puede dar
  ASSETS_PARTIAL.
- Ver `openspec/changes/auto-mixed-visual-runtime/`.

## Cambio cerrado: `pexels-photos-runtime` — COMPLETED / VERIFIED / CLOSED

- Pexels Photos is `AVAILABLE` as an explicit opt-in IMAGE/STOCK provider. It
  never enters defaults; Pexels Video remains `PLANNED`.
- Shared client, Photos adapter, provisional BM25 ordering, provider-fit,
  existing lifecycle/gates, fallback and bridge provenance are implemented.
  BM25 is `PROVISIONAL_BM25` / `NOT VALIDATED`; semantic and pixel gates remain
  the acceptance authority.
- Smoke A: one integrated request, `ASSETS_READY`, 1/1 resolved,
  `RELEVANT`, pixel gate `DISABLED`, raw rank 15, provider rank 1, remaining
  24848. Smoke B: bounded run, 5/7 resolved, `ASSETS_PARTIAL`; remaining
  decreased 24847 → 24841, exact request count `UNKNOWN`.
- Validation: Slice 1 `99` focused / `1751` full; Slice 2 `333` focused; closure
  suite `1758 passed, 0 failed`; `git diff --check` clean.
- Merged into `main` by `5b340db`.

## Cambio cerrado: `pexels-video-runtime-mvp` — COMPLETED / VERIFIED / CLOSED / MERGED (no-ff, merge `bfabf4d`)

- PRODUCT CHANGE. FIRST REAL VIDEO E2E antes de más research de Video. Reusa los
  contratos `IMAGE | VIDEO` existentes; Pexels Video explicit opt-in
  (`--asset-providers pexels --visual-mode videos-only`), sin query adaptation,
  diversity/dedup, smart clip selection, Video audio ni OpenCLIP sobre MP4.
- Slice 1 COMPLETE: capability-aware `visualMode` routing, adapter Pexels Video
  con selección determinista de portrait MP4, lifecycle/downloader (con fix de
  User-Agent), degradación semántica acotada, pixel NOT_APPLICABLE y transporte
  público vía bridge/assets-stage.
- Slice 2 COMPLETE: prepare/renderTimeline, validación media-aware
  (ffprobe/Docker vs Pillow), inputs VIDEO `-stream_loop -1` / mute / crop
  1080x1920 / LOOP_FROM_START, reserva cross-scene selected-only y política
  sparse-metadata partial-match. `resolvedConfig.visuals` alinea el modo
  efectivo (`visualMode` canónico; `mode: images` solo para IMAGES_ONLY).
- Primer E2E Video real `la-2026-08-19-235138` (delfines): `VALIDATED`, 4/4
  VIDEO, 1080x1920 H.264, narración-only, subtitles, 18.52s en rango 18–22s
  PASS. `pexels.video.stock` `AVAILABLE`. Suite `1809 passed`.

## Cambio cerrado: `pexels-photo-selection-benchmark` — COMPLETED / VERIFIED / CLOSED

- Investigación evaluation-only de selectores metadata para ordenar top-3 de
  Pexels Photos. Verdict **`METADATA_SELECTION_EVIDENCE_INSUFFICIENT`**, sin
  selected strategy, `phaseBRequired=false`. Solo 2 queries discriminating (min
  8); A1 no valida, A2 no valida ni NOT_USEFUL (señal PlayStation prometedora).
  Sin runtime, sin Phase B/OpenCLIP.
- Pexels Photos runtime is now completed; A2 BM25 remains usable as top-N
  PROVISIONAL (documentado
  NOT VALIDATED, decisión de ingeniería reversible, no conclusión del
  benchmark); preservar `pexelsQueryRank`, separar futuro `providerRank`;
  semantic/pixel gates siguen siendo autoridad de acceptance; fallback
  permanece; telemetry/provenance para detectar problemas reales.
- `pexels-photo-selection-evidence-extension`: DEFERRED / OPTIONAL, revisit solo
  si evidencia real del runtime lo requiere (no es el siguiente change).

## Change activo: `visual-media-strategy` — COMPLETED / VERIFIED / CLOSED

- Slice 1 fue puro y aditivo: contrato `visualSequence[].mediaPreference`, policy
  `request.visuals.visualMode`, `MediaStrategyDecision` y registry estático de
  capabilities. Sin router productivo, runtime Pexels/VIDEO, executor, prepare,
  renderer, prompt o CLI. Slice 2B posteriormente cableó internals de executor
  y Pixabay, sin cambiar routing, bridge ni metadata pública.
- `mediaPreference` usa `IMAGE_PREFERRED | VIDEO_PREFERRED | EITHER`; ausencia
  histórica canonicaliza a `IMAGE_PREFERRED` bajo VisualPlan schema v2, sin
  reescribir metadata ni elevar versión.
- `visualMode` usa `AUTO | IMAGES_ONLY | VIDEOS_ONLY | MIXED`; ausencia o
  `mode: images` legado significan `IMAGES_ONLY`. Conflicto explícito si ambos
  se contradicen. MIXED es diversidad best-effort, nunca obligación ni descenso
  de calidad.
- El registry separa `pexels.photos.stock` (IMAGE, AVAILABLE, opt-in explícito,
  photograph DIRECT)
  de `pexels.video.stock` (VIDEO, PLANNED, photograph CONDITIONAL); las formas
  exactas son UNSUPPORTED según `pexels-provider-fit-benchmark`. No hay claim de
  runtime ni secretos en registry.
- Validación: focales `130 passed`; suite completa `1650 passed, 0 failed`;
  `git diff --check` limpio.
- Commit: `57479c1` (`feat(visual): add media strategy contracts`).
- Slice 2A hardens only pure contracts: form support is distinct from runtime
  availability in `MediaStrategyDecision`; enums live authoritatively in
  `contracts.visual_media`; absent fit is `UNDECLARED`, not unsupported; and
  capability fit mappings are immutable. `CandidateEnvelope`, Attempt and
  SelectionResult model discovery, gate outcomes and selection invariants; the
  top-N helper preserves discovery order and does not rerank by score.
- Slice 2A made no router/executor/provider/semantic/fidelity/bridge/CLI/render
  change. Validation: focales `66 passed`, VisualPlan `106 passed`, suite
  completa `1692 passed, 0 failed`; `git diff --check` limpio. Commit `c0449f6`
  (`feat(assets): add candidate selection contracts`).
- Slice 2B cablea los contratos candidate al lifecycle first-accepted actual de
  Wikimedia/Pixabay mediante callbacks, sin serializar envelopes/attempts ni
  modificar bridge/metadata pública. Mantiene el orden de provider y queries,
  cache/exclusions y límite 20 de Wikimedia; el comportamiento de primera query
  viable, orden de candidates devuelto por provider, posición final del stream
  como `provider_rank` y límite 20 de Pixabay; semantic antes de download y
  fidelity después. No hay reranking, pool cross-provider, diversity, Pexels ni
  VIDEO runtime. Afectados: `331 passed`; suite completa `1699 passed, 0 failed`;
  `git diff --check` limpio. Commit `9381435`
  (`refactor(assets): unify candidate selection lifecycle`).
- Hardening final: `provider_rank` de Pixabay es la posición 1-based del stream
  final de candidates y no rank remoto/subquery. Tests reales de executor cubren
  progresión semantic/download/pixel, cleanup, cap de 20 y precedence
  `DOWNLOAD_FAILED`; la evidencia es parity-preserving, no equivalencia formal
  before/after. Validación: focales `257 passed`; suite `1703 passed, 0 failed`;
  `git diff --check` limpio. Commit `c2d66f8`
  (`fix(assets): harden candidate lifecycle parity`).

## Investigación cerrada: `pexels-provider-fit-benchmark` — COMPLETED / VERIFIED / CLOSED (mergeada a `main`)

- Benchmark-first del **PROVIDER FIT** de Pexels Photos/Video y de
  `query-adapt-v1`, sin runtime Pexels, rendering, VisualPlan/schema,
  OpenCLIP/BLIP/VLM, generación de imágenes ni perceptual hash. Base `cf391c5`;
  commits `6b18d01` (benchmark), `d948300` (hardening) y cierre documental.
- Evidencia: 58 rows → 56 queryUsed; 39 requests Video adaptadas históricas
  (cap 40, rate-limit 24849/25000). **0 requests, descargas o regeneración de
  contact sheets** durante hardening/cierre. Suite de cierre `1626 passed`.
- Revisión humana: Photos **PEXELS_BETTER=4 / CURRENT_BETTER=3 / TIE=3**;
  Video **ADAPTED_BETTER=2 / RAW_BETTER=1 / TIE=3 / BOTH_UNUSABLE=4**. Pexels
  es complementario, no sustituto global de Wikimedia/Pixabay.
- **`PEXELS_PROVIDER_FIT_VALIDATED`**: exact forms
  (diagram/infographic/illustration/painting) no son satisfacción directa
  Pexels; photograph habilita Photos como provider y Video como candidate.
  `ELIGIBLE` no implica candidate accepted ni fidelidad garantizada; sin matriz
  intent×assetPreference nueva.
- **`QUERY_ADAPTATION_COMPLEMENTARY_NOT_DEFAULT`**: candidate set materialmente
  distinto y ligera diversificación, pero Video review 2 mejor / 1 peor / 3 tie
  / 4 inutilizable. Futuro: pool RAW+ADAPTED y selección posterior; no sustituir
  RAW por ADAPTED.
- **`PEXELS_TOPN_SELECTION_REQUIRED`**: API rank #1 no es asset final.
  `PlayStation Nintendo 64 comparison photograph`: Pexels Photo #3 claramente
  superior; `four stroke engine automobile photograph` conserva el caso top-N
  Video. Diversity/dedup continúa como limitación within-job/topic.
- Roadmap separado: `pexels-photos-runtime` image-only (provider adicional,
  routing provider-fit, top-N), después contrato `VisualAsset kind = IMAGE |
  VIDEO`, luego `pexels-video-runtime` (RAW+adapted, clips,
  normalización/rendering), candidate-selection/diversity. Generación de
  imágenes y manual uploads siguen posteriores.
- Marcador `PEXELS_PROVIDER_FIT_BENCHMARK_CLOSED_AND_MERGED`. Sin push, sin
  reindex.

## Investigación cerrada: `pexels-visual-supply-benchmark` — COMPLETED / VERIFIED / CLOSED (mergeada a `main`)

- Benchmark-first del SUPPLY visual de Pexels (**Video + Photos**) frente al
  stack Wikimedia/Pixabay. Sin integración runtime; sin tocar rendering/
  OpenCLIP/BLIP/VLM/VisualPlan; sin relabel. Base real del benchmark:
  **`de570fa`** (no `321da8a`).
- Datasets reutilizados sin relabel: canonical-38 + development-20 = 58 rows →
  56 queryUsed únicas (dedup exacto; se conserva mapping query→rows y
  `assetPath`).
- **Pexels Video** (fase previa): cobertura **56/56, HIGH_SUPPLY** (>=720x1280
  y >=1080x1920 = 1.0); requests 56/100; 12 clips rank#1 (720x1280); contact
  sheets `01-...-temporal-...` (corregido: aspectos, sin solapamiento) y
  `02-...-top3-...`.
- **Pexels Photos** (extensión): cobertura **56/56, HIGH_SUPPLY** —
  fracción >=720x1280 y >=1080x1920 = **1.0** (originales portrait alta res);
  requests **56/70** (main 56, diag 0); `candidatesReturned=840`,
  `originalPortraitCount=840`; diagnóstico 0 (56/56 `PORTRAIT_SUPPLY_OK`);
  rate-limit `remaining=24888/25000`; 12 rank#1 originales descargados, 0
  fallos.
- Revisión humana externa: Pexels prometedor para fotografía/sujetos físicos/
  ubicaciones/personas/objetos/B-roll tech/server; **no** fiable para visual
  forms explícitos (diagram/infographic/illustration/plan/construction-time);
  raw rank #1 no siempre es el mejor candidato; overlap/repetición en
  castillos/data-center (diversity/dedup futuro); Photos CURRENT vs Pexels:
  **complementarios**.
- **Decisión: `PEXELS_CONDITIONAL_PROVIDER_PROMISING`** — supply validado;
  continuar hacia integración; NO sustituto global; NO integrar todavía; en
  cierre `1586 passed, 0 failed`. Dirección siguiente (separada, NO
  implementada): `pexels-provider-fit-benchmark`.
- Contact sheets en `data/evaluations/pexels-visual-supply-benchmark/`
  (git-ignored): `01-pexels-video-temporal-contact-sheet.png`,
  `02-pexels-top3-search-results.png` y
  `03-pexels-photo-vs-current-contact-sheet.png` (CURRENT vs PEXELS #1/#2/#3).
  Evidencia de vídeo en `data/evaluations/pexels-video-supply-benchmark/`.
- Harness `tools/pexels_photo_supply_benchmark.py` + `tools/pexels_video_supply_benchmark.py`
  (evaluation-only, stdlib urllib, import-safe/offline, User-Agent, key no
  leak). Tests `tests/test_pexels_photo_supply_benchmark.py` (**30 passed**) +
  `tests/test_pexels_video_supply_benchmark.py` (**30 passed**), sin llamadas
  reales.
- Ver `openspec/changes/pexels-visual-supply-benchmark/`.

## Investigación cerrada: `visual-fidelity-vlm-judge-v2` — COMPLETED / VERIFIED / CLOSED (mergeada a `main`)

- Evaluación benchmark-first de un judge multimodal API **menos conservador**
  (`gpt-5.6-luna`, Responses API, una request independiente por asset) frente a
  OpenCLIP y BLIP como segunda etapa visual-semántica. Sin cambios de runtime.
- Contrato del judge: 3 vías `verdict: ACCEPT | REJECT | UNCERTAIN` +
  `reasonCode` + `shortReason`, Structured Output estricto, imagen
  `detail=high`, `reasoning none`, sin tools, SIN `humanLabel`/scores/verdicts
  previos/expected. Input semántico: `queryUsed` + `assetPreference` solo si
  forma parte del contrato persistido del segmento. REJECT solo en mismatch
  material; métrica operativa **UNCERTAIN ⇒ ACCEPT** (fail-open).
- Harness evaluation-only `tools/visual_fidelity_vlm_judge_v2.py` (lazy-import
  openai). Semántica autoritativa de reasonCode = `REASON_CODE_VERDICTS`:
  `INSUFFICIENT_VISUAL_EVIDENCE` puede acompañar ACCEPT, REJECT o UNCERTAIN.
- Preflight de tokens + hard cap `$0.10` (58 assets = 38 canonical + 20 dev).
  Proyección total `$0.030613` (READY); coste real persistido **`$0.013051`**;
  latencia mediana ~1.58-1.59 s, p95 2.6-6.0 s. Sin API key ni base64 en outputs.
- Datasets reutilizados SIN relabel: 38 canónicos y 20 fresh. Los 20 NO cuentan
  como holdout nuevo; son **development evidence**, sin afirmar generalización.
- Resultados: canonical-38 **21/30 retained + 8/8 badRejected** (FA 0, FR 9, 0
  UNCERTAIN); development-20 **4/13 usableRetained + 5/7 badRejected** (FA 2,
  FR 9, 0 UNCERTAIN). El fail-open no llegó a activarse (0 UNCERTAIN).
- Casos críticos: resuelve 4/5 (data-center vs blockchain art, castillo final
  vs construcción, castillo vs planos, castillo vs construction-time diagram);
  falla **motor 2T vs 4T** (lo acepta, mismo punto ciego que OpenCLIP).
- **DECISIÓN: `VLM_JUDGE_V2_NOT_USEFUL`** — falla canonical (21/30<24/30) y
  development (4/13<11/13). Mejor rechazo de bad assets que OpenCLIP/BLIP pero
  peor retención de buenos. **No integración runtime, sin holdout nuevo.**
  OpenCLIP ViT-B-32 @0.2296 sigue como pixel gate vigente cuando está activado;
  `visual-fidelity-runtime` sigue OFF por defecto salvo `VISUAL_FIDELITY_THRESHOLD`.
- Tests: `tests/test_visual_fidelity_vlm_judge_v2.py` (20 passed). Suite en
  cierre: `1526 passed, 0 failed`. Commit cierre documental; merge no-ff a `main`.
- Ver `openspec/changes/visual-fidelity-vlm-judge-v2/`.

## Investigación cerrada: `visual-fidelity-compositional-benchmark` — COMPLETED / VERIFIED / CLOSED (mergeada a `main`)

- Comparación benchmark-first de BLIP ITM (`Salesforce/blip-itm-base-coco`) frente al gate OpenCLIP actual, para comprobar si una cabeza explícita de image-text-matching (late fusion + ITM) mejora la fidelidad composicional (variante de entidad, relaciones tipo-de-contenido/escena) frente al coseno global. Sin cambios de runtime de producción.
- Conclusión canónica: BLIP ITM correcto **clase 1 = MATCH**; calibration (38) **24/30 retained + 6/8 badRejected** (retention 0.80, recall 0.75, FA 2, FR 6) ELIGIBLE; threshold experimental BLIP **0.06636959873139858** (bloqueado antes del holdout); fresh holdout **9/13 usable + 2/7 badRejected**; OpenCLIP fresh holdout @0.2296 **13/13 + 0/7**. **Decisión: TRADEOFF_ONLY**. **BLIP NO se integra en runtime**; OpenCLIP sigue como pixel gate vigente cuando está activado; `visual-fidelity-runtime` sigue OFF por defecto salvo `VISUAL_FIDELITY_THRESHOLD`. La iteración antigua `[0,0]` (threshold 0.015839167404919863, 27/30 + 1/8, NOT_USEFUL) permanece explícitamente **INVALIDADA**.
- Holdout 20: `tests/fixtures/asset_visual_fidelity/holdout_labels.json` (3 CLEARLY_RELEVANT / 10 COARSE_BUT_USABLE / 7 FALSE_POSITIVE_OR_UNUSABLE → 13 ACCEPT / 7 REJECT por labels individuales; el enunciado decía "12/8" globalmente pero el listado individual suma 13/7 y es autoritativo). Disjunto de los 38 canónicos. Imágenes en `data/videos/` (git-ignored); contact sheets en `data/evaluations/visual-fidelity-fresh-e2e/`.
- Evaluación: `tools/visual_fidelity_compositional_benchmark.py` (evaluation-only, lazy-import ML, modelos `blip_itm_base`/`openclip_vit_b32`, device auto/cuda/cpu) en el MISMO entorno aislado externo `/tmp/shorts-visual-fidelity-gpu-venv` (torch 2.11.0+cu128, transformers 5.15.0, Pillow 12.3.0; caché HF `/tmp/shorts-visual-fidelity-hf`). BLIP: `BlipProcessor` + `BlipForImageTextRetrieval`, `use_itm_head=True`, raw `queryUsed`, `eval()`/`no_grad()`/batch=1/RGB/GIF frame 0, score = `softmax(itm_score.float())[0, 1]` = matchProbability. El contrato clase-1=MATCH es la convención oficial Salesforce BLIP (`train_retrieval.py` etiqueta los pares positivos con `ones`; `eval_retrieval.py` puntúa con `itm_head(...)[:, 1]`) y está reforzado por una sanity check de orientación en-run y tests unitarios offline — la clase 0 es NOT-MATCH y nunca se usa como score. `matchProbability` y `notMatchProbability` se persisten por asset. Política de métricas/umbral REUTILIZADA de `tools/visual_fidelity_benchmark.py` sin cambios. Scoreado en GTX 1650 SUPER: BLIP ~136 ms mediana, p95 ~153 ms, pico VRAM 924.6 MiB, sin OOM, load ~4.3 s; OpenCLIP (mismo tool/device, holdout) ~8.3 ms mediana, pico VRAM 624.8 MiB.
- Calibración (38, umbral bloqueado ANTES del holdout): BLIP seleccionó umbral **0.06636959873139858**, **24/30 retained + 6/8 badRejected** (retention 0.80, recall 0.75, FA 2, FR 6) → cumple el target provisional de elegibilidad (>=24/30 y >=6/8). Referencia OpenCLIP @0.2296: 25/30 + 7/8. NOTA: los resultados previos con `[0,0]` eran un bug — la clase 0 es NOT-MATCH en BLIP, por lo que esa corrida puntuó la semántica equivocada (umbral 0.0158 y 27/30 + 1/8 quedan INVALIDADOS).
- Holdout (umbral bloqueado): BLIP **9/13 usable retained + 2/7 badRejected** (FA 5, FR 4); OpenCLIP @0.2296 **13/13 + 0/7** (FA 7, FR 0). BLIP rechaza los 2 false positives críticos más difíciles (motor 2T vs query 4T, blockchain/digital-art vs infraestructura data-center) que OpenCLIP acepta, pero rechaza 4 assets buenos adicionales que OpenCLIP conserva.
- Los 5 casos composicionales críticos (motor 2T vs query 4T, castillo final/no-construcción vs foto de construcción, castillo vs planos arquitectónicos, castillo vs diagrama temporal de construcción, blockchain/digital-art vs infraestructura data-center): BLIP rechaza 2/5 (motor 2T, blockchain/digital-art); los 3 casos de castillo siguen aceptados por ambos modelos.
- **DECISIÓN: TRADEOFF_ONLY** — mejora rechazo (2/7 vs 0/7 holdout; calibración 6/8 + 24/30) pero retención insuficiente (9/13 vs 13/13); no alcanza STRONG (>=10/12 y >=6/8) ni PROMISING (>=9/12 y >=5/8). SIN integración runtime; OpenCLIP ViT-B-32 @0.2296 sigue como pixel gate; `visual-fidelity-runtime` sigue OFF por defecto salvo `VISUAL_FIDELITY_THRESHOLD`. Los targets son criterios de investigación, no contrato de producción. Dirección futura (fuera de alcance aquí): judges sensibles a tipo/contenido (p.ej. la dirección API de Slice 3B) o una fusión de la señal de rechazo de BLIP con la retención de OpenCLIP.
- Commits: `2426016` (benchmark), `4328438` (corrección orientación), cierre documental. Merge no-ff a `main`. Suite en cierre: `1506 passed, 0 failed`.
- Ver `openspec/changes/visual-fidelity-compositional-benchmark/`.

## Change cerrado: `visual-fidelity-runtime` — COMPLETED / VERIFIED / CLOSED (mergeado a `main`)

- Objetivo: productizar OpenCLIP como SEGUNDO gate visual en assets de producción: `metadata gate -> pixel gate -> ACCEPT/REJECT -> siguiente candidato`. El gate de metadata (`deterministic_anchor_coverage_v2`) se mantiene como primera etapa barata y sin cambios.
- Modelo/texto: OpenCLIP `ViT-B-32` / `laion2b_s34b_b79k`, política de texto P1 = `queryUsed`. Justificación: `asset-visual-semantic-fidelity` (CLOSED) midió 25/30 retained + 7/8 badRejected ELIGIBLE (umbral calibrado 0.2296, LOTO 24/30 + 7/8) y decidió `LOCAL_ENCODER_PREFERRED` frente a la API multimodal (17/30 + 8/8).
- Slice 1 COMPLETADO: `src/shorts_creator/assets/visual_fidelity.py` (componente) + tests. Backend lazy singleton (lock thread-safe, fallo cacheado), CUDA automático con fallback CPU + `device_override` para tests, `model.eval()` + `torch.no_grad()`, coseno normalizado, GIF frame 0 sin mutar el archivo, status `SCORED`/`UNAVAILABLE`/`DISABLED`, verdict `ACCEPT`/`REJECT`/`BYPASS`, nunca lanza (fail-soft). Config: solo `VISUAL_FIDELITY_THRESHOLD` — sin threshold/inválido/no-finita → `DISABLED`; torch/open_clip ausente o fallo de load/scoring → `UNAVAILABLE`. Sin imports ML/PIL a nivel de módulo.
- Slice 2 COMPLETADO: integrado en `assets/executor.py` post-descarga/pre-RESOLVED (wikimedia + pixabay) vía `_apply_visual_fidelity_gate(archivo, queryUsed)` provider-agnostic. `SCORED+ACCEPT` → RESOLVED con `visualFidelityAssessment`; `SCORED+REJECT` → borrar archivo + `visualFidelityRejections` + siguiente candidato (agotamiento → `NO_RESULTS`/`DOWNLOAD_FAILED` con `visualFidelityRejections`); `DISABLED`/`UNAVAILABLE` → bypass explícito con warning `VISUAL_FIDELITY_BYPASS:{status}` + assessment persistido. `bridge.py` propaga `visualFidelityAssessment` (+ `_visualFidelityRejections` en unresolved). Hardening: text tokens al device del modelo, score no-finito/no-numérico → `UNAVAILABLE`, imagen cargada con context manager (GIF frame 0 intacto).
- Slice 3 COMPLETADO (validación runtime real): `score_visual_fidelity` sobre el corpus canónico de 38 assets con venv GPU externo `/tmp/shorts-visual-fidelity-gpu-venv` (torch 2.11.0+cu128, open_clip_torch 3.3.0, caché HF reutilizada, device cuda GTX 1650 SUPER). **25/30 retained + 7/8 badRejected**, 38/38 SCORED (0 UNAVAILABLE/DISABLED), scores idénticos al benchmark (<1e-6, max 6.1e-7), goodAssetRetention 0.8333, badAssetRejectionRecall 0.875, falseAcceptances 1 (ilustración Porsche moderno), falseRejections 5. Latencia: total 5.4 s (incl. ~4.3 s de carga), mediana 24.5 ms, p95 214 ms. Reproduce exactamente el benchmark y cumple el target (>=24/30 y >=6/8). Rows: `data/evaluations/visual-fidelity-runtime/runtime-validation.json` (git-ignored).
- Activación: gate OFF por defecto; `VISUAL_FIDELITY_THRESHOLD=0.2296` es la ÚNICA superficie de activación (threshold validado/candidato versionado en `design.md` — NUNCA default hardcodeado). OpenCLIP sigue como dependencia opcional (no en `requirements.txt` base); caché de pesos (`$HF_HOME/hub/models--laion--CLIP-ViT-B-32-laion2B-s34B-b79K`) y memoria CPU/GPU documentadas en `design.md`.
- Commits: `0c807aa` (plan), `86b6162` (slice 1), `ba7bb5f` (slice 2), `3be610d` (slice 3). Mergeado a `main` (no-ff). Fuera de alcance: OpenAI/VLM, Slice 3B, nuevos providers, search-vs-generation, UI.
- Ver `openspec/changes/visual-fidelity-runtime/`.

## Investigación cerrada: `asset-visual-semantic-fidelity` — COMPLETED / VERIFIED / CLOSED

- Seguimiento de la evaluación cerrada `generic-content-pipeline-evaluation` (CLOSED, decisión **YELLOW**): investigar una validación semántico-visual de SEGUNDA ETAPA basada en los píxeles (provider-agnostic, topic-agnostic), conservando el gate de metadata actual (`deterministic_anchor_coverage_v2`) como primera etapa barata. Benchmark-first: sin cambios de runtime de producción hasta que la evidencia lo justifique.
- Labels canónicas de los 38 assets rastreadas por Git en `tests/fixtures/asset_visual_fidelity/labels.json` (16 CLEARLY_RELEVANT / 14 COARSE_BUT_USABLE / 8 FALSE_POSITIVE_OR_UNUSABLE; interpretación binaria ACCEPT = CR+CU, REJECT = FP). Las imágenes permanecen en `data/videos/` (git-ignored).
- Harness offline stdlib-only `tools/visual_fidelity_benchmark.py`: valida labels, calcula goodAssetRetention / badAssetRejectionRecall / falseAcceptances / falseRejections / confusionMatrix, sweep y selección de umbral deterministas (max badRejected sujeto a good retention >= 0.80, luego max acceptableRetained entre empates, umbral más estricto solo si ambos empatan), validación de scores numéricos finitos. Target de elegibilidad del experimento PROVISIONAL: bad rejection >= 6/8 y good retention >= 24/30 — NO es umbral de producción.
- Slice 2 (COMPLETADO, CPU-first): `tools/visual_fidelity_local_benchmark.py` evaluation-only en entornos aislados FUERA del repo (`/tmp/shorts-visual-fidelity-venv` CPU torch 2.13.0+cpu / open_clip_torch 3.3.0 / transformers 5.15.0; GPU `/tmp/shorts-visual-fidelity-gpu-venv` torch 2.11.0+cu128). Estas deps del benchmark NO son deps del proyecto. Resultados calibrados (conteos crudos): OpenCLIP ViT-B-32/laion2b_s34b_b79k P1 25/30 + 7/8 ELIGIBLE (umbral 0.2296, LOTO 24/30 + 7/8); P2 26/30 + 6/8 ELIGIBLE; SigLIP2 base P1 26/30 + 5/8 NEAR_MISS; P2 24/30 + 4/8 NOT_USEFUL. GIF evaluado en frame 0 (coincide con el benchmark humano). CPU medido: OpenCLIP ~39 ms mediana/p95 ~43 ms, RSS ~1.5 GiB; SigLIP2 ~148 ms mediana, RSS ~1.7 GiB. Viabilidad GPU (mejor candidato OpenCLIP ViT-B-32 P1): GTX 1650 SUPER 4 GB batch=1 sin OOM, 690.6 MiB max allocated, mediana 9.8 ms/p95 11.3 ms, scores GPU==CPU (<1e-6). Decisión: **LOCAL_ENCODER_PROMISING** — no integrar aún; Slice 3 (API multimodal) sigue útil para fallos de acción/escena y entidad/temporal (el único bad asset no rechazado por ninguna fila fue la ilustración del modelo Porsche moderno).
- Slice 3A (COMPLETADO): benchmark OpenAI Responses API solo con `gpt-5.6-luna`, `detail=high`, Structured Output, una request independiente por asset y preflight exacto con cap `$0.25`. 38/38 completadas; 68,117 input tokens, 1,011 output, 0 cached/reasoning; coste real `$0.0148366`, promedio `$0.0003904368/asset`; mediana 1.414 s, p95 3.663 s. Métricas: 17/30 retained, 8/8 badRejected, 0 falseAcceptances, 13 falseRejections. Frente a OpenCLIP P1 (25/30, 7/8), decisión **LOCAL_ENCODER_PREFERRED**. Rechazó el Porsche moderno con `WRONG_VARIANT_OR_ERA`; no hay integración runtime.
- Slice 3B (futuro separado): posible escalado selectivo/API o contrato menos conservador, sin probar modelos adicionales automáticamente.
- Ver `openspec/changes/asset-visual-semantic-fidelity/`.

## Evaluación cerrada: `generic-content-pipeline-evaluation` — COMPLETED / VERIFIED / CLOSED

- Benchmark de genericity del pipeline ACTUAL completado (harness offline Fase 1 + ejecución real de 8 temas Fase 2 + revisión visual externa de píxeles). Contact sheets en `data/evaluations/genericity-phase2-visual-review/` (git-ignored).
- Resultado agregado: **YELLOW**. La capa script/VisualPlan es sana y topic-agnostic en los 8 dominios (sin `QUERY_GEN_FAILURE` ni `VISUAL_PLAN_FAILURE`; 0 queries VAGUE; retries 0). Por tema: Volcán `HEALTHY`; Aurora/Porsche/Spring Boot/Pulpos/Videojuegos/Hipoteca `USABLE_WITH_LIMITATIONS`; Roma `SYSTEMIC_FAILURE` (solo capa de assets, no comprensión de dominio).
- Revisión visual de los 38 resueltos: **16 CLEARLY_RELEVANT / 14 COARSE_BUT_USABLE / 8 FALSE_POSITIVE_OR_UNUSABLE**. Fallos repetidos de fidelidad visual/semántica en la aceptación downstream en dominios no relacionados; cobertura de provider limitada (software, videojuegos, conceptos difíciles de ilustrar) = SUPPLY, no corrupción de arquitectura.
- Conclusión de diseño: `asset-entity-fidelity` permanece como EVIDENCIA DE INVESTIGACIÓN SOLO (pausado). NO implementar `deterministic_anchor_coverage_v3` / `FORM_OR_MEDIUM_TERMS`. Cambio futuro registrado: **`asset-visual-semantic-fidelity`** (validación semántico-visual de segunda etapa por píxeles, provider-agnostic, manteniendo el gate de metadata como primera etapa; no diseñado). Dirección de producto separada registrada: fallback search-vs-generation para cobertura.
- Ver `openspec/changes/generic-content-pipeline-evaluation/` (informe completo: `phase2-report.md`).

## Change cerrado: `script-visual-specificity`

- Objetivo: mejorar la especificidad ascendente (script + VisualPlan/query) para que los providers visuales reciban conceptos concretos y recuperables en lugar de queries editoriales vagas (`popular culture`, `future of YouTube`, `viral YouTube video screenshot`, `famous early YouTubers photo`).
- Slice 1 (`f1e4a08`): vocabulario compartido puro en `contracts/visual_terms.py` (mover `GENERIC_FILLER`, `WEAK_SUPPORT_TERMS`, `tokenize`; añadir `STOPWORDS` guard-only), reexport en `assets/semantic.py` sin cambios de comportamiento, y guard conservador en `contracts/visual_specificity.py`.
- Slice 2 (`32f8c75`, `33c562d`): prompt con sujetos concretos/recuperables y grounding anti-alucinación (sin baneo general de "X of Y"), guard conectado a la validación V2 → retry existente, sección de remediación "Especificidad visual insuficiente", y filtro de derivación del router que descarta queries vagas. Sin churn de schema.
- Slice 3 + Slice 3A (`11bcc6d`): evidencia real y calibración. Run de descubrimiento `los-2026-08-17-204707` → `REVIEW_REQUIRED` bajo el guard inicial sobre-estricto → separación de `SPECIFICITY_WEAK_TERMS` (guard-only) del `WEAK_SUPPORT_TERMS` semántico y regla refinada del guard. Run final `los-2026-08-17-205843`: script aprobado en attempt 0 (retries 0), todas las queries persistentes `VALID`, `ASSETS_PARTIAL`, 4/10 resueltos.
- Suite completa en cierre: `1411 passed, 0 failed, 0 skipped`; `git diff --check` limpio. `deterministic_anchor_coverage_v2` sin cambios.
- Limitación aceptada: la query "Smosh fan art" produjo un falso positivo (arte genérico fan/art de Pixabay sin Smosh). Es comportamiento downstream de fidelidad entidad/sujeto del scorer semántico (sin cambios). Tras `generic-content-pipeline-evaluation`, el seguimiento se amplió a `asset-visual-semantic-fidelity`; `asset-entity-fidelity` queda como evidencia de investigación.

## Estado vigente
- Arquitectura modular V2 completa. `src/shorts_creator/` contiene contratos, pipeline, script, audio, assets, rendering, validation e infrastructure; `bin/` son adaptadores CLI.
- Pipeline canónico: `script -> assets -> audio -> prepare -> render -> validate`. n8n es legacy/alternativo.
- Primer E2E técnico completo: job `cmo-2026-08-16-172847`, hasta `VALIDATED`. Request: target 30s, rango 27-30; timeline 20.813s y MP4 aproximadamente 20.88s.
- El mismatch de duración descubierto confirmó que la medición TTS real debe prevalecer sobre el bootstrap WPM.

## Change cerrado: `generic-duration-fitting`
- Slice 1 completado: contrato post-TTS PASS/EXPAND/COMPRESS, ratio genérico 0.70..1.50, distribución por escena y repair voiceover-only desacoplado del presupuesto WPM.
- Slice 2 completado con tests focales simulados: loop en orquestador, máximo dos repairs, proyección compartida con prepare, regeneración TTS forzada y reutilización de assets. Si se agota, el job queda `REVIEW_REQUIRED` con `DURATION_FITTING_EXHAUSTED` sin ejecutar prepare/render.
- Hardening runtime de Slice 2: el repair reutiliza la resolución LLM del dominio script (`.env` incluido) y la regeneración preserva provider/voice/timing del audio previo. No amplía el path per-scene real a multi-provider TTS.
- Slice 3 completado (`6cfb8c3`): `requestedDurationCompliance` usa la duración real del MP4, queda separado de `renderDurationIntegrity`, se persiste en metadata/manifest y un producto fuera de rango termina `REVIEW_REQUIRED`, no `FAILED`.
- Intento E2E real `cmo-2026-08-16-184819`: bloqueado en script porque el gate histórico de estimación WPM rechazó un V2 válido de 67 palabras (37.9s estimados). Fix implementado: V2 válido => `SCRIPT_DRAFT`; la estimación bootstrap sigue como telemetría no bloqueante y TTS real decide después.
- E2E real `cmo-2026-08-16-190441`: el contrato legado de `--duration 30` era 27-30; comprimió 30.587s pese a estar cerca del target y aceptó 27.314s. El contrato canónico ahora usa presets centrados (`quick_30`=27-33, `standard_45`=41-49, `deep_60`=55-65) o duración custom con tolerancia simétrica.
- `quick_30` quedó validado en E2E `cmo-2026-08-16-194012`: una reparación, timeline 31.587s, MP4 31.72s, cumplimiento solicitado PASS y `VALIDATED`. `deep_60` (`cmo-2026-08-16-194540`) se bloqueó en audio con `DURATION_FITTING_EXHAUSTED`: el plan fijo de 4-6 escenas produjo cinco escenas de 12s. Fix implementado: planificación genérica de ~6s/escena; 60s permite 9-11 y prefiere 10.
- Hardening de runtime: retry prompts y repair post-TTS usan el `scenePlan` persistido, por lo que un deep_60 válido de 10 escenas no recae al fallback 4-6 durante EXPAND/COMPRESS.
- E2E canónico deep_60 `cmo-2026-08-16-203059`: MP4 60.37s, 9 escenas (plan adaptativo 9-11, preferencia 10), 2 reparaciones de voiceover, cumplimiento solicitado PASS y `VALIDATED`. El `cmo-2026-08-16-194540` fallido queda como contexto histórico de la planificación adaptativa.

## Change cerrado: `generic-tts-provider-runtime`
- Slice 1 completado: el runtime per-scene ya no fija `edge_tts`; `generate_audio_with_timestamps()` recibe el proveedor seleccionado vía `tts_provider` y `main_per_scene()` lo reenvía. La validación de disponibilidad es uniforme para todos los proveedores (sin fallback silencioso a Edge; credenciales ausentes fallan explícito).
- Modo continuo sigue siendo Edge-only: `continuous` con un proveedor no-Edge falla con `CONTINUOUS_TTS_PROVIDER_UNSUPPORTED` antes de sintetizar o mutar metadata. El modo continuo con ElevenLabs NO es compatible y queda fuera de alcance de este change.
- Slice 2 completado: ElevenLabs es ahora un proveedor per-scene con timing nativo real vía `POST /v1/text-to-speech/{voice_id}/with-timestamps`. El adapter decodifica `audio_base64`, mide el audio real y normaliza el alineamiento de caracteres a las mismas `word_boundaries` canónicas (prefiere `normalized_alignment`, cae a `alignment`; malformado → sin timing nativo → fallback estimado). `timing_support="word"`.
- Metadata corregida: Edge `timing_support="word"`; `activeDurationSource` es `subtitle_timing_last_cue_plus_guard` (neutro al proveedor). Se eliminó el leak de labels de fallback Edge en el generador genérico (`native_word_boundary`/`native_sentence_boundary`).
- Hardening de runtime (config, dentro de Slice 2): la resolución efectiva de provider/voz/secreto/modelo ahora lee `.env` del proyecto (y luego el entorno del proceso) y se calcula una sola vez en `generate_audio()`; la voz del provider (`ELEVENLABS_VOICE_ID`) gana sobre la voz por defecto de Edge, y la misma configuración se usa en disponibilidad y síntesis (inicial y regeneración). El API key no se persiste nunca.
- Plumbling de configuración TTS a nivel job (Slice 3): `bin/run_job.py` expone `--tts-provider`, `--voice`, `--subtitle-timing-provider`; el orquestador resuelve una vez la config efectiva (reuso de semántica de runtime de audio) y la propaga a las etapas `script` (persistida en `request.voice`/`request.subtitles` del metadata) y `audio` (comando inicial), además de mantenerla en las regeneraciones de fitting. `--voice` gana sobre el entorno; la API key nunca se escribe en comandos ni metadata.
- `cmo-2026-08-17-142952` se reclasifica como E2E de regresión Edge (historia muestra `--tts-provider edge_tts --voice es-ES-AlvaroNeural` en fitting), no como validación de ElevenLabs; la causa raíz era la ausencia de superficie `run_job` + `request.voice` hardcodeado.
- Smoke real de ElevenLabs: PASSED (`ELEVENLABS_REAL_SMOKE_OK`, voz `Xb7hH8MSUJpSbSDYk0k2`, 3.84s, `elevenlabs_normalized_alignment`, 10 word boundaries).
- E2E completo real canónico de ElevenLabs `cmo-2026-08-17-145309` (quick_30): target 30, rango 27-33; provider `elevenlabs` / voz `Xb7hH8MSUJpSbSDYk0k2` consistente en `request.voice`, `resolvedConfig` y audio final; todo el timing final de escenas `elevenlabs_normalized_alignment`; fitting inicial 47 palabras (20.065s, EXPAND) → repair 1 95 palabras (42.311s, COMPRESS) → repair 2 66 palabras (28.135s, PASS); MP4 final 28.20s; `requestedDurationCompliance` PASS, `subtitleCoverageValidation` PASS, `technicalValidation` PASS, `renderDurationIntegrity` PASS, `pacingValidation` PASS_WITH_WARNINGS; final `VALIDATED`.
- Estado final soportado: Edge per-scene y continuo VALIDADO (default); ElevenLabs per-scene VALIDADO (smoke + E2E real), continuo NO compatible, no es el default.
- `generic-tts-provider-runtime`: COMPLETED / VERIFIED / CLOSED.

## Change cerrado: `asset-semantic-relevance`

- Slice 1 completado: el router soporta `request.visuals.sourceProviders` (lista explícita de providers con orden preservado; omitida → fallback por defecto de la matriz; lista que deja 0 candidatos → `UNROUTABLE`). Superficie CLI: `bin/run_job.py --asset-providers wikimedia_commons,pixabay` → persistido en `request.visuals.sourceProviders` por la etapa script y encaminado al router por `fetch_images_v2.py`. Sin env vars nuevas ni providers nuevos.
- Contrato semántico genérico: `src/shorts_creator/assets/semantic.py` normaliza metadata nativa de provider (adaptadores Wikimedia/Pixabay) a un contrato común; el scorer es puro, determinista y sin ramas de provider.
- Gate semántico en executor: tras la búsqueda y ANTES de la descarga, en `_resolve_wikimedia` y `_resolve_pixabay`; `IRRELEVANT`/`UNSCORABLE` → skip candidato → next candidato/consulta/provider → `NO_RESULTS` con `semanticRejections` si se agota. Preferir unresolved sobre irrelevante.
- Postcondición genérica: un `RESOLVED` de provider search-strategy sin `semanticAssessment.verdict == RELEVANT` NUNCA entra en `resolvedAssets` (`PROVIDER_ERROR` + warning `SEMANTIC_POSTCONDITION:RESOLVED`). Se decide por `queryStrategy`, sin ramas por nombre de provider.
- Hardening v2 del scorer: `deterministic_anchor_coverage_v2` reemplaza a `token_overlap_v1`. `queryUsed` es la intención primaria; los términos del query se clasifican en anchors discriminativos vs `WEAK_SUPPORT_TERMS` (early/famous/future/popular/viral/logo/screenshot/section/media/social/video/...). Los weak por sí solos nunca producen `RELEVANT`; con múltiples anchors se exige cobertura significativa (≥ mitad, mínimo 2); los `subjects` de la escena no rescatan la falta de anchor. Diagnóstico persistido: `anchorTerms`, `matchedAnchors`, `weakMatches`, `anchorCoverage`.
- Replay real `los-semantic-v2-20260817-203235` sobre `los-2026-08-16-230341`: antes V1 resolvía 11/11 con assets severamente irrelevantes (Volkswagen, campanula/plum blossom, kiwi, flower/screenshot, coast); con V2 quedan **3 resuelto / 8 fallido, `ASSETS_PARTIAL`**. Los 3 aceptados son relevantes a YouTube (shorts, icon app mobile, iphone smartphone). Los falsos positivos obvios quedan rechazados.
- `asset-semantic-relevance`: COMPLETED / VERIFIED / CLOSED.

## Baseline y límites
- Baseline estable conocida en main: **`1215 passed, 0 failed`**. Suite completa de la rama activa tras presets/status: **`1198 passed, 51 skipped, 0 failed`**.
- `AUDIO_DURATION_MISSING` está resuelto. `ffprobe` no está en host y depende del fallback Docker.
- `generic-duration-fitting`: COMPLETED / VERIFIED / CLOSED. quick_30 `cmo-2026-08-16-194012`: VALIDATED. deep_60 `cmo-2026-08-16-203059`: VALIDATED (60.37s, 9 escenas). Suite completa al cierre: **`1243 passed, 0 skipped, 0 failed`**.
- `generic-tts-provider-runtime`: COMPLETED / VERIFIED / CLOSED. Smoke real `ELEVENLABS_REAL_SMOKE_OK`; E2E ElevenLabs `cmo-2026-08-17-145309`: VALIDATED (28.20s). Suite completa al cierre: **`1306 passed, 0 skipped, 0 failed`**.
- `asset-semantic-relevance`: COMPLETED / VERIFIED / CLOSED. Replay real v2 `los-semantic-v2-20260817-203235`: **3 resuelto / 8 fallido, `ASSETS_PARTIAL`** (V1 era 11/11 irrelevante). Suite completa al cierre: **`1345 passed, 0 skipped, 0 failed`**.
- `generic-content-pipeline-evaluation`: COMPLETED / VERIFIED / CLOSED. Benchmark real de 8 temas (quick_30, `--stop-after assets`): decisión agregada **YELLOW**; capa script/VisualPlan genérica y sana; 8/38 assets resueltos `FALSE_POSITIVE_OR_UNUSABLE` en 5 dominios no relacionados; cobertura de provider limitada (SUPPLY). Evidencia y contact sheets en `openspec/changes/generic-content-pipeline-evaluation/` y `data/evaluations/genericity-phase2-visual-review/`.
- Limitación conocida del gate semántico: relevancia gruesa (tema/entidad), no fidelidad temporal/editorial/de contenido de imagen — confirmada como fallo downstream repetido por `generic-content-pipeline-evaluation`. Slice 1 COMPLETED, Slice 2 COMPLETED, Slice 3A COMPLETED; decisión **LOCAL_ENCODER_PREFERRED** (OpenCLIP ViT-B-32 P1 preferido sobre gpt-5.6-luna por mayor retención de assets buenos, sin coste/red/latencia adicionales; no hay integración runtime). No añadir heurísticas semánticas nuevas; NO implementar `asset-entity-fidelity` / `deterministic_anchor_coverage_v3`. Detección de near-duplicates visuales: trabajo futuro. Dirección separada de producto: fallback search-vs-generation.
- Baseline main antes de la rama cerrada: **`fd4d58d`** (`asset-visual-semantic-fidelity` mergeado/cerrado); baseline de la rama `change/visual-fidelity-runtime` al abrir: **`1460 passed, 0 failed, 0 skipped`** (`python3 -m pytest -q tests`; la invocación desde la raíz falla al recolectar `data/postgres/`, volumen Docker de postgres propiedad de root no readable — ambiental, no relacionado con el código). Tras Slice 1: **`1481 passed`**. Tras Slice 2: **`1492 passed`**. Tras Slice 3: **`1494 passed, 0 failed, 0 skipped`** (34 focal + suite completa; validación runtime real 25/30 + 7/8 reproducida en CUDA).
