# Sesión: Runner real prepare verification after contract alignment

- Fecha: 2026-07-06
- Objetivo: Verificación real del runner a través de prepare tras alineación de contratos (script retry, structural validation, shared editorial contract, strategy-as-type removal).
- Cambio OpenSpec: `improve-historical-visual-pipeline` (Phase 23 runner verification)
- Comando: `python3 bin/run_job.py --topic "La caída del Muro de Berlín" --duration 30 --duration-max 35 --stop-after prepare --verbose`

## Precondiciones

| Prerrequisito | Estado |
|---------------|--------|
| git clean (solo archivos modificados intencionalmente) | OK |
| 267 tests passing | OK (6.78s) |
| Scripts importables | 7/7 ok |
| Edge TTS | disponible |
| LLM_API_KEY | presente |
| LLM_PROVIDER | presente |
| PEXELS_API_KEY | presente |
| PIXABAY_API_KEY | presente |

## Resultado: Bloqueo en script stage

**Job ID:** `la-2026-07-06-192920`
**Job path:** `data/videos/la-2026-07-06-192920`

### Runner JSON final

```json
{
  "jobId": "la-2026-07-06-192920",
  "jobPath": "/home/javi/projects/shorts-creator/data/videos/la-2026-07-06-192920",
  "status": "REVIEW_REQUIRED",
  "lastCompletedStage": "script",
  "outputVideoPath": null,
  "validationStatus": null
}
```

### Orchestration

| Stage | Status |
|-------|--------|
| script | REVIEW_REQUIRED |

Runner correctly stopped. No assets, audio, or prepare executed.

### Script retry evidence (3 / MAX_SCRIPT_ATTEMPTS=3)

| Retry | Reason | Words | Est. Dur | Instruction | Structural Issues |
|-------|--------|-------|----------|-------------|-------------------|
| 0 | `insufficient_segments` | 80 | 45.0s | `fix_structure_then_duration` | 3 issues: scene 1 missing ≥2 segments; scene 2 civilian_impact+broll; scene 3 battle_or_assault+broll |
| 1 | `forbidden_segment_asset_type` | 52 | 29.8s | `fix_structure_then_duration` | 2 issues: scene 1 context_map+historical_photograph; scene 3 battle_or_assault+atmospheric_broll |
| 2 | `insufficient_segments` | 61 | 34.7s | `fix_structure_then_duration` | 4 issues: scene 1 insufficient segments; scene 2 battle_or_assault+broll; scene 3 civilian_impact+broll; scene 4 insufficient segments |

### Duration contract

| Campo | Valor |
|-------|-------|
| `status` | FAIL |
| `structureValid` | False |
| `structureIssues` | `[insufficient_segments, forbidden_segment_asset_type, forbidden_segment_asset_type, insufficient_segments]` |
| `wordCount` | 61 |
| `sceneCount` | 5 |
| `estimatedDurationSec` | 34.7 |
| `budget` | 47-52-61 words |

### Verificación de comportamiento

1. **MAX_SCRIPT_ATTEMPTS=3** funcionando: el LLM recibió 1 generación inicial + 2 retries correctivos (3 llamadas total).
2. **Retry prompts contienen el contrato completo**: el LLM corrigió los tipos prohibidos entre retry 0 y retry 1 (broll → atmospheric_broll) pero seguía usando tipos incompatibles.
3. **Structural validation activa**: los 3 intentos fueron rechazados por problemas estructurales, no por duración. Retry 1 habría pasado el presupuesto de words (52 en rango 47-61) pero fue rechazado por `forbidden_segment_asset_type`.
4. **Retry reasons correctos**: estructural issues (no word-count) son la razón principal cuando hay problemas de estructura.
5. **Retry history completo**: 3 entradas con structuralIssues y structuralIssueDetails.
6. **Runner gate respetado**: `REVIEW_REQUIRED`, sin ejecución de assets/audio/prepare.

### Análisis del fallo

Las correcciones al SYSTEM_PROMPT (JSON example, portrait rule, b-roll motionType) y a la validación estructural (`forbidden_segment_asset_type`, `insufficient_segments`) están funcionando correctamente. El LLM todavía produce visualSequences con tipos incompatibles y <2 segmentos en escenas >4s. El prompt de retry incluye los diagnostics estructurales, pero el LLM no los resuelve completamente en 3 intentos.

Esto no es un defecto del pipeline — es un problema de compliance del LLM que requerirá refinamiento del prompt, no cambios en el código de validación.

## No verificado

- Runner a través de prepare (no ejecutado por bloqueo en script).
- Asset validation, fallback, reuse en producción.
- Audio, prepare, render, validate stages.

## Archivos

- Job: `data/videos/la-2026-07-06-192920/`
- Solos archivos de metadata generados por `generate_script.py` y `run_job.py`.
- Sin cambios a código fuente en esta verificación.

## Corrección post-verificación: ambigüedades prompt/schema (misma sesión)

### Contradicciones confirmadas

1. **Schema permitía `broll` genérico**: `primaryAssetType: "...|broll"` y `secondaryAssetType: "...|broll|null"` sin calificación. El LLM usaba `broll` para roles prohibidos.
2. **Faltaba cheat-sheet explícito**: El prompt describía cada rol con "AssetType preferido" pero sin lista completa de tipos permitidos/prohibidos.
3. **Faltaba validación de temporal intent**: `context_map + context_or_setup` no era rechazado.
4. **Faltaba validación de primaryAssetType y secondaryAssetType**.
5. **Instrucciones de retry no incluían sugerencias de reemplazo**.

### Correcciones

1. `editorial_asset_contract.py`: `ROLE_INTENT_RULES`, `is_temporal_intent_allowed()`, `allowed_asset_types_for_role()`, `suggest_replacement_types()`.
2. `_validate_script_structure()`: `forbidden_visual_temporal_intent`, `forbidden_primary_asset_type`, `forbidden_secondary_asset_type`. Cada una con sugerencias `(use: type1, type2)`.
3. SYSTEM_PROMPT: schema calificado + cheat-sheet de tipos + tabla de rol↔intent.
4. Retry: segmentos 5-7s → "EXACTAMENTE 2 segmentos con durationFraction sumando 1.0".

+7 tests (274 total). Sin verificación real del runner.

### Archivos modificados

- `bin/editorial_asset_contract.py` — `ROLE_INTENT_RULES`, `is_temporal_intent_allowed`, `allowed_asset_types_for_role`, `suggest_replacement_types`
- `bin/generate_script.py` — `_validate_script_structure` extendido, SYSTEM_PROMPT cheat-sheet + schema fix, retry segment rules
- `tests/test_generate_script.py` — +7 tests

## Allow-list redesign (misma sesión)

### Por qué el deny-list era inseguro

`allowed_asset_types_for_role()` computaba `all_known_types - forbidden_types`. Esto convertía en "permitidos" todos los tipos no explícitamente prohibidos: `context_map` permitía `portrait`, `painting`, `historical_art`; `military_technology` permitía `broll`; `character_portrait` permitía `generated_reconstruction`.

### Diseño

`ROLE_ALLOWED_TYPES` con sets explícitos por rol. Roles desconocidos y tipos desconocidos → fail closed. `EDITORIAL_ROLE_PREFERENCES` legacy se construye desde `ROLE_ALLOWED_TYPES`.

### Segment-count enforcement

≤4s: 1 seg | 5-7s: 2 segs | ≥8s: 2-3 segs. Códigos: `invalid_segment_count_short/medium/long`.

### Tests: +17 (291 total suite)

Archivos: `editorial_asset_contract.py` (rewrite), `generate_script.py` (segment-count), tests (+17 + 3 updated + 1 updated en semantic).
