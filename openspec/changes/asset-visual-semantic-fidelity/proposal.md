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

## Slice 1 (COMPLETADO) — harness de evaluación benchmark-first

Slice 1 materializó SOLO el harness de evaluación: dataset de 38 labels canónicas rastreado por Git + herramienta offline de métricas + tests focales. **Sin modelos, sin APIs, sin instalación de dependencias ML, sin cambios de runtime.**

- Dataset: `tests/fixtures/asset_visual_fidelity/labels.json` (38 entradas, labels externas de `phase2-report.md`, interpretación binaria ACCEPT = CR+CU / REJECT = FP).
- Harness: `tools/visual_fidelity_benchmark.py` (stdlib-only, offline, sin red, sin ML). Dado labels + scores/verdicts externos, calcula métricas, confusion matrix, sweep de umbrales y selección de umbral determinista (max badRejected → max acceptableRetained entre empates → estricto solo si ambos empatan). Valida scores numéricos finitos (no bool/NaN/inf).
- Tests focales: `tests/test_visual_fidelity_benchmark.py` (31 tests verdes).
- Commit: `5f2ea96` `test(evaluation): add visual fidelity benchmark harness`.

## Slice 2 (COMPLETADO) — benchmark de codificadores locales, CPU-first

Benchmark SOLO de los dos candidatos acordados:

- A. OpenCLIP `ViT-B-32` / pretrained `laion2b_s34b_b79k`
- B. SigLIP 2 `google/siglip2-base-patch16-224`

NO se benchmarquean ViT-L, SO400M, VLMs generativos, más checkpoints ni APIs. El objetivo es determinar si los image-text encoders ligeros son útiles, no explorar un zoo de modelos.

- Entorno temporal aislado fuera del repo (`/tmp/shorts-visual-fidelity-venv` CPU + `/tmp/shorts-visual-fidelity-gpu-venv` GPU); NO se modificaron `pyproject.toml`, requirements, virtualenv del proyecto, `src/`, `bin/`.
- Herramienta evaluation-only `tools/visual_fidelity_local_benchmark.py` (lazy-import ML; lee las 38 imágenes; batch=1; deterministic; GIF = frame 0; escribe scores por `assetPath` bajo `data/evaluations/asset-visual-semantic-fidelity/`, git-ignored).
- Políticas de texto exactas: P1 = `queryUsed`; P2 = `"an image depicting: {queryUsed}"`. Una fila por modelo+política (4 filas), sin max de templates.
- Medido en CPU (no asumido): load time, total scoring time, mediana/p95 latencia, pico RSS. Las estimaciones previas del Plan quedan como provisionales y NO se persistieron como medidas.
- Decisión GPU: el mejor candidato (OpenCLIP ViT-B-32 P1, por regla 1.badRejected→2.retained→3.latencia CPU) cumplió elegibilidad → benchmark GPU ejecutado: GTX 1650 SUPER 4 GB, batch=1, sin OOM, 38/38, mediana 9.8 ms/p95 11.3 ms, max_memory_allocated 690.6 MiB (cabe en 4 GB), scores GPU==CPU (<1e-6).
- Contrato de decisión: OpenCLIP P1/P2 ELIGIBLE (7/8 y 25/30; 6/8 y 26/30), SigLIP2 P1 NEAR_MISS (5/8 y 26/30), SigLIP2 P2 NOT_USEFUL (4/8 y 24/30). Held-out (leave-one-topic-out) del mejor candidato: 7/8 bad y 24/30 retained (no colapsa). NO se integró nada en runtime.
- **Decisión de Slice 2: A. LOCAL_ENCODER_PROMISING.** Slice 3 (API multimodal) sigue útil para comparar, especialmente los fallos de acción/escena y entidad/temporal (el caso no rechazado por ningún candidato fue la ilustración del modelo Porsche moderno). NO se cierra el change global en Slice 2.
- Evidencia completa y métricas: `design.md` y `tasks.md`.

## Candidatos iniciales futuros y costes

- Slice 3 (futuro): benchmark de API multimodal (OpenAI actual) con contrato estructurado ACCEPT/REJECT y coste medido.

### Costes y hardware

- Todas las estimaciones previas de RAM/VRAM/latencia son **provisionales**; no se persistirán como hechos medidos. Los precios de API se registran aparte del uso real; los costes por-imagen del plan NO se persisten como medidos.
- El target de elegibilidad del experimento es **provisional**: bad rejection >= 6/8 y good retention >= 24/30. NO es un umbral de producción.

## Criterios de éxito (Slice 1)

1. Dataset canónico validado: exactamente 38 entradas, 16 CR / 14 CU / 8 FP, sin duplicados `(jobId, sceneNumber, segmentIndex)`, sin `queryUsed` vacío.
2. Harness stdlib-only/offline que calcula: acceptable retained / 30, bad rejected / 8, `goodAssetRetention`, `badAssetRejectionRecall`, `falseAcceptances`, `falseRejections`, confusion matrix; sweep de umbrales y selección determinista (max badRejected sujeto a good retention >= 0.80; entre empates max acceptableRetained; solo si ambos empatan, umbral más estricto).
3. Tests focales verdes (schema/counts, mapeo ACCEPT/REJECT, confusion matrix, sweep, elegibilidad, tie-break, no-mutación, sin dependencia de `data/videos`, sin imports de red/ML, validación de scores).
4. `git diff --check` limpio.
5. Sin diff en `src/` ni `bin/`.

**Criterios de éxito (Slice 1):** COMPLETADO en `5f2ea96` (31 tests verdes).

## Fuera de alcance (Slice 1 y Slice 2)

- Instalación de ML en el entorno del proyecto; descarga de pesos al repo; benchmarks GPU automáticos (solo tras decisión CPU); llamadas a OpenAI o cualquier API de pago.
- Cambios en `src/shorts_creator/` o `bin/`.
- Ejecución de la suite completa; merge/push.
- Cierre del change global en Slice 2.
