# Especificación: Selección de assets visuales

## REQ-001: visualPlan
- Una escena con `visualPlan.strategy=historical_archive` debe intentar fuentes de archivo (Wikimedia, LoC) antes que generación IA.
- `visualPlan` es opcional. Jobs sin él deben seguir funcionando con `visualPrompt`.

## REQ-002: Fallback
- Si una estrategia no produce resultados válidos, debe ejecutarse el fallback definido.
- El fallback aplicado debe registrarse en el asset metadata.

## REQ-003: Metadata de assets
- Cada asset seleccionado debe guardar: `provider`, `sourceUrl`, `queryUsed`, `score`, `scoreReasons`, `license`, `width`, `height`.
- Si un campo no está disponible, guardar `null`.

## REQ-004: Múltiples candidatas
- Por cada escena deben evaluarse entre 3 y 5 candidatas.
- Solo se descarga la candidata seleccionada.
- Las candidatas descartadas se guardan en `discardedCandidates` con motivo.

## REQ-005: Scoring
- Los pesos deben estar centralizados en una constante `SCORING_WEIGHTS`.
- El score debe ser la suma de todos los pesos aplicados.
- Cada peso aplicado debe tener una razón textual en `scoreReasons`.

## REQ-006: Compatibilidad legacy
- Un job sin `visualPlan` debe seguir renderizando usando `visualPrompt` como fallback.
- Si existe `imagePrompt` y no `visualPrompt`, usarlo como segundo fallback.

## REQ-007: Seguridad
- El pipeline no debe guardar secretos en metadata, logs, ni documentación.
- HANDOVER.md y bitácoras no deben contener valores de API keys.

## REQ-008: Sin resultados
- Si no hay resultado válido tras toda la cadena de fallback, debe registrarse en `assets[].error` y continuar.
