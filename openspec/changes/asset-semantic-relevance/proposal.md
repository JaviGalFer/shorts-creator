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

## Riesgos

- Bajo: cambios acotados a `assets/` (source_policy, semantic, router, executor, bridge, fetcher)
- El gate es conservador; puede producir más `UNRESOLVED` cuando el provider no devuelve metadata semántica (preferido sobre asset irrelevante)