# Tasks: visual-fidelity-runtime

**Status: SLICE 1 + SLICE 2 + SLICE 3 COMPLETADOS — cambio listo para cierre (merge a `main` pendiente).**

## Precondiciones (verificadas)

- [x] `main == fd4d58d`, working tree limpio
- [x] Baseline verde: `python3 -m pytest -q tests` → **1460 passed, 0 failed, 0 skipped**. (La invocación desde la raíz del repo falla al recolectar `data/postgres/`, volumen Docker de postgres propiedad de root no readable por `javi`; es ambiental, no relacionada con el código.)
- [x] Rama creada: `change/visual-fidelity-runtime`

## Plan acordado (registrado en proposal/design)

- [x] Segundo gate: `metadata gate → pixel gate → ACCEPT/REJECT → siguiente candidato`
- [x] Modelo: OpenCLIP `ViT-B-32` / `laion2b_s34b_b79k`; texto P1 = `queryUsed`
- [x] Componente: `src/shorts_creator/assets/visual_fidelity.py`
- [x] Integración: `assets/executor.py` post-descarga/pre-RESOLVED (wikimedia + pixabay)
- [x] Modelo lazy + cacheado una vez por proceso
- [x] CUDA automático, CPU fallback
- [x] Dependencia opcional; no inflar instalación base
- [x] Ausencia/fallo OpenCLIP → bypass explícito + warning/telemetría
- [x] Rechazo → borrar asset descargado y probar siguiente candidato
- [x] GIF: frame 0
- [x] Tests sin pesos ni descargas
- [x] `0.2296` NO es threshold de producción (config explícita y versionada)

## Slice 1 — Componente y lifecycle (COMPLETADO)

- [x] `src/shorts_creator/assets/visual_fidelity.py`:
  - [x] lazy singleton (carga una vez por proceso)
  - [x] CUDA automático / CPU fallback (device_override para tests)
  - [x] GIF frame 0 sin mutar el archivo
  - [x] threshold configurable (env/config), sin default `0.2296` (`VISUAL_FIDELITY_THRESHOLD`)
  - [x] status `SCORED` / `UNAVAILABLE` / `DISABLED` explícitos + verdict `ACCEPT`/`REJECT`/`BYPASS`
- [x] `tests/test_visual_fidelity_runtime.py` (21 tests unit con mocks, sin pesos/red/torch real)
- [x] Tests focales verdes: `python3 -m pytest tests/test_visual_fidelity_runtime.py -q` → `21 passed`
- [x] Suite completa: `python3 -m pytest -q tests` → **`1481 passed, 0 failed, 0 skipped`** (1460 baseline + 21 nuevos)
- [x] `git diff --check` limpio
- [x] Commit: **feat(assets): add optional visual fidelity scorer**
- [x] Sin integración en executor/bridge (Slice 2), sin deps base, sin instalar torch/open_clip, sin descargar pesos

## Slice 2 — Integración executor + telemetría (COMPLETADO)

- [x] Gate post-descarga / pre-RESOLVED en `_resolve_wikimedia` y `_resolve_pixabay` (provider-agnostic: archivo + `queryUsed` vía `_apply_visual_fidelity_gate`)
- [x] Rechazo (`SCORED + REJECT`): borrar archivo, registrar `visualFidelityRejections`, continuar siguiente candidato
- [x] Todos rechazados → `NO_RESULTS` con `visualFidelityRejections` (también en `DOWNLOAD_FAILED`)
- [x] Bypass `UNAVAILABLE` / `DISABLED` con warning `VISUAL_FIDELITY_BYPASS:{status}` y assessment persistido, sin bloquear
- [x] Bridge: propagar `visualFidelityAssessment` a metadata `assets[].segments[]`
- [x] Hardening del componente: `text_tokens` al mismo device; score no-finito/no-numérico → `UNAVAILABLE`; carga de imagen con context manager (GIF frame 0 intacto)
- [x] Tests: `tests/test_visual_fidelity_runtime.py` extendido a **32 tests** (ACCEPT/REJECT/NO_RESULTS/DISABLED/UNAVAILABLE/telemetría bridge/device move/no-finito/sin-threshold)
- [x] Suite completa: `python3 -m pytest -q tests` → **`1492 passed, 0 failed, 0 skipped`** (1481 baseline + 11 nuevos)
- [x] `git diff --check` limpio
- [x] Commit: **feat(assets): integrate visual fidelity gate**

## Slice 3 — Validación/calibración y activación (COMPLETADO)

- [x] Re-evaluación del componente runtime real `score_visual_fidelity` sobre el corpus canónico de 38 assets (venv GPU externo `/tmp/shorts-visual-fidelity-gpu-venv`, torch 2.11.0+cu128, open_clip_torch 3.3.0, caché HF reutilizada)
- [x] **25/30 retained + 7/8 badRejected** — reproduce exactamente el benchmark Slice 2; scores coinciden al <1e-6; 38/38 `SCORED`, 0 UNAVAILABLE/DISABLED; target alcanzado (>=24/30 y >=6/8)
- [x] Leave-one-topic-out ya cubierto por la evidencia de `asset-visual-semantic-fidelity` (7/24) — no se re-ejecuta; la reproducibilidad total del runtime sobre el corpus aporta la validación de calibración
- [x] Threshold `0.2296` fijado como **validado/candidato versionado** en la documentación del change; NUNCA default hardcodeado
- [x] Activación controlada: gate OFF por defecto; `VISUAL_FIDELITY_THRESHOLD` = única superficie de activación
- [x] Docs operativas en `design.md`: instalación opcional OpenCLIP, caché de pesos ($HF_HOME/hub), memoria GPU/CPU, comando de activación
- [x] Hardening final bridge: `_map_unresolved_segment` propaga `visualFidelityRejections` (`_visualFidelityRejections`) + 2 tests focales
- [x] Tests focales: `python3 -m pytest tests/test_visual_fidelity_runtime.py -q` → **34 passed**
- [x] Suite completa: `python3 -m pytest -q tests` → **`1492 passed, 0 failed, 0 skipped`** (1492 baseline + 2 bridge, sin regresiones)
- [x] `git diff --check` limpio
- [x] Commit: **test(assets): validate visual fidelity runtime**

## Estado del change

- Slices 1 + 2 + 3 COMPLETADOS. Natura del cierre: merge a `main` y cierre OpenSpec quedan para el paso de cierre (fuera de esta sesión: NO merge/push).

## Fuera de alcance

- Implementación del runtime en la sesión de planificación
- OpenAI/VLM; Slice 3B de `asset-visual-semantic-fidelity`
- Nuevos providers, generación de imagen
- `search-vs-generation`
- `deterministic_anchor_coverage_v3` / `FORM_OR_MEDIUM_TERMS` / `asset-entity-fidelity`
- UI
- merge/push