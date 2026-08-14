# Modular V2 Transformation Roadmap

**Creado:** 2026-07-17
**Última actualización:** 2026-08-14
**Estado:** retiro V1 completado (change `retire-legacy-visual-v1` cerrado); modularización pendiente de inicio

## 1. Estado actual y motivación

shorts-creator es un generador de vídeos cortos verticales con duración y producción configurables. Los scripts de ejecución están en `bin/`, Docker se usa para render, y n8n actúa como orquestador legacy.

El proyecto arrancó con un enfoque centrado exclusivamente en contenido histórico. A lo largo de las iteraciones, VisualPlan V1 fue el contrato visual inicial. VisualPlan V2 lo reemplazó con un contrato más robusto, neutral y extensible. Visual V1 ya no es un producto ni una variante ejecutable soportada. Visual Plan V2 es el contrato visual canónico. La clasificación y rechazo defensivo de metadata legacy permanece en el runner.

La dualidad histórica generó:

- Duplicación de contratos y código
- Ramificación excesiva en scripts y tests
- Contexto innecesario para agentes
- Vínculo artificial con un caso de uso específico (historia)

El objetivo es transformar el repositorio progresivamente hacia una arquitectura modular con un pipeline V2 como único contrato soportado, conservando lo que funciona y sin reescribir desde cero.

## 2. Decisión de no reescribir desde cero

El repositorio actual contiene:

- Tests útiles y estabilizados
- Contratos runtime probados
- E2E que validan el pipeline completo
- Correcciones ya estabilizadas (pacing, Docker, assets)
- Compatibilidad temporal del CLI en `bin/`

Reescribir desde cero perdería todo esto. En su lugar, se transformará progresivamente:

1. Se retira lo obsoleto (V1, defaults históricos)
2. Se estabiliza un pipeline limpio V2
3. Se crea la estructura modular destino
4. Se migra dominio a dominio
5. Se reduce `bin/` a adaptadores

Cada paso es verificable y reversible.

## 3. Arquitectura objetivo

```
shorts-creator/
├── pyproject.toml
├── src/
│   └── shorts_creator/
│       ├── contracts/
│       │   ├── job.py
│       │   ├── states.py
│       │   ├── duration.py
│       │   ├── visual.py
│       │   ├── audio.py
│       │   └── validation.py
│       ├── pipeline/
│       │   ├── orchestrator.py
│       │   ├── stage.py
│       │   ├── results.py
│       │   └── registry.py
│       ├── script/
│       │   ├── service.py
│       │   ├── models.py
│       │   ├── budgets.py
│       │   ├── validation.py
│       │   ├── llm_client.py
│       │   └── prompts/
│       ├── audio/
│       │   ├── service.py
│       │   ├── timing.py
│       │   ├── probing.py
│       │   ├── narration.py
│       │   └── providers/
│       ├── assets/
│       │   ├── service.py
│       │   ├── routing.py
│       │   ├── planning.py
│       │   ├── validation.py
│       │   └── providers/
│       ├── rendering/
│       │   ├── service.py
│       │   ├── timeline.py
│       │   ├── manifest.py
│       │   ├── ffmpeg.py
│       │   ├── subtitles.py
│       │   └── preparation.py
│       ├── validation/
│       │   ├── service.py
│       │   ├── gates.py
│       │   ├── audio.py
│       │   ├── assets.py
│       │   ├── subtitles.py
│       │   └── pacing.py
│       └── infrastructure/
│           ├── metadata_store.py
│           ├── paths.py
│           ├── subprocesses.py
│           ├── docker.py
│           ├── environment.py
│           └── clock.py
├── bin/
│   └── adaptadores CLI temporales
├── tools/
│   └── benchmarks y utilidades de desarrollo
└── tests/
    ├── unit/
    ├── integration/
    ├── contract/
    └── e2e/
```

Esta estructura es el **mapa de destino**. No todos los archivos se crean en la primera migración.

## 4. Reglas de dependencia

### contracts/

- Contratos compartidos, enums, estados y resultados
- Sin dependencias de Docker, FFmpeg, filesystem, providers ni CLI

### pipeline/

- Coordina las etapas
- No implementa TTS, búsqueda de assets, FFmpeg ni validaciones internas

### Dominios (script, audio, assets, rendering, validation)

- Contienen su lógica propia
- Pueden depender de contracts e interfaces técnicas
- Nunca importan desde `bin/`

### infrastructure/

- Implementa metadata, paths, subprocess, Docker, entorno y reloj
- No contiene reglas de negocio

### bin/

- Mantiene temporalmente compatibilidad de CLI, Docker y E2E
- Debe terminar como una capa de adaptadores pequeños
- No recibe nueva lógica una vez migrado el dominio correspondiente

### tools/

- Benchmarks, fixtures y utilidades no pertenecientes al runtime

## 5. Orden de transformación

| # | Fase | Cambio OpenSpec | Dependencias | Progreso |
|---|------|----------------|--------------|----------|
| 1 | Retirar V1 y enfoque histórico | `retire-legacy-visual-v1` | Ninguna | **Completado** (Slices 1-6 cerrados; change cerrado) |
| 2 | Estabilizar pipeline V2, baseline clara | (continuación del anterior) | Fase 1 | Completado — baseline `1181 passed, 0 failed`; quinto E2E validó script V2 PASS + assets V2; full-E2E diferido por `AUDIO_DURATION_MISSING` (fuera de scope) |
| 3 | Crear pyproject.toml y src/shorts_creator/ | (futuro) | Fase 2 | Pendiente (no iniciado todavía) |
| 4 | Extraer contracts/ e infrastructure/ | (futuro) | Fase 3 | Pendiente |
| 5 | Migrar script/ | (futuro) | Fase 4 | Pendiente |
| 6 | Reanudar audio pacing (Phase B) | `improve-short-form-audio-pacing-v2` | Fase 5 | Pendiente |
| 7 | Migrar audio/ | (futuro) | Fase 6 | Pendiente |
| 8 | Migrar assets/ | (futuro) | Fase 7 | Pendiente |
| 9 | Migrar rendering/ | (futuro) | Fase 8 | Pendiente |
| 10 | Migrar validation/ | (futuro) | Fase 9 | Pendiente |
| 11 | Reducir bin/ a adaptadores, limpieza final | (futuro) | Fase 10 | Pendiente |

Cada fase futura tendrá su propio change OpenSpec.

## 6. Relación entre changes futuros

```
retire-legacy-visual-v1
    └── improve-short-form-audio-pacing-v2 (reanudado)
        └── migrate-script-domain (futuro)
            └── migrate-audio-domain (futuro)
                └── migrate-assets-domain (futuro)
                    └── migrate-rendering-domain (futuro)
                        └── migrate-validation-domain (futuro)
                            └── reduce-bin-to-adapters (futuro)
```

Los changes son secuenciales y dependen del anterior. Cada uno produce una baseline verificable.

## 7. Política de compatibilidad de bin/

`bin/` es la capa de compatibilidad temporal:

- **Migración pendiente:** `bin/` contiene la lógica completa del dominio
- **Durante migración:** `bin/` delega a `src/shorts_creator/` vía adaptadores
- **Tras migración:** `bin/` contiene solo adaptadores CLI delgados
- **Final:** `bin/` se reduce a entradas mínimas que invocan la librería

No se añade nueva lógica a `bin/` una vez que el dominio correspondiente migra.

## 8. Política de jobs V1

Los jobs existentes con metadata V1:

- Se conservan en `data/` sin migración automática
- No pueden re-ejecutarse por el pipeline canónico
- Se rechazan con `UNSUPPORTED_LEGACY_SCHEMA` mediante el clasificador defensivo en `run_job.py`
- Sus artefactos (renders, audio, metadata) permanecen como historial

La clasificación y rechazo defensivo de metadata legacy es el único código V1 que permanece en el runtime.

## 9. Estrategia de tests

- **Tests unitarios:** por dominio, usando mocks para dependencias externas
- **Tests de integración:** verifican contratos entre dominios
- **Tests de contrato:** validan schemas y estados
- **Tests E2E:** ejecutan el pipeline completo con datos reales

Durante la migración:

- Tests existentes se conservan y adaptan
- Cada slice produce tests focalizados
- La suite completa se ejecuta al cierre de cada change
- Se mantiene la baseline: `1215 passed, 16 failed (preexistentes)`

## 10. Relación con consumo de contexto y modelos gratuitos

La transformación modular reduce directamente el consumo de contexto de agentes:

- Menos código duplicado → menos archivos que leer
- Contratos explícitos → menos ambigüedad en instrucciones
- Dominios aislados → menos propagación de cambios
- Documentación clara → menos iteraciones para tareas simples

Benchmark R1 (cerrado, commit `4d1715f`) documenta modelos gratuitos aptos para tareas de planificación y código. La reducción de contexto mejora la efectividad de estos modelos al limitar lo que necesitan cargar.

Referencia: `docs/research/opencode-free-models-benchmark-r1.md`

## 11. Riesgos y criterios de parada

### Riesgos

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Tests V1 compartidos se rompen | Alto | Revisar dependencias antes de cada slice |
| Helpers V1 usados implícitamente por V2 | Alto | Búsqueda de dependencias antes de retirar |
| E2E depende de V1 | Alto | Ejecutar E2E V2 canónico como validación |
| Complejidad de migración subestimada | Medio | Fases pequeñas, verificables, reversibles |
| Regresiones no detectadas | Medio | Suite completa al cierre de cada change |

### Criterios de parada

- Más de 10 tests nuevos fallando tras un slice
- E2E V2 canónico no pasa tras 3 intentos de corrección
- Complejidad de un slice excede lo estimado en más de 2x
- Decisión de diseño no resuelta en una sesión

## 12. Estado de Phase B (audio pacing) como trabajo pausado

El change `improve-short-form-audio-pacing-v2` tiene Phase A completada y Phase B pendiente.

- **Phase A** (completada 2026-07-14): Corrección de Docker ffprobe, medición real de duración, escena windows derivados del audio activo, validación de pacing
- **Phase B** (pausada): Calibración de voz/WPM, word budget, Edge TTS rate, E2E 27–30s

Phase B se reanudará **después de migrar el dominio script** a la arquitectura modular (fase 5). Esto permite:

- Trabajar sobre código modular en lugar de scripts monolíticos
- Aprovechar los contratos extraídos en `contracts/` y `script/`
- Evitar conflictos con la migración de `bin/`

El change permanece en estado pausado, no cerrado ni eliminado.
