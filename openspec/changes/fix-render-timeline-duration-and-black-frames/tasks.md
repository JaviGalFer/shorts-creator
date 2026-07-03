# Tasks: Fix Render Timeline Duration and Black Frames

## Fase 1 — Diagnóstico
- [x] Confirmar zoompan frame multiplication: d=N * input_frames = N^2
- [x] Confirmar `-loop 1 -t X` genera X*fps frames de entrada
- [x] Confirmar concat produce duración incorrecta por frames extra

## Fase 2 — Fix render_job.py
- [x] Eliminar `-loop 1 -t X`, usar `-loop 1` sin -t para inputs visuales
- [x] Zoompan: aplicar `trim=end_frame=1` antes para evitar multiplicación
- [x] Zoompan: d = round(durationSec * fps) frames exactos
- [x] Non-zoompan: `trim=duration=X` para control exacto
- [x] Audio: `atrim=duration=X` para sincronizar con video
- [x] Todas las salidas: `setsar=1,format=yuv420p` para SAR consistente
- [x] Documentar fórmula de duración

## Fase 3 — Preflight validation
- [x] Validar renderTimeline entries (startSec, endSec, durationSec, assetPath)
- [x] Validar suma duraciones ≈ audio total
- [x] Fallar con mensaje claro si hay errores

## Fase 4 — Post-render validation
- [x] Extraer duración real con ffprobe/ffmpeg
- [x] Comparar expected vs actual duration
- [x] Extraer frames de validación (0%, 25%, 50%, 75%, 95%)
- [x] Detectar black frames por luminancia media
- [x] Detectar freeze por diferencia entre frames
- [x] Guardar métricas en metadata.json

## Fase 5 — Pipeline de prueba reducido
- [x] Crear script que genera job de prueba de 8-12s
- [x] Ejecutar pipeline completo (script → audio → images → prepare → render)
- [x] Validar duración, black frames, freeze
- [x] Iterar hasta que pase validaciones

## Fase 6 — Render completo
- [x] Ejecutar render completo "La caída de Constantinopla"
- [x] Validar con métricas automáticas
- [x] Tabla de validación con valores ffprobe reales

## Fase 7 — Documentación
- [ ] Actualizar bitácora de sesión
- [ ] Actualizar docs/runbooks/render-troubleshooting.md
- [ ] Cerrar OpenSpec solo con validación automática OK
