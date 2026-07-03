# Spec: Fundación del proyecto

## Requisitos

### Estructura de carpetas
- RF-001: El proyecto sigue la estructura definida en `openspec/changes/bootstrap-video-automation/design.md`.
- RF-002: Los directorios de datos (assets, audio, subtitles, renders, metadata) existen y están excluidos de Git.

### Gestión de secretos
- RF-003: `.env` está en `.gitignore`.
- RF-004: `.env.example` contiene solo placeholders, sin secretos reales.
- RF-005: No hay API keys en archivos markdown, JSON de workflows ni código versionado.

### Persistencia de metadata
- RF-006: Cada trabajo de vídeo tiene un JSON de metadata en `data/metadata/`.
- RF-007: El JSON sigue el esquema definido en `docs/project/architecture.md`.

### Convenciones de logging
- RF-008: Los logs se almacenan en `logs/`.
- RF-009: Los logs no contienen API keys ni secretos.
- RF-010: Los logs están excluidos de Git.

### Ejecución local
- RF-011: El stack n8n + Postgres se levanta con `docker compose up -d`.
- RF-012: FFmpeg está disponible localmente o vía contenedor Docker.

### Reproducibilidad
- RF-013: Mismos inputs de guion e imágenes producen el mismo vídeo (determinismo).
- RF-014: Las versiones de dependencias están documentadas.

### No publicación automática
- RF-015: El pipeline termina con estado `REVIEW_PENDING`.
- RF-016: No hay ningún workflow que publique automáticamente a redes sociales.

### Assets pesados en Git
- RF-017: Los directorios `data/assets/`, `data/audio/`, `data/subtitles/`, `data/renders/` y `data/metadata/` están en `.gitignore`.
- RF-018: Solo archivos `.gitkeep` se versionan dentro de `data/`.
