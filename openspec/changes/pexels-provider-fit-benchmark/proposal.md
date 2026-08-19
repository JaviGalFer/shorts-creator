# Propuesta: pexels-provider-fit-benchmark

**Status: IN_PROGRESS** — investigación benchmark-first (research-only), sin
integración de runtime. Objetivo: determinar CUÁNDO Pexels Photos/Video son
providers adecuados para un segmento y si una adaptación determinista de query
mejora Pexels Video en los casos stock-compatible.

## Contexto

`pexels-visual-supply-benchmark` (CLOSED) midió el SUPPLY técnico de Pexels
Video+Photos sobre las 56 queryUsed persistidas: cobertura 56/56 HIGH_SUPPLY
(>=720x1280 y >=1080x1920 = 1.0) y decidió **`PEXELS_CONDITIONAL_PROVIDER_PROMISING`**.
La revisión humana concluyó: Pexels es prometedor para photography/sujetos
físicos/lugares/personas/objetos/B-roll tech/server; **NO fiable** para visual
forms explícitos (diagram/infographic/illustration/plans/construction-time).

Ese cierre registró como **dirección siguiente (no implementada)**
`pexels-provider-fit-benchmark`: elegibilidad por visual intent + assetPreference,
Photos para intents photographic, Video con adaptación determinista de query,
RAW vs adapted, top-N vs rank#1, overlap entre escenas; benchmark-first.

Este cambio implementa esa investigación. NO toca runtime.

## Objetivo

1. Aislar qué combinación de preferencia de asset / intent / forma de query
   hace a un segmento **stock-compatible** para Pexels.
2. Definir una **política provisional** de provider-fit (regla pura,
   evaluation-only) que distinga `photograph` (stock-compatible) de
   `diagram`/`infographic`/`illustration`/`painting` (explicit form, NO
   stock-compatible como satisfacción directa) y de casos `UNDECIDED`.
3. Comprobar si una **adaptación determinista** de query (eliminar solo
   `photograph`/`photo`/`photography`) mejora el supply/overlap de Pexels Video
   para las queries `photograph` sin perder sujeto/variante/acción.
4. Dejar evidencia visual (3 contact sheets) para **revisión humana externa**
   que decida por query: Photos CURRENT vs PEXELS; Video RAW vs ADAPTED.
5. NO afirmar todavía `PROVIDER_FIT_VALIDATED`, `ADAPTED_BETTER` ni "Pexels
   por defecto".

## Alcance

- Reutiliza los 58 rows persistidos (canonical 38 + development 20; 56
  queryUsed) y la evidencia RAW ya persistida de Photos y Video (sin nuevas
  search requests Photos).
- **Solo** requests nuevas: Pexels Video con queries ADAPTADAS (cap 40).
- Herramienta nueva `tools/pexels_provider_fit_benchmark.py` + tests offline.
- NO integra providers de producción, NO modifica rendering, NO modifica
  VisualPlan/schema, NO OpenCLIP/BLIP/VLM, NO generación de imágenes, NO
  implementa perceptual hash / near-duplicate ML.

## Fuera de alcance

- Decisión final de integración de Pexels.
- Matriz compleja intent×assetPreference (se mide primero si assetPreference /
  forma de query explica ya el fit).
- Perceptual hash / near-duplicate vision.
- Relabel de datasets.