# Session: Implement retire V1 Slice 4B1 physical assets stack

**Date:** 2026-07-25
**Model:** opencode/deepseek-v4-flash-free
**Variant:** default
**Mode:** Build
**Category:** implementation
**Maximum agentic steps:** 7
**Subagents:** none

## Change OpenSpec activo

`retire-legacy-visual-v1` — Slice 4B1: retirada física del stack legacy de assets y migración de cobertura útil.

## Estado inicial

- **HEAD:** `b7aeb22` (refactor(assets): remove legacy runner branches)
- **Working tree:** limpio (único warning conocido: data/postgres/)
- **Cero staged, cero untracked**
- Slice 4A cerrado; Slice 4B1 pendiente; Slice 4B2 pendiente

## Codebase Memory MCP

- **Estado:** DESACTIVADO
- **Cero llamadas MCP**
- **Cero reindexados**
- Fuentes de verdad: código directo, AST, git grep, pytest, git diff

## Preflight imports

- `bin/fetch_images.py` importaba símbolos desde `editorial_asset_contract.py`; ambos forman el stack V1 retirado.
- `tests/test_semantic_asset_validation.py`: 31 imports desde `fetch_images`
- `tests/test_no_topic_specific_contamination.py`: 16 imports desde `fetch_images`
- `tests/test_generate_script.py`: 7 imports desde `fetch_images` y `editorial_asset_contract`
- Cero callers productivos inesperados fuera de `bin/fetch_images.py`

## Preflight AST

| Archivo | Conteo esperado | Conteo real |
|---------|----------------|-------------|
| test_semantic_asset_validation.py | 76 | 76 |
| test_no_topic_specific_contamination.py | 26 | 26 |
| test_generate_script.py | 10 | 10 |
| test_generate_script_v2.py | 77 | 77 |
| test_duration_profiles.py | 36 | 36 |
| test_v2_only_generation_contract.py | 7 | 7 |
| test_run_job.py (5 clases focalizadas) | 48 | 48 |
| test_run_job_v2_assets.py | 20 | 20 |
| test_fetch_images_v2.py | 39 | 39 |
| test_asset_validation_v2_neutral_metadata.py | 28 | 28 |
| test_visual_v2_dry_run_e2e.py | 22 | 22 |
| **Total focalizado preflight** | **389** | **389** |

## 15 tests preservados (baseline pre-eliminación)

- 8 tests semánticos: 8 passed, 0 failed
- 4 tests de neutralidad: 4 passed, 0 failed
- 3 tests de retry: 3 passed, 0 failed

## Módulos productivos eliminados

- `bin/fetch_images.py` — eliminado vía `git rm` (DELETE, no movido a tools/)
- `bin/editorial_asset_contract.py` — eliminado vía `git rm` (DELETE)
- **Motivo:** cero callers productivos canónicos, stack V2 independiente, mantenerlos aumentaría deuda

## Tests eliminados

| Archivo | Antes | Después | Eliminados |
|---------|-------|---------|------------|
| test_semantic_asset_validation.py | 76 | 8 | 68 |
| test_no_topic_specific_contamination.py | 26 | 4 | 22 |
| test_generate_script.py | 10 | 3 | 7 |
| **Total legacy eliminados** | **112** | **15** | **97** |

## Ocho tests semánticos conservados

1. `test_render_timeline_coverage_fills_scene_gaps`
2. `test_clone_job_strips_derived_artifacts`
3. `test_clone_job_applies_scene_patch`
4. `test_prepare_job_regenerates_paths_under_current_job_dir`
5. `test_render_preflight_rejects_cross_job_paths`
6. `test_render_timeline_per_scene_sequential_continuity`
7. `test_border_closure_construction_without_evidence_fails_asset_validation`
8. `test_reuse_civilian_impact_for_distinct_event_1989_fails_asset_validation`

## Cuatro tests de neutralidad conservados

1. `test_no_prohibited_terms_in_bin_asset_validation_source`
2. `test_theme_constraints_empty`
3. `test_legacy_keywords_no_topic_specific`
4. `test_modern_query_keywords_no_topic_specific`

## Tres tests de retry conservados

1. `test_max_script_attempts_is_three`
2. `test_main_retry_loop_3_attempts_3rd_succeeds`
3. `test_main_retry_loop_3_attempts_all_fail_review_required`

## Corrección de asset_validation.py

- Comentario stale actualizado: `the shared editorial_asset_contract allow-lists which are topic-agnostic` → `the allow-lists below, which are topic-agnostic`
- Funciones, constantes y comportamiento no modificados

## Corrección de README

- `python bin/fetch_images.py` → `python bin/fetch_images_v2.py`
- Sin flags adicionales, sin limpieza general

## Corrección del runbook n8n

- Comando legacy `python3 bin/fetch_images.py data/videos/{jobId}/metadata.json --provider pollinations` → `python3 bin/fetch_images_v2.py data/videos/{jobId}/metadata.json`
- Flag `--provider pollinations` eliminado (incompatible con fetch_images_v2.py)
- Tabla de scripts actualizada: `bin/fetch_images_v2.py` con descripción neutral

## Postcondición de imports

- `git grep` por `from fetch_images import`, `import fetch_images`, `from editorial_asset_contract import`, `import editorial_asset_contract`: **cero resultados** en bin/ y tests/ (las coincidencias en test_fetch_images_v2.py son `import fetch_images_v2`, que es el módulo V2)
- `test ! -e bin/fetch_images.py`: PASS
- `test ! -e bin/editorial_asset_contract.py`: PASS
- `importlib.util.find_spec("fetch_images") is None`: PASS
- `importlib.util.find_spec("editorial_asset_contract") is None`: PASS
- Cero comandos operativos hacia `bin/fetch_images.py` en README.md o runbook

## Conteos AST finales

| Archivo | Conteo |
|---------|--------|
| test_semantic_asset_validation.py | 8 |
| test_no_topic_specific_contamination.py | 4 |
| test_generate_script.py | 3 |
| test_generate_script_v2.py | 77 |
| test_duration_profiles.py | 36 |
| test_v2_only_generation_contract.py | 7 |
| test_run_job.py (5 clases focalizadas) | 48 |
| test_run_job_v2_assets.py | 20 |
| test_fetch_images_v2.py | 39 |
| test_asset_validation_v2_neutral_metadata.py | 28 |
| test_visual_v2_dry_run_e2e.py | 22 |
| **Total focalizado** | **292** |

## Resultados tests focalizados (292 passed, 0 failed)

| Comando | Resultado |
|---------|-----------|
| test_semantic_asset_validation.py | 8 passed |
| test_no_topic_specific_contamination.py | 4 passed |
| test_generate_script.py | 3 passed |
| test_generate_script_v2.py | 77 passed |
| test_duration_profiles.py | 36 passed |
| test_v2_only_generation_contract.py | 7 passed |
| test_run_job (5 clases focalizadas) | 48 passed |
| test_run_job_v2_assets.py | 20 passed |
| test_fetch_images_v2.py | 39 passed |
| test_asset_validation_v2_neutral_metadata.py | 28 passed |
| test_visual_v2_dry_run_e2e.py | 22 passed |

## Git diff

```
README.md                                         |    2 +-
bin/asset_validation.py                           |    2 +-
docs/project/current-state.md                     |   20 +-
docs/runbooks/n8n-operations.md                   |    4 +-
openspec/changes/retire-legacy-visual-v1/tasks.md |   24 +-
tests/test_generate_script.py                     |   77 +-
tests/test_no_topic_specific_contamination.py     |  708 +-----
tests/test_semantic_asset_validation.py           | 2648 +--------------------
```

Staged (vía `git rm`):
```
bin/editorial_asset_contract.py |  192 ---
bin/fetch_images.py             | 2748 ---
```

## Archivos no modificados

- .env.example
- docker-compose.yml / docker-compose.yaml
- bin/run_job.py
- bin/fetch_images_v2.py
- bin/visual_provider_config_v2.py
- tests/test_generate_script_v2.py
- tests/test_run_job.py
- tests/test_run_job_v2_assets.py
- tests/test_fetch_images_v2.py
- tests/test_asset_validation_v2_neutral_metadata.py
- tests/test_visual_v2_dry_run_e2e.py
- HANDOVER.md
- docs/project/architecture.md
- docs/project/environment.md
- docs/sessions/20260725-163459-retire-legacy-visual-v1-slice-4a.md
- src/
- pyproject.toml

## Riesgos y dudas

- `test_fetch_images_v2.py` continúa importando `fetch_images_v2` (módulo V2), sin relación con los módulos eliminados.
- Configuración Pexels intacta (pertenece a Slice 4B2).
- `fetch_images.py` eliminado mediante `git rm` (staged), el resto de cambios en working tree sin staged.

## Confirmación

- **Dos eliminaciones staged mediante `git rm`:**
  - `bin/fetch_images.py`
  - `bin/editorial_asset_contract.py`
- **Ocho modificaciones tracked permanecen unstaged.**
- **El session log permanece untracked.**
- **Ningún staging adicional.**
- **Ningún commit.**
- **Cero push**
- **Cero llamadas MCP**
- **Cero reindexados**
- **Slice 4B2 no iniciado**

## Corrección posterior a review

- La primera review confirmó código, imports, AST y 292 tests focalizados.
- Se detectó un finding bloqueante documental en el runbook primario.
- El runbook mostraba assets V2 bajo scenes/ y ordenaba audio antes que assets.
- Se corrigió el orden a script → assets → audio → prepare → render.
- Se corrigió la estructura para documentar assets/ como directorio visual canónico.
- El CLI de fetch_images_v2.py fue validado mediante --help.
- tasks.md fue actualizado para indicar que solo Slice 4B2 permanece pendiente dentro de Slice 4.
- Typos y descripción del staging corregidos.
- Ningún código productivo modificado.
- Ningún test modificado.
- Cero llamadas MCP.
- Cero reindexados.
- Ningún commit.
- Ningún push.
- Se detectó una segunda incoherencia documental: el runbook invocaba `generate_script.py` con `metadata.json` como argumento posicional.
- El CLI real fue verificado mediante `python3 bin/generate_script.py --help`.
- El comando fue sustituido por la sintaxis real basada en `--topic` y `--output`.
- No se ejecutó LLM real.
- No se modificó código productivo.
- No se modificaron tests.
- Ningún staging adicional.
- Cero llamadas MCP.
- Cero reindexados.

## Siguiente acción única

**Review read-only final de Slice 4B1.**

## Review final y cierre

- Verdict final: `APPROVE_WITH_NON_BLOCKING_NOTES`.
- Cero findings bloqueantes.
- Review confirmó la eliminación física de:

  - `bin/fetch_images.py`;
  - `bin/editorial_asset_contract.py`.
- Review confirmó cero imports y callers productivos residuales.
- Review confirmó que `fetch_images_v2.py` permanece disponible.
- Review confirmó que `run_job.py` sigue usando `fetch_images_v2.py`.
- Review confirmó que clasificación y rechazo V1/mixed/invalid permanecen.
- Review confirmó que `asset_validation.py` solo recibió un cambio de comentario.
- Review confirmó los inventarios:

  - `test_semantic_asset_validation.py`: 76 → 8;
  - `test_no_topic_specific_contamination.py`: 26 → 4;
  - `test_generate_script.py`: 10 → 3.
- Review confirmó:

  - 97 tests legacy eliminados;
  - 15 tests neutrales conservados;
  - 292 passed, 0 failed.
- Review confirmó CLI válido de `generate_script.py`.
- Review confirmó CLI válido de `fetch_images_v2.py`.
- Review confirmó el orden canónico del runbook.
- Review confirmó `assets/` como directorio visual canónico.
- Configuración Pexels intacta para Slice 4B2.
- Commit previsto:
  `refactor(assets): remove legacy V1 asset stack`
- Ningún push.
- Próxima acción:
  Slice 4B2 — limpieza de configuración residual.
