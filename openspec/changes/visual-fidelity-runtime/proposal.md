# Propuesta: visual-fidelity-runtime

## Contexto

`asset-visual-semantic-fidelity` (COMPLETADO / CLOSED) dejó la evidencia decisiva para integrar un segundo gate visual por píxeles:

- Benchmark de segunda etapa sobre las 38 labels canónicas (16 CLEARLY_RELEVANT / 14 COARSE_BUT_USABLE / 8 FALSE_POSITIVE_OR_UNUSABLE).
- **OpenCLIP `ViT-B-32` / pretrained `laion2b_s34b_b79k`, política de texto P1 (`queryUsed`)** logró **25/30 retained + 7/8 badRejected, ELIGIBLE** (umbral calibrado `0.2296`, leave-one-topic-out 24/30 + 7/8).
- Frente a la API multimodal (`gpt-5.6-luna`, 17/30 + 8/8, coste real `$0.0148366`): decisión **LOCAL_ENCODER_PREFERRED** — el encoder local retiene más assets buenos sin coste, red ni latencia de API.
- El gate de metadata actual (`deterministic_anchor_coverage_v2`) sigue siendo la primera etapa barata: garantiza relevancia de tema gruesa, no fidelidad de píxeles/entidad/escena. El runtime acepta falsos positivos ya identificados (ej. "Smosh fan art", antena nocturna, GIF frame 0 en blanco, diagrama de pista de tenis, workflow Spring Boot, cabaña de pescador, retrato romano, pulpo colgado).

## Objetivo

Integrar OpenCLIP como **segundo gate visual (píxel)** en el pipeline de assets de producción, conservando el gate de metadata como primera etapa barata:

```
provider candidate
→ metadata gate (deterministic_anchor_coverage_v2, sin cambios)
→ download
→ PIXEL GATE (OpenCLIP ViT-B-32 / laion2b_s34b_b79k, P1 = queryUsed)  ← nuevo
→ ACCEPT / REJECT → siguiente candidato
```

Principios:

- **Provider-agnostic**: el gate no conoce providers; evalúa el archivo descargado contra el `queryUsed`.
- **Fracaso suave**: si OpenCLIP/torch no está instalado, el modelo no carga o el dispositivo no está disponible → **bypass explícito** del gate con warning y telemetría (no bloquea el pipeline).
- **Dependencia opcional**: NO se infla la instalación base (`requirements.txt`); se documenta un extra opcional.
- **Umbral configurable y versionado**: `0.2296` es un resultado de calibración del benchmark, NO un umbral de producción por defecto. El runtime exige threshold explícito (config/env) para activar el gate.
- **Modelo lazy y cacheado una sola vez por proceso**; CUDA automático con fallback CPU.
- **GIF**: evalúa explícitamente el frame 0, sin mutar el archivo.

## Fuera de alcance

- OpenAI/VLM; Slice 3B de `asset-visual-semantic-fidelity` (escalado selectivo/API).
- Nuevos providers, generación de imagen.
- `search-vs-generation` (dirección de producto separada).
- `deterministic_anchor_coverage_v3` / `FORM_OR_MEDIUM_TERMS` / `asset-entity-fidelity`.
- UI.
- Implementación del runtime en la sesión de planificación (solo OpenSpec + contexto de proyecto).

## Criterios de éxito

1. Segundo gate operativo: `metadata gate → pixel gate → ACCEPT/REJECT → siguiente candidato`.
2. Modelo OpenCLIP `ViT-B-32 / laion2b_s34b_b79k`, texto P1 = `queryUsed`.
3. `0.2296` NO hardcodeado como threshold de producción; threshold explícito y versionado.
4. Fracaso suave (ausencia/fallo de OpenCLIP o CUDA) documentado y con telemetría; bypass sin romper el pipeline.
5. Modelo cargado una vez por proceso.
6. GIF evaluado en frame 0.
7. Tests sin pesos ni descargas.
8. Suite completa verde al cierre.
