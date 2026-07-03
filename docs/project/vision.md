# Visión del proyecto

## Propósito

Generar vídeos verticales cortos (Shorts/TikTok/Reels) de divulgación histórica de forma automatizada, con calidad controlada, trazabilidad total y costes predecibles.

## Principios

- Automatización progresiva: empezar con un pipeline semi-automático, eliminar cuellos de botella uno a uno.
- Calidad sobre velocidad: cada vídeo pasa por revisión humana antes de publicación.
- Coste controlado: APIs externas mínimas, priorizar herramientas locales cuando sea viable.
- Trazabilidad: cada vídeo tiene un JSON de metadata, una bitácora y un cambio OpenSpec asociado.
- Portabilidad: el sistema debe poder ejecutarse en cualquier máquina con Docker y FFmpeg.

## Éxito

- Pipeline funcional que genere un vídeo de 30-60s con guion IA, narración ElevenLabs, imágenes de fondo y subtítulos.
- Revisión humana como único gate antes de publicación.
- Capacidad de generar múltiples vídeos variando solo el tema de entrada.
- Documentación suficiente para que una persona retome el proyecto semanas después sin perder contexto.
