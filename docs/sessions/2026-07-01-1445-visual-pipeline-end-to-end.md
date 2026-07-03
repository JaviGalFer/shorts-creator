# Sesión: Pipeline visual end-to-end + validación completa

**Fecha:** 2026-07-01  
**Cambio OpenSpec:** `openspec/changes/improve-historical-visual-pipeline/`  
**Duración:** ~3h

## Resumen

Validación completa del pipeline end-to-end con un job nuevo generado desde cero hasta RENDERED. Se implementaron mejoras adicionales solicitadas: venv local para edge-tts, rate limiting para Wikimedia, adaptación de queries por proveedor, metadata extendida de fallos, e informe comparativo de calidad visual.

## Entorno virtual

```bash
# Reproducible:
python3 -m pip install --user virtualenv    # si no hay pip
python3 -m virtualenv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python3 bin/generate_audio.py <metadata>
```

El archivo `requirements.txt` se generó desde el venv con `pip freeze`.

## Mejoras implementadas en fetch_images.py

### 1. Rate limiting Wikimedia Commons
- Máximo 5 requests por ventana de 12 segundos (`WikimediaRateLimiter`)
- Pausa de 0.6s entre info API calls
- Cache por query (`_wikimedia_cache`) evita re-request
- User-Agent identificable: `ShortsHistoricos/1.0 (...)`
- En 429, espera 5s y reintenta una vez

### 2. Adaptación de queries por proveedor
- `resolve_queries_for_provider()` define queries distintas según el proveedor:
  - Wikimedia Commons: searchQueries históricas del visualPlan
  - Pexels/Pixabay: queries visuales genéricas desde `STRATEGY_VISUAL_QUERIES` (e.g. "old map historical", "candlelight dark room", "ancient manuscript")
  - FreeAI: imageGenerationPrompt + negativePrompt
  - Pollinations: visualPrompt/imagePrompt

### 3. Metadata extendida por escena
- `providerAttemptOrder`: orden de proveedores intentados
- `providerFailures`: lista con razón específica de cada fallo ("freeai: no API key (FREEAI_API_KEY)", "pexels returned 0 results")
- `fallbackApplied`: qué proveedor se usó realmente
- `fallbackReason`: por qué se usó el fallback
- `candidateCount`: total de candidatos evaluados
- `selectedCandidateScore`: score del seleccionado

### 4. Carga de .env
- fetch_images.py ahora carga `.env` (antes solo usaba `os.environ`, lo que dejaba las API keys sin efecto)

## Resultado end-to-end: job `la-2026-07-01-144559`

### Pipeline ejecutado

```bash
# 1. Generar script
python3 bin/generate_script.py --topic "La caída de Constantinopla"
# → 10 escenas con visualPlan

# 2. Descargar assets
python3 bin/fetch_images.py data/videos/la-2026-07-01-144559/metadata.json
# → 4 Wikimedia, 4 Pexels, 2 Pollinations

# 3. Generar audio (con venv)
.venv/bin/python3 bin/generate_audio.py data/videos/la-2026-07-01-144559/metadata.json
# → 10/10 OK, voz es-ES-AlvaroNeural

# 4. Preparar subtítulos
python3 bin/prepare_job.py data/videos/la-2026-07-01-144559/metadata.json
# → subtitle.ass, metadata mergeado

# 5. Renderizar
python3 bin/render_job.py data/videos/la-2026-07-01-144559/metadata.json
# → video.mp4 (4.8MB, ~60s, 1080x1920)
```

### Distribución de proveedores

| Proveedor | Escenas | Calidad |
|-----------|---------|---------|
| Wikimedia Commons | 2, 3, 4, 8 | BUENA - 4 escenas con archivo histórico real |
| Pexels | 5, 7, 9, 10 | ACEPTABLE - Fotos de stock visualmente correctas |
| Pollinations | 1, 6 | INSUFICIENTE - IA genérica (FreeAI sin API key) |

### Bugs corregidos en esta sesión
1. fetch_images.py no cargaba `.env` → API keys nunca se usaban (añadida carga de .env)
2. prepare_job.py sobrescribía assets → merge preserva metadata
3. render_job.py path incorrecto → parents[3] en vez de parents[2]
4. render_job.py Docker API version obsoleta → 1.43→1.44
5. fetch_images.py "exists" shortcut perdía metadata → siempre procesa scoring

### Limitaciones

1. **FREEAI_API_KEY no configurada** → 2 escenas `generated_reconstruction` caen a Pollinations
2. **Scoring sin visión artificial** → solo textual, no evalua calidad visual real
3. **Pexels mismo autor** → 4 escenas de James Frid por queries no variadas
4. **Formato bootstrap sin sceneNumber** → no soportado (hist-175447)

## Decisiones

1. El cambio OpenSpec `improve-historical-visual-pipeline` se considera **completado**. Faltan mejoras (FreeAI key, variedad de queries) pero son issues independientes.
2. `requirements.txt` en raíz define dependencias del venv. Comando reproducible documentado.
3. Pollinations se mantiene como fallback técnico pero no debe considerarse calidad validada.
