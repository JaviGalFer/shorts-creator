# Estado actual del proyecto

**Última actualización:** 2026-08-01

## Estado global

Pipeline funcional de vídeos cortos verticales con duración configurable. Scripts en `bin/` operativos. n8n como orquestador legacy. Docker para render.

**Último change completado:** `integrate-native-visual-plan-v2-generation` (2026-07-14)

**Change pausado:** `improve-short-form-audio-pacing-v2` — Phase A completada, Phase B pendiente (se reanudará tras migrar dominio script)

**Change activo:** `retire-legacy-visual-v1` — Primera fase del plan de transformación modular. Slice 1 implementado, revisado y commiteado. Slice 2 implementado, revisado y cerrado mediante commit. Slice 3A implementado, revisado y cerrado mediante commit. Slice 3B1 implementado, revisado y cerrado mediante el commit de esta iteración. Slice 3B2 implementado, revisado y cerrado mediante el commit de esta iteración. Slice 3B3 implementado, revisado y cerrado mediante el commit de esta iteración. Slice 4A implementado, revisado y cerrado mediante el commit de esta iteración. Slice 4B1 implementado, revisado y cerrado mediante el commit de esta iteración. Slice 4B2 implementado, revisado y cerrado mediante el commit de esta iteración. Slice 4 completo. Slice 5A implementado, revisado, corregido, reaprobado y cerrado mediante el commit `f2a8078`. Slice 5B implementado, auditado, corregido, reaprobado y cerrado mediante el commit `1d9fe37`. Slice 6A implementado, auditado, corregido y reaprobado; baseline vigente `1102 passed, 0 failed`; pendiente exclusivamente de cierre y commit. Slice 6B no iniciado.

### Slice 1 completado (2026-07-17)

- `generate_script.py`: default de `--visual-schema-version` cambiado de 1 a 2; choices [1, 2] conservados; V1 explícito directo sigue soportado sin reinterpretación
- `run_job.py`: `build_script_command()` añade `--visual-schema-version 2`
- Tests focalizados: 13 passed, 0 failed
- Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES` — único finding: descripción stale en session log (corregido)
- No se ha implementado rechazo de jobs V1 ni eliminación de código V1

### Slice 2 completado (2026-07-22)

- `run_job.py`: clasificador `_classify_visual_schema()` fail-closed con 5 categorías
- `run_job.py`: `_schema_error_for_category()` mapea categorías a errores del contrato
- `run_job.py`: validación en bloque común post-script; V1 puro → `UNSUPPORTED_LEGACY_SCHEMA`; mixed → `MIXED_VISUAL_PLAN_SCHEMA_VERSIONS`; inválido → `INVALID_VISUAL_SCHEMA`
- `run_job.py`: `build_stage_command()` siempre devuelve `fetch_images_v2.py` para assets desde el pipeline canónico
- `fetch_images.py` sigue existiendo físicamente (retirada aplazada a Slice 4)
- La rama V1 de `_verify_stage_contract` permanece en el archivo, pero es inalcanzable desde el pipeline canónico tras el guard. Su limpieza queda aplazada a Slice 4.
- Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES` — sin findings funcionales bloqueantes
- Tests focalizados confirmados: 62 passed, 0 failed
- Slice 2 cerrado mediante commit de cierre

### Slice 3A cerrado (2026-07-22)

- `generate_script.py`: `--visual-schema-version` choices restringido a `[2]`; `--visual-schema-version 1` produce `SystemExit(2)` vía argparse
- `generate_script.py`: `call_llm` default cambiado de `SYSTEM_PROMPT` a `SYSTEM_PROMPT_V2`
- `generate_script.py`: `main()` aplanado a V2-only — sin ramas productivas V1
- `generate_script.py`: `visuals_request["schemaVersion"]` siempre 2; `visualSchemaVersion` stdout siempre 2
- Sin flag y con flag `--visual-schema-version 2`, `generate_script.py` usa V2
- Retry, validación y canonicalización son exclusivamente V2 en runtime
- `run_job.py` continúa pasando `--visual-schema-version 2` (sin cambios)
- SYSTEM_PROMPT y helpers V1 siguen físicamente presentes, sin callers productivos desde main()
- Eliminación física de V1 pertenece a Slice 3B
- Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES` — sin findings funcionales bloqueantes
- Tests focalizados confirmados: 138 passed, 0 failed
- Slice 3A cerrado mediante el commit de esta iteración

### Slice 3B1 implementado, revisado y cerrado mediante `5a4e7f2` (2026-07-22)

- `generate_script.py`: cuatro símbolos V1 de prompts eliminados (`SYSTEM_PROMPT`, `_build_duration_prompt_instruction`, `_build_retry_instruction`, `_build_user_prompt`)
- `tests/test_generate_script.py`: 17 tests V1 eliminados; 35 tests permanecen (validator, retry-loop V2, asset-side, segment-count)
- `tests/test_duration_profiles.py`: migrados a equivalentes V2 vía aliases locales; 36 tests pasan
- Fixture `_GOOD_3_SCENE_SCRIPT`, `PROMPT_PATH` eliminados sin impacto; `import re` eliminado de tests/test_generate_script.py (conservado en bin/generate_script.py)
- runtime continúa V2-only
- `_validate_script_structure` continúa temporalmente presente (Slice 3B2)
- Tests del validator V1 siguen presentes (Slice 3B2)
- Resultados tests focalizados:
  - `test_duration_profiles.py`: 36 passed
  - `test_generate_script.py`: 35 passed
  - `test_generate_script_v2.py`: 77 passed
  - `test_v2_only_generation_contract.py`: 7 passed
  - `test_run_job.py -k build_script_command`: 2 passed
- Slice 3B2 es el siguiente trabajo
- Slice 4 no ha comenzado

### Slice 3B2 implementado, revisado y cerrado mediante el commit de esta iteración (2026-07-24)

- `_validate_script_structure` eliminado
- imports editoriales eliminados de generate_script.py
- import re conservado
- tres re.sub productivos conservados
- 25 tests dependientes del validator V1 eliminados
- tests/test_generate_script.py queda con diez tests
- _build_scene_script eliminado
- _seg_script eliminado
- test_shared_contract_used_by_fetch_and_generate transformado en test_fetch_images_imports_editorial_contract
- reglas neutrales de estructura siguen cubiertas por _validate_and_canonicalize_script_v2 y tests/test_generate_script_v2.py
- validación histórica V1 eliminada sin migración
- reglas editorialRole, visualTemporalIntent y assetType V1 eliminadas de generate_script sin migración
- segment-count V1 eliminado sin migración
- editorial_asset_contract continúa utilizado por fetch_images.py hasta Slice 4
- Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES`.
- Cero findings bloqueantes.
- Dos notas cosméticas dentro del slice corregidas antes del commit:
  - separación de líneas top-level en generate_script.py;
  - newline final en tests/test_generate_script.py.
- Comentario stale de fetch_images.py aplazado a Slice 4.
- tests focalizados:
  - test_generate_script.py: 10 passed
  - test_generate_script_v2.py: 77 passed
  - test_duration_profiles.py: 36 passed
  - test_v2_only_generation_contract.py: 7 passed
  - test_run_job.py -k build_script_command: 2 passed
  - total: 132 passed, 0 failed
- Slice 3B3 es el siguiente trabajo
- Slice 4 no ha comenzado

### Slice 3B3 implementado, revisado y cerrado mediante el commit de esta iteración (2026-07-25)

- `generate_script.py`: argumento `--visual-schema-version` eliminado del parser
- `generate_script.py`: variable `args.visual_schema_version` eliminada
- `generate_script.py`: `request.visuals.schemaVersion=2` conservado
- `generate_script.py`: `visualSchemaVersion=2` conservado en salidas diagnósticas (dry-run, normal, JSON)
- `generate_script.py`: exactamente tres `re.sub` conservados
- `run_job.py`: `build_script_command()` ya no pasa el selector
- `run_job.py`: validación de schema V1/mixed/invalid permanece intacta
- Tests del selector transformados, no eliminados
- `test_generate_script_v2.py` continúa con 77 tests
- `test_v2_only_generation_contract.py` continúa con 7 tests
- `test_generate_script.py`: 10 tests (sin cambios)
- `test_duration_profiles.py`: 36 tests (sin cambios)
- `test_run_job.py -k build_script_command`: 2 tests (sin cambios)
- Total focalizado: 132 passed, 0 failed
- Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES`.
- Cero findings bloqueantes.
- El selector CLI fue eliminado del parser y del caller productivo.
- El contrato persistido `request.visuals.schemaVersion=2` permanece.
- Los diagnósticos `visualSchemaVersion=2` permanecen.
- Los tests fueron transformados sin reducción de conteo.
- Tests focalizados finales: 132 passed, 0 failed.
- Slice 4A es el siguiente trabajo.
- Slice 4A implementado pendiente de review y commit.
- Slice 4B no ha comenzado.

### Slice 4A implementado, revisado y cerrado mediante el commit de esta iteración (2026-07-25)

- `run_job.py`: `STAGE_SCRIPTS` ya no referencia `fetch_images.py`
- `run_job.py`: retirados `_collect_visual_plan_schema_versions`, `_uses_v2_visual_assets`, `_check_mixed_schema_versions`
- `run_job.py`: `_verify_stage_contract` para assets simplificado a contrato V2-only (`assets/`, `V2_IMAGE_EXTENSIONS`)
- `run_job.py`: clasificación y rechazo de V1/mixed/invalid conservado (`_classify_visual_schema`, `_schema_error_for_category`, `V1_POSITIVE_FIELDS`)
- `tests/test_run_job_v2_assets.py`: retiradas 4 clases legacy (25 tests). Quedan 20 tests V2-only
- `tests/test_generate_script_v2.py`: `test_run_job_modules_unchanged` transformado a contrato V2 vigente (77 tests)
- `tests/test_run_job.py`: `test_assets_ready_with_images_passes` migrado a contrato V2 (`assets/`, schemaVersion=2)
- `fetch_images.py` sigue existiendo hasta Slice 4B
- `editorial_asset_contract.py` sigue existiendo hasta Slice 4B
- Conteos AST finales: test_run_job_v2_assets.py=20, test_generate_script_v2.py=77, test_run_job.py=91
- Tests focalizados:
  - test_run_job_v2_assets.py: 20 passed, 0 failed
  - test_run_job.py (5 clases focalizadas): 48 passed, 0 failed
  - test_generate_script_v2.py: 77 passed, 0 failed
  - test_fetch_images_v2.py: 39 passed, 0 failed
- Total focalizado de Slice 4A: 184 passed, 0 failed.
- El fallo de `test_v2_metadata_reaches_assets` se debía a reutilización de metadata mutable en el test y quedó corregido.
- Cero regresiones focalizadas detectadas.
- Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES`.
- Cero findings bloqueantes.
- Review confirmó que no existen callers productivos a `fetch_images.py` desde el runner.
- Review confirmó que la clasificación y rechazo V1/mixed/invalid permanece intacta.
- Review confirmó el contrato V2-only de assets.
- Review confirmó los conteos AST:
  - test_run_job_v2_assets.py: 20;
  - test_generate_script_v2.py: 77;
  - test_run_job.py: 91.
- Tests focalizados finales: 184 passed, 0 failed.
- Slice 4B no iniciado

### Slice 4B1 implementado, revisado y cerrado mediante el commit de esta iteración (2026-07-25)

- `fetch_images.py` eliminado físicamente
- `editorial_asset_contract.py` eliminado físicamente
- stack V2 intacto
- cero imports residuales desde `bin/` y `tests/`
- `test_semantic_asset_validation.py`: 76 tests → 8 tests
- `test_no_topic_specific_contamination.py`: 26 tests → 4 tests
- `test_generate_script.py`: 10 tests → 3 tests
- 97 tests legacy eliminados
- 15 tests neutrales conservados en esos tres archivos
- configuración Pexels no modificada
- Slice 4B2 no iniciado
- tests focalizados: 292 passed, 0 failed
- Review final: `APPROVE_WITH_NON_BLOCKING_NOTES`.
- Cero findings bloqueantes.
- Dos módulos legacy eliminados físicamente:

  - `bin/fetch_images.py`;
  - `bin/editorial_asset_contract.py`.
- Cero imports o callers productivos residuales.
- Stack V2 intacto.
- Clasificación y rechazo V1/mixed/invalid del runner intactos.
- 97 tests exclusivamente legacy eliminados.
- 15 tests neutrales conservados.
- Conteos finales:

  - `test_semantic_asset_validation.py`: 8;
  - `test_no_topic_specific_contamination.py`: 4;
  - `test_generate_script.py`: 3.
- Total focalizado final: 292 passed, 0 failed.
- README y runbook primario utilizan CLI V2 válido.
- Runbook primario documenta:

  - script → assets → audio → prepare → render;
  - assets visuales bajo `assets/`.
- Configuración Pexels no modificada (hasta Slice 4B2).
- Slice 4B2 no iniciado.

### Slice 4B2 implementado, revisado y cerrado mediante el commit de esta iteración (2026-07-25)

- `PEXELS_API_KEY` eliminado de `.env.example`
- passthrough de `PEXELS_API_KEY` eliminado de `docker-compose.yml`
- cero consumidores productivos o workflows de `PEXELS_API_KEY`
- entrada `pexels` conservada como proveedor V2 planificado
- Pexels continúa `disabled` y `not implemented`
- Pixabay continúa activo con `PIXABAY_API_KEY`
- Wikimedia continúa activo sin API key
- FreeAI y Pollinations no modificados
- routing y executor no modificados
- tests focalizados ejecutados: todos pasados
- Review final: `APPROVE_WITH_NON_BLOCKING_NOTES`.
- Cero findings bloqueantes.
- `PEXELS_API_KEY` eliminado de `.env.example`.
- Passthrough eliminado de `docker-compose.yml`.
- Cero consumidores productivos o workflows n8n.
- Entrada `pexels` conservada como provider planificado.
- Pexels continúa disabled y not implemented.
- `requiresApiKey=True` representa una capacidad futura, no un contrato activo de variable.
- Pixabay continúa activo con `PIXABAY_API_KEY`.
- Wikimedia continúa activo sin API key.
- FreeAI y Pollinations permanecen sin cambios.
- Router, executor, bridge y fetcher V2 intactos.
- Tests sin modificaciones.
- Conteos focalizados:

  - test_visual_provider_config_v2.py: 13;
  - test_visual_asset_executor_v2.py: 102;
  - test_visual_asset_router_v2.py: 102;
  - test_visual_asset_bridge_v2.py: 34;
  - test_fetch_images_v2.py: 39;
  - test_visual_v2_dry_run_e2e.py: 22;
  - test_failure_no_env_vars_in_metadata: 1.
- Total focalizado final: 313 passed, 0 failed.
- Slice 4 completo.
- Slice 5 pendiente.

## Slice 5A implementado, revisado, corregido, reaprobado y cerrado (2026-07-30)

- README.md reestructurado con identidad centrada en un generador genérico y configurable, independiente de la temática
- `bin/run_job.py` documentado como orquestador canónico
- n8n documentado como infraestructura legacy o alternativa, no como orquestador
- Providers documentados según su estado real (Wikimedia+Pixabay activos, Pexels planificado/deshabilitado, FreeAI+Pollinations deshabilitados)
- Arquitectura actual separada del roadmap futuro
- `docs/project/architecture.md` actualizado con arquitectura actual y futura; referencias legacy retiradas; sección de modelo de configuración añadida
- `docs/architecture/modular-v2-transformation-roadmap.md` actualizado con estado real del progreso
- `openspec/changes/retire-legacy-visual-v1/tasks.md` reestructurado en Slice 5A/5B
- Ocho archivos modificados (corrección de identidad previa al review), un session log actualizado
- Commit de cierre: `f2a8078` (`docs(product): align V2 identity and current architecture`). Cero push, cero reindexados y cero llamadas MCP.

### Limpieza de residuos de identidad runtime (post-implementación, previa al review)

- `bin/run_job.py`: ejemplo del docstring cambiado de "La batalla de Stalingrado" a "Cómo se forma un arcoíris"
- `bin/validate_job.py`: docstring del módulo cambiado de "Validación automatizada de jobs de shorts-históricos" a "Validación automatizada de jobs de vídeos cortos"
- `bin/validate_job.py`: descripción CLI cambiada de "Validate a shorts-historicos job" a "Validate a shorts-creator job"
- `bin/prepare_job.py`: cabecera ASS neutralizada de "shorts-historicos" a "generated by shorts-creator"
- Todos los cambios son exclusivamente textuales, sin efecto funcional
- `visual_normalize.py` permanece presente físicamente; `validate_job.py` importa `normalize_scene_visual` pero nunca lo invoca (import muerto). Es deuda técnica fuera del alcance de `retire-legacy-visual-v1` y debe tratarse en una limpieza de código posterior.
- Ocho archivos modificados (README.md, bin/run_job.py, bin/validate_job.py, bin/prepare_job.py, docs/architecture/modular-v2-transformation-roadmap.md, docs/project/architecture.md, docs/project/current-state.md, openspec/changes/retire-legacy-visual-v1/tasks.md), un session log actualizado
- Cero staging, cero commits, cero reindexados
- Review read-only formal: CHANGES_REQUIRED por una fila Markdown mal formada en la tabla de variables obligatorias del README (F1 MEDIUM).
- F1 corregido mediante una sustitución documental mínima (fila `LLM_PROVIDER` normalizada a dos celdas).
- Reaprobación read-only focalizada: APPROVED_FOR_COMMIT; F2 preservado como LOW no bloqueante.
- Tests focalizados ya ejecutados; los cambios son exclusivamente textuales, sin efecto funcional.
- Cierre mediante el commit de esta sesión con el mensaje `docs(product): align V2 identity and current architecture`.
- Commit de cierre: `f2a8078`, con nueve archivos incluidos; working tree final limpio.
- Cero push, cero reindexados, cero llamadas MCP.

## Slice 5B implementado, auditado con CHANGES_REQUIRED, corregido y reaprobado (2026-08-01)

Slice 5B del change `retire-legacy-visual-v1` implementado. Cambios exclusivamente documentales y de configuración de plantilla; sin cambios de código productivo.

Archivos modificados (implementación):

- `.env.example`: identidad genérica; `PROJECT_ROOT` corregido a `/home/javi/projects/shorts-creator` (solo plantilla); `POSTGRES_DB` conservado; documentado `SUBTITLE_GLOBAL_OFFSET_MS` y variables sin consumidor
- `AGENTS.md`, `Makefile`, `openspec/project.md`: identidad genérica
- `docs/project/environment.md`: componentes (CLI canónico / n8n·Postgres legacy / render worker) y requisitos de variables actualizados
- `docs/project/integrations.md`: estado de providers alineado con runtime
- `docs/project/vision.md`: producto genérico configurable; historia como caso de uso posible
- `docs/runbooks/n8n-operations.md`: n8n como infraestructura legacy
- `.opencode/agents/*.md` (5): identidad genérica
- `openspec/changes/retire-legacy-visual-v1/tasks.md`: estado de implementación de Slice 5B
- `docs/sessions/20260801-000000-retire-legacy-visual-v1-slice-5b-build.md`: session log de implementación

Decisiones de compatibilidad:

- `PROJECT_ROOT` corregido solo en `.env.example` (plantilla); no se toca ningún `.env` real.
- `POSTGRES_DB=shorts_history` conservado por compatibilidad con infraestructura n8n/PostgreSQL y datos persistidos existentes.
- Workflows n8n JSON y `HANDOVER.md` preservados intactos (legacy / contexto legacy frío).
- Código productivo (`bin/`, `tests/`, `docker-compose.yml`) no modificado.

### Auditoría read-only y correcciones (2026-08-01)

La auditoría read-only terminó con `SLICE_5B_REVIEW_CHANGES_REQUIRED`.

Findings corregidos:

- **F1 MEDIUM:** `.env.example` afirmaba soporte nativo `openai | anthropic | google`; se corrigió a "openai, mediante cliente OpenAI-compatible" y se eliminó el bloque alternativo Anthropic. Runtime (`bin/generate_script.py`) solo implementa `provider == "openai"`.
- **F2 MEDIUM:** `docs/project/environment.md` conservaba el layout plano legacy de datos; se sustituyó por el layout canónico `data/videos/{jobId}/`. Python pasó a dependencia obligatoria (3.10+); Faster-Whisper queda opcional.
- **F3 MEDIUM:** `docs/runbooks/n8n-operations.md` omitía `validate`, no presentaba `bin/run_job.py` como vía canónica y referenciaba `bin/review_job.py`; se añadió la etapa de validación, `bin/run_job.py` como orquestador canónico y se corrigió la ruta a `review_job.py`.
- **F4 MEDIUM:** `docs/project/current-state.md` con metadata y próximos pasos obsoletos; se actualizó fecha, resumen, bloque de Slice 5B y próximos pasos.
- **F5 LOW:** `docs/project/integrations.md` describía Edge TTS como síntesis "local"; se reformuló como cliente Python del servicio Microsoft Edge TTS (sin API key, requiere red, no es offline).
- **F6 LOW:** `docs/project/vision.md` afirmaba que cada vídeo tiene una bitácora y un change OpenSpec; se distinguió trazabilidad del job de la trazabilidad de cambios de desarrollo.

Nota no bloqueante:

- **F7 NOTE:** el session log conserva el timestamp `000000`. No existe una hora real verificable del Build y no se inventa un timestamp.

### Reaprobación read-only focalizada (2026-08-01)

La reaprobación read-only focalizada terminó con `SLICE_5B_REAPPROVED_FOR_CLOSURE`.

- F1–F6 confirmados como resueltos.
- Un LOW no bloqueante aceptado en `docs/project/integrations.md`: la frase `Anthropic/Google como opciones declaradas pero no verificadas como clientes implementados`, desambiguada por la línea siguiente que indica que solo existe un cliente OpenAI-compatible.
- F7 aceptado como NOTE no bloqueante (timestamp `000000`; sin hora real verificable; no se renombra ni se inventa una hora).
- Slice 5B aprobado para cierre.
- Repositorio sin cambios durante la reaprobación.
- Commit de cierre todavía pendiente en este punto.
- Slice 6 no iniciado.

### Cierre de Slice 5B (2026-08-01)

- Slice 5B cerrado mediante el commit `1d9fe37` (`docs(project): align Slice 5B environment and integrations`).
- Cero push, cero MCP, cero reindexado.
- Slice 6 es el siguiente trabajo.

## Slice 6A — Baseline y corrección (2026-08-01)

Estado: `SLICE_6A_REAPPROVED_FOR_COMMIT`. Slice 6A implementado, auditado,
corregido y reaprobado. La corrección focalizada de tests (11 neutrales, C2)
está completa y verde, el bloqueo de `test_timing_regression.py` fue resuelto
hermetizando sus cuatro tests (Estrategia A, C5), y el fallo C4 de aislamiento
de `test_fetch_images_v2.py::TestSourceIsolation::test_no_v1_runtime_imports`
fue corregido con restauración gestionada de `sys.modules`. La suite completa
queda verde: **baseline funcional `1102 passed, 0 failed`**. Los cambios
funcionales están validados; la auditoría read-only terminó con CHANGES_REQUIRED
exclusivamente documental y las correcciones documentales F4–F9 están aplicadas.
La reaprobación read-only focalizada finalizó con `SLICE_6A_REAPPROVED_FOR_COMMIT`
con cero findings bloqueantes; F1/F2 LOW y F3 NOTE fueron aceptados como no
bloqueantes y no se corrigieron. Los tres tests (`test_run_job.py`,
`test_timing_regression.py`, `test_fetch_images_v2.py`) no cambiaron durante las
correcciones documentales ni durante la reaprobación. Pendiente exclusivamente de
cierre y commit. No existe commit de Slice 6A todavía. Slice 6B no iniciado.

### HEAD inicial

- Rama `main`; HEAD `3866cc6a547545cad70cc1c5fbbacb08ef216713`.
- Últimos commits: `3866cc6` (record Slice 5B closure), `1d9fe37` (align Slice 5B).
- Working tree limpio; staging 0; `git diff --check` limpio.

### Causa de los 11 fallos

- `tests/test_run_job.py` presentaba 11 tests neutrales (pipeline multi-etapa)
  cuyas fixtures/metadata inline no satisfacían el contrato de schema V2.
- El clasificador fail-closed `_classify_visual_schema` de `bin/run_job.py`
  devolvía `SCHEMA_NOT_AVAILABLE_YET`/`INVALID_SCHEMA` (sin `script.scenes` o
  sin `visualPlan._schemaVersion=2`), por lo que el runner abortaba en la etapa
  `assets` con `INVALID_VISUAL_SCHEMA` y los tests no alcanzaban su etapa prevista.
- No se restauró compatibilidad V1 ni se debilitó `INVALID_VISUAL_SCHEMA`.

### Archivos modificados

- `tests/test_run_job.py` (único archivo de código de 6A; +85/−46 aprox.)
- `tests/test_timing_regression.py` (hermetización en 6A2)
- `tests/test_fetch_images_v2.py` (corrección de aislamiento C4 en 6A3)
- `openspec/changes/retire-legacy-visual-v1/tasks.md`
- `docs/project/current-state.md`
- `docs/sessions/20260801-000000-retire-legacy-visual-v1-slice-6a-baseline.md` (session log 6A + follow-up 6A2 + follow-up 6A3)

### Corrección aplicada (6A)

- Se añadió el helper `_v2_meta(meta)` que enriquece una metadata neutral con el
  contrato V2 mínimo (`script.scenes[].visualPlan._schemaVersion == 2`) sin mutar
  objetos compartidos y sin inventar campos.
- Se aplicó `_v2_meta` a las metadata inline de los 11 tests neutrales.
- Se añadió una imagen en `assets/` (p. ej. `seg_001.jpg`) en los tests
  multi-etapa que necesitan que la etapa `assets` pase su contrato de salida.
- Se corrigió la coincidencia de comando `"fetch_images.py"` → `"fetch_images_v2.py"`
  en dos tests (el runner canónico usa `fetch_images_v2.py`); cambio justificado
  porque impedía corregir esos tests directamente.
- Solo se migraron fixtures neutrales a V2. Los tests de rechazo V1, mixed e
  invalid quedaron intactos. No se cambiaron expected statuses ni aserciones.

### Hermetización de `test_timing_regression.py` (6A2)

- Los 4 tests de timing (`test_sentence_boundary_crossing`,
  `test_punctuation_restoration`, `test_no_cross_scene_leakage`,
  `test_no_single_word_by_boundary`) se reescribieron bajo Estrategia A: importan
  las funciones puras de `bin/generate_audio.py` (`build_full_narration`,
  `_build_canonical_tokens`, `_match_words_to_canonical`, `group_words_into_cues`,
  `_strip_punct`) y usan WordBoundary/cues sintéticos deterministas.
- No se ejecuta `generate_audio.py` como subprocess; no se contacta Edge TTS; no
  se crea audio real; no se usa red, Docker, `.venv`, ni
  `data/videos/la-2026-07-01-173458`.
- Se añadió el fixture `hermetic_guard` que falla de inmediato ante
  `subprocess.run`/`Popen`, `socket.create_connection`, `socket.socket` o un
  provider TTS real (`generate_audio.get_provider`).
- Resultado focalizado: `4 passed`.
- Clasificación del bloqueo heredado: C5 — dependencia de entorno/integración
  externa no hermética (Edge TTS).

### Resultados de `tests/test_run_job.py`

- Antes: `11 failed, 80 passed`.
- Después (aislado): `91 passed, 0 failed`.

### Grupos focalizados

- `test_run_job.py` + `test_semantic_asset_validation.py`: `99 passed`.
- `test_run_job.py` + `test_timing_regression.py` + `test_semantic_asset_validation.py`: `103 passed`.
- Generación/runner V2 (`test_generate_script.py`, `test_generate_script_v2.py`,
  `test_v2_only_generation_contract.py`, `test_run_job_v2_assets.py`): `107 passed`.
- Assets V2 (`test_fetch_images_v2.py`, `test_visual_provider_config_v2.py`,
  `test_visual_asset_executor_v2.py`, `test_visual_asset_router_v2.py`,
  `test_visual_asset_bridge_v2.py`): `290 passed`.
- Dry-run E2E (`test_visual_v2_dry_run_e2e.py`): `22 passed`.

### Preflight de suite y ejecución completa

- `--collect-only tests/`: `1102 tests collected`, cero errores de colección, no
  recorre `data/postgres/`.
- Preflight de efectos externos: subprocess/urllib/socket/edge_tts aparecen en la
  suite, pero todos están mockeados o son imports sin red. `test_continuous_audio.py`
  usa docker/subprocess reales pero solo tiene `main()` (sin funciones `test_`),
  por lo que no se recopila.
- `python3 -m pytest -q tests/ --tb=short`:
  `20 failed, 1082 passed in 12.25s`.

### Fallo adicional de suite (Caso B, resuelto en 6A3)

- Los 20 fallos eran de `tests/test_run_job.py`, **preexistentes** (reproducibles
  con `--ignore=tests/test_timing_regression.py`).
- Causa raíz C4: `tests/test_fetch_images_v2.py::test_no_v1_runtime_imports` hacía
  `sys.modules.pop("run_job", None)` (y otros módulos) sin restauración; el
  `monkeypatch.setattr(sys, "modules", sys.modules)` es un no-op y no registra
  ninguna entrada. Por el orden alfabético de pytest (`fetch_images_v2` <
  `run_job`), `test_run_job.py` corre después y sus `patch("run_job.*")` quedan
  rotos: `patch` reimporta un módulo `run_job` nuevo, distinto del objeto que el
  `main()` ya importado por `test_run_job.py` referencia.
- Clasificación: C4 — test demasiado acoplado por mutar estado global sin restaurar.
- Corrección (6A3): las eliminaciones de `sys.modules` se movieron a
  `with monkeypatch.context() as scoped:` usando `scoped.delitem(sys.modules, mod, raising=False)`,
  que registra y restaura el valor original al salir del bloque. Se añadió
  verificación de identidad post-contexto (objeto original restaurado, o ausencia
  conservada). El propósito del test (comprobar que `fetch_images_v2.main()` no
  reimporta los módulos legacy retirados — `fetch_images`, `asset_validation`,
  `editorial_asset_contract` — ni los módulos productivos vigentes cuya importación
  se bloquea por aislamiento de capas — `generate_script`, `prepare_job`,
  `render_job`, `run_job`) se conserva intacto. La variable de test continúa
  llamándose `v1_modules`, pero su nombre es impreciso y no implica que los siete
  módulos sean legacy.
- Archivo corregido: `tests/test_fetch_images_v2.py` (único archivo de 6A3).
- No se modifica producción.

### Reproducción mínima del C4 (6A3)

- `test_no_v1_runtime_imports` aislado: `1 passed`.
- Orden contaminante (`test_no_v1_runtime_imports` → `test_script_stage_extracts_job_id`):
  antes de la corrección `1 failed, 1 passed`; después `2 passed`.
- Orden inverso: `2 passed`.
- Prueba mínima de 4 tests (contaminante + 3 del runner): `4 passed`.

### Baseline

- Suite completa: **`1102 passed, 0 failed`** — baseline vigente de Slice 6A para el
  HEAD actual, establecida.
- `20 failed, 1082 passed` queda únicamente como resultado intermedio histórico
  de 6A2, no como baseline vigente.
- Baseline focalizada de 6A2: `test_run_job.py` = 91, `test_timing_regression.py` = 4,
  combinado = 103, V2 = 107/290/22.
- La baseline histórica `1215 passed, 16 failed` (Phase A) se conserva únicamente
  como cifra de referencia histórica, no como baseline de suite vigente.

### Estado

- Auditoría read-only completada con `SLICE_6A_REVIEW_CHANGES_REQUIRED`
  (F4–F6 MEDIUM documentales; F1/F2 LOW y F3 NOTE no bloqueantes preservados).
- Correcciones documentales F4–F9 aplicadas.
- Reaprobación read-only focalizada finalizada con `SLICE_6A_REAPPROVED_FOR_COMMIT`
  con cero findings bloqueantes; F1/F2 LOW y F3 NOTE aceptados como no bloqueantes.
- Los tres tests (`test_run_job.py`, `test_timing_regression.py`,
  `test_fetch_images_v2.py`) no cambiaron durante las correcciones documentales
  ni durante la reaprobación.
- Baseline funcional vigente: `1102 passed, 0 failed`.
- Slice 6A implementado, auditado, corregido y reaprobado; pendiente
  exclusivamente de cierre y commit.
- Slice 6B no iniciado.
- No existe commit de Slice 6A.
- Cero E2E real.
- Cero commit, cero push, cero MCP, cero reindexado.

## Resumen

- Slice 3B1: 157 tests focalizados pasados, 0 fallidos
- Slice 3B2: 132 tests focalizados pasados, 0 fallidos
- Slice 3B3: 132 tests focalizados pasados, 0 fallidos
- Slice 4A: implementado, revisado y cerrado mediante el commit de esta iteración
- Slice 4B1: implementado, revisado y cerrado mediante el commit de esta iteración
- Slice 4B2: implementado, revisado y cerrado mediante el commit de esta iteración
- Slice 4: completado
- Slice 5A: implementado, revisado, corregido, reaprobado y cerrado mediante el commit `f2a8078`
- Slice 5B: implementado, auditado, corregido, reaprobado y cerrado mediante el commit `1d9fe37`
- Slice 6: pendiente (6A: implementado, auditado, corregido y reaprobado; baseline funcional `1102 passed, 0 failed`; pendiente exclusivamente de cierre y commit; 6B no iniciado)

## Plan de transformación modular

El proyecto se transformará progresivamente hacia una arquitectura modular con V2 como único contrato visual soportado. No se reescribe desde cero.

Roadmap completo: `docs/architecture/modular-v2-transformation-roadmap.md`

### Orden de fases

1. Retirar V1 y enfoque histórico → `retire-legacy-visual-v1` (planificación)
2. Estabilizar pipeline V2, baseline clara
3. Crear `pyproject.toml` y `src/shorts_creator/`
4. Extraer `contracts/` e `infrastructure/`
5. Migrar `script/`
6. Reanudar audio pacing (Phase B)
7. Migrar `audio/`
8. Migrar `assets/`
9. Migrar `rendering/`
10. Migrar `validation/`
11. Reducir `bin/` a adaptadores, limpieza final

## Benchmark y routing de modelos

- Benchmark R1 cerrado en commit `4d1715f`
- Routing gratuito documentado en `docs/research/opencode-free-models-benchmark-r1.md`
- Modelos gratuitos aptos para planificación y código confirmados

## Próximos pasos

1. Cierre y commit de Slice 6A.
2. Tras el cierre de Slice 6A, iniciar Slice 6B: E2E V2 canónico.
3. Phase B de audio pacing tras migrar script/
4. Crear `pyproject.toml` y estructura `src/`
5. Investigar instalación de ffprobe en el host
6. Registrar FreeAI para imágenes de calidad gratuitas
7. Integrar pipeline v2 con n8n

## Audio pacing v2 — Phase A (completada 2026-07-14)

### Causa raíz del silencio

- Docker client (v1.52) incompatible con Docker daemon (API v1.43).
- `_get_mp3_duration()` fallaba silenciosamente → `durationSec = None` en todas las escenas.
- `prepare_job` usaba `targetDurationSec = 6` como fallback.
- `render_job` aplicaba `apad` + `atrim` para rellenar cada escena hasta 6s.
- Resultado: 50.9% silencio con 48 palabras en 30s.

### Correcciones implementadas

| Archivo | Cambio |
|---------|--------|
| `bin/generate_audio.py` | `_get_mp3_duration()` añade `DOCKER_API_VERSION=1.43`; retorna `(dur, source)`; `duration_estimated` y `durationSource` en metadata; `activeAudioDurationSec` desde último cue + guard |
| `bin/prepare_job.py` | Bloquea cuando `duration_estimated=true` o sin `durationSource`; nueva fórmula `sceneWindowSec = activeAudioDur + tailPause` |
| `bin/render_job.py` | `_docker_ffmpeg()` añade `DOCKER_API_VERSION=1.43`; `build_per_scene_audio_filter` acepta `active_audio_sec` para trim de room tone; pacing validation en quality gate |
| **NUEVO** `bin/pacing_validation.py` | Métricas: silenceRatio, maxInterSceneSilenceSec (con scene boundaries), narrationCoverageRatio, timelineWPM, effectiveSpeechWPM |
| `bin/validate_job.py` | Nuevo check `_check_pacing`; Docker env en `_run_docker_ffprobe` |

### Nuevo contrato temporal

```
activeAudioDurationSec = min(physicalDuration, lastCueEndSec + 0.10s)
sceneWindowSec = activeAudioDurationSec + sceneTailPauseSec (0.25s)
```

`targetDurationSec` es solo informativo. La ventana se deriva del audio activo medido.

### Resultados E2E (job `cmo-2026-07-14-180923`)

| Métrica | Antes (Phase A) | Después (Phase A.1) |
|---------|-------|---------|
| Duración | 22.640s | 18.30s |
| Silencio | 8.74s (38.7%) | ~4.4s (24.2%) |
| Narración coverage | 61.3% | 75.8% |
| maxInterSceneSilence | 1.618s | 0.775s |
| timelineWPM | — | 157.8 |
| effectiveSpeechWPM | — | 208.1 |
| qualityGate | FAIL | PASS |

La reducción de duración a ~18s se debe al word budget de Phase A (48 palabras).
Phase B expandirá a 27–30s con WPM calibrado.

### Baseline de tests

```text
1215 passed, 16 failed (preexistentes en test_run_job.py + test_semantic_asset_validation.py), 0 regresiones
```

> **Nota histórica:** `1215 passed, 16 failed` fue la baseline de Phase A.
> Durante 6A2 se obtuvo temporalmente `20 failed, 1082 passed` por contaminación
> de `sys.modules`. Tras corregir C4 en 6A3, la baseline vigente para el HEAD
> actual es `1102 passed, 0 failed`.
