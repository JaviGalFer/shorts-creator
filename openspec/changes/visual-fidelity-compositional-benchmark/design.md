# Design: visual-fidelity-compositional-benchmark

**Status: COMPLETED / VERIFIED / CLOSED** — investigación benchmark-first, sin cambios de runtime. Ver `results.md` para el informe canónico y `tasks.md` para la ejecución/cierre.

## Arquitectura de evaluación (sin cambios de runtime)

Dos dominios separados, igual que los cambios previos de fidelidad visual:

```
tests/fixtures/asset_visual_fidelity/labels.json          ← 38 canónicos (NO tocados)
tests/fixtures/asset_visual_fidelity/holdout_labels.json  ← 20 fresh (NUEVO, trackeado por Git)
        │
        ▼
tools/visual_fidelity_compositional_benchmark.py  ← evaluation-only, lazy-import ML
        │   (blip_itm_base | openclip_vit_b32; device auto/cuda/cpu)
        ▼
data/evaluations/visual-fidelity-compositional-benchmark/*-scores.json  ← git-ignored
        │
        ▼
tools/visual_fidelity_benchmark.py  ← REUTILIZADO tal cual (stdlib-only, offline)
        │   metricas + threshold calibration (misma política determinista existente)
        ▼
openspec/changes/visual-fidelity-compositional-benchmark/results.md  ← informe
```

### Fixture fresh holdout

- `tests/fixtures/asset_visual_fidelity/holdout_labels.json`: 20 assets de los 3 E2E
  fuera del corpus (`cmo-2026-08-18-210827` motor, `cmo-2026-08-18-211151`
  castillos, `qu-2026-08-18-211511` data center), mismos campos y `allowedLabels`
  que el fixture canónico, sin duplicados, `queryUsed` no vacío.
- La fuente de los assetPaths/queries/providers es el resumen persistido de la
  validación runtime actual (`data/evaluations/visual-fidelity-fresh-e2e/summary.json`).
- Labels humanas individuales definidas por esta tarea de investigación. Recuento
  real por labels individuales: **13 ACCEPT (3 CR + 10 CU) / 7 REJECT**. El enunciado
  de la sesión indicaba "ACCEPT (12) / REJECT (8)" como cuenta global; el listado
  individual de labels que lo acompaña suma 13/7, y ese listado es autoritativo.
  Toda métrica aquí se reporta contra 13/7 y se anota la cuenta nominal 12/8.
- El holdout es disjunto del calibration (0 assetPaths en común, testeado).

### Blip ITM score (contrato de clase corregido)

```
processor = BlipProcessor.from_pretrained("Salesforce/blip-itm-base-coco")
model     = BlipForImageTextRetrieval.from_pretrained(...).eval()
inputs    = processor(text=raw_queryUsed, images=image_rgb_gif_frame0, return_tensors="pt")
outputs   = model(**inputs, use_itm_head=True)
logits    = outputs.itm_score                          # shape (batch, 2)
matchProbability     = softmax(logits.float(), dim=-1)[0, 1]   # CLASE 1 = MATCH
notMatchProbability  = softmax(logits.float(), dim=-1)[0, 0]   # CLASE 0 = NOT_MATCH
```

- `itm_score` con `use_itm_head=True` tiene forma `(batch, 2)`. La clase 1 es la
  clase positiva (MATCH) según la implementación oficial de Salesforce BLIP:
  `train_retrieval.py` construye `itm_labels = cat([ones(bs), zeros(2*bs)])`
  (los pares positivos se etiquetan con clase 1) y `eval_retrieval.py` puntúa el
  retrieval con `model.itm_head(...)[:, 1]`.
- El score usado para thresholding es **matchProbability** = softmax clase 1
  (monótona en logit, rango [0,1], score numérico finito). La probabilidad
  complementaria (clase 0) y los logits crudos se persisten por asset como
  `notMatchScores` e `itmLogits` para que el contrato sea auditable.
- **Guard de orientación en-run:** antes de puntuar, `_check_blip_orientation`
  toma un asset real del conjunto, lo puntúa con su propio `queryUsed` (par
  compatible) y con un texto claramente incompatible; aborta el run si
  `matchProbability(compatible) <= matchProbability(incompatible)`. Esto evita
  volver a heredar una inversión silenciosa clase-0-vs-clase-1.
- Tests unitarios offline (`blip_match_from_logits` + assertion de que el
  assignment del score usa `match` y no `not_match`) fijan el contrato sin
  importar ML.
- Deterministic: `eval()`, `no_grad()`, `torch.manual_seed(0)`, batch=1.
- GIF: frame 0 (misma convención que el benchmark humano y que OpenCLIP runtime).

### Reproducción / aislamiento

- Entorno aislado fuera del repo: `/tmp/shorts-visual-fidelity-gpu-venv`
  (torch 2.11.0+cu128, transformers 5.15.0, open_clip_torch 3.3.0, Pillow 12.3.0).
- Caché HF fuera del repo: `/tmp/shorts-visual-fidelity-hf` (incluye el checkpoint
  BLIP descargado). NO se modifican `pyproject.toml` ni requirements del proyecto.
- Score OpenCLIP sobre el holdout ejecutado con el MISMO tool en el MISMO device
  para comparación directa; el threshold de OpenCLIP es el productivo `0.2296`.

## Threshold calibration (bloqueado en calibration, nunca en holdout)

Se reutiliza `tools/visual_fidelity_benchmark.select_threshold` (política
existente, sin cambios): maximizar `badRejected` sujeto a `goodAssetRetention >=
0.80`; si empate en `badRejected`, maximizar `acceptableRetained`; solo si ambos
empatan, threshold más estricto. El winner se bloquea y se aplica al holdout sin re-ajustar.

Resultado del bloqueo (CORRRIGE el anterior 0.015839167404919863, que usaba la
clase 0 — NOT_MATCH — por error y queda **INVALIDADO**): threshold BLIP =
**0.06636959873139858** (probabilidad matchProbability, clase 1).

## Performance (medida, no asumida)

GTX 1650 SUPER (CUDA 12.8), batch=1 (carga reutilizando la caché HF ya poblada):

| Modelo | load | total (38) | mediana | p95 | pico VRAM alloc | pico RSS | OOM |
|---|---|---|---|---|---|---|---|
| BLIP ITM base (corregido) | ~4.3 s | 6.68 s (38) / 3.19 s (20) | ~136 ms | ~153 ms | 924.6 MiB | 1651 MiB | no |
| OpenCLIP ViT-B-32 (holdout) | 2.70 s | 0.82 s | 8.3 ms | 10.6 ms | 624.8 MiB | 1873 MiB | no |

BLIP carga ligeramente más y puntúa ~16× más lento por asset que OpenCLIP en esta
GPU (~136 ms vs 8.3 ms), con mayor pico de VRAM (924.6 vs 624.8 MiB).

## Riesgos y límites conocidos

- BLIP base está entrenado en COCO (fotografías y pares imagen-texto
  relativamente literales); los assets del pipeline incluyen diagramas e
  ilustraciones abstractas donde el matching literal es más difícil. Este sesgo
  es precisamente lo que se mide.
- Dataset de negativos pequeño (7-8), igual que el benchmark previo; los conteos
  crudos se reportan siempre, no solo porcentajes.
- Score = solo la cabeza ITM (sin agregar la rama ITC/contrastiva); decisión
  documentada del protocolo para aislar el matching explícito.
- El contrato de clase 1=MATCH se fija por fuente oficial, sanity check en-run y
  tests; no se asume silenciosamente (ver sección "Blip ITM score").