# Propuesta: visual-fidelity-compositional-benchmark

## Contexto

`visual-fidelity-runtime` está **COMPLETADO / VERIFICADO / CLOSED** y `main` usa OpenCLIP `ViT-B-32` / `laion2b_s34b_b79k` como SEGUNDO gate visual (umbral calibrado `0.2296`, política P1 = `queryUsed`) sobre los 38 assets canónicos (benchmark `asset-visual-semantic-fidelity`: 25/30 retained + 7/8 badRejected; API `gpt-5.6-luna`: 17/30 + 8/8; decisión `LOCAL_ENCODER_PREFERRED`).

Después del cierre se generaron 3 E2E frescos fuera del corpus (`motor` / `castillos` / `data center`), con revisión humana de los 20 assets resueltos. En ese holdout OpenCLIP NO rechaza ninguno de los 7 bad assets y acepta los 13 buenos (12/12 + 0/8 en la cuenta nominal del enunciado de esta sesión; recuento real por labels individuales 13/13 + 0/7). La fidelidad **composicional** (variante de entidad, relación texto↔escena, "tipo de contenido" vs "concepto") sigue siendo el fallo conocido de la cache de OpenCLIP.

OpenCLIP es un encoder de contraste global (image-text matching implicitamente bi-encoders); un discriminador **explícito de image-text matching** como BLIP ITM (late fusion cross-attention + cabeza de matching) podría capturar relaciones composicionales que el coseno global pierde. La hipótesis de este cambio es evaluar, **benchmark-first**, si BLIP ITM mejora el rechazo de bad assets sin sacrificar la retención de buenos.

## Objetivo

Investigar, **benchmark-first**, la utilidad de BLIP ITM como candidato de segunda etapa visual-semántica frente a OpenCLIP, SIN modificar el runtime de producción:

```
provider candidate
→ metadata gate (deterministic_anchor_coverage_v2, sin cambios)
→ [pixel gate investigado] → ACCEPT / REJECT
```

## Candidato

Solo se evalúa **`Salesforce/blip-itm-base-coco`**:

- `transformers.BlipProcessor` + `transformers.BlipForImageTextRetrieval`
- cabeza ITM (`use_itm_head=True`), score = `softmax(itm_score.float(), dim=-1)[0, 1]` = **matchProbability** (clase positiva de matching)
- El contrato clase-1=MATCH es la convención oficial de Salesforce BLIP: `train_retrieval.py` etiqueta los pares positivos con `ones` (clase 1) y `eval_retrieval.py` puntúa con `itm_head(...)[:, 1]`. La clase 0 es NOT-MATCH y NUNCA se usa como score. Una sanity check de orientación en-run (par compatible vs incompatible sobre un asset real) y tests unitarios offline impiden una inversión silenciosa del contrato.
- raw `queryUsed` como política de texto (P1, sin templates)
- `model.eval()`, `torch.no_grad()`, batch=1, RGB, GIF frame 0
- NO se evalúa `large` en esta fase.

## Protocolo (dos fases, umbral bloqueado)

1. **Calibration (38 canónicos):** seleccionar threshold SOLO con los 38 antiguos usando exactamente la política existente del benchmark (`visual_fidelity_benchmark.select_threshold`): maximizar `badRejected` sujeto a `goodAssetRetention >= 0.80`, empate → mayor `acceptableRetained`, empate total → threshold más estricto. NO alterar labels ni política tras ver el holdout.
2. **Fresh holdout (20):** bloquear el threshold calibrado y medir sobre los 20; reportar `usableRetained/12`, `badRejected/8` (cuenta nominal del enunciado; real 13/7 por labels individuales), `falseAcceptances`, `falseRejections`, resultados por asset y los 5 casos críticos.

**El holdout NO se usa para seleccionar threshold.**

## Invariante de producto

- NO cambia runtime de producción: ni `visual_fidelity.py`, ni `executor.py`, ni `bridge.py`, ni OpenCLIP, ni threshold 0.2296.
- NO se integra BLIP en runtime; los targets de decisión son criterios de investigación, NO contrato de producción.
- NO se modifican los 38 labels canónicos.
- No merge, no push.

## Criterios de decisión (investigación)

- `STRONG_CANDIDATE`: usableRetained >= 10/12 Y badRejected >= 6/8
- `PROMISING`: usableRetained >= 9/12 Y badRejected >= 5/8
- `TRADEOFF_ONLY`: mejora rechazo pero con retención insuficiente
- `NOT_USEFUL`: no mejora materialmente OpenCLIP

Ver `results.md` para el resultado completo y `tasks.md` para la ejecución.