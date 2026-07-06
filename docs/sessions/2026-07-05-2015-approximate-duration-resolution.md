# Sesión: Approximate duration resolution (`--duration` flag)

- Fecha: 2026-07-05
- Objetivo: Implementar `--duration <seconds>` CLI flag que permita a usuarios especificar duración aproximada sin conocer nombres de perfil, con auto-selección de perfil, tolerance-based min/max, y persistencia en metadata.
- Estado inicial: Solo existían `--duration-profile` (nombres de perfil), `--duration-target/min/max` (overrides exactos). No había forma de decir "quiero ~42 segundos".
- Estado final: `resolve_requested_duration()` en `bin/duration_profiles.py`. CLI acepta `--duration 42`, auto-selecciona perfil, calcula rango tolerance-based, valida consistencia, persiste `requestedSec`/`requestedProfile`. 134/134 tests pasando.
- Cambio OpenSpec relacionado: improve-historical-visual-pipeline (Phase 22)
- Validaciones realizadas: 134/134 tests passing. Dry-run verificada con --duration 28, 42, 55, 19, 61, y combinaciones incompatibles.

## Implementación

### `resolve_requested_duration()` en `bin/duration_profiles.py`

Función central que implementa la prioridad de resolución:

1. Overrides explícitos (`--duration-target/min/max`) — máxima prioridad
2. `--duration` N segundos — auto-selecciona perfil, calcula tolerance-based range
3. `--duration-profile NOMBRE` — perfil explícito
4. Default: `short_25_30`

### Auto-selección de perfil

| Rango | Perfil |
|-------|--------|
| 20-30 | `short_25_30` |
| 31-45 | `standard_32_38` |
| 46-60 | `extended_50_60` |

### Tolerance dinámica

```
tolerance = clamp(round(N * 0.10), min=2, max=5)
minSec = requestedSec - tolerance
maxSec = requestedSec + tolerance
```

### Clamping condicional

- **Perfil explícito** + `--duration`: siempre se constrain a profile bounds → si target queda fuera, error.
- **Auto-selección** (solo `--duration`): constrain solo si `min <= target <= max` tras clamping. Si no, se usa rango tolerance-based sin cap.

Ejemplo clave: `--duration 42` → auto `standard_32_38` (32-38). Tol=4 → rango 38-46. Target=42 > max=38 → skip cap, rango final 38-46. Esto es correcto porque el usuario pidió ~42s y el perfil de 35s es solo una guía de ritmo.

### Arquitectura

Toda la lógica de resolución vive en `bin/duration_profiles.py`:
- `resolve_requested_duration()` — nuevo resolver principal
- `_auto_select_profile()` — helper privado para mapeo segundos→perfil
- `resolve_duration_config()` — preservado sin cambios para tests legacy
- `add_duration_profile_args()` — añadido `--duration` arg

`generate_script.py` solo importa y llama `resolve_requested_duration()`, sin lógica de resolución duplicada.

### Persistencia

```json
"request": {
  "duration": {
    "targetSec": 42,
    "minSec": 38,
    "maxSec": 46,
    "strictness": "balanced",
    "requestedSec": 42,
    "requestedProfile": "auto"
  }
}
```

### Renombrado

`MAX_SCENES_FOR_SHORT` → `MAX_SCENES` por claridad. No hay otro perfil con constante separada.

### Tests añadidos

11 tests nuevos en `tests/test_duration_profiles.py`:

| Test | Verifica |
|------|----------|
| `test_duration_28_resolves_short_profile` | Auto-selección short |
| `test_duration_35_resolves_standard_profile` | Auto-selección standard |
| `test_duration_42_resolves_standard_profile` | Auto-selección standard con clamping bypass |
| `test_duration_55_resolves_extended_profile` | Auto-selección extended |
| `test_duration_20_and_60_boundaries` | Valores frontera aceptados |
| `test_duration_19_and_61_fail` | Fuera de rango rechazado |
| `test_explicit_profile_incompatible_duration_fails` | Combo incompatible rechazado |
| `test_explicit_overrides_highest_priority` | Overrides tienen prioridad sobre --duration |
| `test_invalid_numeric_combination_fails` | min > target rechazado |
| `test_legacy_no_args_defaults_to_short` | Sin args = default short |
| `test_word_budget_uses_resolved_values` | Word budget usa valores resueltos |

## Archivos modificados/creados

| Archivo | Cambio |
|---------|--------|
| `bin/duration_profiles.py` | Añadidas `resolve_requested_duration()`, `_auto_select_profile()`, `SUPPORTED_DURATION_MIN/MAX`; actualizada `add_duration_profile_args()` con `--duration` |
| `bin/generate_script.py` | Importa `resolve_requested_duration`; main() usa nuevo resolver; persistencia de `requestedSec`/`requestedProfile`; renombrado `MAX_SCENES_FOR_SHORT` → `MAX_SCENES` |
| `tests/test_duration_profiles.py` | 11 nuevos tests para `resolve_requested_duration()` |
| `openspec/changes/improve-historical-visual-pipeline/design.md` | Añadida Fase 22 |
| `openspec/changes/improve-historical-visual-pipeline/tasks.md` | Añadida Fase 22; eliminada limitación #8 |

## Tests

```bash
python3 -m pytest tests/ -v
# → 134 passed in 6.28s
```

## Verificación dry-run

```bash
# --duration 28 → short_25_30, window 25-30
python3 bin/generate_script.py --topic Stalingrad --duration 28 --dry-run

# --duration 42 → standard_32_38, window 38-46 (clamping bypassed)
python3 bin/generate_script.py --topic Stalingrad --duration 42 --dry-run

# --duration 55 → extended_50_60, window 50-60
python3 bin/generate_script.py --topic Stalingrad --duration 55 --dry-run

# --duration 19 → ERROR
python3 bin/generate_script.py --topic Stalingrad --duration 19 --dry-run

# --duration 61 → ERROR
python3 bin/generate_script.py --topic Stalingrad --duration 61 --dry-run

# --duration 42 --duration-profile short_25_30 → ERROR
python3 bin/generate_script.py --topic Stalingrad --duration 42 --duration-profile short_25_30 --dry-run
```

## Próximos pasos

1. Integrar `--duration` en n8n workflow para que los usuarios puedan especificar duración en el formulario.
2. Considerar aumentar `max_attempts` si el retry único sigue siendo insuficiente para perfiles largos.
3. Evaluar si los valores tolerance-based producen consistentemente guiones que pasan durationContract sin retry.

## Bloqueos o decisiones pendientes

- La verificación real (con LLM call real y metadata.json generado) no se ejecutó por costo de API. La verificación dry-run + tests unitarios cubren toda la lógica de resolución.
- El clamping condicional fue la decisión de diseño más importante: permite que `--duration 42` funcione con `standard_32_38` aunque 42 > 38, porque el usuario pidió explícitamente ~42s.
