# OpenCode Free Models Benchmark R2

Benchmark R2 para revalidar el routing de modelos gratuitos de OpenCode antes de
la modularización. Preparado pero **NO ejecutado** aún.

- **Branch:** `change/opencode-free-models-benchmark-r2`
- **Setup commit:** `65c2400`
- **Primera ronda:** variante `default` para los 4 modelos (reducir variables).
- **Runs previstos:** 8 (4 modelos x 2 tareas).

## Modelos candidatos (IDs verificados con `opencode models opencode --refresh`)

| Id | Variante primera ronda |
|----|------------------------|
| `opencode/big-pickle` | default |
| `opencode/deepseek-v4-flash-free` | default |
| `opencode/nemotron-3.5-lightning-free` | default |
| `opencode/laguna-s-2.1-free` | default |

## Tareas

### R2-A — replay read-only

Replay de la tarea R1 (auditoría V1/V2 sobre `run_job.py` y `generate_script.py`)
sobre el **snapshot exacto de R1** (commit `6e9bed5`) para comparabilidad directa
R1 ↔ R2. Read-only, MCP OFF, agente `benchmark-readonly` (`mode: primary`, **4
pasos**, igual que R1), variante `default`, formato JSON. Sandbox read-only.
Fixture: `fixtures/build-r2a-fixture.sh`. Score: `score_r2a.py`.

### R2-B — Build hermético

Fix real histórico: `_compute_operational_word_target` (fix commit `bafb2d5`,
pre-fix `d62c76a`). El modelo debe implementar la función pura para que pasen 2
tests deterministas (`TestOperationalWordTarget`). Cero red/proveedores/Docker.
Agente `benchmark-builder` (`mode: primary`, 6 pasos), MCP OFF, variante
`default`. Sandbox **escribible**. Cada run trabaja sobre una copia independiente
de la fixture; el commit de solución **nunca** queda en el sandbox.
Fixture: `fixtures/build-r2b-fixture.sh`. Score: `score_r2b.py` (PASS conjunto).

## Material

| Archivo | Descripción |
|---------|-------------|
| `agents/benchmark-readonly.agent.md` | Agente read-only R2-A (`mode: primary`, 4 pasos) |
| `agents/benchmark-builder.agent.md` | Agente build hermético R2-B (`mode: primary`, 6 pasos) |
| `prompts/r2a-prompt.txt` | Prompt R2-A (replay R1, `#WORKDIR#` se sustituye) |
| `prompts/r2b-prompt.txt` | Prompt R2-B |
| `fixtures/build-r2a-fixture.sh` | Construye sandbox R2-A desde `6e9bed5` (read-only) |
| `fixtures/build-r2b-fixture.sh` | Construye sandbox R2-B desde `d62c76a` (writable) |
| `run.sh` | Runner no interactivo (8 runs, preflight, export fallback, autoscoring) |
| `events.py` | Parser compartido del stream `--format json` |
| `score_r2a.py` | Scorer R2-A (schema, respuestas, evidencia, scope) |
| `score_r2b.py` | Scorer R2-B (hash master vs post, tests, scope, PASS conjunto) |
| `session_id.py` | Extrae sessionID del stream |
| `capture_evidence.py` | Comprueba si el stream tiene `text` final + `step_finish` |
| `manifest.json` | Manifiesto de alcance y método |

## Métricas capturadas

Por modelo y tarea: PASS/FAIL, score objetivo, tests, archivos modificados,
violaciones de scope, tool calls (parsing `events.jsonl`), input/output/cache
tokens (eventos `step_finish` y `opencode stats`), wall-clock (`/usr/bin/time`),
errores/timeouts, observaciones. Ver informe `docs/research/opencode-free-models-benchmark-r2.md`.

## Informe

Metodología y tablas: `docs/research/opencode-free-models-benchmark-r2.md`.