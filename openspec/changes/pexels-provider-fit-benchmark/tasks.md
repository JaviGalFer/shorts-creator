# Tasks: pexels-provider-fit-benchmark

**Status: IN_PROGRESS** — investigación benchmark-first (research-only). NO
integra runtime. Estado de evidencia: **READY_FOR_HUMAN_REVIEW** (pendiente la
revisión humana externa de los 3 contact sheets).

## Base / precondiciones

- [x] Base: `main` = `cf391c5` (cierre/merge de `pexels-visual-supply-benchmark`),
      working tree limpio, suite previa `1586 passed`
- [x] Rama `change/pexels-provider-fit-benchmark` creada desde `main`
- [x] Evidencia RAW presente: `photo-supply-benchmark.json` y
      `supply-benchmark.json` (NO se reconstruye el benchmark anterior)

## Limpieza documental mínima (change previo ya CLOSED)

- [x] `openspec/changes/pexels-visual-supply-benchmark/tasks.md`:
      eliminado el resto stale `Estado final: READY_FOR_HUMAN_REVIEW` y
      corregida la nota `No merge, no push, no reindex` (el merge no-ff ya
      ocurrió; siguen ciertos `sin push` y `sin reindex`). Métricas históricas
      NO tocadas.

## Resolución de rows / contrato persistido

- [x] 58/58 rows resueltas por `(jobId, sceneNumber, segmentIndex)` desde
      `data/videos/<jobId>/metadata.json` + fixtures: queryUsed, topic,
      provider, humanLabel (contexto histórico), assetPreference, visualIntent,
      persistedSearchQuery
- [x] `missingRows=0`; 4 rows con `searchQueryMismatch` (fitting regenerate el
      plan tras fetchear el asset) registrados explícitamente
- [x] Distribuciones reales persistidas en `metadata-report.json` (assetPreference,
      intent, intent×assetPreference, queryForm)

## Política provisional de provider-fit

- [x] `classify_provider_fit` (pura): explicit-form precedence
      (diagram/infographic/illustration/painting → `INELIGIBLE_EXACT_FORM` en
      Photos y Video), `photograph` → Photos `ELIGIBLE` / Video
      `ELIGIBLE_CANDIDATE`; resto/ausente → `UNDECIDED`
- [x] No se convierte `diagram` en B-roll ni se inventa política para otros
      assetPreference no observados
- [x] Verdicts persistidos en `policy-report.json`

## Adaptación de query

- [x] `adapt_photograph_query` (pura): elimina solo photograph/photo/photography,
      preserva sujeto/entidad/variante/acción, normaliza espacios, persiste
      rawQuery/adaptedQuery/removedTokens/changed/policyVersion
- [x] 39 adaptaciones planificadas sobre las queries photograph-form (dedup
      exacto, sin colisiones, ninguna coincidence con una queryUsed RAW)

## Requests nuevas (Pexels Video adaptadas)

- [x] 39/40 requests usadas (cap 40), `orientation=portrait`, `locale=en-US`,
      `per_page=15`, User-Agent explícito, clave nunca persistida
- [x] Rate limit final: `remaining=24849/25000`
- [x] Persistido `adapted-video-supply.json`

## Comparación RAW vs ADAPTED y overlap

- [x] 39 comparaciones por query (total_results, top15/top3, portrait 720/1080,
      overlap, rank changes, IDs nuevos)
- [x] Overlap exact-ID top15: Photos RAW (56), Video RAW (56), Video RAW
      fotográfico (39, base justa), Video ADAPTADO (39)
- [x] Within-job/topic repeated IDs por set
- [x] Persistido `raw-vs-adapted.json`

## Review sample y evidencia visual

- [x] Sample determinista de 10 queries (5 mandatory + 5 por diversidad de
      topic) persistida en `review-sample.json`
- [x] 20 clips (RAW+ADAPTED rank#1; RAW reusa cache) persistidos en
      `review-clips.json`
- [x] `01-provider-fit-photo-current-top3.png`
- [x] `02-provider-fit-video-raw-vs-adapted-top3.png`
- [x] `03-provider-fit-video-temporal.png` (frames 20/50/80 %, aspect ratio
      preservado, sin crop, sin solapamiento)

## Tests

- [x] `tests/test_pexels_provider_fit_benchmark.py` (39 passed): resolución,
      missing, política, explicit-form precedence, photograph eligibility,
      adaptación exacta, preservación de términos semánticos, adapted==raw ⇒ no
      request, dedup, hard cap 40, no key leak, reuse RAW evidence, overlap/
      Jaccard exact IDs, review sample determinista, import-safe, no network,
      layout helper
- [x] Suite de las 3 suites de Pexels en verde
- [x] Suite completa `python3 -m pytest -q tests` en verde
- [x] `git diff --check` limpio

## Pendiente humano

- [ ] Revisión humana externa de los 3 contact sheets (decisiones por query:
      Photos CURRENT/PEXELS/TIE; Video RAW/ADAPTED/TIE/BOTH_UNUSABLE; rank#1 útil
      o top3 mejor; si assetPreference=photograph fue suficiente para decidir
      fit; si algún intent requiere regla adicional). NO se producen esos labels
      desde OpenCode.

## Commit

- [x] `git commit -m "test(evaluation): benchmark Pexels provider fit"`
- [ ] Cierre documental en OpenSpec/agent-context (tras revisión humana)

## Notas

- El merge no-ff del change previo ya ocurrió. Siguen siendo `sin push` y
  `sin reindex`.
- Contact sheets requieren Docker `linuxserver/ffmpeg:latest` (host ffmpeg/
  ffprobe ausentes); entrada ffmpeg por defecto y ffprobe vía `--entrypoint`.
- No se afirman `PROVIDER_FIT_VALIDATED`, `ADAPTED_BETTER` ni "Pexels por
  defecto".