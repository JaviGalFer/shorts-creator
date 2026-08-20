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

## Slice 2 — Mixed runtime + E2E (futura, pendiente)

- [ ] Hardening executor fallback (restricciones modo duro).
- [ ] Regression mixta IMAGE/VIDEO prepare/render (fixture).
- [ ] Real AUTO E2E (30s, elevenlabs, wikimedia_commons,pixabay,pexels).
- [ ] Real MIXED E2E (mismos providers).
- [ ] Docs/closure.

**Estado: Slice 2 pending**