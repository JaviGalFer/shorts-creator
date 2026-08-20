# Propuesta: auto-mixed-visual-runtime

**Estado: COMPLETED / VERIFIED / CLOSED — pending authorized merge.**

## Contexto

`pexels-video-runtime-mvp` (COMPLETADO / CLOSED) dejó VIDEO productivo bajo VIDEOS_ONLY:

- El renderer ya soporta timeline IMAGE + VIDEO (encode vertical 1080x1920, `-stream_loop -1` + normalize para VIDEO, imagen con Ken Burns para IMAGE).
- `pexels.video.stock` es `AVAILABLE` (opt-in explícito vía `--asset-providers pexels --visual-mode videos-only`).
- Contracts puros ya existen: `visualMode` (AUTO/IMAGES_ONLY/VIDEOS_ONLY/MIXED), `mediaPreference` (IMAGE_PREFERRED/VIDEO_PREFERRED/EITHER) y `MediaStrategyDecision`.

Hallazgo real: en los E2E VIDEOS_ONLY el LLM emitía `mediaPreference = IMAGE_PREFERRED` en todos los segmentos, y era la policy dura del usuario (VIDEOS_ONLY) quien lo corregía por override. El prompt de generación **no pide nunca `mediaPreference`**: la tabla de `visualSequence[]` del system prompt solo documenta `segmentIndex, assetPreference, durationFraction, searchQuery, transition`, y el canonicalizer aplica el default histórico `IMAGE_PREFERRED` (visual.py `OPTIONAL_SEGMENT_DEFAULTS`). Consecuencia:

- AUTO/MIXED degeneran de facto a IMAGES_ONLY (todos los segmentos rutean IMAGE).
- No existe fallback cross-media en ejecución: el router resuelve un único `mediaKind` por segmento y el executor solo maneja fallback entre providers del mismo kind.
- MIXED no es distinto de AUTO: `mixed_diversity_preferred` solo existe en el contrato puro, ningún runtime lo consume.

## Objetivo

Hacer productivos AUTO y MIXED: que un mismo vídeo pueda combinar assets IMAGE y VIDEO por segmento según intención editorial del LLM, con routing y fallback cross-media mínimos, sin debilitar las constraints duras de usuario (IMAGES_ONLY / VIDEOS_ONLY).

**Principio rector:** AUTO/MIXED MUST USE EDITORIAL MEDIA PREFERENCE WITHOUT WEAKENING HARD USER CONSTRAINTS.

## Alcance

1. Prompt V2: cada `visualSequence[]` emite explícitamente `mediaPreference` con semántica editorial; contexto según `visualMode`; guardia anti-ausencia bajo AUTO/MIXED.
2. Neutralización de wording de medio en queries para VIDEO (`medium_neutral_query`), sin provider-specific query adaptation.
3. Router multi-kind: niveles de medio (preferred → fallback compatible) preservando el orden de `sourceProviders` dentro de cada nivel.
4. Fallback cross-media en runtime reutilizando el executor actual (`providerCandidates` por `priority`), con `mediaFallback` y reason `PREFERRED_MEDIA_EXHAUSTED`.
5. Persistencia aditiva de `mediaDecision` (reusando `MediaStrategyDecision`) a través de router → executor → bridge → `metadata.assets[].segments[]`.
6. MIXED best-effort: contadores de assets seleccionados (selected-only) para tie-break de diversidad en segmentos EITHER, sin cuotas ni optimizer global.

## Fuera de alcance

- Script quality / watchability (mejora narrativa queda registrada como observación futura).
- Provider-specific query adaptation (adaptadores provider-agnósticos únicamente).
- Video semantic vision (OpenCLIP/VLM sobre VIDEO; el pixel gate sigue siendo IMAGE-only).
- Candidate reranking.
- Generated images / manual uploads.
- UI / web.
- Renderer FFmpeg (sigue soportando IMAGE/VIDEO; solo se añadirá fixture mixto en Slice 2).

## Slice 1 (esta sesión)

Decisiones editoriales + routing + fallback + persistencia (offline/mocked):

- Prompt `mediaPreference` real + guardia `MEDIA_PREFERENCE_MISSING`.
- `medium_neutral_query` + `queryUsed` efectivo para VIDEO.
- Router multi-kind con pesos y sourceProviders por nivel.
- Executor `mediaFallback` / `PREFERRED_MEDIA_EXHAUSTED` / propagación de `mediaDecision`.
- Bridge `mediaDecision` / `mediaFallback`.
- MIXED tracker selected-only (tie-break EITHER).

## Slice 2 (futura, no en esta sesión)

Runtime real + E2E:

- Hardening executor / restricciones de modo duro.
- Regression mixta IMAGE/VIDEO prepare/render (fixture).
- Real AUTO E2E y real MIXED E2E.
- Docs/closure.