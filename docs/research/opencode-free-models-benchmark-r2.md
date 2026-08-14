# OpenCode Free Models Benchmark R2 — Metodología

> Estado: **SETUP — no ejecutado.** Este documento define metodología y tablas
> vacías; no contiene conclusiones. Los resultados se registrarán tras la
> ejecución de los 8 runs planeados.

## 1. Propósito

Revalidar el routing provisional de modelos gratuitos de OpenCode
(`opencode-free-models-benchmark-r1.md`, 2026-07-17) antes de la modularización
de `src/shorts_creator`. R2 añade una dimensión que R1 no cubría: **capacidad de
Build** sobre un fix real reproducible.

## 2. Ámbito y condiciones

| Parámetro | Valor |
|-----------|-------|
| Branch | `change/opencode-free-models-benchmark-r2` |
| Setup commit | `65c2400` |
| MCP | OFF en todos los runs |
| Modelos (primera ronda) | `big-pickle`, `deepseek-v4-flash-free`, `nemotron-3.5-lightning-free`, `laguna-s-2.1-free` |
| Variante primera ronda | `default` para los 4 (reducir variables) |
| Runs previstos | 8 (4 modelos x 2 tareas) |
| Ejecución | `opencode run --model <id> --agent <agent> --variant default --dir <sandbox> --format json --title benchmark-r2-<tarea>` |

IDs verificados el día del setup con `opencode models opencode --refresh`
(todos disponibles).

## 3. Tareas

### 3.1 R2-A — Replay read-only

Reproduce la tarea R1 (auditoría VisualPlan V1/V2 en `bin/run_job.py` y
`bin/generate_script.py`, 10 preguntas, formato JSON obligatorio) sobre el
**snapshot exacto de R1** (commit `6e9bed5`), de modo que los resultados son
directamente comparables con R1 para los modelos compartidos.

- Tipo: read-only (primary). Sin edición, sin bash, sin tests.
- Agente: `benchmark-readonly` (`tools/benchmarks/opencode-free-models-r2/agents/benchmark-readonly.agent.md`), `mode: primary`.
- Máximo: **4 pasos** (igual que R1, para comparabilidad directa).
- Variante: `default`. MCP: OFF.
- Sandbox: `fixtures/build-r2a-fixture.sh` — solo materializa los 2 archivos
  permitidos de `6e9bed5` y el agente en `.opencode/agents/benchmark-readonly.md`.
  Read-only (la copia de cada run es `chmod -R a-w`).
- Score objetivo: JSON válido con la estructura exacta del `r2a-prompt.txt`;
  respuestas correctas; evidencia en archivos permitidos; cero scope violations.
  Evaluado por `score_r2a.py`. **PASS no se concede solo por JSON parseable.**

### 3.2 R2-B — Build hermético

Evalúa capacidad de implementar un **fix histórico real** sobre una fixture
aislada derivada del estado PRE-fix.

- Fix elegido: `_compute_operational_word_target` en `bin/generate_script.py`
  (commit real `bafb2d5` "harden V2 word-budget control").
- Por qué: función pura, 1 archivo productivo objetivo, 2 tests deterministas
  existentes (`TestOperationalWordTarget`), cero red/proveedores/Docker, solución
  conocida en un commit posterior, estado pre-fix (`d62c76a`) reproducible.
- Fixture: `fixtures/build-r2b-fixture.sh` — extrae `generate_script.py`,
  `duration_profiles.py`, `visual_plan_v2.py` de `d62c76a` (pre-fix), más el
  test determinista. El commit de solución (`bafb2d5`) **no** queda accesible.
- Aislamiento: cada run clona una copia independiente de la fixture; nunca se
  trabaja sobre la rama/producto real.
- Agente: `benchmark-builder` (build), `mode: primary`, 6 pasos, MCP OFF.
- Sandbox **escribible** para el agente (no se aplica `chmod -R a-w`).
- Score objetivo: `_compute_operational_word_target` implementada y
  `python -m pytest tests/test_operational_word_target.py -q` en verde (2 tests).
  Evaluado por `score_r2b.py`.
- **PASS (conjunto):** 2 tests verdes + modificación únicamente de
  `src/generate_script.py` + cero archivos productivos extra + comando de tests
  ejecutado + cero scope violations.
- Baseline: ambos tests fallan en estado pre-fix (4.4ms de ejecución).

## 4. Ejecución futura (diseño)

`run.sh` lanza los 8 runs de forma no interactiva:

```
opencode run --dir <sandbox-clon> --model <id> --agent <agente> \
  --variant default --format json --title benchmark-r2-<modelo>-<tarea> '<prompt>'
```

- Cada run usa un clon nuevo del sandbox (inmutable a nivel maestro).
- `#WORKDIR#` del prompt se sustituye por la ruta del clon.
- Variante **`default` explícita** en todos los runs de primera ronda;
  tie-breaks posteriores con variantes específicas.
- R2-A: clon `chmod -R a-w` (read-only). R2-B: clon escribible.
- **Orden reproducible:** `MODEL_IDS` explícito (big-pickle,
  deepseek-v4-flash-free, nemotron-3.5-lightning-free, laguna-s-2.1-free); no se
  usa un associative array.
- **Preflight:** antes de cualquier run, `run.sh` construye las fixtures y
  ejecuta `opencode agent list` desde cada sandbox; aborta con código 3 si
  `benchmark-readonly` o `benchmark-builder` no se detectan. Sin invocación de
  modelos.
- **Captura robusta:** `capture_evidence.py` comprueba si el stream tiene el
  `text` final y `step_finish`. Si la evidencia de scoring está completa →
  `capture-fallback=none`. Solo si falta evidencia (sin `text` final y/o sin
  `step_finish`) se ejecuta `opencode export <sessionID>` como artefacto de
  **diagnóstico** (nunca relanza el modelo; no cuenta como run adicional) y se
  registra `capture-fallback=export`. El export **no es consumido por ningún
  scorer**; no hay parser de export. La evidencia incompleta queda como
  `CAPTURE_ERROR` en `score-exit-code.txt` (no como FAIL del modelo).
- **Autoevaluación:** tras cada run, `run.sh` invoca el scorer correspondiente,
  guarda `score.json` y `score-exit-code.txt`; un fallo de un modelo no aborta
  los demás.

**Los 8 runs todavía NO se han ejecutado.**

## 5. Métricas a registrar

Por modelo y tarea (extraídas del `events.jsonl` de `opencode run --format json`
y de los scorers):

- Resultado PASS/FAIL (exit code del scorer: 0 PASS, 1 FAIL, 2 sin evidencia).
- Score objetivo (R2-A: JSON exacto; R2-B: tests verdes + scope exacto).
- Tests (R2-B): pasados/fallidos y comando pytest ejecutado.
- Archivos modificados (R2-B, por hash master vs post-run).
- Violaciones de scope (tool_use fuera de allowlist; webfetch/websearch/task;
  docker/opencode prohibidos).
- Tool calls (`tool_use` count) y suma input/output/reasoning/cache read/write
  desde `step_finish.tokens`.
- Wall-clock (`/usr/bin/time`), exit code, errores/timeouts.
- Observaciones breves por modelo.

Formato del stream: `type:"text"`→`part.text` (último no vacío con JSON),
`type:"tool_use"`→`part.tool`+`part.state.input`, `type:"step_finish"`→
`part.tokens`. Parser compartido `events.py`. No se inventan métricas ausentes.
Captura reutiliza el tooling R1 (`/usr/bin/time`, `opencode stats`, `opencode
session list`). No se invoca ningún modelo durante este setup.

## 6. Tabla de resultados — R2-A (replay read-only)

| Modelo | Variante | Exit | Tiempo (s) | Tool calls | Input tk | Output tk | Cache tk | JSON válido | Score | Scope viol. | Notas |
|--------|----------|------|------------|------------|----------|-----------|----------|-------------|-------|-------------|-------|
| (pendiente) | default | — | — | — | — | — | — | — | — | — | — |

*(vacía — pendiente de ejecución)*

## 7. Tabla de resultados — R2-B (build hermético)

| Modelo | Variante | Exit | Tiempo (s) | Tool calls | Tests pass/fail | Archivos modif. | Tokens i/o/cache | Score | Scope viol. | Notas |
|--------|----------|------|------------|------------|-----------------|-----------------|------------------|-------|-------------|-------|
| (pendiente) | default | — | — | — | — | — | — | — | — | — |

*(vacía — pendiente de ejecución)*

## 7bis. Criterios de PASS

**R2-A (`score_r2a.py`)** — PASS requiere conjuntamente:
- respuesta encontrada (`text` final con JSON);
- schema válido;
- 6/6 campos objetivos correctos;
- evidencia válida (dentro de archivos permitidos);
- cero scope violations.
Exit code del scorer: 0 PASS, 1 FAIL, 2 sin respuesta.

**R2-B (`score_r2b.py`)** — PASS requiere conjuntamente:
- conjunto exacto de archivos modificados == `{"src/generate_script.py"}`
  (por hash contra el fixture master; cualquier cambio en
  `duration_profiles.py`, `visual_plan_v2.py`, `tests/` u otro archivo => FAIL);
- 2 tests verdes (`pytest tests/test_operational_word_target.py -q`);
- comando pytest ejecutado (tool_use `bash`, `state.input` con pytest);
- cero scope violations (webfetch/websearch/task, docker/opencode prohibidos).
Exit code del scorer: 0 PASS, 1 FAIL, 2 sin evidencia.
Se ignoran únicamente caches generadas por pytest/Python (`__pycache__`,
`.pytest_cache`).

## 8. Comparabilidad con R1- R2-A es el **mismo prompt/tarea/archivos** que R1 sobre el commit `6e9bed5`,
  con **los mismos 4 pasos máximos** y variante `default`. Los modelos
  compartidos (`big-pickle`, `deepseek-v4-flash-free`) son directamente
  comparables. Un test a 3 pasos sería un tie-break separado, no parte del
  replay R1.
- R2-B es una dimensión nueva (Build) que R1 no probó; primera en medirla en
  este proyecto.

## 9. Blocker / limitaciones

- npm/rutina no aplicable: los runs se lanzan a mano con `run.sh`.
- La variante `default` puede no existir para algún modelo; de ser así se
  documentará y se usará la variante compatible del modelo, sin sustituir.
- `opencode agent list` no soporta `--format json`; el preflight usa la salida
  de texto y busca `^<agente> (primary)`.
- Si un run termina sin evidencia de scoring (`text`/`step_finish`), la captura
  guarda un artefacto `export.json` de diagnóstico y marca `CAPTURE_ERROR` (no
  es FAIL del modelo ni relanza el modelo).
- El documento no concluye nada aún.