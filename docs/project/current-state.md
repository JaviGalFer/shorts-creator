# Estado actual del proyecto

**Última actualización:** 2026-07-22

## Estado global

Pipeline funcional de vídeos cortos verticales (9:16, ~1 min). Scripts en `bin/` operativos. n8n como orquestador legacy. Docker para render.

**Último change completado:** `integrate-native-visual-plan-v2-generation` (2026-07-14)

**Change pausado:** `improve-short-form-audio-pacing-v2` — Phase A completada, Phase B pendiente (se reanudará tras migrar dominio script)

**Change activo:** `retire-legacy-visual-v1` — Primera fase del plan de transformación modular. Slice 1 implementado, revisado y commiteado. Slice 2 implementado, revisado y cerrado mediante commit. Slice 3A implementado, revisado y cerrado mediante commit. Slice 3B1 implementado, revisado y cerrado mediante el commit de esta iteración.

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

### Slice 3B1 implementado pendiente de review y commit (2026-07-22)

- `generate_script.py`: cuatro símbolos V1 de prompts eliminados (`SYSTEM_PROMPT`, `_build_duration_prompt_instruction`, `_build_retry_instruction`, `_build_user_prompt`)
- `tests/test_generate_script.py`: 13 tests V1 eliminados; 35 tests pasan (validator, retry-loop V2, asset-side, segment-count)
- `tests/test_duration_profiles.py`: migrados a equivalentes V2 vía aliases locales; 36 tests pasan
- Fixture `_GOOD_3_SCENE_SCRIPT`, `PROMPT_PATH`, `import re` eliminados sin impacto
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

1. Slice 3B2 del change `retire-legacy-visual-v1`: eliminar `_validate_script_structure`, imports editoriales muertos y fixtures V1 restantes
2. Estabilizar baseline V2 tras eliminación de V1
3. Phase B de audio pacing (tras migrar script/)
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
