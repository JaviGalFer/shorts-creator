# Tasks: Fail-Closed Asset Validation y Calidad Mínima de Render

## Fase 1 — Diagnóstico de assets actuales
- [x] Revisar metadata de `la-2026-07-01-173458` — identificar todos los assets con placeholders, providers fallidos, y segmentos sin metadata completa
- [x] Marcar el job actual como `INVALID` con `status: ASSET_FAILED` y `review.status: REJECTED`
- [x] Documentar lista exacta de segmentos inválidos y sus razones (10 segmentos, 8 placeholders, 4 negative scores, 2 editorial mismatches)

## Fase 2 — Implementación de reglas de validación
- [x] Implementar `validate_asset_file()`: existencia, decodificable, dimensiones mínimas, fondo uniforme
- [x] Implementar `detect_placeholder_content()`: heurística sobre metadatos (provider nulo, score negativo, filename patterns)
- [x] Implementar `validate_metadata_completeness()`: provider, query, score, assetType, sourceUrl, editorialRole
- [x] Implementar `check_editorial_coherence()`: compatibility matrix assetType × editorialRole, negativeKeywords por período (Constantinopla)
- [x] Implementar `check_provider_allowed()`: reglas por provider (Pollinations → low confidence, Pexels → flagged)
- [x] Implementar `validate_job_for_render()`: orquesta todas las validaciones, produce PASS/REVIEW_REQUIRED/BLOCKED

## Fase 3 — Integración en render_job.py
- [x] Añadir `validate_job_for_render()` como paso previo al render, después del check de renderTimeline
- [x] BLOCKED → abortar render, status=ASSET_FAILED, guardar failures en metadata
- [x] REVIEW_REQUIRED → permitir render con advertencia, status=REVIEW_REQUIRED
- [x] Añadir flag `--skip-asset-validation` para desarrollo
- [x] Asset validation result incluido en metadata.json

## Fase 4 — Crear job de prueba con assets reales
- [x] Crear `bin/create_real_asset_test.py` — descarga 3 assets reales de Wikimedia Commons con metadata completa
- [x] Asset 1: Mapa histórico de Constantinopla (wikimedia_commons, score 80)
- [x] Asset 2: Miniatura otomana de Mehmed II (wikimedia_commons, score 90)
- [x] Asset 3: Mapa bizantino de Constantinopla (wikimedia_commons, score 85)
- [x] Sin placeholders, sin Pollinations, sin Pexels, sin CTA
- [x] `validate_job_for_render` pasa con 3/3 assets válidos

## Fase 5 — Render de prueba controlado
- [x] Renderizar job de prueba con `render_job.py`
- [x] Asset validation PASS (3/3 segments valid)
- [x] Duración: 12.0s expected, 12.0s actual (delta 0.0s)
- [x] Black frame warnings: 0
- [x] Freeze frame warnings: 0
- [x] FFmpeg exit code: 0
- [x] Sin placeholders en el MP4 (todos los assets son históricos reales)

## Fase 6 — Re-render completo de Constantinopla
- [x] Arreglar `fetch_images`: MIME filtering en Wikimedia (PDFs excluidos) + fallback a siguiente provider si download falla
- [x] fetch_images corrido: 11/11 segmentos OK con metadata completa
- [x] prepare_job corrido: timeline y subtítulos regenerados
- [x] validate_job_for_render corrido sin cache: 0 placeholders, 0 missing metadata
- [x] Tabla de validación por segmento generada
- [x] Contact sheet generado en `validation/contact_sheet.png`
- [x] Resolver editorial mismatches (scene 6.1: atmospheric_broll → historical_map, manteniendo context_map)
- [x] Decidir tratamiento de Pexels como low confidence (solo soft roles: consequence_or_legacy, atmospheric_transition, legacy, abstract)
- [x] Render sin placeholders ni editorial mismatches — 11/11 segmentos, 9 Wikimedia + 2 Pexels (soft role), 36.24s, 0 black frames, 0 freeze frames
- [x] Implementar role-based provider chains (HARD_HISTORICAL_ROLES → solo wikimedia_commons, ASSET_UNRESOLVED en lugar de fallback)
- [x] Implementar build_historical_queries() para queries jerárquicas en roles históricos duros
- [x] Re-ejecutar fetch_images con queries mejoradas — resolver 3 ASSET_UNRESOLVED (scene 1 seg 2, scene 3 seg 1 y 2)
- [x] Render final validado — video.mp4 9.1MB, 38s, REVIEW_REQUIRED (esperado), sin BLOCKED

## Fase 7 — Documentación
- [x] Crear `bin/asset_validation.py` con todas las reglas de validación
- [x] Actualizar `docs/runbooks/render-troubleshooting.md` con sección de asset validation
- [x] Actualizar bitácora de sesión
- [x] Cerrar OpenSpec solo con validación automática OK, sin placeholders, sin editorial mismatches en render completo
