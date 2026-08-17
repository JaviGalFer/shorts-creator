# Propuesta: generic-content-pipeline-evaluation

## Contexto

El pipeline actual es un generador de vídeo corto configurable y agnóstico de dominio. La arquitectura prevista delega la comprensión semántica del tema en una sola generación LLM (script + VisualPlan con subjects / searchQueries / assetPreferences / visualSequence[].searchQuery) y hace que el código Python determinista solo imponga contratos/safety, sin ramas de dominio (YouTube, historia, ciencia, coches, software, finanzas, animales, etc.).

`script-visual-specificity` está CERRADO. `asset-entity-fidelity` (relevancia semántica downstream de entidad/sujeto) está EN PAUSA/hipótesis como investigación, pendiente de evidencia de genericity, y NO es la dirección de implementación activa.

Antes de decidir más cambios product/core, necesitamos medir si el pipeline actual se comporta de forma genérica en múltiples dominios no relacionados. Este change es un **harness de evaluación acotado** (no una implementación de features): no cambia el comportamiento productivo.

## Objetivo

Diseñar y materializar un benchmark de genericity de 2 fases:

- **Fase 1 (este change):** setup de la evaluación — matriz de 8 temas, contrato de medición, herramienta offline de extracción (`tools/genericity_matrix.py`), rubric de clasificación y criterios de decisión GREEN/YELLOW/RED. Sin ejecución real de los 8 temas.
- **Fase 2 (futura):** ejecución real de los 8 temas (`--stop-after assets`) + análisis manual + decisión.

Esta primera fase NO ejecuta la matriz de 8 temas ni introduce sondeos/llamadas de provider desde la herramienta.

## Invariante de producto

`shorts-creator` debe permanecer agnóstico de tema y altamente configurable. No debe contener ramas específicas de dominio.

Confirmado por inspección de código: el router (`ROUTING_MATRIX`, `assets/router.py`), el scorer semántico (`assets/semantic.py`) y el guard de especificidad (`contracts/visual_specificity.py`) son neutrales a proveedor y a dominio. No hay ramas para YouTube/historia/ciencia/coches/software/finanzas/animales. Este change NO añade ninguna heurística semántica ni rama de dominio.

## Matriz de 8 temas (canónica, exacta)

1. `Cómo se forma una aurora boreal` — ciencia / fenómeno natural
2. `La evolución del Porsche 911` — producto / automoción / entidad nombrada
3. `Cómo funciona Spring Boot` — software / tema técnico abstracto
4. `Por qué cayó el Imperio Romano` — historia
5. `Cómo cazan los pulpos` — animales / naturaleza
6. `Qué ocurre dentro de un volcán` — geología / proceso
7. `Cómo evolucionaron los videojuegos 3D` — tecnología / evolución cultural
8. `Cómo funciona una hipoteca` — finanzas / concepto abstracto

## Contrate de la herramienta (Fase 1)

`tools/genericity_matrix.py`:

- Solo lectura, offline, sin red, sin LLM ni llamadas de provider.
- Acepta uno o más paths de `metadata.json`.
- No muta el metadata del job.
- Usable como módulo importable y como CLI.
- Extrae datos persistentes de metadata (ver `design.md`).
- NO intenta juicio automático de calidad factual.
- NO decide si una imagen es visualmente correcta solo desde metadata.

## Correcciones de contrato (importantes)

**A. Duración bootstrap.** La validez estructural V2 es bloqueante en la etapa script; la duración bootstrap WPM es telemetría NO bloqueante; la duración TTS real es autoritativa después. `durationContract.status` se registra como telemetría, pero un `FAIL` bootstrap NO clasifica un tema como fallo de genericity por sí solo.

**B. Sin sondeo de provider en Fase 1.** No implementar `--probe-unresolved`. No re-ejecutar búsquedas de provider desde la herramienta. Si el metadata persistido no distingue "provider vacío" de "rechazo semántico", se clasifica como `UNRESOLVED_CAUSE_UNCERTAIN`. Este primer benchmark evalúa exactamente las salidas originales de los jobs, sin llamadas extra de provider ni variabilidad temporal.

**C. Separar fallos CORE de limitaciones de supply/coverage.** Grupos de fallo:

- CORE: `QUERY_GEN_FAILURE`, `VISUAL_PLAN_FAILURE`, `SEMANTIC_GATE_FALSE_POSITIVE`
- SUPPLY / COVERAGE: `PROVIDER_COVERAGE_FAILURE`, `UNRESOLVED_CAUSE_UNCERTAIN`, `ACCEPTABLE_ASSETS_PARTIAL`

No interpretar problemas repetidos de cobertura de provider como corrupción de arquitectura.

## Criterios de decisión agregados

Por tema: `HEALTHY`, `USABLE_WITH_LIMITATIONS`, `SYSTEMIC_FAILURE`.

Agregado:

- **GREEN:** ≥6/8 HEALTHY o USABLE_WITH_LIMITATIONS; sin fallo CORE repetido en dominios no relacionados; limitaciones de coverage de provider NO bloquean GREEN.
- **YELLOW:** un fallo CORE se repite en ≥2 dominios no relacionados, O la cobertura de provider es suficientemente pobre en varios dominios como para justificar investigar la estrategia de provider (sin cambiar la arquitectura semántica).
- **RED:** múltiples familias de temas no relacionadas muestran fallos CORE sistémicos → investigar arquitectura/contratos antes de añadir features.

## Alcance

- `openspec/changes/generic-content-pipeline-evaluation/{proposal,design,tasks}.md`
- `tools/genericity_matrix.py` (nuevo, solo lectura)
- Test focal de la herramienta (fixtures sintéticos, sin dependencia de jobs reales)
- Correcciones de docs de proyecto (agent-context, current-state)

## Fuera de alcance (Fase 1)

- Cambios en `src/shorts_creator/script/`, `assets/`, `contracts/`
- Cambios de comportamiento en `bin/`
- Prompt, scorer semántico, router, executor, providers
- Ejecución de la matriz de 8 temas (Fase 2)
- Sondeos de provider / `--probe-unresolved`
- CLIP/multimodal, near-duplicates, generación de imagen
- Implementación de `asset-entity-fidelity` o `deterministic_anchor_coverage_v3`

## Criterios de éxito (Fase 1)

1. La herramienta extrae las métricas descritas de metadata persistido sin red/LLM.
2. Test focal pasa con fixtures sintéticos (incluye `ASSETS_PARTIAL`, mix resuelto/no-resuelto, sin `semanticAssessment`, sin assets, bootstrap FAIL como telemetría no-fallo, y no-mutación del input).
3. `git diff --check` limpio.
4. Sin diff en `src/shorts_creator/` ni en comportamiento de `bin/`.
