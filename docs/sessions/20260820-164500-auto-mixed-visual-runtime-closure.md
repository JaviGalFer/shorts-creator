# Session — Cierre formal de `auto-mixed-visual-runtime`

- **Sesión:** `auto-mixed-visual-runtime-closure`
- **Modelo:** DeepSeek V4 Flash
- **Modo:** Build / Slice 2 + E2E + Closure
- **Fecha:** 2026-08-20
- **Objetivo:** completar Slice 2 (hardening + smoke mixto + E2E AUTO/MIXED) y
  cerrar formalmente `auto-mixed-visual-runtime` (solo merge autorizado pendiente).

## 1. Estado Git inicial

- Rama `change/auto-mixed-visual-runtime`; HEAD `ae3a3d6` (Slice 1).
- Working tree limpio (solo `data/postgres/` ignorado); baseline `1843 passed`.

## 2. Hardening (Slice 2)

- **A** — Prompt sin contradicción: se eliminó `photograph` de la query del JSON
  de ejemplo del SYSTEM_PROMPT (`aurora borealis solar particles atmosphere`).
  Rules de queries medium-neutral intactas; `assetPreference=photograph` sigue
  siendo un enum válido (solo las SEARCH QUERIES son medium-neutral).
- **B** — Reconciliación de `mediaDecision` con los media kinds que sobreviven a
  constraints/source policy: `_resolve_segment_media_strategy` acepta
  `runtime_override`; el router construye grupos por kind, calcula `surviving` y
  re-resuelve la estrategia con esos kinds antes de ordenar niveles. Así, una
  source policy que excluye Pexels reconcilia `resolvedKind=IMAGE` y no notifica
  `PREFERRED_MEDIA_EXHAUSTED` (ese reason queda reservado para kind primario
  permitido que agotó candidatos en runtime).
- **C** — `mediaDecision` preservado en TODOS los terminales del executor:
  SEMANTIC POSTCONDITION, PROVIDER_UNAVAILABLE (all-unavailable y no-candidates)
  y dry-run unresolved pasan por `_apply_media_decision_outcome`. Unresolved no
  inventa `mediaFallback=true`; solo un RESOLVED con kind real ≠ resolvedKind es
  fallback runtime.
- **D** — Guard `MEDIA_PREFERENCE_MISSING` estricto bajo AUTO/MIXED (generación,
  retries, validación final); design.md actualizado (no se tolera silenciosamente).
  Planes históricos persistentes siguen con el default IMAGE_PREFERRED.

## 3. Mixed local render smoke (offline)

Job `mixed-local-smoke` (temp): 3 escenas (IMAGE/VIDEO/IMAGE) con audio sintético
y dóker ffmpeg local. `prepare → render → validate` **PASS**: timeline correcto
sin gaps, IMAGE rama IMAGE, VIDEO rama VIDEO (trim), output h264 **1080x1920**
**19.08s**, un único audio (narración), sin audio del vídeo fuente, manifest
visualType image/video/image, `resolvedConfig.visuals.visualMode=MIXED`.

## 4. Real E2Es

- **AUTO** `cmo-2026-08-20-152730` — VALIDATED; 9/9 resolved, 8 IMAGE + 1 VIDEO;
  mediaPreference explícito (sin default histórico); mediaDecision==mediaKind
  (sin fallback).
- **Real MIXED runtime run** `por-2026-08-20-153502` — ASSETS_PARTIAL (9/10); mezcla editorial
  5 IMAGE + 4 VIDEO; 1 ilustración pixabay sin cobertura supply. Sin overwrite de
  preferencias fuertes, sin degradar diagramas, sin cuota.
  - `cmo-2026-08-20-153101` (rayos): bloqueado en audio `DURATION_FITTING_EXHAUSTED`
    (fitting de duración, no runtime de medios).
  - `cmo-2026-08-20-153259` (pulpos): ASSETS_PARTIAL con mezcla 4 VIDEO + 2 IMAGE
    (provee evidencia adicional del mecanismo MIXED).

## 5. Verificación LLM

AUTO y MIXED ya NO producen `mediaPreference` por default histórico: todos los
segmentos llevan preferencia explícita (EITHER / IMAGE_PREFERRED /
VIDEO_PREFERRED). Ninguna default/missing.

## 6. Suite y validación

- Full suite final: `1849 passed, 0 failed`; `git diff --check` limpio.

## 7. Cierre

`auto-mixed-visual-runtime` — COMPLETED / VERIFIED / CLOSED, **pending authorized
merge**. Sin merge, push, reindex. No se abre siguiente change.
