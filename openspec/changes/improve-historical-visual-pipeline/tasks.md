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

## Fase 20 — Duration profiles and subtitle quality-gate consistency

### Duration profiles

Implementado un sistema centralizado de perfiles de duración reutilizables:

```python
DURATION_PROFILES = {
    "short_25_30":    {"targetSec": 28, "minSec": 25, "maxSec": 30, "strictness": "balanced"},
    "standard_32_38": {"targetSec": 35, "minSec": 32, "maxSec": 38, "strictness": "balanced"},
    "extended_50_60": {"targetSec": 55, "minSec": 50, "maxSec": 60, "strictness": "balanced"},
}
```

- Definidos en `bin/duration_profiles.py` (único punto central).
- `--duration-profile short_25_30|standard_32_38|extended_50_60` como argumento CLI en `generate_script.py`.
- Los valores explícitos `--duration-target/--duration-min/--duration-max` sobreescriben el perfil.
- Por defecto: `short_25_30` para compatibilidad backward.
- Se persiste `durationProfile` tanto en `request` como en `resolvedConfig` de `metadata.json` y `job-manifest.json`.
- Tests: 7 tests en `tests/test_duration_profiles.py` (todos pasan).

### Subtitle quality-gate consistency

Reemplazada la comparación carácter-exacta de texto de subtítulos con comparación normalizada por tokens:

- Nueva función central `normalize_subtitle_text()` en `bin/subtitle_normalize.py`:
  - lowercase, trim y collapse whitespace
  - punctuation-insensitive (elimina todo carácter no-word)
  - accent-insensitive (NFKD decompose + remove combining marks)
  - normaliza puntuación española invertida (¿¡)
- `cue_text_matches_narration()`: comparación por tokens con umbral configurable (0.95).
- Actualizado `coverage_validation.py`: `validate_cue_text` usa `compare_cue_vs_narration_bulk`.
- Actualizado `validate_job.py`: `_check_subtitle_alignment` usa `normalize_subtitle_text`.
- Añadido `validate_job.py --update-manifest` para re-evaluar quality gates post-fix.

La validación semántica (canonical, cross-scene) y la cobertura temporal permanecen bloqueantes.

### Tareas implementadas

- [x] Crear `bin/duration_profiles.py` con perfiles y función `resolve_duration_config()`.
- [x] Añadir `--duration-profile` CLI arg a `generate_script.py`.
- [x] Persistir `durationProfile` y `resolvedConfig` en metadata y manifest.
- [x] Crear `bin/subtitle_normalize.py` con normalización centralizada.
- [x] Actualizar `coverage_validation.py` para usar nueva normalización.
- [x] Actualizar `validate_job.py` para usar nueva normalización.
- [x] Añadir `validate_job.py --update-manifest` para refrescar gates.
- [x] Tests de perfiles de duración (7 tests, todos pasan).
- [x] Tests de normalización de subtítulos (17 tests, todos pasan).
- [x] Ejecutar validación completa (105/105 tests pasan).
- [x] Re-evaluar v9: qualityGate=PASS tras normalización.
- [x] Session log: `docs/sessions/2026-07-05-1800-duration-profiles-and-subtitle-gate-consistency.md`

### Validación

- Tests: `python3 -m pytest tests/ -v` → 105/105 passed
- Job v9 quality gates tras fix:
  - technicalValidation=PASS
  - subtitleCoverageValidation=PASS
  - assetValidation=PASS
  - qualityGate=PASS

## Fase 21 — Generic duration-to-word-budget enforcement

### Tareas implementadas

- [x] Crear `calculate_word_budget()` en `bin/duration_profiles.py` con fórmula genérica (no atada a perfiles).
- [x] La función acepta cualquier valor numérico: targetSec, minSec, maxSec, WPM, sceneCount, pauseMs.
- [x] Retorna minimumWords/preferredWords/maximumWords, pauseSec, y metadatos.
- [x] Preparada para recibir valores de `--duration`/`requestedSec` futuros sin cambios.
- [x] `generate_script.py` usa `calculate_word_budget()` para presupuesto provisional (5 escenas) antes del primer LLM.
- [x] El prompt inicial ahora incluye minimumWords, preferredWords, maximumWords y rango por escena.
- [x] Tras cada LLM, se recalcula el presupuesto con el número real de escenas generadas.
- [x] `_build_retry_instruction()` genera prompt correctivo con word count real, faltante/excedente, y guía de expansión/reducción.
- [x] `retryHistory` incluye reason, minimumWords/preferredWords/maximumWords, estimatedDurationSec, instructionType.
- [x] `durationContract` incluye minimumWords, preferredWords, maximumWords, pauseSec.
- [x] Tests: 12 tests de word budget (todos pasan, 117/117 total).
- [x] Eliminar reglas fijas de duración/palabras de SYSTEM_PROMPT (25-30s, ~45-55 palabras, <30s).
- [x] SYSTEM_PROMPT ahora contiene solo reglas editoriales y de esquema independientes de duración.
- [x] La única fuente de verdad para duración, presupuesto de palabras y escenas es `_build_duration_prompt_instruction()`.
- [x] Tests de consistencia prompt-contract: 6 tests (sin "25-30", sin "45-55", cada perfil recibe valores dinámicos).
- [x] Session log: `docs/sessions/2026-07-05-1930-generic-duration-word-budget-enforcement.md`

### Validación

- Tests: `python3 -m pytest tests/ -v` → 123/123 passed
- Nuevos tests en `tests/test_duration_profiles.py`:
  - Budget para short_25_30 (28s, 5 scenes)
  - Budget para standard_32_38 (35s, 5 scenes) — min=57, pref=62, max=67
  - Budget para extended_50_60 (55s, 6 scenes)
  - Budget con valores explícitos no relacionados a perfiles (42s, 130 WPM)
  - Budget para 40s, 6 scenes
  - Provisional scene count (1-8 escenas) — fórmula no hardcodeada
  - Overrides explícitos
  - Zero pause para 1 escena
  - Clasificación below_minimum (54 words < 57)
  - Clasificación in_range (62 words in 57-67)
   - Prompt instruction contiene budget numérico
   - Retry instruction contiene corrección con word count, missing words, budgets
   - SYSTEM_PROMPT sin "25-30" fijo
   - SYSTEM_PROMPT sin "45-55" fijo
   - standard_32_38 prompt tiene 32-38 y 57-67
   - extended_50_60 prompt tiene su propio budget dinámico
   - short_25_30 prompt tiene su propio rango 25-30 y budget
   - Prompt dinámico no tiene referencias a "<30s" ni "25-30" fijo

### Limitaciones restantes

1. **FREEAI_API_KEY no configurada** — `generated_reconstruction` sigue cayendo a Pollinations.
2. **Mejorar variedad de queries Pexels/Pixabay** — Rotación de queries para evitar mismo autor.
3. **Visión artificial para scoring** — Evaluación cualitativa de imágenes sigue siendo metadata-textual.
4. **Calidad post-render** — No hay approve/reject por escena automatizado.
5. **Refinar reutilización de assets** — Asset 1961 puede pasar filtro de años si metadata contiene ambos años; debería preferirse búsqueda fresca.
6. **validate_job coverage 81%** — La cobertura de subtítulos en validate_job (20.6s/25.3s) es menor que la del manifest (99.6%) porque validate_job mide cobertura bruta de cues vs manifest usa sceneTimings extendidos. No hay gaps reales.
7. **Scene 2 oscura** — Foto CIA 930x1234 es inherentemente low-contrast. Una foto más brillante mejoraría escena 2.
8. **Riesgo factual en cifras del LLM** — El guion de Stalingrad usó "Más de 2 millones de personas murieron" sin fuente verificada. Las cifras históricas deben redactarse de forma conservativa (ej. "Alrededor de 2 millones") a menos que el prompt exija explícitamente verificación. No hay verificador externo implementado.

## Fase 22 — Approximate duration resolution (`--duration` flag)

### Tareas implementadas

- [x] Añadir `SUPPORTED_DURATION_MIN=20` y `SUPPORTED_DURATION_MAX=60` en `bin/duration_profiles.py`.
- [x] Añadir `_auto_select_profile()` para mapear segundos a perfil (20-30→short, 31-45→standard, 46-60→extended).
- [x] Añadir `resolve_requested_duration()` con prioridad: overrides > --duration > --duration-profile > default.
- [x] Añadir `--duration` CLI arg en `add_duration_profile_args()`.
- [x] Tolerance dinámica: `clamp(round(N * 0.10), min=2, max=5)`.
- [x] Clamping condicional: perfil explícito siempre constrain; auto-selección constrain solo si min ≤ target ≤ max.
- [x] Rechazar --duration < 20 o > 60 con error claro.
- [x] Rechazar combinaciones incompatibles --duration + --duration-profile.
- [x] Rechazar min > target o target > max.
- [x] Persistir `requestedSec` y `requestedProfile` en `request.duration`.
- [x] Renombrar `MAX_SCENES_FOR_SHORT` → `MAX_SCENES` en `generate_script.py`.
- [x] Mantener `resolve_duration_config()` para backward compat en tests legacy.
- [x] Toda la lógica de resolución en `bin/duration_profiles.py` — no duplicada en `generate_script.py`.
- [x] Tests: 11 tests nuevos para `resolve_requested_duration()` (134/134 total).

### Validación

- Tests: `python3 -m pytest tests/ -v` → 134/134 passed
- Dry-run verification:
  - `--duration 28` → short_25_30, window 25-30
  - `--duration 42` → standard_32_38, window 38-46
  - `--duration 55` → extended_50_60, window 50-60
  - `--duration 19` → ERROR: below minimum
  - `--duration 61` → ERROR: exceeds maximum
  - `--duration 42 --duration-profile short_25_30` → ERROR: incompatible combo

## Fase 23 — Unified job runner and orchestration state

### Tareas implementadas

- [x] Crear `bin/run_job.py` — orquestador unificado que ejecuta scripts existentes como subprocesos.
- [x] Stage order: script → assets → audio → prepare → render → validate (descubierto del repositorio).
- [x] `--topic`, `--duration`, `--duration-profile`, `--duration-target/min/max`, `--strictness`, `--model` forwardeados a `generate_script.py`.
- [x] `--stop-after <stage>` para detener en cualquier etapa.
- [x] `--dry-run` imprime plan de ejecución sin invocar subprocesos.
- [x] `--verbose` para output detallado de subprocesos.
- [x] Job ID extraído del JSON estructurado de `generate_script.py`, no adivinado.
- [x] Stages posteriores reciben `metadata_path` como argumento posicional.
- [x] Estado `orchestration` persistido en `metadata.json` con `runnerVersion`, `currentStage`, `statusHistory[]`.
- [x] Estados de etapa: SCRIPT_GENERATING → SCRIPT_DRAFT, ASSETS_FETCHING → ASSETS_READY, etc.
- [x] Stage `REVIEW_REQUIRED` bloquea etapas posteriores.
- [x] Failure metadata: `failedStage`, `error`, `childCommand`, `exitCode`, `timestamp`.
- [x] `subprocess.run()` con `shell=False`, `cwd=project_root`, timeout 600s.
- [x] Errores truncados a 1000 chars, sin secrets en metadata.
- [x] Summary JSON final con jobId, jobPath, status, lastCompletedStage, outputVideoPath, validationStatus.
- [x] 34 tests nuevos (168/168 total):
  - Command construction for all options
  - Script output parsing (valid, missing fields, empty)
  - Metadata load/save preserves fields
  - Dry-run prints plan for all stages
  - Dry-run stop-after script shows only script
  - Invalid duration shows error in dry-run
  - Script stage extracts jobId from JSON
  - Missing script output fails safely
  - REVIEW_REQUIRED stops before assets
  - Non-zero exit produces FAILED with failedStage
  - Stop-after script does not run later stages
  - Stop-after assets does not run audio
  - Asset failure stops before audio
  - Metadata preservation across stages
  - No secrets in failure metadata

### Validación

- Tests: `python3 -m pytest tests/ -v` → 195/195 passed (61 in test_run_job.py)
- Dry-run: todos los stages se muestran con comandos correctos
- Script-only real: `--stop-after script` genera jobId=prueba-2026-07-05-182309, metadata, orchestration, summary JSON
- Duration 35 → profile standard_32_38, requestedSec y requestedProfile en metadata
- Real-run bounded through prepare: **Blocked at assets stage** (see below)

### Real-run verification (2026-07-05)

Two attempts with `bin/run_job.py --topic "La caída del Muro de Berlín" --stop-after prepare --verbose`:

**Attempt 1: `--duration 28`** — script stage blocked at `REVIEW_REQUIRED` (duration contract FAIL: estimated 30.5s > max 30s, 54 words > 53 max). Runner correctly handled REVIEW_REQUIRED gate.

**Attempt 2: `--duration 30 --duration-max 31`** — script ✅ (duration contract PASS, 53 words/5 scenes), assets ❌ (fetch_images.py exit 1: scenes 1–4 unresolvable, scene 5 OK via Wikimedia Commons). Runner correctly handled non-zero exit, set FAILED metadata with failedStage="assets", stopped before audio.

**Root cause of assets failure (corrected 2026-07-05)**: The `editorialRole` field IS populated by the LLM (it was already in the prompt schema). The actual failure: scenes 1–4 have hard historical roles (`context_map`, `civilian_impact`, `battle_or_assault`) which restrict provider chains to **only** `["wikimedia_commons"]` (`fetch_images.py:73-75`). Wikimedia Commons didn't return matching results for the generated queries. Scene 5 with soft role `consequence_or_legacy` succeeded via full provider chain.

**Prompt fix applied**: Added `visualTemporalIntent` (scene-level field + rules) and improved Wikimedia Commons query guidance (specific named entities + year requirement, 2+ queries per scene).

**Runner verdict through script stage: VERIFIED.** Runner correctly handles SCRIPT_DRAFT, REVIEW_REQUIRED, and ASSETS_FETCHING → FAILED paths. Contract verification for assets/audio/prepare remains unit-tested only (195/195 pass).

- Session log: `docs/sessions/2026-07-05-1849-runner-real-staged-verification.md`
- Job: `la-2026-07-05-185053` (FAILED at assets)
- Job: `la-2026-07-05-184917` (REVIEW_REQUIRED at script)

### Phase 23 follow-up: prompt + fallback improvements (2026-07-05)

After correcting the original root-cause diagnosis (editorialRole WAS populated by LLM; real issue was hard historical roles restrict to Wikimedia Commons only), made three improvements:

1. **generate_script.py prompt**: Added `visualTemporalIntent` field + rules section, improved Wikimedia Commons query guidance (named entity + year required, 2+ queries per scene), added editorialRole decision tree with explicit context_map exclusion rule (NO use for events like "Muro cayó en 1989").

2. **fetch_images.py fallback**: Added `_try_hard_role_fallback()` (lines 1806-1990) — when Wikimedia Commons exhausts queries for hard historical roles, tries Pexels then Pixabay with strict relevance filters. Fallback assets carry `provenanceType="illustrative"`, `fallbackReason`, and `originalEditorialRole` metadata. Preserves ASSET_UNRESOLVED blocking state if no acceptable fallback.

3. **Tests**: 10 new prompt tests in `test_generate_script.py`, 4 new fallback tests in `test_semantic_asset_validation.py`. Total 209/209 pass.

**Real-run verification (job la-2026-07-05-193524)**: Improved from 1/5 → 3/5 scenes resolved. Scene 1 (context_map for actual map content) succeeded via Wikimedia. Scenes 2 (civilian_impact) and 3 (battle_or_assault) succeeded via Pexels fallback with `provenanceType=illustrative`. Scenes 4-5 (atmospheric_broll, soft role) failed on download (not a hard-role issue).

### Soft-role temporal intent defect (2026-07-05, segunda iteración)

Diagnóstico de scenes 4-5 del job `la-2026-07-05-193524`: el fallo NO era en API search (60 candidatos recibidos por escena con keywords relevantes), sino en stage 1 filtering:

1. `_classify_temporal_intent()` ignoraba el campo LLM `scene.visualTemporalIntent` y usaba solo heurística de substring sobre voiceover. Para `consequence_or_legacy` con "caída..." o sin indicadores, devolvía `event_depiction` (default). La hard rule "event_depiction + assetTemporalMatch ∈ {unknown, modern_legacy} → reject" descartaba los 60 candidatos modernos legítimos de legado.
2. `EDITORIAL_ROLE_PREFERENCES["consequence_or_legacy"].forbidden = {atmospheric_broll, broll, generated_reconstruction}` combinado con `c["strategy"]` copy en `_fetch_one_asset` rechazaba cualquier candidato si la escena tenía strategy=atmospheric_broll.

Corrección mínima en `bin/fetch_images.py`:

1. `_classify_temporal_intent()` respeta el campo LLM `visualTemporalIntent` cuando válido; cae a la heurística solo si el campo falta (backward compatibility con jobs antiguos y tests existentes).
2. `_fetch_one_asset` stage 1: `forbidden_types` mutable; descartar `atmospheric_broll`/`broll` cuando `editorialRole=consequence_or_legacy` y `visualTemporalIntent=legacy_or_commemoration`. Scenes de event_depiction mantienen set estricto original.
3. Stage 1 low-confidence rejection reinforced: si `semanticConfidence=="low"` Y no `topicTermsMatched` Y no `locationTermsMatched` → reject (antes solo se rechazaba si no había sourceTitle).

Tests nuevos en `tests/test_semantic_asset_validation.py` (8 tests): cubren classify honour LLM field, fallback behaviour, weak-relevance rejection, exhaustion blocking state. Suite: **216/216 pass**.

#### Real-run verification: job la-2026-07-05-203359

Comando:

```
python3 bin/run_job.py --topic "La caída del Muro de Berlín" \
  --duration 30 --duration-max 35 --stop-after prepare --verbose
```

Resultado: **pipeline completó script → assets → audio → prepare**.

Stage-by-stage (orchestration statusHistory, 7 entries, truthful):

1. script: SCRIPT_DRAFT
2. assets: ASSETS_FETCHING
3. assets: ASSETS_READY
4. audio: AUDIO_GENERATING
5. audio: AUDIO_READY
6. prepare: PREPARING
7. prepare: SUBTITLES_READY

Provider/provenance distribution (5 scenes):

| Scene | editorialRole | visualTemporalIntent | Provider | provenanceType |
|-------|---------------|----------------------|----------|----------------|
| 1 | battle_or_assault | event_depiction | pexels (fallback) | illustrative |
| 2 | context_map | event_depiction | wikimedia_commons | documentary |
| 3 | civilian_impact | event_depiction | pexels (fallback) | illustrative |
| 4 | consequence_or_legacy | legacy_or_commemoration | wikimedia_commons | documentary |
| 5 | consequence_or_legacy | legacy_or_commemoration | wikimedia_commons (reuse scene 4) | documentary |

3 documentary + 2 illustrative. 0 Pixabay, 0 FreeAI, 0 Pollinations.

Cross-job path check: 0 violations. All asset/audio/timeline renderTimeline paths inside `data/videos/la-2026-07-05-203359/`. Scene 5 reuses scene-04-01.jpg (allowed: última escena + consequence_or_legacy).

Artefactos:
- `metadata.json` (63907 bytes)
- `subtitle.ass` (1661 bytes)
- `renderTimeline` 5 events, startSec 0.0 → endSec 30.0 (covers full narration)
- `render.path` planeado (vídeo.mp4 NO existe, `--stop-after prepare`)
- 5 narration MP3s (Edge TTS), 4 unique JPG assets

render, validate, review_job NOT ejecutados. OpenSpec change NO se cierra.

- Bitácora completa: `docs/sessions/2026-07-05-1945-prompt-and-hard-role-fallback.md`

### Limitaciones restantes

1. **FREEAI_API_KEY no configurada** — `generated_reconstruction` sigue cayendo a Pollinations.
2. **Mejorar variedad de queries Pexels/Pixabay** — Rotación de queries para evitar mismo autor.
3. **Visión artificial para scoring** — Evaluación cualitativa de imágenes sigue siendo metadata-textual.
4. **Calidad post-render** — No hay approve/reject por escena automatizado.
5. **Refinar reutilización de assets** — Asset 1961 puede pasar filtro de años si metadata contiene ambos años; debería preferirse búsqueda fresca.
6. **validate_job coverage 81%** — La cobertura de subtítulos en validate_job (20.6s/25.3s) es menor que la del manifest (99.6%) porque validate_job mide cobertura bruta de cues vs manifest usa sceneTimings extendidos. No hay gaps reales.
7. **Scene 2 oscura** — Foto CIA 930x1234 es inherentemente low-contrast. Una foto más brillante mejoraría escena 2.
8. **Riesgo factual en cifras del LLM** — El guion de Stalingrad usó "Más de 2 millones de personas murieron" sin fuente verificada. Las cifras históricas deben redactarse de forma conservativa (ej. "Alrededor de 2 millones") a menos que el prompt exija explícitamente verificación. No hay verificador externo implementado.
9. **Pipeline completo no verificado con e2e real** — El runner se verificó solo hasta script stage. Los stages assets/audio/prepare/render/validate no se ejecutaron en esta fase.
10. **Sin resume/retry-from-stage** — `--stop-after` permite detener pero no reanudar desde una etapa.
11. **Assets y audio secuenciales** — Podrían ejecutarse en paralelo para reducir tiempo total.
