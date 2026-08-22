# Spec: pipeline-invocation (Slice 1 — implementado, aprobado, committed)

Límite de invocación reutilizable del runner canónico con identidad de job explícita.

> **Estado:** implementado, aprobado por Review formal (`SLICE_1_APPROVED`) y con commit en
> `change/web-ui-mvp`. Especifica el comportamiento que ya existe en código y tests.

## Requisitos

1. **`run_pipeline(job_id=None)` preserva el comportamiento CLI histórico.**
   - ID derivado de topic (`generate_job_id(topic)`); mismo directorio convencional;
     mismos argumentos de script; misma secuencia; mismo exit-code; mismo stdout.
   - Verificado por el test de comando por defecto y un dry-run real de `bin/run_job.py`.

2. **`run_pipeline(job_id=<id seguro explícito>)` propaga la identidad a través del
   adaptador de subproceso de script.**
   - `build_script_command` añade `--job-id <id>`.
   - `bin/generate_script.py` acepta `--job-id` y lo reenvía a `generate_script(job_id=...)`.

3. **La identidad de job explícita es canónica y triple:**
   ```text
   requested jobId == canonical directory jobId == loaded metadata["jobId"]
   ```
   - La ruta canónica (derecha) y el `metadata["jobId"]` del archivo cargado (identidad)
     son contratos INDEPENDIENTES del stdout del hijo.
   - Tras `load_metadata`, en AMBAS ramas del script (éxito y fallo),
     `_validate_explicit_metadata_identity(data, job_id)` exige `metadata["jobId"] == job_id`.
     Si no coincide, el runner falla cerrado con `SCRIPT_OUTPUT_CONTRACT_VIOLATION` ANTES
     de mutar el archivo (sin `set_failure`, sin `append_orchestration`, sin cambio de
     `status`, sin `save_metadata`, y sin usar ese jobId discrepante como identidad final).
   - El `metadata["jobId"]` cargado es la identidad; el stdout del hijo sigue siendo un
     diagnóstico opcional y NUNCA sustituye esta validación.

4. **El runner no expone una API de output-directory arbitraria.**
   - NO existe `output_dir`/`output` configurable como parámetro público de `run_pipeline`.
   - La ruta canónica `data/videos/<jobId>/metadata.json` se deriva internamente del ID.

5. **Los identificadores explícitos no pueden escapar de `data/videos/`.**
   - `validate_job_id` rechaza traversal (`..`), separadores (`/`, `\`), caracteres de
     control, espacios y vacío, en un límite interno antes de construir la ruta.
   - **Fail-fast:** cuando `generate_script` recibe un `job_id` explícito, lo valida en
     el límite de entrada, ANTES de cualquier llamada al LLM/red, de generación/retry y
     de construcción de rutas en el filesystem. Un ID explícito inválido se rechaza
     (`INVALID_JOB_ID`) sin que `call_llm` pueda ejecutarse nunca.

5b. **Un `job_id` explícito y un `--output` arbitrario son incompatibles.**
   - Un `job_id` explícito fija el invariante canónico
     `jobId == data/videos/<jobId>/metadata.json`; `output` arbitrario y `job_id`
     explícito NUNCA coexisten en silencio.
   - `generate_script` rechaza `job_id != None` + `output != None` con el error interno
     estable `JOB_ID_OUTPUT_CONFLICT`, antes de LLM/red y de trabajo en filesystem.
   - Redundancia de guardia amigable: `--job-id` y `--output` son mutuamente excluyentes
     en `argparse` de `bin/generate_script.py`.
   - Legado preservado: `--output` sin `--job-id` sigue funcionando exactamente igual.

6. **En invocación explícita, la ruta canónica derivada del jobId es autoritativa.**
   - `run_pipeline(job_id=<id explícito>)` NO confía en un `parsed["path"]` reportado por
     el subproceso hijo: la ruta autoritativa es `_canonical_metadata_path(job_id)` =
     `<root>/data/videos/<job_id>/metadata.json`.
   - El `jobId` y `path` reportados por el hijo se conservan SOLO como diagnósticos del
     contrato de salida del script; si el hijo reporta un `jobId != job_id` o un `path`
     distinto del canónico, el runner falla cerrado con
     `SCRIPT_OUTPUT_CONTRACT_VIOLATION` (nunca lee otro archivo).
   - Legado preservado: con `job_id=None` el runner mantiene la descubrimiento de la ruta
     por stdout (`parse_script_output`) sin ninguna verificación de ruta/autoridad.

7. **Los callers web usarán UUID4;** el runner interno reutilizable solo exige un
   identificador seguro (shim de validez por forma, no validación estricta de UUID).

8. **`bin/run_job.py` sigue siendo un adaptador CLI, no un límite de invocación web.**

## Verificación

- `tests/test_run_job_job_id.py`: comportamiento por defecto sin `--job-id`; propagación
  por comando y CLI; directorio/metadata canónicos; fallback derivado de topic; rechazo
  de IDs inseguros; aceptación de IDs seguros; fail-fast del `job_id` explícito; rechazo
  `JOB_ID_OUTPUT_CONFLICT` + exclusión mutua CLI; legado `--output` intacto; autoridad de
  la ruta canónica en `run_pipeline` (rechazo de path ajeno, rechazo de jobId discrepante,
  aceptación del par correcto, y legado de descubrimiento por stdout); hardening final de
  identidad: rechazo del `metadata["jobId"]` cargado discrepante en ramas de éxito y de
  fallo, y tolerancia de stdout malformado cuando la identidad canónica es válida.
- Suite completa `1913 passed, 0 failed`; `git diff --check` limpio.
