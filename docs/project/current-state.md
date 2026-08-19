# Estado actual del proyecto

**Última actualización:** 2026-08-19

## Investigación activa: `pexels-provider-fit-benchmark` — IN_PROGRESS / READY_FOR_HUMAN_REVIEW (rama `change/pexels-provider-fit-benchmark`, NO mergeada)

- Benchmark-first del **PROVIDER FIT** de Pexels Photos/Video y de la
  adaptación determinista de query para Pexels Video. **Research-only; sin
  integración runtime.** NO tocar rendering/OpenCLIP/BLIP/VLM/VisualPlan; NO
  generación de imágenes; NO perceptual hash. Base `main` == `cf391c5`.
- Datasets reutilizados sin relabel (58 rows → 56 queryUsed); **evidencia RAW
  reutilizada** de los benchmarks previos. **Solo requests nuevas: 39/40**
  Pexels Video adaptadas (`orientation=portrait`, `locale=en-US`,
  `per_page=15`; rate-limit final `remaining=24849/25000`).
- Contrato persistido resuelto por `(jobId, sceneNumber, segmentIndex)` desde
  `data/videos/<jobId>/metadata.json`: 58/58, `missingRows=0`, 4 rows con
  `searchQueryMismatch`. Distribuciones: assetPreference {photograph 39,
  diagram 14, illustration 5}; visualIntent {explain 27, show 10,
  contextualize 9, emphasize 9, compare 2, immerse 1}.
- Política provisional `provider-fit-policy-v1`: exactform →
  `INELIGIBLE_EXACT_FORM` (16 rows); photograph → Photos `ELIGIBLE` / Video
  `ELIGIBLE_CANDIDATE` (42); resto `UNDECIDED` (0). Adaptación `query-adapt-v1`
  (elimina solo photograph/photo/photography): 39 adaptaciones únicas, sin
  colisiones, ninguna igual a una queryUsed RAW.
- RAW vs ADAPTED (39): total_results 29/39 disminuye (mediana 6439→6026), pero
  supply portrait intacto (39/39 en 720 y 1080). Overlap exact-ID top15 base
  justa: RAW 456 unique/92 repet./56 pares (J med .124) vs ADAPTED 461/88/50
  (J med .138) — diversifica ligeramente; duplicados within-job/topic persisten
  (Photos el peor: 278).
- Review sample determinista 10 queries (5 mandatory + 5 por round-robin de
  topics; 6 topics); 20 clips (10 RAW con reutilización + 10 ADAPTED, 0 fallos).
- Evidencia visual: `data/evaluations/pexels-provider-fit-benchmark/`
  (`01-provider-fit-photo-current-top3.png`, `02-provider-fit-video-raw-vs-
  adapted-top3.png`, `03-provider-fit-video-temporal.png`).
- **Estado: `READY_FOR_HUMAN_REVIEW`** — pendiente la revisión humana externa
  (Photos CURRENT/PEXELS/TIE; Video RAW/ADAPTED/TIE/BOTH_UNUSABLE). NO se
  afirma `PROVIDER_FIT_VALIDATED`/`ADAPTED_BETTER`/Pexels default.
- Suite en rama: **`1625 passed, 0 failed`** (1586 previos + 39 nuevos). Comun
  `test(evaluation): benchmark Pexels provider fit` (sin merge/push/reindex).
  Marcador `PEXELS_PROVIDER_FIT_BENCHMARK_READY_FOR_HUMAN_REVIEW`.

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
