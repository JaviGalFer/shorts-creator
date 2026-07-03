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

## Riesgos

- Rate limits de Wikimedia Commons (429)
- Licencias no verificables en algunos resultados
- Calidad variable de resultados de búsqueda
