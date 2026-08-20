# Tasks: script-watchability-v1

Una slice funcional.

## Slice 1

- [x] `SYSTEM_PROMPT_V2`: añadir contrato editorial watchability (hook first-sentence +
      desarrollo/progresión + cierre + factualidad) y refinar regla de hook de ritmo.
- [x] Alinear las 3 superficies de CTA (generator.py:81, :448, :978) a CTA opcional.
- [x] `VOICEOVER_REPAIR_SYSTEM_PROMPT`: política EXPAND y COMPRESS.
- [x] `_build_voiceover_repair_prompt`: bloques direccionales EXPAND/COMPRESS.
- [x] `VOICEOVER_COMPRESSION_SYSTEM_PROMPT`: preservación de hook/facts/causa/payoff.
- [x] `tests/test_script_watchability.py`.
- [x] Focales: test_script_watchability, test_duration_fitting_contract,
      test_generate_script_v2, test_auto_mixed_visual_runtime.
- [x] Suite completa `>=1849 passed, 0 failed` + `git diff --check` (1880 passed).
- [x] Commit funcional: `feat(script): improve short-form watchability`.
- [x] Run real A (divulgativo) + evaluación cualitativa del script final.
- [x] Run real B (técnico) + evaluación cualitativa del script final.
- [x] Closure: results.md + agent-context.md + current-state.md.
- [x] Commit closure: `docs(script): close watchability v1`.

## Hardening final (9fadc10)

- [x] Reforzar hook: pregunta tópica genérica desaconsejada; contenido primero.
- [x] Reforzar cierre: evitar resumen adjetival; preferir payoff/consecuencia concreta.
- [x] Coherencia en COMPRESS (system prompt + bloque direccional).
- [x] Tests nuevos (4) de hook/cierre en `test_script_watchability.py`.

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
- [x] Hardening final hook/cierre (`fix(script): strengthen hooks and payoffs` 9fadc10)
- [x] Tests `tests/test_script_watchability.py` (31) + suite completa `1880 passed`
- [x] E2E final `cmo-2026-08-20-164453` VALIDATED (VIDEOS_ONLY + Pexels, 27.92s, 2 repairs)
- [x] Closure: results.md + agent-context.md + current-state.md + commit `docs(... close watchability v1)`
