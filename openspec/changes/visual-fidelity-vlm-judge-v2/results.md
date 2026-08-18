# Results: visual-fidelity-vlm-judge-v2

**Status: COMPLETED / VERIFIED / CLOSED (investigación)** — juez multimodal
`gpt-5.6-luna` menos conservador evaluado **benchmark-first**. **NO se integra
runtime.** Decisión: **`VLM_JUDGE_V2_NOT_USEFUL`**.

## 1. Contrato exacto del judge

- Modelo: **`gpt-5.6-luna`**, Responses API, 1 request independiente por asset.
- Imagen `detail=high`; `reasoning: {effort: none}`; sin web/tools.
- Structured Output estricto (`json_schema`, `strict: true`).
- NO se envía `humanLabel`, ni scores/verdicts de OpenCLIP/BLIP, ni verdict
  esperado.
- Input semántico: `queryUsed` (searchQuery del segmento) + `assetPreference`
  **solo cuando forma parte del contrato persistido del segmento**
  (`metadata.json → script.scenes[n].visualPlan.visualSequence[s].assetPreference`).
- Output: `{verdict: ACCEPT|REJECT|UNCERTAIN, reasonCode, shortReason}`.
- Semántica:
  - **ACCEPT** si representa suficientemente el sujeto/intención principal
    (aproximado/genérico/detalles secundarios opcionales; COARSE_BUT_USABLE pasa).
  - **REJECT SOLO si existe mismatch material** (entidad/variante central
    incorrecta; contradicción factual visible; acción/relación esencial ausente
    y engañosa; tipo de contenido sustituido; imagen esencialmente ajena).
  - **UNCERTAIN** si no hay evidencia visual suficiente para afirmar mismatch
    material.
- Métrica operativa: **UNCERTAIN ⇒ ACCEPT** (fail-open). En la práctica el juez
  nunca emitió UNCERTAIN (0 en ambas fases), por lo que el fail-open no llegó a
  activarse.

## 2. Preflight / coste real (hard cap total `$0.10`)

- Preflight canonical-38: `READY`, input 72 739 tokens, proyección `$0.020 385`.
- Preflight development-20: `READY`, input 35 779 tokens, proyección `$0.010 228`.
- Proyección total: **`$0.030 613`** << cap `$0.10`. No se superó el cap.
- Coste real:
  - canonical-38: **`$0.004 462`** (`$0.000117 425`/asset; alta caché por
    re-ejecución).
  - development-20: **`$0.008 589`** (`$0.000429 430`/asset).
  - Total real persistido: **`$0.013 051`**. (Una 1ª ejecución de canonical-38
    descartada —ver más abajo— sumó ≈`$0.017`; aun así el total real no superó
    `$0.10`.)
- Sin API key ni base64 en outputs (solo fingerprint SHA-256 no secreto).
- Latencia: canonical-38 mediana **1.592 s** / p95 **5.970 s**;
  development-20 mediana **1.584 s** / p95 **2.626 s**.

Nota de determinismo: el juez es **no determinista** (temperatura). La primera
ejecución de canonical-38 (parcial por un edge del reasonCode, corregido) dio
ACCEPT 22 / REJECT 15 / 1 error; la ejecución final ACK 21 / REJECT 17. La
magnitud no cambia la conclusión (rechazo excesivo de buenos en ambos casos).

## 3. Canonical 38

Verdicts finales: **21 ACCEPT / 17 REJECT / 0 UNCERTAIN**.

| Métrica | OpenCLIP @0.2296 | BLIP ITM @0.06637 | Slice3A API | **VLM V2 (esta ejec.)** |
|---|---|---|---|---|
| retained / 30 | 25 | 24 | 17 | **21** |
| badRejected / 8 | 7 | 6 | 8 | **8** |
| falseAcceptances | 1 | 2 | 0 | **0** |
| falseRejections | 5 | 6 | 13 | **9** |

Confusion matrix VLM V2: TP 21 / TN 8 / FP 0 / FN 9.
Reason codes VLM V2: `MISSING_ESSENTIAL_RELATION` 8, `WRONG_CONTENT_TYPE` 4,
`MATCH` 21, `INSUFFICIENT_VISUAL_EVIDENCE` 1, `WRONG_VARIANT_OR_ERA` 1,
`WRONG_ACTION_OR_SCENE` 1, `FACTUAL_CONTRADICTION` 1, `WRONG_ENTITY` 1.

**Barra canonical: `retained >= 24/30` → 21/30 NO CUMPLE.**

## 4. Development 20 (development evidence, NO generalización)

Verdicts finales: **6 ACCEPT / 14 REJECT / 0 UNCERTAIN**.

| Métrica | OpenCLIP @0.2296 | BLIP ITM @0.06637 | **VLM V2 (esta ejec.)** |
|---|---|---|---|
| usableRetained / 13 | 13 | 9 | **4** |
| badRejected / 7 | 0 | 2 | **5** |
| falseAcceptances | 7 | 5 | **2** |
| falseRejections | 0 | 4 | **9** |

Los 20 ya NO cuentan como holdout nuevo; son **development evidence** y no se
afirma generalización sobre ellos.

### 7 bad assets (dev-20)

| Asset | query | VLM V2 verdict |
|---|---|---|
| motor 1.2 | four stroke engine automobile photograph (2T) | **ACCEPT** (falla) |
| castillos 1.1 | medieval castle construction photograph | REJECT ✓ |
| castillos 3.1 | medieval castle architectural plans illustration | REJECT ✓ |
| castillos 4.1 | completed medieval castle photograph | REJECT ✓ |
| castillos 4.2 | medieval castle construction time diagram | REJECT ✓ |
| castillos 5.1 | medieval castle historical significance photograph | **ACCEPT** (falla) |
| data center 1.2 | data center infrastructure diagram | REJECT ✓ |

→ **5/7 badRejected** (mejor que OpenCLIP 0/7 y BLIP 2/7, pero con retención
devastada).

### Los 4 buenos que BLIP rechazaba

| Asset | query | VLM V2 verdict |
|---|---|---|
| castillos 1.2 | medieval workers building castle illustration | REJECT (también) |
| data center 2.2 | application hosting architecture diagram | REJECT (también) |
| data center 4.2 | data center security architecture diagram | REJECT (también) |
| data center 5.2 | data center technology diagram | ACCEPT ✓ |

→ VLM V2 conserva 1 de los 4 que BLIP perdía; rechaza los otros 3 igual.

## 5. Casos críticos

| Caso crítico | OpenCLIP | BLIP | **VLM V2** |
|---|---|---|---|
| motor 2T vs query 4T | ACCEPT | REJECT | **ACCEPT** ✗ |
| data-center vs blockchain art | ACCEPT | REJECT | **REJECT** ✓ |
| castillo final vs construcción | ACCEPT | ACCEPT | **REJECT** ✓ |
| castillo vs planos | ACCEPT | ACCEPT | **REJECT** ✓ |
| castillo vs construction-time diagram | ACCEPT | ACCEPT | **REJECT** ✓ |

VLM V2 resuelve 4/5 casos críticos (los 3 de castillos y data-center vs
blockchain) pero **no** distingue motor 2T vs 4T (mismo punto ciego que
OpenCLIP; el shortReason describió la imagen como diagrama de motor de cuatro
tiempos y la aceptó).

## 6. Comparación OpenCLIP / BLIP / VLM V2

- **Rechazo de bad assets:** VLM V2 (canonical 8/8; dev 5/7) supera a OpenCLIP
  (7/8; 0/7) y a BLIP (6/8; 2/7), sobre todo en dev.
- **Retención de buenos:** VLM V2 es el PEOR (canonical 21/30; dev 4/13), por
  debajo de OpenCLIP (25/30; 13/13) y de BLIP (24/30; 9/13). El juez usa
  abundantemente razones estrictas (`MISSING_ESSENTIAL_RELATION`,
  `WRONG_CONTENT_TYPE`) y rechaza muchos buenos de tipo diagrama/esquema.
- El fail-open (UNCERTAIN ⇒ ACCEPT) **no llegó a activarse** (0 UNCERTAIN), así
  que no mitigó la conservaduría estructural del juez.
- Coste/latencia: asequible ($0.013 real, mediana ~1.6 s), pero irrelevante
  frente a la calidad.

## 7. Decisión

Criterios:

- canonical: `retained >= 24/30` (21) Y `badRejected >= 6/8` (8) → **NO**.
- development-20: `usableRetained >= 11/13` (4) Y `badRejected >= 4/7` (5) → **NO**.

Falla ambas barras. **`VLM_JUDGE_V2_NOT_USEFUL`** — el juez VLM menos
conservador mejora el rechazo de bad assets (ahí coincide con la línea BLIP)
pero sacrifica demasiada retención de buenos (incluso peor que BLIP). **NO se
integra runtime y NO se justifica un holdout nuevo.** OpenCLIP `0.2296` sigue
siendo el pixel gate vigente cuando está activado; `visual-fidelity-runtime`
sigue OFF por defecto.

## 8. Tests

- `tests/test_visual_fidelity_vlm_judge_v2.py`: **20 passed** (contrato 3-vías,
  coherencia reasonCode↔verdict, UNCERTAIN fail-open, `assetPreference` desde
  contrato, coste/caché, fingerprint, sin fugas de labels/secretos/base64, sin
  imports de runtime/producción).
- Suite completa en cierre: ver `tasks.md` (baseline `1506 passed`).

## 9. Coste de la investigación

- Harness `tools/visual_fidelity_vlm_judge_v2.py` (evaluation-only).
- `data/evaluations/visual-fidelity-vlm-judge-v2/*.json` (git-ignored).
- `openspec/changes/visual-fidelity-vlm-judge-v2/` (proposal/design/tasks/results).
- Commit de investigación: ver `tasks.md`. No merge, no push, no reindex.
