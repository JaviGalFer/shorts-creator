# Tasks: visual-fidelity-compositional-benchmark

**Status: COMPLETED / VERIFIED / CLOSED** — investigación benchmark-first, sin integración de runtime. Mergeado a `main` (no-ff).

> **CORRECCIÓN DE ORIENTACIÓN (iteración 2):** la iteración 1 puntuó
> `softmax(itm_score)[0, 0]` (clase 0 = NOT_MATCH del ITM head de BLIP). La
> implementación oficial de Salesforce BLIP usa **clase 1 = MATCH**
> (`train_retrieval.py` etiqueta pares positivos con `ones`;
> `eval_retrieval.py` puntúa con `itm_head(...)[:, 1]`). Todos los números de la
> iteración 1 quedan **INVALIDADOS**. Esta iteración usa
> `softmax(itm_score.float())[0, 1]`, con sanity check de orientación en-run y
> tests unitarios que fijan el contrato clase-1=MATCH.

## Conclusión canónica (cerrado)

- BLIP ITM correcto: **clase 1 = MATCH** (`matchProbability = softmax(itm_score.float())[0, 1]`).
- Calibration (38): **24/30 retained + 6/8 badRejected** (retention 0.80, recall 0.75, FA 2, FR 6) — ELIGIBLE.
- Threshold experimental BLIP: **0.06636959873139858** (bloqueado en calibration; el holdout NO se usó para seleccionarlo).
- Fresh holdout (20): **9/13 usable + 2/7 badRejected** (FA 5, FR 4). BLIP rechaza los 2 casos composicionales más difíciles (motor 2T, blockchain vs data-center).
- OpenCLIP fresh holdout @0.2296: **13/13 + 0/7**.
- **Decisión: TRADEOFF_ONLY** — mejora rechazo con retención insuficiente; no alcanza STRONG ni PROMISING.
- **BLIP NO se integra en runtime.** OpenCLIP sigue siendo el pixel gate vigente cuando está activado.
- `visual-fidelity-runtime` sigue OFF por defecto: solo `VISUAL_FIDELITY_THRESHOLD=0.2296` lo activa.
- La iteración antigua `[0,0]` (threshold 0.015839167404919863, 27/30 + 1/8, NOT_USEFUL) permanece explícitamente **INVALIDADA**.
- Commits: `2426016` (benchmark), `4328438` (corrección de orientación), `<close>` (cierre docs). Merge no-ff a `main`.
- Suite final: **1506 passed, 0 failed**; `git diff --check` limpio.

## Datos (NO tocados)

- [x] `main == dce1624`, working tree limpio, baseline `1494 passed`
- [x] Rama base: `change/visual-fidelity-compositional-benchmark` (HEAD `2426016`, limpio)
- [x] Rama iteración-corrección: misma rama `change/visual-fidelity-compositional-benchmark`

## Datos (NO tocados)

### Calibration set (38 canónicos)
- [x] Reutilizar `tests/fixtures/asset_visual_fidelity/labels.json` SIN alterar sus labels (16 CR / 14 CU / 8 FP)

### Fresh holdout (20 assets de los 3 E2E frescos)
- [x] `tests/fixtures/asset_visual_fidelity/holdout_labels.json` ya trackeado en la iteración 1, SIN cambios de labels
- [x] Recuento real por labels individuales: **13 ACCEPT (3 CR + 10 CU) / 7 REJECT** (autoritativo vs "12/8" global del enunciado)
- [x] The holdout NO se usa para seleccionar threshold (bloqueo estricto tras calibration)

## Blip ITM (solo `Salesforce/blip-itm-base-coco`)

- [x] `transformers.BlipProcessor` + `transformers.BlipForImageTextRetrieval`, `use_itm_head=True`
- [x] **CORREGIDO:** score = `softmax(itm_score.float(), dim=-1)[0, 1]` = **matchProbability** (clase 1 = MATCH, convención oficial Salesforce BLIP)
- [x] La clase 0 quedaría como NOT_MATCH; se persiste explícitamente como `notMatchScores` y los logits como `itmLogits` para auditar el contrato; NUNCA se usa como score
- [x] Sanity check de orientación en-run (`_check_blip_orientation`): compatible vs incompatible sobre un asset real; aborta si `compatible <= incompatible`
- [x] Tests unitarios offline: `blip_match_from_logits` + guard de que el score persistido es `match` no `not_match` + test de que `[0,0]` no indexa match
- [x] `model.eval()`, `torch.no_grad()`, batch=1, RGB, GIF frame 0, seed fijo
- [x] Entorno aislado fuera del repo: `/tmp/shorts-visual-fidelity-gpu-venv` (torch 2.11.0+cu128, transformers 5.15.0, Pillow 12.3.0); caché HF `/tmp/shorts-visual-fidelity-hf`
- [x] CUDA GTX 1650 SUPER ejecutado (VRAM pico 924.6 MiB, sin OOM)
- [x] NO evaluar `large`; NO tocar requirements del proyecto
- [x] Registrado: versiones, device, VRAM/RSS, load, mediana/p95, OOM=no

### Herramienta
- [x] `tools/visual_fidelity_compositional_benchmark.py` (evaluation-only, lazy-import ML, score corregido y persistencia de ambas probabilidades)
- [x] Reutiliza `tools/visual_fidelity_benchmark.py` (métricas + threshold) tal cual — sin cambios en el harness existente
- [x] Tests focales: `tests/test_visual_fidelity_compositional_benchmark.py` (12 tests verdes)

## Calibration (38 antiguos) — CORREGIDO

- [x] Re-score BLIP sobre los 38 con clase positiva correcta (scores en `data/evaluations/visual-fidelity-compositional-benchmark/blip-itm-calibration-scores.json`, git-ignored, SOBRESCRITO)
- [x] Seleccionar threshold con la política existente (max badRejected → max retained → estricto)
- [x] NO alterar labels ni política después de ver el holdout

### Resultado calibration BLIP (corregido)
- [x] Threshold seleccionado y BLOQUEADO: **0.06636959873139858** (matchProbability clase 1)
- [x] **retained 24/30, badRejected 6/8**, goodAssetRetention 0.80, badAssetRejectionRecall 0.75, falseAcceptances 2, falseRejections 6
- [x] Confusion: TP 24 / TN 6 / FP 2 / FN 6 — **ELIGIBLE** (cumple provisional >=6/8 y >=24/30)
- [x] Umbral previo 0.015839167404919863 (clase 0, NOT_MATCH) INVALIDADO

## Fresh holdout (20, threshold bloqueado) — CORREGIDO

- [x] BLIP re-scoreado sobre los 20 con la clase corregida (scores git-ignored, SOBRESCRITOS)
- [x] OpenCLIP sin re-scorear (scores de iteración 1 válidos; mismo tool/device, threshold productivo 0.2296)
- [x] Métricas con threshold bloqueado BLIP 0.06637 y OpenCLIP 0.2296

### Resultado holdout (conteos reales 13/7)
- [x] BLIP ITM base (corregido): **usableRetained 9/13, badRejected 2/7**, falseAcceptances 5, falseRejections 4 (confusion TP 9 / TN 2 / FP 5 / FN 4)
- [x] OpenCLIP ViT-B-32 @0.2296: **usableRetained 13/13, badRejected 0/7**, falseAcceptances 7, falseRejections 0
- [x] BLIP pierde 4 buenos que OpenCLIP conserva: castillos 1.2, data center 2.2, data center 4.2, data center 5.2
- [x] Los 7 bad assets por score BLIP reportados en results.md §7

### Cinco casos críticos (todos FALSE_POSITIVE_OR_UNUSABLE)
- [x] motor 2T vs query 4T (motor 1.2): BLIP 0.01485 **REJECT** / OpenCLIP 0.26753 ACCEPT
- [x] **castle final/no-construcción** vs `medieval castle construction photograph` (castillos 1.1): BLIP 0.14324 ACCEPT / OpenCLIP 0.25211 ACCEPT — (NO llamarlo "workers building"; ese es castillos 1.2, que conserva su label humana COARSE_BUT_USABLE sin cambios)
- [x] castle vs architectural plans (castillos 3.1): BLIP 0.36691 ACCEPT / OpenCLIP 0.25656 ACCEPT
- [x] castle vs construction-time diagram (castillos 4.2): BLIP 0.60616 ACCEPT / OpenCLIP 0.30679 ACCEPT
- [x] blockchain/digital art vs data-center infra (data center 1.2): BLIP 0.00202 **REJECT** / OpenCLIP 0.24839 ACCEPT
- [x] Total **2/5** casos críticos rechazados por BLIP (motor 2T, blockchain vs data-center)

## Decisión (criterios registrados, corregida)

- [x] **Clasificación BLIP: TRADEOFF_ONLY** — mejora rechazo (2/7 vs 0/7 holdout; calibración 6/8 + 24/30) pero con retención insuficiente (9/13 vs 13/13); no alcanza STRONG ni PROMISING
- [x] NO integrar BLIP en runtime
- [x] OPENCLIP sigue como pixel gate vigente y `visual-fidelity-runtime` sigue OFF por defecto salvo `VISUAL_FIDELITY_THRESHOLD`

## Validación

- [x] `python3 -m pytest tests/test_visual_fidelity_compositional_benchmark.py -q` — 12 tests verdes
- [x] `python3 -m pytest -q tests` — suite completa **1506 passed, 0 failed**
- [x] `git diff --check` limpio
- [x] Sin cambios en `visual_fidelity.py`, `executor.py`, `bridge.py`, ni threshold OpenCLIP

## Cierre y merge

- [x] Docs marcadas **COMPLETED / VERIFIED / CLOSED** (tasks, agent-context, current-state)
- [x] Commit de cierre documental
- [x] Merge no-ff a `main`; suite en main `1506 passed, 0 failed`
- [x] NO push, NO borrar rama, NO reindexar

## Fuera de alcance

- Integración runtime de BLIP (descartada; BLIP NO se integra)
- Evaluar `blip-itm-large` u otros checkpoints/métricas
- Nuevos providers, `search-vs-generation`, cambios de prompts/VisualPlan
- `deterministic_anchor_coverage_v3` / `asset-entity-fidelity` (research-only)