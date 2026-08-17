# Tasks: script-visual-specificity

**Status: CLOSED** — all slices implemented, validated and merged to `main`.

## Slice 1 — Vocabulario compartido + guard (COMPLETO, `f1e4a08`)

- [x] Crear `src/shorts_creator/contracts/visual_terms.py` con `GENERIC_FILLER`, `WEAK_SUPPORT_TERMS`, `tokenize` (mover mecánicamente desde `assets/semantic.py`), `STOPWORDS` guard-only
- [x] `assets/semantic.py`: importar/reexportar los nombres movidos; comportamiento del scorer intacto
- [x] Crear `src/shorts_creator/contracts/visual_specificity.py`: guard conservador (`content - filler - stopwords`, `weak`, `anchors`) con diagnóstico (`contentTerms`, `weakTerms`, `anchorTerms`, `verdict`, `reason`)
- [x] Tests focales: reject set, accept set, entidad única válida, all-weak rechazado, stopwords no rescatan una query vaga, paridad del vocabulario tras el move
- [x] Ejecutar tests focales de especificidad + tests del scorer semántico existentes
- [x] `git diff --check` limpio; confirmar que `semantic.py` solo cambia imports/reexport
- [x] Materializar el plan OpenSpec y marcar el cambio activo en docs
- [x] Commit único: `feat(visuals): add visual specificity guard`

## Slice 2 — Integración script + router (COMPLETO, `32f8c75` + `33c562d`)

- [x] Prompt: sección `### Reglas de especificidad de las queries visuales` en `SYSTEM_PROMPT_V2` + refuerzo en user prompt; "X of Y" NO se prohíbe de forma general (nombres recuperables como "Statue of Liberty", "map of Spain", "portrait of Marie Curie", "diagram of human heart" son válidos); grounding en la narración, sin nombres inventados; un solo término de entidad es válido; queries en inglés
- [x] Wiring del guard en `_validate_and_canonicalize_script_v2` (errores `QUERY_NOT_SPECIFIC` / `SEGMENT_QUERY_NOT_SPECIFIC`)
- [x] Bloque de retry dedicado "Especificidad visual insuficiente" en `_build_retry_instruction_v2`
- [x] Filtro en `router._derive_search_queries`: descartar queries derivadas que no pasen el guard; conservar `NO_SEARCH_QUERIES_DERIVED`
- [x] Tests: aserciones de prompt, simulación vago→retry→concreto, filtro de derivación, auditoría/actualización de fixtures afectadas
- [x] Alineación del wording de retry con el contrato "X of Y" (`33c562d`)
- [x] Ejecutar suites focales (especificidad, generate_script_v2, adaptive_scene_planning, router/fetch, executor/bridge, semantic) — todo verde
- [x] `git diff --check` limpio; confirmar que `semantic.py` no tiene diff (scorer intacto)
- [x] Commit: `feat(visuals): enforce visual query specificity`

## Slice 3 — Evidencia real + cierre (COMPLETO)

- [x] Run real del descubrimiento (`--duration-preset quick_30`, `--stop-after assets`): `los-2026-08-17-204707` → `REVIEW_REQUIRED` bajo el guard inicial sobre-estricto. Evidencia de calibración: condujo a separar `SPECIFICITY_WEAK_TERMS` del `WEAK_SUPPORT_TERMS` semántico y a refinar la regla del guard.
- [x] Slice 3A — Calibración (`11bcc6d`): `SPECIFICITY_WEAK_TERMS` guard-only (early, famous, future, popular, viral, culture, media, social, video(s), screen, screenshot(s), section); `logo`, `interface`, `formation`, `first`, `current`, `latest`, `modern`, `new`, `old` NO son weak; regla refinada (VAGUE: sin anchors, o 1 anchor + >=1 weak, o >=2 anchors + weak > anchors); regresiones runtime obligatorias ahora VALID (`Jenna Marbles early YouTube video screenshot`, `YouTube logo photograph`, `YouTube interface screenshot`, `viral content YouTube screenshot`); CTA/grounding en prompt y retry
- [x] Run real final: `los-2026-08-17-205843` → script aprobado en attempt 0 (retries 0), todas las queries persistentes VALID, 5 escenas / 10 segmentos pasan el gate determinista
- [x] Evidencia de assets: `ASSETS_PARTIAL`, 4/10 resueltos (1 claramente relevante, 2 coarse/topic, 1 flag como falso positivo "Smosh fan art" -> arte abstracto sin Smosh). Limitación aceptada: fidelidad de entidad/sujeto es downstream del scorer (`asset-entity-fidelity` como cambio futuro). El gate semántico NO se modificó.
- [x] Suite completa: `1411 passed, 0 failed, 0 skipped` (baseline anterior al cambio: 1345); `git diff --check` limpio
- [x] Cierre: actualizar `agent-context.md` / `current-state.md`, marcar tasks y cerrar change
- [x] Commit de cierre: `docs(project): close script visual specificity`
- [x] Merge `--no-ff` a `main`; rama conservada; sin push

## Evidencia final (junto con el cierre)

- Run de descubrimiento (calibración): `los-2026-08-17-204707` — `REVIEW_REQUIRED` bajo el guard inicial sobre-estricto.
- Run final aceptado: `los-2026-08-17-205843` — `ASSETS_PARTIAL`, script attempt 0, retries 0.
- Suite completa: `1411 passed, 0 failed, 0 skipped`.
- Commits: `f1e4a08`, `32f8c75`, `33c562d`, `11bcc6d`, `docs(project): close ...`.

## Seguimiento futuro (NO diseñado ni implementado ahora)

- Cambio sugerido: `asset-entity-fidelity`.
- Problem statement: la relevancia semántica puede pasar cuando coinciden anchors secundarios de la query pero NO coincide el anchor de la entidad/tema definitorio (p. ej. "Smosh fan art" casando solo "fan" + "art"). Fuera de alcance de este change; el scorer no se modificó.