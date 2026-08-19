# Tasks: pexels-visual-supply-benchmark

**Status: COMPLETED / VERIFIED / CLOSED** — investigación benchmark-first
(Pexels Video + Pexels Photos) cerrada tras la **revisión humana externa** de
los 3 contact sheets. Sin integración de runtime. Decisión:
**`PEXELS_CONDITIONAL_PROVIDER_PROMISING`**.


## Datos (NO tocados)

- [x] Base real del benchmark: `main` == `de570fa`, working tree limpio,
      suite previa `1556 passed`
- [x] Rama original `change/pexels-video-supply-benchmark` @ `ead4cb2`
      renombrada a `change/pexels-visual-supply-benchmark`
- [x] OpenSpec renombrado `openspec/changes/pexels-visual-supply-benchmark`
- [x] Datasets reutilizados SIN relabel (38 canonical + 20 development = 58
      rows → 56 queryUsed únicas)

## Renombre / limpieza

- [x] `git branch -m change/pexels-visual-supply-benchmark`
- [x] `git mv openspec/changes/pexels-video-supply-benchmark openspec/changes/pexels-visual-supply-benchmark`
- [x] Actualizar referencias documentales al nuevo nombre (agent-context,
      current-state, OpenSpec)
- [x] Corregir estado stale de la base: **`de570fa`** era la base real al abrir
      (no `321da8a`); la historia real de commits no se altera
- [x] NO se borró evidencia existente (vídeo)

## Corrección contact sheet temporal de VÍDEO

- [x] Bug de layout: los frames portrait 720x1280 redimensionados a width=270
      quedan ~270x480, pero la fila reservaba ~270px de alto → solapamiento
- [x] Corregido: `compute`-style layout con `_load_scaled` pre-computado que
      reserva la altura real por fila (label_h + row_gap + frame_h), preserva
      aspect ratio, sin crop, sin solapamiento, labels con wrap
- [x] Regenerado usando clips/frames YA existentes (sin requests Pexels, sin
      redescarga) → `01-pexels-video-temporal-contact-sheet.png` (866×6944)
- [x] `02-pexels-top3-search-results.png` se mantiene

## Pexels Photos benchmark

- [x] Harness `tools/pexels_photo_supply_benchmark.py` (evaluation-only,
      stdlib urllib, import-safe/offline, User-Agent explícito, key no leak)
- [x] Búsqueda principal portrait sobre las 56 queries (requests 56/70,
      main=56 diag=0) → cobertura 100 %
- [x] Diagnóstico landscape → 0 requests (todas PORTRAIT_SUPPLY_OK)
- [x] Persistencia por foto: id, WxH, url, photographer(+url/id), avg_color,
      alt y 8 variantes `src` (original..tiny). Sin secrets.
- [x] Métricas de supply Photos (por query + agregadas + clasificación)
- [x] 12 imágenes rank#1 originales descargadas (reutilizando rawResults,
      sin nuevas búsquedas) + previews rank 2/3 (large2x)
- [x] `03-pexels-photo-vs-current-contact-sheet.png` (CURRENT vs PEXELS #1/#2/#3)

## Comparación directa

- [x] CURRENT usa `assetPath` del fixture (12/12 existen)
- [x] PEXELS usa ranking raw (pid, WxH original, photographer)
- [x] Layout: aspect ratio preservado, sin crop, sin solapamiento, labels legibles

## Sin juicio semántico

- [x] No se generan CLEARLY_RELEVANT / COARSE_BUT_USABLE / FALSE_POSITIVE
- [x] No se afirma `PEXELS_PHOTOS_BETTER` (ni `PEXELS_BETTER`)
- [x] Estado final del change: COMPLETED / VERIFIED / CLOSED (la revisión
      humana externa se completó y se registró en `results.md`; los píxeles
      quedaron resueltos como evidencia cualitativa)

## Tests

- [x] `tests/test_pexels_video_supply_benchmark.py` (30 passed)
- [x] `tests/test_pexels_photo_supply_benchmark.py` (30 passed; parsing Photo,
      src variants, dedup 56, orientation/resolution helpers, supply metrics,
      rate-limit, request cap, diagnostic fallback, key never persisted,
      User-Agent, import-safe, no network, fixtures unchanged, layout helper)
- [x] Suite completa `python3 -m pytest -q tests` + `git diff --check`
- [x] Sin llamadas reales en pytest

## Commit

- [x] `git commit -m "test(evaluation): extend Pexels visual supply benchmark"`
- [x] Revisión humana externa de los 3 contact sheets completada y registrada
      en `results.md` (evidencia cualitativa)
- [x] Decisión → **`PEXELS_CONDITIONAL_PROVIDER_PROMISING`** (NO
      `PEXELS_BETTER` / `PEXELS_PHOTOS_BETTER`)
- [x] Dirección siguiente `pexels-provider-fit-benchmark` registrada (NO
      implementada)
- [x] Paths de evidencia corregidos (vídeo vs photos; sin mover evidencia
      git-ignored)
- [x] Estado del change → **COMPLETED / VERIFIED / CLOSED**
- [x] Cierre documental: `git commit -m "docs(evaluation): close Pexels visual supply benchmark"`
- [x] Merge no-ff a `main`; suite en main `1586 passed, 0 failed`. Sin push.

## Notas

- Se resuelve la clave con la política existente (env → `.env`); nunca se
  imprime ni persiste.
- Contact sheets requieren Docker `linuxserver/ffmpeg:latest` (host ffmpeg/
  ffprobe ausentes); entrada ffmpeg por defecto y ffprobe vía `--entrypoint`.
- El merge no-ff a `main` ya ocurrió (commit `cf391c5`). Siguen siendo
  ciertos `sin push` y `sin reindex`.
