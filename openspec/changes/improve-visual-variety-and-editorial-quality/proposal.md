# Mejora de Variedad Visual, Tratamiento de Mapas y Calidad Editorial

## Problema

El pipeline multi-segmento funciona (9 segmentos, 7 escenas, transiciones cut/fade), pero el vídeo generado presenta problemas observables:

1. **Repetición de assets**: mismo paisaje de ruinas/cielo aparece en escenas distintas sin justificación editorial.
2. **Mapas horizontales ilegibles**: forzados a 9:16 sin crop a región relevante, textos y leyendas ininteligibles.
3. **B-roll genérico**: escenas clave (asedio, batalla) cubiertas con "ruinas bonitas" en vez de recursos históricos específicos.
4. **Reconstrucciones IA con estética fantasía/videojuego**: sin realismo documental.
5. **Retratos sin valor informativo**: misma imagen repetida sin crop/zoom/overlay.
6. **Same-provider saturation**: Pexels mismo autor múltiples veces por vídeo.

## Solución propuesta

Introducir un sistema de reglas editoriales por escena, anti-repetición obligatorio, tratamiento específico de mapas y retratos en render, mejora de prompts IA, y rotación forzada de queries/proveedores.

## Cambios necesarios

- `generate_script.py`: añadir `editorialRole` al visualPlan
- `fetch_images.py`: scoring con anti-repetición, penalización por autor repetido, rotación de queries
- `render_job.py`: crop a región relevante en mapas, overlay de fecha/lugar, blur background, reserva de subtítulos
- `prepare_job.py`: propagar nuevos campos editoriales

## No incluye

- Vídeo generado por IA
- Visión artificial para detección de duplicados visuales reales
- OCR para mapReadabilityScore (aproximado por dimensiones)
- Ken Burns o animaciones de cámara
- Múltiples capas simultáneas
