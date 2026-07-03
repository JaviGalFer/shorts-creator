# Proposal: Continuous Audio and Subtitle Timing

## Problema

El vídeo de "La caída de Constantinopla" tiene pausas artificiales entre escenas porque cada escena genera su propio MP3 mediante edge-tts. Al concatenar en FFmpeg, los silencios naturales de inicio/fin de cada archivo se acumulan, rompiendo la fluidez narrativa.

Los subtítulos se calculan sobre duración estimada (`targetDurationSec`) cuando no hay WordBoundary, produciendo cues desincronizados con el audio real.

## Solución propuesta

**Estrategia preferida**: Generar UNA sola pista de narración para todo el vídeo, concatenando todos los voiceovers con puntuación natural. Esto elimina las pausas entre escenas porque edge-tts produce una locución continua.

**Fallback**: Si edge-tts no soporta texto largo (>3000 chars), recortar silencios iniciales/finales de cada MP3 por escena y unir con pausas editoriales controladas (0.10–0.35s máximo).

## Impacto

- `generate_audio.py`: Refactor mayor — nuevo modo "continuous" vs per-scene
- `prepare_job.py`: RenderTimeline basado en timings reales de audio, no `targetDurationSec`
- Nuevo módulo: validación de pausas (`audio_silence_detector.py` o integrado en asset_validation)
- `render_job.py`: Soporte para single audio source
- Metadata: Nuevo campo `audio.sceneTimings` con mapeo escena→rango temporal

## No entra en este cambio

- Sourcing visual, providers, maps, motion types
- Contact sheets, comparativas before/after de assets
- Cierre del OpenSpec anterior (`fail-closed-assets-and-render-quality`)

## Criterios de éxito

1. Una sola pista de narración O silencios recortados <0.45s
2. Subtítulos que reproducen exactamente el texto narrado
3. No hay pausas inesperadas >0.45s
4. Assets modernos solo si beat explícito de legado presente
5. Test controlado de 12–15s pasa antes de regenerar Constantinopla
