# Propuesta: script-visual-specificity

## Problema actual

El gate semántico (`deterministic_anchor_coverage_v2`, CLOSED) rechaza basura obvia con éxito, pero su calidad está limitada por la intención que recibe. Las queries del VisualPlan generadas por el script son frecuentemente vagas/editoriales (`popular culture`, `future of YouTube`, `viral YouTube video screenshot`, `famous early YouTubers photo`) en lugar de conceptos concretos y recuperables (personas, obras, productos, eventos, lugares, fechas, objetos, fenómenos).

El benchmark real `los-semantic-v2-20260817-203235` quedó en 3 resuelto / 8 fallido (`ASSETS_PARTIAL`) por esta falta de especificidad ascendente. El problema no está en la etapa de assets: está en la generación de script y en el plan visual, que no exige queries con sustancia discriminativa.

## Solución propuesta

Tres slices:

1. **Slice 1 (este cambio):** Guard determinista y conservador de especificidad de queries visuales (`QUERY_NOT_SPECIFIC`), con vocabulario léxico compartido y puro. Sin integración en script/router todavía.
2. **Slice 2:** Integración en la generación de script (prompt + validación + retry) y filtro de derivación de queries en el router.
3. **Slice 3:** Replay/E2E real de soporte + cierre de documentación.

## Diseño del guard (Slice 1)

Regla de validez conservadora por query (scene `searchQueries[i]` y segmento `searchQuery` no nulo):

```
content = tokenize(query) - GENERIC_FILLER - STOPWORDS
weak    = content ∩ WEAK_SUPPORT_TERMS
anchors = content - weak

Rechazar si:
- anchors está vacío (sin contenido discriminativo), O
- len(weak) >= len(anchors) (los términos editoriales/calificadores dominan o empatan)
```

- Rechaza: `popular culture`, `future of YouTube`, `viral YouTube video screenshot`, `famous early YouTubers photo`, `future of the youtube`.
- Acepta: `Smosh`, `Minecraft`, `Chernobyl`, `aurora borealis solar particles photograph`, `test query`, `early YouTube vlogs image` (esta última es semiconcreta — ver diseño; no está en el set de rechazo obligatorio).
- El guard es conservador: rechaza lo claramente vago/editorial, no pretende demostrar calidad con conteos.
- `deterministic_anchor_coverage_v2` no cambia su comportamiento.

## Alcance

- Vocabulario compartido puro en `contracts/visual_terms.py` (mover `GENERIC_FILLER`, `WEAK_SUPPORT_TERMS`, `tokenize`; añadir `STOPWORDS` guard-only).
- `semantic.py` reexporta los nombres movidos sin cambios de comportamiento.
- Guard puro en `contracts/visual_specificity.py` con diagnósticos (`contentTerms`, `weakTerms`, `anchorTerms`, `verdict`, `reason`).
- Tests focales (reject/accept/paridad/límites).

## Fuera de alcance

- Integración en `script.generator` (prompt, validación, retry) — Slice 2
- Filtro de derivación en `assets/router.py` — Slice 2
- Providers nuevos, generación de imagen, CLIP/multimodal, near-duplicates
- Cambio en `contracts/visual.py` (sin churn de schema)
- Cambio en `deterministic_anchor_coverage_v2`
- Ejecución real/E2E — Slice 3

## Criterios de éxito (Slice 1)

1. Suite focada de especificidad + tests del scorer semántico: `0 failed`.
2. `semantic.py`: diff solo de imports/reexport; comportamiento del scorer intacto.
3. `git diff --check` limpio.
4. Sin integración script/router en este slice.