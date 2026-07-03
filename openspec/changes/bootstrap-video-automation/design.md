# Diseño: Bootstrap de la automatización de vídeo

## Arquitectura del MVP

```
[Webhook manual] -> n8n -> LLM API -> validar JSON -> ElevenLabs -> Pexels -> FFmpeg -> MP4
```

n8n es el orquestador central. No hay backend permanente.

## Flujo de datos

Ver `docs/project/architecture.md`.

## Gestión de archivos

Ver `docs/project/architecture.md`.

## Variables de entorno

Ver `.env.example`.

## Estrategia de errores

- n8n maneja reintentos.
- Fallos de API -> estado FAILED.
- Logging básico por ahora.

## Seguridad de claves

- API keys en `.env`.
- n8n credenciales cifradas en BD.

## Qué hace n8n

- Orquestar llamadas API.
- Validar JSON de guion.
- Coordinar descarga de assets.
- Ejecutar FFmpeg.
- Guardar metadata.

## Qué hace FFmpeg

- Composición de vídeo vertical 9:16.
- Inserción de imágenes por escena.
- Mezcla de audio narrado.
- Quemado de subtítulos (burn-in o SRT separado).
- Recorte a duración exacta.

## Qué se deja fuera de v1

- Publicación automática.
- Música de fondo.
- Múltiples voces.
- Dashboard.
- Colas de trabajo.
- Procesamiento paralelo.
