# Tasks: asset-visual-semantic-fidelity

**Status: IN PROGRESS — Slice 3A COMPLETED. Slice 1 y Slice 2 COMPLETED.**

## Contexto registrado (del change CLOSED)

- `generic-content-pipeline-evaluation`: CLOSED / decisión agregada **YELLOW**.
- 38 assets resueltos revisados por píxeles: **16 CLEARLY_RELEVANT / 14 COARSE_BUT_USABLE / 8 FALSE_POSITIVE_OR_UNUSABLE**.
- El gate de metadata (semántico, `deterministic_anchor_coverage_v2`) permanece como PRIMERA ETAPA barata; la segunda etapa por píxeles es la investigación activa.
- `asset-entity-fidelity`: EVIDENCIA DE INVESTIGACIÓN SOLO (pausado). NO implementar `deterministic_anchor_coverage_v3` / `FORM_OR_MEDIUM_TERMS`.
- `search-vs-generation`: asunto de producto separado y futuro (fuera de este change).

## Slice 1 — Harness de evaluación (COMPLETADO)

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
- [x] Selección de umbral determinista: maximizar badRejected sujeto a goodAssetRetention >= 0.80, entre empates maximizar acceptableRetained, y solo si ambos empatan elegir el umbral más estricto
- [x] Validación de scores de modo numérico: numérico, finito (no bool/NaN/+inf/-inf); los límites -inf/+inf siguen siendo mecánica interna de los umbrales de sweep
- [x] NO definir umbral de producción; el target de elegibilidad (>=6/8 y >=24/30) es provisional y documentado como tal

### Tests focales
- [x] `tests/test_visual_fidelity_benchmark.py` (31 tests verdes):
  - schema/counts de labels (incluye rechazo de campos faltantes, label inválida, queryUsed vacío, clave duplicada)
  - totales canónicos exactos 16/14/8
  - mapeo ACCEPT/REJECT
  - confusion matrix (perfecto, accept-all, reject-all)
  - sweep de umbrales (límites, retención no creciente)
  - elegibilidad pass/fail (met, degenerate accept-all, sin umbral viable con min > 1.0)
  - regla de selección refinada (badRejected → acceptableRetained → estricto), probada con la API pública y `_select_best_point`
  - validación de scores (bool, NaN, +inf, no-numérico) y límites de sweep -inf/+inf permitidos
  - no mutación de inputs
  - sin dependencia de `data/videos` (prueba real con assetPaths inexistentes)
  - sin imports de red/ML en el harness
- [x] Tests focales verdes: `python3 -m pytest tests/test_visual_fidelity_benchmark.py -q`

### OpenSpec y docs
- [x] Materializar `openspec/changes/asset-visual-semantic-fidelity/{proposal,design,tasks}.md`
- [x] Actualizar `docs/project/agent-context.md` (main base 296d553; evaluation CLOSED; asset-entity-fidelity research-only; asset-visual-semantic-fidelity = investigación activa de benchmark)
- [x] Actualizar `docs/project/current-state.md` (mismo estado vigente)

### Verificación y cierre de Slice 1
- [x] `git diff --check` limpio
- [x] Sin cambios en `src/` ni `bin/` (sin cambios de runtime de producción)
- [x] Commit único: `test(evaluation): add visual fidelity benchmark harness` (`5f2ea96`)
- [x] Sin merge, sin push

## Slice 2 — Benchmark de codificadores locales (COMPLETADO)

### Candidatos (SOLO estos dos)
- [x] A. OpenCLIP `ViT-B-32` / pretrained `laion2b_s34b_b79k`
- [x] B. SigLIP 2 `google/siglip2-base-patch16-224`
- [x] NO ViT-L, NO SO400M, NO VLMs generativos, NO más checkpoints, NO API

### Aislamiento de dependencias
- [x] Entorno temporal aislado fuera del repo `/tmp/shorts-visual-fidelity-venv` (CPU) + `/tmp/shorts-visual-fidelity-gpu-venv` (GPU), con caché HF en `/tmp/shorts-visual-fidelity-hf`
- [x] Descargas de modelos/caché fuera del repo; no se commitean pesos ni cachés
- [x] NO modificado `pyproject.toml`, requirements, virtualenv del proyecto, `src/`, `bin/`

### Herramienta de benchmark local
- [x] `tools/visual_fidelity_local_benchmark.py` (evaluation-only; lazy-import ML stack; lee las 38 imágenes; batch=1; deterministic; no muta archivos; escribe scores por assetPath; GIF = frame 0)
- [x] Políticas de texto exactas: P1 = `queryUsed`; P2 = `"an image depicting: {queryUsed}"` (una fila por modelo+política, sin max de templates)

### Ejecución CPU (MEDIDO, no asumido)
- [x] 4 filas: OpenCLIP ViT-B-32 P1/P2, SigLIP2 base P1/P2
- [x] Scores crudos persistidos en `data/evaluations/asset-visual-semantic-fidelity/` (git-ignored)
- [x] Métricas + umbral calibrado por fila (ver "Evidencia medida" abajo)
- [x] Lista de los 8 bad assets y su rechazo; lista de good assets falsamente rechazados
- [x] Per-topic + leave-one-topic-out sanity
- [x] Performance CPU: load time, total scoring time, mediana/p95 latencia, pico RSS

### Decisión GPU (EJECUTADA para el mejor candidato)
- [x] OpenCLIP ViT-B-32 P1 cumplió elegibilidad provisional → benchmark GPU opcional (candidato elegido por regla 1.badRejected → 2.retained → 3.latencia CPU)
- [x] GPU: GTX 1650 SUPER 4 GB, batch=1, sin OOM, sin forzar batch/quantización; scores GPU == CPU (<1e-6); mediana 9.8 ms / p95 11.3 ms; max_memory_allocated 690.6 MiB; max_memory_reserved 775.9 MiB

### Contrato de decisión
- [x] Clasificación por modelo/política (ver "Evidencia medida"): OpenCLIP P1/P2 ELIGIBLE; SigLIP2 P1 NEAR_MISS; SigLIP2 P2 NOT_USEFUL
- [x] Calibración comparada con leave-one-topic-out (held-out no colapsa en el mejor candidato)
- [x] NO integrado nada en runtime

### Decisión de Slice 2
- [x] **A. LOCAL_ENCODER_PROMISING** — OpenCLIP ViT-B-32 P1 cumple el target provisional (7/8 bad, 25/30 retained) y su held-out no colapsa (7/8 bad, 24/30 retained)
- [x] NO se cierra el change global en Slice 2; Slice 3 (API multimodal) sigue útil para comparar fallos de acción/escena

### Evidencia medida (Slice 2)

Entorno CPU: `python3.10`, 16 cores, WSL2 Linux; packages: torch 2.13.0+cpu, torchvision 0.28.0+cpu, open_clip_torch 3.3.0, transformers 5.15.0, timm 1.0.28, Pillow 12.3.0. GPU env: torch 2.11.0+cu128. Estas deps son del benchmark aislado; NO son dependencias del proyecto.

| Modelo / política | Umbral | retained/30 | badRej/8 | retención | recall | falseAcc | falseRej | eligibilidad | LOTO bad/ret |
|---|---|---|---|---|---|---|---|---|---|
| OpenCLIP ViT-B-32 / P1 | 0.2296 | 25 | 7 | 0.833 | 0.875 | 1 | 5 | **ELIGIBLE** | 7 / 24 |
| OpenCLIP ViT-B-32 / P2 | 0.2338 | 26 | 6 | 0.867 | 0.75 | 2 | 4 | **ELIGIBLE** | 5 / 26 |
| SigLIP2 base / P1 | 0.00093 | 26 | 5 | 0.867 | 0.625 | 3 | 4 | NEAR_MISS | 5 / 24 |
| SigLIP2 base / P2 | 0.00101 | 24 | 4 | 0.8 | 0.5 | 4 | 6 | NOT_USEFUL | 5 / 23 |

Performance CPU (medido):
- OpenCLIP ViT-B-32: load ~2.9–4.7 s; total 38 assets ~3.3–3.7 s; mediana ~39 ms / p95 ~43 ms por candidato; pico RSS ~1512 MiB
- SigLIP2 base: load ~5.8–6.0 s; total ~6.8 s; mediana ~148 ms / p95 ~158 ms; pico RSS ~1695 MiB

Performance GPU (OpenCLIP ViT-B-32 P1, GTX 1650 SUPER 4 GB): load 4.38 s; mediana 9.76 ms / p95 11.3 ms; max_memory_allocated 690.6 MiB; max_memory_reserved 775.9 MiB; sin OOM; 38/38; scores GPU==CPU (max diff < 1e-6).

8 bad assets vs OpenCLIP P1: rechazados 7/8 (antena aurora, GIF frame 0, pista de tenis, workflow Spring Boot, cabaña pescador, retrato romano, pulpo colgado). NO rechazado: ilustración de modelo Porsche moderno (s2.2) — fidelidad entidad/temporal, caso más difícil. Good assets falsamente rechazados (5): aurora night-sky PNG, diagrama Earth-solar, volcán paisaje, VR headset, gráfico amortización.

## Slice 3A — Benchmark multimodal OpenAI (COMPLETADO)

### Configuración y guardia de coste
- [x] Solo `gpt-5.6-luna`, Responses API oficial, una request independiente por asset
- [x] `detail="high"`, `reasoning.effort="none"`, `max_output_tokens=128`, sin tools/web/estado compartido
- [x] Structured Output estricto: `verdict` (`ACCEPT`/`REJECT`) + `reasonCode` enum, sin confidence ni explicación libre
- [x] GIF animado convertido en memoria a PNG frame 0; fichero original no mutado
- [x] Preflight obligatorio con `responses.input_tokens.count` usando el payload real; 68,117 input tokens exactos
- [x] Pricing de referencia (2026-08-18, no medido): input $0.20/M, cached input $0.02/M, output $1.20/M
- [x] Guardia `MAX_TOTAL_COST_USD=0.25`; máximo proyectado $0.0194602 → autorizado; no se ejecuta si supera el cap
- [x] Entorno SDK aislado `/tmp/shorts-visual-fidelity-api-venv`: `openai 3.2.0`, `Pillow 12.3.0`; sin cambios de deps del proyecto

### Herramienta y tests
- [x] `tools/visual_fidelity_api_benchmark.py`: modos explícitos `--preflight` / `--execute`, payload determinista, no persiste secrets/base64/headers, errores por asset explícitos
- [x] `tests/test_visual_fidelity_api_benchmark.py`: preflight sin inferencia, cap, costes, structured output, no leakage de humanLabel/provider, API key no persistida, GIF frame 0, malformed/partial failure, no runtime imports
- [x] Tests focales: `42 passed`

### Evidencia real
- [x] 38/38 requests completadas, status `completed`, cached input 0, reasoning tokens 0
- [x] Input real: 68,117 tokens; output real: 1,011 tokens; coste real total **$0.0148366**, promedio **$0.0003904368/asset**
- [x] Métricas harness: **17/30 retained**, **8/8 badRejected**, retention **0.5667**, recall **1.0**, falseAcceptances **0**, falseRejections **13**
- [x] Confusion matrix: TP 17 / TN 8 / FP 0 / FN 13
- [x] Latencia: median **1.414 s**, p95 **3.663 s**, wall-clock acumulado por request **65.644 s**
- [x] Porsche moderno (`Porsche 911 original model illustration`): **REJECT / WRONG_VARIANT_OR_ERA**; el único bad no rechazado por los encoders locales queda corregido por la API
- [x] Per-topic: Aurora 2/4 retained + 2/2 bad; Porsche 4/6 + 2/2; Spring Boot 2/2 + 1/1; Roma 2/2 + 2/2; Pulpos 1/4 + 1/1; Volcán 4/6 + 0/0; Videojuegos 0/2 + 0/0; Hipoteca 2/4 + 0/0

### Decisión Slice 3A
- [x] Comparación OpenCLIP P1: local 25/30 retained + 7/8 badRejected vs API 17/30 + 8/8
- [x] **LOCAL_ENCODER_PREFERRED** — la API elimina un false acceptance y añade un rechazo difícil, pero pierde 8 assets buenos adicionales; el coste/red/complejidad no justifican la mejora materialmente limitada
- [x] NO integrar API ni OpenCLIP en runtime; Slice 3B separado solo si se desea investigar escalado selectivo/contratos menos conservadores

## Fuera de alcance (todos los slices)
- Cambios de runtime en `src/` o `bin/`
- Script prompts, VisualPlan, `deterministic_anchor_coverage_v2`
- `deterministic_anchor_coverage_v3` / `FORM_OR_MEDIUM_TERMS` / `asset-entity-fidelity`
- Providers nuevos, generación de imagen
- `search-vs-generation` (dirección de producto separada)
