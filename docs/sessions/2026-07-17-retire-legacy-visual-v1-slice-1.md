# Sesión: Implement retire V1 Slice 1

- **Fecha:** 2026-07-17
- **Modelo:** opencode/deepseek-v4-flash-free
- **Variante:** low
- **Modo:** Build
- **Categoría:** implementation
- **Cambio activo:** retire-legacy-visual-v1
- **HEAD:** ab1549d

## Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `bin/generate_script.py` | `--visual-schema-version` default: 1 → 2; choices [1,2] conservados; V1 explícito sin reinterpretación |
| `bin/run_job.py` | `build_script_command()` adds `--visual-schema-version 2` unconditionally |
| `tests/test_v2_only_generation_contract.py` | **NUEVO** — 7 tests covering default V2, explicit V1 not reinterpreted, build_script_command V2 flag, args preservation |
| `openspec/changes/retire-legacy-visual-v1/tasks.md` | Slice 1 tasks marked [x] |
| `docs/project/current-state.md` | Updated: Slice 1 committed, review done, Slice 2 next |

## Comportamiento anterior

- `generate_script.py` default era `--visual-schema-version 1` → usaba SYSTEM_PROMPT V1
- `run_job.py` construía comando sin `--visual-schema-version` → heredaba default V1

## Comportamiento nuevo

- `generate_script.py` default es `--visual-schema-version 2` → usa SYSTEM_PROMPT_V2
- `generate_script.py` recibe `--visual-schema-version 1` → usa V1 sin reinterpretación (comportamiento preexistente)
- `run_job.py` siempre añade `--visual-schema-version 2` al comando de generación

## Tests (Slice 1 — contrato de generación V2)

- 7 tests nuevos en `tests/test_v2_only_generation_contract.py`: 7 PASS
- 4 tests existentes `test_generate_script_v2.py::TestCliAndRequest`: 4 PASS
- 2 tests existentes `test_run_job.py::test_build_script_command_*`: 2 PASS
- **Total: 13 passed, 0 failed**
- Sin llamadas reales al LLM (mocked api_key + dry-run)

## Alcance no tocado

- `build_stage_command()` no modificado
- No se implementó rechazo de metadata V1
- No aparece `UNSUPPORTED_LEGACY_SCHEMA`
- No se modificó `fetch_images.py` ni `fetch_images_v2.py`
- No se eliminaron prompts o helpers V1
- No se modificó audio, pacing, render o validation
- No se creó `src/`
- `data/cache/` intacto
- No hubo commit ni push

## Review

Review read-only aprobado: `APPROVE_WITH_NON_BLOCKING_NOTES`.

El único finding fue la descripción stale que mencionaba `deprecation warning` en la cobertura de tests. Corregido en esta sesión de cierre. No hubo findings funcionales bloqueantes.

## Siguiente paso

Slice 2: V2-only asset runtime.
