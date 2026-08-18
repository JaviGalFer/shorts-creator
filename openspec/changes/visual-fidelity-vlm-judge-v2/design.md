# Design: visual-fidelity-vlm-judge-v2

**Status: EN PROGRESO** — investigación benchmark-first, sin cambios de runtime.
Ver `results.md` para el informe y `tasks.md` para la ejecución.

## Arquitectura de evaluación (sin cambios de runtime)

```
tests/fixtures/asset_visual_fidelity/labels.json          ← 38 canónicos (NO tocados)
tests/fixtures/asset_visual_fidelity/holdout_labels.json  ← 20 development (NO tocados)
        │
        ▼
tools/visual_fidelity_vlm_judge_v2.py  ← evaluation-only, lazy-import openai
        │   model gpt-5.6-luna · Responses API · 1 request independiente por asset
        │   detalle high · reasoning none · sin tools · Structured Output estricto
        ▼
data/evaluations/visual-fidelity-vlm-judge-v2/*.json  ← git-ignored
        │
        ▼
tools/visual_fidelity_benchmark.py  ← REUTILIZADO (metrics); UNCERTAIN ⇒ ACCEPT via
        │   judge_v2_operational_metrics (ver abajo)
        ▼
openspec/changes/visual-fidelity-vlm-judge-v2/results.md  ← informe
```

## Judge V2 — contrato exacto

### Input (por request)

- `model = gpt-5.6-luna`
- `instructions`: instrucciones del judge (ver contracto de `JUDGE_INSTRUCTIONS`)
- `input` (usuario único): `input_text` con el input semántico + `input_image`
  con la imagen (`detail=high`), GIF ⇒ frame 0 (sin mutar el archivo)
- `reasoning = {effort: "none"}`
- `max_output_tokens` (implícito en el cap)
- `text.format = {type: json_schema, name: "visual_fidelity_verdict_v2",
  strict: true, schema}`
- SIN web/tools, SIN `humanLabel`, SIN scores/verdicts de otros modelos, SIN
  expected verdict.

Input semántico textual:

```
Visual intent: {queryUsed}
Asset preference: {assetPreference}   # SOLO si está en el contrato del segmento
```

`assetPreference` se resuelve desde el contrato persistido del job
(`data/videos/<jobId>/metadata.json` ⇒
`script.scenes[sceneNumber-1].visualPlan.visualSequence[segmentIndex-1].assetPreference`),
unido por `(jobId, sceneNumber, segmentIndex)`. Si el segmento/fixture no lo
tiene, NO se envía (nunca se inventa).

### Output estructurado

```json
{
  "verdict": "ACCEPT" | "REJECT" | "UNCERTAIN",
  "reasonCode": "<enum cerrado>",
  "shortReason": "<texto breve ≤ 180 chars>"
}
```

- `REASON_CODES`: `MATCH`, `WRONG_ENTITY`, `WRONG_VARIANT_OR_ERA`,
  `WRONG_ACTION_OR_SCENE`, `WRONG_CONTENT_TYPE`, `MISSING_ESSENTIAL_RELATION`,
  `FACTUAL_CONTRADICTION`, `IRRELEVANT`, `INSUFFICIENT_VISUAL_EVIDENCE`
  (ver mapping REJECT/UNCERTAIN abajo).
- `shortReason` máx. 180 caracteres, texto legible (no afecta métricas).

### Semántica

- **ACCEPT**: la imagen representa suficientemente el sujeto/intención
  principal, aunque sea aproximada, genérica o no incluya detalles secundarios
  (COARSE_BUT_USABLE debe poder pasar).
- **REJECT SOLO si existe mismatch material**: entidad/variante central
  incorrecta; contradicción factual visible; acción/relación esencial ausente y
  la imagen resulta engañosa; tipo de contenido solicitado sustituido por algo
  semánticamente distinto; imagen esencialmente ajena al concepto.
- **UNCERTAIN**: sin evidencia visual suficiente para afirmar un mismatch
  material.
- Métrica operativa: **UNCERTAIN ⇒ ACCEPT** (fail-open para proteger retención).

### Validación y resiliencia

- `parse_judge_output`: valida set exacto de claves, `verdict` en enum y
  `reasonCode` coherente con verdict:
  - `ACCEPT` ⇒ reasonCode ∈ ACCEPT_CODES + INSUFFICIENT_VISUAL_EVIDENCE
  - `REJECT` ⇒ reasonCode ∈ REJECT_CODES
  - `UNCERTAIN` ⇒ reasonCode == `INSUFFICIENT_VISUAL_EVIDENCE`
- Errores por asset independientes: se registran (`status=ERROR`,
  `errorType`, `error` truncado a 500) y no abortan la fase.
- Nunca levanta con excepción del modelo; fail-fast solo para
  configuración/preflight/coste.
- No se persiste API key ni base64; solo SHA-256 fingerprint no secreto.

## Coste

- Pricing de referencia del benchmark API previo (Slice 3A,
  `PRICING_REFERENCE_DATE=2026-08-18`):
  - input `$0.20/M`, cached input `$0.02/M`, output `$1.20/M`
- Preflight: `client.responses.input_tokens.count` por request +
  `requestFingerprint`; proyección con `max_output_tokens` y pricing de
  referencia.
- Hard cap **`$0.10`** total (canonical 38 + development 20 = 58 assets).
  Si `projectedMaxTotalCostUsd > 0.10` ⇒ `COST_BUDGET_EXCEEDED`, no ejecutar.
  Durante ejecución, si el coste real acumulado supera el cap, abortar.
- Persistir por request: `inputTokens`, `cachedInputTokens`, `outputTokens`,
  `reasoningTokens`, `costUsd`, `latencySeconds`. Reporte con `totalCostUsd`,
  `averageCostUsd`.

## Métricas

- `tools/visual_fidelity_benchmark.py` (REUTILIZADO, sin tocar): `evaluate_verdicts`
  sobre verdicts operativos (UNCERTAIN ⇒ ACCEPT) y confusion matrix.
- Adicionalmente el harness reporta: distribución raw de
  ACCEPT/REJECT/UNCERTAIN, `uncertainOperationalized` (cuántos UNCERTAIN
  pasaron a ACCEPT), latencia mediana/p95, per-asset rows.
- Banderas de decisión (solo investigación):
  - canonical: `retained >= 24/30` Y `badRejected >= 6/8`
  - development-20: `usableRetained >= 11/13` Y `badRejected >= 4/7`

## Tabla de razón de motivo (mapping)

| reasonCode | verdict(es) permitidos |
|---|---|
| `MATCH` | ACCEPT |
| `WRONG_ENTITY` | REJECT |
| `WRONG_VARIANT_OR_ERA` | REJECT |
| `WRONG_ACTION_OR_SCENE` | REJECT |
| `WRONG_CONTENT_TYPE` | REJECT |
| `MISSING_ESSENTIAL_RELATION` | REJECT |
| `FACTUAL_CONTRADICTION` | REJECT |
| `IRRELEVANT` | REJECT |
| `INSUFFICIENT_VISUAL_EVIDENCE` | ACCEPT, REJECT, UNCERTAIN |

`INSUFFICIENT_VISUAL_EVIDENCE` es un reasonCode descriptivo y NO gatea el
verdict: se permite con cualquiera de los tres (p. ej. el modelo puede rechazar
un GIF ambiguo citando evidencia insuficiente). Las métricas operativas usan
solo `verdict`; el reasonCode documenta el motivo.

## Fuera de alcance

- NO tocar: `visual_fidelity.py`, `executor.py`, `bridge.py`, OpenCLIP
  threshold, BLIP runtime, providers, prompts del generador.
- NO integrar nada en runtime; el siguiente paso, si el candidate es PROMISING,
  sería un holdout REALMENTE nuevo con nuevos E2E.
- No merge, no push, no reindex.