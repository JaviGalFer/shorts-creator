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
- Hardening de runtime: retry prompts y repair post-TTS usan el `scenePlan` persistido, por lo que un deep_60 válido de 10 escenas no recae al fallback 4-6 durante EXPAND/COMPRESS.
- E2E canónico deep_60 `cmo-2026-08-16-203059`: MP4 60.37s, 9 escenas (plan adaptativo 9-11, preferencia 10), 2 reparaciones de voiceover, cumplimiento solicitado PASS y `VALIDATED`. El `cmo-2026-08-16-194540` fallido queda como contexto histórico de la planificación adaptativa.

## Change activo: `generic-tts-provider-runtime`
- Slice 1 completado: el runtime per-scene ya no fija `edge_tts`; `generate_audio_with_timestamps()` recibe el proveedor seleccionado vía `tts_provider` y `main_per_scene()` lo reenvía. La validación de disponibilidad es uniforme para todos los proveedores (sin fallback silencioso a Edge; credenciales ausentes fallan explícito).
- Modo continuo sigue siendo Edge-only en Slice 1: `continuous` con un proveedor no-Edge falla con `CONTINUOUS_TTS_PROVIDER_UNSUPPORTED` antes de sintetizar o mutar metadata.
- Slice 2 completado: ElevenLabs es ahora un proveedor per-scene con timing nativo real vía `POST /v1/text-to-speech/{voice_id}/with-timestamps`. El adapter decodifica `audio_base64`, mide el audio real y normaliza el alineamiento de caracteres a las mismas `word_boundaries` canónicas (prefiere `normalized_alignment`, cae a `alignment`; malformado → sin timing nativo → fallback estimado). `timing_support="word"`.
- Metadata corregida: Edge `timing_support="word"`; `activeDurationSource` es `subtitle_timing_last_cue_plus_guard` (neutro al proveedor). Se eliminó el leak de labels de fallback Edge en el generador genérico (`native_word_boundary`/`native_sentence_boundary`).
- Hardening de runtime (config, dentro de Slice 2): la resolución efectiva de provider/voz/secreto/modelo ahora lee `.env` del proyecto (y luego el entorno del proceso) y se calcula una sola vez en `generate_audio()`; la voz del provider (`ELEVENLABS_VOICE_ID`) gana sobre la voz por defecto de Edge, y la misma configuración se usa en disponibilidad y síntesis (inicial y regeneración). El API key no se persiste nunca.
- Slice 3 (pendiente): validación real de ElevenLabs (opt-in con key) / cierre. Edge sigue siendo el proveedor validado y por defecto.

## Baseline y límites
- Baseline estable conocida en main: **`1215 passed, 0 failed`**. Suite completa de la rama activa tras presets/status: **`1198 passed, 51 skipped, 0 failed`**.
- `AUDIO_DURATION_MISSING` está resuelto. `ffprobe` no está en host y depende del fallback Docker.
- `generic-duration-fitting`: COMPLETED / VERIFIED / CLOSED. quick_30 `cmo-2026-08-16-194012`: VALIDATED. deep_60 `cmo-2026-08-16-203059`: VALIDATED (60.37s, 9 escenas). Suite completa al cierre: **`1243 passed, 0 skipped, 0 failed`**.
