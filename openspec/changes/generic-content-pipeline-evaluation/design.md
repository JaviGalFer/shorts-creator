# Diseño: generic-content-pipeline-evaluation

## Arquitectura del harness

```
tools/genericity_matrix.py   (nuevo, puro/offline)
  ├─ importable: build_job_metrics(metadata: dict) -> dict
  ├─ CLI:        python3 tools/genericity_matrix.py <metadata1> [metadata2 ...]
  │                -> imprime: JSON resumen + tabla humana compacta
  └─ NO red / NO LLM / NO provider calls / NO mutación de metadata
```

La herramienta depende `únicamente` de:

- `contracts/visual_specificity.assess_query_specificity` (reutilizado tal cual, para los conteos VALID/VAGUE de queries persistentes).
- Lectura directa de los campos del metadata JSON persistido por el pipeline (`request`, `script.scenes[].visualPlan`, `assets[]`, `_visualAssetBridgeV2`, `status`, `durationContract`).

No importa nada de `script/`, `assets/` (executor/router/bridge) ni `providers/`, y no ejecuta ninguna búsqueda.

## Campos extraídos

### JOB
- `jobId`
- `topic`
- `status`
- `sceneCount` (len de `script.scenes`)
- `bootstrapDurationContractStatus` (de `durationContract.status`) — **solo telemetría**

### VISUAL PLAN
- `totalSceneSearchQueries` (suma de len `visualPlan.searchQueries` por escena)
- `totalSegmentSearchQueries` (suma de segmentos con `visualSequence[].searchQuery` no nulo)
- `specificityValid` / `specificityVague` (conteo por query persistida usando `assess_query_specificity`)
- `totalSegments` (suma de len `visualSequence` por escena)
- `assetPreferencesDistribution` (Counter sobre `visualPlan.assetPreferences` y `visualSequence[].assetPreference`)

### ASSETS
- `resolved` (len de `assets[].segments[]` con `segmentValidationStatus == "PASS"` / result exitoso)
- `unresolvedOrFailed` (resto de segmentos)
- `resolutionRatio` (resolved / total segundos contados, o null si 0)
- `providerDistribution` (Counter sobre provider resuelto)
- `queryUsedForResolved` (lista de `queryUsed`)
- `semanticAssessments` (lista de `semanticAssessment` persistido: `verdict`, `matchedAnchors`, `anchorTerms`) donde exista
- `executorStatusCounts` / `resolvedSegmentReason` (distribución de `_executorStatus` y `error`/`reason` persistido)

Nota: los campos manuales (coherencia de guion, alucinación, calidad query/intent, falso positivo de imagen, coarse-but-usable) NO se derivan automáticamente; quedan para la revisión manual de Fase 2.

## Regla de conteo de assets

Se recorre `metadata["assets"]` (array por escena, cada uno con `segments[]`). Cada segmento persistido por el bridge v2 tiene un `segmentValidationStatus` (`PASS`/`FAIL`) y campos opcionales `_executorStatus`, `error`, `provider`, `queryUsed`, `semanticAssessment`.

- `resolved` = segmentos con `segmentValidationStatus == "PASS"`.
- `unresolvedOrFailed` = segmentos con `segmentValidationStatus == "FAIL"` (incluye `_executorStatus` `UNRESOLVED`, `NO_RESULTS`, `DOWNLOAD_FAILED`, `PROVIDER_ERROR`, `PROVIDER_UNAVAILABLE`, y el sintético "no executor result").
- Si `assets` está ausente o vacío, `resolved=0`, `unresolvedOrFailed=0`, `resolutionRatio=null`, y se señala `noAssets=true`.

La herramienta NUNCA infiere la causa de un unresolved no distinguible: si el metadata persistido no contiene evidencia de `semanticRejections`/causa, la causa queda como `UNRESOLVED_CAUSE_UNCERTAIN` (ver clasificación), sin sondeo de provider.

## Bootstrap duration (telemetría)

`durationContract.status` (`PASS`/`FAIL`) se expone como `bootstrapDurationContractStatus` para que la revisión manual lo pueda ver, pero el harness NO emite ninguna clasificación de genericity ni alerta basada en él. Un `FAIL` bootstrap por sí solo no clasifica un tema como fallo de genericity.

## Clasificación (contrato)

Grupos de fallo (pagados al análisis de Fase 2, no por la herramienta):

- **CORE:** `QUERY_GEN_FAILURE`, `VISUAL_PLAN_FAILURE`, `SEMANTIC_GATE_FALSE_POSITIVE`
- **SUPPLY / COVERAGE:** `PROVIDER_COVERAGE_FAILURE`, `UNRESOLVED_CAUSE_UNCERTAIN`, `ACCEPTABLE_ASSETS_PARTIAL`

Por tema:

- **HEALTHY** — guion/VisualPlan coherente; queries concretas y apropiadas; sin falsos positivos obvios en revisión manual; unresolved/ASSETS_PARTIAL permitidos.
- **USABLE_WITH_LIMITATIONS** — el core script/VisualPlan sigue siendo genérico y útil; gaps notables de cobertura de provider o un pequeño número de assets coarse; sin corrupción sistémica del intent.
- **SYSTEMIC_FAILURE** — el script/VisualPlan malentendido repetido del tema, O muchos assets aceptados claramente fuera de tema, O el mismo fallo CORE hace inusable la familia de temas.

Agregado:

- **GREEN:** ≥6/8 HEALTHY o USABLE_WITH_LIMITATIONS; sin fallo CORE repetido en dominios no relacionados; coverage de provider solo no bloquea GREEN.
- **YELLOW:** fallo CORE repetido en ≥2 dominios no relacionados, O coverage de provider suficientemente pobre en varios dominios como para justificar investigar estrategia de provider (sin cambiar la arquitectura semántica).
- **RED:** múltiples familias de temas no relacionadas con fallos CORE sistémicos → investigar arquitectura/contratos antes de features.

## Propiedad de módulos / sin acoplamiento

- La herramienta vive en `tools/`, separada del runtime. No se importa desde `src/`.
- Reutiliza solamente el guard puro `contracts/visual_specificity.assess_query_specificity` (hoja, sin I/O). No modifica ningún módulo de dominio.
- No se tocan `script/`, `assets/`, `contracts/visual.py`, `contracts/visual_terms.py`, `semantic.py`, `router.py`, `executor.py`, `providers/`, `bin/`.

## Fases

1. **Fase 1 (este change):** matriz + contrato + herramienta offline + test focal + corrección de docs. Sin ejecución real de 8 temas.
2. **Fase 2 (futura):** ejecutar los 8 temas con

   ```
   python bin/run_job.py --topic "<TOPIC>" --duration-preset quick_30 \
     --asset-providers wikimedia_commons,pixabay --stop-after assets
   ```

   y pasar cada `metadata.json` a `tools/genericity_matrix.py`; análisis manual (coherencia, alucinación, calidad query/intent, falsos positivos, coarse) + agregado + decisión GREEN/YELLOW/RED.

## Cierre (criterios de éxito Fase 1)

- Herramienta y test verde con fixtures sintéticos.
- `git diff --check` limpio.
- Sin diff en `src/`; sin cambios de comportamiento en `bin/`.
- Docs actualizados: `agent-context` (main base `b7b8d57`, `script-visual-specificity` CLOSED, `asset-entity-fidelity` PAUSED, active evaluation `generic-content-pipeline-evaluation`), `current-state` (sin "script specificity" como siguiente prioridad).

## Cierre final (Fase 2 + revisión visual) — COMPLETADO / VERIFICADO / CLOSED

- 8/8 jobs `ASSETS_PARTIAL` (script attempt 1, retries 0, 0 queries VAGUE), sin fallo de infraestructura. Contact sheets generados en `data/evaluations/genericity-phase2-visual-review/` (evidencia, git-ignored).
- Revisión visual de píxeles externa: 38 resueltos → 16 CR / 14 CU / 8 FP. Per-topic: Volcán HEALTHY; Aurora, Porsche, Spring Boot, Pulpos, Videojuegos, Hipoteca USABLE_WITH_LIMITATIONS; Roma SYSTEMIC_FAILURE (solo capa de assets).
- Agregado: **YELLOW**. Arquitectura core genérica y sana (sin `QUERY_GEN_FAILURE` ni `VISUAL_PLAN_FAILURE`); fallo CORE repetido en la aceptación downstream (fidelidad visual/semántica) en dominios no relacionados; cobertura de provider limitada = SUPPLY.
- Conclusión de diseño: `asset-entity-fidelity` sigue siendo evidencia de investigación SOLO. Futuro cambio registrado: **`asset-visual-semantic-fidelity`** (segunda etapa de validación semántico-visual por píxeles, provider-agnostic, manteniendo el gate de metadata como primera etapa). `deterministic_anchor_coverage_v3` / `FORM_OR_MEDIUM_TERMS` NO es la dirección aprobada. Dirección de producto separada registrada: fallback search-vs-generation.
- Evidencia completa: `phase2-report.md`.
