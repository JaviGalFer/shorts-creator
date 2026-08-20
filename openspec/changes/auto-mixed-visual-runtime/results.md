# Results: auto-mixed-visual-runtime

## Status

**COMPLETED / VERIFIED / CLOSED** — pending authorized merge.

## Product Result

AUTO y MIXED ahora usan la preferencia editorial real del LLM
(`mediaPreference`) por segmento, con routing multi-kind y fallback compatible,
sin debilitar las constraints duras IMAGES_ONLY/VIDEOS_ONLY.

- El prompt V2 emite `mediaPreference` explícito (VIDEO_PREFERRED /
  IMAGE_PREFERRED / EITHER) y una guardia estricta `MEDIA_PREFERENCE_MISSING`
  bajo AUTO/MIXED impide generaciones sin decisión editorial.
- El router construye niveles de medio (preferred → fallback compatible) y
  reconcilia `mediaDecision` con los media kinds que realmente sobreviven a
  constraints/source policy (un failback de runtime NO se notifica cuando el
  medio primario nunca fue permitido por la source policy).
- `mediaDecision` se persiste por segmento (router → executor → bridge →
  `assets[].segments[]`); `mediaFallback`/`PREFERRED_MEDIA_EXHAUSTED` distinguen
  fallback real de runtime de la degradación de estrategia.
- MIXED añade diversity best-effort EITHER-only con contadores de assets
  seleccionados (selected-only), sin cuotas ni optimizer global.
- Queries para VIDEO son medium-neutrales (`medium_neutral_query`): el
  `queryUsed` efectivo y la búsqueda usan la misma intención.

## Suite

- Baseline `main` `f401baa`: `1809 passed`.
- Slice 1 (commit `ae3a3d6`): `1843 passed, 0 failed`.
- Final suite: `1849 passed, 0 failed`; `git diff --check` limpio.

## Mixed local render smoke (offline)

Job `mixed-local-smoke` en `/tmp` con audio sintético y dóker ffmpeg local:

- Timeline: scene 1 IMAGE (0.0–6.3) → scene 2 VIDEO (6.3–12.7) → scene 3 IMAGE
  (12.7–19.1). Sin gaps; orden correcto.
- IMAGE usa rama IMAGE (scale/Ken Burns); VIDEO usa rama VIDEO (trim).
- Output `video.mp4`: h264, **1080x1920**, 25 fps, **19.08s** (esperado 19.05).
- Un único stream de audio (narración aac); el vídeo de origen NO aporta audio.
- Asset validation 3/3 PASS; preflight PASS; `prepare → render → validate`
  **PASS** (0 errores).
- Manifest `visualType` por escena: image / video / image. `resolvedConfig.visuals.visualMode = MIXED`.

## Real AUTO E2E

Job `cmo-2026-08-20-152730` — topic "Cómo funciona un volcán y qué ocurre
durante una erupción", 30s, `wikimedia_commons,pixabay,pexels`, `--visual-mode
auto`, ElevenLabs.

- Status: **ASSETS_READY → AUDIO_READY → SUBTITLES_READY → RENDERED_WITH_WARNINGS → VALIDATED**. `validationStatus=PASS`. MP4 ~29.4s (dentro de 27–33).
- 5 scenes / 9 segments, **9/9 resolved** (`_visualAssetBridgeV2.summary`).
- Media preferences: todos explícitos (EITHER/IMAGE_PREFERRED/VIDEO_PREFERRED) — **sin default histórico IMAGE_PREFERRED**.
- `mediaDecision.resolvedKind == mediaKind` en todos los segmentos → **sin fallback espurio** (`mediaFallback=false` en todos).
- Distribution resolved: **IMAGE 8 / VIDEO 1** (VIDEO en scene 3 seg1: `VIDEO_PREFERRED` → `pexels.video.stock`).
- AUTO no necesita ambos medios para pasar; aquí produjo ambos de forma editorial.

## Real MIXED runtime run

Job `por-2026-08-20-153502` — topic "Por qué el cielo es azul y por qué se pone
rojo al atardecer", 30s, mismos providers, `--visual-mode mixed`, ElevenLabs.

- Status: **ASSETS_PARTIAL** (9/10 resolved; 1 ilustración pixabay sin cobertura supply).
- Mezcla editorial observada: `VIDEO_PREFERRED → pexels.video.stock` (movimiento/
  atardecer) y `IMAGE_PREFERRED → wikimedia/pixabay` (diagrama/ilustración).
- `mediaDecision.resolvedKind == mediaKind` en todos los resueltos; `mediaFallback=false`.
- Distribution resolved: **IMAGE 5 / VIDEO 4** → ambos medios, mezcla editorial best-effort.
- **No** se sobreescribieron preferencias fuertes, no se degradaron diagramas a B-roll, no se impuso cuota.

Otras ejecuciones MIXED documentadas (no media-runtime):
- `cmo-2026-08-20-153101` (rayos): bloqueado en audio por `DURATION_FITTING_EXHAUSTED` (4 escenas/71 palabras, proyección 33.17s) — convergencia del fitting de duración, no del runtime de medios.
- `cmo-2026-08-20-153259` (pulpos): `ASSETS_PARTIAL` pero con mezcla editorial 4 VIDEO + 2 IMAGE; 2 ilustraciones/diagramas sin cobertura supply.

## Fallbacks observados

Ningún `PREFERRED_MEDIA_EXHAUSTED` se disparó en los E2E: tras la
reconciliación de la estrategia con los media kinds supervivientes, cada segmento
resolvió en su `resolvedKind` (sin fallback cross-media espurio). El fallback
runtime queda cubierto por tests mockeados (video agotado → IMAGE resuelve con
`mediaFallback=true` + reason) y por la semántica de reconciliation.

## No regresión de modos duros

Cubierto por la suite completa: IMAGES_ONLY nunca produce fallback VIDEO y
VIDEOS_ONLY nunca produce fallback IMAGE (router multi-kind de un solo nivel);
`exact forms` nunca reciben VIDEO (`UNSUPPORTED` excluido); VIDEOS_ONLY render
(stream_loop/trim) sin cambios.

## Limitaciones aceptadas (fuera de alcance)

- Asset supply: algunos segmentos de ilustración/diagrama quedan sin resolver
  (`ASSETS_PARTIAL`) según cobertura de providers — no es un bug del runtime de
  medios.
- Script quality / watchability.
- Provider-specific query adaptation.
- Video semantic vision (OpenCLIP/VLM sobre VIDEO).
- Candidate reranking.
- Generated / manual media.
- Web UI.