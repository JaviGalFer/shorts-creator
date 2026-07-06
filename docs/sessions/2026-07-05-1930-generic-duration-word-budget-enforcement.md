# Sesión: Generic duration-to-word-budget enforcement

- Fecha: 2026-07-05
- Objetivo: Implementar un motor genérico de presupuesto de palabras basado en valores numéricos de duración, que fuerce al LLM a generar guiones con el word count correcto descontando pausas entre escenas.
- Estado inicial: El LLM generaba sistemáticamente guiones cortos para `standard_32_38` (54 palabras → 30.9s cuando se necesitan 32s mínimos). El prompt usaba estimación lineal WPM sin descontar pausas.
- Estado final: `calculate_word_budget()` en `bin/duration_profiles.py`. Prompt inicial y retry incluyen minimumWords/preferredWords/maximumWords. 117/117 tests pasando.
- Cambio OpenSpec relacionado: improve-historical-visual-pipeline (Phase 21)
- Validaciones realizadas: 117/117 tests passing. Metadata generation verificada.

## Implementación

### `calculate_word_budget()` en `bin/duration_profiles.py`

Función genérica que calcula el presupuesto de palabras a partir de valores numéricos:

```python
pauseSec = max(0, sceneCount - 1) * estimatedScenePauseMs / 1000
minimumWords   = ceil(max(0, minSec - pauseSec) / 60 * WPM)
preferredWords = round(max(0, targetSec - pauseSec) / 60 * WPM)
maximumWords   = floor(max(0, maxSec - pauseSec) / 60 * WPM)
```

No referencia nombres de perfil — solo valores numéricos.

### Cambios en `generate_script.py`

1. **Prompt inicial**: `_build_duration_prompt_instruction()` ahora recibe el budget completo e incluye minimumWords, preferredWords, maximumWords, y rango por escena.
2. **Validación post-LLM**: se recalcula el budget con sceneCount real.
3. **Retry**: `_build_retry_instruction()` genera prompt correctivo específico con word count real, faltante, y guía de expansión.
4. **Duration contract**: incluye minimumWords, preferredWords, maximumWords, pauseSec.
5. **Retry history**: ampliado con reason, minimumWords/preferredWords/maximumWords, instructionType.

### Tests añadidos

12 tests nuevos en `tests/test_duration_profiles.py`:
- Budget para todos los perfiles (short, standard, extended)
- Budget con valores explícitos no relacionados a perfiles
- Provisional scene count (1-8)
- Zero pause para 1 escena
- Overrides explícitos
- Clasificación below_minimum / in_range
- Prompt instruction contiene budget
- Retry instruction contiene corrección

## Archivos modificados/creados

| Archivo | Cambio |
|---------|--------|
| `bin/duration_profiles.py` | Añadida `calculate_word_budget()` + targetSec/minSec/maxSec en return |
| `bin/generate_script.py` | Nuevas funciones `_build_duration_prompt_instruction(budget)` y `_build_retry_instruction()`; main() usa word budget en prompt, retry, y durationContract |
| `tests/test_duration_profiles.py` | 12 nuevos tests de word budget |
| `openspec/changes/improve-historical-visual-pipeline/design.md` | Añadida Phase 21 |
| `openspec/changes/improve-historical-visual-pipeline/tasks.md` | Añadida Phase 21 |

## Tests

```bash
python3 -m pytest tests/ -v
# → 117 passed in 5.79s
```

## Verificación metadata

```bash
python3 bin/generate_script.py --duration-profile standard_32_38 --topic "La batalla de Stalingrado"
```

Resultado: 57 palabras, 32.5s estimados, SCRIPT_DRAFT (no REVIEW_REQUIRED).
RetryHistory: reason=in_range.
DurationContract: minimumWords=57, preferredWords=62, maximumWords=67, pauseSec=1.4.

## Corrección posterior: prompt-contract contradiction

Se identificó que SYSTEM_PROMPT contenía reglas fijas de "Reglas de ritmo para Short (<30s)" con duración "25-30 segundos" y "~45-55 palabras" que contradecían las instrucciones dinámicas para perfiles standard_32_38 y extended_50_60.

Se reescribió la sección para que contenga solo reglas independientes de duración. La duración, presupuesto de palabras y número de escenas se delegan exclusivamente a `_build_duration_prompt_instruction()`.

Tests añadidos (6):
- SYSTEM_PROMPT sin "25-30"
- SYSTEM_PROMPT sin "45-55"
- standard_32_38 prompt dinámico incluye 32-38 y 57-67
- extended_50_60 prompt dinámico incluye su propio budget
- short_25_30 prompt dinámico incluye su rango correcto
- Prompt dinámico no tiene referencias fijas a under-30

## Stalingrad — factual-risk wording

El guion generado para Stalingrad incluye:

> "Más de 2 millones de personas murieron en Stalingrado, un horror inimaginable."

La cifra "más de 2 millones" no es universalmente aceptada. Las estimaciones de bajas totales (militares + civiles, ambos bandos) varían entre 1.1M y 2.5M. Se recomienda redacción conservativa como "Alrededor de 2 millones" o "Más de un millón" a menos que se disponga de fuente verificada. No se añade verificador externo — queda como nota de riesgo documental.

## Próximos pasos

1. Implementar `--duration` CLI flag y `requestedSec` en el request schema.
2. Verificar jobs legacy con el nuevo word budget.
3. Considerar aumentar `max_attempts` si el retry único sigue siendo insuficiente para perfiles largos.

## Bloqueos o decisiones pendientes

- El `max_attempts=2` (1 initial + 1 retry) puede ser insuficiente para perfiles como `extended_50_60` donde el salto de palabras es mayor. Evaluar tras verificar con generaciones reales.
- `--duration` / `requestedSec` no forma parte de esta fase — será Phase 22.
