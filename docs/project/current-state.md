# Estado actual del proyecto

**Última actualización:** 2026-07-25

## Estado global

Pipeline funcional de vídeos cortos verticales (9:16, ~1 min). Scripts en `bin/` operativos. n8n como orquestador legacy. Docker para render.

**Último change completado:** `integrate-native-visual-plan-v2-generation` (2026-07-14)

**Change pausado:** `improve-short-form-audio-pacing-v2` — Phase A completada, Phase B pendiente (se reanudará tras migrar dominio script)

**Change activo:** `retire-legacy-visual-v1` — Primera fase del plan de transformación modular. Slice 1 implementado, revisado y commiteado. Slice 2 implementado, revisado y cerrado mediante commit. Slice 3A implementado, revisado y cerrado mediante commit. Slice 3B1 implementado, revisado y cerrado mediante el commit de esta iteración. Slice 3B2 implementado, revisado y cerrado mediante el commit de esta iteración. Slice 3B3 implementado, revisado y cerrado mediante el commit de esta iteración. Slice 4A implementado, revisado y cerrado mediante el commit de esta iteración. Slice 4B1 implementado, revisado y cerrado mediante el commit de esta iteración. Slice 4B2 permanece pendiente.

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
- Configuración Pexels no modificada.
- Slice 4B2 no iniciado.

## Resumen

- Slice 3B1: 157 tests focalizados pasados, 0 fallidos
- Slice 3B2: 132 tests focalizados pasados, 0 fallidos
- Slice 3B3: 132 tests focalizados pasados, 0 fallidos
- Slice 4A: implementado, revisado y cerrado mediante el commit de esta iteración
- Slice 4B1: implementado, revisado y cerrado mediante el commit de esta iteración

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

1. Slice 4B2 del change `retire-legacy-visual-v1`: resolver la configuración residual de proveedores y PEXELS_API_KEY.
2. Phase B de audio pacing (tras migrar script/)
3. Crear `pyproject.toml` y estructura `src/`
4. Investigar instalación de ffprobe en el host
5. Registrar FreeAI para imágenes de calidad gratuitas
6. Integrar pipeline v2 con n8n

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
