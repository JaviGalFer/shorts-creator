# Spec: job-execution (PLANNED — no implementado)

Ejecución de jobs de larga duración fuera del request HTTP.

## Requisitos

- La request HTTP **nunca** ejecuta el pipeline completo de forma síncrona.
- **Executor inicial:** background executor local, **max concurrency = 1**.
- **Un worker Uvicorn** mientras se use el executor en memoria (varios workers duplicarían
  la cola/registro en memoria y podrían ejecutar en paralelo el mismo job).
- El **estado de ejecución** es distinto del **estado canónico de pipeline**.

### Estados de ejecución conceptuales

- `QUEUED`
- `RUNNING`
- `FINISHED`
- `INTERRUPTED`
- `FAILED`

> `FINISHED` significa que la ejecución se detuvo, NO "resultado de pipeline exitoso".
> El resultado de pipeline permanece en `metadata["status"]` canónico.

### Restart / staleness

- En arranque, jobs `QUEUED`/`RUNNING` obsoletos (worker muerto) se marcan como
  `INTERRUPTED` **a menos que** exista un mecanismo real de resumibilidad (hoy NO existe).
- **No** se simula reanudación automática.
- **Sin** cola durable, Redis ni Celery para MVP.

### Cancelación

- **No** hay cancelación en MVP. No añadir estados/contratos especulativos de cancelación.

### Progreso

- Progress **por stage** via `metadata.orchestration.statusHistory` / `currentStage`.
- **Sin** porcentajes falsos.
- Polling (~1 s) hasta estado terminal.

## No implementar

- No crear `LocalJobExecutor`/`JobService`/estado de ejecución/colas todavía.
- No installar FastAPI.
- No añadir DB/Redis/Celery.
- No añadir cancelación.
