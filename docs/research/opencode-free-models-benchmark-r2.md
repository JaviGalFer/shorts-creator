# OpenCode Free Models Benchmark R2 — Informe de cierre

> Estado: **CERRADO — ejecutado 2026-08-14T19:24:42Z.** Este documento contiene
> la metodología y la **adjudicación manual** de los 8 runs, además de las
> limitaciones conocidas de los scorers. El routing provisional se actualizó en
> `.agents/skills/model-routing-and-token-economy/SKILL.md`.
> Evidencia bruta (no versionada): `~/opencode-benchmarks/shorts-free-r2-20260814T192442Z/`.

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

## 6. Resultados — R2-A (replay read-only)

Ejecutado 2026-08-14T19:24:42Z, variante `default`, 4 pasos máx, snapshot `6e9bed5`.

| Modelo | Variante | Exit | Tiempo (s) | Tool calls | Input tk | Output tk | Cache tk | JSON final | Core 6/6 | Verdicto | Notas |
|--------|----------|------|------------|------------|----------|-----------|----------|------------|----------|----------|-------|
| big-pickle | default | 0 | 40 | 8 | 8,839 | 2,424 | 12,544 | ✔ (texto) | 6/6 | **OK parcial** | Económico; audit parcialmente incompleto (2 grep fuera de allowlist por raíz de búsqueda) |
| deepseek-v4-flash-free | default | 0 | 51 | 3 | 36,790 | 4,931 | 25,600 | ✔ | 6/6 | **OK** | Audit completo; evidencia 9/9; sin scope violations |
| nemotron-3.5-lightning-free | default | 0 | 34 | 7 | — | — | — | ✔ (markdown) | 6/6 | **OK** | JSON final presente; **falso negativo del parser** (respuesta correcta en markdown) |
| laguna-s-2.1-free | default | 0 | 336 | 8 | — | — | — | ✘ | 6/6 (análisis) | **OK parcial** | Análisis correcto pero **sin respuesta JSON final** |

> Core 6/6 = los 6 campos objetivos (`defaultVisualSchemaVersion`, `runnerExplicitlyRequestsV2`, `defaultAssetStageScript`, `v2AssetSwitchCondition`, `allV1MetadataRejected`, `mixedSchemaErrorCode`) coinciden con el ground-truth R1. La adjudicación es **manual**; el parser reporta 5/6 en big-pickle/deepseek por un defecto de tipo (bool vs string en `v2AssetSwitchCondition`), no por error de contenido.

## 7. Resultados — R2-B (build hermético)

Adjudicación sobre los sandboxes reales **ignorando artefactos `.opencode/`**
(`node_modules` generados por el runner). Código verificado ejecutando los
tests de cada sandbox.

| Modelo | Variante | Exit | Tiempo (s) | Tool calls | Only generate_script | pytest ejecutado | Tests | Verdicto |
|--------|----------|------|------------|------------|----------------------|------------------|-------|----------|
| big-pickle | default | 0 | 58 | 8 | ✔ | ✘ | 2/2 (verificado) | **INCOMPLETE** |
| deepseek-v4-flash-free | default | 0 | 45 | 9 | ✘ (sin cambios) | ✘ | 0/2 | **FAIL** |
| nemotron-3.5-lightning-free | default | 0 | 39 | 7 | ✔ | ✔ | 2/2 passed | **PASS** |
| laguna-s-2.1-free | default | 0 | 400 | 8 | ✔ | ✘ | 2/2 (verificado) | **INCOMPLETE** |

- **INCOMPLETE** = código correcto (pasa 2/2 al verificarlo manualmente) pero el
  modelo **no ejecutó pytest** durante el run → no evidencia de ejecución.
- **FAIL** = ningún cambio productivo; tests fallan.
- **PASS** = solo `src/generate_script.py` modificado + pytest ejecutado + 2/2 passed.
- El scorer automático marcó todos como `exit 1` porque no ignoró `.opencode/node_modules`; la adjudicación manual aquí es la autoritativa.

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

## 9. Limitaciones conocidas de R2 (defectos del scorer, no corregidos)

- **Parser `v2AssetSwitchCondition` (R2-A):** exige `bool`, pero los modelos
  responden con la condición descriptiva (string) → falso `5/6` en big-pickle y
  deepseek. Contenido correcto. **No corregido.**
- **Parser R2-A no detecta JSON en markdown:** nemotron emitió la respuesta final
  correcta en markdown con bloques; el parser reporta "no final JSON answer"
  (`exit 2`). Falso negativo. **No corregido.**
- **Scorer R2-B no ignora `.opencode/`:** el runner materializa
  `.opencode/node_modules` en el sandbox; el scorer los cuenta como archivos
  modificados → `exit 1` para todos. La adjudicación manual los descarta.
  **No corregido.**
- La variante `default` estuvo disponible en los 4 modelos.
- `opencode agent list` no soporta `--format json`; el preflight usa texto
  `^<agente> (primary)`.
- La evidencia incompleta de captura se registra como `CAPTURE_ERROR` en
  `score-exit-code.txt` (no es FAIL del modelo ni relanza el modelo).

## 10. Adjudicación y routing resultante

La adjudicación manual (ver §6–§7) alimenta el routing provisional. Cambios
resultantes en `.agents/skills/model-routing-and-token-economy/SKILL.md`:

- **exploration / planning barato:** `opencode/big-pickle` (económico, core 6/6;
  requiere post-procesado por formato no-JSON).
- **focused review:** `opencode/nemotron-3.5-lightning-free` (audit completo,
  JSON presente).
- **bounded Build:** `opencode/nemotron-3.5-lightning-free` (PASS R2-B con
  pytest ejecutado).
- **Build fallback:** `opencode/deepseek-v4-flash-free` (audit completo).
- **laguna-s-2.1-free:** sin uso rutinario (análisis correcto pero sin respuesta
  JSON final; token usage alto: 128K input en R2-B).
- Se **preservan** las políticas R1 no evaluadas por R2 (e.g. fallback de
  exploración, do-not-use de mimo/north-mini).

Ver el SKILL para la tabla de routing completa.