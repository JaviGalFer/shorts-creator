# Session: retire-legacy-visual-v1 — Slice 3A

**Fecha:** 2026-07-22
**Change:** `retire-legacy-visual-v1`
**Slice:** 3A — Disable V1 generation runtime
**Modelo:** opencode/deepseek-v4-flash-free
**Variante:** low
**Modo:** Build
**Categoría:** implementation

## Contrato CLI

- `--visual-schema-version` choices restringido de `[1, 2]` a `[2]`
- `--visual-schema-version 1` produce `SystemExit(2)` vía argparse (error estándar `invalid choice`)
- `--visual-schema-version 2` funciona normalmente (equivalente a omitir el flag)
- Default sigue siendo `2`

## Adaptación de call_llm

- `system_prompt` default cambiado de `SYSTEM_PROMPT` a `SYSTEM_PROMPT_V2`
- Todos los callers productivos de main() pasan explícitamente `system_prompt=SYSTEM_PROMPT_V2`
- `SYSTEM_PROMPT` permanece como constante muerta (pendiente Slice 3B)

## Ramas productivas V1 retiradas de main()

Las siguientes bifurcaciones `visual_schema_version == 2` fueron eliminadas (se mantuvo solo el camino V2):

1. Selección de prompt: `active_system_prompt` siempre es `SYSTEM_PROMPT_V2`; `base_prompt` siempre usa `_build_user_prompt_v2`
2. Dry-run: imprime siempre `active_system_prompt` (sin fallback a `SYSTEM_PROMPT`)
3. Retry loop: validación V2 directa sin condicional; retry instruction V2; user prompt V2
4. LLM call: `call_llm` siempre con `system_prompt=SYSTEM_PROMPT_V2`
5. Post-retry validation: `_validate_and_canonicalize_script_v2` directo sin condicional
6. REVIEW_REQUIRED: guard simplificado sin `visual_schema_version == 2`
7. Canonical persistence: `if all_ok:` sin condicional de versión
8. `visuals_request["schemaVersion"]` = 2 incondicional
9. `visualSchemaVersion` stdout = `visual_schema_version` (siempre 2 por argparse)

## Código V1 todavía presente pero sin callers productivos

- `SYSTEM_PROMPT` (línea 40)
- `_build_duration_prompt_instruction()` (línea 516)
- `_validate_script_structure()` (línea 601)
- `_build_retry_instruction()` (línea 709)
- `_build_user_prompt()` (línea 797)
- Tests unitarios V1 en `test_generate_script.py` (líneas 19-400 approx)

## Tests migrados

### test_generate_script.py

- `test_main_retry_loop_3_attempts_3rd_succeeds`: migrado a fixtures V2 (`_V2_VALID_4_SCENE`, `_V2_ABOVE_MAX_WORDS`, `_V2_SINGLE_SCENE_CTA`); mock actualizado para aceptar `system_prompt`; asserts actualizados para `INSUFFICIENT_SCENE_COUNT`
- `test_main_retry_loop_3_attempts_all_fail_review_required`: migrado a fixture V2 single-scene CTA; mock actualizado

### test_generate_script_v2.py

- `test_default_uses_system_prompt`: simplificado, verifica default V2
- `test_explicit_v1_uses_system_prompt` → `test_explicit_v1_is_rejected`: `pytest.raises(SystemExit)`, code == 2, "invalid choice" en stderr
- `test_v1_prompt_preserves_historical_requirements` → `test_v1_is_rejected_by_argparse`: misma estructura de rechazo

### test_v2_only_generation_contract.py

- `test_explicit_v1_not_reinterpreted` → `test_explicit_v1_is_rejected`: `pytest.raises(SystemExit)`, code == 2, "invalid choice" en stderr

## Resultados de tests

```
test_v2_only_generation_contract.py:  7 passed
test_generate_script_v2.py:          77 passed
test_generate_script.py:             52 passed
test_run_job.py (build_script_command): 2 passed
Total focalizado:                   138 passed, 0 failed
```

## Reindexado

Ejecutado: `codebase-memory-mcp cli index_repository --repo-path ... --mode fast --persistence false`

## Review y cierre

- **Resultado:** APPROVE_WITH_NON_BLOCKING_NOTES
- Sin findings funcionales bloqueantes
- Nombre del session log corregido: eliminado ":" para portabilidad Windows
- SYSTEM_PROMPT y helpers V1 siguen físicamente presentes, sin callers productivos desde main()
- La eliminación física queda pendiente para Slice 3B
- Reducción de assertions internas del retry prompt: considerada no bloqueante, revisable en Slice 3B
- Tests focalizados reconfirmados: 138 passed, 0 failed
- Slice 3A cerrado mediante el commit de esta iteración

## Siguiente trabajo

Slice 3B — eliminación física de SYSTEM_PROMPT, helpers V1, imports y tests muertos.
