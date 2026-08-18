# Tasks: visual-fidelity-runtime

**Status: SLICE 1 COMPLETADO — Slice 2 y Slice 3 pendientes.**

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

## Slice 2 — Integración executor + telemetría (PENDIENTE)

- [ ] Gate post-descarga / pre-RESOLVED en `_resolve_wikimedia` y `_resolve_pixabay`
- [ ] Rechazo: borrar archivo, registrar `visualFidelityRejections`, continuar siguiente candidato
- [ ] Todos rechazados → `NO_RESULTS` con `visualFidelityRejections`
- [ ] Bypass `UNAVAILABLE` / `DISABLED` con warning y telemetría
- [ ] Bridge: propagar `visualFidelityAssessment` a metadata `assets[].segments[]`
- [ ] Tests de flujo + suite completa verde

## Slice 3 — Validación/calibración y activación (PENDIENTE)

- [ ] Re-evaluación con runtime real sobre corpus canónico de 38 assets (target provisional: retained >= 24/30, badRejected >= 6/8)
- [ ] Leave-one-topic-out sobre los 8 topics
- [ ] Fijar threshold versionado (config, no hardcodeado)
- [ ] Activación controlada (env/flag)
- [ ] Docs operativas (extra opcional, caché de pesos, memoria)

## Fuera de alcance

- Implementación del runtime en la sesión de planificación
- OpenAI/VLM; Slice 3B de `asset-visual-semantic-fidelity`
- Nuevos providers, generación de imagen
- `search-vs-generation`
- `deterministic_anchor_coverage_v3` / `FORM_OR_MEDIUM_TERMS` / `asset-entity-fidelity`
- UI
- merge/push