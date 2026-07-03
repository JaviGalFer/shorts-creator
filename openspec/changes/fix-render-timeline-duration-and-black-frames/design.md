# Design: Fix Render Timeline

## 1. Root Cause: zoompan frame multiplication

zoompan(https://ffmpeg.org/ffmpeg-filters.html#zoompan) genera `d` frames de salida **por cada frame de entrada**. Con `-loop 1 -t 5 -i img` se generan 125 frames de entrada. Si `d=125`, zoompan produce 125 * 125 = 15.625 frames (625s).

### Fix

Aplicar `trim=end_frame=1` antes de zoompan para asegurar exactamente 1 frame de entrada:

```
input → trim=end_frame=1 → zoompan=z=...:d=N → output (N frames)
```

Para non-zoompan filters, usar `-loop 1` (sin `-t`) y la duración se controla por `trim=end_frame=N` o por zoompan.

**Nuevo enfoque**: Todos los inputs visuales usan `-loop 1` (sin `-t`). La duración se controla exclusivamente con `trim=duration=X` al final del filter chain.

Esto simplifica: un solo `-loop 1` por input, duración controlada por el último `trim` en el filter.

## 2. Preflight Validation

Antes de construir el filter graph, validar:

- Cada renderTimeline entry:
  - `startSec >= 0`
  - `endSec > startSec`
  - `durationSec > 0.5` (salvo justificación)
  - `durationSec <= 8.0` (salvo CTA)
  - `assetPath` apunta a archivo existente
- Suma de duraciones ≈ duración total de audio ± 1s
- Diferencia máxima entre timeline total y expected: 1.0s

## 3. Post-Render Validation

Tras render, ejecutar ffprobe:

- `actualVideoDurationSec` del MP4
- `actualAudioDurationSec` del stream de audio
- `durationDeltaSec = actualVideoDurationSec - expectedDurationSec`
- Fallo si `durationDeltaSec > 2.0` o `durationDeltaSec < -2.0`
- Fallo si `actualVideoDurationSec > 120` para shorts configurados < 60s

## 4. Black Frame Detection

- Extraer frames en 5 puntos temporales (0%, 25%, 50%, 75%, 95%)
- Calcular luminancia media
- Warning si >3 frames con luminancia media < 25
- Guardar screenshots en `data/videos/{jobId}/validation/`

## 5. Freeze Detection

- Extraer frames cada 1s
- Calcular diferencia media de píxeles entre frame i y frame i+1
- Warning si diferencia < 0.01 por más de 5 frames consecutivos

## 6. Pipeline de prueba

Antes de render completo, ejecutar job de prueba:
- 2 escenas
- 3 segmentos visuales
- 1 zoompan
- 1 pan
- 1 static
- 1 fade
- 8-12s total
