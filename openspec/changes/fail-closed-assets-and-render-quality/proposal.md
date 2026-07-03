# Proposal: Fail-Closed Asset Validation y Calidad Mínima de Render

## Problema

El render `la-2026-07-01-173458` (36.24s, "La caída de Constantinopla") pasó todas las validaciones técnicas:
- Duración: 36.24s vs 36.15s esperados (delta 0.09s ✓)
- Black frames: 0 ✓
- Freeze frames: 0 ✓
- FFmpeg exit code: 0 ✓

Sin embargo, el vídeo contiene:
- Placeholders con texto "Escena X Seg Y" generados por Pillow
- Imágenes modernas/fotos genéricas sin relevancia histórica
- Fondos grises uniformes sin contenido histórico
- Assets sin metadatos de provider, query, score, licencia

**Causa raíz:** El pipeline no valida el **contenido semántico y editorial** de los assets antes del render. Los fallos de `fetch_images` (5/11 segmentos) fueron silenciosamente reemplazados por placeholders sintéticos sin marcar el job como inválido.

## Objetivo

Ningún vídeo final puede renderizarse si contiene placeholders, imágenes inválidas, assets de baja relevancia histórica o segmentos sin una fuente visual válida.

## Reglas obligatorias

1. **Prohibición total de placeholders en render final** — solo para tests sintéticos.
2. **Validación pre-render** por segmento: existencia, decodificable, sin texto debug, sin fondo uniforme, dimensiones mínimas, provider+query, assetType+editorialRole, score mínimo.
3. **Validación editorial mínima** — coherencia histórica por period/location/entities/negativeKeywords.
4. **Quality gate** — `validate_job_for_render(metadata)` → PASS / REVIEW_REQUIRED / BLOCKED.
5. **Render de prueba controlado** con assets reales antes de nuevo render completo.
6. **Subtítulos solo desde voiceover cues** — sin overlays editoriales por defecto.
7. **Informe final** con tabla por segmento y métricas agregadas.

## Criterios de éxito

- No aparecen placeholders en el MP4 final
- No se usan imágenes modernas para escenas históricas sin justificación
- Todos los assets tienen provider, query y score registrados
- `validate_job_for_render` bloquea el render si hay fallos
- Bitácora y tasks.md actualizados
