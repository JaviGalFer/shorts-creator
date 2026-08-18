# Informe de resultados: visual-fidelity-compositional-benchmark

**Estado:** investigación benchmark-first COMPLETADA — BLIP ITM base **NOT_USEFUL**. Sin integración runtime.

Resumen de 1 línea: BLIP ITM base no rechaza ningún bad asset en el holdout fresco
(0/7, igual que OpenCLIP), degrada frente a OpenCLIP en el calibration (1/8 vs 7/8)
y es 17× más lento por asset en la misma GPU. No mejora materialmente el estado actual.

---

## 1. Entorno

- CPU/GPU: NVIDIA GeForce GTX 1650 SUPER (CUDA 12.8), 4 GB VRAM (910 MiB en uso por display; ~3.2 GB libres).
- Python/venv aislado: `/tmp/shorts-visual-fidelity-gpu-venv` (fuera del repo).
- Versiones: `torch 2.11.0+cu128`, `transformers 5.15.0`, `open_clip_torch 3.3.0`, `Pillow 12.3.0`.
- Caché HF externa: `/tmp/shorts-visual-fidelity-hf` (checkpoint BLIP descargado ahí). Sin cambios en requirements del proyecto.
- Config: batch=1, `eval()`, `no_grad()`, seed fijo, RGB, GIF frame 0, raw `queryUsed`, `use_itm_head=True`, score = `softmax(itm_score)[0,0]`.

## 2. BLIP CUDA / VRAM / latencia (medido, no asumido)

| run | load (s) | total score (s) | mediana (ms) | p95 (ms) | pico VRAM alloc (MiB) | pico RSS (MiB) | OOM |
|---|---|---|---|---|---|---|---|
| calibration 38 | 15.30 (incluye descarga pesos) | 25.97 | 140.9 | 264.0 | 924.6 | 2324 | no |
| holdout 20 | 11.07 | 6.51 | 140.9 | 154.1 | 924.6 | 1654 | no |
| OpenCLIP ViT-B-32 holdout 20 | 2.70 | 0.82 | 8.3 | 10.6 | 624.8 | 1873 | no |

Observación: BLIP base cabe en la GTX 1650 SUPER sin OOM con batch=1. Latencia por
asset ~140.9 ms de mediana (>17× OpenCLIP 8.3 ms), pico VRAM 924.6 vs 624.8 MiB.

## 3. Calibration 38

Labels: 16 CR / 14 CU / 8 FP → 30 ACCEPT / 8 REJECT (invariantes).

Threshold seleccionado con la política existente (max badRejected sujeto a
goodAssetRetention >= 0.80 → max retained → estricto): **0.015839167404919863** (probabilidad ITM).

| modelo | threshold | retained/30 | badRejected/8 | retention | recall | falseAcc | falseRej | eligible (provisional) |
|---|---|---|---|---|---|---|---|---|
| **BLIP ITM base P1** | 0.01584 | 27 | 1 | 0.9 | 0.125 | 7 | 3 | NO |
| OpenCLIP ViT-B-32 P1 (referencia, previo) | 0.2296 | 25 | 7 | 0.833 | 0.875 | 1 | 5 | SÍ |

Confusión BLIP: TP 27 / TN 1 / FP 7 / FN 3.

Los scores BLIP son **bimodales** (min 0.0028, max 0.99997, mediana 0.536; la
mayoría de assets caen ~0.0 o ~0.99+ y la franja media está casi vacía). La cabeza
ITM produce decisiones de "match/no-match" muy confiadas que no separan los
negativos del pipeline: solo rechaza el caso extremo (ilustración de modelo Porsche
moderno, score 0.0131) y deja pasar 7 false positives.

## 4. Threshold BLIP bloqueado

- `0.015839167404919863` (probabilidad softmax ITM de la clase de matching).
- BLOQUEADO desde calibration; el holdout solo se evalúa contra él. Nunca aparece en fixtures (assert testado).

## 5. Fresh holdout 20

Labels individuales: 3 CR / 10 CU / 7 FP → **13 ACCEPT / 7 REJECT** (el enunciado
global decía "12/8"; el listado individual de labels suma 13/7 y es la fuente
autoritativa; equivalencia sobre la cuenta nominal 12/8 se anota abajo).

Métricas @ threshold bloqueado (BLIP) y @0.2296 (OpenCLIP productivo):

| modelo | usableRetained/13 | badRejected/7 | falseAcc | falseRej | confusion |
|---|---|---|---|---|---|
| **BLIP ITM base** @0.01584 | 13 | 0 | 7 | 0 | TP 13 / TN 0 / FP 7 / FN 0 |
| OpenCLIP ViT-B-32 @0.2296 | 13 | 0 | 7 | 0 | TP 13 / TN 0 / FP 7 / FN 0 |

En la cuenta nominal del enunciado (12/8): BLIP **12/12 + 0/8**, OpenCLIP **12/12 + 0/8** — equivalentes.

## 6. Comparación OpenCLIP vs BLIP

- En el holdout fresco ambos aceptan TODO: 13/13 usable retained y 0/7 bad rejected.
- En el calibration BLIP es **peor**: 1/8 badRejected vs 7/8 de OpenCLIP, con igual
  "coste" en retención (27/30 vs 25/30). La curva ROC implícita de BLIP no alcanza
  una operación útil en los 38.
- Rendimiento: OpenCLIP es más rápido y ligero en esta GPU.
- Conclusión de comparación: BLIP ITM base no aporta ninguna ganancia de rechazo
  sobre OpenCLIP ni en calibración ni en datos nuevos; la decisión de producto
  existente (`LOCAL_ENCODER_PREFERRED` → OpenCLIP) se mantiene.

## 7. Los cinco casos críticos (todos FALSE_POSITIVE_OR_UNUSABLE)

| caso | asset | BLIP score | OpenCLIP score | rechazado por |
|---|---|---|---|---|
| motor 2T vs query 4T | motor 1.2 | 0.98515 | 0.26753 | ninguno (FAIL) |
| castle genérico vs workers building | castillos 1.1 | 0.85676 | 0.25211 | ninguno (FAIL) |
| castle landscape vs architectural plans | castillos 3.1 | 0.63309 | 0.25656 | ninguno (FAIL) |
| castle genérico vs construction-time diagram | castillos 4.2 | 0.39384 | 0.30679 | ninguno (FAIL) |
| blockchain/digital art vs data-center infrastructure | data center 1.2 | 0.99798 | 0.24839 | ninguno (FAIL) |

Los 5 casos suponen fallos **composicionales/tipológicos** (variante de motor, tipo
de contenido "construcción/planos/diagrama temporal" vs "castillo", arte digital vs
infraestructura). BLIP ITM confía alto en 4/5 (0.85–0.99) y bajo-medio en uno
(0.39), pero ninguno cae bajo el threshold bloqueado. La cabeza ITM de BLIP no
resuelve la fidelidad composicional que motiva esta investigación y en 4 de los 5
casos es más confiada que OpenCLIP.

## 8. Decisión

- **Clasificación: NOT_USEFUL** (retained 13/13 pero badRejected 0/7; no hay mejora
  material sobre OpenCLIP 0/7; en calibration BLIP 1/8 < OpenCLIP 7/8).
- No cumple ningún tramo de `STRONG_CANDIDATE` (>=10/12 y >=6/8) ni `PROMISING`
  (>=9/12 y >=5/8); no aplica `TRADEOFF_ONLY` porque no mejora el rechazo.
- **NO se integra BLIP en runtime.** Se mantiene OpenCLIP ViT-B-32 @0.2296 como el
  pixel gate vigente. Los targets siguen siendo criterios de investigación, no
  contrato de producción.
- Línea futura (no en este cambio): el caso de blockchain/digital-art vs
  data-center y los fallos tipológicos sugieren que la ganancia no vendrá de un
  discriminador imagen-texto binario literal (BLIP), sino de judges con vocabulario
  de tipo/contenido (p.ej. dirección API estudiada en Slice 3B de
  `asset-visual-semantic-fidelity`) o de características composicionales
  específicas. No se decide nada aquí.

## 9. Validación

- `python3 -m pytest -q tests` → suite completa verde (baseline 1494 + tests del harness).
- `git diff --check` limpio.
- Sin cambios en `visual_fidelity.py`, `executor.py`, `bridge.py`, threshold OpenCLIP ni producción.
- Artefactos de scores (git-ignored): `data/evaluations/visual-fidelity-compositional-benchmark/`.
- Commit (rama `change/visual-fidelity-compositional-benchmark`): investigación/docs únicamente.