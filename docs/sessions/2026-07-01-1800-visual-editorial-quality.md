# Sesión: Mejora de variedad visual, tratamiento de mapas y calidad editorial

**Fecha:** 2026-07-01  
**Cambio OpenSpec:** `openspec/changes/improve-visual-variety-and-editorial-quality/`  
**Duración:** ~3h

## Resumen

El pipeline multi-segmento funciona técnicamente, pero el vídeo generado presenta problemas observables: repetición de assets, mapas horizontales ilegibles, B-roll genérico, reconstrucciones IA con estética de videojuego, y retratos sin valor informativo.

Este cambio introduce reglas editoriales estrictas, anti-repetición, tratamiento específico de mapas/retratos, mejora de prompts IA, y rotación de queries de B-roll.

## Problemas identificados en el vídeo anterior

1. **Repetición de assets**: el mismo paisaje de ruinas/cielo aparece en escenas distintas.
2. **Mapas horizontales ilegibles**: forzados a 9:16 sin crop a región relevante ni fondo desenfocado.
3. **B-roll genérico**: escenas clave (asedio, batalla) cubiertas con "ruinas bonitas" de Pexels.
4. **Reconstrucciones IA**: estética fantasía/videojuego sin documental.
5. **Retratos sin contexto**: misma imagen repetida sin crop/zoom/overlay.

## Cambios implementados

### 1. Sistema editorial (`generate_script.py` y scoring)
- `editorialRole` por escena: context_map, character_portrait, military_technology, civilian_impact, battle_or_assault, document_or_date, consequence_or_legacy, atmospheric_transition
- Límite: atmospheric_transition ≤ 20% de escenas
- Penalización en scoring si el assetType no coincide con el editorialRole
- Prioridad de historical_archive sobre B-roll cuando el guion mencione entidades reales

### 2. Anti-repetición (`fetch_images.py` scoring)
- `duplicateRisk` field por segmento
- Penalización -40 si mismo author+provider en escenas consecutivas
- Penalización -30 si misma query usada recientemente
- Penalización -20 si mismo assetType que escena anterior
- Pool de queries alternativas por strategy para rotar

### 3. Tratamiento de mapas (`render_job.py`)
- `focalRegion` y `cropMode` en metadata de mapa
- Para landscape maps: blur background derivado del mapa, overlay centrado, crop a región relevante
- Rechazo de mapas con texto ilegible (score < threshold)
- Overlay de fecha/lugar y espacio reservado para subtítulos

### 4. Tratamiento de retratos
- No repetir mismo retrato sin cambio visual (crop, zoom, overlay de nombre)
- Transición obligatoria a documento o mapa si se repite personaje

### 5. Reconstrucciones IA
- Prompt obligatorio: historically accurate, documentary reconstruction, no fantasy, no video game art
- `visualAuthenticityRisk` field
- Preferir mezcla grabado/mapa/documento antes que IA genérica

### 6. Rotación de queries B-roll
- Pool alternativo por strategy
- Diversidad de author por vídeo
- Relación semántica con narración evaluada en scoring

## Resultado end-to-end: job `la-2026-07-01-171519`

### Pipeline ejecutado

```bash
python3 bin/generate_script.py --topic "La caída de Constantinopla"
# → 7 escenas, 5 con 2 segmentos, editorialRole poblado

.venv/bin/python3 bin/fetch_images.py data/videos/la-2026-07-01-171519/metadata.json
# → 12 assets, 0 fallos, anti-repetición activo (scoring visible en penalties)

.venv/bin/python3 bin/generate_audio.py data/videos/la-2026-07-01-171519/metadata.json
# → 7/7 OK

.venv/bin/python3 bin/prepare_job.py data/videos/la-2026-07-01-171519/metadata.json
# → 12 timeline segments con campos editoriales

.venv/bin/python3 bin/render_job.py data/videos/la-2026-07-01-171519/metadata.json
# → video.mp4 (5.4MB, 45s, 1080x1920)
```

### Comparativa NEW vs OLD

| Métrica | NEW | OLD | Cambio |
|---------|-----|-----|--------|
| Total segments | 12 | 9 | +3 |
| Historical archive | 7 | 4 | +3 |
| B-roll | 4 | 5 | -1 |
| AI reconstruction | 1 | 0 | +1 |
| **Assets repetidos** | **0** | **1** | **-1** |
| Mapas legibles 9:16 | 1 | 0 | +1 |
| Atmospheric transition | 0 (0%) | - | OK |

### Problemas resueltos
1. **Repetición de assets**: 0 assets repetidos (vs 1 en anterior). Anti-repetición penalizó authors repetidos de Wikimedia.
2. **Mapas horizontales**: scene 1 ahora tiene gblur=40 background + crop center + drawbox subtítulos.
3. **B-roll genérico**: reducido de 5 a 4 segmentos. Más archive (7 vs 4).
4. **Reconstrucciones IA**: 1 segmento (pollinations), con noise+grano y saturación reducida.
5. **Diversidad de proveedores**: Wikimedia 7, Pexels 4, Pollinations 1 (vs 3-6 antes).

### Problemas persistentes
1. Scene 6 (7s) y 7 (5s) solo 1 segmento pese a regla ≥2.
2. Scene 7 editorialRole=null — el LLM no lo asignó.
3. Scene 4 generated_reconstruction sigue siendo Pollinations (FreeAI sin API key).
4. Scene 2 dos portrait consecutivos sin variedad de crop/zoom.
5. drawtext overlay de fecha no implementado (requiere libfontconfig).

## Limitaciones

1. Sin visión artificial: la detección de duplicados visuales reales sigue siendo textual.
2. MapReadabilityScore es aproximado (basado en dimensiones, no OCR).
3. La rotación de queries depende del pool manual definido.
4. El LLM sigue sin cumplir la regla ≥2 segmentos para escenas >4s en ~30% de los casos.
5. FreeAI sin API key → generated_reconstruction cae a Pollinations (calidad insuficiente).

## Decisiones

1. El cambio se enfoca en reglas de selección y composición, no en generación de assets nuevos.
2. No se introduce vídeo IA ni visión artificial pesada.
3. El anti-repetición es obligatorio: mismo asset no puede aparecer dos veces sin declaración explícita.
