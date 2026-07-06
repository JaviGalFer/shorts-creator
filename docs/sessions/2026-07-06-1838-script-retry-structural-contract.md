# Sesión: Script retry structural contract

- Fecha: 2026-07-06
- Objetivo: Arreglar el contrato de retry en `generate_script.py` expuesto por el job `la-2026-07-06-183114`.
- Cambio OpenSpec: `improve-historical-visual-pipeline` (Phase 23 script retry fix)

## Raíz del problema

El job `la-2026-07-06-183114` (`run_job.py --stop-after prepare`) falló en script stage con `REVIEW_REQUIRED`. Tres defectos en `generate_script.py`:

1. **`max_attempts=2`** permitía solo 1 retry correctivo (initial + 1 intento). El segundo intento de 8 palabras/1 escena fue el último, sin oportunidad de un tercer intento.

2. **Retry prompt descartaba el contrato completo.** El prompt de retry reemplazaba el original (con schema JSON, visualPlan, visualSequence, narrativeBeats, motionType, regla de 2+ segmentos) por uno mínimo que solo mencionaba el topic y las reglas básicas. El LLM perdía contexto y producía respuestas degeneradas.

3. **No existía validación estructural.** Solo se validaba scene count y duration. Una respuesta de 1 escena CTA con 8 palabras no era rechazada por falta de contenido histórico o estructura visual.

## Cambios realizados

### 1. `MAX_SCRIPT_ATTEMPTS = 3`

```python
MAX_SCRIPT_ATTEMPTS = 3  # initial generation + up to 2 corrective retries
```

Permite initial + 2 retries correctivos. Sin loop infinito.

### 2. Función `_validate_script_structure`

Nueva función que verifica antes de aceptar cualquier script:

| Comprobación | Código |
|-------------|--------|
| Escenas no vacías | `empty_scenes` |
| Escenas >= `MIN_SCENE_COUNT` (4) | `insufficient_scene_count` |
| Voiceover no vacío | `empty_voiceover` |
| visualPlan presente | `missing_visualPlan` |
| visualSequence presente | `missing_visualSequence` |
| Escenas >4s con ≥2 segmentos | `insufficient_segments` |
| Orden de sceneNumber | `unordered_scenes` |
| Contenido histórico (fecha o entidad nombrada) | `cta_only_or_non_historical` |

Retorna `{valid: bool, reasons: [(code, message), ...]}`.

### 3. Prompt de retry preserva el contrato completo

- Extraído `_build_user_prompt(topic, budget, strictness)` — función reusable que construye el prompt completo con schema, visualPlan, visualSequence, narrativeBeats, motionType, regla de segmentos.
- En cada retry: `base_retry = _build_user_prompt(...)` + `retry_instruction`.
- Los problemas estructurales se inyectan en `_build_retry_instruction` como sección "Problemas estructurales que debes corregir".

### 4. Taxonomía de razones de retry

| Código | Prioridad | Condición |
|--------|-----------|-----------|
| `code from _validate_script_structure` | 1ª (más alta) | `sv["valid"] == False` |
| `below_minimum_words` | 2ª | `word_count < min` y estructura OK |
| `above_maximum_words` | 2ª | `word_count > max` y estructura OK |
| `duration_out_of_range` | 2ª | duración fuera de rango pero word_count en budget |
| `in_range` | — | aceptación |

Si hay problemas estructurales, no se reporta el word count como razón principal.

### 5. Gate estructural antes de aceptación

```python
if sv["valid"] and duration_ok:
    break  # accept
```

Script debe pasar validación estructural Y duration para ser aceptado.

### 6. Metadata enriquecido

`durationContract` ahora incluye:
- `structureValid`: boolean
- `structureIssues`: lista de códigos si no válido

Cada entrada de `retryHistory` incluye `structuralIssues` y `structuralIssueDetails` cuando aplica.

## Tests añadidos (7 nuevos)

| Test | Cobertura |
|------|-----------|
| `test_max_script_attempts_is_three` | `MAX_SCRIPT_ATTEMPTS == 3` |
| `test_one_scene_eight_word_cta_is_structurally_invalid` | Script CTA de 1 escena → estructuralmente inválido |
| `test_multi_scene_valid_historical_passes_structure` | Script histórico de 4 escenas con visualPlan → válido |
| `test_structurally_invalid_accepted_only_if_duration_fits` | Inválido estructural rechazado aunque word count esté en rango |
| `test_retry_prompt_preserves_full_contract` | Prompt de retry contiene schema + visualPlan + visualSequence + narrativeBeats + motionType |
| `test_exhausted_retries_produce_review_required_structure_issues` | Retry history incluye structuralIssues |
| `test_build_user_prompt_contains_historical_requirements` | `_build_user_prompt` contiene reglas completas |

**Suite: 252/252 passed** (7 nuevos + 10 existentes en test_generate_script.py).

## No verificado

- No se ejecutó ningún job real del pipeline.
- Runner real a través de prepare sigue pendiente.
- Assets/audio/prepare production verification remains pending.

## Archivos modificados

- `bin/generate_script.py` — `MAX_SCRIPT_ATTEMPTS`, `_build_user_prompt`, `_validate_script_structure`, retry loop reescrito, `_build_retry_instruction` extendido, metadata enriquecido
- `tests/test_generate_script.py` — +7 tests

## Cierre de gaps (misma sesión)

### Defect A — faltaban tests de integración del bucle de retry

Los tests existentes solo validaban helpers y simulaban historia manualmente. No probaban `main()` completo.

**Corrección:**
- `test_main_retry_loop_3_attempts_3rd_succeeds` — `main()` completo con LLM mockeado. 3 llamadas: above_maximum_words → CTA estructuralmente inválido → válido. Assert: 3 call_llm, prompts contienen contrato completo, historia de retry verdadera, SCRIPT_DRAFT.
- `test_main_retry_loop_3_attempts_all_fail_review_required` — 3 llamadas todas fallan → REVIEW_REQUIRED, structureIssues persistidos.

### Defect B — conflicto de tipos segmento/rol entre generación y fetching

`generate_script.py` no validaba que los segment types fueran compatibles con el editorial role. Un script podía pedir `context_map + atmospheric_broll`, que `fetch_images.py` rechazaría.

**Corrección:**
- Creado `bin/editorial_asset_contract.py` con `EDITORIAL_ROLE_PREFERENCES` e `is_asset_type_allowed(role, type, temporal_intent)`.
- `fetch_images.py` importa desde el módulo compartido (eliminada duplicación).
- `generate_script.py` importa `is_asset_type_allowed` y lo usa en `_validate_script_structure`.
- Nueva razón: `forbidden_segment_asset_type`.
- Documented exception: `consequence_or_legacy + legacy_or_commemoration` permite atmospheric_broll/broll.

### Tests adicionales

| Test | Cobertura |
|------|-----------|
| `test_context_map_rejects_atmospheric_broll_in_script_structure` | context_map + atmospheric_broll → REJECT |
| `test_document_or_date_rejects_historical_photograph_in_script_structure` | document_or_date + historical_photograph → REJECT |
| `test_consequence_legacy_atmospheric_broll_allowed_with_legacy_intent` | exception → ALLOW |
| `test_consequence_legacy_atmospheric_broll_rejected_with_event_depiction` | event_depiction → REJECT |
| `test_shared_contract_used_by_fetch_and_generate` | ambos importan del mismo módulo |
| + test existente `test_multi_scene_valid_historical_passes_structure` actualizado con tipos compatibles |

**Suite: 259/259 passed.**

## Contract alignment (misma sesión)

### Contradicciones encontradas y corregidas

1. **SYSTEM_PROMPT JSON example** mostraba `context_map` con un segmento `atmospheric_broll` — prohibido por el contrato. Corregido a `document`.
2. **Prosa "Reglas de composición"** decía "Para portrait, puede ocupar todo el segmento o ir acompañado de broll atmosférico" — `character_portrait` prohíbe `atmospheric_broll`. Corregido.
3. **Prosa "motionType"** decía "B-roll: static, slow_zoom_in" sin restricción de rol. Añadida restricción: solo `consequence_or_legacy + legacy_or_commemoration`.
4. **fetch_images.py** tenía lógica duplicada de excepciones `.discard("atmospheric_broll")` / `.discard("broll")` en `_fetch_one_asset` y `score_editorial_role`. Reemplazada por `is_asset_type_allowed()` del módulo compartido.
5. **`_validate_segment_for_role`** leía `forbidden` directamente de prefs en lugar de usar `is_asset_type_allowed`. Reemplazado.
6. **Reuse path** en `main()` leía `ftypes` manualmente. Reemplazado por `is_asset_type_allowed`.

### Tests adicionales

| Test | Cobertura |
|------|-----------|
| `test_system_prompt_json_example_no_context_map_atmospheric_broll` | Ejemplo JSON no contiene par inválido |
| `test_prompt_prose_no_broll_for_portrait` | Prosa no recomienda broll para character_portrait |
| `test_validate_segment_for_role_uses_shared_helper` | Validador delega a `is_asset_type_allowed` |
| `test_fetch_images_no_duplicate_atmospheric_discard` | Sin `.discard()` duplicado en `_fetch_one_asset` |

**Suite: 263/263 passed.**

## Strategy-as-type removal (misma sesión)

### Incorrect call sites found

1. `_fetch_one_asset` filter (line ~920): `is_asset_type_allowed(er, c.get("strategy"), ...)` — trataba el strategy name como asset type.
2. `_fetch_one_asset` filter reasons (line ~1097): mismo patrón para logging.
3. `_fetch_one_asset` scoring (line ~901): `score_editorial_role(c.get("strategy"), er)` — puntuaba strategy como tipo.
4. `_try_hard_role_fallback` scoring (line ~1832): `score_editorial_role(c.get("strategy"), editorial_role)` — mismos errores.

### Design elegido

**Remover filtros basados en strategy** de `_fetch_one_asset`:
  - El validador final `_validate_segment_for_role` es la autoridad única de aceptación/rechazo por tipo.
  - Los filtros tempranos de candidato permanecen solo para: score negativo, score < MIN_SCORE, dimensiones, y Pexels para hard historical roles.

**Mantener `score_editorial_role`** pero con firma correcta:
  - Añadido `temporal_intent` opcional para aplicar la excepción de consequence_or_legacy.
  - Solo se llama desde `main()` (post-aceptación) y `_try_hard_role_fallback` (post-selección) con `seg_at` real.
  - Los callers pasan temporal_intent vía `_classify_temporal_intent(scene)`.

**Invariantes:**
- `is_asset_type_allowed` nunca recibe `candidate["strategy"]`.
- `strategy` determina provider chain y queries, no compatibilidad de tipo.
- `_validate_segment_for_role` sigue siendo la única autoridad final de tipo solicitado.

### Tests adicionales

| Test | Cobertura |
|------|-----------|
| `test_is_asset_type_allowed_never_receives_strategy_in_fetch_one_asset` | Invariante: sin strategy en filtros |
| `test_candidate_strategy_historical_archive_not_rejected_as_forbidden_type` | Candidate con strategy=historical_archive + effective_map → no rechazado |
| `test_consequence_legacy_atmospheric_broll_no_forbidden_score_penalty` | Excepción en scoring |
| `test_consequence_legacy_atmospheric_broll_event_depiction_scoring` | Sin excepción → penaliza |

**Suite: 267/267 passed.**
