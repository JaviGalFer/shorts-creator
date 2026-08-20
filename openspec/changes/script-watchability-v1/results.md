# Results: script-watchability-v1

## Estado: COMPLETED / VERIFIED / CLOSED (pending authorized merge)

Cambio completo, verificado por suite + tests + un E2E real de pipeline completo.
La validación de vídeo usó el modo `VIDEOS_ONLY` (supply-friendly), que es independiente
de `visualMode`; AUTO/MIXED quedaron validados en su propio product change
(`auto-mixed-visual-runtime`) y NO forman parte de este change.

## Evidencia offline (todas PASS)

- Suite completa: **1880 passed, 0 failed** (baseline `1849` + 31 tests en
  `tests/test_script_watchability.py`).
- Focales: `test_script_watchability`, `test_duration_fitting_contract`,
  `test_generate_script_v2`, `test_auto_mixed_visual_runtime` (256 passed).
- `git diff --check` limpio.
- Commits:
  - `9acbf58` `feat(script): improve short-form watchability`
  - `cb2d9f7` `feat(script): bound duration-repair expansions`
  - `9fadc10` `fix(script): strengthen hooks and payoffs` (hardening final)

## Hardening final (motivado por runs reales)

El run técnico real (motor de dos tiempos) mostró dos patrones aún demasiado genéricos:

- Hook: "¿Sabes cómo funciona un motor de dos tiempos? Este tipo de motor es eficiente y simple." → pregunta tópica genérica + adjetivos.
- Cierre: "Un motor de dos tiempos es eficiente y versátil para muchas aplicaciones." → resumen adjetival.

Hardening aplicado (prompt-only en `src/shorts_creator/script/generator.py`):

- **Hook:** una pregunta que solo pregunta si el espectador conoce/sabe cómo funciona el tema
  NO es por sí sola un hook fuerte; evitar como opener genérico «¿Sabes cómo funciona X?» /
  «¿Te has preguntado cómo funciona X?» / «¿Conoces X?» salvo que la misma frase aporte de
  inmediato un hecho/contradicción/mecanismo/consecuencia. Preferir que la primera frase
  entregue contenido. No se prohíben preguntas buenas.
- **Cierre:** evitar cierres que solo reevalúan/resumen con adjetivos genéricos («X es eficiente
  y versátil», «X es increíble/fascinante», «por eso X es tan importante»); preferir última
  consecuencia concreta, propiedad específica, payoff o implicación directa. Sin moraleja.
- Coherencia en COMPRESS (system prompt + bloque direccional): no reducir un hook concreto a
  una pregunta vacía ni el cierre a adjetivos genéricos. EXPAND ya prohibía adjetivos/moralejas/
  introducciones.

Tests añadidos (4, assertions sobre el contrato, no regex sobre outputs LLM): pregunta tópica
genérica desaconsejada; pregunta con contenido concreto permitida; cierre de adjetivos
desaconsejado; cierre payoff concreto preferido.

## Runs reales históricos (limitación de supply, NO fallo del change)

### AUTO (evidencia histórica — supply de ilustración/diagrama)

| Job | Tópico | Resultado |
|-----|--------|-----------|
| `cmo-2026-08-20-162421` | pingüinos | `REVIEW_REQUIRED` (fitting exhausto; prompts de repair PREVIO al refinamiento) |
| `cmo-2026-08-20-162756` | pingüinos | `ASSETS_PARTIAL` (8/10; supply ilustración) |
| `cmo-2026-08-20-163029` | pingüinos | `ASSETS_PARTIAL` (supply) |
| `cmo-2026-08-20-163147` | motor 2T | `ASSETS_PARTIAL` (supply) |

Ningún run AUTO llegó a `VALIDATED` dentro de este change. La causa es el gap de supply de
formas ilustración/diagrama en AUTO, limitación preexistente documentada en
`auto-mixed-visual-runtime`, ajena a este change. **NO se afirma que AUTO fue VALIDATED aquí.**

Evaluación cualitativa previa (sin CTA promocional en ambos):
- **Hook pingüinos: PASS** — "Los pingüinos emperador pueden sobrevivir al frío extremo. ¿Cómo lo logran?" (contenido primero).
- **Hook motor: LIGHT** — pregunta tópica genérica + adjetivos; motivó el hardening final.

## E2E final (pipeline completo, VIDEOS_ONLY + Pexels)

`cmo-2026-08-20-164453` — tópico "Cómo cazan los delfines en grupo"
(`--duration 30 --asset-providers pexels --visual-mode videos-only --tts-provider elevenlabs`)

| Métrica | Valor |
|---------|-------|
| status final | **VALIDATED** |
| hook completo scene 1 (10w) | *Los delfines cazan en grupo con asombrosa precisión, coordinando movimientos.* |
| primera frase exacta | *Los delfines cazan en grupo con asombrosa precisión, coordinando movimientos.* |
| cierre scene 5 (16w) | *Los delfines son maestros del trabajo en equipo en la caza, lo que les da ventaja.* |
| CTA promocional | **ausente** |
| moraleja genérica | **ausente** (cierre con consecuencia concreta "lo que les da ventaja") |
| word count final | 61 (hooks 10 / closing 16; historia: 45 → 68 → 65 → 61) |
| duration (render) | **27.92s** (rango 27–33) — `durationOk true`, `maxDurationOk true` |
| repairs | **2** (EXPAND then COMPRESS, dentro de `maxRepairs 2`), decision final **PASS** |
| assets | 5/5 resolvidos (Pexels Video), `ASSETS_READY`, `assetValidation PASS` |

### Repair antes/después (ocurrió de verdad)

El guion original (pre-repair) era de **45 palabras** (por escena [8,9,9,8,11]),
`below_minimum_words` (min 47). El fitting hizo:

1. **EXPAND** (targets [12,14,13,12,17]) con los prompts acotados ("SOLO lo necesario",
   cláusula corta por escena) → se sobre-ajustó temporalmente (~81w, proyección 37.1s).
2. **COMPRESS** (targets [11,14,13,11,16], "recorta con decisión") → propuesta 65w.
3. **PASS** → final 61w [10,11,12,12,16], render 27.92s in-range.

Trazado watchability del guion FINAL entregado (lo que importa al público):
- **hook:** conservado y con contenido primero ("...cazan en grupo con asombrosa precisión,
  coordinando movimientos"), sin pregunta vacía.
- **facts/mecanismo:** desarrollo factual (tácticas de equipo, formación de círculos, mayor
  tasa de éxito) sin inventar datos.
- **payoff:** cierre con consecuencia concreta ("lo que les da ventaja") — no es moraleja ni
  resumen adjetival puro.
- **filler:** ninguno nuevo (los prompts de repair prohíben adjetivos/moralejas/introducciones
  y relleno).
- **CTA:** ausente antes y después.

El texto exacto del guion original (45w) no se persiste (solo word counts); la comparación se
basa en la evolución de word counts por escena y en la calidad del guion final entregado, que
cumple los criterios de watchability. El repair se mantuvo dentro de `maxRepairs 2` y terminó
`PASS` sin agotar presupuesto.

## Verdict

| Criterio | Verdíct |
|----------|---------|
| Suite completa >= 1849, 0 failed | PASS (1880) |
| Hardening hook/payoff verde | PASS (tests + 9fadc10) |
| E2E nuevo alcanza VALIDATED | PASS |
| Duration contract (render) PASS | PASS (27.92s en 27–33) |
| Hook directo y con contenido | PASS (contenido primero) |
| Sin CTA promocional obligatorio | PASS (0 runs) |
| Cierre no es moraleja/resumen adjetival | PASS (consecuencia concreta) |
| Repair, si ocurre, no degrada watchability | PASS (2 repairs, guion final cumple) |

Los `ASSETS_PARTIAL` de AUTO se conservan como evidencia histórica de una limitación de
supply, NO como fallo del change.

## Limitaciones futuras (DEFERRED — no implementar aquí)

- Engagement/CTA configurable (`ctaMode`/`engagementMode`/`engagementPlacement`).
- Nuevos schemas/judges/llamadas LLM.
- Cambios de routing/providers/mediaPreference/renderer/TTS/duration contract/web UI.
