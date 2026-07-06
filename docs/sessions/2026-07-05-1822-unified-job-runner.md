# Sesión: Unified job runner and orchestration state (Phase 23)

- Fecha: 2026-07-05
- Objetivo: Crear `bin/run_job.py` — un punto de entrada único que orqueste los seis scripts del pipeline en el orden de dependencia correcto, persista el estado de orquestación, y maneje errores/gates de forma predecible.
- Estado inicial: Seis scripts CLI independientes. Sin orquestación centralizada. Sin trazabilidad de qué etapa se ejecutó o falló.
- Estado final: `bin/run_job.py` con 6 etapas (script → assets → audio → prepare → render → validate), estado `orchestration` en metadata.json, manejo de REVIEW_REQUIRED, failure metadata, dry-run, stop-after. 168/168 tests pasando.
- Cambio OpenSpec relacionado: improve-historical-visual-pipeline (Phase 23)
- Validaciones realizadas: 168/168 tests passing. Dry-run verificada con --duration 42. Script-only real ejecutado con --stop-after script.

## Stage order (descubierto del repositorio)

| Orden | Script | Dependencias |
|-------|--------|-------------|
| 1 | `generate_script.py` | — (crea metadata.json) |
| 2 | `fetch_images.py` | metadata.json con script |
| 3 | `generate_audio.py` | metadata.json con script |
| 4 | `prepare_job.py` | metadata.json + audio + assets |
| 5 | `render_job.py` | metadata.json con renderTimeline |
| 6 | `validate_job.py` | metadata.json + video.mp4 |

Assets (2) y audio (3) son independientes — pueden ejecutarse en cualquier orden. Prepare (4) necesita ambos. Render (5) necesita el timeline de prepare. Validate (6) es post-render.

## Diseño de `bin/run_job.py`

### CLI

```
python3 bin/run_job.py \
  --topic "Tema histórico" \
  --duration 42 \
  [--duration-profile] [--duration-target] [--duration-min] [--duration-max] \
  [--strictness] [--model] \
  [--stop-after script|assets|audio|prepare|render|validate] \
  [--dry-run] [--verbose]
```

### Job identity

1. `generate_script.py` imprime JSON a stdout con `{"jobId": "...", "path": "..."}`
2. El runner parsea esa línea con `parse_script_output()` — busca el primer objeto JSON que contenga `jobId` y `path`
3. Verifica que el archivo exista en disco
4. Stages posteriores reciben `metadata_path` como argumento posicional

No se adivinan paths desde el topic.

### State machine

```
script:   SCRIPT_GENERATING → SCRIPT_DRAFT | REVIEW_REQUIRED | FAILED
assets:   ASSETS_FETCHING   → ASSETS_READY (u ASSET_UNRESOLVED) | FAILED
audio:    AUDIO_GENERATING  → AUDIO_READY | REVIEW_REQUIRED | FAILED
prepare:  PREPARING         → SUBTITLES_READY | FAILED
render:   RENDERING         → RENDERED (o variantes) | FAILED
validate: VALIDATING        → VALIDATED | FAILED
```

### REVIEW_REQUIRED handling

- Script stage: si `metadata.status == "REVIEW_REQUIRED"`, el runner imprime mensaje y retorna 0
- Etapas posteriores: verifican `data.get("status") == "REVIEW_REQUIRED"` antes de ejecutar
- Nunca se sobreescribe REVIEW_REQUIRED con un estado exitoso

### Failure handling

- Código de salida != 0 → `data["status"] = "FAILED"`, se persiste `failure` con:
  - `failedStage`, `error` (truncado a 1000 chars), `childCommand`, `exitCode`, `timestamp`
- Stages posteriores no se ejecutan
- Summary JSON final con status FAILED

### Orchestration persistence

```json
"orchestration": {
  "runnerVersion": "1",
  "currentStage": "assets",
  "statusHistory": [
    {"stage": "script", "status": "SCRIPT_DRAFT", "startedAt": "...", "finishedAt": "..."}
  ]
}
```

Cada etapa escribe un entry en `statusHistory[]`. Los metadatos previos (request, script, durationContract, etc.) nunca se sobreescriben.

## Archivos creados/modificados

| Archivo | Cambio |
|---------|--------|
| `bin/run_job.py` | Nuevo — orquestador unificado (310 líneas) |
| `tests/test_run_job.py` | Nuevo — 34 tests (unitarios, mocks, dry-run, failure) |
| `openspec/changes/improve-historical-visual-pipeline/design.md` | Añadida Fase 23 |
| `openspec/changes/improve-historical-visual-pipeline/tasks.md` | Añadida Fase 23 |
| `README.md` | Añadido ejemplo de run_job.py |

## Tests

```bash
python3 -m pytest tests/test_run_job.py -v
# → 34 passed in 0.09s

python3 -m pytest tests/ -v
# → 168 passed in 5.97s
```

## Verificación dry-run

```bash
python3 bin/run_job.py --topic "Prueba duración 42" --duration 42 --dry-run
# → Plan de 6 stages con comandos correctos, profile standard_32_38, rango 38-46
```

## Verificación script-only real

```bash
python3 bin/run_job.py --topic "Prueba runner script only" --duration 35 --stop-after script
# → jobId=prueba-2026-07-05-182309, status=SCRIPT_DRAFT
# → orchestration con 1 entry, requestedSec=35, requestedProfile="auto"
# → Summary JSON con outputVideoPath=null, validationStatus=null
```

## Próximos pasos

1. Verificar pipeline completo (etapas asset→validate) con un job real que tenga API keys y Docker.
2. Implementar `--resume-from` para reanudar desde una etapa fallida.
3. Considerar assets/audio paralelos para reducir tiempo total.
4. Integrar `run_job.py` en n8n workflow como paso único.

## Bloqueos o decisiones pendientes

- Pipeline completo no verificado por falta de API keys de assets (Pexels, Pixabay) y Docker para render.
- `--resume-from` no implementado porque requeriría lectura del estado de orchestration y es más complejo que `--stop-after`.
