# Tasks: visual-media-strategy

**Status: IN PROGRESS — Slice 1 COMPLETED**

## Slice 1: contratos, policy y registry

- [x] Crear change desde `main` `b94118f` en `change/visual-media-strategy`.
- [x] Añadir `mediaPreference` opcional por segmento a VisualPlan v2, con
      default compatible `IMAGE_PREFERRED`, sin aumentar schema version.
- [x] Añadir contrato puro de `visualMode` y detección explícita de conflicto
      con `mode: images` histórico.
- [x] Añadir `MediaStrategyDecision` puro para preferencias, constraints,
      fallback y degradaciones A-D.
- [x] Añadir registry estático `ProviderCapability` con Pexels Photos/Video
      separados y `PLANNED`.
- [x] Añadir tests focales de contratos, compatibilidad y capabilities.
- [x] Actualizar `agent-context.md` y `current-state.md` sin bitácora.
- [x] Validación focal: `130 passed` (`test_visual_plan_v2`, media strategy,
      capability registry).
- [x] Suite completa: `1650 passed` (`python3 -m pytest -q tests`).
- [x] `git diff --check` limpio.
- [ ] Commit `feat(visual): add media strategy contracts`.

## Slices posteriores (no implementados)

- [ ] Candidate envelope y selección top-N para Photos.
- [ ] Runtime `pexels-photos` image-only.
- [ ] Evolución `VisualAsset.kind = IMAGE | VIDEO`.
- [ ] Playback contract y rendering VIDEO local.
- [ ] Runtime Pexels Video RAW+adapted, diversidad y selección posterior.
