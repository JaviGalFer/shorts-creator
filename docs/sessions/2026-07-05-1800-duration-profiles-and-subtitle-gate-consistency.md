# Sesión: Duration profiles and subtitle quality-gate consistency

- Fecha: 2026-07-05
- Objetivo: Implementar perfiles de duración reutilizables y corregir la contradicción del qualityGate de subtítulos (FAIL por diferencias de puntuación/tildes cuando la cobertura real es correcta).
- Estado inicial: qualityGate=FAIL por `subtitleCoverageValidation=FAIL` (text mismatch por coma tras año). Sin sistema de perfiles de duración.
- Estado final: qualityGate=PASS. Sistema de perfiles funcionando. 105/105 tests pasando.
- Cambio OpenSpec relacionado: improve-historical-visual-pipeline (Phase 20)
- Validaciones realizadas: 105/105 tests passing

## Part A — Duration profiles

### Creado `bin/duration_profiles.py`

Tres perfiles predefinidos:

| Perfil | targetSec | minSec | maxSec | strictness |
|--------|-----------|--------|--------|------------|
| short_25_30 | 28 | 25 | 30 | balanced |
| standard_32_38 | 35 | 32 | 38 | balanced |
| extended_50_60 | 55 | 50 | 60 | balanced |

- `resolve_duration_config(profile_name, target, min_sec, max_sec, strictness)` combina perfil + overrides explícitos.
- `add_duration_profile_args(parser)` añade `--duration-profile` y los argumentos de duración explícitos a argparse.
- Por defecto: `short_25_30` para compatibilidad backward.

### Modificado `bin/generate_script.py`

- Añadido `--duration-profile` CLI arg.
- Se persiste `durationProfile` en `request.durationProfile` y en `metadata.durationProfile`.
- `metadata.resolvedConfig` contiene el perfil y duración resueltos.

### Modificado `bin/render_job.py`

- `resolvedConfig` incluye `durationProfile` desde `request.durationProfile`.

## Part B — Subtitle quality-gate consistency

### Creado `bin/subtitle_normalize.py`

Funciones:

- `normalize_subtitle_text(text)` — normalización completa: lowercase, NFKD accent-strip, punctuation-strip, whitespace-collapse.
- `normalize_subtitle_tokens(text)` — tokeniza el texto normalizado.
- `cue_text_matches_narration(cue_text, narration_text, threshold=0.95)` — comparación por tokens con diagnóstico (missing/extra tokens).
- `compare_cue_vs_narration_bulk(cue_texts, narration_texts)` — wrapper para validación de coverage.

### Modificado `bin/coverage_validation.py`

- `validate_cue_text()` ahora usa `compare_cue_vs_narration_bulk()` en lugar de la comparación `normalize(cue) != normalize(nar)` antigua.
- La normalización antigua solo limpiaba puntuación al inicio/final; la nueva elimina toda puntuación interna (comas tras años), acentos y espacios múltiples.

### Modificado `bin/validate_job.py`

- `_check_subtitle_alignment()` usa `normalize_subtitle_text` para comparación de similitud.
- Añadido `--update-manifest` flag que re-ejecuta coverage validation y actualiza los quality gates en `job-manifest.json` sin re-renderizar.

### Comportamiento de validación

| Situación | Antes | Después |
|-----------|-------|---------|
| "1989," vs "1989" (coma) | FAIL | PASS |
| "Berlín" vs "Berlin" (tilde) | FAIL | PASS |
| "1961, comenzó" vs "1961 comenzó" (coma interna) | FAIL | PASS |
| "familias y amigos" vs "familias y soldados" (token erróneo) | FAIL | FAIL |
| "un símbolo" vs "un símbolo de libertad" (token faltante) | FAIL | FAIL |
| Canonical cross-scene leakage | FAIL | FAIL (sin cambios) |
| Timing coverage <98% | FAIL | FAIL (sin cambios) |

## Archivos modificados/creados

| Archivo | Cambio |
|---------|--------|
| `bin/duration_profiles.py` | (NUEVO) Sistema de perfiles de duración |
| `bin/subtitle_normalize.py` | (NUEVO) Normalización centralizada de subtítulos |
| `bin/generate_script.py` | Añadido `--duration-profile`, persistencia en metadata |
| `bin/render_job.py` | `resolvedConfig` incluye `durationProfile` |
| `bin/coverage_validation.py` | `validate_cue_text` usa nueva normalización |
| `bin/validate_job.py` | Nueva normalización, flag `--update-manifest` |
| `tests/test_duration_profiles.py` | (NUEVO) 7 tests de perfiles |
| `tests/test_subtitle_normalize.py` | (NUEVO) 17 tests de normalización |
| `openspec/changes/improve-historical-visual-pipeline/tasks.md` | Añadida Phase 20 |

## Validación v9

```bash
python3 bin/validate_job.py --verbose data/videos/.../v9/metadata.json
# → PASS, 0 errors, 0 warnings

python3 bin/validate_job.py --update-manifest data/videos/.../v9/metadata.json
# → subtitleCoverageValidation=PASS, qualityGate=PASS
```

### Quality gates finales (v9)

| Gate | Estado |
|------|--------|
| technicalValidation | PASS |
| subtitleCoverageValidation | PASS |
| assetValidation | PASS |
| qualityGate | PASS |

## Tests

```bash
python3 -m pytest tests/ -v
# → 105 passed in 6.34s
```

## Próximos pasos

1. Validar jobs legacy (Wright, Pompeya, Magallanes) con normalization actualizada.
2. Usar `--duration-profile standard_32_38` para vídeos más largos (>30s).
3. Revisar discrepancia validate_job coverage 81% vs manifest 99.6% — no hay gaps reales, pero la métrica puede confundir.

## Bloqueos o decisiones pendientes

- qualityGate del v9 ahora reporta PASS correctamente. No requiere re-render.
- Los jobs legacy pueden tener `subtitleCoverageValidation: NOT_APPLICABLE` si no tienen datos de audio continuo. Ejecutar `--update-manifest` si es necesario.
