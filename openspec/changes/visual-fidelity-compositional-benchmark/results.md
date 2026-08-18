# Informe de resultados: visual-fidelity-compositional-benchmark (CORREGIDO)

**Estado:** investigación benchmark-first **COMPLETED / VERIFIED / CLOSED** — BLIP ITM base **TRADEOFF_ONLY**. Sin integración runtime. Mergeada a `main` (no-ff).

> **CORRECCIÓN DE ORIENTACIÓN:** la primera versión de este benchmark puntuó
> `softmax(itm_score)[0, 0]`, es decir, la probabilidad de la clase 0 =
> **NOT_MATCH** de la cabeza ITM de BLIP. La implementación oficial de
> Salesforce BLIP usa la clase **1 = MATCH** (pares positivos etiquetados con
> `ones` en `train_retrieval.py`; retrieval puntuado con `itm_head(...)[:, 1]`
> en `eval_retrieval.py`). Todos los resultados de esa primera versión
> (threshold 0.015839167, 27/30 + 1/8, decisión NOT_USEFUL, "scores
> bimodales") están **INVALIDADOS**. Este informe usa `softmax(itm_score.float())[0, 1]`
> = matchProbability, con sanity check de orientación en-run y tests.

Resumen de 1 línea: corregido, BLIP ITM base cumple el target provisional de
calibración (6/8 y 24/30) y en el holdout fresco rechaza 2/7 bad assets (los dos
más difíciles: motor 2T y blockchain vs data-center) donde OpenCLIP rechaza 0/7,
pero sacrifica retención (9/13) frente a OpenCLIP (13/13) → TRADEOFF_ONLY.

---

## 1. Prueba de orientación clase 0/1

- **Fuente oficial:** `train_retrieval.py` etiqueta pares positivos con `ones`
  (clase 1) y negativos con `zeros` (clase 0); `eval_retrieval.py` puntúa el
  ranking de retrieval con `model.itm_head(...)[:, 1]`. Clase 1 = MATCH, clase 0
  = NOT_MATCH.
- **Sonda manual (2 assets conocidos-buenos):**
  - Volcano (`qu-2026-08-17-234954` s4.1, query "volcanic ash eruption
    photograph"): match(propio query)=0.9963, match(texto no relacionado)=0.0003.
  - Pulpo (`cmo-2026-08-17-234735` s4.1, query "blue ringed octopus venom
    photograph"): match(propio query)=0.9972, match(texto no relacionado)=0.0001.
- **Sanity check en-run (`_check_blip_orientation`):** carga el primer asset del
  conjunto y compara matchProbability(own queryUsed) vs
  matchProbability(texto incompatible); aborta el run si `compatible <=
  incompatible`. En calibration: 0.000103 > 0.000014 (ok). En holdout:
  0.125861 > 0.000018 (ok).
- **Tests unitarios offline:** `blip_match_from_logits` (softmax clase 1) + test
  de que el score persistido por asset es `match` y nunca `not_match` + test de
  que `[0, 0]` no indexa el match. 12 tests verdes.

## 2. Entorno

- GPU: NVIDIA GeForce GTX 1650 SUPER (CUDA 12.8), 4 GB VRAM (910 MiB en uso por display; ~3.2 GB libres).
- venv aislado: `/tmp/shorts-visual-fidelity-gpu-venv` (fuera del repo).
- Versiones: `torch 2.11.0+cu128`, `transformers 5.15.0`, `open_clip_torch 3.3.0`, `Pillow 12.3.0`.
- Caché HF externa: `/tmp/shorts-visual-fidelity-hf`. Sin cambios en requirements del proyecto.
- Config: batch=1, `eval()`, `no_grad()`, seed fijo, RGB, GIF frame 0, raw `queryUsed`, `use_itm_head=True`.

## 3. BLIP CUDA / VRAM / latencia (medido, no asumido)

| run | load (s) | total score (s) | mediana (ms) | p95 (ms) | pico VRAM alloc (MiB) | pico RSS (MiB) | OOM |
|---|---|---|---|---|---|---|---|
| calibration 38 | 4.33 | 6.68 | 136.1 | 152.8 | 924.6 | 1651 | no |
| holdout 20 | 4.22 | 3.19 | 135.6 | 143.3 | 924.6 | 1651 | no |
| OpenCLIP ViT-B-32 holdout 20 | 2.70 | 0.82 | 8.3 | 10.6 | 624.8 | 1873 | no |

BLIP cabe en la GTX 1650 SUPER sin OOM con batch=1. Mediana ~136 ms/asset (~16×
OpenCLIP 8.3 ms), pico VRAM 924.6 vs 624.8 MiB.

## 4. Calibration 38 (retiene + badRejected)

Labels: 16 CR / 14 CU / 8 FP → 30 ACCEPT / 8 REJECT (invariantes).

Threshold seleccionado con la política existente (max badRejected sujeto a
goodAssetRetention >= 0.80 → max retained → estricto): **0.06636959873139858**
(matchProbability, clase 1).

| modelo | threshold | retained/30 | badRejected/8 | retention | recall | falseAcc | falseRej | eligible (provisional) |
|---|---|---|---|---|---|---|---|---|
| **BLIP ITM base P1 (corregido)** | 0.06637 | 24 | 6 | 0.80 | 0.75 | 2 | 6 | **SÍ** (>=24/30 y >=6/8) |
| OpenCLIP ViT-B-32 P1 (referencia) | 0.2296 | 25 | 7 | 0.833 | 0.875 | 1 | 5 | SÍ |

Confusión BLIP: TP 24 / TN 6 / FP 2 / FN 6.

Sweep (puntos clave): con t=0.06637 se rechazan 6/8 malos; subir a 0.08346 ya
pierde un bueno sin ganar un malo (23/30, 6/8) y 0.14098 da 23/30 + 7/8 pero
rompe retención; bajar a 0.05384 queda en 5/8 con 24/30.

## 5. NUEVO threshold bloqueado

- `0.06636959873139858` (probabilidad softmax ITM de la clase 1 = MATCH).
- Bloqueado desde calibration; el holdout solo se evalúa contra él. Anterior
  `0.015839167404919863` (clase 0, NOT_MATCH) INVALIDADO. Nunca aparece en fixtures (assert testado).

## 6. Fresh holdout 20

Labels individuales: 3 CR / 10 CU / 7 FP → **13 ACCEPT / 7 REJECT** (el enunciado
global decía "12/8"; el listado individual de labels suma 13/7 y es la fuente
autoritativa; equivalencia sobre la cuenta nominal 12/8 se anota abajo).

Métricas @ threshold bloqueado (BLIP 0.06637) y @0.2296 (OpenCLIP productivo):

| modelo | usableRetained/13 | badRejected/7 | falseAcc | falseRej | confusion |
|---|---|---|---|---|---|
| **BLIP ITM base** @0.06637 | 9 | 2 | 5 | 4 | TP 9 / TN 2 / FP 5 / FN 4 |
| OpenCLIP ViT-B-32 @0.2296 | 13 | 0 | 7 | 0 | TP 13 / TN 0 / FP 7 / FN 0 |

Sobre la cuenta nominal del enunciado (12/8): BLIP **9/13 (~8/12) usable + 2/7
(~2/8) bad**; OpenCLIP **12/12 + 0/8**.

Modelo FALSO-rechaza 4 buenos que OpenCLIP conserva: castillos 1.2 ("medieval
workers building castle illustration", blip 0.0063), data center 2.2 (0.0024),
data center 4.2 (0.0006), data center 5.2 (0.0389).

## 7. Siete bad assets (holdout) — scores BLIP corregidos

| scene | query | human | BLIP match | BLIP verdict | OpenCLIP |
|---|---|---|---|---|---|
| castillos 4.2 | medieval castle construction time diagram | REJECT | 0.60616 | ACCEPT | 0.30679 |
| castillos 3.1 | medieval castle architectural plans illustration | REJECT | 0.36691 | ACCEPT | 0.25656 |
| castillos 5.1 | medieval castle historical significance photograph | REJECT | 0.27643 | ACCEPT | 0.25593 |
| castillos 1.1 | medieval castle construction photograph | REJECT | 0.14324 | ACCEPT | 0.25211 |
| castillos 4.1 | completed medieval castle photograph | REJECT | 0.06949 | ACCEPT | 0.24077 |
| motor 1.2 | four stroke engine automobile photograph | REJECT | **0.01485** | **REJECT** | 0.26753 |
| data center 1.2 | data center infrastructure diagram | REJECT | **0.00202** | **REJECT** | 0.24839 |

BLIP rechaza 2/7; los 5 de castillos quedan aceptados. Los dos rechazados son los
casos composicionales más difíciles que OpenCLIP no rechaza.

## 8. Comparación OpenCLIP vs BLIP (corregida)

- **En el holdout fresco BLIP YA NO acepta todo:** rechaza 2/7 bad assets.
- La señal de rechazo de BLIP es **discreta pero certera**: solo los 2 casos menos
  literales del set son cazados (motor 2T y blockchain/digital-art vs
  infraestructura); los 5 casos de castillos (todos variantes "castillo
  final/generic") se le escapan.
- Coste en retención: BLIP pierde 4 buenos (13→9); OpenCLIP pierde 0.
- Calibration: BLIP cuasi-equivalente a OpenCLIP (24/30 + 6/8 vs 25/30 + 7/8).
- Rendimiento: OpenCLIP sigue más rápido y ligero.
- Conclusión: no hay reemplazo del gate, pero la señal de rechazo de BLIP es
  complementaria y valorable a futuro (ver §9).

## 9. Cinco casos críticos (todos FALSE_POSITIVE_OR_UNUSABLE de la fase 2)

| caso | asset | BLIP match | BLIP verdict | OpenCLIP | OpenCLIP verdict |
|---|---|---|---|---|---|
| motor 2T vs query 4T | motor 1.2 | 0.01485 | **REJECT** | 0.26753 | ACCEPT |
| castle final/no-construcción vs `medieval castle construction photograph` | castillos 1.1 | 0.14324 | ACCEPT | 0.25211 | ACCEPT |
| castle vs architectural plans (castillos 3.1) | `medieval castle architectural plans illustration` | 0.36691 | ACCEPT | 0.25656 | ACCEPT |
| castle vs construction-time diagram (castillos 4.2) | `medieval castle construction time diagram` | 0.60616 | ACCEPT | 0.30679 | ACCEPT |
| blockchain/digital art vs data-center infra | data center 1.2 | 0.00202 | **REJECT** | 0.24839 | ACCEPT |

BLIP rechaza **2/5** de los casos críticos (motor 2T y blockchain vs
data-center); los 3 casos de castillo quedan aceptados por ambos modelos. A
diferencia del informe anterior, BLIP ya no es un "acepta todo".

## 10. Decisión (criterios registrados)

- Bloquear/suelto BLIP 9/13 usable retained y 2/7 badRejected:
  - NO es `STRONG_CANDIDATE` (necesita >=10/12 usable Y >=6/8 bad; tiene ~8/12 y ~2/8).
  - NO es `PROMISING` (necesita >=9/12 usable Y >=5/8 bad; tiene ~8/12 y ~2/8).
  - **SÍ es `TRADEOFF_ONLY`**: mejora el rechazo de bad assets (2/7 vs 0/7 en
    holdout; hit de calibración 6/8 + 24/30) pero con retención insuficiente
    (9/13 vs 13/13).
- **NO se integra BLIP en runtime.** Se mantiene OpenCLIP ViT-B-32 @0.2296 como
  el pixel gate vigente. Los targets siguen siendo criterios de investigación,
  no contrato de producción.
- Línea futura (no en este cambio): estudiar una **fusión** de la señal de
  rechazo de BLIP (certera en casos composicionales) con la retención de
  OpenCLIP, o judges con vocabulario de tipo/contenido (dirección API del Slice
  3B de `asset-visual-semantic-fidelity`). No se decide nada aquí.

## 11. Validación

- `python3 -m pytest tests/test_visual_fidelity_compositional_benchmark.py -q` → 12 verdes.
- `python3 -m pytest -q tests` → suite completa verde.
- `git diff --check` limpio.
- Sin cambios en `visual_fidelity.py`, `executor.py`, `bridge.py`, threshold OpenCLIP ni producción.
- Artefactos de scores (git-ignored): `data/evaluations/visual-fidelity-compositional-benchmark/`.
- Commit (rama `change/visual-fidelity-compositional-benchmark`): corrección de orientación + docs.