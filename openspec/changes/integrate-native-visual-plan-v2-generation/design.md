# Diseño: integrate-native-visual-plan-v2-generation

## Arquitectura del cambio

```
generate_script.py
├── call_llm(prompt, api_key, model, provider, system_prompt=SYSTEM_PROMPT)
├── _build_duration_prompt_instruction()               # v1 only  
├── _build_duration_prompt_instruction_v2()             # v2 new — neutral
├── _validate_script_structure()                       # v1 only
├── _validate_and_canonicalize_script_v2()              # v2 new
├── _build_retry_instruction()                         # v1 only
├── _build_retry_instruction_v2()                      # v2 new
├── _build_user_prompt()                               # v1 only
├── _build_user_prompt_v2()                            # v2 new (uses _instruction_v2)
└── main() → branches on --visual-schema-version
```

## Contrato CLI

```bash
# v1 (default)
python3 bin/generate_script.py --topic "..." --duration 30
python3 bin/generate_script.py --topic "..." --duration 30 --visual-schema-version 1

# v2
python3 bin/generate_script.py --topic "Cómo se produce una aurora boreal" --duration 30 --visual-schema-version 2
```

## Flujo v2 en main()

1. Resolver duración
2. Calcular word budget
3. `_build_user_prompt_v2()` genera prompt neutro
4. Bucle de retry (max 3):
   a. `call_llm(current_prompt, ..., system_prompt=SYSTEM_PROMPT_V2)`
   b. `json.loads()` parse
   c. `_validate_and_canonicalize_script_v2(script_data)` → canonical o errores
   d. Si válido: break como SCRIPT_DRAFT
   e. Si no: `_build_retry_instruction_v2()` con errores por escena
5. Persistir metadata con `request.visuals.schemaVersion = 2`

## Validación y canonicalización

```python
def _validate_and_canonicalize_script_v2(
    script_data: dict,
    *,
    allow_generated_images: bool,
) -> tuple[dict | None, list[dict], list[dict]]:
```

Retorna `(canonical_script | None, errors, warnings)`.

### Por cada escena:
1. Checks básicos: scene_count (4-6), sceneNumber (int, >0, exactamente secuencial), voiceover, targetDurationSec (finito, >0), visualPlan, _schemaVersion == 2
2. Request-level enforcement: `allowGeneratedImages=false` → rechaza allowGeneratedImage=true, generated en preferences/segmentos, imageGenerationPrompt no vacío
3. `canonicalize_visual_plan_v2(raw_vp)` → `{ok, canonicalPlan, diagnostics}`
4. Si `ok == False`: recolectar errores con sceneNumber, code, path, message
5. Si `ok == True`: promover TODOS los warnings a errores (strict-native real)

### Strict-native policy (true):
- **TODO warning** del canonicalizador → error estructural reparable
- No hay allowlist: cualquier código de warning se promueve a error
- El repair retry recibe el código exacto del warning original

### Validación estructural previa (scene-level):
- Scene count: 4-6 (`INSUFFICIENT_SCENE_COUNT` / `EXCESSIVE_SCENE_COUNT`)
- sceneNumber: int, no bool, >0, exactamente `[1, 2, ..., N]` (`INVALID_SCENE_NUMBER_SEQUENCE`)
- targetDurationSec: int/float, no bool, `math.isfinite`, >0 (`INVALID_TARGET_DURATION`)
- voiceover: no vacío
- visualPlan: presente y dict

### Enforcement request-level de generación:
- `allow_generated_images=False` → error `GENERATED_IMAGES_DISABLED_BY_REQUEST` para:
  - `allowGeneratedImage=true`
  - `"generated"` en `assetPreferences`
  - `assetPreference="generated"` en cualquier segmento
  - `imageGenerationPrompt` no nulo/no vacío

### Solo si todo OK:
- Deep copy del script
- Sustituir cada `visualPlan` por `canonicalPlan`
- Devolver `(canonical_script, [], [])`

## Retry v2

Primer intento: `SYSTEM_PROMPT_V2 + user_prompt_v2`

Retry: repair instruction con:
- Errores por escena (sceneNumber, code, path, message)
- Afirmación: todos los VisualPlan schema 2
- Afirmación: sin campos desconocidos
- Respeta restricción de imágenes generadas
- Sin API keys, sin metadata sensible

Tras 3 intentos:
- `status = REVIEW_REQUIRED`
- `exit code = 0`
- structuralIssues con `VISUAL_PLAN_V2_INVALID`

## Persistencia

### v1 (sin cambios):
- `request.visuals`: sin campo `schemaVersion`

### v2 éxito:
```json
{
  "request": {
    "visuals": {
      "mode": "images",
      "allowGeneratedImages": false,
      "schemaVersion": 2
    }
  },
  "script": { "scenes": [{ "visualPlan": { "_schemaVersion": 2, ... } }] }
}
```

### v2 fallo:
```json
{
  "status": "REVIEW_REQUIRED",
  "structuralIssues": ["VISUAL_PLAN_V2_INVALID"],
  "script": { ... }
}
```

## Compatibilidad

- `call_llm()` añade `system_prompt` opcional con default `SYSTEM_PROMPT`
- V1 no pasa el nuevo argumento → comportamiento idéntico
- Tests v1 sin cambios
- `run_job.py` sin cambios: detecta `_schemaVersion == 2` automáticamente
- `visual_plan_v2.py` sin cambios

## Resolución de PIXABAY_API_KEY

```python
def _resolve_pixabay_api_key() -> str | None:
    key = os.environ.get("PIXABAY_API_KEY")
    if key:
        return key
    # Fallback a .env si no está en os.environ
    return _load_key_from_dotenv("PIXABAY_API_KEY")
```

- `os.environ` preferente (compatible con Docker, systemd, CI)
- Fallback a `.env` cuando el script se ejecuta desde CLI sin export explícito
- Sin persistencia de secretos en disco ni en metadata

## Bridge diagnostics

El bridge de `run_job.py` a `fetch_images_v2.py` ahora lee:

- `providerAttempts` (campo moderno del canonicalizador v2)
- En lugar de `attemptedProviders` (campo legacy)

Las métricas de diagnóstico se exponen como `diagnostics.providerAttempts` en el log de fetch.

## E2E final

- **Job:** `cmo-2026-07-14-180923`
- Generación nativa v2: SCRIPT_DRAFT con 3 intentos internos, 5 escenas, 9 segmentos
- ASSETS_READY 9/9 (7 Pixabay, 2 Wikimedia)
- Render: 1080x1920, 30.0s, H.264 + AAC, 2.2MB
- SHA-256: `db47881adcdf9e96e44631ef371ed3fb25d6929e84dcd05cd607c558413d0b15`
- validate_job PASS, 0 errors, todos los gates PASS

### Primer intento bloqueado (documentado)

- ASSETS_PARTIAL 6/9 — 3 RATE_LIMITED de Wikimedia, Pixabay no activado
- Causa raíz: PIXABAY_API_KEY no en `os.environ`
- Corregido con `_resolve_pixabay_api_key()` y fallback a `.env`
