# Sesión: retire-legacy-visual-v1-slice-6a-baseline

## 1. Configuración

- **Sesión:** `retire-legacy-visual-v1-slice-6a-baseline`
- **Modelo:** `opencode/deepseek-v4-flash-free`
- **Variante:** `default`
- **Modo:** `Build`
- **Máximo de pasos agentic:** 22
- **Subagentes:** ninguno
- **MCP:** desactivado
- **Llamadas MCP:** 0

Objetivo: Slice 6A — baseline y corrección focalizada de tests. No ejecutar el
E2E real de Slice 6B y no cerrar el change.

## 2. Estado Git inicial

```
Repositorio: /home/javi/projects/shorts-creator
Rama:       main
HEAD:       3866cc6a547545cad70cc1c5fbbacb08ef216713
Working tree: limpio
Staging:    0
Untracked:  0
git diff --check: limpio
```

Últimos commits: `3866cc6` (record Slice 5B closure), `1d9fe37` (align Slice 5B).

## 3. Baseline anterior y por qué quedó obsoleta

La cifra `1215 passed, 16 failed` era la baseline de referencia previa. Queda
obsoleta como cifra de suite completa porque en esta sesión la suite no pudo
ejecutarse de forma segura (ver §10). No se reutiliza como baseline real.

## 4. Reproducción de los 11 fallos

Comando: `python3 -m pytest -q tests/test_run_job.py --tb=short`

Resultado: `11 failed, 80 passed`. El conjunto coincidía exactamente con el
esperado:

- `test_non_zero_exit_fails_metadata`
- `test_stop_after_assets_does_not_run_audio`
- `test_asset_failure_stops_before_audio`
- `test_assets_exit0_but_stale_status_fails`
- `test_audio_exit0_but_no_audio_file_fails`
- `test_prepare_missing_subtitle_fails_pipeline`
- `test_render_exit0_but_no_video_fails`
- `test_render_exit1_with_warnings_and_video_succeeds`
- `test_render_exit1_with_failure_and_no_video_fails`
- `test_validate_exit0_sets_validated`
- `test_prepare_exit1_fails_pipeline`

Todos abortaban en la etapa `assets` con `ERROR [assets]: INVALID_VISUAL_SCHEMA`.

## 5. Mapa de fixtures y consumidores

| Fixture/helper | Tests consumidores | Requiere V2 válido | Requiere incompleta/V1/invalid |
| -------------- | ------------------ | ------------------ | ------------------------------ |
| `fake_job_dir` | todos los pipeline tests | — (solo dir temporal) | — |
| `fake_metadata` | `test_append_orchestration*`, `test_set_failure*`, `test_failure_no_*` | no (helpers puros) | no |
| `initial_metadata_file` | `test_stop_after_assets`, `test_assets_exit0_stale`, `test_audio_exit0`, `test_prepare_missing_subtitle`, `test_render_*`, `test_validate_exit0`, `test_prepare_exit1*` | sí (multi-etapa) | no |
| `metadata`/`script_meta` inline | los 11 tests (via `load_metadata` parcheado) | sí | no |
| `assets_meta`/`audio_meta`/`prepare_meta`/`render_meta` inline | multi-etapa | sí | no |
| `V2_FIXTURE` + `TestClassifyVisualSchema` | tests `_classify_visual_schema` (V1/mixed/invalid/v2) | — | sí (los tests negativos) |

Los tests negativos de schema (V1, mixed, invalid) no usan `initial_metadata_file`
ni los dicts inline migrados; no se tocaron.

## 6. Estrategia de migración

Se eligió un helper explícito y mínimo que enriquece una metadata neutral con el
contrato V2, aplicado a los dicts inline de los 11 tests. No se modifica
`bin/run_job.py` y no se debilita la validación fail-closed.

## 7. Contrato V2 mínimo confirmado

`_classify_visual_schema` (`bin/run_job.py:51`) exige, para `SUPPORTED_V2`:

- metadata dict no vacío;
- `script` dict con `scenes` lista no vacía;
- cada escena: dict con `visualPlan` dict y `visualPlan._schemaVersion == 2`
  (int, no bool);
- `request.visuals.schemaVersion`, si existe, debe ser int 2 (no bool); si
  `request`/`visuals` no existen, no bloquea.

Mínimo válido usado:

```json
{"script": {"scenes": [{"sceneNumber": 1, "visualPlan": {"_schemaVersion": 2}}]}}
```

## 8. Diff realizado en `tests/test_run_job.py` (+85/−46 aprox.)

- Añadido helper `_v2_meta(meta)`: devuelve copia con `script.scenes[].visualPlan._schemaVersion=2`
  si no existe `script`; no muta objetos compartidos y no inventa campos.
- Aplicado `_v2_meta` a los dicts inline de los 11 tests (`metadata`,
  `script_meta`, `assets_meta`, `audio_meta`, `prepare_meta`, `render_meta`,
  `validated_meta`, `stale_meta`).
- Añadida imagen `assets/seg_001.jpg` en los tests multi-etapa que requieren que
  la etapa `assets` pase su contrato de salida (contrato exige imágenes reales en
  `assets/` cuando el status es `ASSETS_READY`).
- Corregida la coincidencia de comando `"fetch_images.py"` → `"fetch_images_v2.py"`
  en `test_stop_after_assets_does_not_run_audio` y `test_asset_failure_stops_before_audio`.
  Justificación: el runner canónico ejecuta `fetch_images_v2.py`; con el matcher
  legacy, la rama de assets nunca se activaba y estos dos tests no podían
  corregirse (el test de fallo de assets no contabilizaba la llamada).

## 9. Tests focalizados

- 11 tests conocidos: `11 passed`.
- `test_run_job.py`: `91 passed`.
- `test_run_job.py` + `test_semantic_asset_validation.py`: `99 passed`.
- Generación/runner V2: `107 passed`.
- Assets V2: `290 passed`.
- Dry-run E2E: `22 passed`.

## 10. Suite completa y clasificación de fallos residuales

- `--collect-only tests/`: `1102 tests collected`, cero errores de colección,
  no recorre `data/postgres/`.
- Preflight de red/Docker: subprocess, urllib, docker y ffprobe están mockeados/
  fakeados en la práctica totalidad de archivos. `test_continuous_audio.py` usa
  docker/subprocess reales pero no tiene funciones `test_` (solo `__main__`), por
  lo que no se recopila.
- **Bloqueo:** `tests/test_timing_regression.py` contiene 4 tests
  (`test_sentence_boundary_crossing`, `test_punctuation_restoration`,
  `test_no_cross_scene_leakage`, `test_no_single_word_by_boundary`) que invocan
  `bin/generate_audio.py --subtitle-timing-provider edge_tts` mediante subprocess
  real y sin mock. Edge TTS es un servicio de red real
  (`bin/generate_audio.py:956` usa el provider `edge_tts` que sintetiza en red).
  `.venv/bin/python3` y `data/videos/la-2026-07-01-173458` existen, por lo que la
  llamada se ejecutaría de verdad.
- La suite completa `python3 -m pytest -q tests/` NO se ejecutó.
- `test_timing_regression.py` NO se modificó (fuera de alcance autorizado; no se
  añadieron skips ni cambios de configuración pytest).
- Clasificación del bloqueo: dependencia de entorno/red real (Edge TTS). No es
  una regresión V1 ni V2; es una integración externa real no mockeada. No se
  ejecutó ningún otro fallo adicional de la suite.

## 11. Baseline resultante

- Sin baseline completa verde: la suite no pudo ejecutarse.
- Baseline parcial de Slice 6A:
  - `test_run_job.py`: `91 passed`;
  - grupos V2 focalizados: `107`/`290`/`22`;
  - `test_semantic_asset_validation.py`: 8 passed.
- La cifra anterior `1215 passed, 16 failed` queda obsoleta como referencia de
  suite completa.

## 12. Restricciones respetadas

- No se modificó `bin/run_job.py` ni ningún otro archivo de `bin/` o `tests/`
  fuera de `tests/test_run_job.py`.
- No se restauró compatibilidad V1 ni se debilitó `INVALID_VISUAL_SCHEMA`.
- No se cambiaron expected statuses ni se sustituyeron aserciones.
- No se eliminaron tests, ni se marcaron `skip`/`xfail`.
- Tests negativos de schema (V1, mixed, invalid) intactos.
- No se ejecutó llamada real a proveedor externo alguno.
- No se ejecutó el E2E de Slice 6B.

## 13. Estado pendiente de review

Cambios sin stagear, listos para auditoría read-only. No se ha declarado Slice 6A
revisado ni cerrado. No se ha cerrado `retire-legacy-visual-v1`.

Verdict de sesión: `SLICE_6A_BASELINE_BLOCKED`.

## 14. Estado Git final

```
Rama:          main
HEAD:          3866cc6a547545cad70cc1c5fbbacb08ef216713 (sin cambios)
Working tree:  modificado (sin stagear)
Staging:       0
```

Archivos modificados:

- `M tests/test_run_job.py`
- `M openspec/changes/retire-legacy-visual-v1/tasks.md`
- `M docs/project/current-state.md`
- `?? docs/sessions/20260801-000000-retire-legacy-visual-v1-slice-6a-baseline.md`

Cero staging, cero commit, cero push, cero MCP, cero reindexado. Cero E2E real,
cero providers reales. `git diff --check` limpio.

---

# Follow-up 6A2 — hermetización de `test_timing_regression.py`

## 1. Sesión y configuración

- **Sesión:** `retire-legacy-visual-v1-slice-6a2-hermetic-timing-tests`
- **Modelo:** `opencode/deepseek-v4-flash-free`
- **Variante:** `default`
- **Modo:** `Build`
- **Máximo de pasos agentic:** 24
- **Subagentes:** ninguno
- **MCP:** desactivado
- **Llamadas MCP:** 0

Objetivo: eliminar el bloqueo de suite heredado de 6A hermetizando los cuatro
tests de timing. No ejecutar E2E de Slice 6B ni cerrar el change.

## 2. Estado Git heredado

- Rama `main`; HEAD `3866cc6a547545cad70cc1c5fbbacb08ef216713` (sin cambios).
- Working tree con los cambios de 6A sin stagear:
  - `M tests/test_run_job.py`
  - `M openspec/changes/retire-legacy-visual-v1/tasks.md`
  - `M docs/project/current-state.md`
  - `?? docs/sessions/20260801-000000-retire-legacy-visual-v1-slice-6a-baseline.md`
- `git diff --check` limpio (salvo el warning ignorado de `data/postgres/`).
- `tests/test_run_job.py` verde en aislamiento: `91 passed`.

## 3. Clasificación C5 del bloqueo heredado

El bloqueo de suite de 6A se confirma como:

```text
C5 — dependencia de entorno/integración externa no hermética
```

Cuatro tests (`test_sentence_boundary_crossing`, `test_punctuation_restoration`,
`test_no_cross_scene_leakage`, `test_no_single_word_by_boundary`) invocaban
`bin/generate_audio.py --subtitle-timing-provider edge_tts` mediante subprocess
real y sin mock. Edge TTS es un servicio de red real. No es una regresión V1 ni
V2.

## 4. Análisis de los cuatro tests

| Test | Input original | Contrato que valida | Dependencia externa actual | Salida/assertions |
| ---- | -------------- | ------------------- | -------------------------- | ----------------- |
| `test_sentence_boundary_crossing` | metadata 2 escenas + Edge TTS | agrupación de cues sin cruce de límites de oración | subprocess `generate_audio.py` + Edge TTS red | cue1 de escena 1 sin "Segunda"/"Tercera" |
| `test_punctuation_restoration` | metadata 2 escenas + Edge TTS | restauración de puntuación desde texto canónico | idem | algún cue contiene "oración." |
| `test_no_cross_scene_leakage` | metadata 2 escenas + Edge TTS | cues respetan ventanas de escena (sin fuga entre escenas) | idem | cues esc1 sin "comienza"; cues esc2 sin "Primera" |
| `test_no_single_word_by_boundary` | metadata 2 escenas + Edge TTS | no se crea cue de una sola palabra solo por boundary | idem | cada cue esc1 ≥ 2 palabras salvo último en borde |

Contratos reales bajo prueba: canonicalización (`_match_words_to_canonical`),
agrupación por escena y oración (`group_words_into_cues`), restauración de
puntuación (via tokens canónicos) y splitting de cues. NO se prueba síntesis de
voz ni persistencia de metadata; `subtitleTiming.cues` era el único artefacto
usado por las assertions.

## 5. Funciones productivas reutilizadas

De `bin/generate_audio.py` (importadas, no modificadas):

- `build_full_narration(scenes)` → `(full_text, narration_units)`
- `_build_canonical_tokens(narration_units)` → tokens canónicos con sceneNumber
- `_match_words_to_canonical(words, canonical_tokens)` → palabras anotadas + metrics
- `group_words_into_cues(words, sentence_boundaries=None)` → cues
- `_strip_punct(text)` → normalización de puntuación para eventos sintéticos

El `import edge_tts` en `bin/tts_provider.py` es lazy (dentro de métodos), por lo
que importar `generate_audio` no abre red ni instancia provider.

## 6. Estrategia elegida: A — funciones puras con eventos sintéticos

Se eligió la Estrategia A (prioridad máxima y viable): los cuatro tests se
reescriben para ejercitar las funciones puras del pipeline de timing con
WordBoundary/cues sintéticos deterministas, sin subprocess, sin audio real, sin
red, sin `.venv` y sin `data/videos/la-2026-07-01-173458`.

Justificación: la lógica bajo prueba ya está separada de la síntesis. El contrato
completo (`_match_words_to_canonical` + `group_words_into_cues`) cubre todas las
invariantes de los cuatro tests. No se necesita la Estrategia B ni C.

## 7. Cambios exactos en `tests/test_timing_regression.py`

- Eliminados: `VENV_PYTHON`, `GENERATE_AUDIO`, `PREPARE_JOB`, `TEST_JOB_DIR`,
  `REF_JOB_DIR`, `_build_metadata`, `run`, `_run_audio_and_load`, `setup_job`.
- Añadido: import de las funciones puras de `bin/generate_audio.py` vía
  `importlib.import_module` con `sys.path` extendido a `bin`.
- Añadido: `SCENES` sintéticos (2 escenas deterministas), `WORD_DURATION = 0.5`.
- Añadido: helper `_build_cues()` que construye eventos WordBoundary sintéticos
  (texto sin puntuación, offsets/duraciones fijos), ejecuta el pipeline puro y
  agrupa cues por `sceneNumber`. Incluye un guard de `unmatchedRatio <= 0.10`.
- Añadido: fixture `hermetic_guard(monkeypatch)` que falla de inmediato si algún
  camino intenta `subprocess.run`/`Popen`, `socket.create_connection`,
  `socket.socket`, o instancia un provider TTS real (`generate_audio.get_provider`).
- Los cuatro tests conservan nombre, docstring y assertions semánticas, aplicados
  a los cues puros por escena. Se conserva el guard de `_build_cues()` sobre la
  calidad del canonical matching.

## 8. Garantías de hermeticidad

- Sin `subprocess` (run/Popen bloqueados por `hermetic_guard`).
- Sin red (`socket.create_connection`/`socket.socket` bloqueados).
- Sin provider TTS real (`generate_audio.get_provider` bloqueado).
- Sin Docker; sin escritura bajo `data/videos/`, `data/audio/`, `data/metadata/`.
- Sin `.venv`; sin `data/videos/la-2026-07-01-173458`.
- Import del módulo `generate_audio` sin efectos colaterales (edge_tts lazy).
- `git status` de `data/videos`, `data/audio`, `data/metadata`: vacío tras la
  ejecución focalizada.

## 9. Resultado focalizado

- `python3 -m pytest -q tests/test_timing_regression.py` → `4 passed`.
- Combinado (`test_run_job.py` + `test_timing_regression.py` +
  `test_semantic_asset_validation.py`) → `103 passed`.

## 10. Regresiones focalizadas V2

- Generación/runner V2 (`test_generate_script.py`, `test_generate_script_v2.py`,
  `test_v2_only_generation_contract.py`, `test_run_job_v2_assets.py`): `107 passed`.
- Assets V2 (`test_fetch_images_v2.py`, `test_visual_provider_config_v2.py`,
  `test_visual_asset_executor_v2.py`, `test_visual_asset_router_v2.py`,
  `test_visual_asset_bridge_v2.py`): `290 passed`.
- Dry-run E2E (`test_visual_v2_dry_run_e2e.py`): `22 passed`.

## 11. Preflight de suite y ejecución completa

- `--collect-only tests/`: `1102 tests collected`, cero errores de colección.
- Preflight de efectos externos: subprocess/urllib/socket/edge_tts aparecen en la
  suite, pero todos están mockeados o son imports sin red. `test_continuous_audio.py`
  usa docker/subprocess reales pero solo tiene `main()` (sin funciones `test_`),
  por lo que no se recopila.
- `python3 -m pytest -q tests/ --tb=short`:
  `20 failed, 1082 passed in 12.25s`.

## 12. Fallos adicionales de la suite (Caso B)

Los 20 fallos son exclusivamente de `tests/test_run_job.py` y son **preexistentes**
(reproducibles con `--ignore=tests/test_timing_regression.py`).

- **Causa raíz:** `tests/test_fetch_images_v2.py::test_no_v1_runtime_imports` hace
  `sys.modules.pop("run_job", None)` y luego `monkeypatch.setattr(sys, "modules",
  sys.modules)` (un no-op de restauración), dejando `run_job` fuera de
  `sys.modules` de forma permanente para el resto de la sesión. Por el orden
  alfabético de pytest (`fetch_images_v2` < `run_job`), `test_run_job.py` corre
  después y sus `patch("run_job.*")` apuntan a un módulo re-importado, no al que
  usa `main()`, rompiendo 20 tests del runner.
- Reproducción mínima sin mi cambio:
  `pytest tests/test_fetch_images_v2.py tests/test_run_job.py::test_script_stage_extracts_job_id`
  → `FileNotFoundError` en `run_job.load_metadata`.
- **Clasificación:** C4 — test incorrecto/demasiado acoplado por mutar estado
  global (`sys.modules`) sin restauración. Fuera del conjunto autorizado de esta
  sesión (no se modifica `test_fetch_images_v2.py` ni `test_run_job.py`).

## 13. Baseline

- No se obtiene una baseline completa verde en esta sesión por el fallo preexistente
  C4. La suite se ejecuta: `20 failed, 1082 passed`.
- Baseline focalizada de 6A2: `test_run_job.py` = 91, `test_timing_regression.py` = 4,
  combinado = 103, V2 = 107/290/22.
- La baseline histórica `1215 passed, 16 failed` queda obsoleta como referencia de
  suite completa y es sustituida por los resultados reales de esta sesión.

## 14. Estado

- `tests/test_timing_regression.py` hermetizado (4/4 verde).
- Pendiente de auditoría read-only (cambios sin stagear).
- `Obtener baseline limpia` queda pendiente por el fallo C4.
- Slice 6B no iniciado.
- Cero E2E real, cero providers reales, cero red, cero Docker.

Verdict de sesión: `SLICE_6A_BASELINE_NEEDS_FOLLOWUP`.

## 15. Estado Git final

```
Rama:          main
HEAD:          3866cc6a547545cad70cc1c5fbbacb08ef216713 (sin cambios)
Staging:       0
```

Archivos modificados (máximo permitido):

- `M tests/test_run_job.py` (heredado de 6A, sin cambios en 6A2)
- `M tests/test_timing_regression.py`
- `M openspec/changes/retire-legacy-visual-v1/tasks.md`
- `M docs/project/current-state.md`
- `?? docs/sessions/20260801-000000-retire-legacy-visual-v1-slice-6a-baseline.md`

Cero staging, cero commit, cero push, cero MCP, cero reindexado. Cero red,
providers, Docker y E2E real. `git diff --check` limpio.

---

# Follow-up 6A3 — aislamiento de imports y baseline completa

## 1. Sesión y configuración

- **Sesión:** `retire-legacy-visual-v1-slice-6a3-import-isolation`
- **Modelo:** `opencode/deepseek-v4-flash-free`
- **Variante:** `default`
- **Modo:** `Build`
- **Máximo de pasos agentic:** 20
- **Subagentes:** ninguno
- **MCP:** desactivado; llamadas MCP: 0.

Objetivo: corregir exclusivamente el fallo C4 de aislamiento de
`tests/test_fetch_images_v2.py::TestSourceIsolation::test_no_v1_runtime_imports`,
ejecutar la suite completa y establecer la baseline limpia. No se ejecuta el E2E
real de Slice 6B y no se cierra el change.

## 2. Estado Git heredado

- Rama `main`; HEAD `3866cc6a547545cad70cc1c5fbbacb08ef216713` (sin cambios).
- Últimos commits: `3866cc6` (record Slice 5B closure), `1d9fe37` (align Slice 5B).
- Staging 0; `git diff --check` limpio (solo warning no bloqueante de
  `data/postgres/`).
- Working tree heredado:

  ```
  M  tests/test_run_job.py
  M  tests/test_timing_regression.py
  M  openspec/changes/retire-legacy-visual-v1/tasks.md
  M  docs/project/current-state.md
  ?? docs/sessions/20260801-000000-retire-legacy-visual-v1-slice-6a-baseline.md
  ```

## 3. Reproducción mínima

- `test_no_v1_runtime_imports` aislado: `1 passed`.
- Orden contaminante (`test_no_v1_runtime_imports` → `test_script_stage_extracts_job_id`):
  `1 failed, 1 passed` antes de la corrección (fallo `FileNotFoundError` en
  `load_metadata`, `run_job.py:190`).
- Orden inverso (`test_script_stage_extracts_job_id` → `test_no_v1_runtime_imports`):
  `2 passed`.

## 4. Causa raíz C4

El test eliminaba permanentemente de `sys.modules` los módulos `fetch_images`,
`asset_validation`, `editorial_asset_contract`, `generate_script`, `prepare_job`,
`render_job` y `run_job` con `sys.modules.pop(mod, None)`, y el
`monkeypatch.setattr(sys, "modules", sys.modules)` que lo seguía era un no-op: no
registraba ni restauraba ninguna entrada. `test_run_job.py` importa `run_job` al
cargar el módulo, pero como pytest ordena `fetch_images_v2` antes que `run_job`,
tras la eliminación sus `patch("run_job.*")` reimportaban un módulo `run_job`
nuevo, distinto del objeto que el `main()` ya importado por `test_run_job.py`
referencia. Los parches se aplicaban a un objeto diferente y los tests de
`test_run_job.py` fallaban.

Clasificación: **C4 — test incorrecto o demasiado acoplado por mutación global no
restaurada**.

## 5. Corrección aplicada

En `tests/test_fetch_images_v2.py::TestSourceIsolation::test_no_v1_runtime_imports`:

- Se capturó el estado original de cada módulo con
  `v1_original_modules = {mod: sys.modules.get(mod) for mod in v1_modules}`.
  No se utilizó sentinel: `sys.modules.get()` confluye ausencia y valor `None`.
  En los estados observados de esta suite no había entradas con valor `None`;
  `monkeypatch.context()` restauró correctamente las entradas originales y la
  comprobación de identidad fue suficiente para los estados reales reproducidos.
- Las eliminaciones de `sys.modules` se movieron a
  `with monkeypatch.context() as scoped:` usando
  `scoped.delitem(sys.modules, mod, raising=False)`, que registra el valor original
  y lo restaura al salir del bloque.
- Se conservó el cuerpo: `fetch_images_v2.main([str(metadata_path)])` seguido de
  las aserciones `assert mod not in sys.modules` para los módulos prohibidos.
- Se añadió verificación de identidad post-contexto.

## 6. Módulos afectados

- `tests/test_fetch_images_v2.py` — único archivo de código modificado en 6A3.
- No se modificó producción (`bin/**` intacto).
- No se modificó `tests/test_run_job.py` ni `tests/test_timing_regression.py`.
- Módulos globales cubiertos por la restauración, con su clasificación real:

  - **Legacy retirados:**
    - `fetch_images`
    - `asset_validation`
    - `editorial_asset_contract`

  - **Productivos vigentes bloqueados por el test para verificar aislamiento:**
    - `generate_script`
    - `prepare_job`
    - `render_job`
    - `run_job`

  El propósito del test (comprobar que `fetch_images_v2.main()` no reimporta los
  módulos prohibidos) sigue siendo válido. La variable `v1_modules` tiene
  nomenclatura imprecisa y no implica que los siete módulos sean legacy; no se
  renombra durante esta corrección documental. La imprecisión no afecta a la
  baseline.

## 7. Verificación de identidad/restauración

Post-contexto, para cada módulo de `v1_modules`:

- si existía originalmente, `sys.modules[mod]` debe ser exactamente el mismo objeto
  (`is`); se comprueba con una aserción;
- si no existía, debe continuar ausente de `sys.modules`; también se comprueba.

## 8. Resultados en ambos órdenes

- Contaminante: `2 passed`.
- Inverso: `2 passed`.
- Prueba mínima de 4 tests (contaminante + `test_script_stage_extracts_job_id` +
  `test_non_zero_exit_fails_metadata` + `test_validate_exit0_sets_validated`): `4 passed`.

## 9. Resultados por archivos

- `test_fetch_images_v2.py` + `test_run_job.py`: `130 passed`.
- `test_run_job.py` + `test_fetch_images_v2.py` (orden invertido): `130 passed`.
- `test_run_job.py` + `test_timing_regression.py` + `test_semantic_asset_validation.py`:
  `103 passed`.

## 10. Focalizados V2

- Generación/runner V2: `107 passed`.
- Assets V2: `290 passed`.
- Dry-run E2E: `22 passed`.

## 11. Suite completa

- `--collect-only tests/`: `1102 tests collected`, cero errores de colección.
- `python3 -m pytest -q tests/ --tb=short`: `1102 passed in 11.47s`.

## 12. Baseline nueva

- **`1102 passed, 0 failed`** — baseline limpia establecida para el HEAD actual.
- `20 failed, 1082 passed` queda solo como resultado intermedio histórico de 6A2.
- `1215 passed, 16 failed` (Phase A) se conserva únicamente como referencia
  histórica, no como baseline vigente.

## 13. Estado pendiente de review

- Slice 6A pendiente de auditoría read-only (cambios sin stagear).
- Slice 6B no iniciado. Cero commit, cero push, cero MCP, cero reindexado.
- Cero staging; `git diff --check` limpio.

## 14. Cero red, Docker, providers y E2E real

No se invocó LLM, Edge TTS real, ElevenLabs, Pixabay, Wikimedia, Docker ni
FFmpeg real. No se ejecutó `bin/run_job.py`. No se contactó ningún servicio
externo. Cero E2E real.

---

# Auditoría read-only de Slice 6A

- **Sesión:** `retire-legacy-visual-v1-slice-6a-review`
- **Modo:** Plan/read-only
- **Modelo:** `opencode/deepseek-v4-flash-free`
- **Variante:** `default`
- **MCP:** desactivado; llamadas MCP: 0.

Verdict: `SLICE_6A_REVIEW_CHANGES_REQUIRED`.

- Suite confirmada: `1102 passed, 0 failed`.
- Cambios funcionales C2/C5/C4 validados (producción intacta).
- Causa del verdict: F4–F6 MEDIUM documentales.
- F1 y F2 LOW y F3 NOTE preservados como no bloqueantes (no corregidos en esta
  sesión).
- F7–F9 LOW corregidos junto con F4–F6.
- Reaprobación read-only focalizada pendiente.
- Slice 6B no iniciado.
- No se declara aprobación.

## Estado final

Correcciones documentales F4–F9 aplicadas.
Slice 6A pendiente de reaprobación read-only focalizada.
Baseline funcional vigente: `1102 passed, 0 failed`.
Slice 6B no iniciado.

No se declara commit, cierre ni reaprobación.

---

# Reaprobación read-only focalizada de Slice 6A

- **Sesión:** `retire-legacy-visual-v1-slice-6a-reapproval`
- **Modelo:** `opencode/deepseek-v4-flash-free`
- **Variante:** `default`
- **Modo:** Plan/read-only
- **MCP:** desactivado; llamadas MCP: 0.

Verdict: `SLICE_6A_REAPPROVED_FOR_COMMIT`.

- Correcciones documentales F4–F9 confirmadas como resueltas.
- F1/F2 LOW y F3 NOTE aceptados como no bloqueantes (no corregidos).
- Baseline funcional vigente: `1102 passed, 0 failed`.
- Los tres tests (`test_run_job.py`, `test_timing_regression.py`,
  `test_fetch_images_v2.py`) no cambiaron durante las correcciones documentales
  ni durante esta reaprobación.
- Cero pytest ejecutados durante la reaprobación (read-only).
- Slice 6B no iniciado.
- Commit de Slice 6A pendiente.
- No se declara cierre todavía.

---

# Cierre y commit de Slice 6A

- **Sesión:** `retire-legacy-visual-v1-slice-6a-closure`
- **Modelo:** `opencode/deepseek-v4-flash-free`
- **Variante:** `default`
- **Modo:** Build
- **MCP:** desactivado; llamadas MCP: 0.

Commit A — `SLICE_6A_COMMIT`:

- Hash completo: `86170d3f6edefbfb6b6e115d61ecca5922de43bf`
- Hash corto: `86170d3`
- Subject: `test(v2): establish clean Slice 6A baseline`
- Staging selectivo de los seis archivos de Slice 6A:
  - `tests/test_run_job.py`
  - `tests/test_timing_regression.py`
  - `tests/test_fetch_images_v2.py`
  - `docs/project/current-state.md`
  - `openspec/changes/retire-legacy-visual-v1/tasks.md`
  - `docs/sessions/20260801-000000-retire-legacy-visual-v1-slice-6a-baseline.md`
- Baseline funcional: `1102 passed, 0 failed`.
- Slice 6A cerrado.
- Slice 6B no iniciado.
- Change completo `retire-legacy-visual-v1` todavía abierto.
- Cero push, cero MCP, cero reindexado, cero red, cero providers, cero Docker,
  cero E2E real.
- Commit B pendiente exclusivamente para registrar el hash de Commit A.
