# Tasks: auto-mixed-visual-runtime

## Slice 1 — Editorial media decision + routing (offline/mocked)

- [x] Prompt `mediaPreference` (system prompt, ejemplo, request blocks AUTO/MIXED/IMAGES_ONLY/VIDEOS_ONLY).
- [x] Guardia anti-ausencia `MEDIA_PREFERENCE_MISSING` (detección sobre payload crudo, posterior a canonicalizar cuando ya no es generación).
- [x] `medium_neutral_query` en `visual_terms` + `MEDIUM_MARKERS`.
- [x] `_derive_search_queries`: no añadir suffix medium-only (photograph/stock).
- [x] Pexels Video: query efectiva neutralizada + `queryUsed` == query efectiva (autoridad).
- [x] Router multi-kind: preferred → fallback(s), sourceProviders por nivel, mediaDecision + fallbackKinds.
- [x] Executor: `mediaFallback`, `PREFERRED_MEDIA_EXHAUSTED`, propagación `mediaDecision`.
- [x] Fetcher: `mix_counts` tracker selected-only (tie-break EITHER en MIXED).
- [x] Bridge: `mediaDecision` / `mediaFallback` aditivos en `assets[].segments[]`.
- [x] Tests: prompt, query, router, executor, tracker, bridge.
- [x] Suite completa 1843 passed (1809 base + 34 nuevos), 0 failed; `git diff --check` limpio.

**Estado: Slice 1 COMPLETE**

## Slice 2 — Mixed runtime + E2E (completada)

- [x] Hardening A: prompt sin contradicción (ejemplo de queries medium-neutral).
- [x] Hardening B: reconciliación `mediaDecision` con media kinds supervivientes (source-policy); `PREFERRED_MEDIA_EXHAUSTED` solo para kind primario permitido que agotó candidatos.
- [x] Hardening C: `mediaDecision` preservado en TODOS los terminales del executor (incl. SEMANTIC POSTCONDITION, PROVIDER_UNAVAILABLE, dry-run, no-candidates).
- [x] Hardening D: guardia `MEDIA_PREFERENCE_MISSING` estricta en AUTO/MIXED; design.md actualizado (no se tolera silenciosamente).
- [x] Mixed local render smoke (prepare/render/validate real, IMAGE/VIDEO/IMAGE, 1080x1920, PASS).
- [x] Real AUTO E2E `cmo-2026-08-20-152730` VALIDATED (8 IMAGE + 1 VIDEO, mediaDecision==mediaKind, sin fallback).
- [x] Real MIXED E2E `por-2026-08-20-153502` ASSETS_PARTIAL (9/10, mezcla 5 IMAGE + 4 VIDEO).
- [x] Verificación del comportamiento LLM: mediaPreference explícito, sin default histórico.
- [x] Suite completa 1849 passed, 0 failed; `git diff --check` limpio.

**Estado: Slice 2 COMPLETE**

## Estado del change

**COMPLETED / VERIFIED / CLOSED — pending authorized merge.**

Baseline `1809` → Slice 1 `1843` → final `1849 passed, 0 failed`.