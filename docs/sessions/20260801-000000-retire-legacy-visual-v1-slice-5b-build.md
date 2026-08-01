# Sesión: retire-legacy-visual-v1-slice-5b-build

## Configuración

- **Sesión:** `retire-legacy-visual-v1-slice-5b-build`
- **Modelo:** `opencode/deepseek-v4-flash-free`
- **Variante:** `default`
- **Modo:** `Build`
- **MCP:** desactivado
- **Llamadas MCP:** 0

## Estado Git inicial

```
Repositorio: /home/javi/projects/shorts-creator
Rama:       main
HEAD:       a4e3f74f54c9a0d3f979b28d6a9b015b8f0a2692
Working tree: limpio
```

## Objetivo de Slice 5B

Implementar la limpieza documental y de configuración no funcional de identidad,
entorno e integraciones, alineando la documentación operativa con el runtime V2
actual. Sin cambios de código productivo. No se realiza staging, commit, push,
MCP ni reindexado.

## Contratos confirmados (inspección directa)

| Contrato | Fuente directa | Resultado |
|----------|---------------|-----------|
| Orquestador | `bin/run_job.py` | `bin/run_job.py` es el orquestador canónico |
| Pipeline | `bin/run_job.py` L26 | script → assets → audio → prepare → render → validate |
| TTS canónico | `bin/generate_audio.py` L1543 | `edge_tts` default; elevenlabs alternativo |
| Wikimedia | `bin/visual_provider_config_v2.py` L18-24 | Activo, implementado, sin API key |
| Pixabay | `bin/visual_provider_config_v2.py` L31-37 | Activo, implementado, requiere `PIXABAY_API_KEY` |
| Pexels | `bin/visual_provider_config_v2.py` L25-30 | Planificado, deshabilitado, no implementado |
| FreeAI | `bin/visual_provider_config_v2.py` L38-43 | Deshabilitado, no implementado |
| Pollinations | `bin/visual_provider_config_v2.py` L44-48 | Deshabilitado, no implementado |
| `SUBTITLE_GLOBAL_OFFSET_MS` | `bin/generate_audio.py` L1303 | Default real `0` |
| `SPOKEN_WORDS_PER_MINUTE` | `bin/generate_script.py` L24 | No leído por código (hardcodeado 110) |
| `PROJECT_ROOT` | `render_server.py` / compose | Solo usado por render-worker / compose |
| `ELEVENLABS_API_KEY` | `bin/tts_provider.py` L249 | Solo si provider=elevenlabs |
| n8n | workflow `*-v1`, `docker-compose.yml` | Legacy / alternativa, no orquestador |

## Archivos modificados

- `.env.example`
- `AGENTS.md`
- `Makefile`
- `openspec/project.md`
- `docs/project/environment.md`
- `docs/project/integrations.md`
- `docs/project/vision.md`
- `docs/runbooks/n8n-operations.md`
- `.opencode/agents/integration-researcher.md`
- `.opencode/agents/n8n-workflow-engineer.md`
- `.opencode/agents/project-architect.md`
- `.opencode/agents/quality-and-ops-reviewer.md`
- `.opencode/agents/video-pipeline-engineer.md`
- `openspec/changes/retire-legacy-visual-v1/tasks.md`
- `docs/project/current-state.md`
- `docs/sessions/20260801-000000-retire-legacy-visual-v1-slice-5b-build.md` (este log)

## Archivos revisados y preservados intactos

- `HANDOVER.md` — ya marcado como contexto legacy frío (L1); preservado sin cambios.
- Workflows n8n JSON (`workflow-*.json`) — legacy; preservados sin cambios (revisión documental).

## Decisiones de compatibilidad

- `PROJECT_ROOT` corregido solo en `.env.example` (plantilla) a `/home/javi/projects/shorts-creator`. No se toca ningún `.env` real.
- `POSTGRES_DB=shorts_history` conservado por compatibilidad con infraestructura n8n/PostgreSQL y datos persistidos.
- No se añade `PEXELS_API_KEY` ni `FREEAI_API_KEY`.
- Código productivo (`bin/`, `tests/`, `docker-compose.yml`) no modificado.

## Resultado

Cambios exclusivamente documentales y de configuración de plantilla. Working tree
con cambios de implementación sin stagear, listo para la siguiente auditoría
read-only. Slice 5B no está revisado, reaprobado, cerrado ni commiteado.

## Corrección de findings del review (2026-08-01)

La auditoría read-only terminó con `SLICE_5B_REVIEW_CHANGES_REQUIRED`.

Findings corregidos:

- **F1 MEDIUM — `.env.example`:** la afirmación "Proveedores soportados: openai | anthropic | google" se sustituyó por "Proveedor soportado actualmente: openai, mediante cliente OpenAI-compatible". Se eliminó la referencia a la URL de Anthropic y el bloque alternativo Anthropic (L25-28). `LLM_PROVIDER=openai` se conserva. No se modificó código ni README.
- **F2 MEDIUM — `docs/project/environment.md`:** el bloque "Directorios de datos" plano legacy se sustituyó por el layout canónico `data/videos/{jobId}/` (metadata.json, video.mp4, subtitle.ass, assets/, scenes/), con `data/postgres/` como persistencia legacy n8n/PostgreSQL. Python pasó a dependencia obligatoria (3.10+); Faster-Whisper quedó opcional.
- **F3 MEDIUM — `docs/runbooks/n8n-operations.md`:** se reestructuró el runbook en "Ejecución canónica" (`bin/run_job.py`, pipeline script → assets → audio → prepare → render → validate) y "Ejecución manual por etapas" (se añadió `bin/validate_job.py`). La tabla de scripts incluye `bin/run_job.py`, `bin/validate_job.py` y corrige `bin/review_job.py` → `review_job.py` (script en la raíz).
- **F4 MEDIUM — `docs/project/current-state.md`:** se actualizó fecha (2026-08-01), resumen del change activo, bloque de Slice 5B (con auditoría y correcciones), resumen y próximos pasos.
- **F5 LOW — `docs/project/integrations.md`:** la descripción "Método: local, gratuito, sin API key" de Edge TTS se sustituyó por "cliente Python del servicio Microsoft Edge TTS, sin API key", con nota de que se ejecuta desde el entorno local, requiere red y no es síntesis offline.
- **F6 LOW — `docs/project/vision.md`:** el principio de trazabilidad se reformuló para distinguir la metadata del job de las bitácoras/changes OpenSpec de desarrollo, alineado con `AGENTS.md`.

Nota no bloqueante:

- **F7 NOTE:** el timestamp `000000` del nombre del session log se conserva. No existe una hora real verificable del Build y no se inventa un timestamp. F7 no se corrige en esta sesión.

## Archivos modificados durante la corrección

- `.env.example`
- `docs/project/environment.md`
- `docs/runbooks/n8n-operations.md`
- `docs/project/current-state.md`
- `docs/project/integrations.md`
- `docs/project/vision.md`
- `openspec/changes/retire-legacy-visual-v1/tasks.md`
- `docs/sessions/20260801-000000-retire-legacy-visual-v1-slice-5b-build.md` (este log)

## Validaciones documentales ejecutadas

- `grep` de proveedores LLM en `.env.example`, `bin/generate_script.py`, `README.md`, `docs/project/integrations.md`.
- `grep` de layout de datos y clasificación de Python en `docs/project/environment.md`.
- `grep` de orquestación en `docs/runbooks/n8n-operations.md`.
- Inspección de parsers CLI de `bin/run_job.py`, `bin/validate_job.py`, `review_job.py` (rutas y argumentos reales).
- Verificación de nombres de archivos y directorios del layout canónico contra `bin/*.py` y el runbook vigente.
- `git diff --check` limpio.

## Estado

Slice 5B con las correcciones F1–F6 aplicadas y sin stagear. **Pendiente de reaprobación read-only.** El slice no está reaprobado, cerrado ni commiteado. Cero staging, cero commit, cero push, cero MCP y cero reindexado.

## Reaprobación read-only focalizada (2026-08-01)

La reaprobación read-only focalizada terminó con `SLICE_5B_REAPPROVED_FOR_CLOSURE`.

- **Sesión:** `retire-legacy-visual-v1-slice-5b-reapproval`
- **Modelo:** `opencode/deepseek-v4-flash-free`
- **Variante:** `default`
- **Modo:** Plan
- F1–F6 confirmados como resueltos.
- Un LOW no bloqueante aceptado en `docs/project/integrations.md`: la frase `Anthropic/Google como opciones declaradas pero no verificadas como clientes implementados`, desambiguada por la línea siguiente que indica que solo existe un cliente OpenAI-compatible.
- F7 aceptado como NOTE no bloqueante (timestamp `000000`; sin hora real verificable; no se renombra ni se inventa una hora).
- Repositorio sin cambios durante la reaprobación.
- Slice 5B aprobado para cierre.
- Commit de cierre todavía pendiente en este punto.

## Cierre de Slice 5B (2026-08-01)

- Commit A creado mediante staging selectivo (16 archivos: 15 modificados + 1 nuevo).
- Hash completo: `1d9fe3780da60fe7391722a88a846fa64359660c`.
- Hash corto: `1d9fe37`.
- Subject: `docs(project): align Slice 5B environment and integrations`.
- Slice 5B cerrado.
- Cero push, cero MCP, cero reindexado.
- Commit B pendiente únicamente para registrar el hash real del Commit A.
