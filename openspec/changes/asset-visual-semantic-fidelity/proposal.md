# Propuesta: asset-visual-semantic-fidelity

## Contexto

`generic-content-pipeline-evaluation` está **COMPLETADO / VERIFICADO / CLOSED** (decisión agregada **YELLOW**). Su evidencia final:

- 38 assets resueltos revisados por píxeles (revisión visual externa).
- **16 `CLEARLY_RELEVANT` / 14 `COARSE_BUT_USABLE` / 8 `FALSE_POSITIVE_OR_UNUSABLE`**.
- La capa script/VisualPlan (LLM) es sana y topic-agnostic en los 8 dominios; el gate de metadata semántico (`deterministic_anchor_coverage_v2`) es un filtro previo barato y útil pero NO puede probar que los píxeles representen la intención visual pedida.
- Los fallos cubren entidades, conceptos, ACCIONES y semántica de escena → `asset-entity-fidelity` permanece como **EVIDENCIA DE INVESTIGACIÓN SOLO** (pausado). NO se implementará `deterministic_anchor_coverage_v3` / `FORM_OR_MEDIUM_TERMS`.
- La dirección de producto "fallback search-vs-generation" sigue siendo un **asunto futuro separado** y NO se toca en este change.

## Objetivo

Investigar, **benchmark-first**, una validación semántico-visual de SEGUNDA ETAPA basada en los PÍXELES de la imagen, provider-agnostic y topic-agnostic, que conserve el gate de metadata actual como primera etapa barata:

```
provider candidate
→ metadata semantic gate (actual, sin cambios)
→ [SEGUNDA ETAPA PIXEL — investigada en este change]
→ accept / reject / next candidate
```

El segundo stage debe permanecer:
- topic-agnostic y provider-agnostic
- opcional/pluggable
- acotado en coste y complejidad

## Invariante de producto

- NO se cambia el runtime de producción (`src/`, `bin/`).
- NO se cambia script prompts, VisualPlan, `deterministic_anchor_coverage_v2`, router, executor, providers.
- NO se reviven `deterministic_anchor_coverage_v3` / `FORM_OR_MEDIUM_TERMS`.
- NO se implementa `asset-entity-fidelity`.
- NO se añaden providers ni generación de imagen.
- NO se combina con search-vs-generation (problema separado).

## Fase activa: Slice 1 (este change) — harness de evaluación benchmark-first

Slice 1 materializa SOLO el harness de evaluación: dataset de 38 labels canónicas rastreado por Git + herramienta offline de métricas + tests focales. **Sin modelos, sin APIs, sin instalación de dependencias ML, sin cambios de runtime.**

- Dataset: `tests/fixtures/asset_visual_fidelity/labels.json` (38 entradas, labels externas de `phase2-report.md`, interpretación binaria ACCEPT = CR+CU / REJECT = FP).
- Harness: `tools/visual_fidelity_benchmark.py` (stdlib-only, offline, sin red, sin ML). Dado labels + scores/verdicts externos, calcula métricas, confusion matrix, sweep de umbrales y selección de umbral determinista.
- Tests focales: `tests/test_visual_fidelity_benchmark.py`.

### Candidatos iniciales para Slice 2 (SOLO estos, sin instalar/descargar en Slice 1)

- CLIP `ViT-B/32`
- SigLIP `base-patch16-224`

### Costes y hardware

- Todas las estimaciones previas de RAM/VRAM/latencia son **provisionales**; no se persistirán como hechos medidos. Los precios de API se registran aparte del uso real; los costes por-imagen del plan NO se persisten como medidos.
- El target de elegibilidad del experimento es **provisional**: bad rejection >= 6/8 y good retention >= 24/30. NO es un umbral de producción.

## Criterios de éxito (Slice 1)

1. Dataset canónico validado: exactamente 38 entradas, 16 CR / 14 CU / 8 FP, sin duplicados `(jobId, sceneNumber, segmentIndex)`, sin `queryUsed` vacío.
2. Harness stdlib-only/offline que calcula: acceptable retained / 30, bad rejected / 8, `goodAssetRetention`, `badAssetRejectionRecall`, `falseAcceptances`, `falseRejections`, confusion matrix; sweep de umbrales y selección determinista (maximizar bad rejection sujeto a good retention >= 0.80, tie-break hacia el umbral más estricto).
3. Tests focales verdes (schema/counts, mapeo ACCEPT/REJECT, confusion matrix, sweep, elegibilidad, tie-break, no-mutación, sin dependencia de `data/videos`, sin imports de red/ML).
4. `git diff --check` limpio.
5. Sin diff en `src/` ni `bin/`.

## Fuera de alcance (Slice 1)

- Instalación de torch/transformers/open_clip; descarga de pesos de modelos.
- Benchmarks de CPU/GPU reales; llamadas a OpenAI o cualquier API de pago.
- Cambios en `src/shorts_creator/` o `bin/`.
- Ejecución de la suite completa.
