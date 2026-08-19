# Tasks: visual-media-strategy

**Status: IN PROGRESS — Slice 1 COMPLETED / VERIFIED; Slice 2A COMPLETED / VERIFIED; Slice 2B HARDENED / VERIFIED; FINAL READ-ONLY REVIEW pending**

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
- [x] Commit `57479c1` `feat(visual): add media strategy contracts`.

## Slices de evolución del change

- [x] Slice 2A: separar form support de runtime availability en la decisión
      pura, unificar enums de medio y añadir `UNDECLARED` para fit ausente.
- [x] Slice 2A: añadir `CandidateEnvelope`, `CandidateAttempt`,
      `CandidateSelectionResult` y helper puro top-N sin wiring productivo.
- [x] Slice 2A: focales `66 passed`; regresión VisualPlan `106 passed`; suite
      completa `1692 passed`; `git diff --check` limpio.
- [x] Slice 2A commit `c0449f6` `feat(assets): add candidate selection contracts`.
- [x] Slice 2B: cablear lifecycle común candidate-first-accepted con paridad
      de Wikimedia/Pixabay, sin runtime Pexels.
- [x] Slice 2B: tests afectados `331 passed`; suite completa `1699 passed`;
      `git diff --check` limpio.
- [x] Slice 2B commit `9381435` `refactor(assets): unify candidate selection lifecycle`.
- [x] Hardening final: rank Pixabay = posición 1-based del discovery stream
      final; wiring real, límite 20 y precedence `DOWNLOAD_FAILED` verificados.
- [x] Hardening validation: focused `257 passed`; full suite `1703 passed`;
      `git diff --check` limpio.
- [x] Hardening commit `c2d66f8` `fix(assets): harden candidate lifecycle parity`.
- [ ] FINAL READ-ONLY REVIEW antes de cierre/merge.
- [ ] Runtime `pexels-photos` image-only.
- [ ] Evolución `VisualAsset.kind = IMAGE | VIDEO`.
- [ ] Playback contract y rendering VIDEO local.
- [ ] Runtime Pexels Video RAW+adapted, diversidad y selección posterior.
