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

## Slices futuros (NO en este change)

- **Slice 2 (futuro):** benchmark de codificadores locales — SOLO CLIP `ViT-B/32` y SigLIP `base-patch16-224`; CPU-first, GPU opcional; métricas sobre los 38 assets; decisión 4 GB VRAM / CPU medida (no asumida). Requiere instalar dependencias ML y descargar pesos (fuera de Slice 1).
- **Slice 3 (futuro):** benchmark de API multimodal (OpenAI actual), contrato estructurado ACCEPT/REJECT, coste medido. Decisión B/C/D/E.
- **Integración en runtime** (si el benchmark aprueba): `executor.py` post-descarga, antes del return RESOLVED; gate de metadata se mantiene como primera etapa. Solo si el benchmark lo justifica.
