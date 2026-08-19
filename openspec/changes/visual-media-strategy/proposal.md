# Propuesta: visual-media-strategy

**Status: COMPLETED / VERIFIED / CLOSED**

## Contexto

El pipeline V2 actual materializa solo imágenes, aunque Pexels Photos/Video ya
tienen evidencia de provider fit complementaria. El VisualPlan describe forma
visual, pero no puede expresar una preferencia editorial de medio sin acoplarse
a proveedores. La policy del job tampoco separa restricciones de usuario de la
intención editorial.

## Objetivo

Separar responsabilidades para que una evolución posterior permita coexistir
imágenes y clips de vídeo por segmento:

```text
VisualPlan -> intención editorial
Job policy -> restricciones explícitas del usuario
MediaStrategy -> resolución y degradaciones auditables
Provider capabilities -> infraestructura concreta
```

El provider no lo decide el LLM. `request.visuals.sourceProviders` permanece
como policy explícita de usuario/operación y se intersectará con capabilities
en un routing posterior.

## Slice 1: foundation pura

- Añadir `visualSequence[].mediaPreference` opcional al VisualPlan v2:
  `IMAGE_PREFERRED | VIDEO_PREFERRED | EITHER`.
- Canonicalizar su ausencia histórica a `IMAGE_PREFERRED` sin subir schema
  version ni reescribir metadata persistido.
- Definir normalización pura de `request.visuals.visualMode`:
  `AUTO | IMAGES_ONLY | VIDEOS_ONLY | MIXED`.
- Definir decisión pura `MediaStrategyDecision`, incluyendo degradaciones
  explícitas.
- Registrar capabilities estáticas conocidas sin secretos ni claims de runtime.
- Documentar y probar compatibilidad image-only.

## Slice 2A: candidate contracts

- Separar soporte de forma visual de disponibilidad runtime en
  `MediaStrategyDecision`.
- Crear `CandidateEnvelope`, `CandidateAttempt`, `CandidateSelectionResult` y
  top-N puro, sin I/O ni routing productivo.

## Slice 2B: wiring conservador

- Adaptar Wikimedia/Pixabay al lifecycle IMAGE first-accepted existente.
- Mantener provider/query order, gates, failover, shapes públicos y semántica
  legacy de status.

## Fuera de alcance original de Slice 1

- Routing productivo, executor, providers, candidate selection o diversity.
- Estos puntos quedaron limitados a contracts en Slice 1; el wiring conservador
  de candidate selection se realizó solo en Slice 2B.

## Fuera de alcance total del change

- Runtime Pexels, clips VIDEO, probing, prepare o renderer.
- Capability routing productivo, prompt LLM produciendo `mediaPreference` y
  CLI/UI para `visualMode`.
- Reranking, diversity, pools cross-provider y generated/manual ejecutables.

## Criterios de éxito

- Un VisualPlan histórico sin `mediaPreference` canonicaliza a
  `IMAGE_PREFERRED` bajo schema v2.
- Jobs sin `visualMode` conservan `IMAGES_ONLY` efectivo.
- Conflictos entre `mode: images` histórico y `visualMode` fallan explícitamente.
- Los casos arquitectónicos A-D producen decisiones/degradaciones auditables.
- Pexels Photos y Video son capabilities separadas y ambas `PLANNED`.
