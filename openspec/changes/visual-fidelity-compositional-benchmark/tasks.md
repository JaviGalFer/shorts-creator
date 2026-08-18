# Tasks: visual-fidelity-compositional-benchmark

**Status: COMPLETED — investigación benchmark-first, sin integración de runtime.**

## Precondiciones verificadas

- [x] `main == dce1624`, working tree limpio, baseline `1494 passed` (confirmado por contexto del cambio; validación de suite en el paso final)
- [x] Rama creada: `change/visual-fidelity-compositional-benchmark`

## Datos

### Calibration set (38 canónicos)
- [x] Reutilizar `tests/fixtures/asset_visual_fidelity/labels.json` SIN alterar sus labels (16 CR / 14 CU / 8 FP)

### Fresh holdout (20 assets de los 3 E2E frescos)
- [x] Casos disponibles en el resumen persisted de la validación runtime actual (`data/evaluations/visual-fidelity-fresh-e2e/summary.json`)
- [x] Crear fixture trackeado `tests/fixtures/asset_visual_fidelity/holdout_labels.json` con los 20 assets y labels humanas
- [x] Recuento real por labels individuales: **13 ACCEPT (3 CR + 10 CU) / 7 REJECT** (el enunciado decía 12/8 como cuenta global; el listado individual sumó 13/7 y es autoritativo — documentado en design.md y results.md)
- [x] The holdout NO se usa para seleccionar threshold (bloqueo estricto tras calibration)

## BLIP ITM (solo `Salesforce/blip-itm-base-coco`)

- [x] `transformers.BlipProcessor` + `transformers.BlipForImageTextRetrieval`, `use_itm_head=True`
- [x] Score = `softmax(itm_score)[0, 0]` (probabilidad de matching), raw `queryUsed` (P1, sin templates)
- [x] `model.eval()`, `torch.no_grad()`, batch=1, RGB, GIF frame 0, seed fijo (determinístico)
- [x] Entorno aislado fuera del repo: `/tmp/shorts-visual-fidelity-gpu-venv` (torch 2.11.0+cu128, transformers 5.15.0, Pillow 12.3.0); caché HF `/tmp/shorts-visual-fidelity-hf`
- [x] Preferir CUDA GTX 1650 SUPER: ejecutado en cuda (VRAM pico 924.6 MiB, sin OOM)
- [x] NO evaluar `large`; NO tocar requirements del proyecto
- [x] Registrado: versiones torch/transformers/Pillow, device, VRAM/RSS, model load, mediana/p95, OOM=no

### Herramienta
- [x] `tools/visual_fidelity_compositional_benchmark.py` (evaluation-only, lazy-import ML, un output por etiqueta)
- [x] Reutiliza `tools/visual_fidelity_benchmark.py` (metricas + threshold) tal cual — sin cambios en el harness existente
- [x] Tests focales: `tests/test_visual_fidelity_compositional_benchmark.py` (9 tests verdes)

## Calibration (38 antiguos)

- [x] Ejecutar BLIP sobre los 38 (scores persisted en `data/evaluations/visual-fidelity-compositional-benchmark/blip-itm-calibration-scores.json`, git-ignored)
- [x] Seleccionar threshold con la política existente del benchmark (max badRejected → max retained → estricto)
- [x] NO alterar labels ni política después de ver el holdout

### Resultado calibration BLIP (38)
- [x] Threshold seleccionado y BLOQUEADO: **0.015839167404919863**
- [x] **retained 27/30, badRejected 1/8**, goodAssetRetention 0.9, badAssetRejectionRecall 0.125, falseAcceptances 7, falseRejections 3
- [x] Confusion: TP 27 / TN 1 / FP 7 / FN 3 — NO eligible (target provisional >=6/8 y >=24/30)
- [x] Los scores BLIP son bimodales (~0.0 o ~1.0) con franja media casi vacía: el discriminador ITM no separa buenos/malos de forma utilizable

## Fresh holdout (20, threshold bloqueado)

- [x] BLIP + OpenCLIP scoreados sobre los 20 con el mismo tool/device
- [x] Métricas con threshold bloqueado BLIP 0.015839167 y OpenCLIP productivo 0.2296

### Resultado holdout (conteos reales 13/7 por labels individuales)
- [x] BLIP ITM base: **usableRetained 13/13, badRejected 0/7**, falseAcceptances 7, falseRejections 0 (confusion TP 13 / TN 0 / FP 7 / FN 0)
- [x] OpenCLIP ViT-B-32 @0.2296: **usableRetained 13/13, badRejected 0/7**, falseAcceptances 7, falseRejections 0 (idéntico)
- [x] Cuenta nominal del enunciado equivalentemente: BLIP 12/12 + 0/8; OpenCLIP 12/12 + 0/8

### Cinco casos críticos (todos FALSE_POSITIVE_OR_UNUSABLE, aceptados por ambos modelos)
- [x] motor 2T vs query 4T (motor 1.2): BLIP 0.98515 / OpenCLIP 0.26753 → ambos ACCEPT (FAIL)
- [x] castle genérico vs workers building (castillos 1.1): BLIP 0.85676 / OpenCLIP 0.25211 → FAIL
- [x] castle landscape vs architectural plans (castillos 3.1): BLIP 0.63309 / OpenCLIP 0.25656 → FAIL
- [x] castle genérico vs construction-time diagram (castillos 4.2): BLIP 0.39384 / OpenCLIP 0.30679 → FAIL
- [x] blockchain/digital art vs data-center infrastructure (data center 1.2): BLIP 0.99798 / OpenCLIP 0.24839 → FAIL

## Decisión

- [x] Clasificación BLIP: **NOT_USEFUL** — no mejora materialmente OpenCLIP (0/7 bad reject en holdout = OpenCLIP; degradation en calibration 1/8 vs 7/8; más lento y más VRAM)
- [x] NO integrar BLIP en runtime
- [x] No merge, no push; rama experimental lista para revisión/cierre

## Validación

- [x] `python3 -m pytest -q tests` — suite completa
- [x] `git diff --check` limpio
- [x] Sin cambios en `visual_fidelity.py`, `executor.py`, `bridge.py`, ni threshold OpenCLIP
- [x] Commit único de investigación/docs

## Fuera de alcance

- Integración runtime de BLIP (queda descriptor a cierre abierto)
- Evaluar `blip-itm-large` u otros checkpoints/métricas
- Nuevos providers, `search-vs-generation`, cambios de prompts/VisualPlan
- `deterministic_anchor_coverage_v3` / `asset-entity-fidelity` (research-only)