# Propuesta: asset-semantic-relevance

## Problema actual

El pipeline visual v2 selecciona el primer asset que un provider devuelve y pasa a validación sin comprobar que el asset sea semánticamente relevante para la intención visual de la escena. Cuando el provider devuelve un resultado fuera de tema, el asset se persiste como `RESOLVED`/`PASS` aunque no tenga relación con el sujeto ni la consulta.

Regresión canónica (`los-2026-08-16-230341`):
- «YouTube logo image» → Volkswagen
- «YouTube comments section screenshot» → kiwi
- «famous early YouTubers photo» → flor
- «rainbow formation illustration» → bandera Pride no relacionada

Además, el pipeline no permite restringir a una lista explícita de providers manteniendo su orden (política de fuentes).

## Solución propuesta

Slice 1 (este cambio):

1. **Política de fuentes (source policy)**: el router soporta `request_visuals.sourceProviders` (lista explícita de providers). Sin lista → orden de fallback por defecto existente (matriz). Con lista → usa solo esos providers, conservando el orden de la lista.
2. **Contrato semántico de candidato genérico**: normalizar resultados de provider en campos `provider`, `queryUsed`, `title`, `description`, `tags/labels`, `assetType`, con adaptadores por provider. El scorer NO contiene ramas específicas de provider.
3. **Gate semántico**: tras la búsqueda de provider y ANTES de la descarga, comparar `queryUsed` (intención primaria) + `subjects` de la escena contra la metadata semántica del candidato. Devuelve `RELEVANT / IRRELEVANT / UNSCORABLE` + score + reasons + método.
4. **Preferir unresolved sobre irrelevante**: `IRRELEVANT`/`UNSCORABLE` → saltar candidato → siguiente candidato/consulta/provider según política → unresolved si se agota.
5. **Persistencia**: el assessment semántico se persiste en el asset seleccionado.

## Alcance

- Política de fuentes en router (`sourceProviders` en `request_visuals`)
- Adaptadores semánticos por provider (Wikimedia, Pixabay) → contrato genérico
- Scorer determinista puro (sin CLIP, embeddings ni LLM)
- Gate en executor tras búsqueda y antes de descarga
- Persistencia de `semanticAssessment` en assets via bridge
- Encaminar `request.visuals` desde `fetch_images_v2.py` al router

## Fuera de alcance

- Mejorar especificidad de script/VisualPlan (nombres, entidades, fechas, mejores queries) — cambio posterior separado
- Pexels y generación de imágenes (freeai/pollinations)
- Nuevas implementaciones reales de provider
- Llamadas HTTP reales, CLIP, embeddings, LLM/visión

## Criterios de éxito

1. Suite completa final: `0 failed, 0 skipped`
2. Tests focales: rejects de regresión (Volkswagen, kiwi, flor, Pride) y controles positivos (YouTube, rainbow, prism)
3. `git diff --check` limpio
4. Scorer puro determinista y provider-agnostic (tests lo aseguran)
5. Sin secretos en outputs/logs

## Cierre (2026-08-17)

Estado: **COMPLETED / VERIFIED / CLOSED**, mergeado a `main` sin squash.

### Alcance final entregado

Slice 1 (gate + fuente) y hardening v2:

1. **Política de fuentes (source policy)**: `request_visuals.sourceProviders` (lista explícita, orden preservado; sin lista → fallback por defecto de la matriz). Superficie CLI: `bin/run_job.py --asset-providers wikimedia_commons,pixabay`, persistido en `request.visuals.sourceProviders` por la etapa script y encaminado al router por `fetch_images_v2.py`.
2. **Contrato semántico de candidato genérico**: adaptadores por provider (Wikimedia, Pixabay) → campos `provider`, `queryUsed`, `title`, `description`, `tags/labels`, `assetType`; el scorer NO contiene ramas de provider.
3. **Gate semántico**: tras la búsqueda y ANTES de la descarga, en `_resolve_wikimedia` y `_resolve_pixabay`; `IRRELEVANT`/`UNSCORABLE` → saltar candidato → next candidato/consulta/provider → `NO_RESULTS` con `semanticRejections` si se agota.
4. **Postcondición genérica en executor**: un `RESOLVED` de provider search-strategy sin `semanticAssessment.verdict == RELEVANT` NUNCA entra en `resolvedAssets` (downgrade a `PROVIDER_ERROR` + warning `SEMANTIC_POSTCONDITION:RESOLVED`). Sin ramas por nombre de provider; se decide por `queryStrategy`.
5. **Scorer determinista v2 (anchor-aware)**: `deterministic_anchor_coverage_v2` reemplaza a `token_overlap_v1`. `queryUsed` es la intención primaria; los términos se clasifican en anchors discriminativos vs tokens débiles/soporte. Los débiles por sí solos NUNCA producen `RELEVANT`. Con múltiples anchors se exige cobertura significativa (≥ mitad, mínimo 2). Los `subjects` de la escena NO pueden rescatar la falta de anchor del query. Diagnóstico persistido: `anchorTerms`, `matchedAnchors`, `weakMatches`, `anchorCoverage`.
6. **Persistencia**: `semanticAssessment` en el asset seleccionado via bridge.

### Evidencia de validación

- Suite completa final: **`1345 passed, 0 failed, 0 skipped`**.
- Replay real sobre `los-2026-08-16-230341`:
  - V1 (token_overlap): **11/11 resuelto** con assets severamente irrelevantes (Volkswagen, campanula/plum blossom, kiwi, flower/screenshot, coast).
  - V2 (anchor_coverage): **3 resuelto / 8 fallido, `ASSETS_PARTIAL`** (`los-semantic-v2-20260817-203235`). Los 3 aceptados son relevantes a YouTube (shorts, icon app mobile, iphone smartphone). Los falsos positivos obvios (Volkswagen, kiwi, flor, coast) quedan rechazados.
- `git diff --check` limpio.

### Limitaciones conocidas

La completitud de metadata del provider + el scorer por anchors garantiza relevancia gruesa (tema/entidad), NO fidelidad temporal/editorial/de contenido de imagen. Siguiente prioridad: especificidad de script + VisualPlan/query. La detección de near-duplicates visuales queda como trabajo futuro.