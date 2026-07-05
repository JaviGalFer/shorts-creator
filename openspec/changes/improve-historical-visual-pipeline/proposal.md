# Propuesta: Mejora del pipeline visual histórico

## Problema actual

Las imágenes del pipeline son pobres, genéricas y poco históricas:
- Una sola imagen por escena sin criterio editorial
- Sin metadata de fuente, licencia o score
- Sin estrategia de selección según el tipo de contenido
- Dependencia excesiva de Pollinations.ai (baja calidad, rate-limited)
- Sin capacidad de evaluar múltiples candidatas

## Impacto en calidad

Los vídeos parecen presentaciones de imágenes IA genéricas, no mini documentales históricos.

## Solución propuesta

Evolucionar el pipeline visual con:
1. Nuevo contrato `visualPlan` por escena (estrategia, búsquedas, fuentes preferidas)
2. Sistema de sourcing multi-proveedor con cadena de fallback
3. Búsqueda y evaluación de múltiples candidatas por escena (3-5)
4. Sistema de scoring explicable sin visión artificial
5. Metadata completa de assets (provider, URL, licencia, score, razones)
6. Script CLI `generate_script.py` que genera guion + visualPlan
7. Mantener compatibilidad total con jobs legacy

## Alcance

- Seguridad: eliminar secretos de documentación, actualizar reglas
- Modelo de datos: `visualPlan` como campo opcional en escenas
- Sourcing: Wikimedia Commons, Pexels, Pixabay, FreeAI, Pollinations como fallback
- Scoring: basado en metadata, sin modelos de visión
- Metadata de assets: provider, sourceUrl, license, score, queryUsed, scoreReasons
- Múltiples candidatas: buscar 3-5, evaluar, descartar, guardar la mejor
- Compatibilidad: jobs sin visualPlan siguen funcionando con visualPrompt como fallback

## Fuera de alcance

- Render multicapa (2+ assets por escena)
- Transiciones intra-escena (Ken Burns, zoom, pan)
- Visión artificial para evaluar imágenes
- Publicación automática
- Dashboard web

## Criterios de éxito

1. Jobs legacy sin visualPlan siguen renderizando
2. Nuevos jobs con visualPlan seleccionan imágenes con metadata completa
3. Sistema intenta fuentes históricas antes que IA
4. Assets guardan provider, sourceUrl, license, score y scoreReasons
5. Múltiples candidatas evaluadas por escena
6. Al menos un vídeo de prueba renderizado exitosamente
7. Sin secretos en documentación

## Fase 17 — Validación semántica hard de assets históricos

### Problema

El pipeline podía seleccionar assets semánticamente incorrectos para escenas históricas:
- Escenas `context_map` recibían fotografías ordinarias en lugar de mapas/documentos.
- Escenas `event_depiction` reutilizaban assets de años incorrectos (ej. foto de 1961 para una escena sobre la caída de 1989).
- Assets de aniversarios recientes ("35th anniversary") se clasificaban como contexto archivístico en vez de legado moderno.
- La reutilización de assets no verificaba el año explícito de la escena cuando el periodo no lo contenía.

### Solución

1. **Hard rule `context_map`**: verificar `visualPlan.primaryAssetType` contra un conjunto de tipos permitidos (`map`, `historical_map`, `document`, `newspaper`, `map_or_document`, `historical_map_or_document`).
2. **Hard rule `event_depiction`**: rechazar assets cuyo `assetTemporalMatch` sea `unknown` o `modern_legacy`.
3. **`assetTemporalMatch` mejorado**:
   - Matching sin acentos y multilingüe (español → inglés/alemán).
   - Extracción de año desde `period`, `entities` y `voiceover`.
   - Periodo "Post-Guerra Fría" mapeado a "fall of the Berlin Wall" / 1989.
   - Indicadores modernos (`anniversary`, `celebration`) priorizados sobre coincidencia de periodo cuando no hay año de evento.
4. **Reutilización segura**:
   - Bloquear reúso para `event_depiction` si el asset reusado es `modern_legacy` o `unknown`.
   - Extraer años del `voiceover` actual para detectar mismatch (ej. 1961 vs 1989).
   - Re-evaluar `assetTemporalMatch` en el contexto de la escena destino.
   - Preservar `title`/`description` en `asset_meta` para que el matching funcione en cadenas de reuso.
5. **Queries históricas para `event_depiction`**: generar queries históricas incluso para roles no hard cuando el intent temporal es `event_depiction`, evitando quedarse con queries genéricas como "Berlin Wall fall celebrations".

### Criterios de éxito

- Job `validation-realistic-berlin-wall-v5-assets-*` alcanza `ASSETS_READY` sin render.
- Escena 1 obtiene un mapa histórico real.
- Escena 4 obtiene un asset de 1989 (no reutiliza el asset de 1961 de la escena 3).
- Todos los tests de `tests/test_semantic_asset_validation.py` pasan.

## Riesgos

- Rate limits de Wikimedia Commons (429)
- Licencias no verificables en algunos resultados
- Calidad variable de resultados de búsqueda
