# Results: script-watchability-v1

## Estado: BLOCKED (validación de vídeo real)

Código y tests del change: **COMPLETOS, verdes e independientes**.
La validación de extremo a extremo en vídeo real no pudo completarse por una limitación
ambiental preexistente y ajena al change (gap de supply de assets en modo AUTO).

## Evidencia de validación offline (todas PASS)

- Suite completa: **1876 passed, 0 failed** (baseline previo `1849` + 27 tests nuevos de
  `tests/test_script_watchability.py`).
- Focales verdes: `test_script_watchability`, `test_duration_fitting_contract`,
  `test_auto_mixed_visual_runtime`, `test_generate_script_v2`.
- `git diff --check` limpio en cada commit.
- Commits funcionales:
  - `9acbf58` `feat(script): improve short-form watchability`
  - `cb2d9f7` `feat(script): bound duration-repair expansions`

## Runs reales (config: `--duration 30 --visual-mode auto --tts-provider elevenlabs`)
`--asset-providers wikimedia_commons,pixabay,pexels`

### A — Divulgativo: "Cómo sobreviven los pingüinos emperador al invierno antártico"

| Job | Resultado | Nota |
|-----|-----------|------|
| `cmo-2026-08-20-162421` | `REVIEW_REQUIRED / DURATION_FITTING_EXHAUSTED` | Usó prompts de repair PREVIO al refinamiento: EXPAND ~109 palabras (proyección 52.2s) y COMPRESS recortó poco. Motivó el refinamiento. |
| `cmo-2026-08-20-162756` | `ASSETS_PARTIAL` (8/10) | Guion final (retry 1, estructural, 49 palabras): hook sólido y sin CTA. Escena 1 `VIDEO_PREFERRED`. |
| `cmo-2026-08-20-163029` | `ASSETS_PARTIAL` | Reintento mismo tópico; bloqueado de nuevo por supply de ilustración. |

Evaluación del guion de A (`162756`, 5 escenas / 49 palabras):

- **Hook (escena 1):** "Los pingüinos emperador pueden sobrevivir al frío extremo. ¿Cómo lo logran?"
  — 11 palabras, abre con afirmación concreta + pregunta; sin intro genérica ni clickbait.
- **Desarrollo (2-4):** mecanismos concretos y densos (plumaje aislante → agrupación en colonias →
  huevo/incubación). Progresión causa-efecto correcta.
- **Cierre (5):** "Así, los pingüinos emperador sobreviven al invierno antártico." — payoff-resolución,
  conector inicial leve ("Así,"), sin moraleja y sin CTA.
- **CTA promocional:** ausente. ✓

### B — Técnico: "Cómo funciona un motor de dos tiempos"

| Job | Resultado | Nota |
|-----|-----------|------|
| `cmo-2026-08-20-163147` | `ASSETS_PARTIAL` | Guion final (retry 1, 60 palabras), sin CTA. |

Evaluación del guion de B (`163147`, 5 escenas / 60 palabras):

- **Hook (escena 1):** "¿Sabes cómo funciona un motor de dos tiempos? Este tipo de motor es
  eficiente y simple." — 16 palabras. La pregunta es un gancho tópico asumible, pero el segundo
  tramo es descriptivo-adjetival ("eficiente y simple") sin dato concreto. Hook más débil que A.
- **Desarrollo (2-4):** ciclo de dos etapas (compresión/explosión) → mezcla aceite+combustible →
  ligereza/simplicidad. Mecanismo presente, con imprecisión menor en la descripción del ciclo.
- **Cierre (5):** "Un motor de dos tiempos es eficiente y versátil para muchas aplicaciones." —
  cierre genérico-adjetival, sin moraleja y sin CTA.
- **CTA promocional:** ausente. ✓

## Resultado frente a acceptance

| Criterio | Verdict |
|----------|---------|
| Suite completa >= 1849, 0 failed | PASS (1876) |
| Sin regresión duration/visual (tests mediaPreference/visuales) | PASS |
| Hooks de runs reales claramente directos | LIGHT (A buena, B más débil) |
| Ningún run introduce CTA promocional obligatorio | PASS (0 runs) |
| Repair, si ocurre, no degrada hook/payoff | **NO VERIFICADO IN SITU** — el único repair real (162421) fue PREVIO al refinamiento y degradó; el refinamiento lo arregla por diseño+tests, pero no hubo run real post-refinamiento que alcanzara audio. |
| Duration contract PASS cuando corresponde | **NO VERIFICADO** — ningún run post-refinamiento alcanzó render (todos bloqueados en assets). |

No se ha honrado el umbral de acceptance de extremo a extremo (necesita un run real que
llegue a `VALIDATED` bajo los prompts finales). Por ello **NO** se declara `READY_TO_MERGE`.

## Decisión de estado

`SCRIPT_WATCHABILITY_V1_BLOCKED`

Razón: los dos tópicos de prueba se bloquearon sistemáticamente en `ASSETS_PARTIAL` por el gap de
supply de formas ilustración/diagrama en modo AUTO (limitación preexistente y documentada en
`auto-mixed-visual-runtime`, no introducida por este change), impidiendo verificar duration PASS y
repair-sin-degradación con los prompts finales en un run real.

La entrega offline (contrato editorial en prompt + políticas de repair con límites + 27 tests) es
**completa, verde e independiente**. La única vía a `READY_TO_MERGE` es conseguir un run real que
llegue a `VALIDATED` con los prompts finales (p.ej. resolviendo o eludiendo el gap de supply de
assets), o confirmación del operador de aceptar la verificación por suite+tests+pausa del repair
previo como suficiente pese al bloqueo ambiental.

## Limitaciones futuras (no implementar aquí)

- Engagement/CTA configurable (`ctaMode`/`engagementMode`/`engagementPlacement`).
- Nuevos schemas/judges/llamadas LLM.
- Cambios de routing/providers/mediaPreference/renderer/TTS/duration contract/web UI.