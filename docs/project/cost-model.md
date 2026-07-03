# Modelo de costes

## APIs externas (costes variables)

| Servicio | Plan gratuito | Coste estimado por vídeo (45s) | Notas |
|----------|--------------|-------------------------------|-------|
| OpenAI GPT-4o-mini | No | ~$0.01 | Guion ~500-800 tokens |
| ElevenLabs TTS | 10k caracteres/mes | ~$0.005 | Voz ~300-500 caracteres |
| Pexels | 200 requests/hora | Gratuito | ~8 imágenes por vídeo |
| Pixabay | 5000 requests/hora | Gratuito | Fallback de Pexels |

## Costes fijos

- n8n: Gratuito (self-hosted)
- FFmpeg: Gratuito (open source)
- Postgres: Gratuito (Docker)

## Total estimado por vídeo

~$0.015 USD por vídeo en APIs (asumiendo plan de pago de OpenAI y ElevenLabs).

## Control de costes

- Límite de caracteres en guion para controlar tokens LLM.
- Caché de imágenes local para evitar descargas repetidas.
- Logging de coste por trabajo en metadata JSON.
- Alertas manuales si el consumo mensual se desvía de lo esperado.
