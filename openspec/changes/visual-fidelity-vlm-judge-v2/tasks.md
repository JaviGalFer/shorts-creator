# Tasks: visual-fidelity-vlm-judge-v2

**Status: COMPLETED / VERIFIED / CLOSED** — investigación benchmark-first, sin
integración de runtime. Resultado: **`VLM_JUDGE_V2_NOT_USEFUL`**; no se integra,
no se hace holdout nuevo. `visual-fidelity-runtime` sigue OFF por defecto;
OpenCLIP `0.2296` sigue siendo el pixel gate vigente cuando está activado.

## Datos (NO tocados)

- [x] `main` == `1ee283d`, working tree limpio, baseline `1506 passed`
- [x] Rama base: `change/visual-fidelity-vlm-judge-v2` (creada, limpia)

### Datasets reutilizados SIN relabel

- [x] `tests/fixtures/asset_visual_fidelity/labels.json`: 38 canónicos
  (16 CR / 14 CU / 8 FP ⇒ 30 ACCEPT / 8 REJECT)
- [x] `tests/fixtures/asset_visual_fidelity/holdout_labels.json`: 20 fresh
  (3 CR / 10 CU / 7 FP ⇒ 13 ACCEPT / 7 REJECT)
- Nota: los 20 SON development evidence; NO se afirma generalización sobre ellos.

## Tasks

- [x] Crear harness `tools/visual_fidelity_vlm_judge_v2.py` (evaluation-only,
  reutilizando la infraestructura del benchmark API de la Slice 3A)
- [x] Contracto judge V2, sin humanLabel/scores/expected (tests: 20 passed)
- [x] `assetPreference` desde el contrato persistido del segmento si existe
- [x] Preflight de tokens + hard cap `$0.10`; PARAR si proyección > cap
      (READY; proyección total `$0.030 613` << cap; coste real `$0.013 051`)
- [x] Ejecutar canonical 38; reportar métricas operativas (UNCERTAIN ⇒ ACCEPT)
      → **21/30 retained + 8/8 badRejected** (FA 0, FR 9), 0 UNCERTAIN
- [x] Ejecutar development 20; reportar 13/7, los 7 bad assets y los 4 buenos
      de BLIP → **4/13 usableRetained + 5/7 badRejected** (FA 2, FR 9); los
      4 buenos de BLIP: VLM conserva 1/4 (data center 5.2), rechaza 3/4
- [x] Casos críticos: 4/5 resueltos (data-center vs blockchain art, castillo
      final vs construcción, castillo vs planos, castillo vs construction-time
      diagram); falla **motor 2T vs 4T** (ACCEPT, mismo punto ciego que
      OpenCLIP)
- [x] Comparación OpenCLIP / BLIP / VLM V2 (ver `results.md`; VLM V2 es el PEOR
      en retención de buenos y el MEJOR en rechazo de bad assets)
- [x] Decisión → **`VLM_JUDGE_V2_NOT_USEFUL`** (falla canonical 21/30<24/30 y
      development 4/13<11/13). No integración, sin holdout nuevo.
- [x] Tests unitarios del harness → `tests/test_visual_fidelity_vlm_judge_v2.py`
      (20 passed)
- [x] Suite `python3 -m pytest -q tests` + `git diff --check`
      → **1526 passed, 0 failed**; diff limpio
- [x] Commit de investigación; NO merge, NO push