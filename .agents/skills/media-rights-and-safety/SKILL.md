---
name: media-rights-and-safety
description: Verificar licencias y atribuciones de recursos visuales, musicales y de audio
---

# Skill: media-rights-and-safety

## Cuándo usarla
Antes de incluir cualquier recurso visual, musical o de audio en el pipeline.

## Entradas
- URL o referencia del recurso.
- Tipo (imagen, música, vídeo).
- Fuente (Pexels, Pixabay, etc.).

## Salidas
- Veredicto: APROBADO | CONDICIONAL (requiere atribución) | RECHAZADO.
- Texto de atribución si es requerido.

## Procedimiento
1. Identificar la licencia del recurso en la fuente.
2. Verificar si requiere atribución y en qué formato.
3. Verificar si permite uso comercial (si aplica a futuro).
4. Documentar la decisión.

## Validaciones
- La licencia está documentada en la fuente oficial.
- No asumir licencia por defecto.

## Límites
- No verificar licencias de herramientas (FFmpeg, n8n) — solo de contenido.
- No usar scraping como método de obtención de recursos.
