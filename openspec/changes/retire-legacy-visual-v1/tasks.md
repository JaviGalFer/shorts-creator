# Tareas: retire-legacy-visual-v1

## Slice 1 — V2-only generation contract

- [x] `generate_script.py`: cambiar default `--visual-schema-version` a `2`
- [x] ~~`generate_script.py`: deprecar `--visual-schema-version 1` con warning + tratar como V2~~ — superseded por Slice 3A: V1 se rechaza mediante argparse con `SystemExit(2)`
- [x] Tests focalizados de generación (V2 only)

## Slice 2 — V2-only asset runtime

- [x] `run_job.py`: validar `request.visuals.schemaVersion` al inicio del pipeline
- [x] `run_job.py`: rechazar metadata V1 pura → `UNSUPPORTED_LEGACY_SCHEMA`
- [x] `run_job.py`: rechazar metadata mixta → `MIXED_VISUAL_PLAN_SCHEMA_VERSIONS`
- [x] `run_job.py`: rechazar metadata visual inválida → `INVALID_VISUAL_SCHEMA`
- [x] `run_job.py`: eliminar bifurcación fetch_images vs fetch_images_v2
- [x] `run_job.py`: invocar siempre `fetch_images_v2.py`
- [x] Tests focalizados de assets (V2 only)
- [x] Tests focalizados de contratos runtime
- [x] Tests focalizados de runner (rechazo V1)
- [x] Actualizar `current-state.md`
- [x] Crear session log

## Slice 3 — Remove V1 generation logic

### Slice 3A — Disable V1 generation runtime (cerrado 2026-07-22)

- [x] `generate_script.py`: `--visual-schema-version` choices restringido a `[2]`; V1 produce `SystemExit(2)`
- [x] `generate_script.py`: `call_llm` default cambiado de `SYSTEM_PROMPT` a `SYSTEM_PROMPT_V2`
- [x] `generate_script.py`: `main()` aplanado a V2-only (sin ramas productivas V1)
- [x] `generate_script.py`: `visuals_request["schemaVersion"]` siempre 2
- [x] `generate_script.py`: `visualSchemaVersion` stdout siempre 2
- [x] Tests de retry migrados a fixtures V2 (`test_generate_script.py`)
- [x] Tests CLI invertidos para rechazo V1 (`test_generate_script_v2.py`, `test_v2_only_generation_contract.py`)
- [x] Tests focalizados: 138 passed, 0 failed

### Slice 3B1 — Eliminar V1 prompts y builders (completado, revisado y cerrado mediante el commit de esta iteración 2026-07-22)

- [x] `generate_script.py`: retirar `SYSTEM_PROMPT` V1
- [x] `generate_script.py`: retirar `_build_duration_prompt_instruction()`
- [x] `generate_script.py`: retirar `_build_retry_instruction()`
- [x] `generate_script.py`: retirar `_build_user_prompt()`
- [x] Conservar `SYSTEM_PROMPT_V2` y funciones `_v2`
- [x] Retirar tests exclusivamente V1 (17 tests: 13 tests de contenido de SYSTEM_PROMPT + 4 tests de builders V1)
- [x] Conservar tests compartidos V1/V2
- [x] Migrar tests neutrales de duración a equivalentes V2 (`test_duration_profiles.py`)
- [x] Eliminar fixture `_GOOD_3_SCENE_SCRIPT` sin callers
- [x] Eliminar `import re` y `PROMPT_PATH` sin uso residual

### Slice 3B2 — Eliminar validator V1 (completado, revisado y cerrado mediante el commit de esta iteración)

- [x] Revisar y trasladar cobertura útil del validator V1
- [x] `generate_script.py`: retirar `_validate_script_structure()`
- [x] Eliminar imports editoriales muertos
- [x] Eliminar fixtures y helpers V1 restantes
- [x] Convertir test compartido a test funcional real
- [x] Mantener `import re`, tres re.sub productivos intactos
- [x] Conservar `editorial_asset_contract.py` para fetch_images hasta Slice 4
- [x] **Conservar runtime, retry y validación V2-only**
- [x] Ejecutar tests focalizados: 132 passed, 0 failed
- [x] Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES`, sin findings bloqueantes.

### Slice 3B3 — Eliminar `--visual-schema-version` CLI (completado, revisado y cerrado mediante el commit de esta iteración)

- [x] `generate_script.py`: retirar `--visual-schema-version` CLI arg (ya no es necesario)
- [x] `run_job.py`: retirar paso de `--visual-schema-version` en `build_script_command`
- [x] Transformar tests del selector (no eliminar)
- [x] Conservar `request.visuals.schemaVersion=2`
- [x] Conservar diagnósticos `visualSchemaVersion=2`
- [x] Tests focalizados: 132 passed, 0 failed
  - test_generate_script_v2.py: 77 passed
  - test_v2_only_generation_contract.py: 7 passed
  - test_run_job.py -k build_script_command: 2 passed
  - test_generate_script.py: 10 passed
  - test_duration_profiles.py: 36 passed
- [x] Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES`, sin findings bloqueantes.

Slice 4 completado: Slice 4A, Slice 4B1 y Slice 4B2 fueron implementados, revisados y cerrados.

## Slice 4 — Remove legacy asset implementation

### Slice 4A — Retirar ramas runtime legacy de assets (completado, revisado y cerrado mediante el commit de esta iteración)

- [x] entrada assets legacy eliminada de STAGE_SCRIPTS
- [x] helpers muertos eliminados (_collect_visual_plan_schema_versions, _uses_v2_visual_assets, _check_mixed_schema_versions)
- [x] `_verify_stage_contract` simplificado a contrato V2-only
- [x] clasificación y rechazo de V1/mixed/invalid conservados
- [x] tests legacy del runner retirados (4 clases, 25 tests)
- [x] compatibilidad V2 de generación transformada
- [x] test assets-ready del runner migrado a assets/
- [x] Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES`, sin findings bloqueantes.
- [x] Tests focalizados: 184 passed, 0 failed
  - `test_run_job_v2_assets.py`: 20 passed
  - cinco clases focalizadas de `test_run_job.py`: 48 passed
  - `test_generate_script_v2.py`: 77 passed
  - `test_fetch_images_v2.py`: 39 passed

### Slice 4B1 — Retirada física del código legacy y migración de cobertura (completado, revisado y cerrado mediante el commit de esta iteración)

- [x] `bin/fetch_images.py` eliminado
- [x] `bin/editorial_asset_contract.py` eliminado
- [x] cero imports productivos o de tests hacia ambos módulos
- [x] `test_semantic_asset_validation.py` reducido de 76 a 8 tests neutrales
- [x] `test_no_topic_specific_contamination.py` reducido de 26 a 4 tests de asset_validation
- [x] `test_generate_script.py` reducido de 10 a 3 tests de retry V2
- [x] comentario stale de `asset_validation.py` corregido
- [x] README actualizado con comando V2 válido
- [x] runbook n8n actualizado sin flags V1 incompatibles
- [x] tests focalizados ejecutados
- [x] Review read-only final: `APPROVE_WITH_NON_BLOCKING_NOTES`, sin findings bloqueantes.
- [x] Tests focalizados finales: 292 passed, 0 failed.

### Slice 4B2 — Limpieza de configuración residual (completado, revisado y cerrado mediante el commit de esta iteración)

- [x] `PEXELS_API_KEY` eliminado de `.env.example`
- [x] passthrough de `PEXELS_API_KEY` eliminado de `docker-compose.yml`
- [x] cero consumidores productivos o workflows n8n de `PEXELS_API_KEY`
- [x] entrada `pexels` conservada como proveedor V2 planificado, disabled y not implemented
- [x] documentación de entorno actualizada para Pixabay y Wikimedia
- [x] FreeAI y Pollinations conservados sin cambios
- [x] Pixabay y Wikimedia conservados como proveedores activos
- [x] tests focalizados ejecutados
- [x] Review read-only: `APPROVE_WITH_NON_BLOCKING_NOTES`, sin findings bloqueantes.
- [x] Tests focalizados finales: 313 passed, 0 failed.

## Slice 5 — Product and documentation cleanup

### Slice 5A — Product identity and architecture (completado, revisado, corregido, reaprobado y cerrado mediante el commit de esta sesión)

- [x] README.md: reestructurar con identidad de generador genérico y configurable, personalización como propuesta principal, separación entre capacidades actuales y dirección futura, apertura sin referencia histórica, quick start no histórico, duración no fijada a ~1 min
- [x] `docs/project/architecture.md`: distinguir arquitectura actual de futura; retirar referencias a n8n como orquestador, `bin/fetch_images.py`, Pexels como provider activo, ElevenLabs como TTS canónico; actualizar paths de assets a `assets/`; documentar Visual Plan V2 como canónico
- [x] `docs/architecture/modular-v2-transformation-roadmap.md`: actualizar estado de partida (V1 ya no es runtime ejecutable); reflejar progreso real (Slices 1-4 completados, Slice 5 en ejecución, Slice 6 pendiente)
- [x] `openspec/changes/retire-legacy-visual-v1/tasks.md`: estructurar Slice 5 en 5A y 5B; marcar tareas de implementación 5A como completadas
- [x] `docs/project/current-state.md`: añadir bloque factual de Slice 5A implementado
- [x] `docs/sessions/20260730-214000-retire-legacy-visual-v1-slice-5a.md`: session log de implementación
- [x] Neutralizar identidad histórica residual en textos expuestos y docstrings del runtime sin alterar comportamiento
- [x] Review read-only de Slice 5A
- [x] Correcciones derivadas del review
- [x] Reaprobación read-only focalizada de Slice 5A
- [x] Cierre y commit de Slice 5A

Review formal: CHANGES_REQUIRED por F1 MEDIUM en tabla Markdown del README (fila `LLM_PROVIDER` con tres celdas en tabla de dos columnas); F1 corregido con sustitución de celda única; reaprobación read-only focalizada: APPROVED_FOR_COMMIT; Slice 5A cerrado mediante el commit de esta sesión.

### Slice 5B — Environment, integrations and operational references (implementado, corregido, reaprobado y cerrado)

- [x] Actualizar `docs/project/environment.md`: distinguir pipeline CLI canónico / infraestructura n8n·Postgres legacy / render worker; corregir requisitos de `ELEVENLABS_API_KEY`; documentar `SUBTITLE_GLOBAL_OFFSET_MS`; clasificar variables sin consumidor
- [x] Actualizar `docs/project/integrations.md`: estado de providers (Wikimedia+Pixabay activos; Pexels/FreeAI/Pollinations deshabilitados); orquestador canónico `bin/run_job.py`; n8n legacy; edge_tts default; ElevenLabs alternativa opcional
- [x] Actualizar `docs/runbooks/n8n-operations.md`: n8n como infraestructura legacy; workflows `*-v1` identificados como legacy y sin soporte de contratos/providers V2
- [x] Actualizar `AGENTS.md`: identidad genérica y contexto V2-only
- [x] Actualizar `docs/project/vision.md`: producto genérico configurable; historia como caso de uso posible
- [x] Actualizar `openspec/project.md` y `Makefile`: identidad genérica (texto cosmético)
- [x] Actualizar `.env.example`: identidad genérica; `PROJECT_ROOT` → `shorts-creator` (solo plantilla); `POSTGRES_DB` conservado con nota de compatibilidad; documentar `SUBTITLE_GLOBAL_OFFSET_MS` y variables sin consumidor
- [x] Actualizar `.opencode/agents/*.md` (5 agentes): identidad genérica
- [x] Revisar `HANDOVER.md`: preservado intacto (ya marcado como contexto legacy frío)
- [x] Revisar workflows n8n documentados: JSON preservados intactos (legacy, revisión documental)
- [x] Auditoría read-only de Slice 5B (terminó con `CHANGES_REQUIRED`)
- [x] Correcciones derivadas del review (F1–F6)
- [x] Reaprobación read-only focalizada de Slice 5B
- [x] Cierre de Slice 5B
- [x] Commit de cierre de Slice 5B

Reaprobación: SLICE_5B_REAPPROVED_FOR_CLOSURE; cero findings bloqueantes.

Slice 5B cerrado mediante el commit `1d9fe37` (`docs(project): align Slice 5B environment and integrations`).

## Slice 6 — Baseline and closure

### Slice 6A — baseline y corrección focalizada de tests

Estado: la corrección de los 11 tests neutrales (C2), la hermetización de
`test_timing_regression.py` (C5) y la corrección del aislamiento de
`test_fetch_images_v2.py::TestSourceIsolation::test_no_v1_runtime_imports`
(C4) están completas. La suite completa queda verde: baseline limpia
`1102 passed, 0 failed`. La auditoría read-only terminó con
`CHANGES_REQUIRED` exclusivamente documental; las correcciones documentales
F4–F9 están aplicadas; la reaprobación read-only focalizada terminó con
`SLICE_6A_REAPPROVED_FOR_COMMIT`. Slice 6A cerrado mediante el commit `86170d3`
(`test(v2): establish clean Slice 6A baseline`). Slice 6B se ejecutó
posteriormente (E2E V2 canónico BLOCKED); ver sección «Slice 6B».

- [x] Ejecutar tests focalizados por slice
- [x] Ejecutar suite completa — `1102 passed, 0 failed`
- [x] Clasificar fallos ligados a V1
- [x] Resolver o documentar fallos V1
- [x] Obtener baseline limpia — `1102 passed, 0 failed`
- [x] Actualizar `docs/project/current-state.md` (progreso de 6A; la actualización final de cierre queda en el cierre)
- [x] Actualizar session document (session log 6A; la actualización de cierre queda en el cierre)
- [x] Auditoría read-only de Slice 6A — CHANGES_REQUIRED
- [x] Correcciones documentales F4–F9
- [x] Reaprobación read-only focalizada de Slice 6A

Reaprobación: SLICE_6A_REAPPROVED_FOR_COMMIT.
Cero findings bloqueantes.
F1/F2 LOW y F3 NOTE aceptados como no bloqueantes.

- [x] Cierre de Slice 6A
- [x] Commit de Slice 6A

Commit de Slice 6A:
`86170d3` test(v2): establish clean Slice 6A baseline

> Nota: el E2E V2 canónico pertenece a Slice 6B y no forma parte de las tareas
> de cierre de Slice 6A.

### Slice 6B — E2E V2 canónico (ejecutado 2026-08-02)

- [x] Ejecutar primer intento controlado del E2E V2 canónico
- [x] Auditoría read-only del primer intento — SLICE_6B_REVIEW_CHANGES_REQUIRED
- [x] Implementar corrección de prompt/retry
- [x] Añadir cobertura de enum y retries
- [x] Auditoría read-only de la corrección — SLICE_6B_FIX_REVIEW_CHANGES_REQUIRED
- [x] Aplicar correcciones F1–F6 del review
- [x] Reaprobación read-only focalizada
- [x] Commit de la corrección
- [x] Nuevo E2E V2 canónico
- [ ] Obtener E2E V2 canónico PASS
- [ ] Cierre formal del change

Resultado del nuevo E2E (2026-08-02):

- Job: `cmo-2026-08-02-204451`; path `data/videos/cmo-2026-08-02-204451`
- Comando: `python3 bin/run_job.py --topic "Cómo se forma un arcoíris" --duration 30`
- Exit code top-level: 0; una única invocación
- Resultado: `REVIEW_REQUIRED`; etapa final `script` (BLOCKED controlado por contrato)
- Providers: LLM `openai` (`gpt-4o-mini`); Wikimedia activo + Pixabay activo; Pexels/FreeAI/Pollinations deshabilitados; TTS `edge_tts` (no alcanzado)
- Vídeo: ninguno (pipeline detenido en `script`)
- `qualityGate`: no ejecutado
- Causa: `DURATION_OUT_OF_RANGE: estimated=39.0s (spoken=37.6s + pauses=1.4s), target=30s, min=27s, max=30s, words=69, scenes=5`
- Session log: `docs/sessions/20260802-224326-retire-legacy-visual-v1-slice-6b-canonical-e2e-rerun.md`
- La corrección de prompt/retry sí funcionó para el contrato visual: `structureValid=true`, `request.visuals.schemaVersion=2`, `request.visuals.allowGeneratedImages=false`, cero enums inválidos (`assetPreferences`/`visualSequence` todos dentro de `ALLOWED_ASSET_PREFERENCES`), cero campos V1, `sceneNumber` secuencial 1–5.
- Persiste el exceso de palabras: wordCount=69 > maximumWords=52; retry history 60 → 56 → 69 (el retry 2 empeoró).

Reaprobación:
SLICE_6B_REVIEW_FIXES_REAPPROVED_FOR_COMMIT.

Cero findings bloqueantes.
Baseline confirmada: 1117 passed, 0 failed.

Commit de la corrección:
f48f98f fix(script): harden V2 prompt and retry contract

Resultado del primer intento: BLOCKED por contrato (`REVIEW_REQUIRED`), no PASS.

- Job ID: `cmo-2026-08-02-192443`
- Comando exacto: `python3 bin/run_job.py --topic "Cómo se forma un arcoíris" --duration 30`
- Exit code: 0 (el runner terminó de forma controlada, pero con estado final `REVIEW_REQUIRED`)
- Status final: `REVIEW_REQUIRED`; `lastCompletedStage`: `script`
- `qualityGate`: N/D (no se alcanzó la etapa `validate`)
- Duración solicitada: 30s (perfil `short_25_30`)
- Provider LLM: `openai` (cliente OpenAI-compatible); modelo `gpt-4o-mini`
- Providers visuales: Wikimedia activo, Pixabay activo (con key); Pexels/FreeAI/Pollinations deshabilitados
- Provider TTS: `edge_tts` (no alcanzado)
- Vídeo final: no producido (se detuvo en `script`)

Causa (documentada, sin corrección de código en esta sesión):
- `VISUAL_PLAN_V2_INVALID: v2 plan validation failed after 3 attempts`
  - `V2_STRUCTURE_INVALID_ENUM_VALUE:assetPreferences[0]: scene 3: got 'animation'`
  - `V2_STRUCTURE_INVALID_ENUM_VALUE:visualSequence[0].assetPreference: scene 3: got 'animation'`
  - `V2_STRUCTURE_INVALID_ENUM_VALUE:assetPreferences[0]: scene 5: got 'infographic'`
  - `V2_STRUCTURE_INVALID_ENUM_VALUE:visualSequence[0].assetPreference: scene 5: got 'infographic'`
  - Los enum permitidos son: archive, diagram, document, generated, illustration, map, painting, photograph, stock.
- `DURATION_OUT_OF_RANGE: estimated=30.9s (spoken=29.5s + pauses=1.4s), target=30s, min=27s, max=30s, words=54, scenes=5`
- Retry history: retry 0 = 74 words (reduce_content); retry 1 = 59 words (reduce_content); retry 2 = 54 words + enums inválidos (fix_v2_structure_then_duration). Tras 3 intentos el plan V2 siguió inválido → REVIEW_REQUIRED.

Auditoría de contrato V2 del job:
- `request.visuals.schemaVersion == 2`
- `script.scenes` = 5, todas con `visualPlan._schemaVersion == 2` (sin mezcla V1/V2)
- Campos V1 residuales (`editorialRole`, `strategy`, `primaryAssetType`, `secondaryAssetType`, `visualTemporalIntent`): 0 apariciones
- El orquestador respetó el contrato y terminó de forma controlada en `script`.

Corrección de prompt/retry (Build):
- Prompt: el enum de `assetPreferences` se deriva de `ALLOWED_ASSET_PREFERENCES`
  vía `_build_asset_preferences_section()`; sin listas manuales divergentes.
  `generated` condicionado a `allowGeneratedImage`; `diagram` definido como valor
  exacto; regla de enum cerrado y términos prohibidos (animation, animated,
  infographic, photo, image, video).
- Retry: `_build_retry_instruction_v2` es ahora siempre contractual — toda rama
  (incluida `reduce_content`) re-declara el enum cerrado, prohíbe sinónimos,
  ordena preservar campos `visualPlan` válidos, fija el límite absoluto de
  palabras y pide revalidar estructura y duración antes de responder.
- Alias `infographic → diagram`: NO implementado (requeriría segunda
  canonicalización; se documenta como mejora futura). `animation` e `infographic`
  continúan inválidos.
- Validator (`visual_plan_v2.py`), runner (`run_job.py`), perfiles
  (`duration_profiles.py`) y contrato temporal intactos. `MAX_SCRIPT_ATTEMPTS == 3`.
- Tests: 8 añadidos (T1–T7) en `tests/test_generate_script_v2.py`.
- Suite completa: `1110 passed, 0 failed`. Cero providers reales; cero commit.

Session log del E2E: `docs/sessions/20260802-212305-retire-legacy-visual-v1-slice-6b-e2e.md`
Session log del fix (Build): `docs/sessions/20260802-214507-retire-legacy-visual-v1-slice-6b-script-contract-fix.md`

La corrección de prompt/retry y la cobertura de enum/retries están implementadas
(ver el session log del Build y `current-state.md`). La auditoría read-only de la
corrección terminó con `SLICE_6B_FIX_REVIEW_CHANGES_REQUIRED` (F1/F2 MEDIUM,
F3–F6 LOW); las correcciones F1–F6 están aplicadas y fueron reaprobadas
read-only (`SLICE_6B_REVIEW_FIXES_REAPPROVED_FOR_COMMIT`), commiteadas
(`f48f98f`) y seguidas del nuevo E2E V2 canónico. [histórico, ya cerrado]

Correcciones F1–F6 aplicadas (Build del review fixes):
- F1: gate request-scoped de `generated`. `allow_generated_images` se define antes
  de construir `base_prompt` y gobierna primer prompt, retry, validación y
  `request.visuals.allowGeneratedImages` (mismo booleano, sin duplicación). El
  primer prompt incluye un bloque `## Restricción visual de esta request` con el
  valor real (false). `_build_user_prompt_v2` recibe `allow_generated_images`
  (keyword-only) y admite el caso futuro true.
- F2: Slice 6A en `tasks.md` ya no lista el E2E (pertenece a 6B); se añadió una
  nota y se eliminó la sección `Pendientes` que re-listaba E2E/cierre.
- F3: los términos prohibidos (animation, animated, infographic, photo, image,
  video) se limitan explícitamente a valores del enum en
  `_build_asset_preferences_section` y `_build_asset_preference_constraint_block`,
  con aclaración de que pueden aparecer en `searchQueries`/`subjects`.
- F4: `_build_retry_instruction_v2` transmite `issue["path"]` explícitamente
  (código, path y mensaje separados), sin duplicar `scenes[x].visualPlan` cuando
  el path ya está cualificado, y también para issues sin `sceneNumber`.
- F5: test integrado hermético del flujo real `reduce_content` vía `main()`
  (2 calls, status SCRIPT_DRAFT, durationContract PASS).
- F6: T1 (asserts de slice), T2 (gate real false/true), T4 (paths explícitos en
  issues independientes) y T5 (parametrizado; valida ambos paths) reforzados.

Resultados del review fixes:
- Tests focalizados: `test_generate_script_v2.py` = 92 passed; generación
  combinada = 138 passed; `test_run_job.py` = 91 passed.
- Collect-only: `1117 tests collected`, cero errores de colección.
- Suite completa: **`1117 passed, 0 failed`** (baseline anterior `1110`; +7 tests).
  Cero skips, cero xfail, cero warnings.
- Cero providers reales; cero commit; ningún nuevo E2E; ningún PASS en el momento
  del Build del review. [histórico del primer Build del review; cerrado después
  mediante `f48f98f` y el nuevo E2E]
- Pendiente (estado vigente): la corrección temporal de duración (exceso de
  palabras) del nuevo E2E, revisión read-only de esa corrección, commit de la
  corrección temporal, un siguiente E2E V2 canónico PASS y el cierre formal del
  change.

### Nota sobre la hermetización de `test_timing_regression.py` (6A2)

- Los 4 tests de timing se reescribieron bajo Estrategia A: importan las funciones
  puras de `bin/generate_audio.py` (`build_full_narration`, `_build_canonical_tokens`,
  `_match_words_to_canonical`, `group_words_into_cues`, `_strip_punct`) y usan
  WordBoundary/cues sintéticos deterministas. No se contacta Edge TTS en la suite
  normal. Resultado focalizado: `4 passed`.
- Resultado focalizado combinado (`test_run_job.py` + `test_timing_regression.py` +
  `test_semantic_asset_validation.py`): `103 passed`.

### Corrección de aislamiento de imports (6A3)

- Causa raíz C4: `tests/test_fetch_images_v2.py::TestSourceIsolation::test_no_v1_runtime_imports`
  hacía `sys.modules.pop("run_job", None)` (y otros módulos) sin restauración; el
  `monkeypatch.setattr(sys, "modules", sys.modules)` era un no-op. Por orden
  alfabético, `test_run_job.py` corría después y sus `patch("run_job.*")`
  reimportaban un módulo `run_job` nuevo, distinto del objeto que `main()` usaba
  ya importado. Resultado: `20 failed, 1082 passed` en la suite completa.
- Corrección: las eliminaciones de `sys.modules` se movieron a
  `with monkeypatch.context() as scoped:` usando `scoped.delitem(sys.modules, mod, raising=False)`,
  que registra y restaura el valor original al salir del bloque. Se añadió
  verificación de identidad post-contexto (objeto original restaurado, o ausencia
  conservada).
- Contrato conservado: durante el contexto, el test sigue comprobando que
  `fetch_images_v2.main()` no reimporta los módulos legacy retirados
  (`fetch_images`, `asset_validation`, `editorial_asset_contract`) ni los módulos
  productivos vigentes bloqueados por aislamiento de capas (`generate_script`,
  `prepare_job`, `render_job`, `run_job`). La variable de test continúa llamándose
  `v1_modules`, aunque su nombre es impreciso y no implica que los siete módulos
  sean legacy. Sin debilitar la lista prohibida ni eliminar assertions.
- Ambos órdenes del par contaminante/inverso: `2 passed` cada uno; prueba mínima
  de 4 tests: `4 passed`; archivos `test_fetch_images_v2.py` + `test_run_job.py`
  en ambos órdenes: `130 passed` cada uno.
- Slice 6A cerrado mediante el commit `86170d3`. Slice 6B ejecutado posteriormente
  (E2E V2 canónico BLOCKED); ver sección «Slice 6B».

### Fallo adicional de suite (Caso B, resuelto en 6A3)

Resultado intermedio histórico de 6A2: suite completa `20 failed, 1082 passed`.
Resuelto en 6A3. C4 ya no está pendiente.

- `test_run_job.py`: `91 passed` en aislamiento.
- Los 20 fallos eran de `test_run_job.py`, preexistentes (reproducibles con
  `--ignore=tests/test_timing_regression.py`).
- Causa C4: `tests/test_fetch_images_v2.py::test_no_v1_runtime_imports` hacía
  `sys.modules.pop("run_job", None)` sin restauración (el `monkeypatch.setattr(sys,
  "modules", sys.modules)` es un no-op). Por orden alfabético, `test_run_job.py`
  corría después y sus `patch("run_job.*")` quedaban rotos.
- Clasificación: C4 — test demasiado acoplado por mutar estado global sin restaurar.
- Corrección (6A3): las eliminaciones de `sys.modules` se movieron a
  `with monkeypatch.context() as scoped:` usando
  `scoped.delitem(sys.modules, mod, raising=False)`.
- Baseline posterior: `1102 passed, 0 failed`. C4 ya no está pendiente.

### Slice 6B — Follow-up temporal (retry de duración por compresión de voiceovers)

Sesión: `retire-legacy-visual-v1-slice-6b-duration-retry-fix` (Build).

- [x] Auditoría read-only del segundo E2E — SLICE_6B_DURATION_REVIEW_CHANGES_REQUIRED
- [x] Implementar retry temporal basado en voiceovers anteriores
- [x] Añadir budget determinista por escena
- [x] Añadir protección anti-regresión y best attempt
- [x] Añadir cobertura de convergencia
- [x] Review read-only de la corrección temporal — SLICE_6B_DURATION_FIX_REVIEW_CHANGES_REQUIRED
- [x] Aplicar correcciones F1–F4 del review
- [x] Aplicar hardening F5–F7
- [x] Primera reaprobación focalizada — SLICE_6B_DURATION_REVIEW_FIXES_REAPPROVAL_CHANGES_REQUIRED
- [x] Corregir F8: usar candidato canónico en compression prompt y merge
- [x] Añadir cobertura canónica del prompt y merge
- [x] Reaprobación final read-only de la corrección temporal — SLICE_6B_DURATION_CANONICAL_FOLLOWUP_REAPPROVED_FOR_COMMIT
- [x] Commit de la corrección temporal — 9eb1f13
- [ ] Siguiente E2E V2 canónico

Estado del follow-up temporal:

- El segundo E2E V2 canónico (job `cmo-2026-08-02-204451`) quedó BLOCKED
  (`REVIEW_REQUIRED`) en `script` **únicamente** por duración
  (`DURATION_OUT_OF_RANGE`); el contrato visual ya era válido
  (`structureValid=true`, cero enums inválidos).
- Auditoría read-only: `SLICE_6B_DURATION_REVIEW_CHANGES_REQUIRED`, diagnóstico
  D1/D2/D3/D4/D6/D7 confirmado y D8 como factor contribuyente.
- Corrección implementada (Build): retry temporal especializado de compresión de
  voiceovers, reparto determinista del máximo global por escena
  (`_allocate_scene_word_caps`), merge local seguro (`_apply_voiceover_repair`),
  protección anti-regresión con best attempt y trazabilidad ampliada en
  `retryHistory`.
- Review read-only de la corrección: `SLICE_6B_DURATION_FIX_REVIEW_CHANGES_REQUIRED`
  — F1 HIGH (system prompt de compresión usaba `SYSTEM_PROMPT_V2`), F2 MEDIUM
  (`{expected}` literal), F3 MEDIUM (caps solo telemetría), F4 MEDIUM (flag de
  regresión), F5–F7 LOW.
- Correcciones aplicadas (esta sesión):
  - F1: constant `VOICEOVER_COMPRESSION_SYSTEM_PROMPT`; selección por estrategia
    (`compression` → prompt dedicado; resto → `SYSTEM_PROMPT_V2`).
  - F2: `{expected}` interpolado a la secuencia real (p. ej. `[1, 2, 3, 4, 5]`).
  - F3: enforcement real de caps (`MIN_WORDS_PER_SCENE <= wordCount <= sceneWordCap`)
    con `REPAIR_SCENE_WORD_MINIMUM_NOT_MET`, `REPAIR_SCENE_WORD_CAP_EXCEEDED` y
    `REPAIR_INVALID_SCENE_CAPS`; semántica `repairShapeValid`/`repairBudgetValid`/
    `repairPayloadValid`.
  - F4: flag `lastAttemptDiscardedAsRegression` corregido vía ranking centralizado
    (`_candidate_rank`) y telemetría `candidateUpdated`/`candidateRank`.
  - F5: representación canónica siempre participa (best candidate, compresión,
    persistencia) aunque falle la duración.
  - F6: telemetría de payload rechazado (`candidateReused`, `wordCountSource`).
  - F7: `acceptedAsBest` final inequívoco (uno solo) con `becameBestCandidate` de
    telemetría durante el bucle.
- Validator (`visual_plan_v2.py`), runner (`run_job.py`) y perfiles
  (`duration_profiles.py`) intactos. `MAX_SCRIPT_ATTEMPTS == 3`.
- Suite completa vigente: **`1155 passed, 0 failed`** (baseline anterior `1138`;
  +17 tests). Cero skips, cero xfail, cero warnings.
- Primera reaprobación read-only focalizada:
  `SLICE_6B_DURATION_REVIEW_FIXES_REAPPROVAL_CHANGES_REQUIRED`. F1–F4 y F6–F7
  resueltos; **F8 MEDIUM bloqueante** (compression prompt y merge usaban la
  representación raw en lugar de la canónica); **F9–F11 LOW** (F9 aceptado como
  no bloqueante; F10 gaps de cobertura; F11 tracking documental corregido).
- F8 corregido en el follow-up canónico: representación activa única y canónica
  (`candidate_script = canonical` cuando `v2_valid == true`) usada en el
  compression prompt, el merge, el siguiente retry, el best candidate y la
  persistencia. Rama estructural inválida intacta (sin candidato inventado).
- Cobertura canónica añadida: compression prompt recibe candidato canónico,
  base del merge canonicalizada, y seis escenas en el prompt.
- Suite completa vigente tras F8: **`1158 passed, 0 failed`** (baseline anterior
  `1155`; +3 tests). Cero skips, cero xfail, cero warnings.
- Pendiente: reaprobación final read-only, commit de la corrección y siguiente
  E2E V2 canónico.
- No se ejecutó un tercer E2E; ningún PASS; sin commit; sin cierre. El change
  `retire-legacy-visual-v1` continúa abierto.
