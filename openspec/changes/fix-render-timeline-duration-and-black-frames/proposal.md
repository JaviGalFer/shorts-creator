# Proposal: Fix Render Timeline Duration and Black Frames

## Problema

El render final del cambio `improve-narrative-rhythm-and-subtitles` produce un MP4 de 27:35 minutos en vez de ~36 segundos. Causas identificadas:

1. **zoompan multiplica frames**: `d=N` genera N frames *por cada input frame*. Con `-loop 1 -t 5` generando 125 frames y `d=125`, el output es 15.625 frames = 625s por segmento.
2. **Sin preflight validation**: No se validan duraciones, existencias de assets, ni consistencia antes de renderizar.
3. **Sin post-render validation**: No se verifica duración real del output, black frames ni freeze.
4. **Audio corrompido**: 3 kb/s indica que el concat de audio no funciona correctamente.
5. **Pantallas negras**: Por duración incorrecta, algunos segmentos quedan vacíos.

## Alcance

1. Corregir zoompan para que no multiplique frames.
2. Añadir preflight validation (assets, duraciones, consistencia).
3. Añadir post-render validation con ffprobe.
4. Pipeline de prueba reducido (8-12s) antes de render completo.
5. Render completo de "La caída de Constantinopla" con validación automática.
