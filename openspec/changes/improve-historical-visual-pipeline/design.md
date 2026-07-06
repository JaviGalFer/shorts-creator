# Diseño: Mejora del pipeline visual histórico

## Contrato visualPlan (nuevo)

```json
{
  "visualPlan": {
    "strategy": "historical_archive",
    "primaryAssetType": "historical_photograph",
    "secondaryAssetType": "map",
    "period": "Spanish Civil War, 1936",
    "location": "Spain",
    "entities": ["Spanish Civil War"],
    "searchQueries": ["Spanish Civil War 1936 photograph"],
    "imageGenerationPrompt": "...",
    "negativePrompt": "...",
    "style": "historical documentary",
    "mood": "tense and somber",
    "preferredSources": ["wikimedia_commons"],
    "allowGeneratedImage": true,
    "licenseRequired": "public_domain_or_cc",
    "visualImportance": "high"
  }
}
```

## Estrategias visuales

| Estrategia | Fuentes prioridad | Fallback |
|------------|-------------------|----------|
| `historical_archive` | Wikimedia → LoC → Openverse → Pexels → generado IA | visualPrompt |
| `map_or_document` | Wikimedia → LoC → Openverse | generado IA si permitido |
| `atmospheric_broll` | Pexels → Pixabay → FreeAI → Pollinations | visualPrompt |
| `generated_reconstruction` | FreeAI → proveedor IA existente → Pollinations | visualPrompt |

## Sistema de scoring

Pesos centralizados:

```python
SCORING_WEIGHTS = {
    "entity_match": 30,
    "period_or_location_match": 20,
    "asset_type_match": 15,
    "sufficient_resolution": 15,
    "clear_license": 10,
    "preferred_source": 10,
    "modern_or_irrelevant": -30,
    "duplicate_entity": -30,
    "unknown_license": -40,
    "low_resolution": -50,
}
```

## Metadata de assets

```json
{
  "sceneNumber": 1,
  "selected": true,
  "path": "scenes/scene-01.jpg",
  "provider": "wikimedia_commons",
  "strategy": "historical_archive",
  "assetType": "historical_photograph",
  "sourceUrl": "https://...",
  "title": "...",
  "author": "Unknown",
  "license": "Public Domain",
  "attributionRequired": false,
  "queryUsed": "...",
  "width": 2000,
  "height": 1400,
  "score": 82,
  "scoreReasons": ["Entity match: Spanish Civil War", "..."],
  "downloadedAt": "ISO_DATE"
}
```

## Flujo actualizado de fetch_images.py

```
Por cada escena:
  1. Leer visualPlan (o fallback a visualPrompt)
  2. Determinar estrategia y proveedores
  3. Para cada proveedor:
     a. Ejecutar queries de búsqueda
     b. Obtener lista de candidatas (3-5)
     c. Evaluar cada candidata con scoring
  4. Ordenar todas las candidatas por score
  5. Seleccionar la mejor como primary
  6. Descargar primary
  7. Guardar metadata de todas las candidatas
  8. Si nada funciona: fallback a visualPrompt legacy
```

## Script bin/generate_script.py

```bash
python3 bin/generate_script.py --topic "La caída de Constantinopla" [--dry-run]
```

- Lee .env (LLM_API_KEY, LLM_PROVIDER, LLM_MODEL)
- Construye system prompt con instrucciones para visualPlan
- Llama a la API de OpenAI
- Genera metadata.json completo en data/videos/{jobId}/
- --dry-run imprime el prompt sin llamar a la API

## Validación semántica hard de assets (Fase 17)

### Asset temporal match

Campo calculado por escena/candidata con valores:
- `historical_event`: el asset muestra el año y el periodo/entidad del evento.
- `archival_context`: el asset es histórico y está relacionado con la entidad/ubicación.
- `modern_legacy`: el asset es moderno (aniversario, conmemoración, año ≥ 2000) o contiene indicadores modernos.
- `unknown`: no hay evidencia suficiente.

El matching:
- Es sin acentos (`_unaccent`).
- Soporta equivalencias multilingües (español ↔ inglés ↔ alemán).
- Extrae el año de evento desde `visualPlan.period`, `visualPlan.entities` y `scene.voiceover`.

### Hard rules de filtrado

```python
if editorial_role == "context_map":
    assert primaryAssetType in {"map", "historical_map", "document", "newspaper",
                                "map_or_document", "historical_map_or_document"}
    assert assetTemporalMatch != "unknown"

if visualTemporalIntent == "event_depiction":
    assert assetTemporalMatch not in ("unknown", "modern_legacy")
```

### Reutilización de assets entre escenas

Solo se permite para:
- Última escena (CTA).
- Escenas con `editorialRole == "consequence_or_legacy"`.

Restricciones adicionales:
- `event_depiction` no puede reusar asset `modern_legacy` ni `unknown`.
- Se extraen años del asset reusado y de la escena destino (`period` + `voiceover`). Si no hay intersección, se bloquea.
- Se re-evalúa `assetTemporalMatch` en el contexto destino y se actualiza en el asset reusado.
- Se preservan `title` y `description` en `asset_meta` para que el matching funcione en cadenas de reuso.

### Queries históricas para event_depiction

Cuando `_classify_temporal_intent(scene) == "event_depiction"`, se generan queries históricas (`build_historical_queries`) aunque el `editorialRole` no esté en `HARD_HISTORICAL_ROLES`. Esto evita que escenas como `consequence_or_legacy` con voiceover de evento ("El Muro cayó en 1989") se queden con queries genéricas tipo "Berlin Wall fall celebrations".

## Fase 18 — Aislamiento de artefactos derivados y evidencia visual de cierre de frontera

### Aislamiento de jobs clonados

Los jobs de validación se crean frecuentemente clonando un job anterior. El clon debe descartar **todos** los artefactos derivados para evitar que rutas del job anterior contaminen el nuevo:

```python
DERIVED_KEYS = {
    "assets", "timeline", "renderTimeline", "subtitles", "render",
    "assetValidation", "validation", "review", "resolvedConfig", "updatedAt",
}
```

- `bin/clone_job.py` implementa `clone_job()` que copia solo `request` + `script`, aplica parches por escena (por ejemplo, cambiar el `editorialRole` de la escena 2) y escribe un `metadata.json` limpio.
- El estado inicial del clon es `SCRIPT_READY`.

### Validación de referencias cruzadas en render_job.py

Antes del render se ejecuta `validate_no_cross_job_paths()`:

- Recolecta todos los valores de campos cuya clave termina en `Path` (o es conocida: `path`, `imagePath`, `assetPath`, `audioPath`).
- Resuelve rutas absolutas y relativas contra el directorio del job actual.
- Falla con `CROSS_JOB_ARTIFACT_REFERENCE` si cualquier ruta local cae fuera del directorio del job.
- La comprobación se ejecuta dentro de `preflight_validate()` antes de cualquier otra validación.

### Nuevo rol: `border_closure_construction`

Escena 2 del guion del Muro de Berlín ("El 13 de agosto de 1961, comenzó la construcción del Muro") necesita un rol más amplio que `battle_or_assault`:

- Añadido a `HARD_HISTORICAL_ROLES` y `EVENT_DEPICTION_ROLES`.
- Proveedor forzado a `wikimedia_commons` (sin stock ni IA).
- Evidencia directa aceptada (metadata del candidato):
  - `barbed wire`, `barricades`, `road block`, `border closure`.
  - Términos alemanes: `Stacheldraht`, `Mauerbau`, `Abriegelung`, `Grenzsperre`, `Sperranlagen`.
- Rechazo explícito de:
  - Fotos de separación familiar (`families separated`, `clinging hands`, `wedding`, ...).
  - Conmemoraciones/aniversarios.
  - Checkpoints genéricos (`checkpoint charlie`, `border crossing`).
- Hard rule: `borderClosureSubjectEvidence` no vacío **y** sin indicadores de rechazo.
- Se almacena en `semanticEvidence.borderClosureSubjectEvidence`.

### Queries adicionales para escena 2

`_build_scene_query_variants()` añade variantes en inglés y alemán para `border_closure_construction`:

- `Berlin Wall barbed wire 1961`
- `Stacheldraht Berlin`
- `Mauerbau Berlin`
- `Grenzsperre Berlin`
- etc.

## Fase 19 — Evidencia de fecha y endurecimiento de reutilización

### Clasificación de evidencia de fecha

`_classify_date_evidence()` separa `sourceDepictedDateEvidence` de `sourceContextDateEvidence`:

- **Heurística de rango con guión**: un título que contiene un rango tipo "1961 - 1989" o "1961–1989" se reconoce como contexto, no como depiction. Los años individuales dentro del rango no se marcan como depicted a menos que exista una indicación independiente de depiction.
- **Heurística de retrospectiva**: frases como "post-war", "after the fall", "desde su construcción" indican que el año mencionado es contexto, no depiction.
- **Heurística de verbo depictivo**: verbos como "shows", "depicts", "during", "photographed in" indican que el año es depicted.
- Los conjuntos depicted y context se mantienen independientes. Un año se considera "depicted" si existe algún cue de depiction independiente.

### Endurecimiento de reutilización

`check_reuse_compatibility()` en `asset_validation.py`:

- Compara `sourceDepictedDateEvidence` del asset origen con los años extraídos de la escena destino (`period` + `voiceover`). Si no hay intersección, se bloquea el reuso.
- Rechaza reuso cuando el rol editorial original es `civilian_impact` y la escena destino difiere materialmente del evento origen.
- Rechaza reuso de assets con `divisionSubjectEvidence` (fotos de separación familiar) para escenas de caída/legado sin evidencia de caída.
- Se almacena `reuseCompatibilityReason` con el motivo del bloqueo o aprobación.

### Nuevos campos en semanticEvidence

```json
{
  "sourceDepictedDateEvidence": ["1961"],
  "sourceContextDateEvidence": ["1961", "1962", ..., "1989"],
  "fallOpeningSubjectEvidence": ["juggling on the berlin wall"],
  "divisionSubjectEvidence": ["families separated", "separated by the wall"]
}
```

### Nuevo rol: `border_closure_construction` en asset_validation.py

- Añadido a `EDITORIAL_ROLE_COMPATIBILITY`.
- `check_role_evidence()` requiere `borderClosureSubjectEvidence` no vacío.

### check_reuse_compatibility en asset_validation.py

Se añade a `validate_job_for_render()` como paso posterior a las hard rules.

## Fase 20 — Duration profiles y consistencia de quality gates de subtítulos

### Duration profiles

Sistema centralizado de perfiles de duración reutilizables para evitar duplicación de constantes entre `generate_script.py` y `render_job.py`:

```python
# bin/duration_profiles.py
DURATION_PROFILES = {
    "short_25_30":    {"targetSec": 28, "minSec": 25, "maxSec": 30, "strictness": "balanced"},
    "standard_32_38": {"targetSec": 35, "minSec": 32, "maxSec": 38, "strictness": "balanced"},
    "extended_50_60": {"targetSec": 55, "minSec": 50, "maxSec": 60, "strictness": "balanced"},
}
```

Cada perfil define `targetSec`, `minSec`, `maxSec` y `strictness`. El perfil por defecto es `short_25_30` para mantener compatibilidad backward con jobs existentes que no especifican perfil.

#### `resolve_duration_config()`

Toma un nombre de perfil (opcional) y valores explícitos opcionales. Devuelve `(profile_name, resolved_dict)`. Los valores explícitos sobreescriben el perfil:

```python
resolve_duration_config(profile_name="standard_32_38", target=40)
# → ("standard_32_38", {"targetSec": 40, "minSec": 32, "maxSec": 38, "strictness": "balanced"})
```

#### Persistencia en metadata

- `request.durationProfile`: nombre del perfil solicitado (o default).
- `request.duration`: valores numéricos del perfil (o explicit overrides).
- `metadata.durationProfile`: espejo del request level para acceso rápido.
- `resolvedConfig.durationProfile`: confirmación del perfil usado.
- `resolvedConfig.duration`: valores numéricos finales (incluye `spokenWordsPerMinute` y `estimatedScenePauseMs`).

En `render_job.py`, el `resolvedConfig` del manifest lee `request.durationProfile` y lo persiste en `resolvedConfig.durationProfile`.

#### CLI

```bash
python3 bin/generate_script.py --duration-profile standard_32_38 --topic "Tema"
python3 bin/generate_script.py --duration-profile extended_50_60 --duration-target 52 --topic "Tema"
```

`--duration-target`, `--duration-min`, `--duration-max` y `--strictness` sobreescriben campos individuales del perfil.

### Subtitle quality-gate consistency

#### Problema original

`coverage_validation.py` usaba una función `normalize()` que solo eliminaba puntuación inicial/final, pero:
- No normalizaba puntuación interna (ej. coma tras año: `"1961,"` vs `"1961"`).
- No eliminaba acentos (`"Berlín"` vs `"Berlin"`).
- Concatenaba todos los cues en un string y toda la narración en otro, luego comparaba carácter por carácter.

Esto producía `subtitleCoverageValidation=FAIL` y `qualityGate=FAIL` incluso cuando el contenido semántico era idéntico.

#### Solución: normalización por tokens

Se crea `bin/subtitle_normalize.py` con tres funciones:

1. **`normalize_subtitle_text(text)`**: normalización centralizada:
   - lowercase
   - trim y collapse de whitespace
   - eliminación de puntuación (solo caracteres de palabra `\w`)
   - descomposición NFKD + eliminación de marcas diacríticas (acentos)
   - preservación de tokens numéricos y alfanuméricos significativos

2. **`cue_text_matches_narration(cue, narration, threshold=0.95)`**: comparación por tokens:
   - Fast path: strings normalizados iguales → PASS
   - Tokeniza ambos textos, compara conjuntos
   - Considera solo diferencias significativas (token >2 chars o puramente alfabético)
   - Si el solapamiento de tokens supera el threshold, se considera PASS

3. **`compare_cue_vs_narration_bulk(cue_texts, narration_texts)`**: wrappea la comparación bulk para `coverage_validation.py`.

#### Impacto en gates de validación

| Gate | Antes | Después | ¿Bloqueante? |
|------|-------|---------|-------------|
| `subtitleCoverageValidation` | FAIL por puntuación/acentos | PASS con normalización | Sí |
| `qualityGate` | FAIL (arrastraba subtitle) | PASS | Sí |
| Validación semántica (canonical, cross-scene) | PASS | PASS (sin cambios) | Sí |
| Cobertura temporal (timing coverage) | PASS | PASS (sin cambios) | Sí |

La validación semántica (canonical matching, cross-scene ownership) y la cobertura temporal permanecen como gates bloqueantes independientes. Solo se relaja la comparación textual carácter-exacta.

#### `validate_job.py --update-manifest`

Nuevo flag que re-evalúa los quality gates y escribe los resultados en `job-manifest.json` sin necesidad de re-renderizar. Útil para corregir manifests de jobs ya renderizados cuyo único fallo era `subtitleCoverageValidation` por diferencias textuales menores.

## Fase 21 — Generic duration-to-word-budget enforcement

### Problema original

El sistema de perfiles de duración (Phase 20) resolvía correctamente los valores numéricos (`targetSec`, `minSec`, `maxSec`), pero el prompt de generación de guion usaba una estimación lineal `wordCount * WPM / 60` que no descontaba las pausas entre escenas. Como resultado, el LLM generaba guiones sistemáticamente cortos para perfiles como `standard_32_38` (54 palabras → 30.9s estimados frente a los 32s mínimos requeridos).

### Solución: `calculate_word_budget()`

Función genérica central en `bin/duration_profiles.py` que calcula el presupuesto de palabras a partir de valores numéricos de duración, no de nombres de perfil:

```python
calculate_word_budget(
    target_sec,          # duración objetivo en segundos
    min_sec,             # duración mínima
    max_sec,             # duración máxima
    spoken_words_per_minute=110,   # WPM de Edge TTS
    scene_count=5,       # número de escenas (provisional o real)
    estimated_scene_pause_ms=350,  # pausa entre escenas
)
```

#### Fórmula

```
pauseSec = max(0, sceneCount - 1) * estimatedScenePauseMs / 1000

minimumWords   = ceil(max(0, minSec - pauseSec) / 60 * WPM)
preferredWords = round(max(0, targetSec - pauseSec) / 60 * WPM)
maximumWords   = floor(max(0, maxSec - pauseSec) / 60 * WPM)
```

#### Ejemplo (standard_32_38, 5 escenas)

| Campo | Cálculo | Resultado |
|-------|---------|-----------|
| pauseSec | 4 × 0.35 | 1.4s |
| minimumWords | ceil((32 − 1.4) / 60 × 110) | 57 |
| preferredWords | round((35 − 1.4) / 60 × 110) | 62 |
| maximumWords | floor((38 − 1.4) / 60 × 110) | 67 |

#### Salida estructurada

```json
{
  "targetSec": 35,
  "minSec": 32,
  "maxSec": 38,
  "sceneCount": 5,
  "pauseSec": 1.4,
  "minimumWords": 57,
  "preferredWords": 62,
  "maximumWords": 67,
  "spokenWordsPerMinute": 110,
  "estimatedScenePauseMs": 350
}
```

### Integración en generate_script.py

1. **Antes del primer LLM**: se calcula un presupuesto provisional con `scene_count=5` (valor preferido del proyecto). El prompt incluye `minimumWords`, `preferredWords`, `maximumWords`, duración y rango por escena.

2. **Después del LLM**: se recalcula el presupuesto con el número real de escenas generadas. Se valida el word count real contra minimum/maximum.

3. **En retry**: se usa `_build_retry_instruction()` que genera un mensaje correctivo específico con:
   - word count real vs requerido
   - escenas reales vs esperadas
   - duración estimada vs requerida
   - instrucción de expansión o reducción de contenido factual

### Retry behavior

El `retryHistory` se amplía con metadatos del presupuesto:

```json
{
  "retry": 1,
  "reason": "below_minimum_words",
  "actualWordCount": 54,
  "minimumWords": 57,
  "preferredWords": 62,
  "maximumWords": 67,
  "estimatedDurationSec": 30.9,
  "instructionType": "expand_factual_content"
}
```

Casos:
- `below_minimum_words`: el prompt de retry pide expandir contenido factual en ~N palabras.
- `above_maximum_words`: el prompt de retry pide reducir contenido.
- `duration_out_of_range`: la duración no cae en el rango aunque el word count esté dentro del presupuesto (caso borde).

### Persistencia en durationContract

El `durationContract` de `metadata.json` ahora incluye:

| Campo | Descripción |
|-------|-------------|
| `minimumWords` | Palabras mínimas calculadas |
| `preferredWords` | Palabras objetivo preferidas |
| `maximumWords` | Palabras máximas |
| `pauseSec` | Segundos de pausa entre escenas |
| `retryHistory[].reason` | Razón del retry |
| `retryHistory[].minimumWords` | Presupuesto mínimo en ese intento |
| `retryHistory[].preferredWords` | Presupuesto preferido en ese intento |
| `retryHistory[].maximumWords` | Presupuesto máximo en ese intento |
| `retryHistory[].instructionType` | Tipo de instrucción enviada |

### Compatibilidad backward

- Perfiles `short_25_30`, `standard_32_38`, `extended_50_60` funcionan sin cambios.
- Overrides explícitos `--duration-target/min/max` funcionan sin cambios.
- La función es genérica: no referencia nombres de perfil, solo valores numéricos.
- Preparada para recibir valores de `--duration` / `requestedSec` futuros:
  ```python
  # En el futuro:
  resolved = resolve_duration_values(requested_sec=42)
  budget = calculate_word_budget(**resolved, scene_count=5)
  ```

## Fase 22 — Approximate duration resolution (`--duration` flag)

### Resolución centralizada en `bin/duration_profiles.py`

Toda la lógica de resolución de duración vive en `bin/duration_profiles.py`, no en `generate_script.py`:

```
resolve_requested_duration()
  ├── valida requested_sec (20-60)
  ├── determina profile (auto | explícito | default)
  ├── calcula tolerance-based min/max
  ├── aplica clamping condicional según perfil
  ├── aplica overrides explícitos (máxima prioridad)
  └── valida consistencia (min <= target <= max)
```

### Prioridad de resolución

1. Overrides explícitos (`--duration-target/min/max`) — máxima prioridad
2. `--duration` N segundos — auto-selecciona perfil, calcula tolerance-based range
3. `--duration-profile NOMBRE` — perfil explícito
4. Default: `short_25_30`

### Auto-selección de perfil

| Rango | Perfil |
|-------|--------|
| 20-30 | `short_25_30` |
| 31-45 | `standard_32_38` |
| 46-60 | `extended_50_60` |

### Tolerance dinámica

```
tolerance = clamp(round(N * 0.10), min=2, max=5)
minSec = requestedSec - tolerance
maxSec = requestedSec + tolerance
```

Ejemplos: N=28 → tol=3 → rango 25-31; N=42 → tol=4 → rango 38-46; N=55 → tol=5 → rango 50-60.

### Clamping condicional

- **Perfil explícito** (`--duration-profile X --duration Y`): siempre se constrain a profile bounds.
- **Auto-selección** (`--duration Y` sin profile): constrain solo si `min <= target <= max` tras clamping. Si target queda fuera, se usa el rango tolerance-based sin cap.

Ejemplo: `--duration 42` → auto `standard_32_38` (32-38). Tol=4 → rango 38-46. Target=42 > max=38 → skip cap, rango final 38-46.

### Persistencia en request.duration

```json
{
  "targetSec": 42,
  "minSec": 38,
  "maxSec": 46,
  "strictness": "balanced",
  "requestedSec": 42,
  "requestedProfile": "auto"
}
```

- `requestedSec`: el valor original de `--duration` (o null si no se usó)
- `requestedProfile`: nombre del perfil o `"auto"` si se auto-seleccionó (o null si no aplica)

### Renombrado

`MAX_SCENES_FOR_SHORT` → `MAX_SCENES` en `generate_script.py` por claridad (no hay otro perfil con constante separada).

### Compatibilidad backward

- `resolve_duration_config()` se mantiene sin cambios para tests legacy.
- Perfiles existentes no se modifican.
- Perfiles `short_25_30`, `standard_32_38`, `extended_50_60` siguen funcionando vía `--duration-profile` o por defecto.

## Fase 23 — Unified job runner and orchestration state

### Motivación

El repositorio tiene seis scripts CLI independientes (`generate_script.py`, `fetch_images.py`, `generate_audio.py`, `prepare_job.py`, `render_job.py`, `validate_job.py`). No existe un punto de entrada único. Cualquier futura integración (FastAPI, n8n, UI) necesitaría conocer el orden exacto, las dependencias y el formato de salida de cada script.

### Solución

`bin/run_job.py` — un orquestador que ejecuta los scripts existentes como subprocesos, en el orden de dependencia correcto, y mantiene un registro de estado (`orchestration`) dentro del `metadata.json`.

### Stage order (discovered from repository)

1. **script** — `generate_script.py` (LLM genera guion, crea metadata.json)
2. **assets** — `fetch_images.py` (descarga imágenes para cada escena)
3. **audio** — `generate_audio.py` (genera narración TTS + timings)
4. **prepare** — `prepare_job.py` (timelines, subtítulos ASS, render path)
5. **render** — `render_job.py` (FFmpeg render + asset/codec validation)
6. **validate** — `validate_job.py` (comprehensive job validation)

Assets y audio son independientes entre sí (orden intercambiable). Prepare necesita ambos.

### Orchestration state model

Cada etapa tiene un estado de "ejecutando" y uno de "completado". El runner persiste una entrada en `metadata.orchestration.statusHistory[]`:

```json
{
  "orchestration": {
    "runnerVersion": "1",
    "currentStage": "assets",
    "statusHistory": [
      {
        "stage": "script",
        "status": "SCRIPT_DRAFT",
        "startedAt": "2026-07-05T00:00:00.000Z",
        "finishedAt": "2026-07-05T00:01:00.000Z"
      }
    ]
  }
}
```

Estados por etapa:

| Etapa | Running | Success | Posible bloqueante |
|-------|---------|---------|--------------------|
| script | SCRIPT_GENERATING | SCRIPT_DRAFT | REVIEW_REQUIRED |
| assets | ASSETS_FETCHING | ASSETS_READY | ASSET_UNRESOLVED |
| audio | AUDIO_GENERATING | AUDIO_READY | REVIEW_REQUIRED |
| prepare | PREPARING | SUBTITLES_READY | — |
| render | RENDERING | RENDERED | REVIEW_REQUIRED, RENDER_FAILED |
| validate | VALIDATING | VALIDATED | — |

### Failure state

```json
{
  "status": "FAILED",
  "failure": {
    "failedStage": "assets",
    "error": "Asset download failed",
    "childCommand": "/usr/bin/python3 bin/fetch_images.py ...",
    "exitCode": 1,
    "timestamp": "2026-07-05T00:00:00.000Z"
  }
}
```

### Job identity

- `generate_script.py` imprime una línea JSON a stdout con `jobId` y `path`.
- El runner parsea esa línea, no adivina paths.
- Los stages posteriores reciben `metadata_path` como argumento posicional, igual que los scripts existentes.
- Todos los artefactos quedan dentro de `data/videos/{jobId}/`.

### CLI

```
python3 bin/run_job.py \
  --topic "La batalla de Stalingrado" \
  --duration 42 \
  [--duration-profile] [--duration-target] [--duration-min] [--duration-max] \
  [--strictness] [--model] \
  [--stop-after script|assets|audio|prepare|render|validate] \
  [--dry-run] [--verbose]
```

`--stop-after script` ejecuta solo el script stage y detiene.
`--stop-after validate` (default) ejecuta el pipeline completo.

### Dry-run

Imprime el plan de ejecución resuelto (duración, perfil, comandos) sin invocar subprocesos ni mutar archivos.

### Subprocess safety

- `subprocess.run()` con `shell=False`, comando como lista de strings.
- `cwd` fijado al project root para que las rutas relativas funcionen.
- stdout/stderr capturados, truncados a 500 chars en resúmenes de error.
- Timeout de 10 minutos por etapa.
- No se persisten secrets, API keys ni variables de entorno.

### REVIEW_REQUIRED gate

Si el script stage produce `status: REVIEW_REQUIRED`, el runner detiene el pipeline antes de assets. Lo mismo si cualquier etapa posterior produce `REVIEW_REQUIRED`. El estado `REVIEW_REQUIRED` nunca se sobreescribe con un estado exitoso.

### Final summary

Al finalizar, el runner imprime una línea JSON:

```json
{
  "jobId": "prueba-2026-07-05-182309",
  "jobPath": "data/videos/prueba-2026-07-05-182309",
  "status": "SCRIPT_DRAFT",
  "lastCompletedStage": "script",
  "outputVideoPath": null,
  "validationStatus": null
}
```
