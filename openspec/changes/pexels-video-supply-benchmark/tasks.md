# Tasks: pexels-video-supply-benchmark

**Status: READY_FOR_HUMAN_REVIEW** — investigación benchmark-first concluida,
sin integración de runtime. Pendiente de revisión humana con los contact sheets
antes de decidir (NO CLOSED).

## Datos (NO tocados)

- [x] `main` == `de570fa`, working tree limpio, baseline `1526 passed`
- [x] Rama base: `change/pexels-video-supply-benchmark` (creada, limpia)

### Datasets reutilizados SIN relabel

- [x] `tests/fixtures/asset_visual_fidelity/labels.json`: 38 canónicos
- [x] `tests/fixtures/asset_visual_fidelity/holdout_labels.json`: 20 development
- [x] Total lógico 58 rows → 56 queryUsed únicas tras dedup exacto

## Tasks

- [x] Preflight: branch main + HEAD `de570fa` + working tree limpio + baseline ok
- [x] Resolver `PEXELS_API_KEY` desde entorno/`.env` sin imprimirla ni persistirla
- [x] Harness `tools/pexels_video_supply_benchmark.py` (evaluation-only,
      stdlib urllib, import-safe/offline, lazy network/ML)
- [x] Parsing API, dedup queries, rate-limit metadata, selección MP4 portrait,
      request cap, diagnóstico landscape (ver tests)
- [x] Tests offline `tests/test_pexels_video_supply_benchmark.py` (30 passed,
      sin llamadas reales)
- [x] Búsqueda principal portrait sobre las 56 queries → cobertura 100 %
- [x] Diagnóstico landscape para queries sin supply → 0 requests (todas OK)
- [x] 12 clips rank#1 descargados (reutilizando `rawResults`, sin requests extra)
- [x] Contact sheets PNG vía Docker ffmpeg/ffprobe + PIL
      (01 temporal + 02 top3)
- [x] Comparación preliminar cobertura/supply; NO se afirma `PEXELS_BETTER`
- [x] OpenSpec `proposal/design/tasks/results` en `READY_FOR_HUMAN_REVIEW`
- [x] Suite `python3 -m pytest -q tests` + `git diff --check`
- [ ] (externo) Revisión humana de los contact sheets → decisión y cierre

## Notas de ejecución

- Primer intento de requests daba `403 Forbidden` por falta de User-Agent;
  añadido `User-Agent` → OK (la primera pasada de 56 no consumió cuota de
  búsqueda; rate-limit real final `remaining=24944/25000`).
- Contact sheets requieren Docker `linuxserver/ffmpeg:latest` (host `ffmpeg` y
  `ffprobe` ausentes); ffprobe se invoca con `--entrypoint ffprobe` y la
  entrada ffmpeg por defecto NO se prefija.
- No merge, no push, no reindex.
