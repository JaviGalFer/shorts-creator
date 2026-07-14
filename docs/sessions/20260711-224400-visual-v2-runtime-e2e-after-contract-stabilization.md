# Runtime E2E Visual v2 — stabilize-visual-v2-runtime-contracts

**Sesión:** 2026-07-11T22:44 — E2E live post-contract-stabilization
**Modelo:** DeepSeek V4 Pro
**Modo:** Build (no code changes)
**Job ID:** `e2e-arcoiris-20260711-225029`

---

## Tema

Cómo se forma un arcoíris — 3 escenas, 5 segmentos totales.

## Clasificación final

**E2E_BLOCKED**

---

## Pipeline ejecutado

### Etapa 1: fetch_images_v2

| Campo | Valor |
|-------|-------|
| Comando | `python3 bin/fetch_images_v2.py data/videos/e2e-arcoiris-20260711-225029/metadata.json --user-agent "shorts-creator-e2e/1.0"` |
| Exit code | 0 |
| Status | ASSETS_PARTIAL |
| Resolved | 2/5 |
| Failed | 3/5 |

**Assets resueltos (2/5):**

| Scene | Seg | Path | Dimensiones | Provider |
|-------|-----|------|-------------|----------|
| 2 | 2 | `assets/scene_002_seg_002.jpg` | 960×720 | wikimedia_commons |
| 3 | 1 | `assets/scene_003_seg_001.jpg` | 1360×2048 | wikimedia_commons |

**Assets fallidos (3/5):**

| Scene | Seg | Error |
|-------|-----|-------|
| 1 | 1 | no candidate passed minimum filters |
| 2 | 1 | no candidate passed minimum filters |
| 3 | 2 | no candidate passed minimum filters |

Se realizaron 6 intentos en jobs distintos variando queries de Wikimedia Commons. El mejor resultado fue 3/5 (primer intento). Ningún intento consiguió 5/5. El provider Wikimedia Commons devuelve resultados inconsistentes entre ejecuciones, y varias queries no producen candidatos que superen el filtro dimensional 720×720.

### Etapa 2: generate_audio

| Campo | Valor |
|-------|-------|
| Comando | `python3 bin/generate_audio.py data/videos/e2e-arcoiris-20260711-225029/metadata.json` |
| Exit code | 1 |
| Status | REVIEW_REQUIRED |
| Error | AUDIO_DURATION_MISSING — las 3 escenas sin durationSec |

**Causa raíz:** `bin/generate_audio.py:1480` (y también `bin/render_job.py:709`, `bin/validate_job.py:673`) hardcodean `os.environ['DOCKER_API_VERSION'] = '1.43'`, pero el Docker daemon del entorno requiere mínimo `1.44`. La función `_get_mp3_duration()` usa Docker para ffprobe y falla silenciosamente con:

```
docker: Error response from daemon: client version 1.43 is too old.
Minimum supported API version is 1.44
```

**Workaround aplicado:** Las duraciones se sondearon manualmente con `DOCKER_API_VERSION=1.44` y se inyectaron en metadata:

| Scene | Audio duration | Target | SceneWindowSec |
|-------|---------------|--------|----------------|
| 1 | 10.272s | 10s | 10.272 |
| 2 | 12.192s | 12s | 12.192 |
| 3 | 12.048s | 12s | 12.048 |

### Etapa 3: prepare_job

| Campo | Valor |
|-------|-------|
| Comando | `python3 bin/prepare_job.py data/videos/e2e-arcoiris-20260711-225029/metadata.json` |
| Exit code | 1 |
| Status | ASSET_UNRESOLVED |
| Failures | 4 |

**Fallos detectados:**

```
SEGMENT_ERROR: scene 1 seg 1 → "no candidate passed minimum filters"
SEGMENT_ERROR: scene 2 seg 1 → "no candidate passed minimum filters"
SEGMENT_ERROR: scene 3 seg 2 → "no candidate passed minimum filters"
SCENE_NOT_SELECTED: scene 1 → selected=False
```

**Primer fallo real del pipeline:** prepare_job bloquea con `ASSET_UNRESOLVED` porque 3/5 segmentos carecen de asset y la escena 1 no está seleccionada.

### Etapas 4 y 5: render_job / validate_job

No ejecutadas — bloqueadas por prepare_job.

---

## Verificaciones aplicables

| Check | Resultado |
|-------|-----------|
| Assets Wikimedia resueltos | Parcial (2/5, paths únicos `scene_XXX_seg_XXX.ext`) |
| Asset menor que contrato v2 (720×720) | Ninguno bajo — los 2 resueltos cumplen |
| `audio.scenes[].durationSec` positivo | Sí (10.272, 12.192, 12.048) — inyectado manualmente |
| Video generado | No |
| Resolución 1080×1920 | N/A |
| Stream de audio | N/A |
| Asset validation no BLOCKED | BLOCKED — ASSET_UNRESOLVED en prepare_job |
| Preflight | No alcanzado |
| Subtítulos | No generados |

---

## Primer fallo real

**Etapa:** `prepare_job`
**Comando:** `python3 bin/prepare_job.py data/videos/e2e-arcoiris-20260711-225029/metadata.json`
**Exit code:** 1
**Status:** ASSET_UNRESOLVED
**Mensaje:** 3 segmentos sin asset + 1 escena no seleccionada. Los 3 segmentos fallaron en `fetch_images_v2` con `no candidate passed minimum filters`. La escena 1 quedó con `selected=False` porque su único segmento falló.

**Causa raíz:** El pipeline no puede resolver 5/5 assets desde Wikimedia Commons live en una sola ejecución. El provider `resolve_wikimedia_candidate_v2` selecciona el primer candidato que supera el filtro 720×720 por query. Con múltiples segmentos en la misma escena compartiendo `searchQueries`, segmentos posteriores no encuentran candidatos adicionales que cumplan el filtro. Además, las queries usadas (`sun`, `prism`, `rainbow`) devuelven resultados inconsistentes sujetos a rate-limiting (HTTP 429) de Wikimedia Commons.

## Corrección mínima recomendada

**1.** Cambiar `DOCKER_API_VERSION = '1.43'` → `'1.44'` en:
- `bin/generate_audio.py:1480`
- `bin/generate_audio.py:1209` (main_continuous)
- `bin/render_job.py:709`
- `bin/validate_job.py:673`

**2.** Para resolver el bloqueo de assets, el executor debería iterar sobre múltiples candidatos del mismo query y excluir los ya descargados, en lugar de seleccionar siempre el primero. Esto requiere modificar `visual_asset_executor_v2.py:_try_live_resolution` para aceptar un parámetro `exclude_urls` o similar.

---

## Artifacts conservados

```
data/videos/e2e-arcoiris-20260711-225029/
├── metadata.json
├── assets/
│   ├── scene_002_seg_002.jpg  (30 KB,  960×720)
│   └── scene_003_seg_001.jpg  (3.7 MB, 1360×2048)
└── scenes/
    ├── scene-01.mp3  (61 KB, 10.272s)
    ├── scene-02.mp3  (73 KB, 12.192s)
    └── scene-03.mp3  (72 KB, 12.048s)
```

Sin video.mp4, sin subtitle.ass.
