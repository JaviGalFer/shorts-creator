# Mejora de Ritmo Narrativo, Subtítulos Sincronizados y Movimiento Visual

## Problema

El vídeo actual ha mejorado en selección editorial, variedad de assets y tratamiento de mapas, pero sigue pareciendo una presentación de PowerPoint con voz encima:

1. Las imágenes cambian por duración fija de escena, no por beats semánticos de la narración.
2. Los subtítulos son frases editoriales genéricas ("Un cambio que alteró la historia"), no representan lo que se dice.
3. Los assets permanecen demasiado tiempo estáticos (0 movimiento).
4. Los cortes y fades no coinciden con palabras clave ni giros narrativos.
5. El CTA final es genérico y repetitivo.

## Solución propuesta

Construir una edición guiada por narración donde la voz sea la fuente de verdad temporal:

- Subtítulos derivados de la narración real con timestamps de edge-tts.
- Beats narrativos por escena que dividen el texto en unidades semánticas.
- Movimiento visual sutil (zoom/pan) por segmento.
- Overlays editoriales separados de subtítulos.
- CTA opcional y breve.
- Cortes y fades sincronizados con beats.

## Cambios necesarios

- `generate_audio.py`: capturar WordBoundary events de edge-tts → subtitleTiming
- `generate_script.py`: añadir narrativeBeats a cada escena
- `prepare_job.py`: consumir subtitleTiming + narrativeBeats → renderTimeline + ASS real
- `render_job.py`: aplicar motion filters, consumir renderTimeline, CTA handling

## No incluye

- Vídeo generado por IA
- Visión artificial pesada
- Dashboard web
- Edición manual con interfaz
- Animaciones complejas tipo After Effects
- Tracking de objetos
- Publicación automática
