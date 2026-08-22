# Runbook: Desarrollo local

## Prerrequisitos

```bash
docker --version
docker compose version
ffmpeg -version
```

## Iniciar stack

```bash
docker compose up -d
```

Esto levanta:
- n8n en http://localhost:5679
- Postgres en localhost:5433

## Detener stack

```bash
docker compose down
```

## Ver logs

```bash
docker compose logs -f n8n
```

## Acceder a n8n

Abrir http://localhost:5679 en el navegador.

## Iniciar Web API local

Desde la raíz del repositorio:

```bash
PYTHONPATH=src python3 -m uvicorn shorts_creator.web.app:app --host 0.0.0.0 --port 8000 --workers 1
```

Mientras `LocalJobExecutor` permanezca en proceso, el MVP requiere un único
worker Uvicorn. Varios workers crearían instancias independientes del executor
y del estado operativo en memoria.

## Abrir opencode

```bash
opencode .
```
