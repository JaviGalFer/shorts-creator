# Tasks: asset-visual-semantic-fidelity

**Status: IN PROGRESS — Slice 1 (harness benchmark-first) activo.**

## Contexto registrado (del change CLOSED)

- `generic-content-pipeline-evaluation`: CLOSED / decisión agregada **YELLOW**.
- 38 assets resueltos revisados por píxeles: **16 CLEARLY_RELEVANT / 14 COARSE_BUT_USABLE / 8 FALSE_POSITIVE_OR_UNUSABLE**.
- El gate de metadata (semántico, `deterministic_anchor_coverage_v2`) permanece como PRIMERA ETAPA barata; la segunda etapa por píxeles es la investigación activa.
- `asset-entity-fidelity`: EVIDENCIA DE INVESTIGACIÓN SOLO (pausado). NO implementar `deterministic_anchor_coverage_v3` / `FORM_OR_MEDIUM_TERMS`.
- `search-vs-generation`: asunto de producto separado y futuro (fuera de este change).

## Slice 1 — Harness de evaluación (ACTIVO)

### Precondiciones verificadas
- [x] `main == 296d553`, working tree limpio
- [x] Rama creada: `change/asset-visual-semantic-fidelity`

### Dataset canónico (rastreado por Git)
- [x] Materializar `tests/fixtures/asset_visual_fidelity/labels.json` con las 38 labels externas de `openspec/changes/generic-content-pipeline-evaluation/phase2-report.md`
- [x] Validar exactamente: 38 entradas, 16 CR / 14 CU / 8 FP, sin duplicados `(jobId, sceneNumber, segmentIndex)`, sin `queryUsed` vacío
- [x] Interpretación binaria: ACCEPT = CLEARLY_RELEVANT + COARSE_BUT_USABLE; REJECT = FALSE_POSITIVE_OR_UNUSABLE
- [x] NO requerir que los archivos de imagen locales existan en los tests

### Herramienta de benchmark
- [x] Implementar `tools/visual_fidelity_benchmark.py` (stdlib-only, offline, sin red, sin ML)
- [x] Métricas: acceptableRetained / 30, badRejected / 8, goodAssetRetention, badAssetRejectionRecall, falseAcceptances, falseRejections, confusionMatrix, eligibility provisional
- [x] Reportar todos los conteos subyacentes (no ocultar el dataset de 8 negativos tras porcentajes)
- [x] Sweep de umbrales determinista (midpoints + límites -inf/+inf)
- [x] Selección de umbral determinista: maximizar badRejected sujeto a goodAssetRetention >= 0.80, tie-break hacia el umbral más estricto
- [x] NO definir umbral de producción; el target de elegibilidad (>=6/8 y >=24/30) es provisional y documentado como tal

### Tests focales
- [x] `tests/test_visual_fidelity_benchmark.py`:
  - schema/counts de labels (incluye rechazo de campos faltantes, label inválida, queryUsed vacío, clave duplicada)
  - totales canónicos exactos 16/14/8
  - mapeo ACCEPT/REJECT
  - confusion matrix (perfecto, accept-all, reject-all)
  - sweep de umbrales (límites, retención no creciente)
  - elegibilidad pass/fail (met, degenerate accept-all, sin umbral viable con min > 1.0)
  - tie-break determinista (estricto) y determinismo
  - no mutación de inputs
  - sin dependencia de `data/videos`
  - sin imports de red/ML en el harness
- [x] Tests focales verdes: `python3 -m pytest tests/test_visual_fidelity_benchmark.py -q`

### OpenSpec y docs
- [x] Materializar `openspec/changes/asset-visual-semantic-fidelity/{proposal,design,tasks}.md`
- [x] Actualizar `docs/project/agent-context.md` (main base 296d553; evaluation CLOSED; asset-entity-fidelity research-only; asset-visual-semantic-fidelity = investigación activa de benchmark)
- [x] Actualizar `docs/project/current-state.md` (mismo estado vigente)

### Verificación y cierre de Slice 1
- [x] `git diff --check` limpio
- [x] Sin cambios en `src/` ni `bin/` (sin cambios de runtime de producción)
- [x] Commit único: `test(evaluation): add visual fidelity benchmark harness`
- [ ] Sin merge, sin push

## Slice 2 (futuro, NO en este change) — codificadores locales
- Candidatos SOLO: CLIP `ViT-B/32` y SigLIP `base-patch16-224`
- Instalar deps ML y descargar pesos (fuera de Slice 1)
- Benchmark CPU-first sobre los 38 assets; GPU opcional
- Medir (no asumir) latencia/RAM/VRAM en 4 GB
- Decidir elegibilidad del experimento (provisional) y siguiente paso

## Slice 3 (futuro, NO en este change) — API multimodal
- Benchmark de API multimodal (OpenAI actual) con contrato estructurado ACCEPT/REJECT
- Registrar precios de API por separado del uso real; coste medido, no estimado del plan
- Comparar alternativas arquitectónicas B/C/D/E y decidir

## Fuera de alcance (todos los slices)
- Cambios de runtime en `src/` o `bin/`
- Script prompts, VisualPlan, `deterministic_anchor_coverage_v2`
- `deterministic_anchor_coverage_v3` / `FORM_OR_MEDIUM_TERMS` / `asset-entity-fidelity`
- Providers nuevos, generación de imagen
- `search-vs-generation` (dirección de producto separada)
