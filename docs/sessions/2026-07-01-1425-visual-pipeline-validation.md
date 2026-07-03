# Sesión: Validación del pipeline visual evolucionado

**Fecha:** 2026-07-01  
**Cambio OpenSpec:** `openspec/changes/improve-historical-visual-pipeline/`  
**Agente:** @video-pipeline-engineer + @quality-and-ops-reviewer  
**Duración:** ~2h

## Resumen

Validación completa de los scripts evolucionados (generate_script.py, fetch_images.py, prepare_job.py, render_job.py). Se corrigieron 4 bugs durante la validación.

## Qué se hizo

### Fase 4 — Validación

1. **generate_script.py --dry-run** — Verificado, muestra prompts correctamente
2. **generate_script.py real** — Llamada a OpenAI gpt-4o-mini generó script de 7 escenas con visualPlan completo
3. **fetch_images.py con visualPlan** — Descargó imágenes para las 7 escenas, metadata completa, scoring funcional
4. **fetch_images.py legacy (franco5)** — Compatibilidad backward, 10 escenas desde Pollinations
5. **fetch_images.py legacy (hist-181103)** — Formato transicional (con sceneNumber, sin visualPlan) funciona
6. **fetch_images.py muy antiguo (hist-175447)** — CRASHEA (formato bootstrap sin sceneNumber)
7. **prepare_job.py** — Subtítulos ASS/SRT generados, metadata mergea correctamente
8. **render_job.py** — Render Docker FFmpeg completado para franco5 (53s, 3MB)

### Bugs corregidos

| # | Archivo | Bug | Fix |
|---|---------|-----|-----|
| 1 | `bin/fetch_images.py:350` | "exists" shortcut retornaba metadata mínima sin provider/score | Ahora siempre procesa scoring y salta solo descarga |
| 2 | `bin/prepare_job.py:131` | Sobrescribía assets array rico con entries mínimos | Mergea preservando campos existentes |
| 3 | `bin/render_job.py:77` | `parents[2]` → montaba `data/` en vez de raíz proyecto | Cambiado a `parents[3]` |
| 4 | `bin/render_job.py:81` | Docker API version 1.43 obsoleta | Actualizado a 1.44 |

### Limitaciones encontradas

- Todos los assets van a Pollinations (calidad baja) — Wikimedia rate-lockea, FreeAI sin key, Pexels/Pixabay queries no óptimas
- Formato bootstrap (hist-175447, sin sceneNumber) incompatible
- edge-tts no instalable (pip no disponible)
- Pollinations lento (10-30s por imagen)

### Jobs creados/afectados

- `la-2026-07-01-142511` — Nuevo job con visualPlan (La caída de Constantinopla, 7 escenas)
- `franco5-2026-06-30-204654` — Renderizado completo (53s MP4)
- `hist-2026-06-30-181103` — Legacy actualizado con metadata completa

### Decisiones

1. El formato bootstrap (sin sceneNumber) queda como no soportado. Los jobs existentes con ese formato (hist-175447, hist-181103 con variante) no se migrarán activamente.
2. Se prioriza conseguir FreeAI API key como siguiente paso para mejorar calidad visual.
3. Pollinations se mantiene como último fallback pero documentado como calidad insuficiente.

## Próximos pasos

1. Configurar `FREEAI_API_KEY` en `.env`
2. Instalar edge-tts: `pip install edge-tts`
3. Optimizar queries de búsqueda para Pexels/Pixabay (strategy→query templates)
4. Añadir rate-limit handling con backoff para Wikimedia Commons
