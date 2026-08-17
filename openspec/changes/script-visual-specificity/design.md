# Diseño: script-visual-specificity

## Arquitectura (3 slices)

```
Slice 1:  contracts/visual_terms.py          (vocabulario léxico puro compartido)
          contracts/visual_specificity.py    (guard conservador de especificidad)
          assets/semantic.py                 (reexport de nombres movidos)

Slice 2:  script/generator.py                (prompt + validación + retry)
          assets/router.py                   (filtro de derivación de queries)

Slice 3:  replay/E2E real + cierre de docs
```

## Propiedad de módulo

Dependencias actuales verificadas: `contracts` es hoja pura; `fetcher` (assets) ya importa `contracts.visual`; `script.generator` ya importa `contracts`. La solución NO introduce nuevas aristas de dominio:

- **`contracts/visual_terms.py`** (nuevo, puro): único origen de `GENERIC_FILLER`, `WEAK_SUPPORT_TERMS`, `tokenize`, más `STOPWORDS` (guard-only, NO se usa en el scorer).
- **`assets/semantic.py`**: importa y reexporta los nombres movidos desde `contracts.visual_terms`. Público del módulo intacto; lógica del scorer intacta.
- **`contracts/visual_specificity.py`** (nuevo, puro): consumido por `script.generator` (Slice 2) y `assets.router` (Slice 2) sin ciclos.

No hay dependencia `validation -> assets`. No hay churn de arquitectura.

## Vocabulario compartido

`tokenize` se mueve mecánicamente (mismo comportamiento: minúsculas, alfanuméricos `[a-z0-9]+`, longitud >= 3, excluye `GENERIC_FILLER`). `GENERIC_FILLER` y `WEAK_SUPPORT_TERMS` se mueven sin alterar valores. `STOPWORDS` es un conjunto nuevo y separado (artículos/preposiciones/conjunciones tipo `the`, `and`, `of`, `with`, `for`, `from`, `this`, `that`) usado sólo por el guard; no toca al scorer. `SPECIFICITY_WEAK_TERMS` (calibración Slice 3A) es un subconjunto guard-only del vocabulario débil semántico; no toca al scorer.

## Guard de especificidad (`visual_specificity.py`)

Para cada query (string no vacío):

```
content = tokenize(query) - GENERIC_FILLER - STOPWORDS     # GENERIC_FILLER ya lo excluye tokenize
weak    = content ∩ SPECIFICITY_WEAK_TERMS                 # subconjunto guard-only, NO WEAK_SUPPORT_TERMS
anchors = content - weak
```

Vercticts:
- `VALID`: `anchors` no vacío y ninguna condición de rechazo se da.
- `VAGUE`: `anchors` vacío (sin contenido discriminativo), o `len(anchors) == 1 and len(weak) >= 1` (único anchor relleno de débiles), o `len(anchors) >= 2 and len(weak) > len(anchors)` (los débiles dominan).
- Sin tokens: tratado como `VAGUE` (sin sustancia).

`SPECIFICITY_WEAK_TERMS` (guard-only) contiene solo: `early, famous, future, popular, viral, culture, media, social, video, videos, screen, screenshot, screenshots, section`. NO se clasifican como weak: `logo, interface, formation, first, current, latest, modern, new, old` (la calibración del guard se separó del `WEAK_SUPPORT_TERMS` semántico tras el run de descubrimiento `los-2026-08-17-204707`).

Diagnóstico por query: `contentTerms`, `weakTerms`, `anchorTerms`, `verdict`, `reason`. Para un plan: recorre `searchQueries` y `visualSequence[].searchQuery` no nulos, emite errores `QUERY_NOT_SPECIFIC` / `SEGMENT_QUERY_NOT_SPECIFIC` con path por escena/índice.

Ejemplos verificados contra la regla final:

| Query | weak/anchor | Verdict |
|-------|-------------|---------|
| `popular culture` | weak=2 anchors=0 → sin anchors | VAGUE |
| `future of YouTube` | anchors=1 weak=1 → 1+weak | VAGUE |
| `viral YouTube video screenshot` | anchors=1 weak=3 → 1+weak | VAGUE |
| `famous early YouTubers photo` | anchors=1 weak=2 → 1+weak | VAGUE |
| `future of the youtube` | (stop `the`) anchors=1 weak=1 → VAGUE | VAGUE |
| `Jenna Marbles early YouTube video screenshot` | anchors=3 weak=3 → 3>3? no | VALID (calibración) |
| `YouTube logo photograph` | anchors=2 weak=0 (logo no weak) | VALID (calibración) |
| `YouTube interface screenshot` | anchors=2 weak=1 → 1>2? no | VALID (calibración) |
| `viral content YouTube screenshot` | anchors=2 weak=2 → 2>2? no | VALID (calibración) |
| `early YouTube vlogs image` | weak=1 anchors=2 → 1>2? no | VALID (semiconcreto) |
| `Smosh` / `Minecraft` / `Chernobyl` | weak=0 | VALID |
| `test query` | weak=0 anchors=2 | VALID |
| `aurora borealis solar particles photograph` | weak=0 | VALID |

El guard rechaza lo claramente vago/editorial de forma conservadora; no absuelve calidad (acepta `test query`). Las entidades de un solo término se mantienen válidas.

## Sin cambios de comportamiento en `deterministic_anchor_coverage_v2`

El scorer no se toca: mismas constantes (mismo origen, movido), misma función `tokenize`, mismos umbrales, mismos mensajes. El único cambio en `semantic.py` es el import/reexport de los nombres movidos.

## Fases de implementación

1. Slice 1: `visual_terms.py` + reexport en `semantic.py` + `visual_specificity.py` + tests focales.
2. Slice 2: prompt (system/user), wiring de validación en `_validate_and_canonicalize_script_v2`, bloque de retry "Especificidad visual insuficiente", filtro de derivación en `router._derive_search_queries`.
3. Slice 3: run real YouTube-topic, gate determinista de metadata (todas las queries persistentes pasan el guard) como criterio primario, evidencia de resolución como soporte (parcial aceptable), suite completa, `git diff --check`, cierre de docs.
4. Slice 3A (calibración, `11bcc6d`): separar `SPECIFICITY_WEAK_TERMS` del `WEAK_SUPPORT_TERMS` semántico + regla refinada, tras el run de descubrimiento `los-2026-08-17-204707` (REVIEW_REQUIRED bajo el guard inicial sobre-estricto).

## Cierre

- Run final `los-2026-08-17-205843`: script aprobado en attempt 0 (retries 0), todas las queries persistentes `VALID`, 5 escenas / 10 segmentos pasan el gate determinista, `ASSETS_PARTIAL`, 4/10 resueltos.
- Suite completa en cierre: `1411 passed, 0 failed, 0 skipped`. `git diff --check` limpio.
- Limitación aceptada: `"Smosh fan art"` produjo un falso positivo (arte genérico fan/art de Pixabay sin Smosh). Es comportamiento downstream de fidelidad entidad/sujeto en `deterministic_anchor_coverage_v2` (scorer sin cambios, fuera de alcance). Seguimiento futuro: cambio `asset-entity-fidelity` (no diseñado ni implementado).