# Visual Sequencing and Composition

## Problema

El pipeline actual asigna 1 imagen por escena. Esto provoca:
1. Mapas horizontales ilegibles forzados a 9:16 sin tratamiento
2. Repetición de paisajes/ruinas atmosféricas entre escenas
3. Imágenes IA genéricas sin realismo histórico
4. Falta de relación visual específica entre narración y asset
5. Subtítulos compitiendo con texto contextual

## Solución propuesta

Dividir cada escena en una microsecuencia visual de 1-3 segmentos, cada uno con su propio asset, tratamiento según tipo, y transición.

## Cambios necesarios

- `generate_script.py`: el prompt debe generar `visualSequence` en visualPlan
- `fetch_images.py`: buscar y descargar N assets por escena
- `prepare_job.py`: resolver timeline plano con transiciones
- `render_job.py`: consumir timeline plano, generar vídeo multi-segmento

## No incluye

- Animaciones complejas (flechas, zooms, Ken Burns)
- Visión artificial
- Múltiples capas simultáneas
