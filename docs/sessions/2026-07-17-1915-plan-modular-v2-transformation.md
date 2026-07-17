# Sesión: Plan modular V2 transformation

- Fecha: 2026-07-17 19:15 (Europe/Madrid)
- Objetivo: Formalizar el plan de transformación modular y crear el change `retire-legacy-visual-v1`
- Estado inicial: Pipeline funcional V1+V2 coexistiendo, benchmark R1 cerrado, Phase A pacing completada
- Estado final: Plan registrado, change de planificación creado, current-state actualizado
- Agente responsable: opencode/big-pickle (default)
- Cambio OpenSpec relacionado: `retire-legacy-visual-v1` (creado)
- Riesgo asumido: Ninguno (solo.documentación)
- Validaciones realizadas:
  - Estructura de change OpenSpec verificada
  - Archivos referenciados en current-state.md verificados
  - Ningún archivo Python, test o configuración modificado
- Archivos creados:
  - `openspec/changes/retire-legacy-visual-v1/proposal.md`
  - `openspec/changes/retire-legacy-visual-v1/design.md`
  - `openspec/changes/retire-legacy-visual-v1/tasks.md`
  - `docs/architecture/modular-v2-transformation-roadmap.md`
  - `docs/sessions/2026-07-17-1915-plan-modular-v2-transformation.md`
- Archivos modificados:
  - `docs/project/current-state.md`
- Comandos ejecutados: Solo mkdir y validaciones de estructura
- Resultado: Plan de transformación modular formalizado. Change `retire-legacy-visual-v1` listo para planificación
- Próximos pasos:
  1. Ejecutar Slice 1 del change `retire-legacy-visual-v1` (V2-only generation contract)
  2. Ejecutar Slices sucesivos hasta completar la retirada de V1
  3. Tras cierre: crear `pyproject.toml` y `src/shorts_creator/`
- Bloqueos o decisiones pendientes:
  - Identificador exacto de `UNSUPPORTED_LEGACY_SCHEMA` se verificará contra convenciones antes de implementar
  - Renombrado de módulos `_v2` se difiere a change futuro
