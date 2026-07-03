# Tareas: Mejora del pipeline visual histórico

## Fase 1 — Seguridad y documentación base

- [x] Eliminar secretos de HANDOVER.md (CORREGIDO)
- [x] Actualizar docs/project/security.md con reglas de no exposición
- [x] Actualizar AGENTS.md con regla explícita de no escribir secretos en docs
- [x] Crear docs/project/visual-asset-strategy.md
- [x] Actualizar docs/project/integrations.md (nuevos proveedores, estados)
- [x] Crear bitácora de sesión (docs/sessions/)
- [x] Crear OpenSpec (proposal.md, design.md, tasks.md, specs/)

## Fase 2 — Modelo de datos y generate_script.py

- [x] Crear bin/generate_script.py (CLI, --topic, --dry-run, lee .env)
- [x] Prompt incluye visualPlan con estrategias, searchQueries, preferredSources
- [x] Mantener compatibilidad: visualPrompt + imagePrompt legacy
- [x] Script genera metadata.json completo en data/videos/{jobId}/

## Fase 3 — Sourcing, scoring y fetch_images.py

- [x] Centralizar SCORING_WEIGHTS como dict configurable
- [x] Implementar búsqueda multi-proveedor (Wikimedia, Pexels, FreeAI, Pollinations)
- [x] Implementar evaluación de 3-5 candidatas por escena
- [x] Implementar scoring explicable con razones
- [x] Implementar selección de candidata principal
- [x] Guardar metadata completa de assets (provider, URL, licencia, score)
- [x] Guardar candidatas descartadas con motivo
- [x] Implementar cadena de fallback por estrategia
- [x] Mantener compatibilidad: jobs sin visualPlan usan visualPrompt

### Mejoras adicionales implementadas

- [x] Rate limiting conservador para Wikimedia (5 requests/12s, backoff en 429)
- [x] Cache de queries por proveedor (evita re-request)
- [x] User-Agent identificable configurable
- [x] Pausas entre requests (0.6s entre info API calls, 0.5s entre escenas)
- [x] Logging de fallos por proveedor con razón específica
- [x] Adaptación de queries por proveedor:
  - Wikimedia/Library: searchQueries históricas
  - Pexels/Pixabay: queries visuales genéricas según estrategia (STRATEGY_VISUAL_QUERIES)
  - FreeAI: imageGenerationPrompt + negativePrompt
  - Pollinations: visualPrompt/imagePrompt
- [x] Metadata extendida por escena: providerAttemptOrder, providerFailures, fallbackApplied, fallbackReason, candidateCount, selectedCandidateScore

## Fase 4 — Validación

### Validación de scripts individuales
- [x] `generate_script.py --dry-run` — Funciona, muestra prompts correctamente
- [x] `generate_script.py` real — Genera script con visualPlan (10 escenas)
- [x] `fetch_images.py` con visualPlan — Búsqueda multi-proveedor, scoring, metadata completa
- [x] `fetch_images.py` legacy (franco5) — Compatibilidad backward
- [x] `generate_audio.py` con edge-tts vía venv — Audio generado para 10 escenas
- [x] `prepare_job.py` — Subtítulos ASS generados, merge de metadata
- [x] `render_job.py` — Render Docker FFmpeg completado

### Validación legacy
- [x] Test: franco5 (10 escenas, sin visualPlan) — Renderizado completo (53s MP4)
- [x] Test: hist-181103 (6 escenas, formato transicional) — Assets descargados
- [x] Compatibilidad prepare_job.py con metadata legacy — Merge correcto (bug corregido)
- [x] Bug: prepare_job.py sobrescribía assets — Corregido (mergea preservando campos)

### Validación end-to-end de job nuevo
- [x] Job: `la-2026-07-01-144559` — "La caída de Constantinopla"
- [x] generate_script.py → script con visualPlan (10 escenas, múltiples estrategias)
- [x] fetch_images.py → 4 de Wikimedia, 4 de Pexels, 2 Pollinations
- [x] generate_audio.py → edge-tts es-ES-AlvaroNeural, 10/10 OK
- [x] prepare_job.py → subtítulos ASS, metadata preservada
- [x] render_job.py → video.mp4 (4.8MB, ~60s)
- [x] Estado final: RENDERED
- [x] Metadata completa: providerAttemptOrder, providerFailures, fallbackReason, candidateCount, scoreReasons, discardedCandidates

### Bugs encontrados y corregidos en validación

| # | Archivo | Bug | Fix |
|---|---------|-----|-----|
| 1 | `bin/fetch_images.py` | "exists" shortcut retornaba metadata mínima | Ahora siempre procesa scoring, salta solo descarga |
| 2 | `bin/prepare_job.py` | Sobrescribía assets array rico con entries mínimos | Mergea preservando campos existentes |
| 3 | `bin/render_job.py` | `parents[2]` → montaba `data/` en vez de raíz | Cambiado a `parents[3]` |
| 4 | `bin/render_job.py` | Docker API version 1.43 obsoleta | Actualizado a 1.44 |
| 5 | `bin/fetch_images.py` | No cargaba `.env` → API keys no disponibles | Añadida carga de .env al inicio |

## Fase 5 — Informe final

- [x] Documentar resultados reales
- [x] Documentar limitaciones encontradas
- [x] Listar próximas mejoras recomendadas

---

## Informe final: Pipeline visual evolucionado

### Resultados del job end-to-end `la-2026-07-01-144559`

| Escena | Estrategia | Proveedor | Score | Calidad |
|--------|-----------|-----------|-------|---------|
| 1 | generated_reconstruction | Pollinations | 15 | INSUFICIENTE - IA genérica (FreeAI sin key) |
| 2 | historical_archive (map) | Wikimedia Commons | 40 | BUENA - Mapa histórico real CC BY-SA |
| 3 | historical_archive (portrait) | Wikimedia Commons | 65 | BUENA - Retrato histórico real, Public Domain |
| 4 | historical_archive (document) | Wikimedia Commons | 5 | ACEPTABLE - Documento histórico, baja resolución |
| 5 | atmospheric_broll | Pexels | 35 | ACEPTABLE - Foto stock visualmente correcta |
| 6 | generated_reconstruction | Pollinations | -15 | INSUFICIENTE - IA genérica (FreeAI sin key) |
| 7 | atmospheric_broll | Pexels | 5 | ACEPTABLE - Foto stock |
| 8 | map_or_document (map) | Wikimedia Commons | 20 | BUENA - Mapa histórico real CC0 |
| 9 | atmospheric_broll | Pexels | 35 | ACEPTABLE - Foto stock |
| 10 | atmospheric_broll | Pexels | 35 | ACEPTABLE - Foto stock |

**Totales:**
- 4 escenas con archivo histórico real (Wikimedia Commons) — 40%
- 4 escenas con B-oll de stock (Pexels) — 40%
- 2 escenas con IA genérica (Pollinations) — 20% (debieran ser FreeAI)

### Limitaciones encontradas

1. **FREEAI_API_KEY no configurada** — Las 2 escenas `generated_reconstruction` caen a Pollinations (IA genérica de baja calidad) en vez de usar FLUX Schnell.
2. **Scoring sin visión artificial** — No se puede evaluar calidad visual real, solo metadata textual. Una foto de stock de Pexels con título genérico puntúa igual que una de Wikimedia con título detallado.
3. **Pollinations calidad baja** — 576x1024, sin control de estilo, imágenes genéricas sin valor documental.
4. **Atmospheric broll desde Pexels** — Las 4 escenas de Pexels son del mismo autor (James Frid) porque las queries visuales genéricas devuelven resultados consistentes pero poco variados.
5. **Formato bootstrap sin sceneNumber no soportado** — hist-175447 queda como legacy no migrable.

### Próximas mejoras recomendadas

1. **Obtener FREEAI_API_KEY** — Prioridad máxima. Las escenas `generated_reconstruction` pasarían de Pollinations (score -15/15) a FLUX Schnell con control de estilo.
2. **Mejorar variedad de queries Pexels/Pixabay** — Rotar entre múltiples queries visuales para cada escena, no elegir siempre la primera.
3. **Añadir visión artificial para scoring** — Evaluar si la imagen contiene elementos relevantes (personas, mapas, texto, etc.) mediante clasificación básica.
4. **Añadir evaluación de calidad post-render** — Revisar el video.mp4 generado y permitir approve/reject por escena.
5. **Instalar edge-tts documentado** — Comando reproducible: `.venv/bin/pip install -r requirements.txt`
