# Propuesta: Pipeline mínimo v1

## Problema

No existe un pipeline funcional que genere vídeos. Tenemos la estructura del proyecto, n8n funcionando, pero cero workflows implementados.

## Alcance

1. Workflow n8n que recibe un tema histórico y genera un guion estructurado vía LLM.
2. Workflow n8n que toma el guion, genera narración con ElevenLabs y descarga imágenes de Pexels.
3. Pipeline FFmpeg que compone el vídeo final 9:16 con imágenes + audio + subtítulos.
4. Metadata JSON por cada trabajo generado.
5. Revisión humana del resultado.

## Fuera de alcance

- Publicación automática.
- Música de fondo.
- Múltiples voces.
- Dashboard web.
- Base de datos en n8n (metadata en JSON local).

## Resultado esperado

Un pipeline que, dado un tema histórico, genere un MP4 listo para revisión humana.

## Criterios de éxito

- Workflow n8n funcional con LLM real (no mock).
- Audio generado con ElevenLabs.
- Render FFmpeg produce MP4 válido.
- Metadata JSON se guarda por cada trabajo.

## Riesgos

- Dependencia de API keys externas.
- FFmpeg puede no estar instalado localmente.
