# Spec: web-security (PLANNED — no implementado)

> **Seguridad como invariante arquitectónico de ALTO NIVEL.** El Web API debe exponer
> **recursos de dominio**, nunca **recursos de filesystem**.

## Identidad de job

- Los jobs futuros creados por HTTP DEBEN usar **UUID4 opaco** generado por el backend.
- Para un job web: **API jobId == directorio jobId == metadata.jobId** (una sola identidad).
- **UUID es un identificador, NO autorización.** Los futuros checks de autenticación/
  ownership deben insertarse antes del acceso a recursos sin cambiar la semántica pública
  de recursos.

## Frontera absoluta de filesystem

El frontend NUNCA debe:

- enviar un directorio;
- enviar un filesystem path;
- enviar un nombre de archivo usado para resolución de path;
- recibir un filesystem path;
- recibir un directorio;
- recibir paths de artefactos internos absolutos/relativos.

Formas prohibidas de API (equivalentes):

```text
GET  /files?path=...
GET  /download?path=...
POST {"outputDir": "..."}
POST {"output": "..."}
POST {"filename": "..."}
```

Estilo válido de recurso de dominio:

```text
GET /api/v1/jobs/{uuid}
GET /api/v1/jobs/{uuid}/video
GET /api/v1/jobs/{uuid}/download
```

Flujo backend:

```text
UUID
→ validate
→ lookup job
→ hook de autorización/ownership (futuro)
→ resolver raíz de job interna canónica
→ seleccionar `video.mp4` conocido
→ verificar recurso
→ servir
```

Sin concatenación de paths controlada por el cliente. **Defensa en profundidad incluso con
UUIDs.**

## Las capacidades CLI existentes NO son capacidades del Web API

- `bin/generate_script.py` ya tiene `--output` histórico. Eso puede permanecer como
  capacidad CLI/interna. El **future HTTP request DTO NO debe exponerlo** ni mapear ningún
  campo de HTTP controlado por el usuario hacia él.
- `_final_summary` del orchestrator emite diagnósticos CLI incluyendo paths como `jobPath` /
  `outputVideoPath`. Son SOLO diagnósticos CLI. El backend web NUNCA debe:
  - reenviar `_final_summary` como respuesta de API;
  - exponer stdout capturado directamente;
  - exponer `jobPath`;
  - exponer `outputVideoPath`;
  - exponer paths de comandos de subproceso.

## DTO allowlist

El API NUNCA devuelve `metadata.json` raw. Límite obligatorio:

```text
metadata.json
→ projection
→ response DTO explícito
→ frontend
```

Los response DTOs son **allowlists**. Añadir un campo metadata privado/interno NO debe hacerlo
automáticamente público.

No exponer:

- filesystem paths;
- comandos hijo;
- stdout/stderr crudo de subproceso;
- valores de entorno;
- API keys;
- stack traces;
- configuración interna no requerida por el frontend;
- payloads arbitrarios de providers;
- metadata solo-debug.

## Excepciones

- El backend futuro debe tener **mapeo centralizado de errores** de aplicación/API.
- No dispersar `HTTPException(500, str(exc))` por las rutas.
- Modelo de error de aplicación pequeño y tipado, incl. casos como:
  - request/job id inválido;
  - job not found;
  - video unavailable;
  - execution failure;
  - internal storage failure.
- Errores públicos con códigos estables + mensajes saneados:

```json
{
  "error": {
    "code": "JOB_NOT_FOUND",
    "message": "Job not found."
  }
}
```

- Los detalles inesperados del backend van SOLO a los logs del backend.
- Nunca devolver strings de excepción crudas, tracebacks Python ni stderr de subproceso al
  navegador.

## Ownership / auth / rate limiting futuros

NO implementarlos ahora. Pero rutas/servicios NO deben dificultar añadirlos después.

Flujo futuro:

```text
request
→ authentication
→ principal
→ job lookup
→ ownership/authorization
→ resource
```

Diseñar `GET /jobs` semánticamente como:

> jobs visibles al caller

no:

> todos los jobs de la instalación

aunque el MVP tenga inicialmente un operador local único.

El hardening futuro debe poder añadir:

- autenticación;
- ownership;
- rate limiting;
- job quotas;
- límites de concurrencia;
- límites de payload;
- request timeouts;
- CORS más estricto;
- hardening de HTTPS/deployment;
- auditoría/logging de seguridad.

**No implementar esos en esta tarea.**
