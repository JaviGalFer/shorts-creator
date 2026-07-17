# Procedencia — OpenCode Free Models Benchmark R1

## Propósito

Preservar la evidencia reproducible del benchmark R1 de modelos gratuitos de
OpenCode, ejecutado sobre el repositorio **JaviGalFer/shorts-creator**.

## Identificador

`opencode-free-models-r1`

## Fecha UTC

2026-07-17T19:06:21Z

## Commit del repositorio

`6e9bed53631e289b71d824337a236eb1c8b04517`

## Material reproducible versionado

```
tools/benchmarks/opencode-free-models-r1/
├── prompt.txt
├── run.sh
├── benchmark-readonly.agent.md
├── manifest.json
├── checksums.sha256
├── README.md
└── raw-metadata/
    ├── commit.txt
    ├── git-status-before.txt
    ├── git-status-after.txt
    ├── git-status.diff
    ├── stats-before.txt
    └── stats-after.txt
```

## Archivo comprimido bruto (no versionado)

| Campo | Valor |
|-------|-------|
| Nombre | `shorts-free-r1-20260717T190621Z.rar` |
| Ruta original | `/home/javi/opencode-benchmarks/shorts-free-r1-20260717T190621Z.rar` |
| Tamaño | 165170 bytes |
| SHA-256 | `f041878330f47e120cce761c9573b524740fbaa545c88c1cb5f1e62fa3d6136b` |

## Directorio bruto original (no versionado)

`/home/javi/opencode-benchmarks/shorts-free-r1-20260717T190621Z/`

## Exclusión de eventos completos y RAR

- Los `*.events.jsonl` contienen las respuestas completas de cada modelo y no
  se versionan por su tamaño agregado (~946 KB) y porque el prompt, runner y
  agente son suficientes para reproducir el experimento.
- El archivo RAR (~161 KB) agrupa toda la salida bruta incluyendo eventos,
  stderr, tiempos y sesiones. No se versiona por contener datos derivados cuya
  reconstrucción es posible desde el material reproducible.

## Estado

**evidence preserved; conclusions audited**

## Referencia al informe canónico

El informe técnico auditado se encuentra en:
`docs/research/opencode-free-models-benchmark-r1.md`

El resumen JSON estructurado se encuentra en:
`tools/benchmarks/opencode-free-models-r1/results-summary.json`