# Tareas: Mejora de Variedad Visual y Calidad Editorial

## Fase 1 — Diseño y OpenSpec
- [x] Crear proposal.md
- [x] Crear design.md con contratos actualizados
- [x] Crear tasks.md
- [x] Crear specs/anti-repetition.md
- [x] Crear specs/map-treatment.md
- [x] Crear specs/editorial-roles.md

## Fase 2 — generate_script.py
- [x] Añadir `editorialRole` al visualPlan en system prompt
- [x] Añadir reglas de segmentación por editorialRole
- [x] Añadir `focalRegion`, `cropMode`, `overlayText` en segmentos de mapa
- [x] Limitar atmospheric_transition a 20% de escenas
- [x] Reforzar que escenas >4s generen ≥2 segmentos
- [ ] MEJORA FUTURA: El LLM sigue sin generar ≥2 segmentos en escenas 5-7s consistentemente (2 de 7 fallaron)
- [ ] MEJORA FUTURA: Scene 7 sigue teniendo editorialRole=null

## Fase 3 — fetch_images.py

### 3.1 Sistema de anti-repetición
- [x] Añadir penalización -40 por mismo author+provider en escenas consecutivas
- [x] Añadir penalización -30 por misma query usada <3 escenas antes
- [x] Añadir penalización -20 por mismo assetType que escena anterior
- [x] Añadir penalización -50 por URL duplicada
- [x] Guardar `duplicateRisk`, `previousSimilarAssets`, `reuseAllowed`

### 3.2 Mejora de queries
- [x] Ampliar STRATEGY_VISUAL_QUERIES con pool diverso (13-15 queries por strategy)
- [x] Implementar rotación de queries para evitar mismo author
- [x] Añadir penalización si author ya apareció en vídeo

### 3.3 Filtros editoriales
- [x] Editorial role scoring: +15 para preferred, -20 para forbidden
- [x] Si editorialRole es character_portrait, penalizar broll (-20)
- [x] Rechazo de mapas con dimensiones <800x800 (en download)

## Fase 4 — prepare_job.py
- [x] Propagar nuevos campos editoriales al timeline
- [x] Propagar duplicateRisk, focalRegion, cropMode, overlayText
- [x] Propagar visualAuthenticityRisk si existe

## Fase 5 — render_job.py

### 5.1 Tratamiento de mapas
- [x] Implementar blur background derivado del mapa (gblur=sigma=40)
- [x] Implementar crop a focalRegion (center/north/south/east/west)
- [x] Reservar 15% inferior para subtítulos (drawbox negro 55% opacidad)
- [ ] PENDIENTE: overlay drawtext de fecha/lugar (requiere libfontconfig)

### 5.2 Tratamiento de retratos
- [ ] PENDIENTE: Si mismo retrato se repite, aplicar crop/zoom diferente
- [ ] PENDIENTE: Overlay de nombre si hay datos

### 5.3 Reconstrucciones IA
- [x] Aplicar reduce saturación 15% (colorlevels=rimax=0.85)
- [x] Añadir grano cinematográfico leve (noise=alls=3)

## Fase 6 — Validación
- [x] Generar job nuevo: la-2026-07-01-171519
- [x] fetch_images con anti-repetición activo
- [x] prepare_job con campos editoriales
- [x] render_job con mapas legibles en 9:16
- [x] Verificar que no hay repetición injustificada de assets (0 assets repetidos)
- [x] Verificar atmospheric_transition = 0% (≤ 20% ✓)
- [x] Tabla comparativa vs vídeo anterior

## Fase 7 — Informe
- [x] Documentar resultados reales
- [x] Documentar limitaciones
- [x] Actualizar bitácora de sesión
