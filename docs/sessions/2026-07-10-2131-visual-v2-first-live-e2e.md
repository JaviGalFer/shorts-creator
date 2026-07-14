# Session: Visual v2 First Live E2E — Rainbow

**Created:** 2026-07-10 21:31 UTC
**Type:** Build / E2E execution
**OpenSpec change:** `improve-historical-visual-pipeline` (already active)

## 1. Tipo de E2E realizado

**Runtime E2E starting from canonical v2 metadata.**

`generate_script.py` produce exclusivamente visualPlans v1 legacy con `editorialRole`, `strategy`, `primaryAssetType`, etc. No genera `_schemaVersion == 2`. Por tanto, el pipeline completo desde `generate_script` no puede producir v2 sin cambios de código. Se creó metadata v2 manual canónico y se ejecutó el runtime pipeline desde ese punto.

## 2. Razón de esa elección

- `generate_script.py` (line 38) tiene un `SYSTEM_PROMPT` hardcodeado que define campos v1 legacy (`editorialRole`, `strategy`, `primaryAssetType`, `visualTemporalIntent`, etc.) y nunca inyecta `_schemaVersion`.
- `run_job.py` detecta correctamente v2 (via `_uses_v2_visual_assets`) pero el script generado es v1, por lo que `run_job.py --topic` enrutaría a `fetch_images.py` (v1).
- La metadata v2 se construyó manualmente siguiendo exactamente el schema canonical de `visual_plan_v2.py`.

## 3. Tema y jobId

**Tema:** Cómo se forma un arcoíris
**Idioma:** español (es-ES)
**Formato:** vertical 9:16

### Primer intento (audit trail)
- **jobId:** `e2e-v2-rainbow-20260710-212743`
- **Path:** `data/videos/e2e-v2-rainbow-20260710-212743/`
- **Escenas:** 4, **Segmentos:** 7
- **Resultado fetch_images_v2:** ASSETS_PARTIAL (6/7 resolved, 1 failed)
- **Causa del fallo:** Colisión de nombres de archivo cross-scene. El executor usa `segmentIndex` como prefijo de filename sin scope de escena. Con 4 escenas y 3+ segmentos con index=1, las extensiones `.jpg`, `.gif`, `.png` se agotan. Scene 4 Seg 1 falla con `DOWNLOAD_FAILED: file already exists`.
- **prepare_job:** Bloqueado en ASSET_UNRESOLVED (segment unresolved).

### Segundo intento (retry)
- **jobId:** `e2e-v2-rainbow-20260710-213023`
- **Path:** `data/videos/e2e-v2-rainbow-20260710-213023/`
- **Escenas:** 3 (reestructurado para evitar colisiones de filename), **Segmentos:** 5
- **Resultado fetch_images_v2:** ASSETS_READY (5/5 resolved)

## 4. Metadata inicial (retry job)

3 escenas con voiceover en español:

| Escena | Voiceover | Segs | Prefs |
|--------|-----------|------|-------|
| 1 | "¿Sabes cómo se forma realmente un arcoíris? No es magia, es un fenómeno de la luz." | 1 | photograph |
| 2 | "La luz del sol entra en las gotas de lluvia, se refracta y se descompone en los siete colores del espectro visible." | 2 | diagram, illustration |
| 3 | "El reflejo interno en cada gota crea el arco perfecto que vemos en el cielo. Así se forma un arcoíris." | 2 | photograph, diagram |

Todas las escenas con `_schemaVersion: 2`, sin campos legacy (editorialRole, strategy, primaryAssetType, secondaryAssetType, visualTemporalIntent, style, mood, licenseRequired, visualImportance).

## 5. Configuración de providers

```json
{
  "wikimedia_commons": {"enabled": true, "implemented": true, "live": true},
  "pexels": {"enabled": false, "implemented": false},
  "pixabay": {"enabled": false, "implemented": false},
  "freeai": {"enabled": false, "implemented": false},
  "pollinations": {"enabled": false, "implemented": false}
}
```

- `allowGeneratedImage: false` en todos los visualPlans
- `allowGeneratedImages: false` en `request.visuals`
- `generated` no incluido en `assetPreferences`
- Solo `wikimedia_commons` como provider preferido

## 6. User-Agent utilizado

```
ShortsCreator-E2E/1.0 (https://github.com/anomalyco/shorts-creator; research project)
```

## 7. Comandos exactos y exit codes (retry job)

| Etapa | Comando | Exit Code |
|-------|---------|-----------|
| fetch_images_v2 | `python3 bin/fetch_images_v2.py <meta> --user-agent "ShortsCreator-E2E/1.0 (...)"` | 0 |
| generate_audio | `python3 bin/generate_audio.py <meta>` | 0 |
| prepare_job | `python3 bin/prepare_job.py <meta>` | 0 |
| render_job | `python3 bin/render_job.py <meta>` | 1 (BLOCKED) |

## 8. Transición de statuses por etapa (retry job)

| Etapa | Status antes | Status después |
|-------|-------------|----------------|
| fetch_images_v2 | SCRIPT_DRAFT | ASSETS_READY |
| generate_audio | ASSETS_READY | AUDIO_READY |
| prepare_job | AUDIO_READY | SUBTITLES_READY |
| render_job | SUBTITLES_READY | ASSET_FAILED (BLOCKED) |

## 9. Resultados de Wikimedia

Wikimedia Commons respondió correctamente a todas las queries. Todas las búsquedas devolvieron resultados. Las descargas HTTP fueron exitosas para 5/5 segmentos.

**Problema detectado:** El executor descarga el primer resultado sin filtrar por resolución. Dos GIFs de Wikimedia (700x435) están por debajo del mínimo de asset validation (720x720).

## 10. Assets descargados

| Path | Provider | queryUsed | sourceUrl | License | Dims |
|------|----------|-----------|-----------|---------|------|
| assets/seg_001.jpg | wikimedia_commons | rainbow in the sky after rain photograph | commons.wikimedia.org/wiki/File:The%20clouds%20and%20the%20rainbow%20after%20rain%20in%20Murree.jpg | CC BY-SA 3.0 | 3872x2592 |
| assets/seg_001.gif | wikimedia_commons | visible light dispersion prism spectrum diagram | commons.wikimedia.org/wiki/File:Light%20dispersion%20conceptual.gif | Public domain | 700x435 |
| assets/seg_002.gif | wikimedia_commons | light dispersion prism visible spectrum diagram | commons.wikimedia.org/wiki/File:Light%20dispersion%20conceptual.gif | Public domain | 700x435 |
| assets/seg_001.png | wikimedia_commons | rainbow formation internal reflection diagram | commons.wikimedia.org/wiki/File:Rainbow%20formation.png | CC BY-SA 3.0 | 721x902 |
| assets/seg_002.png | wikimedia_commons | rainbow formation internal reflection diagram | commons.wikimedia.org/wiki/File:Rainbow%20formation.png | CC BY-SA 3.0 | 721x902 |

**Notas:**
- seg_001.gif y seg_002.gif: mismo sourceUrl (archivo duplicado)
- seg_001.png y seg_002.png: mismo sourceUrl (archivo duplicado)
- score=0.0 en todos (sentinel neutral correcto)
- No hay campos legacy en ningún segmento

## 11. Resultado de asset_validation

**Status:** BLOCKED

**Failures:**
- `dimensions_too_small`: assets/seg_001.gif (700x435, both < 720x720)
- `dimensions_too_small`: assets/seg_002.gif (700x435, both < 720x720)

**Summary:**
- totalSegments: 5, validAssets: 3, invalidAssets: 2
- renderBlocked: true
- assetsFromArchive: 5

## 12. Resultado de generate_audio

**Status:** AUDIO_READY

- Provider: Edge TTS
- Voice: es-ES-AlvaroNeural
- 3 archivos MP3 generados: scene-01.mp3 (39KB), scene-02.mp3 (42KB), scene-03.mp3 (45KB)
- 8 cues de subtítulos (WordBoundary)
- Sin errores TTS

## 13. Resultado de prepare_job

**Status:** SUBTITLES_READY

- subtitle.ass generado (1,427 bytes)
- renderTimeline: 5 segmentos (todos con paths assets/seg_XXX.ext)
- Paths preservados como relativos (no transformación a scenes/)
- Sin referencias a archivos inexistentes
- audioReady: true, assetsReady: true

## 14. Resultado de render_job

**Status:** ASSET_FAILED (exit code 1)

- preflight_validate: assets encontrados correctamente (paths resueltos contra video_dir)
- asset_validation: BLOCKED por dimensions_too_small en los GIFs
- video.mp4: NO generado
- Render abortado según contrato

## 15. Resultado de validate_job

No ejecutado (pipeline bloqueado en render).

## 16. Datos de ffprobe

No disponibles (video.mp4 no generado).

## 17. Capturas creadas

No aplica (render bloqueado).

## 18. Reintentos realizados

**1 reintento** (máximo permitido):

| Intento | JobId | Escenas | Segments | Fetch result | Block cause |
|---------|-------|---------|----------|-------------|-------------|
| 1 (original) | e2e-v2-rainbow-20260710-212743 | 4 | 7 | ASSETS_PARTIAL (6/7) | Filename collision cross-scene |
| 2 (retry) | e2e-v2-rainbow-20260710-213023 | 3 | 5 | ASSETS_READY (5/5) | GIF dimensions too small |

**Cambio realizado en el retry:** Solo contenido del job (reducción de 4 a 3 escenas, queries ajustadas). No se modificó código fuente.

## 19. Problemas encontrados

### P1: Colisión de nombres de archivo cross-scene (BLOCKER - intento 1)
- **Archivo:** `bin/visual_asset_executor_v2.py`
- **Descripción:** El executor genera filenames `seg_{segmentIndex}.{ext}` sin scope de escena. Con 4 escenas teniendo todas segmentIndex=1, las 3 extensiones comunes (.jpg, .gif, .png) se agotan y el cuarto intento falla con DOWNLOAD_FAILED.
- **Impacto:** Jobs con 4+ escenas donde 3+ tienen segmentIndex=1 no pueden completar fetch_images_v2.
- **Severidad:** Crítica para pipelines con >3 escenas.

### P2: GIFs de Wikimedia con resolución insuficiente (BLOCKER - intento 2)
- **Archivo:** `bin/visual_provider_wikimedia_v2.py`
- **Descripción:** El provider Wikimedia no filtra resultados por resolución mínima. Descargó GIFs de 700x435 que asset_validation bloquea (mínimo 720x720 en ambas dimensiones).
- **Impacto:** Render bloqueado para cualquier query que devuelva assets pequeños.
- **Severidad:** Bloqueante.

### P3: Assets duplicados (mismo sourceUrl para segmentos distintos)
- **Archivo:** `bin/visual_asset_executor_v2.py` y/o `bin/visual_provider_wikimedia_v2.py`
- **Descripción:** Scene 2 Seg 1 y Seg 2 comparten el mismo sourceUrl (Light dispersion conceptual.gif). Scene 3 Seg 1 y Seg 2 comparten el mismo sourceUrl (Rainbow formation.png). El executor no evita reutilizar el mismo archivo para distintos segmentos.
- **Impacto:** Calidad visual (misma imagen repetida en segmentos consecutivos).
- **Severidad:** Media.

### P4: No hay filtro por score/calidad en Wikimedia
- **Descripción:** El provider no rankea resultados por calidad. El score se deja en 0.0 (sentinel neutral). No hay mecanismo para preferir imágenes de mayor resolución o formato.
- **Impacto:** Baja calidad de selección de assets.
- **Severidad:** Media.

## 20. Confirmación: no se usó --skip-asset-validation

**Confirmado.** `render_job.py` se ejecutó sin `--skip-asset-validation`. El bloqueo es legítimo según las reglas de asset_validation v2.

## 21. Confirmación: no se añadieron campos legacy

**Confirmado.** Verificación recursiva de todos los segmentos en `metadata["assets"]`: cero campos legacy (`editorialRole`, `strategy`, `primaryAssetType`, `secondaryAssetType`, `visualTemporalIntent`, `style`, `mood`, `licenseRequired`, `visualImportance`).

## 22. Confirmación: no se añadieron modos de dominio

**Confirmado.** La metadata no contiene ningún campo de modo (`mode`, `domain`, `category`, `historical`, `science`, `general`, `documentary`, `legacy`). `is_v2` se detecta mecánicamente via `_visualAssetBridgeV2`.

## 23. Confirmación: no se modificó código

**Confirmado.** `git diff --check` limpio. `git status --short` muestra solo los archivos previamente modificados (M) y untracked (??) que ya existían antes de esta sesión. Los únicos cambios nuevos son los directorios de jobs E2E bajo `data/videos/`.

## 24. Decisión final

**E2E_BLOCKED**

El pipeline v2 runtime funciona correctamente en las etapas:
- fetch_images_v2 (descarga HTTP real de Wikimedia)
- generate_audio (Edge TTS real)
- prepare_job (timeline v2 con paths assets/)

Pero el render está bloqueado porque:
- asset_validation v2 bloquea correctamente assets con dimensiones inferiores a 720x720
- El Wikimedia provider descarga GIFs de 700x435 sin filtrar por resolución

Adicionalmente, el intento 1 reveló un defecto de filename collision cross-scene que impide jobs con >3 escenas.

## 25. Próximo Build mínimo recomendado

### Build A: Filtrar resolución en Wikimedia provider (prioridad: alta)
- En `visual_provider_wikimedia_v2.py`, después de la búsqueda HTTP, filtrar resultados con `width < 720 OR height < 720` antes de seleccionar el primer candidato.
- Si ningún resultado pasa el filtro, devolver NO_RESULTS para que el executor intente con otra query.

### Build B: Scope de filename por escena (prioridad: alta)
- En `visual_asset_executor_v2.py`, generar filenames con formato `seg_{sceneNumber}_{segmentIndex}.{ext}` en lugar de `seg_{segmentIndex}.{ext}`.
- Actualizar `visual_asset_bridge_v2.py` y `prepare_job.py` para manejar el nuevo formato.
- Esto resolvería P1 (colisión cross-scene) y permitiría jobs con 4+ escenas.

### Build C: Evitar duplicados de sourceUrl (prioridad: media)
- En el executor, mantener un set de sourceUrls ya descargados y saltar resultados que apunten al mismo archivo.
- Permitiría que segmentos distintos en la misma escena obtengan imágenes diferentes.

### Build D: Ranking por calidad en Wikimedia (prioridad: baja)
- Ordenar resultados de Wikimedia por resolución (width * height) descendente y seleccionar el de mayor calidad.
- Mejoraría significativamente la calidad visual del output.

## Confirmaciones adicionales

- No se usaron assets fabricados ni placeholder.
- No se usaron imágenes manuales.
- No se usaron providers no implementados.
- No se usó --dry-run en el fetch live.
- No se modificó OpenSpec.
- No se hizo commit.
- No se publicó el vídeo.
