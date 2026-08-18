# Tasks: generic-content-pipeline-evaluation

**Status: EN CURSO — Fase 1 COMPLETADA, Fase 2 ACTIVA (evaluación/benchmark real). Change abierto pendiente de revisión.**

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

## Fase 2 — Ejecución real + análisis (ACTIVA, en curso en este change)

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
- [ ] Revisión VISUAL de píxeles (pendiente — pendiente de entorno con capacidad de inspección de imagen; clasificaciones provisionales + `VISUAL_REVIEW_PENDING`)
- [x] Clasificar cada tema (provisional) + agregado: COMPLETADO → `AGGREGATE_DECISION_PENDING_VISUAL_REVIEW` (lean provisional YELLOW)
- [ ] Análisis y cierre; marcar este change CLOSED cuando corresponda (tras revisión visual externa)

## Evidencia Fase 2 (runtime)

- 8/8 jobs `ASSETS_PARTIAL`, todos script attempt 1 (retries 0), ninguno `REVIEW_REQUIRED`, sin fallo de infra/auth/API.
- 3 jobs con `durBootstrap=FAIL` (Porsche, Spring Boot, hipoteca) = telemetría no bloqueante (contrato A confirmado).
- 0 queries VAGUE en los 8 dominios (gate de especificidad OK).
- CORE: probables `SEMANTIC_GATE_FALSE_POSITIVE` repetidos en 4 dominios no relacionados (Porsche, Spring Boot, Roma, hipoteca).
- SUPPLY/COVERAGE: `NO_RESULTS` alto en Spring Boot (7), Videojuegos (8), Roma (5), Pulpos (4); causa persistida no distinguible → `UNRESOLVED_CAUSE_UNCERTAIN` (contrato B).
- Detalle completo y paths de assets en `phase2-report.md`.

## FUERA DE ALCANCE (Fase 1 y 2)

- Cambios en `src/shorts_creator/script/`, `assets/`, `contracts/`
- Cambios de comportamiento en `bin/`
- Prompt, scorer semántico, router, executor, providers
- `--probe-unresolved` o re-ejecución de búsquedas de provider desde la herramienta
- Ejecución real de los 8 temas
- Implementación de `asset-entity-fidelity` / `deterministic_anchor_coverage_v3`
