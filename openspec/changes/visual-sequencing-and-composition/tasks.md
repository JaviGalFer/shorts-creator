# Tareas: Visual Sequencing and Composition

## Fase 1 — Diseño y OpenSpec
- [x] Diseñar contrato visualSequence
- [x] Diseñar formato de timeline plano
- [x] Definir tratamiento por assetType
- [x] Definir reglas de secuenciación

## Fase 2 — generate_script.py
- [ ] Actualizar system prompt con visualSequence
- [ ] Cada escena debe generar 1-3 segmentos según duración
- [ ] Incluir editorialReason por segmento
- [ ] Mantener compatibilidad: si no hay visualSequence, comportamiento legacy

## Fase 3 — fetch_images.py
- [ ] Detectar visualSequence en visualPlan
- [ ] Buscar asset por segmento (1 asset por searchQuery única)
- [ ] Almacenar como segments array en el asset entry de la escena
- [ ] Mantener path legacy apuntando al primer segmento
- [ ] Compatibilidad: escenas sin visualSequence → segmento único implícito

## Fase 4 — prepare_job.py
- [ ] Si hay segments, resolver timeline plano global
- [ ] Calcular start/end times absolutos
- [ ] Asignar transiciones entre segmentos
- [ ] Guardar timeline en metadata
- [ ] Compatibilidad: sin segments, timeline legacy 1:1 con escenas

## Fase 5 — render_job.py
- [ ] Leer timeline en vez de scenes directamente
- [ ] Para cada segmento: -loop 1 -t duración -i imagen
- [ ] Audio: 1 por escena (se comparte entre segmentos de la misma escena)
- [ ] Construir filter graph con concat por escena + concat global
- [ ] Implementar transition=fade con xfade
- [ ] Fondo borroso para landscape maps (scale + crop + blur + overlay)
- [ ] Compatibilidad: timeline plano legacy

## Fase 6 — Validación
- [ ] Generar job nuevo con visualSequence
- [ ] fetch_images descarga N assets por escena
- [ ] prepare_job genera timeline correcto
- [ ] render_job produce video con múltiples segmentos
- [ ] Verificar transiciones cut y fade
- [ ] Verificar mapa landscape con fondo borroso
- [ ] Tabla final por escena

## Fase 7 — Informe
- [ ] Documentar resultados
- [ ] Documentar limitaciones
