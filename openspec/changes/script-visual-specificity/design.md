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

`tokenize` se mueve mecánicamente (mismo comportamiento: minúsculas, alfanuméricos `[a-z0-9]+`, longitud >= 3, excluye `GENERIC_FILLER`). `GENERIC_FILLER` y `WEAK_SUPPORT_TERMS` se mueven sin alterar valores. `STOPWORDS` es un conjunto nuevo y separado (artículos/preposiciones/conjunciones tipo `the`, `and`, `of`, `with`, `for`, `from`, `this`, `that`) usado sólo por el guard; no toca al scorer.

## Guard de especificidad (`visual_specificity.py`)

Para cada query (string no vacío):

```
content = tokenize(query) - GENERIC_FILLER - STOPWORDS
weak    = content ∩ WEAK_SUPPORT_TERMS
anchors = content - weak
```

Vercticts:
- `VALID`: `anchors` no vacío y `len(weak) < len(anchors)`.
- `VAGUE`: `anchors` vacío (sin contenido discriminativo) o `len(weak) >= len(anchors)` (términos editoriales/calificadores dominan o empatan).
- `EMPTY` / sin tokens: tratado como `VAGUE` (sin sustancia).

Diagnóstico por query: `contentTerms`, `weakTerms`, `anchorTerms`, `verdict`, `reason`. Para un plan: recorre `searchQueries` y `visualSequence[].searchQuery` no nulos, emite errores `QUERY_NOT_SPECIFIC` / `SEGMENT_QUERY_NOT_SPECIFIC` con path por escena/índice.

Ejemplos verificados contra la regla:

| Query | weak/anchor | Verdict |
|-------|-------------|---------|
| `popular culture` | weak=2 anchors=0 → sin anchors | VAGUE |
| `future of YouTube` | weak=1 anchors=1 → 1>=1 | VAGUE |
| `viral YouTube video screenshot` | weak=3 anchors=1 → 3>=1 | VAGUE |
| `famous early YouTubers photo` | weak=2 anchors=1 → 2>=1 | VAGUE |
| `future of the youtube` | (stop `the`) weak=1 anchors=1 → VAGUE | VAGUE |
| `early YouTube vlogs image` | weak=1 anchors=2 → 1<2 | VALID (semiconcreto, aceptado) |
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