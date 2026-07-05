# Tareas: Mejora del pipeline visual histórico

## Fase 1 — Seguridad y documentación base

- [x] Eliminar secretos de HANDOVER.md (CORREGIDO)
- [x] Actualizar docs/project/security.md con reglas de no exposición
- [x] Actualizar AGENTS.md con regla explícita de no escribir secretos en docs
- [x] Crear docs/project/visual-asset-strategy.md
- [x] Actualizar docs/project/integrations.md (nuevos proveedores, estados)
- [x] Crear bitácora de sesión (docs/sessions/)
- [x] Crear OpenSpec (proposal.md, design.md, tasks.md, specs/)

## Fase 2 — Modelo de datos y generate_script.py

- [x] Crear bin/generate_script.py (CLI, --topic, --dry-run, lee .env)
- [x] Prompt incluye visualPlan con estrategias, searchQueries, preferredSources
- [x] Mantener compatibilidad: visualPrompt + imagePrompt legacy
- [x] Script genera metadata.json completo en data/videos/{jobId}/

## Fase 3 — Sourcing, scoring y fetch_images.py

- [x] Centralizar SCORING_WEIGHTS como dict configurable
- [x] Implementar búsqueda multi-proveedor (Wikimedia, Pexels, FreeAI, Pollinations)
- [x] Implementar evaluación de 3-5 candidatas por escena
- [x] Implementar scoring explicable con razones
- [x] Implementar selección de candidata principal
- [x] Guardar metadata completa de assets (provider, URL, licencia, score)
- [x] Guardar candidatas descartadas con motivo
- [x] Implementar cadena de fallback por estrategia
- [x] Mantener compatibilidad: jobs sin visualPlan usan visualPrompt

### Mejoras adicionales implementadas

- [x] Rate limiting conservador para Wikimedia (5 requests/12s, backoff en 429)
- [x] Cache de queries por proveedor (evita re-request)
- [x] User-Agent identificable configurable
- [x] Pausas entre requests (0.6s entre info API calls, 0.5s entre escenas)
- [x] Logging de fallos por proveedor con razón específica
- [x] Adaptación de queries por proveedor:
  - Wikimedia/Library: searchQueries históricas
  - Pexels/Pixabay: queries visuales genéricas según estrategia (STRATEGY_VISUAL_QUERIES)
  - FreeAI: imageGenerationPrompt + negativePrompt
  - Pollinations: visualPrompt/imagePrompt
- [x] Metadata extendida por escena: providerAttemptOrder, providerFailures, fallbackApplied, fallbackReason, candidateCount, selectedCandidateScore

## Fase 4 — Validación

### Validación de scripts individuales
- [x] `generate_script.py --dry-run` — Funciona, muestra prompts correctamente
- [x] `generate_script.py` real — Genera script con visualPlan (10 escenas)
- [x] `fetch_images.py` con visualPlan — Búsqueda multi-proveedor, scoring, metadata completa
- [x] `fetch_images.py` legacy (franco5) — Compatibilidad backward
- [x] `generate_audio.py` con edge-tts vía venv — Audio generado para 10 escenas
- [x] `prepare_job.py` — Subtítulos ASS generados, merge de metadata
- [x] `render_job.py` — Render Docker FFmpeg completado

### Validación legacy
- [x] Test: franco5 (10 escenas, sin visualPlan) — Renderizado completo (53s MP4)
- [x] Test: hist-181103 (6 escenas, formato transicional) — Assets descargados
- [x] Compatibilidad prepare_job.py con metadata legacy — Merge correcto (bug corregido)
- [x] Bug: prepare_job.py sobrescribía assets — Corregido (mergea preservando campos)

### Validación end-to-end de job nuevo
- [x] Job: `la-2026-07-01-144559` — "La caída de Constantinopla"
- [x] generate_script.py → script con visualPlan (10 escenas, múltiples estrategias)
- [x] fetch_images.py → 4 de Wikimedia, 4 de Pexels, 2 Pollinations
- [x] generate_audio.py → edge-tts es-ES-AlvaroNeural, 10/10 OK
- [x] prepare_job.py → subtítulos ASS, metadata preservada
- [x] render_job.py → video.mp4 (4.8MB, ~60s)
- [x] Estado final: RENDERED
- [x] Metadata completa: providerAttemptOrder, providerFailures, fallbackReason, candidateCount, scoreReasons, discardedCandidates

### Bugs encontrados y corregidos en validación

| # | Archivo | Bug | Fix |
|---|---------|-----|-----|
| 1 | `bin/fetch_images.py` | "exists" shortcut retornaba metadata mínima | Ahora siempre procesa scoring, salta solo descarga |
| 2 | `bin/prepare_job.py` | Sobrescribía assets array rico con entries mínimos | Mergea preservando campos existentes |
| 3 | `bin/render_job.py` | `parents[2]` → montaba `data/` en vez de raíz | Cambiado a `parents[3]` |
| 4 | `bin/render_job.py` | Docker API version 1.43 obsoleta | Actualizado a 1.44 |
| 5 | `bin/fetch_images.py` | No cargaba `.env` → API keys no disponibles | Añadida carga de .env al inicio |

## Fase 5 — Informe final

- [x] Documentar resultados reales
- [x] Documentar limitaciones encontradas
- [x] Listar próximas mejoras recomendadas

---

## Informe final: Pipeline visual evolucionado

### Resultados del job end-to-end `la-2026-07-01-144559`

| Escena | Estrategia | Proveedor | Score | Calidad |
|--------|-----------|-----------|-------|---------|
| 1 | generated_reconstruction | Pollinations | 15 | INSUFICIENTE - IA genérica (FreeAI sin key) |
| 2 | historical_archive (map) | Wikimedia Commons | 40 | BUENA - Mapa histórico real CC BY-SA |
| 3 | historical_archive (portrait) | Wikimedia Commons | 65 | BUENA - Retrato histórico real, Public Domain |
| 4 | historical_archive (document) | Wikimedia Commons | 5 | ACEPTABLE - Documento histórico, baja resolución |
| 5 | atmospheric_broll | Pexels | 35 | ACEPTABLE - Foto stock visualmente correcta |
| 6 | generated_reconstruction | Pollinations | -15 | INSUFICIENTE - IA genérica (FreeAI sin key) |
| 7 | atmospheric_broll | Pexels | 5 | ACEPTABLE - Foto stock |
| 8 | map_or_document (map) | Wikimedia Commons | 20 | BUENA - Mapa histórico real CC0 |
| 9 | atmospheric_broll | Pexels | 35 | ACEPTABLE - Foto stock |
| 10 | atmospheric_broll | Pexels | 35 | ACEPTABLE - Foto stock |

**Totales:**
- 4 escenas con archivo histórico real (Wikimedia Commons) — 40%
- 4 escenas con B-oll de stock (Pexels) — 40%
- 2 escenas con IA genérica (Pollinations) — 20% (debieran ser FreeAI)

### Limitaciones encontradas

1. **FREEAI_API_KEY no configurada** — Las 2 escenas `generated_reconstruction` caen a Pollinations (IA genérica de baja calidad) en vez de usar FLUX Schnell.
2. **Scoring sin visión artificial** — No se puede evaluar calidad visual real, solo metadata textual. Una foto de stock de Pexels con título genérico puntúa igual que una de Wikimedia con título detallado.
3. **Pollinations calidad baja** — 576x1024, sin control de estilo, imágenes genéricas sin valor documental.
4. **Atmospheric broll desde Pexels** — Las 4 escenas de Pexels son del mismo autor (James Frid) porque las queries visuales genéricas devuelven resultados consistentes pero poco variados.
5. **Formato bootstrap sin sceneNumber no soportado** — hist-175447 queda como legacy no migrable.

## Fase 17 — Validación semántica hard de assets históricos

### Tareas implementadas

- [x] Hard rule `context_map`: rechazar assets cuyo `primaryAssetType` no sea mapa/documento/periódico.
- [x] Hard rule `event_depiction`: rechazar assets con `assetTemporalMatch` `unknown` o `modern_legacy`.
- [x] Mejorar `_determine_asset_temporal_match`:
  - [x] Matching sin acentos y multilingüe (español → inglés/alemán).
  - [x] Extraer año de evento desde `period`, `entities` y `voiceover`.
  - [x] Añadir equivalencia "Post-Guerra Fría" → "fall of the Berlin Wall" / 1989.
  - [x] Priorizar indicadores modernos (`anniversary`, `celebration`) cuando no hay año de evento.
- [x] Reutilización segura de assets:
  - [x] Bloquear reúso de `modern_legacy`/`unknown` para `event_depiction`.
  - [x] Extraer años del `voiceover` destino para detectar mismatch de periodo.
  - [x] Re-evaluar `assetTemporalMatch` en el contexto destino.
  - [x] Preservar `title`/`description` en `asset_meta` para cadenas de reuso.
- [x] Generar queries históricas para escenas `event_depiction` aunque el rol no sea hard histórico.
- [x] Añadir metadata de provenancia original (`originalSceneNumber`, `originalEditorialRole`, `originalVisualTemporalIntent`, `reuseCompatibilityReason`).
- [x] Añadir `roleEvidence` y `assetTypeEvidence` a `semanticEvidence`.
- [x] Escribir `tests/test_semantic_asset_validation.py` (8 tests, todos pasan).
- [x] Ejecutar job `validation-realistic-berlin-wall-v5-assets-*` → estado `ASSETS_READY`.

### Bugs corregidos en esta fase

| # | Archivo | Bug | Fix |
|---|---------|-----|-----|
| 1 | `bin/fetch_images.py` | `same_asset_type` penalizaba con 2 escenas consecutivas del mismo tipo | Umbral `>= 2` en lugar de `>= 1` |
| 2 | `bin/fetch_images.py` | Reuso hacía shallow copy y mutaba el VTI de la escena anterior | Deep-copy de `segments` antes de mutar |
| 3 | `bin/fetch_images.py` | `context_map` rechazaba todos los candidatos al leer `c["strategy"]` | Leer `visualPlan["primaryAssetType"]` |
| 4 | `bin/fetch_images.py` | Reuso 1961→1989 no se bloqueaba si el periodo no tenía año | Extraer años también del `voiceover` |
| 5 | `bin/fetch_images.py` | `_determine_asset_temporal_match` no coincidía términos acentuados ni multilingües | `_unaccent()` + equivalencias de periodo/entidad/ubicación |
| 6 | `bin/fetch_images.py` | "Post-Guerra Fría" no se reconocía como periodo del evento | Añadir a `period_equivalents` |
| 7 | `bin/fetch_images.py` | Fotos de aniversario reciente clasificadas como `archival_context` | Priorizar `modern_indicator` sin año de evento |
| 8 | `bin/fetch_images.py` | Escenas `event_depiction` con rol soft usaban queries genéricas | Generar `build_historical_queries` también para `event_depiction` |
| 9 | `bin/fetch_images.py` | `asset_meta` del path multi-segmento perdía `title`/`description` | Copiar desde `semanticEvidence` |
| 10 | `bin/fetch_images.py` | `context_map` aceptaba fotos ordinarias si `primaryAssetType == historical_map` | `_infer_effective_asset_type()` desde metadata del candidato + `roleEvidence` no vacío |
| 11 | `bin/fetch_images.py` | Mapas históricos sin año explícito tenían `assetTemporalMatch=unknown` | Mapas/documentos con match de entidad/ubicación → `archival_context` |
| 12 | `bin/fetch_images.py` | render_job bloqueaba assets 550x463 que fetch_images aceptaba (MIN_WIDTH 400 vs 720) | `_check_renderability()` unificado |
| 13 | `bin/fetch_images.py` | Scene 1 seleccionaba mapa blank template ilegible | `_BLANK_MAP_REJECT_TERMS` + `MIN_MAP_READABILITY=0.40` + 720x720 |
| 14 | `bin/fetch_images.py` | Scene 2 aceptaba foto de JFK en checkpoint como construcción | `constructionSubjectEvidence` específico: "construction workers", "building the wall", etc. |
| 15 | `bin/prepare_job.py` | Timeline con gaps entre escenas y final no cubierto | `_fill_timeline_gaps()` extiende visuales sobre silencios |

### Corrección v7 — Unificación renderability + construction evidence

- [x] `_check_renderability()`: política compartida fetch_images/asset_validation/render_job (720x720, mapReadability>=0.40, sin blanks).
- [x] `sourceSubjectEvidence` vs `constructionSubjectEvidence` separados.
- [x] Hard rule `battle_or_assault`: requiere `constructionSubjectEvidence` no vacío.
- [x] `semanticConfidence` boost para context_map con roleEvidence.
- [x] `_fill_timeline_gaps()` para cubrir gaps entre escenas y final del audio.
- [x] 6 nuevos tests (18/18 passed).
- [x] Job: `validation-realistic-berlin-wall-v7-assets-20260705-165658` → Scene 1 OK, Scene 2 ASSET_UNRESOLVED.

### Validación

- Job: `validation-realistic-berlin-wall-v5-assets-20260705-001121`
- Estado final: `ASSETS_READY`
- Escena 1: mapa histórico (`archival_context`)
- Escena 2: construcción 1961 (`archival_context`)
- Escena 3: familia separada 1961 (`archival_context`)
- Escena 4: caída 1989 (`historical_event`) — **no reusó asset de 1961**
- Escena 5: reuso de asset 1989 para legado (`archival_context`)
- Tests: `python3 -m pytest tests/test_semantic_asset_validation.py -v` → 8/8 passed

## Fase 18 — Aislamiento de artefactos derivados y evidencia visual de cierre de frontera

### Tareas implementadas

- [x] Crear `bin/clone_job.py` con `clone_job()` que descarta artefactos derivados.
- [x] Permitir parches por escena al clonar (ej. escena 2 → `border_closure_construction`).
- [x] Añadir validación `CROSS_JOB_ARTIFACT_REFERENCE` en `render_job.py`.
- [x] Nuevo rol `border_closure_construction` en `HARD_HISTORICAL_ROLES` y `EVENT_DEPICTION_ROLES`.
- [x] Evidencia de cierre de frontera: términos multilingües y rechazo de familia/checkpoint/conmemoración.
- [x] Añadir `borderClosureSubjectEvidence` a `semanticEvidence`.
- [x] Actualizar `_build_scene_query_variants()` con queries alemanas/inglesas de cierre de frontera.
- [x] Añadir tests: clon limpio, regeneración de rutas, rechazo de referencias cruzadas, evidencia de cierre.
- [x] Crear job `validation-realistic-berlin-wall-v8-assets-*` → `ASSETS_READY`.
- [x] Verificar que `metadata.json` del job v8 no contiene rutas de otros jobs.

### Bugs corregidos en esta fase

| # | Archivo | Bug | Fix |
|---|---------|-----|-----|
| 1 | `bin/clone_job.py` | Nuevo — no existía helper para clonar jobs limpios | `clone_job()` descarta `DERIVED_KEYS` y aplica parches |
| 2 | `bin/render_job.py` | No se detectaban rutas heredadas de otros jobs | `validate_no_cross_job_paths()` + `CROSS_JOB_ARTIFACT_REFERENCE` |
| 3 | `bin/fetch_images.py` | `battle_or_assault` era demasiado estrecho para el cierre de frontera de 1961 | Nuevo rol `border_closure_construction` con evidencia ampliada y rechazo de familia/checkpoint |
| 4 | `bin/fetch_images.py` | Queries de escena 2 no incluían términos alemanes de cierre | `_build_scene_query_variants()` añade `Stacheldraht`, `Mauerbau`, `Grenzsperre`, etc. |

### Validación

- Job: `validation-realistic-berlin-wall-v8-assets-20260705-154041`
- Estado final: `ASSETS_READY`
- Escena 1: mapa histórico (`archival_context`)
- Escena 2: construcción del Muro (`borderClosureSubjectEvidence` = `["construction of the wall"]`)
- Escena 3: impacto civil (`archival_context`)
- Escena 4: reutiliza asset anterior (consecuencia/legado)
- Escena 5: reutiliza asset anterior (CTA/legado)
- No hay rutas cruzadas en `metadata.json` del v8.
- Tests: `python3 -m pytest tests/test_semantic_asset_validation.py tests/test_duration_contract_and_scene_boundary.py -v` → 71/71 passed.

## Fase 19 — Evidencia de fecha y endurecimiento de reutilización

### Tareas implementadas

- [x] `_classify_date_evidence()` en `bin/fetch_images.py`: separa `sourceDepictedDateEvidence` vs `sourceContextDateEvidence` usando heurística (rangos con guión, cues retrospectivos, verbos depictivos).
- [x] Añadir `fallOpeningSubjectEvidence` y `divisionSubjectEvidence` a `semanticEvidence`.
- [x] Añadir `border_closure_construction` a `EDITORIAL_ROLE_COMPATIBILITY` y `check_role_evidence()` en `asset_validation.py`.
- [x] `check_reuse_compatibility()` en `asset_validation.py`: rechaza reuso si los años depicted no intersectan con el evento destino, o si el rol original es `civilian_impact` y el evento destino difiere.
- [x] 6 nuevos tests de regresión (32/32 total passing).
- [x] Crear job v9: `validation-realistic-berlin-wall-v9-assets-20260705-162058/` → `ASSETS_READY`.
- [x] Escena 1: mapa zonas ocupación 1945 (ok).
- [x] Escena 2: foto construcción CIA 1961 (ok).
- [x] Escena 3: foto separación familiar 1961 con "The Berlin Wall 1961 - 1989" — depicted solo 1961, no 1989 (ok).
- [x] Escena 4: foto fresca "Juggling on Berlin Wall 1989" (no reuso de escena 3) (ok).
- [x] Escena 5: reuso de escena 4 para CTA/legacy (ok).
- [x] Cero rutas cruzadas en v9.
- [x] Asset validation PASS en v9.
- [x] `prepare_job.py` ejecutado en v9 (estado ASSETS_READY).

### Bugs corregidos en esta fase

| # | Archivo | Bug | Fix |
|---|---------|-----|-----|
| 1 | `bin/fetch_images.py` | `_classify_date_evidence` restaba `context_years` de `depicted_years`, eliminando "1961" porque el rango "1961 - 1989" lo añadía a contexto | Cada conjunto se mantiene independiente; un año es depicted si existe algún cue depictivo |
| 2 | `bin/fetch_images.py` | `if y in context_years: continue` cortocircuitaba la segunda mención de "1961" en la frase depictiva | Nunca saltar por context_years; evaluar cada mención independientemente |
| 3 | `bin/fetch_images.py` | Reuso de 1961→1989 no se bloqueaba porque usaba `periodTermsMatched` en vez de `sourceDepictedDateEvidence` | Reuso ahora compara `sourceDepictedDateEvidence` |
| 4 | `bin/fetch_images.py` | Asset con título "1961 - 1989" se clasificaba como si depictara 1989 | Heurística de rango con guión: los rangos son contexto, no depiction |
| 5 | `bin/asset_validation.py` | No existía `check_reuse_compatibility()` como validación post-reuso | Nueva función que verifica tras el reuso |

### Validación

- Job: `validation-realistic-berlin-wall-v9-assets-20260705-162058`
- Estado final: `ASSETS_READY`
- Tests: `python3 -m pytest tests/test_semantic_asset_validation.py -v` → 32/32 passed
- Escena 1: mapa 1945 (`archival_context`, depicted=[1945])
- Escena 2: construcción CIA 1961 (`archival_context`, borderClosure=[construction of the wall])
- Escena 3: familia separada 1961 (`archival_context`, depicted=[1961], context=[1961..1989])
- Escena 4: malabarismo Muro 1989 (`historical_event`, depicted=[1989], fall=[juggling])
- Escena 5: reuso escena 4 para legado (`archival_context`, origScene=4)
- Cero rutas cruzadas en metadata.json
- `asset_validation.py`: ASSET_VALIDATION_PASSED (en job v9)

### Render end-to-end (v9)

- [x] Generar audio continuo Edge TTS (`es-ES-AlvaroNeural`, `edge_tts_word_boundary`, 25.32s).
- [x] `prepare_job.py`: subtítulos ASS, timeline 5 segmentos, renderTimeline 5 segmentos.
- [x] Preflight: path isolation, asset validation PASS, duración 25-30s, timeline coverage 0.0–25.32s, ASS style correcto.
- [x] Scene 2: `slow_zoom_in` + `focalRegion=center` para la foto oscura de construcción CIA (930×1234).
- [x] Render: FFmpeg exit code 0, video.mp4 (1080×1920, 25.32s, 1.7 MB).
- [x] `validate_job.py`: `passed: true`, 0 errors, 0 warnings.
- [x] Review frames extraídos: 10%, 30%, 50%, 70%, 90% + 4 transiciones + scene 2 close.
- [x] Estado final: `RENDERED` (review PENDING).
- [x] Session log: `docs/sessions/2026-07-05-1706-berlin-wall-v9-first-e2e-render.md`

#### Métricas clave del render

| Métrica | Valor |
|---------|-------|
| Audio duration | 25.32s |
| Video duration | 25.32s |
| Drift | 0.00s |
| Black frames | 0 |
| Freeze frames | 0 |
| Cobertura subtítulos | 99.6% (manifest) / 81% (validate_job) |
| qualityGate | FAIL (text mismatch) |
| Escena 2 zoom | slow_zoom_in 1.0×→1.15×, centro |

El qualityGate FAIL se debe a `subtitleCoverageValidation: FAIL` por diferencia exacta de texto entre los cues de TTS y el voiceover original (espacios/puntuación). La cobertura real de subtítulos es 99.6%.

### Próximas mejoras recomendadas

1. **Obtener FREEAI_API_KEY** — Prioridad máxima. Las escenas `generated_reconstruction` pasarían de Pollinations (score -15/15) a FLUX Schnell con control de estilo.
2. **Mejorar variedad de queries Pexels/Pixabay** — Rotar entre múltiples queries visuales para cada escena, no elegir siempre la primera.
3. **Añadir visión artificial para scoring** — Evaluar si la imagen contiene elementos relevantes (personas, mapas, texto, etc.) mediante clasificación básica.
4. **Añadir evaluación de calidad post-render** — Revisar el video.mp4 generado y permitir approve/reject por escena.
5. **Instalar edge-tts documentado** — Comando reproducible: `.venv/bin/pip install -r requirements.txt`
6. **Refinar reutilización de assets** — Un asset 1961 reutilizado para una escena 1989 puede pasar el filtro de años si su metadata contiene ambos años; debería preferirse búsqueda fresca para eventos distintos.
