# Tareas: stabilize-visual-v2-runtime-contracts

## Phase A — Asset identity and renderability contract

- [x] Crear `bin/visual_asset_renderability_v2.py` (contrato canónico v2)
- [x] Crear `tests/test_visual_asset_renderability_v2.py`
- [x] Modificar `bin/visual_asset_executor_v2.py` — añadir `asset_namespace` con validación
- [x] Modificar `bin/fetch_images_v2.py` — propagar sceneNumber como namespace
- [x] Modificar `bin/visual_provider_wikimedia_v2.py` — usar contrato v2, defaults 720
- [x] Modificar `bin/asset_validation.py` — dimensiones v2 vs v1
- [x] Actualizar `tests/test_visual_asset_executor_v2.py` — tests de namespace
- [x] Actualizar `tests/test_fetch_images_v2.py` — tests de sceneNumber + namespace
- [x] Actualizar `tests/test_visual_provider_wikimedia_v2.py` — tests de dimensiones v2
- [x] Actualizar `tests/test_asset_validation_v2_neutral_metadata.py` — tests de dimensiones
- [x] Crear session document (Build A)
- [x] Ejecutar suite completa y verificar baseline (874/16)

### Correcciones Phase A (post-review)

- [x] Bridge: asociación explícita por `(sceneNumber, segmentIndex)` vía `_get_explicit_slot`
- [x] Bridge: fallback FIFO `_claim_segment` solo para resultados sin sceneNumber
- [x] fetch_images_v2: `_tag_results_with_scene_number` añade sceneNumber a todos los resultados
- [x] fetch_images_v2: validación de sceneNumber único antes de ejecutar
- [x] `_make_synthetic_unresolved` acepta `scene_number` opcional
- [x] Wikimedia: importa `MIN_V2_ASSET_WIDTH`, `MIN_V2_ASSET_HEIGHT` de `visual_asset_renderability_v2`
- [x] renderability_v2: NaN/Infinity → False sin excepción (usa `math.isfinite`)
- [x] Tests: bridge explicit sceneNumber matching (7 tests)
- [x] Tests: bridge invalid sceneNumber (5 tests)
- [x] Tests: bridge compatibility without sceneNumber (2 tests)
- [x] Tests: fetch_images duplicate sceneNumber detection
- [x] Tests: fetch_images sceneNumber in results
- [x] Tests: wikimedia canonical constants import (4 tests)
- [x] Tests: renderability NaN/Infinity/bool/list/dict/negative/zero (10 tests)
- [x] Ejecutar suite completa: 899 passed, 16 failed (mismos preexistentes)

## Phase B — Per-scene audio, subtitle and duration contract

- [x] Diseñar contrato de duración por escena
- [x] Diseñar contrato de padding de audio
- [x] Diseñar contrato de offsets de subtítulos
- [x] Diseñar preflight agregado
- [x] Implementar `_get_mp3_duration()` y `durationSec` en `generate_audio.py` per-scene
- [x] Implementar `resolve_scene_window_duration()` en `prepare_job.py`
- [x] Modificar `build_render_timeline()` para usar sceneWindowSec
- [x] Modificar `generate_ass_from_cues()` para aceptar `scene_offsets`
- [x] Reordenar `main()` en `prepare_job.py` para derivar offsets del timeline
- [x] Modificar cadena FFmpeg per-scene en `render_job.py` (apad + atrim con sceneWindow)
- [x] Modificar `preflight_validate()` para validación agregada por escena
- [x] Fix `expected_duration` desde timeline
- [x] Crear `tests/test_prepare_job_scene_temporal_contract.py` (22 tests)
- [x] Crear `tests/test_render_job_scene_audio_contract.py` (26 tests)
- [x] Crear `specs/per-scene-temporal-contract.md`
- [x] Ejecutar suite completa: 947 passed, 16 failed (sin regresiones)
- [x] E2E live (Build B): job e2e-pixabay-20260714-184248 — ver Build D

### Correcciones Phase B (post-review)

- [x] prepare_job preserva `audio.scenes[].durationSec` (no reemplaza todo data["audio"])
- [x] generate_audio: probe fallido → REVIEW_REQUIRED (no AUDIO_READY con 0.0)
- [x] generate_audio: voice persistida en metadata per-scene
- [x] Validación estricta de scene_audio_durations en prepare_job
- [x] durationFraction normalizada (suma = 1.0, último segmento cierra ventana)
- [x] Preflight detecta overlaps (no solo gaps)
- [x] Preflight resuelve audioPath desde entries (no solo hardcodeado)
- [x] Preflight tests mockean `_docker_ffprobe_duration` vía `__globals__`
- [x] resolve_and_validate_global_cues() con validación temporal
- [x] build_per_scene_audio_filter() helper puro
- [x] resolve_expected_duration() helper puro
- [x] render.durationSeconds con round a 3 decimales (no int)
- [x] Crear `tests/test_generate_audio_scene_duration_contract.py` (14 tests)
- [x] Extender `tests/test_prepare_job_scene_temporal_contract.py` (+18 tests)
- [x] Extender `tests/test_render_job_scene_audio_contract.py` (+5 tests)
- [x] Ejecutar suite completa: 980 passed, 16 failed (sin regresiones nuevas)

### Correcciones finales Phase B

- [x] main_per_scene siempre persiste metadata (no return temprano)
- [x] main_per_scene tests asíncronos con mocks (4 tests: success, probe fail, preexisting, generation fail)
- [x] resolve_expected_duration conectado al runtime de render_job.main()
- [x] Validación estricta de build_per_scene_audio_filter y resolve_expected_duration
- [x] generate_ass_from_cues escribe desde la lista global validada (single source)
- [x] resolve_and_validate_global_cues no reordena cues (rechaza orden no monotónico)
- [x] Preflight recibe expected_total desde resolve_expected_duration (no None)
- [x] Manifest usa resolve_manifest_scene_audio_duration (no 0.0 hardcodeado)
- [x] Tests de expanded scenes preflight (3 tests)
- [x] Tests de manifest scene audio duration (7 tests)
- [x] Ejecutar suite completa: 994 passed, 16 failed (sin regresiones nuevas)
- [x] E2E live (Build B): job e2e-pixabay-20260714-184248 — ver Build D

## Build C — Docker API, Wikimedia pool/batch, rate-limit diagnostics

- [x] Eliminar pin obsoleto `DOCKER_API_VERSION = "1.43"` de `bin/generate_audio.py` (2 sitios), `bin/render_job.py`, `bin/validate_job.py`, `scripts/render_job.py`, `Makefile`, `docker-compose.yml`
- [x] Docker CLI negocia automáticamente la versión; no se fuerza versión
- [x] `_get_mp3_duration()` sin inyección manual de variable de entorno
- [x] Pool/batch de candidatos Wikimedia: imageinfo agrupado en una sola petición por batch
- [x] Exclusión de URLs por `sourceUrl` y `fileUrl` entre segmentos
- [x] Query cache para evitar repetir HTTP en mismas queries
- [x] Parámetros opcionales backward-compatibles (`excluded_source_urls`, `excluded_file_urls`, `cache`)
- [x] Propagación de exclusiones entre escenas: `fetch_images_v2` mantiene sets acumulados
- [x] `WikimediaRateLimitedError` para diagnóstico de 429
- [x] Executor propaga `PROVIDER_ERROR / RATE_LIMITED` cuando 429 agotado
- [x] `NO_RESULTS` exclusivamente cuando la respuesta fue válida pero ningún candidato pasó filtros
- [x] `Retry-After` respetado con espera acotada (máx. 10s)
- [x] Tests: 2 segmentos misma query → distintas URLs
- [x] Tests: candidato excluido → siguiente usado
- [x] Tests: agotados en q1 → continúa q2
- [x] Tests: exclusiones acumuladas entre escenas
- [x] Tests: cache reutilizado sin repetir HTTP
- [x] Tests: 429 agotado → PROVIDER_ERROR / RATE_LIMITED
- [x] Tests: respuesta válida sin candidatos → NO_RESULTS
- [x] Tests: Docker probe sin DOCKER_API_VERSION
- [x] Tests: Dry-run sin cambios (pre-existente)
- [x] Tests: escenas paths únicos (pre-existente)
- [x] Ejecutar suite completa: 1008 passed, 16 failed (mismos preexistentes, sin regresiones)
- [x] E2E live (Build C): job e2e-buildc-20260711-232623

## Bugs corregidos

| # | Origen | Bug | Fix |
|---|--------|-----|-----|
| 1 | E2E v2 rainbow | Colisiones de filenames entre escenas | asset_namespace con sceneNumber |
| 2 | E2E v2 rainbow | Wikimedia acepta 700x435, asset_validation lo bloquea | Contrato canónico v2 720x720 |
| 3 | Review Phase A | Bridge asigna resultados por FIFO sin sceneNumber, invirtiendo escenas | `_get_explicit_slot` con clave `(sceneNumber, segmentIndex)` |
| 4 | Review Phase A | sceneNumber duplicados no detectados | Validación de unicidad en main() |
| 5 | Review Phase A | NaN/Infinity causan excepción en renderability | `math.isfinite()` |
| 6 | Review Phase A | Wikimedia duplica literales 720 | Importa constantes canónicas |
| 7 | Post-review Phase B | prepare_job destruye durationSec al reemplazar data["audio"] | Preservar audio_config, solo actualizar path/exists |
| 8 | Post-review Phase B | Probe ffprobe fallido persiste 0.0 y AUDIO_READY | REVIEW_REQUIRED + None en durationSec |
| 9 | Post-review Phase B | durationFraction sin normalizar, gaps entre segmentos | Normalización a suma=1, último segmento cierra ventana |
| 10 | Post-review Phase B | Preflight solo detecta gaps, no overlaps | Delta negativo → overlap error |
| 11 | Post-review Phase B | Cues sin validación temporal global | resolve_and_validate_global_cues() |
| 12 | Post-review Phase B | Tests de preflight no mockean ffprobe | monkeypatch via __globals__ |
| 13 | Build C - E2E rainbow | Docker API 1.43 obsoleto (daemon requiere 1.44) | Eliminar pin, negociación automática |
| 14 | Build C - E2E rainbow | Wikimedia N+1 HTTP por query | Batch imageinfo en una sola petición |
| 15 | Build C - E2E rainbow | Candidatos repetidos entre segmentos | Pool de exclusión con sourceUrl/fileUrl acumulados |
| 16 | Build C - E2E rainbow | 429 retornado como NO_RESULTS | WikimediaRateLimitedError → PROVIDER_ERROR/RATE_LIMITED |

## Resultados de tests

**Baseline antes de Build A:** 820 passed, 16 failed
**Tras Build A:** 874 passed, 16 failed
**Tras correcciones Phase A:** 899 passed, 16 failed (mismos 16 preexistentes)
**Tras Phase B:** 947 passed, 16 failed (mismos 16 preexistentes, sin regresiones)
**Tras correcciones Phase B:** 980 passed, 16 failed (mismos 16 preexistentes, sin regresiones nuevas)
**Tras correcciones finales:** 994 passed, 16 failed (mismos 16 preexistentes)
**Tras Build C:** 1008 passed, 16 failed (mismos 16 preexistentes, sin regresiones)
**Tras Build D:** 1132 passed, 16 failed (mismos 16 preexistentes, sin regresiones)

Fallos preexistentes:
- 15 en `tests/test_run_job.py`
- 1 en `tests/test_semantic_asset_validation.py`

Nuevos tests:
- Phase B inicial: 48
- Correcciones Phase B: 37
- Correcciones finales: 10
- Build C: 14
- Build D (Pixabay + duration + subtitle validation): 69
- Total nuevos: 178 tests

## Resultado E2E Build C

**Job:** `e2e-buildc-20260711-232623`
**Tema:** arcoíris, 3 escenas, 5 segmentos, Wikimedia único

| Etapa | Resultado |
|-------|-----------|
| generate_audio | AUDIO_READY — 3/3 escenas, durationSec: 6.576 / 6.936 / 7.536 |
| fetch_images_v2 | ASSETS_PARTIAL — 4/5 resueltos (1 download failed) |
| prepare_job | ASSET_UNRESOLVED — bloqueado por segmento no resuelto |
| render_job | No alcanzado |

**Clasificación:** `E2E_REVIEW_REQUIRED`

**Causa del fallo:** El segmento `scene_003_seg_002` (diagram) encontró un candidato en Wikimedia pero la descarga falló. No fue 429 ni error de búsqueda — fue un fallo de red en la descarga HTTP.

**URLs distintas:** 4 URLs únicas entre 4 assets resueltos — la exclusión funciona.
**durationSec:** Obtenido automáticamente sin inyección manual — el pin Docker eliminado funciona.
**Cache:** Las queries repetidas entre segmentos reutilizaron el cache sin HTTP extra.
**Pipeline:** Funcional hasta fetch_images; la fiabilidad Wikimedia-only es insuficiente (80%).

**Siguiente acción:** Añadir un segundo provider (e.g. Pexels, Pixabay o FreeAI) como decisión arquitectónica para alcanzar 100% de cobertura de assets.

## Build D — Pixabay provider, duration contract, per-scene subtitle validation

- [x] Implementar Pixabay v2 provider (`bin/visual_provider_pixabay_v2.py`, 57 tests)
- [x] Failover multiproveedor en executor (`provider_credentials` + try/except)
- [x] Pixabay como P2 débil en diagram (router)
- [x] Fix `_check_durations()` en `validate_job.py`: distinguir scene.targetDurationSec de segment durationSec
- [x] Alinear `MAX_SEGMENT_DURATION=20.0` entre `validate_job.py` y `render_job.py`
- [x] Derivar total duration canonical desde `max(renderTimeline.endSec)`
- [x] Módulo compartido `bin/subtitle_validation_context.py` (29 tests)
- [x] Branching per-scene vs legacy en `validate_job.py._check_subtitle_cues()`
- [x] Branching en `render_job.py` para coverage validation per-scene
- [x] Cues globales derivados de offsets del renderTimeline + cues locales
- [x] Validación ASS real (parse `Dialogue:` → comparar tiempos y texto normalizado)
- [x] Quality gate PASS para per-scene subtitle validation
- [x] Ejecutar suite completa: 1132 passed, 16 failed (mismos preexistentes, sin regresiones)
- [x] E2E live (Build D): job e2e-pixabay-20260714-184248 — ASSETS_READY 5/5, render 30.0s, validate_job PASS, 0 errors

### Resultado E2E Build D

**Job:** `e2e-pixabay-20260714-184248`
**Tema:** arcoíris, 3 escenas, 5 segmentos, Wikimedia + Pixabay multiproveedor

| Etapa | Resultado |
|-------|-----------|
| generate_audio | AUDIO_READY — 3/3 escenas, durationSec reales |
| fetch_images_v2 | ASSETS_READY — 5/5 resueltos |
| prepare_job | OK — 5 timeline segments |
| render_job | RENDERED — 30.0s, 1080x1920, audio presente |
| validate_job | PASS — 0 errors, subtitleCoverageValidation PASS, assetValidation PASS, technicalValidation PASS, qualityGate PASS |

**Clasificación:** `E2E_PASS`

**Providers por segmento:**
| Scene | Seg | Preference | Provider |
|-------|-----|-----------|----------|
| 1 | 1 | photograph | pixabay |
| 2 | 1 | diagram | wikimedia_commons |
| 2 | 2 | illustration | pixabay |
| 3 | 1 | photograph | pixabay |
| 3 | 2 | diagram | pixabay |

**Video:** `data/videos/e2e-pixabay-20260714-184248/video.mp4` (1.7MB, 30.0s, sha256 sin cambios durante correcciones)

### Bugs corregidos en Build D

| # | Origen | Bug | Fix |
|---|--------|-----|-----|
| 17 | E2E Build C | Cobertura Wikimedia-only insuficiente (80%) | Pixabay como P2 con failover automático |
| 18 | E2E Build C | MAX_SEGMENT_DURATION=8.0 falsea errores en escenas expandidas | Alinear a 20.0, distinguir target vs segment |
| 19 | E2E Build C | validate_job falsea overlaps en cues locales concatenados | subtitle_validation_context.py con offsets del timeline |
| 20 | E2E Build C | render_job coverage 0% con sceneTimings vacíos | Branching per-scene en coverage validation |

### Resultados finales de tests

**Baseline final:** 1132 passed, 16 failed (preexistentes en test_run_job.py y test_semantic_asset_validation.py), 0 regresiones

Nuevos tests acumulados:
- Build A + Phase A corrections: 79
- Phase B + corrections: 90
- Build C: 14
- Build D (Pixabay + duration + subtitle validation): 69
- **Total nuevos: 252 tests**

### Contratos estabilizados

1. Wikimedia + Pixabay multiproveedor operativo con failover real
2. Identidad de assets por `(sceneNumber, segmentIndex)` — key compuesta, sin inferencia posicional
3. Contrato de renderabilidad v2: `width >= 720 AND height >= 720` con `math.isfinite()`
4. Duración real de audio por escena (`audio.scenes[].durationSec`) desde ffprobe
5. `sceneWindowSec = max(targetDurationSec, actualAudioDurationSec)`
6. Padding de audio: `aresample → asetpts → apad → atrim=duration=sceneWindowSec`
7. Timeline multi-segmento distribuido sobre `sceneWindowSec`
8. Subtítulos per-scene con offsets globales desde `renderTimeline`
9. Validación ASS real (parse `Dialogue:`, comparar tiempos y texto normalizado)
10. Validación de duración por cuatro niveles: segment, scene, timeline, total

### Trabajos futuros separados

- Generación nativa de VisualPlan v2 desde `generate_script.py`
- Calidad y relevancia semántica de assets
- Mejora de voz (Edge TTS AlvaroNeural)
- Integración del pipeline v2 con n8n
