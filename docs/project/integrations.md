# Integraciones

Cada integración tiene un estado de validación: `VALIDADO`, `PENDIENTE_DE_VALIDAR` o `DESCARTADO`.

> **Orquestador canónico:** `bin/run_job.py` es el orquestador del pipeline vigente
> (`script → assets → audio → prepare → render → validate`). n8n es infraestructura
> **legacy o alternativa**, no el pipeline canónico.

---

## Proveedor LLM (guion + visualPlan)

- **Estado**: `VALIDADO`
- **Opciones**: OpenAI GPT-4o-mini (cliente OpenAI-compatible). Anthropic/Google como opciones declaradas pero no verificadas como clientes implementados.
- **Método**: API REST configurable vía `LLM_PROVIDER` (solo se implementa un cliente OpenAI-compatible).
- **Credenciales**: `LLM_API_KEY` en `.env`
- **Límites**: Depende del proveedor
- **Pipeline vigente**: `bin/generate_script.py` (invocado por `bin/run_job.py`).
- **Evidencia histórica**: el workflow n8n `generate-script-v1` (legacy) se ejecutó con OpenAI real durante el desarrollo; no forma parte del pipeline vigente.

## Edge TTS (narración)

- **Estado**: `VALIDADO`
- **URL**: vía librería `edge-tts` (Python)
- **Método**: cliente Python del servicio Microsoft Edge TTS, sin API key. Se ejecuta desde el entorno local, requiere conectividad de red y no es síntesis offline ni un modelo TTS autoalojado.
- **Voz**: `es-ES-AlvaroNeural` (español de España)
- **Dependencia**: `pip install edge-tts`
- **Pipeline vigente**: `bin/generate_audio.py`; `edge_tts` es el TTS por defecto (`TTS_PROVIDER=edge_tts`).

## ElevenLabs (narración, alternativa opcional)

- **Estado**: `VALIDADO` para el runtime TTS per-scene. Timing nativo `/with-timestamps` con normalización de alineamiento char→word; smoke real PASSED (`ELEVENLABS_REAL_SMOKE_OK`, voz `Xb7hH8MSUJpSbSDYk0k2`, 3.84s); E2E canónico `cmo-2026-08-17-145309` VALIDADO (28.20s, `elevenlabs_normalized_alignment`). El modo continuo NO es compatible con ElevenLabs. No es el TTS canónico.
- **Método**: API REST; `POST /v1/text-to-speech/{voice_id}/with-timestamps` con normalización char→word a `word_boundaries` canónicas.
- **Credenciales**: `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL_ID` en `.env`
- **Pipeline vigente**: solo se usa cuando `TTS_PROVIDER=elevenlabs` vía `bin/generate_audio.py` (`src/shorts_creator/audio/tts_provider.py`). No es el TTS canónico.
- **Config runtime**: la resolución efectiva (provider, voz, modelo, credenciales) está en `src/shorts_creator/audio/generator.py`. Precedencia de voz: `--voice`/request → `ELEVENLABS_VOICE_ID` (para `elevenlabs`) → `TTS_VOICE` (genérico) → default del provider. `ELEVENLABS_VOICE_ID` gana sobre la voz por defecto de Edge (`es-ES-AlvaroNeural`) cuando el provider es `elevenlabs`; el API key nunca se persiste en metadata.
- **Nota**: plan gratuito con voces españolas limitadas.

## n8n self-hosted (infraestructura legacy o alternativa)

- **Estado**: `VALIDADO` (infraestructura operativa)
- **URL**: http://localhost:5679
- **Método**: Docker Compose
- **Credenciales**: `N8N_ENCRYPTION_KEY`
- **Workflows exportados**: JSON en la raíz del proyecto (`workflow-*.json`), todos legacy (`*-v1`).
- **Rol**: no es el orquestador canónico. Solo documentado como alternativa manual. Ver `docs/runbooks/n8n-operations.md`.

## FFmpeg (render local)

- **Estado**: `VALIDADO`
- **Método**: Contenedor Docker `linuxserver/ffmpeg`
- **Credenciales**: Ninguna
- **Límites**: CPU/GPU local
- **Pipeline vigente**: `bin/render_job.py` probado con ASS y SRT.

## Wikimedia Commons (imágenes)

- **Estado**: `VALIDADO` (proveedor visual implementado y activo)
- **URL**: https://commons.wikimedia.org/w/api.php
- **Método**: REST API (sin API key)
- **Credenciales**: Ninguna
- **Límites**: Rate limit no documentado (429 observado tras ~10 requests rápidas)
- **Licencias**: Variable (Public Domain, CC0, CC-BY, CC-BY-SA)
- **Atribución**: Requerida según licencia
- **Uso**: archive / map_or_document
- **Riesgos**: Rate limiting, calidad variable, atribución requerida

## Pixabay (imágenes)

- **Estado**: `VALIDADO` (proveedor visual implementado y activo)
- **URL**: https://pixabay.com/api/docs/
- **Método**: REST API
- **Credenciales**: `PIXABAY_API_KEY` en `.env`
- **Límites**: 5000 requests/hora en plan gratuito
- **Atribución**: No requerida
- **Uso**: b-roll de stock

## Pexels Photos (imágenes)

- **Estado**: `DISPONIBLE` como provider IMAGE/STOCK explícito; no es default.
- **URL**: https://www.pexels.com/api/
- **Método**: REST API
- **Credenciales**: `PEXELS_API_KEY` en `.env` o process env; nunca se persiste.
- **Límites**: 200 requests/hora en plan gratuito
- **Atribución**: conservar fotógrafo, perfil y URL de la foto para crédito futuro; la UI no forma parte de este change.
- **Rol actual**: disponible solo mediante `request.visuals.sourceProviders` o `--asset-providers pexels`; el orden explícito se conserva.
- **Selección**: `PROVISIONAL_BM25`, explícitamente `NOT VALIDATED`; solo ordena intentos. Los gates semántico y pixel siguen siendo la autoridad.
- **Fuera de alcance**: Pexels Video, adaptación de query y pagination adicional.

## FreeAI (imágenes generadas, deshabilitado)

- **Estado**: `PENDIENTE_DE_VALIDAR` — **deshabilitado y no implementado** en el pipeline vigente.
- **URL**: https://api.free.ai/v1/image/generate/
- **Método**: POST, OpenAI-compatible
- **Credenciales**: `FREEAI_API_KEY` (sin contrato de variable activo)
- **Modelos**: flux-schnell (gratis), sdxl, premium/flux-pro
- **Rol actual**: proveedor deshabilitado en `bin/visual_provider_config_v2.py` con `enabled=false, implemented=false`.

## Pollinations (imágenes generadas, deshabilitado)

- **Estado**: `PENDIENTE_DE_VALIDAR` — **deshabilitado y no implementado** en el pipeline vigente.
- **URL**: https://image.pollinations.ai/
- **Método**: HTTP GET sin API key
- **Credenciales**: Ninguna
- **Rol actual**: proveedor deshabilitado en `bin/visual_provider_config_v2.py` con `enabled=false, implemented=false`. Antes actuaba como fallback de baja calidad; no es provider activo del pipeline vigente.
