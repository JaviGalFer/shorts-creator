# Sesión: Fail-Closed Asset Validation y Calidad Mínima de Render

**Fecha:** 2026-07-01
**Cambio OpenSpec:** `openspec/changes/fail-closed-assets-and-render-quality/`
**Contexto:** El render `la-2026-07-01-173458` pasó todas las validaciones técnicas de duración (36.24s, delta 0.09s, 0 black frames, 0 freeze frames) pero contiene placeholders de depuración, imágenes modernas irrelevantes, y fondos grises con texto tipo "Escena X Seg Y". El pipeline trató fallos de asset sourcing como contenido válido de producción.

## Problema

No existe ninguna validación del **contenido semántico y editorial** de los assets antes del render. El pipeline actual solo verifica:
- Existencia de archivo (`assetPath exists`)
- Duración (timeline vs expected)

Pero NO verifica:
- Si el asset es un placeholder generado por Pillow
- Si el asset es una imagen moderna/irrelevante para la escena histórica
- Si el asset tiene metadatos de provider, query, score, licencia
- Si el assetType es compatible con el editorialRole
- Si el asset supera dimensiones mínimas
- Si el asset contiene texto de depuración

## Decisión

Crear un sistema **fail-closed** de validación de assets que impida el render si algún segmento no tiene un asset válido, relevante y con trazabilidad completa. Ningún placeholder, fallback sintético, o imagen sin metadata puede llegar al MP4 final.

## Implementación completada

### Calidad de validación
- Job `la-2026-07-01-173458`: 10/10 segmentos inválidos (8 placeholders, 4 negative scores, 2 editorial mismatches) → BLOCKED
- Job `test-real-2026-07-01-183119`: 3/3 segmentos válidos (mapa histórico, miniatura otomana, mapa bizantino) → PASS → RENDERED

### Resultados del render de prueba
```
Asset validation: PASS (3/3 segments valid)
Duración: 12.0s expected, 12.0s actual (delta 0.0s)
Black frames: 0 | Freeze frames: 0 | FFmpeg exit: 0
Status: RENDERED
```

### Archivos creados/modificados

| Archivo | Descripción |
|---------|-------------|
| `bin/asset_validation.py` | Módulo de validación con 6 funciones de reglas + quality gate |
| `bin/render_job.py` | Integración del quality gate antes del render |
| `bin/create_real_asset_test.py` | Generador de jobs de prueba con assets históricos reales |
| `openspec/changes/fail-closed-assets-and-render-quality/proposal.md` | Problema y objetivos |
| `openspec/changes/fail-closed-assets-and-render-quality/design.md` | Arquitectura completa |
| `openspec/changes/fail-closed-assets-and-render-quality/tasks.md` | Tareas actualizadas |
| `data/videos/la-2026-07-01-173458/metadata.json` | Marcado como ASSET_FAILED con 10 failures documentados |

### Pendiente (Fase 6)
Re-render completo de "La caída de Constantinopla" requiere arreglar `fetch_images` para que descargue assets reales (actualmente 9/10 segmentos no tienen provider). Esto queda para la siguiente sesión.
