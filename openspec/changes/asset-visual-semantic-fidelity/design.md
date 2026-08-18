# Diseño: asset-visual-semantic-fidelity

## Arquitectura del harness (Slice 1)

```
tests/fixtures/asset_visual_fidelity/labels.json   (canónico, rastreado por Git)
  └─ 38 entradas: topic, jobId, sceneNumber, segmentIndex, assetPath,
     queryUsed, provider, humanLabel

tools/visual_fidelity_benchmark.py   (nuevo, stdlib-only / offline)
  ├─ importable: validate_labels, load_labels, human_label_to_verdict,
  │   evaluate_verdicts, evaluate_scores, threshold_sweep, select_threshold
  ├─ CLI: python3 tools/visual_fidelity_benchmark.py labels.json
  │        [--scores scores.json] [--threshold T]
  │        [--select-threshold] [--sweep]
  └─ NO red / NO torch / NO open_clip / NO transformers / NO descargas
```

Slice 1 NO ejecuta modelos: los llamadores suministran externamente verdicts
(`ACCEPT`/`REJECT`) o scores numéricos y el harness calcula las métricas.

## Contrato del dataset (labels)

- **Interpretación binaria:** `ACCEPT` = `CLEARLY_RELEVANT` + `COARSE_BUT_USABLE`; `REJECT` = `FALSE_POSITIVE_OR_UNUSABLE`.
- **Campos requeridos por entrada:** `topic`, `jobId`, `sceneNumber`, `segmentIndex`, `assetPath` (relativa, bajo `data/videos/...`), `queryUsed`, `provider`, `humanLabel`.
- **Validación exacta:** 38 entradas; 16 CR / 14 CU / 8 FP; clave única `(jobId, sceneNumber, segmentIndex)`; `queryUsed` no vacío; `humanLabel` en el set permitido.
- **Los archivos de imagen NO se requieren en los tests** (se evalúa solo labels + scores/verdicts). El dataset permanece en Git; las imágenes quedan en `data/videos/` (git-ignored).

## Contrato de métricas

Dado un conjunto de verdicts/scores por `assetPath`:

- `acceptableRetained` / `badRejected` (conteos crudos, siempre reportados para no ocultar el dataset de 8 negativos tras porcentajes).
- `goodAssetRetention` = acceptableRetained / goodAssets (None si 0).
- `badAssetRejectionRecall` = badRejected / badAssets (None si 0).
- `falseAcceptances` (bad aceptados) / `falseRejections` (good rechazados).
- `confusionMatrix`: truePositive (good aceptado), trueNegative (bad rechazado), falsePositive (bad aceptado), falseNegative (good rechazado).
- `eligibility` (provisional): target badRejected >= 6 y goodRetained >= 24; `eligible` = ambos.

Los conteos subyacentes se exponen siempre. El target de elegibilidad es provisional y NO es un umbral de producción.

## Sweep y selección de umbral (modo score numérico)

- **Interpretación:** score más alto = más similar/relevante; ACCEPT si `score >= threshold`.
- **Candidatos de sweep (deterministas):** puntos medios entre scores únicos consecutivos + límites `-inf` (accept-all) y `+inf` (reject-all).
- **Selección (`select_threshold`):** considerar solo umbrales con `goodAssetRetention >= 0.80`; maximizar `badRejected` (conteo crudo); **tie-break hacia el umbral más estricto** (mayor threshold → menos ACCEPTs). Determinista y documentado.
- NO se define un umbral de producción; el umbral seleccionado es un resultado de calibración del benchmark y no generaliza más allá de este dataset.

## Propiedad de módulos / sin acoplamiento

- El harness vive en `tools/`, separado del runtime. No se importa desde `src/`.
- No se tocan `script/`, `assets/`, `contracts/`, `providers/`, `bin/`.
- Slice 1 no añade dependencias de proyecto (ni torch ni API clients).

## Slice 1 (este change) — archivos

- `tests/fixtures/asset_visual_fidelity/labels.json`
- `tools/visual_fidelity_benchmark.py`
- `tests/test_visual_fidelity_benchmark.py`
- `openspec/changes/asset-visual-semantic-fidelity/{proposal,design,tasks}.md`
- Correcciones de docs: `docs/project/agent-context.md`, `docs/project/current-state.md`

## Slice 2 (ACTIVO) — benchmark de codificadores locales (CPU-first)

- **Candidatos SOLO:** A. OpenCLIP `ViT-B/32` / `laion2b_s34b_b79k`; B. SigLIP 2 `google/siglip2-base-patch16-224`. NO ViT-L, NO SO400M, NO VLMs generativos, NO más checkpoints, NO API.
- **Aislamiento:** entorno temporal fuera del repo (p.ej. `/tmp/shorts-visual-fidelity-venv`), CPU-only; descargas fuera del repo; NO tocar `pyproject.toml`/requirements/venv del proyecto/`src/`/`bin/`.
- **Herramienta** `tools/visual_fidelity_local_benchmark.py` (evaluation-only): lazy-import del stack ML (NO es runtime de producción); lee las 38 imágenes reales de `assetPath`; batch=1; deterministic; NO muta imagen/metadata; escribe scores por `assetPath`.
- **GIF:** evaluar explícitamente el frame 0 (coincide con el benchmark humano que clasificó el frame inicial del GIF aurora como FP).
- **Políticas de texto (exactas, sin tuning):** P1 = `queryUsed`; P2 = `"an image depicting: {queryUsed}"`. Una fila por modelo+política; NO max de templates.
- **Similitud nativa:** usar el comportamiento documentado de similitud imagen-texto de cada modelo. OpenCLIP y SigLIP2 NO comparten escala numérica; el umbral se calibra por separado por modelo/política.
- **4 filas CPU:** OpenCLIP P1, OpenCLIP P2, SigLIP2 P1, SigLIP2 P2. Scores crudos bajo `data/evaluations/asset-visual-semantic-fidelity/` (git-ignored), luego alimentados al harness.
- **Salida por fila:** umbral calibrado, acceptableRetained / 30, badRejected / 8, goodAssetRetention, badAssetRejectionRecall, falseAcceptances, falseRejections, elegibilidad provisional; lista de los 8 bad assets y su rechazo; lista de good assets falsamente rechazados.
- **Per-topic + leave-one-topic-out:** agrupar por los 8 topics; calibrar con 7 topics y evaluar el retenido; agregar las 8 predicciones held-out (badRejected, acceptableRetained, falseAcceptances, falseRejections). Evidencia de apoyo, no umbral de producción.
- **Performance medida en CPU:** load time, total scoring time 38 assets, mediana/p95 latencia por candidato, pico RSS (Linux). No persistir estimaciones previas del Plan como medidas.
- **Decisión GPU:** NO instalar CUDA automáticamente. Si ninguna fila cumple o roza el target (badRejected >= 5/8 Y acceptableRetained >= 22/30) → SKIP GPU (la GPU no arregla accuracy). Si hay candidato prometedor: elegir el mejor (1) mayor badRejected, (2) mayor acceptableRetained, (3) menor latencia CPU; un benchmark GPU opcional para ese candidato (batch=1, `torch.cuda.is_available()` verificado, OOM = resultado válido, medir `max_memory_allocated`/`max_memory_reserved`/load success/mediana+p95 latencia; NO forzar batch/quantización).
- **Contrato de decisión por modelo/política:** ELIGIBLE (badRejected>=6/8 y acceptableRetained>=24/30) / NEAR_MISS (>=5/8 y >=22/30) / NOT_USEFUL (por debajo). Comparar calibración vs leave-one-topic-out antes de recomendar viabilidad. NO integrar en runtime.
- **Decisión única de Slice 2:** A. LOCAL_ENCODER_PROMISING (el caso held-out no colapsa obviamente; el benchmark API de Slice 3 sigue útil para fallos de acción/escena) o B. LOCAL_ENCODER_NOT_SUFFICIENT (proceder a Slice 3). NO se cierra el change global en Slice 2.

## Evidencia medida (Slice 2)

Entorno aislado (NO deps del proyecto): CPU `/tmp/shorts-visual-fidelity-venv` (torch 2.13.0+cpu, torchvision 0.28.0+cpu, open_clip_torch 3.3.0, transformers 5.15.0, timm 1.0.28, Pillow 12.3.0), GPU `/tmp/shorts-visual-fidelity-gpu-venv` (torch 2.11.0+cu128). Caché HF fuera del repo.

Resultados calibrados sobre los 38 assets (umbral por selección determinista; conteos crudos):

| Modelo / política | Umbral | retained/30 | badRej/8 | retención | recall | falseAcc | falseRej | Clasificación | LOTO bad/ret |
|---|---|---|---|---|---|---|---|---|---|
| OpenCLIP ViT-B-32 / P1 | 0.2296 | 25 | 7 | 0.833 | 0.875 | 1 | 5 | ELIGIBLE | 7 / 24 |
| OpenCLIP ViT-B-32 / P2 | 0.2338 | 26 | 6 | 0.867 | 0.75 | 2 | 4 | ELIGIBLE | 5 / 26 |
| SigLIP2 base / P1 | 0.00093 | 26 | 5 | 0.867 | 0.625 | 3 | 4 | NEAR_MISS | 5 / 24 |
| SigLIP2 base / P2 | 0.00101 | 24 | 4 | 0.8 | 0.5 | 4 | 6 | NOT_USEFUL | 5 / 23 |

Nota: las escalas de score de OpenCLIP (coseno ~0.23) y SigLIP2 (prob. sigmoid ~0.001) NO son comparables; el umbral se calibra por separado por modelo/política (comportamiento nativo documentado de cada modelo).

Performance CPU medida: OpenCLIP ViT-B-32 load 2.9–4.7 s, total 38 assets 3.3–3.7 s, mediana ~39 ms / p95 ~43 ms, RSS ~1512 MiB; SigLIP2 base load 5.8–6.0 s, total ~6.8 s, mediana ~148 ms / p95 ~158 ms, RSS ~1695 MiB.

Performance GPU medida (OpenCLIP ViT-B-32 P1, GTX 1650 SUPER 4 GB): load OK 4.38 s, sin OOM, 38/38; mediana 9.76 ms / p95 11.3 ms; max_memory_allocated 690.6 MiB, max_memory_reserved 775.9 MiB; scores GPU==CPU (max diff < 1e-6) → misma métrica (25/30, 7/8, ELIGIBLE).

Detalle bad assets (OpenCLIP P1): rechaza 7/8 — antena nocturna, GIF frame 0 en blanco, diagrama pista de tenis, workflow Spring Boot, cabaña de pescador, retrato romano, pulpo colgado. NO rechaza la ilustración de modelo Porsche moderno (s2.2) → fidelidad entidad/temporal es el caso difícil para image-text encoders. Good assets falsamente rechazados (5): aurora night-sky PNG, diagrama Earth-solar, paisaje volcán, VR headset, gráfico amortización.

Decisión Slice 2: **A. LOCAL_ENCODER_PROMISING** (OpenCLIP ViT-B-32 P1 cumple target provisional; held-out no colapsa). Slice 3 (API multimodal) mantiene valor comparativo, especialmente para fallos de acción/escena.

## Slice 3 (futuro, NO en este change) — API multimodal
- Benchmark de API multimodal (OpenAI actual) con contrato estructurado ACCEPT/REJECT
- Registrar precios de API por separado del uso real; coste medido, no estimado del plan
- Comparar alternativas arquitectónicas B/C/D/E y decidir

## Integración en runtime (futura, solo si el benchmark aprueba)
- `executor.py` post-descarga, antes del return RESOLVED; gate de metadata se mantiene como primera etapa. Solo si el benchmark lo justifica.
