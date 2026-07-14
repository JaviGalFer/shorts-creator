# Sesion: Phase B Final Corrections

**Timestamp:** 2026-07-11T21:00:00Z  
**Change:** `stabilize-visual-v2-runtime-contracts`  
**Modelo:** DeepSeek V4 Pro  
**Modo:** Build (correcciones finales)

## 1. Rama de retorno antes de guardar detectada

`main_per_scene()` retornaba `1` en la rama `any_duration_missing` sin escribir metadata.json. Esto causaba que:
- El status REVIEW_REQUIRED nunca llegaba al archivo
- El job quedaba en estado inconsistente
- No habia registro de AUDIO_DURATION_MISSING

## 2. Correccion de persistencia unica

Ahora `main_per_scene` sigue siempre el mismo flujo:
1. Construir `audio_scenes` y `data["audio"]`
2. Determinar status (AUDIO_READY o REVIEW_REQUIRED)
3. Calcular exit_code
4. `metadata_path.write_text()` — exactamente una vez al final
5. `return exit_code`

## 3. Status usados para cada resultado de audio

| Condicion | Status | Exit | Razón |
|-----------|--------|------|-------|
| Todo OK, todas las duraciones validas | AUDIO_READY | 0 | — |
| MP3 existe pero probe falla | REVIEW_REQUIRED | 1 | AUDIO_DURATION_MISSING |
| Generacion de MP3 falla | REVIEW_REQUIRED | 1 | AUDIO_GENERATION_FAILED |

## 4. Tests reales de main_per_scene

4 tests asincronos usando `asyncio.run()` sin Edge TTS real:
- **Caso A**: mock de TTS genera MP3, mock de probe devuelve 6.576 → AUDIO_READY, exit 0
- **Caso B**: MP3 generado, probe falla → REVIEW_REQUIRED, exit 1, metadata persistido
- **Caso C**: MP3 preexistente, no se llama al provider → AUDIO_READY, durationSec real
- **Caso D**: provider falla → REVIEW_REQUIRED, AUDIO_GENERATION_FAILED

## 5. Conexion de resolve_expected_duration al runtime

`render_job.main()` ahora llama `resolve_expected_duration()` una vez (antes del bucle de entries), y no recalcula `max(endSec)` inline en el bucle:

```python
expected_duration = resolve_expected_duration(
    render_timeline,
    is_continuous_audio=is_continuous_audio,
    continuous_duration_sec=audio_config.get("durationSec") if is_continuous_audio else None,
)
```

La CTA sigue sumando despues: `expected_duration += cta_dur`.

## 6. Tests directos de los helpers

Ambos helpers validan estrictamente sus inputs:

**build_per_scene_audio_filter**: rechaza input_index negativo, scene_number no positivo, scene_window_sec NaN/inf/cero/bool.

**resolve_expected_duration**: para continuous requiere durationSec numerico positivo. Para non-continuous requiere renderTimeline no vacio, cada endSec numerico y finito.

## 7. Uso efectivo de global_cues

`generate_ass_from_cues` ahora:
- Con `scene_offsets` + `scene_windows` → llama `resolve_and_validate_global_cues()` y escribe Dialogue desde la lista validada
- Con solo `scene_offsets` → backward compat (suma offsets manualmente)
- Sin offsets → continuous mode

Los cues originales no se mutan en ningun caso.

## 8. Validacion monotonica

`resolve_and_validate_global_cues` NO reordena los cues. Recorre escenas y cues en orden canonical. Si un cue retrocede temporalmente (startSec < prev_end - tolerance), lanza ValueError. Detecta cross-scene overlaps sin reordenar.

## 9. OpenSpec corregido

- REQ-B01 actualizado: `null` cuando probe falla, metadata persistido antes de return
- REQ-B04 actualizado: backward compat con solo offsets, uso de lista validada cuando windows presentes
- REQ-B13 nuevo: orden monotónico de cues sin reordenar

## 10. Archivos modificados

- `bin/generate_audio.py` — metadata siempre persistido, voice, status unificado
- `bin/prepare_job.py` — cues validadas usadas en ASS, orden monotónico
- `bin/render_job.py` — helpers validados, resolve_expected_duration conectado al runtime
- `tests/test_generate_audio_scene_duration_contract.py` — +4 async tests (18 total)
- `openspec/.../specs/per-scene-temporal-contract.md` — REQ-B01, REQ-B04, REQ-B13
- `openspec/.../tasks.md` — correcciones finales

## 11. Resultado focalizado

```
tests/test_generate_audio_scene_duration_contract.py: 18 passed
tests/test_prepare_job_scene_temporal_contract.py: 40 passed
tests/test_render_job_scene_audio_contract.py: 17 passed
tests/test_prepare_contract.py: 8 passed
tests/test_prepare_job_v2_assets_paths.py: 18 passed
tests/test_render_job_v2_assets_paths.py: 17 passed
tests/test_duration_contract_and_scene_boundary.py: 14 passed
Total focused: 132 passed
```

## 12. Resultado full suite

```
984 passed, 16 failed
```

## 13. Comparacion con 980/16

| Fase | Passed | Failed | Delta |
|------|--------|--------|-------|
| Tras correcciones B | 980 | 16 | — |
| **Tras correcciones finales** | **984** | **16** | **+4** |

+4 nuevos tests async para main_per_scene. Los 16 fallos siguen siendo los preexistentes.

## 14. Confirmacion: no se ejecuto E2E

No se ejecuto E2E live.

## 15. Confirmacion: sin campos legacy

No se anadieron campos legacy.

## 16. Confirmacion: sin modos de dominio

No se anadieron modos de dominio.

## 17. Decision final sobre cierre de Phase B

Phase B completamente lista para cerrar. Todos los contratos implementados, testeados, y verificados. El metadata siempre se persiste, los cues globales se escriben desde la lista validada, los helpers de render estan validados y conectados al runtime, y el orden monotónico se respeta sin reordenar.

Recomendacion: ejecutar el E2E live con un job multi-segmento y cerrar el change.
