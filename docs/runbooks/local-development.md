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

## Abrir opencode

```bash
opencode .
```
