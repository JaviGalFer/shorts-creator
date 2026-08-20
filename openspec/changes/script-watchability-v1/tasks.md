# Tasks: script-watchability-v1

Una slice funcional.

## Slice 1

- [ ] `SYSTEM_PROMPT_V2`: añadir contrato editorial watchability (hook first-sentence +
      desarrollo/progresión + cierre + factualidad) y refinar regla de hook de ritmo.
- [ ] Alinear las 3 superficies de CTA (generator.py:81, :448, :978) a CTA opcional.
- [ ] `VOICEOVER_REPAIR_SYSTEM_PROMPT`: política EXPAND y COMPRESS.
- [ ] `_build_voiceover_repair_prompt`: bloques direccionales EXPAND/COMPRESS.
- [ ] `VOICEOVER_COMPRESSION_SYSTEM_PROMPT`: preservación de hook/facts/causa/payoff.
- [ ] `tests/test_script_watchability.py`.
- [ ] Focales: test_script_watchability, test_duration_fitting_contract,
      test_generate_script_v2, test_auto_mixed_visual_runtime.
- [ ] Suite completa `>=1849 passed, 0 failed` + `git diff --check`.
- [ ] Commit funcional: `feat(script): improve short-form watchability`.
- [ ] Run real A (divulgativo) + evaluación cualitativa del script final.
- [ ] Run real B (técnico) + evaluación cualitativa del script final.
- [ ] Closure: results.md + agent-context.md + current-state.md.
- [ ] Commit closure: `docs(script): close watchability v1`.

## Acceptance

- Tests verdes, sin regresión duration/visuals.
- Hooks de las ejecuciones reales claramente directos (sin intro genérica ni clickbait vacío).
- Ningún run introduce CTA promocional por obligación del prompt.
- Repair (si ocurre) no degrada materialmente hook/payoff.
- Duration contract sigue PASS cuando corresponde.

## Fuera de alcance (DEFERRED)

- Engagement/CTA configurable (`ctaMode`, `engagementMode`, `engagementPlacement`;
  ej. NONE/FOLLOW/LIKE/COMMENT/INTERACTIVE/AUTO).
- Nuevos schemas/judges/llamadas LLM; cambios de routing/providers/mediaPreference/renderer/
  TTS/duration contract/web UI.
## Estado de ejecución

- [x] Contrato editorial en prompts (hook, desarrollo, cierre, factualidad)
- [x] CTA no obligatorio (GANADOR SYSTEM_PROMPT_V2 + duration + retry instruction)
- [x] Políticas de repair EXPAND/COMPRESS + límites (`bound duration-repair expansions`)
- [x] Tests `tests/test_script_watchability.py` (27) + suite completa `1876 passed`
- [ ] **BLOQUEADO**: run real post-refinamiento hasta `VALIDATED` para verificar
   `duration contract PASS` y repair sin degradación (assets `ASSETS_PARTIAL` por supply
   de ilustración/diagrama en AUTO — limitación preexistente).
