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
- [x] CLI `--asset-providers` (run_job → generate_script → `request.visuals.sourceProviders`; omitido → fallback por defecto)
- [x] Postcondición genérica: `RESOLVED` search-strategy sin `verdict == RELEVANT` nunca entra en `resolvedAssets`
- [x] Scorer v2 `deterministic_anchor_coverage_v2`: anchors discriminativos vs weak terms; weak por sí solos nunca `RELEVANT`; múltiples anchors exigen cobertura significativa; `subjects` no rescatan el query
- [x] Fixtures del replay real (11 candidatos Pixabay del cache local) y diagnóstico `anchorTerms/matchedAnchors/weakMatches/anchorCoverage`
- [x] Replay real `los-semantic-v2-20260817-203235`: 3 resuelto / 8 fallido, `ASSETS_PARTIAL` (V1 era 11/11 irrelevante)
- [x] Suite completa final: `1345 passed, 0 failed, 0 skipped`
- [x] `git diff --check` sin salida

Estado: **COMPLETED / VERIFIED / CLOSED** — mergeado a `main` sin squash.