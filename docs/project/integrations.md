# Integraciones

Cada integración tiene un estado de validación: `VALIDADO`, `PENDIENTE_DE_VALIDAR` o `DESCARTADO`.

---

## Proveedor LLM (guion + visualPlan)

- **Estado**: `VALIDADO`
- **Opciones**: OpenAI GPT-4o-mini, Anthropic Claude Haiku, Google Gemini Flash
- **Método**: API REST configurable vía `LLM_PROVIDER`
- **Credenciales**: API Key en `.env`
- **Límites**: Depende del proveedor
- **Validación actual**: workflow `generate-script-v1` ejecutado con OpenAI real. Script `bin/generate_script.py` creado.

## Edge TTS (narración)

- **Estado**: `VALIDADO`
- **URL**: vía librería `edge-tts` (Python)
- **Método**: local, gratuito, sin API key
- **Voz**: `es-ES-AlvaroNeural` (español de España)
- **Dependencia**: `pip install edge-tts`
- **Alternativa**: ElevenLabs (plan gratuito solo voces inglés, las españolas requieren plan pago)
- **Validación actual**: `bin/generate_audio.py` probado con éxito

## n8n self-hosted

- **Estado**: `VALIDADO`
- **URL**: http://localhost:5679
- **Método**: Docker Compose
- **Credenciales**: N8N_ENCRYPTION_KEY
- **Workflows exportados**: JSON en raíz del proyecto

## FFmpeg (render local)

- **Estado**: `VALIDADO`
- **Método**: Contenedor Docker `linuxserver/ffmpeg`
- **Credenciales**: Ninguna
- **Límites**: CPU/GPU local
- **Validación actual**: `bin/render_job.py` probado con ASS y SRT

## Pexels (imágenes)

- **Estado**: `VALIDADO`
- **URL**: https://www.pexels.com/api/
- **Método**: REST API
- **Credenciales**: API Key en `.env`
- **Límites**: 200 requests/hora en plan gratuito
- **Atribución**: No requerida
- **Uso**: atmospheric_broll, fallback para archive
- **Validación actual**: workflow `fetch-assets-v1` ejecutado con éxito

## Pixabay (imágenes)

- **Estado**: `VALIDADO`
- **URL**: https://pixabay.com/api/docs/
- **Método**: REST API
- **Credenciales**: API Key en `.env`
- **Límites**: 5000 requests/hora en plan gratuito
- **Atribución**: No requerida
- **Uso**: atmospheric_broll, fallback

## Wikimedia Commons (imágenes históricas)

- **Estado**: `VALIDADO`
- **URL**: https://commons.wikimedia.org/w/api.php
- **Método**: REST API (sin API key)
- **Credenciales**: Ninguna
- **Límites**: Rate limit no documentado (429 observado tras ~10 requests rápidas)
- **Licencias**: Variable (Public Domain, CC0, CC-BY, CC-BY-SA)
- **Atribución**: Requerida según licencia
- **Uso**: historical_archive, map_or_document
- **Riesgos**: Rate limiting, calidad variable, atribución requerida

## FreeAI (imágenes generadas)

- **Estado**: `PENDIENTE_DE_VALIDAR`
- **URL**: https://api.free.ai/v1/image/generate/
- **Método**: POST, OpenAI-compatible
- **Credenciales**: `FREEAI_API_KEY` en `.env`
- **Límites**: 30K tokens/día gratis (30+ imágenes)
- **Modelos**: flux-schnell (gratis), sdxl, premium/flux-pro
- **Atribución**: No requerida
- **Uso**: generated_reconstruction, fallback

## Pollinations (imágenes generadas, último fallback)

- **Estado**: `VALIDADO` (pero baja calidad)
- **URL**: https://image.pollinations.ai/
- **Método**: HTTP GET sin API key
- **Credenciales**: Ninguna
- **Límites**: ~1 req/sec, rate-limited (429)
- **Atribución**: No requerida
- **Uso**: Último fallback cuando todo falla
- **Riesgos**: Calidad baja, rate limiting, imágenes irrelevantes
