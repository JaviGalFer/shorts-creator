# Propuesta: visual-fidelity-vlm-judge-v2

**Status: COMPLETED / VERIFIED / CLOSED** — investigación benchmark-first, sin
integración de runtime. Resultado: **`VLM_JUDGE_V2_NOT_USEFUL`**, no se integra.
Ver `results.md` para el informe y `tasks.md` para la ejecución.

## Contexto

`visual-fidelity-runtime` está **COMPLETADO / VERIFICADO / CLOSED**: OpenCLIP
`ViT-B-32` / `laion2b_s34b_b79k` es el pixel gate vigente (segunda etapa,
después del metadata gate) con umbral calibrado `0.2296` y política P1
(`queryUsed`). Sobre los 38 canónicos: **25/30 retained + 7/8 badRejected**
(FA 1, FR 5). El gate está OFF por defecto; solo `VISUAL_FIDELITY_THRESHOLD`
lo activa.

`visual-fidelity-compositional-benchmark` (CLOSED) evaluó BLIP ITM
(`Salesforce/blip-itm-base-coco`) frente a OpenCLIP como candidato de fidelidad
**composicional** (variante de entidad, relación texto↔escena, tipo de
contenido): BLIP calibra 24/30 + 6/8 ELIGIBLE pero en el fresh holdout de 20
(que hoy se considera **development evidence**, no holdout de generalización)
rechaza 2/7 bad assets (los dos críticos: motor 2T y blockchain vs data-center)
sacrificando retención: 9/13 usable (4 buenos perdidos) frente a 13/13 de
OpenCLIP. Decisión: **TRADEOFF_ONLY**, BLIP NO integrado.

El fallo restante conocico es que OpenCLIP acepta falsos positivos
composicionales (motor 2T, blockchain/digital-art, castillo final vs
construcción, planos, construction-time diagram); el API multimodal de la
Slice 3A (`gpt-5.6-luna`, judge estricto binario ACCEPT/REJECT) tuvo demasiada
retención sacrificada: 17/30 + 8/8 (0 FA, 13 FR). La hipótesis de este cambio
es que un judge VLM **menos conservador**, con tres vías
(ACCEPT / REJECT / UNCERTAIN) y fail-open operativo (UNCERTAIN ⇒ ACCEPT),
pueda capturar los mismatches materiales que OpenCLIP pierde **sin** sacrificar
la retención de buenos.

## Objetivo

Investigar, benchmark-first, un judge multimodal API menos conservador como
candidato de segunda etapa visual-semántica frente a OpenCLIP y BLIP, SIN
modificar el runtime de producción.

```
provider candidate
→ metadata gate (deterministic_anchor_coverage_v2, sin cambios)
→ [pixel gate investigado] → ACCEPT / REJECT
```

## Candidato

- Modelo API: **`gpt-5.6-luna`** (Responses API), una request independiente por
  asset:
  - imagen `detail=high`
  - `reasoning: {effort: none}`
  - sin web/buscador/tools
  - Structured Output estricto (`json_schema`, `strict: true`)
  - NO se envía `humanLabel`, ni scores/verdicts de OpenCLIP/BLIP, ni verdict
    esperado.
- Input semántico:
  - `queryUsed` (el `searchQuery` del segmento, política P1)
  - `assetPreference` **solo si ya forma parte del contrato del segmento**
    (se lee del contrato persistido del job, no se inventa)
- Output estructurado:
  - `verdict`: `ACCEPT` | `REJECT` | `UNCERTAIN`
  - `reasonCode` (enum cerrado)
  - `shortReason` (texto breve)

### Contrato del judge

- **ACCEPT**: la imagen representa suficientemente el sujeto/intención
  principal, aunque sea aproximada, genérica o no incluya detalles secundarios.
- **REJECT SOLO si existe mismatch material**:
  - entidad/variante central incorrecta
  - contradicción factual visible
  - acción/relación esencial ausente y la imagen resulta engañosa
  - tipo de contenido solicitado sustituido por algo semánticamente distinto
  - imagen esencialmente ajena al concepto
- **UNCERTAIN**: no hay evidencia visual suficiente para afirmar un mismatch
  material.
- Para métricas operativas: **UNCERTAIN ⇒ ACCEPT** (fail-open para proteger
  retención).
- No se exige literalidad total de la query; COARSE_BUT_USABLE debe poder pasar.

## Protocolo (dos fases, sin seleccionar threshold — judge directo)

1. **Canonical 38:** ejecutar el judge sobre los 38 canónicos y reportar
   `retained/30`, `badRejected/8`, `FP`, `FN`, distribución
   ACCEPT/REJECT/UNCERTAIN, confusion matrix, coste real y latencia mediana/p95.
2. **Development 20:** los 20 ya etiquetados se reutilizan SIN relabel y **NO
   cuentan como holdout nuevo de generalización**; son development evidence.
   Reportar `usableRetained/13`, `badRejected/7`, FP/FN, los 7 bad assets y los
   4 buenos que BLIP rechazaba.

**Los 20 no se usan para calibrar nada; son development evidence.**

## Coste

- Preflight de tokens antes de ejecutar.
- Hard cap total: **$0.10** entre las dos fases (38 + 20 = 58 assets).
- Si la proyección supera `$0.10`, PARAR sin ejecutar.
- Persistir uso/coste real por request; sin API key ni base64 en los outputs.

## Invariante de producto

- NO cambia runtime: ni `visual_fidelity.py`, ni `executor.py`, ni `bridge.py`,
  ni el umbral OpenCLIP `0.2296`, ni BLIP, ni providers, ni prompts del
  generador.
- NO se modifican los labels de los 38 canónicos ni de los 20.
- No merge, no push, no reindex.

## Criterios de decisión (investigación)

Un candidato se considera **`VLM_JUDGE_V2_PROMISING`** solo si cumple:

- canonical: `retained >= 24/30` Y `badRejected >= 6/8`
- development-20: `usableRetained >= 11/13` Y `badRejected >= 4/7`

En caso contrario, **`VLM_JUDGE_V2_NOT_USEFUL`** y se para.

Aun siendo PROMISING: **NO se integra runtime**. El siguiente paso sería un
holdout REALMENTE nuevo con nuevos E2E.

Ver `tasks.md` para ejecución y `results.md` para el informe.