# Design: auto-mixed-visual-runtime

## Principio

AUTO/MIXED usan la preferencia editorial del LLM para elegir el medio de cada segmento, con fallback compatible, sin debilitar IMAGES_ONLY/VIDEOS_ONLY (constraints duras de usuario).

## Semántica que se conserva

| visualMode | allowedKinds | Fallback cross-media | Comportamiento |
|-----------|--------------|----------------------|----------------|
| IMAGES_ONLY | (IMAGE,) | No | Solo IMAGE. Sin regresión. |
| VIDEOS_ONLY | (VIDEO,) | No | Solo VIDEO. Sin regresión. |
| AUTO | (IMAGE, VIDEO) | Sí (compatible) | Preferencia editorial del LLM por segmento. |
| MIXED | (IMAGE, VIDEO) | Sí (compatible) | Misma autoridad editorial que AUTO + diversidad best-effort EITHER-only. |

- `EITHER` en AUTO/MIXED se resuelve con el orden determinista contractual (primer kind de `runtime_eligible`, hoy IMAGE por orden de `allowed_kinds`).
- Un kind `UNSUPPORTED` para la forma nunca entra como fallback (diagram/infographic/illustration/painting nunca reciben VIDEO).
- Un job MIXED que termina usando un solo medio es válido; no hay cuota 50/50 ni fallo por single-medium.

## Prompt mediaPreference

- Cada `visualSequence[]` DEBE emitir `mediaPreference` bajo AUTO/MIXED.
- Semántica editorial (el LLM decide SOLO el medio ideal, nunca provider/capabilityId/availability/API/fallback):
  - `VIDEO_PREFERRED`: movimiento real aporta información o engagement — acción, comportamiento, desplazamiento, interacción, animales, procesos visibles, paisajes dinámicos, B-roll.
  - `IMAGE_PREFERRED`: visual fijo comunica mejor — diagramas, mapas, documentos, fotos históricas, comparaciones estáticas, gráficos, ilustraciones.
  - `EITHER`: ambos medios funcionan de forma comparable.
- No existe matriz rígida visualIntent→mediaKind.
- Contexto según modo:
  - AUTO/MIXED: cada segmento DEBE emitir mediaPreference editorial.
  - IMAGES_ONLY: policy dura sigue imponiendo IMAGE.
  - VIDEOS_ONLY: policy dura sigue imponiendo VIDEO; se puede sugerir la preferencia coherente pero el runtime es autoridad.

## Guardia anti-ausencia

Distinguimos:

- A) LLM emitió explícitamente IMAGE_PREFERRED en todos → válido.
- B) LLM omitió mediaPreference (presencia ausente) y el canonicalizer aplicó el default histórico → bajo AUTO/MIXED provoca retry correctivo.

La detección se hace sobre la estructura raw del payload ANTES de canonicalizar (antes de que el default borre la información de presencia). Error estructurado: `MEDIA_PREFERENCE_MISSING`.

Este comportamiento es ESTRICTO durante la generación AUTO/MIXED (generación, retries y validación final): una generación final AUTO/MIXED sin `mediaPreference` se considera inválida y no se tolera silenciosamente — provoca retries correctivos y, agotados los intentos, termina en REVIEW_REQUIRED.

Compatibilidad histórica: planes persistidos sin mediaPreference continúan canonicalizando a IMAGE_PREFERRED cuando no se están regenerando. No se reescribe metadata histórica.

## Normas de implementación

### Prompt

- `SYSTEM_PROMPT_V2`: añadir `mediaPreference` a la tabla de `visualSequence[]` con la semántica editorial, y al JSON de ejemplo.
- `_build_user_prompt_v2` / retry: bloque request-scoped según `visualMode` (AUTO/MIXED exigen emisión; hard modes indican la preferencia coherente).
- `_validate_and_canonicalize_script_v2`: nueva señal `visual_mode`; en AUTO/MIXED, si el payload crudo contiene segmentos sin la clave `mediaPreference`, emitir error `MEDIA_PREFERENCE_MISSING` (provoca retry). Emitir el error SOLO una vez por script (si ya hubo reparación con recurrencia, se deja pasar para no bloquear convergencia: en el último intento se tolera).

### Query neutral para VIDEO

- `contracts/visual_terms.py`: `MEDIUM_MARKERS` (vocabulario reutilizado de GENERIC_FILLER + {video, videos, footage, clip, clips}) y `medium_neutral_query(query)` puro.
- Solo elimina markers de medio; NUNCA formas reales (diagram, infographic, illustration, map, document, painting, archive, …).
- Si tras neutralizar la query queda vacía/inválida, usar la ORIGINAL y dejar que los guards actuales decidan.
- `_derive_search_queries`: al construir `subject + assetPreference`, no añadir el sufijo cuando `assetPreference` es medium-only (`photograph`, `stock`).
- Aplicación en el adapter VIDEO (generic por media_kind, no por provider): `pexels_videos.search_pexels_videos` neutraliza la query antes de la llamada.

### queryUsed — autoridad

Para VIDEO, la query efectiva enviada a Pexels Video DEBE ser también el `queryUsed` persistido en `CandidateEnvelope` y el evaluado por el gate semántico. El VisualPlan original no se reescribe. IMAGE queda intacto.

### Router multi-kind

- `_route_segment` construye niveles de medio en vez de un único kind:
  - preferred kind = `decision.resolved_kind`
  - fallback kinds = (`allowed ∩ form_supported ∩ runtime_available`) - {preferred}, en orden determinista
  - ordered kinds = [preferred] + fallbacks
- Cada nivel produce candidates a partir de la matriz del assetPreference filtrada por kind (mismo flujo actual), aplicando gates/bloqueos y `_apply_source_policy` DENTRO del nivel (preserva order de `sourceProviders` dentro del mismo media level).
- Se concatena por nivel y se renumeran los `priority` de forma global. Media level domina sobre provider order.
- Ejemplo `sourceProviders=[wikimedia_commons,pixabay,pexels]`:
  - VIDEO_PREFERRED: 1. pexels.video.stock → 2. wikimedia IMAGE → 3. pixabay IMAGE → 4. pexels.photos.stock.
  - IMAGE_PREFERRED: 1. wikimedia IMAGE → 2. pixabay IMAGE → 3. pexels.photos.stock → 4. pexels.video.stock.
- Hard modes: un solo nivel (sin fallback cross-media).
- Un nivel vacío tras constraints se descarta; si todos vacíos → `UNROUTABLE` (sin cambios en semántica).
- `mediaDecision` + `fallbackKinds` se persisten en el segmento del sourcing plan.

### Executor / fallback runtime

- `providerCandidates` ya se procesan por `priority` → no hay lifecycle nuevo.
- Si el nivel preferido se agota (NO_RESULTS/DOWNLOAD_FAILED/PROVIDER_ERROR) y AUTO/MIXED permite otro kind, el executor continúa con los candidates fallback.
- `mediaFallback = true` cuando el asset resuelto tiene `mediaKind != mediaDecision.resolvedKind`.
- Reason explícito: `PREFERRED_MEDIA_EXHAUSTED`. No se reutiliza `MEDIA_PREFERENCE_UNAVAILABLE` (esa constante queda para degradación de estrategia cuando la capability NO estaba disponible; aquí la capability estaba AVAILABLE y lo ocurrido fue agotamiento de candidatos/runtime).
  - Distinción documentada:
    - strategy degradation = `mediaDecision.degradations` (calculada antes del sourcing, en el resolver puro).
    - runtime fallback = `mediaFallback` + `PREFERRED_MEDIA_EXHAUSTED` (detectada en ejecución).
- Resolved/unresolved preservan `mediaDecision` del segmento planificado.

### mediaDecision

Bloque aditivo por segmento (reusa `MediaStrategyDecision`):

```
mediaDecision = {
  visualMode, editorialPreference, allowedKinds, formSupportedKinds,
  runtimeAvailableKinds, resolvedKind, preferenceStatus, degradations,
  fallbackKinds
}
```

- `mediaDecision.resolvedKind` = kind elegido por la estrategia ANTES del sourcing.
- `segment.mediaKind` = kind REAL del asset finalmente seleccionado.
- Si difieren → `mediaFallback=true`.
- Propagación: router → executor → bridge → `metadata.assets[].segments[]`.
- Historical metadata: sin reescritura.

### MIXED best-effort

- MIXED añade SOLO diversity best-effort: en segmentos con `editorialPreference == EITHER`, preferir el kind menos usado según `mix_counts` reales de assets seleccionados.
- `mix_counts` (IMAGE/VIDEO) se actualiza SOLO tras un asset RESOLVED/SELECTED (no por routing, candidate attempt, provider attempt ni unresolved).
- Empate → orden determinista contractual actual.
- Preferencias fuertes (IMAGE_PREFERRED/VIDEO_PREFERRED) nunca se sobreescriben por diversity.
- Implementación: `mix_counts` se pasa como parámetro puro al router (`build_visual_sourcing_plan_v2(..., mix_counts=None)`); el fetcher mantiene el tracker entre escenas y lo actualiza tras cada escena con los mediaKind de los assets resueltos.

## Renderer

No se toca FFmpeg. El renderer ya soporta IMAGE/VIDEO por entrada y `build_render_timeline` ya propaga `mediaKind`/`mimeType`. Slice 1 solo garantiza que metadata/routing produce correctamente ambos kinds; el fixture mixto real queda en Slice 2.

## Implementación (Slice 1)

- `contracts/visual_terms.py`: `MEDIUM_MARKERS` + `medium_neutral_query`.
- `assets/providers/pexels_videos.py`: `search_pexels_videos` neutraliza la query y la usa como `queryUsed` efectivo (buscar y evaluar la misma intención).
- `assets/router.py`: `_resolve_segment_media_strategy` (devuelve la decisión completa), `_ordered_media_levels` (preferred → fallback, con tie-break EITHER-only bajo MIXED usando `mix_counts`), `_decision_to_dict`, niveles de candidatos con source policy por nivel, `MEDIUM_ONLY_ASSET_PREFS` (no añadir suffix photograph/stock), persistence de `mediaDecision` + `fallbackKinds` en el segmento.
- `assets/executor.py`: `PREFERRED_MEDIA_EXHAUSTED`, `_apply_media_decision_outcome` (mediaDecision + mediaFallback), mediaKind explícito en resolvers IMAGE, anotación de unresolved (incl. PROVIDER_UNAVAILABLE).
- `assets/fetcher.py`: `mix_counts` thread entre escenas; se actualiza SOLO tras assets resueltos.
- `assets/bridge.py`: `mediaDecision` / `mediaFallback` / `mediaFallbackReason` aditivos en `assets[].segments[]` (resolved, unresolved y missing).
- `script/generator.py`: semántica `mediaPreference` en system prompt + ejemplo; bloque por `visual_mode`; guardia `MEDIA_PREFERENCE_MISSING` sobre payload crudo solo en AUTO/MIXED; regla 8 de queries neutrales; retry correctivo.

Diferencia frente al Plan: el guard de ausencia se implementa en `_validate_and_canonicalize_script_v2` con `visual_mode` como parámetro (None en repairs), y el `queryUsed` efectivo se centraliza en el adapter de Pexels Video (búsqueda y evaluación usan la misma query neutralizada).
## Estado / Cierre

**COMPLETED / VERIFIED / CLOSED — pending authorized merge.**

Baseline `1809` → Slice 1 `1843` → final `1849 passed, 0 failed`; `git diff --check` limpio.

AUTO E2E `cmo-2026-08-20-152730` VALIDATED (8 IMAGE + 1 VIDEO; mediaDecision==mediaKind,
sin fallback). MIXED E2E `por-2026-08-20-153502` ASSETS_PARTIAL (9/10, mezcla editorial
5 IMAGE + 4 VIDEO; 1 ilustración sin cobertura supply). Mixed local smoke PASS
(IMAGE/VIDEO/IMAGE, 1080x1920, 19.08s). Ver `results.md`.
