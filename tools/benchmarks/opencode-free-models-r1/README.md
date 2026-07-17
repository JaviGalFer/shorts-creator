# OpenCode Free Models Benchmark R1

Benchmark read-only que compara seis modelos gratuitos de OpenCode analizando
código del repositorio **JaviGalFer/shorts-creator**.

- **Fecha UTC:** 2026-07-17T19:06:21Z
- **Commit:** `6e9bed53631e289b71d824337a236eb1c8b04517`
- **Tarea:** Análisis read-only sobre `bin/run_job.py` y `bin/generate_script.py`
  usando el agente `benchmark-readonly` (sin bash, sin modificaciones).

## Modelos comparados

| Modelo | Variante |
|--------|----------|
| `opencode/big-pickle` | — |
| `opencode/deepseek-v4-flash-free` | low |
| `opencode/hy3-free` | low |
| `opencode/mimo-v2.5-free` | low |
| `opencode/nemotron-3-ultra-free` | low |
| `opencode/north-mini-code-free` | none |

## Material reproducible

| Archivo | Descripción |
|---------|-------------|
| `prompt.txt` | Prompt exacto entregado a cada modelo |
| `run.sh` | Script de ejecución del benchmark (entorno bash) |
| `benchmark-readonly.agent.md` | Plantilla del agente read-only |
| `raw-metadata/` | Metadatos de antes/después: commit, git status, stats, diff |

## Informes de auditoría (conclusiones auditadas)

| Informe | Descripción |
|---------|-------------|
| **[Informe técnico canónico](../research/opencode-free-models-benchmark-r1.md)** | Análisis completo con métricas, tabla comparativa, análisis por modelo, correctness contrastado con código, routing provisional |
| **[Resumen JSON estructurado](results-summary.json)** | Datos tabulares para consumo programático |
| **[Procedencia](../research/opencode-free-models-benchmark-r1-provenance.md)** | Cadena de custodia de la evidencia bruta |

## Archivos no versionados

- **Eventos completos** (`*.events.jsonl`): no se versionan por su tamaño y
  porque contienen las respuestas completas de los modelos.
- **Archivo comprimido bruto** (`*.rar`): no se versiona por su tamaño.
- **Respuestas de los modelos**: se conservan exclusivamente en el RAR externo.

## Integridad

```bash
cd tools/benchmarks/opencode-free-models-r1
sha256sum -c checksums.sha256
```

## Validación del runner

```bash
bash -n tools/benchmarks/opencode-free-models-r1/run.sh
```

## Estado

**Conclusiones auditadas** (2026-07-17).

Este benchmark **no debe repetirse rutinariamente**. Las conclusiones son
específicas de la tarea read-only utilizada (10 preguntas técnicas, formato
JSON obligatorio, 4 pasos máximos, 2 archivos permitidos). No extrapolar a
capacidades de implementación, debugging, o trabajo multi-paso prolongado.

Ver [Reglas para no repetir](../research/opencode-free-models-benchmark-r1.md#13-reglas-para-no-repetir-el-benchmark-rutinariamente) y [Condiciones de revalidación](../research/opencode-free-models-benchmark-r1.md#14-condiciones-de-revalidacion) en el informe canónico.