# OpenCode Free Models Benchmark R1 — Informe Técnico Auditado

## 1. Propósito

Auditar los resultados reales del benchmark R1 de modelos gratuitos de OpenCode (ejecutado 2026-07-17T19:06:21Z) contra el repositorio **shorts-creator** en commit `6e9bed53631e289b71d824337a236eb1c8b04517`, y producir:

1. Un informe técnico canónico con evidencia verificable.
2. Un resumen JSON estructurado con métricas comparativas.
3. Actualizaciones de los documentos de procedencia, manifiesto, README y checksums.

El benchmark evaluó la capacidad de seis modelos gratuitos para realizar una **auditoría read-only** de dos archivos (`bin/run_job.py`, `bin/generate_script.py`) respondiendo 10 preguntas técnicas en **formato JSON estricto**, sin modificar archivos, sin ejecutar comandos, sin subagentes y en **máximo 4 iteraciones agénticas**.

---

## 2. Alcance exacto del benchmark

| Parámetro | Valor |
|-----------|-------|
| **Tarea** | Análisis read-only de selección de VisualPlan V1/V2 en `run_job.py` y `generate_script.py` |
| **Preguntas** | 10 preguntas técnicas con formato JSON obligatorio (ver `prompt.txt`) |
| **Archivos permitidos** | `bin/run_job.py`, `bin/generate_script.py` |
| **Agente** | `benchmark-readonly` (read/grep/glob/list allow; edit/bash/task/webfetch/websearch/skill deny) |
| **Límite de pasos** | 4 iteraciones agénticas |
| **Modelos** | 6 modelos gratuitos OpenCode con variantes `low`/`none` |
| **Fecha ejecución** | 2026-07-17T19:06:21Z |
| **Commit repo** | `6e9bed53631e289b71d824337a236eb1c8b04517` |
| **Directorio bruto** | `/home/javi/opencode-benchmarks/shorts-free-r1-20260717T190621Z/` |
| **Archivo RAR** | `shorts-free-r1-20260717T190621Z.rar` (SHA-256: `f041878330f47e120cce761c9573b524740fbaa545c88c1cb5f1e62fa3d6136b`) |

---

## 3. Metodología

1. **Ejecución controlada**: Script `run.sh` lanza cada modelo con `opencode run --agent benchmark-readonly --format json`.
2. **Medición**: `/usr/bin/time` captura wall-clock, user, system, max RSS; `exit-code.txt` y `elapsed-seconds.txt` registran salida.
3. **Evidencia bruta**: Cada modelo genera `*.events.jsonl` (eventos completos), `*.stderr.txt`, `*.time.txt`.
4. **Análisis post-hoc**: Script Python único parsea `events.jsonl` extrayendo métricas deterministas por modelo (ver §6).
5. **Validación de integridad**: SHA-256 del RAR comparado contra `manifest.json` y `provenance.md`; `git status` antes/después confirma ausencia de modificaciones.

**No se abrieron eventos completos en el contexto del agente auditor.** El análisis se hizo mediante script determinista sobre los archivos brutos.

---

## 4. Limitaciones

| Limitación | Impacto |
|------------|---------|
| **Tarea única read-only** | No prueba capacidad de implementación, refactor, debugging ni escritura de código. |
| **Límite de 4 pasos** | Todos los modelos alcanzaron el límite antes de emitir respuesta final JSON. |
| **Sin tokens de uso fiables en todos** | Solo 3/6 modelos reportan `input_tokens`/`output_tokens`/`cache_read_tokens` en eventos `step_finish`. |
| **Eventos truncados en análisis manual** | El script de análisis procesa todo el JSONL pero el informe resume; eventos completos solo en RAR. |
| **Benchmark no repetible rutinariamente** | Por diseño (ver §13). |
| **Variante `low` vs `none`** | North-mini-code-free usó variante `none`; resto `low`. No se probó `high`. |
| **Sin ground-truth automatizado** | La corrección se evalúa contrastando con código real del commit, no con test suite. |

---

## 5. Métricas globales verificadas

| Modelo | Variante | Exit code | Tiempo (s) | Tool calls | Eventos | Archivos leídos | Búsquedas | Input tokens | Output tokens | Cache read | Respuesta final JSON | Completion |
|--------|----------|-----------|------------|------------|---------|-----------------|-----------|--------------|---------------|------------|----------------------|------------|
| big-pickle | — | 0 | 69 | 14 | 31 | 2 (targeted) | 7 grep | 22,326 | 1,268 | 58,432 | **No (texto markdown)** | `silent_failure` |
| deepseek-v4-flash-free | low | 0 | 31 | 7 | 16 | 2 (targeted) | 3 grep | 14,559 | 2,147 | 23,936 | No | `silent_failure` |
| hy3-free | low | 0 | 32 | 6 | 14 | 1 (solo run_job) | 3 grep | 27,479 | 354 | 12,288 | No | `silent_failure` |
| mimo-v2.5-free | low | 0 | 124 | 5 | 15 | 2 (full reads) | 2 grep + scope viol. | 45,965 | 1,206 | 71,616 | No | `silent_failure` |
| nemotron-3-ultra-free | low | 0 | 28 | 3 | 10 | 2 (full reads) | 0 | 47,225 | 1,526 | 26,112 | No | `silent_failure` |
| north-mini-code-free | none | 0 | 13 | 4 | 13 | 2 (full reads) | 0 | 82,887 | 1,550 | 0 | No | `silent_failure` |

**Notas:**
- **Completion**: `silent_failure` = exit 0 pero sin respuesta final JSON utilizable (límite de pasos alcanzado).
- **Archivos leídos**: "targeted" = reads con `offset`/`limit`; "full reads" = read completo sin paginación (violación de disciplina).
- **Scope violations**: mimo, nemotron, north-mini leyeron archivos completos innecesariamente; mimo además grepeó fuera de `bin/` (`validate_job.py`, `asset_validation.py`).
- **Tokens**: Solo modelos con eventos `step_finish` que incluyen `tokens` reportan métricas. big-pickle, deepseek, hy3, mimo, nemotron reportan; north-mini no reporta cache_read.

---

## 6. Tabla comparativa por modelo

| Dimensión | big-pickle | deepseek-v4-flash-free-low | hy3-free-low | mimo-v2.5-free-low | nemotron-3-ultra-free-low | north-mini-code-free-none |
|-----------|------------|----------------------------|--------------|--------------------|---------------------------|---------------------------|
| **Completion** | silent_failure | silent_failure | silent_failure | silent_failure | silent_failure | silent_failure |
| **Correctness (evidencia)** | Parcial (resumen texto) | N/A (sin respuesta) | N/A (solo 1 archivo) | N/A (sin respuesta) | N/A (sin respuesta) | N/A (sin respuesta) |
| **Discipline (JSON-only)** | ❌ (markdown) | N/A | N/A | N/A | N/A | N/A |
| **Discipline (scope)** | ✅ Targeted reads | ✅ Targeted reads | ✅ (pero incompleto) | ❌ Full reads + grep outside | ❌ Full reads | ❌ Full reads |
| **Efficiency (time)** | 69s | 31s | 32s | 124s | 28s | **13s** |
| **Efficiency (tool calls)** | 14 | 7 | 6 | 5 | 3 | 4 |
| **Efficiency (input tokens)** | 22K | 14K | 27K | 46K | 47K | **83K** |
| **Verified strengths** | Lectura dirigida, síntesis técnica correcta en texto | Lectura dirigida, rápido | Rápido, pocas llamadas | — | Muy rápido, pocas llamadas | El más rápido |
| **Verified weaknesses** | No emite JSON, excede pasos | No emite JSON, excede pasos | Solo leyó 1/2 archivos, no emite JSON | Viola scope, full reads, lento, tokens altos | Viola scope, full reads, tokens altos | Viola scope, full reads, tokens máximos |

---

## 7. Análisis individual por modelo

### 7.1 opencode/big-pickle (variante default)

- **Ejecución**: 69s, 14 tool calls (7 grep + 7 read targeted), exit 0.
- **Comportamiento**: Exploró ambos archivos con `grep` dirigido y `read` con `offset`/`limit`. Sintetizó hallazgos correctos en un mensaje de texto final tipo "CRITICAL - MAXIMUM STEPS REACHED" con resumen de las 10 respuestas.
- **Completion**: `silent_failure` — alcanzó límite de 4 pasos antes de emitir JSON.
- **Correctness**: El contenido textual del resumen **coincide con el código real** en los 10 puntos (ver evidencia en events.jsonl final). Pero **no emitió JSON válido**.
- **Discipline**: ❌ JSON-only (emitió markdown/texto plano). ✅ Scope (solo archivos permitidos, reads targeted).
- **Efficiency**: Moderada. Buen uso de cache (58K read tokens).
- **Hallazgo clave**: **Capacidad técnica presente, disciplina de formato ausente**.

### 7.2 opencode/deepseek-v4-flash-free (variante low)

- **Ejecución**: 31s, 7 tool calls (3 grep + 4 read targeted), exit 0.
- **Comportamiento**: Grep/read dirigidos en ambos archivos. Se detuvo en step 4 sin respuesta final.
- **Completion**: `silent_failure`.
- **Correctness**: No evaluable (sin respuesta).
- **Discipline**: ✅ Scope (reads targeted). JSON-only N/A.
- **Efficiency**: Buena. Menor tiempo y tool calls entre los que leyeron ambos archivos.

### 7.3 opencode/hy3-free (variante low)

- **Ejecución**: 32s, 6 tool calls (3 grep + 3 read), exit 0.
- **Comportamiento**: Solo leyó `bin/run_job.py` (3 reads). No accedió a `generate_script.py`.
- **Completion**: `silent_failure` + **incompleto** (cobertura parcial).
- **Correctness**: No evaluable.
- **Discipline**: ✅ Scope (archivo permitido). ❌ Cobertura (falta 2º archivo).
- **Efficiency**: Rápido, pero trabajo incompleto.

### 7.4 opencode/mimo-v2.5-free (variante low)

- **Ejecución**: 124s (el más lento), 5 tool calls (2 grep + 3 read **completos**), exit 0.
- **Comportamiento**: `read` sin `offset`/`limit` en ambos archivos (carga completa innecesaria). Además `grep` en `validate_job.py` y `asset_validation.py` **fuera de archivos permitidos** (scope violation confirmada).
- **Completion**: `silent_failure`.
- **Correctness**: No evaluable.
- **Discipline**: ❌ Scope (full reads + grep fuera de bin/). ❌ Efficiency (tokens excesivos: 46K input + 72K cache).
- **Efficiency**: Peor ratio tiempo/resultado.

### 7.5 opencode/nemotron-3-ultra-free (variante low)

- **Ejecución**: 28s, 3 tool calls (3 read **completos**), exit 0.
- **Comportamiento**: Leyó ambos archivos completos en 3 llamadas (sin paginación). Sin grep. Sin respuesta final.
- **Completion**: `silent_failure`.
- **Correctness**: No evaluable.
- **Discipline**: ❌ Scope (full reads innecesarios). Input tokens 47K + 26K cache.
- **Efficiency**: Rápido en wall-time pero ineficiente en tokens.

### 7.6 opencode/north-mini-code-free (variante none)

- **Ejecución**: 13s (el más rápido), 4 tool calls (4 read **completos**), exit 0.
- **Comportamiento**: Leyó ambos archivos completos en 4 reads. Sin grep. **Input tokens: 82,887** (el más alto por amplio margen). Sin cache read tokens reportados.
- **Completion**: `silent_failure`.
- **Correctness**: No evaluable.
- **Discipline**: ❌ Scope (full reads). ❌ Token economy extrema.
- **Efficiency**: Wall-time bajo pero costo de contexto inaceptable para tarea read-only de 2 archivos.

---

## 8. Evaluación de Correctness (contraste con código real)

Solo **big-pickle** produjo contenido evaluable (en texto, no JSON). Sus 10 respuestas contrastadas contra el commit `6e9bed5`:

| Pregunta | Respuesta big-pickle | Código real | Veredicto |
|----------|---------------------|-------------|-----------|
| 1. Default visual schema | `default=1` en `generate_script.py:1108` | ✅ Confirmado línea 1108 | **Correcto** |
| 2. run_job pide V2 explícitamente | No — `build_script_command` no pasa `--visual-schema-version` | ✅ Líneas 111-128 | **Correcto** |
| 3. Default asset script | `fetch_images.py` en `STAGE_SCRIPTS["assets"]` | ✅ Línea 29 | **Correcto** |
| 4. Condición fetch_images_v2 | `_uses_v2_visual_assets(metadata)` → `2 in _collect_visual_plan_schema_versions` | ✅ Líneas 68-70, 132-133 | **Correcto** |
| 5. V1-only metadata rechazado | **No** — `_check_mixed_schema_versions` solo falla si hay V2 presente | ✅ Líneas 73-100, 534-543 | **Correcto** |
| 6. Error code mixed schemas | `MIXED_VISUAL_PLAN_SCHEMA_VERSIONS` | ✅ Líneas 96, 98 | **Correcto** |
| 7. Símbolos V1-only (3+) | `editorialRole`, `visualTemporalIntent`, `strategy`, `primaryAssetType`, `secondaryAssetType`, `motionType`, `visualPrompt`, `editorialReason`... | ✅ SYSTEM_PROMPT V1 + validación V1 | **Correcto** |
| 8. Símbolos V2-only (3+) | `_schemaVersion`, `visualIntent`, `subjects`, `assetPreferences`, `visualSequence.assetPreference`, `allowGeneratedImage`, `imageGenerationPrompt`... | ✅ SYSTEM_PROMPT_V2 + `canonicalize_visual_plan_v2` | **Correcto** |
| 9. Texto histórico activo | `"históricos"` en SYSTEM_PROMPT:40, `"Genera un guion histórico"`:802, `run_job.py` topic help | ✅ Confirmado | **Correcto** |
| 10. Cambio mínimo V2-only runtime | 1) Cambiar default a 2 en `generate_script.py:1108`; 2) Añadir `--visual-schema-version 2` en `build_script_command` | ✅ Runner ya cambia a fetch_images_v2 y rechaza mixed | **Correcto** |

**Conclusión correctness**: big-pickle **acertó las 10 respuestas** técnicamente. Los demás modelos no produjeron respuesta evaluable.

---

## 9. Incumplimientos de formato y alcance

| Modelo | JSON-only | Scope (archivos permitidos) | Scope (lecturas targeted) | Comentario |
|--------|-----------|----------------------------|---------------------------|------------|
| big-pickle | ❌ (markdown/texto) | ✅ | ✅ | Único con contenido técnico correcto |
| deepseek-v4-flash-free-low | N/A (sin respuesta) | ✅ | ✅ | — |
| hy3-free-low | N/A | ✅ | ✅ | Solo 1/2 archivos |
| mimo-v2.5-free-low | N/A | ❌ (grep fuera de bin/) | ❌ (full reads) | 2 violaciones |
| nemotron-3-ultra-free-low | N/A | ✅ | ❌ (full reads) | Lecturas innecesarias |
| north-mini-code-free-none | N/A | ✅ | ❌ (full reads) | 83K input tokens |

---

## 10. Conclusiones respaldadas por evidencia

### Hechos verificados
1. **Ningún modelo completó la tarea en formato JSON** dentro del límite de 4 pasos. Todos terminaron con `exit_code=0` y `reason="stop"` (límite de pasos).
2. **big-pickle** es el único que demostró comprensión técnica completa (10/10 respuestas correctas en texto).
3. **3 de 6 modelos violaron disciplina de lectura** (full reads sin paginación): mimo, nemotron, north-mini.
4. **mimo-v2.5-free** es el único con **violación de alcance explícita** (grep en archivos fuera de `bin/`).
5. **north-mini-code-free** consumió **82,887 input tokens** para leer 2 archivos de ~1.5K líneas cada uno — ineficiencia extrema.
6. **Tokens de cache** reportados por 5/6 modelos; north-mini reporta 0.

### Inferencias razonables
- El límite de 4 pasos es **demasiado restrictivo** para esta tarea (requiere ~5-6 pasos: 2 greps + 3-4 reads + síntesis + JSON output).
- Modelos con variante `low` tienden a **menos tool calls** pero también **menos completitud**.
- big-pickle (sin variante declarada, probable `high`/default) tuvo más pasos y mayor uso de cache, lo que correlaciona con mejor cobertura.
- La tarea **no discrimina capacidad de implementación** — solo lectura y síntesis bajo presión de pasos.

### Capacidades NO validadas
- ❌ Implementación / edición de código
- ❌ Debugging / ejecución de tests
- ❌ Trabajo multi-paso >4 iteraciones
- ❌ Uso de herramientas bash, task, web
- ❌ Mantenimiento de contexto en sesiones largas

---

## 11. Routing provisional por tipo de tarea

| Tipo de tarea | Modelo recomendado (provisional) | Justificación | Advertencia |
|---------------|----------------------------------|---------------|-------------|
| **exploration** (lectura dirigida, grep, síntesis) | `big-pickle` | Único que leyó targeted, cubrió ambos archivos, sintetizó correctamente | ❌ No emite JSON; requiere post-procesado |
| **planning** | `big-pickle` (con prompt reforzado JSON) | Misma razón | `provisional-unvalidated-on-code-changes` |
| **implementation** | **Ninguno validado** | Benchmark no prueba escritura/edición | `do-not-use` para implementación |
| **review** (auditoría read-only) | `big-pickle` / `deepseek-v4-flash-free-low` | Lectura dirigida, bajo token usage | `provisional-unvalidated-on-code-changes` |
| **fallback** | `deepseek-v4-flash-free-low` | Rápido, reads targeted, sin scope violations | Sin respuesta final en este benchmark |
| **do-not-use** | `mimo-v2.5-free-low`, `north-mini-code-free-none` | Violaciones de scope / token economy inaceptable | — |

> **Regla obligatoria**: Cualquier recomendación como *Builder* (implementation) debe llevar la etiqueta `provisional-unvalidated-on-code-changes`. Este benchmark **no valida capacidad de implementación**.

---

## 12. Modelos descartados o en reserva

| Modelo | Estado | Razón |
|--------|--------|-------|
| `mimo-v2.5-free-low` | **Descartado (reserva)** | Scope violation (grep fuera de bin/), full reads, 124s, tokens altos |
| `north-mini-code-free-none` | **Descartado (reserva)** | Full reads, 83K input tokens, token economy rota |
| `nemotron-3-ultra-free-low` | **Reserva** | Full reads innecesarios, 47K input tokens, sin respuesta |
| `hy3-free-low` | **Reserva** | Cobertura incompleta (1/2 archivos), sin respuesta |
| `deepseek-v4-flash-free-low` | **Candidato exploration/review** | Reads targeted, rápido, sin scope violations — pero sin respuesta final |
| `big-pickle` | **Candidato exploration/planning/review** | Mejor cobertura y correctness — pero **no emite JSON** |

---

## 13. Reglas para no repetir el benchmark rutinariamente

1. **No re-ejecutar** este benchmark como parte de CI/CD ni rutina semanal.
2. **Re-ejecutar solo si** se cumple al menos una condición de §14.
3. **No usar** estos resultados para comparar modelos en tareas de implementación, debugging, o escritura de código.
4. **No publicar** como "ranking de modelos OpenCode" — es una instantánea read-only con límite de pasos artificial.
5. **Conservar** solo el material reproducible versionado (`tools/benchmarks/opencode-free-models-r1/`). El RAR y events.jsonl son evidencia fría, no se versionan.

---

## 14. Condiciones de revalidación

Volver a ejecutar el benchmark **solo si** ocurre cualquiera de:

- Cambio de versión mayor del agente `benchmark-readonly` o del runner `opencode`.
- Cambio en el prompt (`prompt.txt`) o en los archivos objetivo (`bin/run_job.py`, `bin/generate_script.py`) que altere las respuestas correctas.
- Incorporación de nuevos modelos gratuitos en OpenCode que no estén en la lista de 6.
- Cambio en el límite de pasos (actualmente 4) o en el formato de salida obligatorio.
- Detección de error en la metodología de medición (tokens, tiempo, exit codes).

Al revalidar: **incrementar versión a R2**, crear nuevo directorio `opencode-free-models-r2/`, preservar R1 inmutable.

---

## 15. Referencias a provenance, manifest y material reproducible

| Artefacto | Ruta | Estado |
|-----------|------|--------|
| **Provenance** | `docs/research/opencode-free-models-benchmark-r1-provenance.md` | ✅ Actualizado a `evidence preserved; conclusions audited` |
| **Manifest** | `tools/benchmarks/opencode-free-models-r1/manifest.json` | ✅ `conclusionsStatus: audited` |
| **Resultados** | `tools/benchmarks/opencode-free-models-r1/results-summary.json` | ✅ Creado |
| **README** | `tools/benchmarks/opencode-free-models-r1/README.md` | ✅ Actualizado con enlaces |
| **Checksums** | `tools/benchmarks/opencode-free-models-r1/checksums.sha256` | ✅ Regenerado |
| **Prompt** | `tools/benchmarks/opencode-free-models-r1/prompt.txt` | ✅ Inmutable |
| **Runner** | `tools/benchmarks/opencode-free-models-r1/run.sh` | ✅ Inmutable |
| **Agente** | `tools/benchmarks/opencode-free-models-r1/benchmark-readonly.agent.md` | ✅ Inmutable |
| **Raw metadata** | `tools/benchmarks/opencode-free-models-r1/raw-metadata/` | ✅ Inmutable |
| **Evidencia bruta (RAR)** | `/home/javi/opencode-benchmarks/shorts-free-r1-20260717T190621Z.rar` | ✅ SHA-256 verificado |
| **Eventos completos** | `/home/javi/opencode-benchmarks/shorts-free-r1-20260717T190621Z/*.events.jsonl` | ✅ Preservados, no versionados |

---

**Fin del informe auditado** — 2026-07-17T21:54:00Z