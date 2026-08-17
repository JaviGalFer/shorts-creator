# Diseño: asset-semantic-relevance

## Arquitectura

```
request.visuals (metadata)
  └─ sourceProviders, preferredProviders, ... → router  (política de fuentes)

router.py
  ├─ _validate_request_config  (+sourceProviders)
  ├─ _route_segment       (+subjects en el segmento, source policy)
  └─ _apply_source_policy (nuevo)

semantic.py (NUEVO, puro, stdlib)
  ├─ to_semantic_candidate(native)  → contrato genérico  (adaptadores por provider)
  └─ score_semantic_relevance(expected, candidate) → {verdict, score, reasons, matchedEvidence, method}

executor.py
  ├─ _evaluate_semantic(segment, native_candidate)   (nuevo)
  ├─ gate en _resolve_wikimedia antes de download
  ├─ gate en _resolve_pixabay antes de download
  └─ semanticAssessment persistido en resolved asset

bridge.py
  └─ _map_resolved_asset  (+semanticAssessment)

fetch_images_v2.py
  └─ leer metadata["request"]["visuals"] y pasarlo al router
```

## Contrato semántico de candidato

Normalizado por adaptador:

```python
{
  "provider": str,
  "queryUsed": str,
  "title": str,
  "description": str,
  "tags": list[str],
  "labels": list[str],
  "assetType": str,
}
```

Adaptadores (registrados en `PROVIDER_ADAPTERS`; el scorer no conoce providers):
- `wikimedia_commons`: `title` = ImageDescription, `labels` extraídos del nombre de archivo.
- `pixabay`: `tags` (string separado por comas) → `tags` list.
- genérico: lee campos genéricos cuando existan (`title`, `description`, `tags`, `labels`, `keywords`, `categories`, `assetType`/`imageType`/`mimeType`).

## Scorer determinista v2 (anchor-aware)

Función pura `score_semantic_relevance(expected, candidate)` / `assess_candidate(expected, native_candidate)`.

- `expected = {"query": queryUsed, "subjects": [...]}` — `queryUsed` es la intención primaria.
- `candidate` = contrato semántico normalizado.
- Tokenización: minúsculas, alfanuméricos, longitud >= 3, excluyendo relleno genérico (`image`, `photo`, `stock`, ...).
- Evidencia del candidato = `title ∪ description ∪ tags ∪ labels` (excluye `assetType` y `queryUsed`).

Clasificación de términos del query:

- **Anchors discriminativos** = términos del query que no están en `WEAK_SUPPORT_TERMS` (p. ej. `youtube`, `comments`, `youtubers`, `rainbow`).
- **Términos débiles/soporte** (`WEAK_SUPPORT_TERMS`) = temporales/de popularidad/presentación/contexto de plataforma (`early`, `famous`, `future`, `popular`, `viral`, `logo`, `screenshot`, `section`, `media`, `social`, `video`, `culture`, ...). Son visibles en `weakMatches` para diagnóstico pero NUNCA establecen relevancia.

Regla conservadora (justificada por fixtures del replay real):

| Caso | Condición | Verdict |
|------|-----------|---------|
| Sin tokens sustantivos en evidencia del candidato | metadata ausente o solo relleno | `UNSCORABLE` |
| Sin anchors en el query | query sin términos discriminativos | `UNSCORABLE` |
| Cobertura de anchors insuficiente | `|matched_anchors| < required` | `IRRELEVANT` |
| Cobertura de anchors suficiente | `required` = 1 (anchor único) o `max(2, ceil(n/2))` (múltiples) | `RELEVANT` |

- Los `subjects` de la escena NO forman parte de la decisión de relevancia: describen la escena pero no rescatan un query sin anchor.
- Los `weakMatches` por sí solos nunca producen `RELEVANT` (los falsos positivos del replay eran matchs débiles: `logo`, `early`, `section`, `screenshot`, `popular`).

Score:
- `RELEVANT`: `60 + min(40, round(40 * anchor_coverage))` con `anchor_coverage = |matched_anchors| / |anchor_terms|` → rango 60–100.
- `IRRELEVANT`: `0`. `UNSCORABLE`: `None`.

`method = "deterministic_anchor_coverage_v2"`. Diagnóstico persistido en el assessment:
`anchorTerms`, `matchedAnchors`, `weakMatches`, `anchorCoverage`, `matchedEvidence` (= anchors), `reasons`.

## Gate en executor

Tras la búsqueda y antes de la descarga:

```
candidate_native = provider.search(...)
semantic = _evaluate_semantic(segment, candidate_native)
if semantic.verdict != "RELEVANT":
    semantic_rejections.append(semantic)
    add URLs a excluded_* sets   # no reconsiderar
    continue                     # siguiente candidato/consulta/provider
download(...)
if ok: resolved["semanticAssessment"] = semantic
```

Cuando se agotan todos los candidatos rechazados semánticamente → `NO_RESULTS` con `semanticRejections` (preferir unresolved sobre irrelevante).

### Postcondición de resolución (search-strategy)

Posteriormente a los gates por provider, el executor aplica un invariante genérico en el punto de recolección (`_search_semantic_ok(resolved, strategy)`):

- Estrategia `search` → el resultado `RESOLVED` DEBE llevar `semanticAssessment.verdict == RELEVANT`; si no, NUNCA entra en `resolvedAssets` (downgrade a `PROVIDER_ERROR` + warning `SEMANTIC_POSTCONDITION:RESOLVED`).
- Estrategia `generation` (prompt) → se permite sin assessment token-overlap.
- No hay ramas por nombre de provider; decide únicamente `queryStrategy` del candidato.

## Política de fuentes

En router, tras restricciones de request y antes de policy de prioridad:

```python
source_providers = request_visuals.get("sourceProviders") or []
if source_providers:
    candidates, excluded = _apply_source_policy(candidates, excluded, source_providers)
else:
    candidates = _apply_priority_policy(...)  # orden/fallback por defecto actual
```

`_apply_source_policy`: mantiene solo providers en la lista, los ordena por posición de la lista, renumera `priority`, y añade a `excludedProviders` con razón `"not in explicit source policy"`. Si la lista deja 0 candidatos → `routingStatus = UNROUTABLE`.

### Superficie CLI para sourceProviders

`bin/run_job.py --asset-providers wikimedia_commons,pixabay` → `orchestrator.run_pipeline(asset_providers=...)` → `build_script_command` añade `--asset-providers` → `bin/generate_script.py` divide en lista y llama a `generate_script(source_providers=...)`, que persiste `request.visuals.sourceProviders` en orden. `fetch_images_v2.py` lee `metadata["request"]["visuals"]` y lo pasa al router. Omitido → sin campo → fallback por defecto. Sin variables de entorno nuevas, sin providers nuevos.

## Router: subjects en segmento

`_route_segment` añade `subjects = list(canonical_plan.subjects)` al segmento (campo opcional) para que el executor pueda usarlas como semántica esperada complementaria.

## Config de request

`DEFAULT_REQUEST_VISUALS["sourceProviders"] = []`. `_validate_request_config` valida `sourceProviders` contra `ALLOWED_PROVIDERS` (semántica igual a `preferredProviders`/`blockedProviders`).

## Secretos

Ningún cambio introduce secretos. `provider_credentials` sigue sin copiarse al resultado. El scorer solo manipula metadata textual normalizada.

## Fases de implementación

1. `semantic.py` (contrato + adaptadores + scorer).
2. Router: `sourceProviders` + subjects + `_apply_source_policy`.
3. Executor: `_evaluate_semantic` + gates wikimedia/pixabay + persistir assessment.
4. Bridge: propagar `semanticAssessment`.
5. Fetcher: encaminar `request.visuals` al router.
6. Tests focales + suite completa.
7. CLI `--asset-providers` → `request.visuals.sourceProviders` (run_job → orquestador → generate_script).
8. Postcondición `_search_semantic_ok` en recolector del executor.
9. Hardening scorer v2 (anchor-coverage) con fixtures del replay real + suite completa `1345 passed`.