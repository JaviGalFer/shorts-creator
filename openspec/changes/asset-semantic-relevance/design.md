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

## Scorer determinista

Función pura `score_semantic_relevance(expected, candidate)`.

- `expected = {"query": queryUsed, "subjects": [...]}`
- `candidate` = contrato semántico normalizado.
- Tokenización: minúsculas, alfanuméricos, longitud >= 3, excluyendo relleno genérico (`image`, `photo`, `stock`, ...).
- Evidencia del candidato = `title ∪ description ∪ tags ∪ labels` (excluye `assetType` y `queryUsed`).

Regla conservadora (justificada por fixtures):

| Caso | Condición | Verdict |
|------|-----------|---------|
| Sin tokens sustantivos en evidencia del candidato | metadata ausente o solo relleno | `UNSCORABLE` |
| Sin tokens sustantivos en expected | consulta+subjects vacíos/genéricos | `UNSCORABLE` |
| Sin token sustantivo compartido | evidencia presente, 0 overlap | `IRRELEVANT` |
| ≥ 1 token sustantivo compartido | overlap → provee discriminant | `RELEVANT` |

Score:
- `RELEVANT`: `60 + min(40, round(40 * overlap_ratio))` con `overlap_ratio = |shared_substantive| / |expected_substantive|` → rango 60–100.
- `IRRELEVANT`: `0`.
- `UNSCORABLE`: `None`.

`method = "deterministic_token_overlap_v1"`. `matchedEvidence` = tokens sustantivos compartidos ordenados. `reasons` = lista legible.

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

Cuando se agotan todos los candidatos rechazados semánticamente → `NO_RESULTS` con razón que menciona rechazo semántico (preferir unresolved sobre irrelevante).

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