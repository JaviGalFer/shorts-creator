# Tasks: asset-semantic-relevance

- [x] Crear `src/shorts_creator/assets/semantic.py` (contrato + adaptadores + scorer puro)
- [x] Scorer determinista: `RELEVANT / IRRELEVANT / UNSCORABLE` + score + matchedEvidence + method
- [x] Adaptadores por provider (wikimedia_commons, pixabay) → contrato genérico; scorer sin ramas provider
- [x] Router: soporte `sourceProviders` en `_validate_request_config` y `DEFAULT_REQUEST_VISUALS`
- [x] Router: `_apply_source_policy` (filtrar + ordenar lista explícita, `UNROUTABLE` si 0)
- [x] Router: añadir `subjects` al segmento enrutado
- [x] Executor: `_evaluate_semantic` y gate antes de download en `_resolve_wikimedia`
- [x] Executor: gate antes de download en `_resolve_pixabay`
- [x] Executor: persistir `semanticAssessment` en resolved asset; rechazos → siguiente candidato/consulta/provider → `NO_RESULTS`
- [x] Bridge: propagar `semanticAssessment` en `_map_resolved_asset`
- [x] Fetcher: leer `metadata["request"]["visuals"]` y pasarlo al router
- [x] Tests focales: rejects regresión (Volkswagen, kiwi, flor, Pride) y controles positivos (YouTube, rainbow, prism)
- [x] Suite completa final: `0 failed, 0 skipped`
- [x] `git diff --check` sin salida