# Propuesta: Bootstrap de la automatización de vídeo

## Problema

No existe ningún sistema para generar vídeos cortos de historia de forma automatizada. Actualmente no hay pipeline, ni estructura documental, ni integraciones definidas.

## Alcance de esta fase

1. Estructura documental del proyecto.
2. Reglas para agentes (AGENTS.md).
3. Skills especializadas.
4. Agentes especializados.
5. Bitácora de sesiones y decisiones.
6. Estructura OpenSpec.
7. Documentación de integraciones previstas.
8. Plan MVP ejecutable.
9. Docker Compose para n8n + Postgres.

## Fuera de alcance

- Implementación del pipeline n8n.
- Integración real con ElevenLabs, LLM o Pexels.
- Render de vídeos.
- Publicación.

## Resultado esperado

Un proyecto estructurado y documentado listo para comenzar la implementación del pipeline mínimo.

## Criterios de éxito

- AGENTS.md funcional.
- Skills y agentes creados.
- ADR-0001 aceptado.
- OpenSpec con diseño del MVP aprobado.
- Docker Compose levantable.

## Riesgos iniciales

- Estructura duplicada con proyecto n8n existente (mitigado: proyecto independiente).
- APIs externas no disponibles sin validar (mitigado: documentado como pendiente).
