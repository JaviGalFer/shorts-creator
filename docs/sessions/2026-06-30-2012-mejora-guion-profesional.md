# Sesión: Mejora profesional del guion por escenas

- Fecha: 2026-06-30 20:12 (Europe/Madrid)
- Objetivo: mejorar el workflow de guion para que el resultado sea usable en TTS, subtítulos y montaje por escenas.
- Estado inicial: `generate-script-v1` generaba una narración global y escenas poco acopladas al audio.
- Estado final: `generate-script-v1` genera un guion estructurado por escenas con `voiceover`, `subtitle`, `visualPrompt`, `purpose` y duración objetivo por escena.
- Agente responsable: opencode
- Cambio OpenSpec relacionado: `openspec/changes/pipeline-minimo-v1/`
- Riesgo asumido: incrementar la complejidad del prompt para mejorar la calidad del output y asumir un ligero aumento del consumo de tokens.
- Validaciones realizadas: ejecución real del workflow contra OpenAI y creación del archivo `data/metadata/hist-2026-06-30-181103.json`.
- Archivos modificados: `docs/project/architecture.md`, workflow `generate-script-v1` en n8n.
- Comandos ejecutados: actualización del workflow vía API REST de n8n y ejecución por CLI con `n8n execute --id=vnyalikS6G28nsAF`.
- Resultado: el guion ahora está orientado a producción y cada escena ya puede convertirse en audio, subtítulo e imagen de forma coherente.
- Próximos pasos: generar audio por escena en ElevenLabs y descargar assets con Pexels usando `visualPrompt`.
- Bloqueos o decisiones pendientes: queda transformar el trigger manual en una entrada más cómoda (webhook o formulario) cuando el resto del pipeline esté estabilizado.
