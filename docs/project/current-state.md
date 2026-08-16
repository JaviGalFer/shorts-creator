# Estado actual del proyecto

**Última actualización:** 2026-08-16

## Estado vigente
- Arquitectura modular V2 completa. `src/shorts_creator/` contiene contratos, pipeline, script, audio, assets, rendering, validation e infrastructure; `bin/` son adaptadores CLI.
- Pipeline canónico: `script -> assets -> audio -> prepare -> render -> validate`. n8n es legacy/alternativo.
- Primer E2E técnico completo: job `cmo-2026-08-16-172847`, hasta `VALIDATED`. Request: target 30s, rango 27-30; timeline 20.813s y MP4 aproximadamente 20.88s.
- El mismatch de duración descubierto confirmó que la medición TTS real debe prevalecer sobre el bootstrap WPM.

## Change activo: `generic-duration-fitting`
- Slice 1 completado: contrato post-TTS PASS/EXPAND/COMPRESS, ratio genérico 0.70..1.50, distribución por escena y repair voiceover-only desacoplado del presupuesto WPM.
- Slice 2 completado con tests focales simulados: loop en orquestador, máximo dos repairs, proyección compartida con prepare, regeneración TTS forzada y reutilización de assets. Si se agota, el job queda `REVIEW_REQUIRED` con `DURATION_FITTING_EXHAUSTED` sin ejecutar prepare/render.
- Hardening runtime de Slice 2: el repair reutiliza la resolución LLM del dominio script (`.env` incluido) y la regeneración preserva provider/voice/timing del audio previo. No amplía el path per-scene real a multi-provider TTS.
- Slice 3 completado (`6cfb8c3`): `requestedDurationCompliance` usa la duración real del MP4, queda separado de `renderDurationIntegrity`, se persiste en metadata/manifest y un producto fuera de rango termina `REVIEW_REQUIRED`, no `FAILED`.
- Intento E2E real `cmo-2026-08-16-184819`: bloqueado en script porque el gate histórico de estimación WPM rechazó un V2 válido de 67 palabras (37.9s estimados). Fix implementado: V2 válido => `SCRIPT_DRAFT`; la estimación bootstrap sigue como telemetría no bloqueante y TTS real decide después.
- E2E real `cmo-2026-08-16-190441`: el contrato legado de `--duration 30` era 27-30; comprimió 30.587s pese a estar cerca del target y aceptó 27.314s. El contrato canónico ahora usa presets centrados (`quick_30`=27-33, `standard_45`=41-49, `deep_60`=55-65) o duración custom con tolerancia simétrica.
- `quick_30` quedó validado en E2E `cmo-2026-08-16-194012`: una reparación, timeline 31.587s, MP4 31.72s, cumplimiento solicitado PASS y `VALIDATED`. `deep_60` (`cmo-2026-08-16-194540`) se bloqueó en audio con `DURATION_FITTING_EXHAUSTED`: el plan fijo de 4-6 escenas produjo cinco escenas de 12s. Fix implementado: planificación genérica de ~6s/escena; 60s permite 9-11 y prefiere 10.

## Baseline y límites
- Baseline estable conocida en main: **`1215 passed, 0 failed`**. Suite completa de la rama activa tras presets/status: **`1198 passed, 51 skipped, 0 failed`**.
- `AUDIO_DURATION_MISSING` está resuelto. `ffprobe` no está en host y depende del fallback Docker.
- Siguiente paso exacto, antes de otra prioridad: `python3 bin/run_job.py --topic "Cómo funciona un agujero negro" --duration-preset deep_60 --verbose`.
