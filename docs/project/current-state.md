# Estado actual del proyecto

**Última actualización:** 2026-07-14

## Estado global

Pipeline funcional de vídeos cortos verticales (9:16, ~1 min). Scripts en `bin/` operativos. n8n como orquestador legacy. Docker para render.

**Último change completado:** `integrate-native-visual-plan-v2-generation` (2026-07-14)

**Change activo:** `improve-short-form-audio-pacing-v2` — Phase A completada, Phase B pendiente

## Próximos pasos

1. Phase B: calibración de voz/WPM, word budget, Edge TTS rate, nuevo E2E 27–30s
2. Mejorar prompts de búsqueda de imágenes v2 (`improve-visual-query-relevance-v2`)
3. Mejorar calidad y relevancia semántica de assets
4. Mejorar voz Edge TTS
5. Investigar instalación de ffprobe en el host
6. Registrar FreeAI para imágenes de calidad gratuitas
7. Integrar pipeline v2 con n8n

## Audio pacing v2 — Phase A (completada 2026-07-14)

### Causa raíz del silencio

- Docker client (v1.52) incompatible con Docker daemon (API v1.43).
- `_get_mp3_duration()` fallaba silenciosamente → `durationSec = None` en todas las escenas.
- `prepare_job` usaba `targetDurationSec = 6` como fallback.
- `render_job` aplicaba `apad` + `atrim` para rellenar cada escena hasta 6s.
- Resultado: 50.9% silencio con 48 palabras en 30s.

### Correcciones implementadas

| Archivo | Cambio |
|---------|--------|
| `bin/generate_audio.py` | `_get_mp3_duration()` añade `DOCKER_API_VERSION=1.43`; retorna `(dur, source)`; `duration_estimated` y `durationSource` en metadata; `activeAudioDurationSec` desde último cue + guard |
| `bin/prepare_job.py` | Bloquea cuando `duration_estimated=true` o sin `durationSource`; nueva fórmula `sceneWindowSec = activeAudioDur + tailPause` |
| `bin/render_job.py` | `_docker_ffmpeg()` añade `DOCKER_API_VERSION=1.43`; `build_per_scene_audio_filter` acepta `active_audio_sec` para trim de room tone; pacing validation en quality gate |
| **NUEVO** `bin/pacing_validation.py` | Métricas: silenceRatio, maxInterSceneSilenceSec (con scene boundaries), narrationCoverageRatio, timelineWPM, effectiveSpeechWPM |
| `bin/validate_job.py` | Nuevo check `_check_pacing`; Docker env en `_run_docker_ffprobe` |

### Nuevo contrato temporal

```
activeAudioDurationSec = min(physicalDuration, lastCueEndSec + 0.10s)
sceneWindowSec = activeAudioDurationSec + sceneTailPauseSec (0.25s)
```

`targetDurationSec` es solo informativo. La ventana se deriva del audio activo medido.

### Resultados E2E (job `cmo-2026-07-14-180923`)

| Métrica | Antes (Phase A) | Después (Phase A.1) |
|---------|-------|---------|
| Duración | 22.640s | 18.30s |
| Silencio | 8.74s (38.7%) | ~4.4s (24.2%) |
| Narración coverage | 61.3% | 75.8% |
| maxInterSceneSilence | 1.618s | 0.775s |
| timelineWPM | — | 157.8 |
| effectiveSpeechWPM | — | 208.1 |
| qualityGate | FAIL | PASS |

Duración activa por escena:
- S1: 3.825s, S2: 3.587s, S3: 3.712s, S4: 3.113s, S5: 2.763s
- Total + 5 × 0.25s = 18.25s

La reducción de duración a ~18s se debe al word budget de Phase A (48 palabras).
Phase B expandirá a 27–30s con WPM calibrado.

### Baseline de tests

```text
1215 passed, 16 failed (preexistentes en test_run_job.py + test_semantic_asset_validation.py), 0 regresiones
```
