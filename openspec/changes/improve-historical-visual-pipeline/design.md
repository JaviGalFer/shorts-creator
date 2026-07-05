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
