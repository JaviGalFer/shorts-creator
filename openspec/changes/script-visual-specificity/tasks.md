# Tasks: script-visual-specificity

## Slice 1 — Vocabulario compartido + guard (COMPLETO, `f1e4a08`)

- [x] Crear `src/shorts_creator/contracts/visual_terms.py` con `GENERIC_FILLER`, `WEAK_SUPPORT_TERMS`, `tokenize` (mover mecánicamente desde `assets/semantic.py`) y `STOPWORDS` guard-only
- [x] `assets/semantic.py`: importar/reexportar los nombres movidos; comportamiento del scorer intacto
- [x] Crear `src/shorts_creator/contracts/visual_specificity.py`: guard conservador (`content - filler - stopwords`, `weak`, `anchors`; rechaza sin anchors o `len(weak) >= len(anchors)`) con diagnóstico (`contentTerms`, `weakTerms`, `anchorTerms`, `verdict`, `reason`)
- [x] Tests focales: reject set (`popular culture`, `future of YouTube`, `viral YouTube video screenshot`, `famous early YouTubers photo`, `future of the youtube`), accept set (`Smosh`, `Minecraft`, `Chernobyl`, `aurora borealis solar particles photograph`, `test query`, `early YouTube vlogs image`), entidad única válida, all-weak rechazado, stopwords no rescatan una query vaga, paridad del vocabulario tras el move
- [x] Ejecutar tests focales de especificidad + tests del scorer semántico existentes
- [x] `git diff --check` limpio; confirmar que `semantic.py` solo cambia imports/reexport
- [x] Materializar el plan OpenSpec y marcar el cambio activo en docs
- [x] Commit único: `feat(visuals): add visual specificity guard`

## Slice 2 — Integración script + router

- [x] Prompt: sección `### Reglas de especificidad de las queries visuales` en `SYSTEM_PROMPT_V2` + refuerzo en user prompt (entidades concretas, prohibición de abstracciones editoriales como "popular culture", "future of X", "impact of X", "why X matters"; "X of Y" NO se prohíbe de forma general — nombres propios recuperables como "Statue of Liberty" siguen válidos; grounding en la narración, sin nombres inventados; un solo término de entidad es válido; queries en inglés)
- [x] Wiring del guard en `_validate_and_canonicalize_script_v2` (errores `QUERY_NOT_SPECIFIC` / `SEGMENT_QUERY_NOT_SPECIFIC`)
- [x] Bloque de retry dedicado "Especificidad visual insuficiente" en `_build_retry_instruction_v2`
- [x] Filtro en `router._derive_search_queries`: descartar queries derivadas que no pasen el guard; conservar `NO_SEARCH_QUERIES_DERIVED`
- [x] Tests: aserciones de prompt, simulación vago→retry→concreto, filtro de derivación, auditoría/actualización de fixtures afectadas (`test_adaptive_scene_planning`, derivación del router)
- [x] Ejecutar suites focales (especificidad, generate_script_v2, adaptive_scene_planning, router/fetch, executor/bridge, semantic) — todo verde
- [x] `git diff --check` limpio; confirmar que `semantic.py` no tiene diff (scorer intacto)
- [x] Commit único: `feat(visuals): enforce visual query specificity`

## Slice 3 — Evidencia real + cierre

- [ ] Run real sobre tema YouTube (`bin/run_job.py --preset quick_30 --asset-providers wikimedia_commons,pixabay`)
- [ ] Gate determinista primario: todas las queries del script persistido pasan el guard (checker programático sobre metadata)
- [ ] Evidencia de resolución como soporte (recuentos + revisión manual de falsos positivos; `ASSETS_PARTIAL` aceptable; no determina el pass/fail)
- [ ] Suite completa `0 failed`, sin regresiones de skips; `git diff --check` limpio
- [ ] Cierre: actualizar `agent-context.md` / `current-state.md`, marcar tasks y cerrar change