# Tasks: Continuous Audio and Subtitle Timing

## Fase 0 — Diagnóstico de audio actual ✅
- [x] Medir silencios al inicio y final de cada MP3 de Constantinopla
- [x] Generar tabla: scene, audio_duration, leading_silence, trailing_silence, voice_duration, internal_pauses
- [x] Analizar audio final del MP4 y comparar con MP3 por escena
- [x] Confirmar origen de pausas (Edge TTS per-scene + concat gaps)
- [x] Documentar duración total de audio útil vs duración del archivo
- [x] Conclusión: 17.66s de silencio en 36.24s de vídeo (49%!)
  - EdgeTTS leading+trailing por escena: 7.20s total
  - Concat gaps adicionales en render: +8.61s
  - Pausas internas EdgeTTS: 1.84s
  - Causa raíz: COMBINACIÓN — per-scene MP3 introduce leading/trailing, y FFmpeg concat añade más gaps
  - Recomendación: Single narration MP3 elimina ambos problemas (0 concat gaps, 0 leading/trailing entre escenas)

## Fase 1 — Diseño y documentación ✅
- [x] Crear proposal.md
- [x] Crear design.md con sceneTimings por SentenceBoundary, pausas clasificadas, cobertura de audio
- [x] Crear tasks.md con 9 fases
- [x] Crear specs/continuous-audio.md (SentenceBoundary sequence matching, no first/last word)
- [x] Crear specs/subtitle-timing.md
- [x] Crear specs/audio-validation.md (diferenciar pausas naturales de errores, cobertura)
- [x] Crear specs/modern-asset-blocking.md (Pexels no auto-válido, coherencia con beat concreto)
- [x] Crear bitácora de sesión

## Fase 2 — Implementación: audio continuo (single MP3) ✅
- [x] Refactor `generate_audio.py`: modo `--continuous` que genera un solo MP3
- [x] Construir texto completo concatenando voiceovers con puntuación natural
- [x] Construir `narration_units[]` por oración/escena
- [x] Extraer SentenceBoundary del audio continuo
- [x] Calcular sceneTimings por secuencia de SentenceBoundary con validación de similitud textual
- [x] Si SentenceBoundary count ≠ narration_units count → timingConfidence=low, REVIEW_REQUIRED
- [x] Guardar `audio.continuous`, `audio.sceneTimings[]`, `audio.narrationUnits[]` en metadata

## Fase 3 — Implementación: subtítulos desde audio real ✅
- [x] Los cues de subtítulos usan timings ABSOLUTOS del audio continuo
- [x] Cada cue incluye `sceneNumber` al que pertenece
- [x] Aplicar reglas: cue min 0.7s, max 2.5s, sin cues vacíos
- [x] Dividir por puntuación y grupos semánticos
- [x] Timing derivado de WordBoundary → SentenceBoundary → estimación
- [x] Verificar que texto concatenado de cues coincide con narración normalizada

## Fase 4 — Implementación: sincronización de timeline ✅
- [x] `build_render_timeline()` usa sceneTimings para start/end absolutos
- [x] No usar `targetDurationSec` como fuente primaria de duración
- [x] Cada cambio visual en límite de escena o beat narrativo real
- [x] ASS subtitles con timings absolutos
- [x] `render_job.py`: soporte para single audio source (narration.mp3)

## Fase 5 — Implementación: validación de pausas ✅
- [x] Implementar `detect_silence_ranges()` (FFmpeg silencedetect)
- [x] Implementar `classify_silence()`: natural vs chapter_break vs unexpected
- [x] Tolerancias ajustadas: chapter_break detectado con |start - endSec| < 1.2s
- [x] Intra-scene silences de EdgeTTS (~1.1s post-punctuation) clasificados como natural con tolerancia 0.6s
- [x] Guardar `audioValidation` en metadata con clasificación por silencio

## Fase 6 — Implementación: validación de cobertura de audio ✅
- [x] Suma de sceneTimings cubre ≥98% del audio útil (100% con sceneTimings que incluyen chapter_break gaps)
- [x] No hay solapes entre escenas
- [x] Cada cue pertenece a una sola escena
- [x] Texto concatenado de cues coincide con narración normalizada
- [x] Integrar en render_job.py como validación post-render

## Fase 7 — Implementación: bloqueo de assets modernos fuera de contexto ✅
- [x] Añadir regla `check_modern_asset_context()` en asset_validation.py
- [x] Detectar provider pexels, assetType broll/atmospheric, queries modernas
- [x] Pexels NO es auto-válido en consequence_or_legacy — necesita keyword de presente
- [x] Si el asset es calle/edificio moderno, "Estambul actual" debe estar en el texto
- [x] BLOCKED si no cumple condiciones; no modificar editorialRole

## Fase 8 — Prueba controlada ✅
- [x] Crear job de prueba inline con 3 voiceovers reales
- [x] Generar single MP3 con edge-tts es-ES-AlvaroNeural
- [x] Extraer SentenceBoundary y WordBoundary del audio real
- [x] sceneTimings por SentenceBoundary sequence matching
- [x] Cues de subtítulos con timings absolutos
- [x] Renderizar con FFmpeg
- [x] Validar: sceneTimings 99.2% cobertura, delta 0.0s, 0 black/freeze frames
- [x] Publicar métricas: duración 18.24s, FFmpeg exit 0, status RENDERED

## Fase 9 — Render final de Constantinopla ✅
- [x] Generar audio single MP3 (narration.mp3 desde edge-tts, recortado a narration_trimmed.mp3)
- [x] Recortar silencios chapter_break (de ~1.1s a 0.35s) con trim_narration_silences.py
- [x] Remapear cues proporcionalmente al audio recortado
- [x] Ajustar sceneTimings al audio recortado (27.098s total)
- [x] Reemplazar todos los assets Pexels por Wikimedia Commons (6 assets reemplazados)
- [x] Renderizar con validaciones activas
- [x] Validaciones: asset PASSED, coverage 100%, audio technical PASS, 0 black/freeze
- [x] Estado RENDERED
- [ ] Revisión visual humana del MP4 final
- [ ] Cerrar OpenSpec tras revisión
