# Sesión: retire-legacy-visual-v1-slice-5a

## Configuración

- **Sesión:** `retire-legacy-visual-v1-slice-5a-build`
- **Modelo:** `opencode/big-pickle`
- **Variante:** `default`
- **Modo:** `Build`
- **MCP:** desactivado
- **Llamadas MCP:** 0

## Estado Git inicial

```
Repositorio: /home/javi/projects/shorts-creator
Rama:       main
HEAD:       f8bd4f2900f964df6529aa136d9e78f58ec9baa7
Working tree: limpio
```

## Objetivo de Slice 5A

Implementar la limpieza de identidad de producto y arquitectura:
- README como entrada genérica al proyecto
- Arquitectura actual separada del roadmap futuro
- Roadmap modular actualizado con progreso real
- OpenSpec tasks reestructuradas en Slice 5A/5B
- current-state.md actualizado con Slice 5A implementado
- Session log de la implementación

## Fuentes de verdad utilizadas

| Contrato | Fuente directa | Resultado |
|----------|---------------|-----------|
| Orquestador | `bin/run_job.py` | `bin/run_job.py` es el orquestador canónico |
| Pipeline | `bin/run_job.py` L26 | script → assets → audio → prepare → render → validate |
| Scripts | `bin/run_job.py` L28-33, L148-154 | `generate_script.py`, `fetch_images_v2.py`, `generate_audio.py`, `prepare_job.py`, `render_job.py`, `validate_job.py` |
| Paths visuales V2 | `bin/run_job.py` L278-282 | `assets/` con extensiones V2_IMAGE_EXTENSIONS |
| TTS canónico | `bin/generate_audio.py --help` | edge_tts (default), elevenlabs secundario |
| Wikimedia | `bin/visual_provider_config_v2.py` L18-24 | Activo, implementado, sin API key |
| Pixabay | `bin/visual_provider_config_v2.py` L31-37 | Activo, implementado, requiere `PIXABAY_API_KEY` |
| Pexels | `bin/visual_provider_config_v2.py` L25-30 | Planificado, deshabilitado, no implementado |
| FreeAI | `bin/visual_provider_config_v2.py` L38-43 | Deshabilitado, no implementado |
| Pollinations | `bin/visual_provider_config_v2.py` L44-48 | Deshabilitado, no implementado |
| n8n | `docker-compose.yml`, workflow files | Servicio Docker, workflows legacy, NO orquestador canónico |
| `src/shorts_creator/` | `test -d` | No existe |
| `pyproject.toml` | `test -f` | No existe |
| `review_job.py` | `test -f` | No existe |
| `visual_normalize.py` | `test -f` + `rg -n callers` | Existe pero sin callers |

## Archivos modificados

1. `README.md`
2. `docs/project/architecture.md`
3. `docs/architecture/modular-v2-transformation-roadmap.md`
4. `docs/project/current-state.md`
5. `openspec/changes/retire-legacy-visual-v1/tasks.md`

## Archivos creados

1. `docs/sessions/20260730-214000-retire-legacy-visual-v1-slice-5a.md`

## Cambios realizados

### README.md

- Identidad genérica: educativa, explicativa, divulgativa, histórica y otros temas
- Estado del proyecto: evolución activa, no producto final
- Capacidades actuales enumeradas
- Pipeline canónico documentado con tabla de etapas
- `bin/run_job.py` como orquestador canónico
- Inicio rápido con requisitos reales
- Configuración de TTS y subtítulos
- Providers visuales clasificados por estado real
- Arquitectura actual con paths `assets/`
- Arquitectura futura como roadmap, no como realidad
- Docker y n8n como infraestructura auxiliar
- Limitaciones conocidas
- n8n ya no es el orquestador; es infraestructura disponible
- Pexels ya no aparece como provider activo
- Duración documentada como configurable (perfiles)
- Diagrama Mermaid eliminado (no reflejaba el pipeline real)

### docs/project/architecture.md

- Sección de "Arquitectura actual" con orquestador, pipeline, Visual Plan V2, paths `assets/`, TTS edge_tts canónico, providers reales, render, validación, Docker y n8n
- Sección de "Arquitectura futura" con `src/shorts_creator/` como objetivo, `pyproject.toml` pendiente
- n8n ya no se describe como orquestador
- ElevenLabs ya no es el TTS canónico (es edge_tts)
- Pexels ya no aparece como provider activo
- `fetch_images.py` y `editorial_asset_contract.py` ya no se mencionan
- `scenes/scene-*.jpg` reemplazado por `assets/scene-*.jpg`
- `visual_normalize.py` no se menciona (sin callers)
- `review_job.py` no se menciona (no existe)

### docs/architecture/modular-v2-transformation-roadmap.md

- Estado actualizado: V1 ya no es runtime ejecutable
- Visual Plan V2 es el contrato canónico
- Slice 1-4 completados, Slice 5 en ejecución, Slice 6 pendiente
- `pyproject.toml` y `src/shorts_creator/` todavía no existen
- Tabla de orden de transformación con columna de progreso
- Política de jobs V1 actualizada: clasificación defensiva es el único código V1 remanente

### openspec/changes/retire-legacy-visual-v1/tasks.md

- Slice 5 reestructurado en Slice 5A (product identity and architecture) y Slice 5B (environment, integrations, operational references)
- Tareas de implementación 5A marcadas como completadas
- Review, correcciones y commit de 5A pendientes
- Todas las tareas de 5B y Slice 6 pendientes

### docs/project/current-state.md

- Bloque "Slice 5A implementado" añadido tras Slice 4B2
- Resumen actualizado con Slice 5A y 5B
- Próximos pasos actualizados

## Validaciones ejecutadas

- `git diff --check`: sin espacios en blanco problemáticos
- `git status --short`: 5 archivos modificados, 1 untracked
- Scripts canónicos: todos existen
- Referencias eliminadas: `rg` sobre README y architecture.md sin coincidencias vigentes
- Orquestador y pipeline: referencias presentes
- n8n: presente pero no como orquestador
- Providers: clasificación correcta
- Arquitectura futura: referencias a `src/` y `pyproject.toml` presentadas como futuras
- V1 en roadmap: sin afirmaciones de runtime dual vigente

## Resultados

- 5 archivos modificados
- 1 session log creado
- 0 staged
- 0 commits
- 0 push
- 0 reindexados
- 0 llamadas MCP
- Working tree: sucio controlado

## Limitaciones

- Sin suite completa de tests
- Sin E2E real
- Sin providers reales
- Sin Docker
- Sin red
- Sin modificación de código o tests

## Estado Git final

```
HEAD:       f8bd4f2900f964df6529aa136d9e78f58ec9baa7
Modificados: 5 archivos
Creados:     1 archivo
Staged:      0
Commits:     0
Push:        0
Reindexados: 0
```

## Corrección de identidad previa al review

### Motivo

El resultado de Slice 5A original no cumplía suficientemente la identidad de producto porque presentaba una enumeración de categorías (educativo, explicativo, divulgativo, histórico) como identidad genérica, en lugar de posicionar el producto como un generador configurable e independiente de la temática.

### Diferencia clave

- **Antes:** identidad genérica definida como "varias categorías de contenido"
- **Después:** identidad centrada en "generador automatizado y configurable", donde la temática es un parámetro de entrada, no una categoría del producto

### Cambios aplicados

#### README.md

- Apertura reescrita: shorts-creator es un generador automatizado y configurable de vídeos cortos
- El pipeline se describe como coordinación de guion → recursos visuales → narración → subtítulos → render → validación
- El núcleo del pipeline se declara independiente de la temática
- Badge LLM corregido de "OpenAI | Claude | Gemini" a "OpenAI-compatible" (solo openai implementado)
- Sección "Capacidades actuales" reemplazada por "Qué puedes configurar" con tabla de controles verificados
- Sección "Dirección del producto" añadida con controles futuros claramente etiquetados como no implementados
- Quick start cambiado de "La batalla de Stalingrado" a "Cómo se forma un arcoíris"
- Primer ejemplo de pipeline cambiado de "Título del vídeo" a "Tema del vídeo"
- Referencia a proveedores LLM corregida (solo OpenAI-compatible implementado)
- Typo "oncelabs" corregido a "ElevenLabs" (ya no mencionado explícitamente en la tabla de controles actuales; aparece correctamente como `elevenlabs` en el proveedor TTS)
- Duración no fijada a ~1 min; se documentan perfiles reales

#### docs/project/architecture.md

- "9:1080×1920" corregido a "9:16 (1080×1920)"
- Sección "Modelo de configuración del producto" añadida con contrato actual y contrato objetivo
- Controles actuales documentados con tabla de superficies
- Contrato objetivo (topic, format, duration, language, voice, subtitles, music, visuals, quality, reviewPolicy, publication) marcado como no implementado

#### docs/architecture/modular-v2-transformation-roadmap.md

- Resumen inicial cambiado de "~1 min" a "duración y producción configurables"

#### docs/project/current-state.md

- Resumen global cambiado de "~1 min" a "duración configurable"
- Criterio de Slice 5A cambiado de "identidad genérica (educativo, explicativo...)" a "identidad centrada en un generador genérico y configurable"

#### openspec/changes/retire-legacy-visual-v1/tasks.md

- Criterio de aceptación de README ampliado para incluir identidad configurable, separación presente/futuro, apertura sin historia, quick start no histórico, duración no fijada

### Controles actuales verificados

| Control | Superficie | Evidencia |
|---------|-----------|-----------|
| Tema | `--topic` | CLI run_job.py |
| Duración | `--duration`, `--duration-profile`, `--duration-target`, `--duration-min`, `--duration-max`, `--strictness` | CLI run_job.py |
| Modelo LLM | `--model` | CLI run_job.py |
| Proveedor TTS | `--tts-provider`, `TTS_PROVIDER` env | CLI generate_audio.py |
| Voz | `--voice`, `TTS_VOICE` env | CLI generate_audio.py |
| Timing subtítulos | `--subtitle-timing-provider`, `SUBTITLE_TIMING_PROVIDER` env | CLI generate_audio.py |
| Estilo subtítulos | `--subtitle-style` | CLI prepare_job.py |
| Providers visuales | Wikimedia Commons, Pixabay | Código y configuración |
| Ejecución parcial | `--stop-after` | CLI run_job.py |
| Planificación | `--dry-run` | CLI run_job.py |

### Controles futuros claramente etiquetados

Idioma, música, clips de fondo, estrategia visual, calidad, revisión, publicación e interfaz web aparecen explícitamente como dirección del producto no implementada.

### Cambio textual del CLI

`bin/run_job.py`: ayuda de `--topic` corregida de "Historical topic for the video" a "Topic or instruction for the video".

### Validaciones

- `git diff --check`: sin errores de espacio en blanco
- `git status --short`: 6 archivos modificados, 1 untracked (session log)
- HEAD verificado: f8bd4f2900f964df6529aa136d9e78f58ec9baa7
- Cero staging, cero commits, cero reindexados

## Limpieza final de identidad runtime previa al review

### Coincidencias encontradas

| Archivo | Línea | Categoría | Decisión |
|---------|-------|-----------|----------|
| `bin/run_job.py` | 8 | Ejemplo vigente sesgado ("La batalla de Stalingrado") | Corregido |
| `bin/validate_job.py` | 2 | Identidad vigente incorrecta ("shorts-históricos") | Corregido |
| `bin/validate_job.py` | 930 | Identidad vigente incorrecta ("shorts-historicos job") | Corregido |

### Coincidencias legítimas preservadas

Referencias a `historical_map`, `historical_photograph`, `historical_art_or_document` en `bin/asset_validation.py` y `bin/render_job.py` son tipos de asset semánticos, no identidad de producto. Se preservan sin cambios.

### Referencias aplazadas a Slice 5B

- `.env.example`: `PROJECT_ROOT=/home/javi/projects/shorts-historicos`, `POSTGRES_DB=shorts_history`
- `HANDOVER.md`: referencia a históricos
- `AGENTS.md`: sin residuos directos
- `docs/project/vision.md`: "divulgación histórica" (identidad legacy, pendiente de decisión)
- Session logs históricos: identidad legacy preservada como historial frío
- `docs/runbooks/render-troubleshooting.md`: referencia a coherencia histórica

### Resultado de visual_normalize.py

- `visual_normalize.py` existe físicamente (`bin/visual_normalize.py`)
- `validate_job.py` importa `normalize_scene_visual` desde `visual_normalize` (línea 38)
- La función nunca se invoca en `validate_job.py` (import muerto)
- No existen otros callers en `bin/` o `tests/`
- Clasificación: deuda técnica fuera del alcance de `retire-legacy-visual-v1`. Debe tratarse en una limpieza de código posterior, salvo que Slice 6 detecte una regresión relacionada.

### Cambios aplicados

- `bin/run_job.py`: docstring line 8, Stalingrado → "Cómo se forma un arcoíris"
- `bin/validate_job.py`: docstring line 2, "shorts-históricos" → "vídeos cortos"
- `bin/validate_job.py`: CLI description line 930, "shorts-historicos job" → "shorts-creator job"
- Todos los cambios son exclusivamente textuales, sin efecto funcional

### Archivos modificados

7 modificados, 1 untracked:
- README.md (previo)
- bin/run_job.py (previo + nuevo)
- bin/validate_job.py (nuevo)
- docs/architecture/modular-v2-transformation-roadmap.md (previo)
- docs/project/architecture.md (previo)
- docs/project/current-state.md (previo + nuevo)
- openspec/changes/retire-legacy-visual-v1/tasks.md (previo + nuevo)
- docs/sessions/20260730-214000-retire-legacy-visual-v1-slice-5a.md (untracked, actualizado)

### Validaciones

- AST de ambos archivos: OK
- Ayuda CLI de ambos: sin residuos históricos
- `rg` sobre runtime canónico: sin residuos de identidad temática
- `git diff --check`: sin errores de espacio en blanco

### Resumen

- 0 staging
- 0 commits
- 0 reindexados
- 0 llamadas MCP
- HEAD: f8bd4f2900f964df6529aa136d9e78f58ec9baa7

## Microcorrección final previa al review

### Residuo encontrado en bin/prepare_job.py

- **Archivo:** `bin/prepare_job.py`
- **Línea:** 167
- **Texto anterior:** `"; ASS subtitles for shorts-historicos",`
- **Texto nuevo:** `"; ASS subtitles generated by shorts-creator",`
- **Naturaleza:** comentario en cabecera del formato ASS (sin efecto en parsing o runtime)
- **Impacto funcional:** cero — es una etiqueta textual en la primera línea del bloque `[Script Info]`

El cambio es exclusivamente textual. No se modificaron estilos ASS, resolución, fuentes, timings, diálogos, formato, funciones ni lógica.

### Clasificación corregida de visual_normalize.py

El import muerto de `normalize_scene_visual` desde `visual_normalize.py` en `validate_job.py` se clasifica como:

> Deuda técnica fuera del alcance de `retire-legacy-visual-v1`. Debe tratarse en una limpieza de código posterior, salvo que Slice 6 detecte una regresión relacionada.

No es trabajo de Slice 5B (documentación y operaciones) ni de Slice 6 (baseline E2E y cierre del change). Es un trabajo independiente de limpieza de código muerto.

### Recuento final de archivos

- **Modificados:** 8 (README.md, bin/run_job.py, bin/validate_job.py, bin/prepare_job.py, docs/architecture/modular-v2-transformation-roadmap.md, docs/project/architecture.md, docs/project/current-state.md, openspec/changes/retire-legacy-visual-v1/tasks.md)
- **Creados:** 1 (docs/sessions/20260730-214000-retire-legacy-visual-v1-slice-5a.md)
- **Staged:** 0
- **Commits:** 0
- **Reindexados:** 0
- **Llamadas MCP:** 0

### Validaciones ejecutadas

- AST de `bin/prepare_job.py`: OK
- `git diff --check`: sin errores de espacio en blanco
- `git status --short`: 8 modificados, 1 untracked
- Búsqueda de identidad runtime: sin residuos de identidad temática en el runtime canónico
- HEAD verificado: f8bd4f2900f964df6529aa136d9e78f58ec9baa7

### Cambios en current-state.md

- Añadido `bin/prepare_job.py` a la lista de cambios runtime
- Clasificación de `visual_normalize.py` corregida de "pendiente de Slice 5B/6" a deuda técnica fuera del change
- Recuento de archivos modificados actualizado a 8

### Cambios en session log

- Eliminado `bin/prepare_job.py` de "Referencias aplazadas a Slice 5B"
- Clasificación de `visual_normalize.py` actualizada
- Microcorrección documentada

## Review formal y corrección F1

### Configuración

- **Sesión:** `retire-legacy-visual-v1-slice-5a-review-f1-fix`
- **Modelo:** `opencode/big-pickle`
- **Variante:** `default`
- **Modo:** `Build`
- **Nota:** El review formal previo se ejecutó en modo Plan; esta sesión Build aplicó exclusivamente la corrección documental F1.
- **MCP:** desactivado
- **Llamadas MCP:** 0

### Review formal

- **Verdict:** `CHANGES_REQUIRED`
- **Finding F1 — MEDIUM:** `README.md`: tabla "Obligatorias" con una fila de tres celdas dentro de una tabla de dos columnas. La fila `| \`LLM_PROVIDER\` | \`openai\` | Proveedor LLM (solo OpenAI-compatible implementado) |` tenía tres celdas en una tabla cuya cabecera define Variable | Descripción (dos columnas).
- **Finding F2 — LOW (preservado sin cambios):** `docs/project/current-state.md`: "n8n como orquestador legacy".

### Corrección aplicada

**Archivo:** `README.md`, línea de la fila `LLM_PROVIDER`.

**Anterior:**
```markdown
| `LLM_PROVIDER` | `openai` | Proveedor LLM (solo OpenAI-compatible implementado) |
```

**Nueva:**
```markdown
| `LLM_PROVIDER` | `openai` — Proveedor LLM; actualmente solo se implementa un cliente OpenAI-compatible |
```

La columna "Descripción" unifica el valor y la explicación en una sola celda, respetando el esquema de dos columnas. `openai` se conserva como valor documentado. No se introducen afirmaciones de proveedores no soportados. F2 no se modifica.

### Validaciones ejecutadas

- Tabla Markdown validada: `README_LLM_PROVIDER_TABLE_OK line=142`
- `git diff --check`: sin errores de espacio en blanco
- `git status --short`: 8 modificados, 1 untracked (sin cambios en el conjunto de archivos)
- HEAD: `f8bd4f2900f964df6529aa136d9e78f58ec9baa7`
- Cero staging, cero commits, cero reindexados

### Archivos modificados en esta sesión

1. `README.md` (corrección material F1)
2. `openspec/changes/retire-legacy-visual-v1/tasks.md` (trazabilidad)
3. `docs/project/current-state.md` (estado)
4. `docs/sessions/20260730-214000-retire-legacy-visual-v1-slice-5a.md` (session log)

### Resultados

- 0 staged
- 0 commits
- 0 push
- 0 reindexados
- 0 llamadas MCP
- Working tree: sucio controlado (8 modificados, 1 untracked)

### Próxima acción

Ejecutar reaprobación read-only focalizada de Slice 5A, verificando F1, trazabilidad y ausencia de cambios nuevos fuera del alcance.

## Próxima acción (post-F1)

Ejecutar reaprobación read-only focalizada de Slice 5A, verificando F1 corregido, trazabilidad documental y ausencia de cambios fuera del alcance autorizado.

## Reaprobación y cierre de Slice 5A

### Reaprobación

- **Sesión:** `retire-legacy-visual-v1-slice-5a-focused-reapproval`
- **Modelo:** `opencode/big-pickle`
- **Modo:** `Plan`
- **MCP:** desactivado
- **Verdict:** `APPROVED_FOR_COMMIT`
- F1 confirmado como corregido.
- F2 preservado como LOW no bloqueante.
- Working tree sin modificaciones durante el review.

### Cierre

- **Sesión:** `retire-legacy-visual-v1-slice-5a-close`
- **Modelo:** `opencode/big-pickle`
- **Modo:** `Build`
- Nueve archivos incluidos.
- Un único commit.
- Mensaje:

```text
docs(product): align V2 identity and current architecture
```

- Sin push.
- Sin reindexado.
- Slice 5A cerrado.
- Slice 5B pendiente.
