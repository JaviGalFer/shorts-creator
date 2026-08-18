# Tasks: generic-content-pipeline-evaluation

**Status: CLOSED — Fases 1 y 2 completadas, revisión visual externa completada, decisión YELLOW. Merged a `main` con `--no-ff`.**

## Fase 1 — Setup, contrato y herramienta offline (COMPLETADA)

- [x] Verificar `main == b7b8d57`, working tree limpio
- [x] Crear rama `change/generic-content-pipeline-evaluation`
- [x] Materializar `openspec/changes/generic-content-pipeline-evaluation/{proposal,design,tasks}.md`
- [x] Documentar la matriz canónica de 8 temas (exacta)
- [x] Documentar el contrato (A: bootstrap duration = telemetría no bloqueante; B: sin sondeo de provider, `UNRESOLVED_CAUSE_UNCERTAIN`; C: grupos CORE vs SUPPLY/COVERAGE)
- [x] Documentar el rubric por tema (HEALTHY / USABLE_WITH_LIMITATIONS / SYSTEMIC_FAILURE) y agregado (GREEN / YELLOW / RED)
- [x] Implementar `tools/genericity_matrix.py` (read-only, offline, CLI + módulo)
- [x] Test focal de la herramienta con fixtures sintéticos (sin jobs reales)

## Correcciones de docs de proyecto

- [x] `agent-context.md`: main base refleja `b7b8d57`; `script-visual-specificity` CLOSED; `asset-entity-fidelity` PAUSED / research-only pendiente de evidencia de genericity; evaluation activa `generic-content-pipeline-evaluation`
- [x] `current-state.md`: dejar de describir la especificidad de script como próxima prioridad; reflejar `generic-content-pipeline-evaluation` como evaluación activa

## Fase 2 — Ejecución real + análisis (COMPLETADA)

- [x] Refinar el harness (resolvedDetails + coverage): COMPLETADO
- [x] Actualizar tests focales sintéticos con los campos nuevos: COMPLETADO
- [x] Ejecutar los 8 temas:

  ```
  python bin/run_job.py --topic "<TOPIC>" --duration-preset quick_30 \
    --asset-providers wikimedia_commons,pixabay --stop-after assets
  ```

  (1. Cómo se forma una aurora boreal, 2. La evolución del Porsche 911, 3. Cómo funciona Spring Boot, 4. Por qué cayó el Imperio Romano, 5. Cómo cazan los pulpos, 6. Qué ocurre dentro de un volcán, 7. Cómo evolucionaron los videojuegos 3D, 8. Cómo funciona una hipoteca)
- [x] Pasar cada `metadata.json` a `tools/genericity_matrix.py` y recopilar filas de la matriz: COMPLETADO (ver `phase2-report.md`)
- [x] Revisión de guion/VisualPlan y matriz resuelto/no resuelto: COMPLETADO
- [x] Revisión VISUAL de píxeles: COMPLETADA (revisión externa multimodal desde los contact sheets `data/evaluations/genericity-phase2-visual-review/`; 38 resueltos → 16 CR / 14 CU / 8 FP). Clasificaciones finales (no provisionales) en `phase2-report.md`
- [x] Clasificar cada tema (final) + agregado: COMPLETADO → **YELLOW**
- [x] Análisis, conclusiones de diseño y cierre: COMPLETADO → change CLOSED

## Evidencia Fase 2 (runtime)

- 8/8 jobs `ASSETS_PARTIAL`, todos script attempt 1 (retries 0), ninguno `REVIEW_REQUIRED`, sin fallo de infra/auth/API.
- 3 jobs con `durBootstrap=FAIL` (Porsche, Spring Boot, hipoteca) = telemetría no bloqueante (contrato A confirmado).
- 0 queries VAGUE en los 8 dominios (gate de especificidad OK).
- CORE: `SEMANTIC_GATE_FALSE_POSITIVE` CONFIRMADO por píxeles en 5 temas de dominios no relacionados (Aurora 2, Porsche 2, Spring Boot 1, Roma 2, Pulpos 1).
- SUPPLY/COVERAGE: `NO_RESULTS` alto en Spring Boot (7), Videojuegos (8), Roma (5), Pulpos (4); causa persistida no distinguible → `UNRESOLVED_CAUSE_UNCERTAIN` (contrato B).
- Clasificación final por tema: Volcán HEALTHY; Aurora, Porsche, Spring Boot, Pulpos, Videojuegos, Hipoteca USABLE_WITH_LIMITATIONS; Roma SYSTEMIC_FAILURE (solo capa de assets).
- Detalle completo y paths de assets en `phase2-report.md`.

## Cierre (CLOSED) — decisiones registradas

- `asset-entity-fidelity`: permanece como EVIDENCIA DE INVESTIGACIÓN SOLO (pausado, no activo). NO implementar `deterministic_anchor_coverage_v3` / `FORM_OR_MEDIUM_TERMS`.
- Cambio futuro registrado: **`asset-visual-semantic-fidelity`** — validación semántico-visual de segunda etapa basada en píxeles (provider-agnostic), conservando el gate de metadata actual como primera etapa. NO diseñado en esta sesión.
- Dirección de producto separada registrada: fallback search-vs-generation para cobertura de conceptos difíciles de ilustrar con stock.
- Contact sheets: `data/evaluations/genericity-phase2-visual-review/` (evidencia git-ignored vía `.gitignore` `data/evaluations/`).

## FUERA DE ALCANCE (Fase 1 y 2)

- Cambios en `src/shorts_creator/script/`, `assets/`, `contracts/`
- Cambios de comportamiento en `bin/`
- Prompt, scorer semántico, router, executor, providers
- `--probe-unresolved` o re-ejecución de búsquedas de provider desde la herramienta
- Ejecución real de los 8 temas
- Implementación de `asset-entity-fidelity` / `deterministic_anchor_coverage_v3`
