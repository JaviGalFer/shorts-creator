# Sesión: Workflow de guion v1 operativo

- Fecha: 2026-06-30 19:56 (Europe/Madrid)
- Objetivo: dejar operativo el primer workflow n8n para generación de guion histórico y persistencia local de metadata.
- Estado inicial: n8n accesible, API keys cargadas, workflows previos fallidos por incompatibilidad de nodos y restricciones de entorno.
- Estado final: workflow `generate-script-v1` funcional con `Manual Trigger`, llamada real a OpenAI y guardado de JSON en `data/metadata/`.
- Agente responsable: opencode
- Cambio OpenSpec relacionado: `openspec/changes/pipeline-minimo-v1/`
- Riesgo asumido: habilitar acceso a variables de entorno en nodos y permitir escritura de archivos en `/data` dentro del contenedor n8n.
- Validaciones realizadas: ejecución real del workflow por CLI, respuesta válida de OpenAI, archivo `data/metadata/hist-2026-06-30-175447.json` creado correctamente.
- Archivos modificados: `docker-compose.yml`, `docs/runbooks/n8n-operations.md`, `openspec/changes/pipeline-minimo-v1/tasks.md`, `.env`.
- Comandos ejecutados: login por API a n8n, creación/borrado de workflows vía REST, reinicios del stack con `make docker-down` y `make docker-up`, ejecución de `n8n execute --id=...` con puertos alternativos.
- Resultado: primera pieza del pipeline lista; el sistema ya genera guiones estructurados y los persiste localmente.
- Próximos pasos: crear workflow de audio (ElevenLabs), workflow de assets (Pexels) e integración de render FFmpeg.
- Bloqueos o decisiones pendientes: el trigger actual es manual; el webhook se retoma después. Falta endurecer credenciales y cambiar la password temporal de n8n.
