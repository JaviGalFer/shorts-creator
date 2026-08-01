# Visión del proyecto

## Propósito

Generar vídeos verticales cortos (Shorts/TikTok/Reels) de forma automatizada y configurable, independientes de la temática, con calidad controlada, trazabilidad total y costes predecibles.

La divulgación histórica es un caso de uso posible, no la identidad exclusiva del producto.

## Principios

- Automatización progresiva: empezar con un pipeline semi-automático, eliminar cuellos de botella uno a uno.
- Calidad sobre velocidad: cada vídeo pasa por revisión humana antes de publicación.
- Coste controlado: APIs externas mínimas, priorizar herramientas locales cuando sea viable.
- Trazabilidad: cada vídeo conserva metadata de ejecución. Las bitácoras de desarrollo y los changes OpenSpec se crean cuando el nivel y las reglas de gobernanza del cambio lo requieren.
- Portabilidad: el sistema debe poder ejecutarse en cualquier máquina con Docker y FFmpeg.

## Éxito

- Pipeline funcional que genere un vídeo de duración configurable con guion IA, narración por voz, imágenes de fondo y subtítulos.
- Revisión humana como único gate antes de publicación.
- Capacidad de generar múltiples vídeos variando solo el tema de entrada.
- Documentación suficiente para que una persona retome el proyecto semanas después sin perder contexto.
