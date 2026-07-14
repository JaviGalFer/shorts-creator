# Sesion: Phase B Preflight-Manifest Alignment

**Timestamp:** 2026-07-11T21:30:00Z
**Change:** `stabilize-visual-v2-runtime-contracts`
**Modelo:** DeepSeek V4 Pro
**Modo:** Build (alineacion final)

## 1. Desalineacion preflight/timeline encontrada

`render_job.main()` pasaba `expected_total=None` al preflight para audio no continuo. El preflight caia en el fallback historico: sumar los `targetDurationSec` de todas las escenas. Esto producia falsos positivos cuando las escenas habian sido ampliadas por tener audio mas largo que el target.

## 2. Ejemplo: target total 10s vs timeline 19s

Escena 1: target=5s, audio=9s, timeline=0→9s
Escena 2: target=5s, audio=10s, timeline=9→19s

Suma de targets = 10s. Duracion canonical = 19s. El preflight comparaba 19s vs 10s y generaba error:

```
total timeline=19.0s vs expected=10.0s (delta=9.0s > 3.0s)
```

## 3. Causa raiz

El calculo de `expected_duration` via `resolve_expected_duration()` se hacia DESPUES del preflight (en la zona de construccion de filtros FFmpeg). El preflight se ejecutaba antes sin tener acceso a la duracion canonical.

## 4. Nueva fuente unica de expected_duration

Ahora `resolve_expected_duration()` se llama UNA vez, ANTES del preflight:

```python
audio_config = data.get('audio', {})
is_continuous_audio = audio_config.get('continuous', False)

expected_duration = resolve_expected_duration(
    render_timeline,
    is_continuous_audio=is_continuous_audio,
    continuous_duration_sec=(
        audio_config.get("durationSec") if is_continuous_audio else None
    ),
)
```

## 5. Confirmacion: se calcula antes del preflight

```python
errors = preflight_validate(
    ...,
    expected_total=expected_duration,  # ya no es None
    ...
)
```

El mismo valor se reutiliza despues para:
- Logging
- Musica
- CTA (`expected_duration += cta_dur`)
- Post-render validation
- Metadata final

No hay segunda llamada a `resolve_expected_duration()`.

## 6. Bug del manifest con audioDurationSec=0.0

`_get_scene_audio_info()` hardcodeaba `audioDurationSec = 0.0` para todas las escenas no continuas. No consultaba `audio.scenes[].durationSec`.

## 7. Fuente nueva desde audio.scenes[]

Nuevo helper `resolve_manifest_scene_audio_duration(audio_config, scene_number)`:

- Busca en `audio.scenes[]` por `sceneNumber`
- Devuelve duracion finita y positiva, o `None`
- `None` → zero, negativo, NaN, inf, bool, string, escena no encontrada
- No usa ffprobe
- No usa targetDurationSec
- No muta audio_config

El manifest ahora contiene `audioDurationSec: 6.576` en lugar de `0.0`.

## 8. Asociacion por sceneNumber

La asociacion es por `sceneNumber`, no por orden de array. Un `audio.scenes` con orden [3, 1, 2] asigna correctamente cada duracion a su escena.

## 9. Tests anadidos

**Preflight alignment (3 tests):**
- `test_expanded_scenes_use_scene_window_not_target_sum` — expanded timeline 19s no compara contra target 10s
- `test_resolve_expected_duration_for_expanded_scenes` — max(endSec) = 19.0
- `test_main_passes_expected_to_preflight` — spy intercepta preflight y verify `expected_total == 19.0`

**Manifest (7 tests):**
- `test_resolve_returns_duration_from_scenes` — 6.576 y 7.536
- `test_association_by_scene_number_not_order` — orden no importa
- `test_invalid_duration_returns_none` — None, 0.0, NaN, -1, bool, string → None
- `test_scene_not_found_returns_none` — escena inexistente
- `test_continuous_returns_none` — continuous audio
- `test_metadata_not_mutated` — no modifica config
- `test_integration_with_skip_render` — manifest con duraciones reales

## 10. Archivos modificados

- `bin/render_job.py` — expected_duration antes del preflight, resolve_manifest_scene_audio_duration
- `tests/test_render_job_scene_audio_contract.py` — +10 tests (27 total)
- `openspec/.../specs/per-scene-temporal-contract.md` — REQ-B07, REQ-B14
- `openspec/.../tasks.md` — tareas actualizadas

## 11. Resultado focalizado

```
tests/test_render_job_scene_audio_contract.py: 27 passed
All related suites: 197 passed
```

## 12. Resultado full suite

```
994 passed, 16 failed
```

## 13. Comparacion con 984/16

| Fase | Passed | Failed | Delta |
|------|--------|--------|-------|
| Tras correcciones finales | 984 | 16 | — |
| **Tras alignment** | **994** | **16** | **+10** |

## 14. OpenSpec actualizado

`specs/per-scene-temporal-contract.md`: REQ-B07 ampliado, REQ-B14 anadido.

## 15. Confirmacion: no se ejecuto E2E

No se ejecuto E2E live.

## 16. Confirmacion: sin campos legacy

No se anadieron.

## 17. Confirmacion: sin modos de dominio

No se anadieron.

## 18. Decision final sobre Phase B

Phase B completamente lista para cerrar. El preflight recibe la duracion canonical correcta. El manifest conserva las duraciones reales por escena. Todos los contratos estan implementados, testeados y alineados con el runtime.

**Recomendacion: ejecutar el E2E live con un job multi-segmento y cerrar el change.**
