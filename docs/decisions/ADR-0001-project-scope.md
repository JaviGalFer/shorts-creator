# ADR-0001: Alcance del proyecto

- **Estado**: Aceptado
- **Fecha**: 2026-06-29
- **Contexto**: Se necesita definir el alcance y la arquitectura del proyecto de generación automatizada de Shorts históricos.
- **Decisión**: El MVP será un pipeline local/semi-local con n8n como orquestador, APIs externas para LLM y TTS, y FFmpeg para el render. Sin backend permanente, sin base de datos obligatoria, sin publicación automática.
- **Alternativas consideradas**:
  - Backend Spring Boot/Node: Rechazado por sobrearquitectura para el MVP.
  - Pipeline con Python puro: Rechazado porque n8n aporta orquestación visual, reintentos y monitoreo sin código.
  - Publicación automática directa: Rechazado hasta tener revisión humana.
- **Consecuencias**:
  - n8n gestiona toda la orquestación, lo que reduce código personalizado.
  - FFmpeg se ejecuta localmente (vía comando n8n o contenedor Docker).
  - El coste variable depende del volumen de vídeos y APIs usadas.
  - La trazabilidad es manual basada en archivos JSON, no en base de datos.
- **Riesgos**: Dependencia de conectividad a APIs externas para generación. Sin API externa no hay pipeline completo.
- **Cómo revertirla**: Migrar a un pipeline Python autónomo si n8n se vuelve un cuello de botella.
- **Referencias**: `docs/project/vision.md`, `docs/project/architecture.md`
