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

## REQ-009: Validación semántica hard
- Escenas con `editorialRole=context_map` solo aceptan assets cuyo `effectiveAssetType` (inferido desde metadata del candidato) sea `map`, `historical_map`, `document`, `newspaper`, `map_or_document` o `historical_map_or_document`. No se debe confiar solo en `primaryAssetType` declarado. Se debe verificar `roleEvidence` no vacío con indicadores de contexto-mapa.
- Escenas con `visualTemporalIntent=event_depiction` solo aceptan assets con `assetTemporalMatch` igual a `historical_event` o `archival_context`.
- El campo `assetTemporalMatch` debe calcularse usando matching sin acentos, equivalencias multilingües y extracción de año desde `period`, `entities` y `voiceover`.
- Assets con indicadores modernos (`anniversary`, `celebration`, `commemoration`, etc.) y sin año de evento coincidente deben clasificarse como `modern_legacy`.
- Mapas y documentos históricos con match de entidad/ubicación deben clasificarse como `archival_context` aunque no tengan año explícito en su metadata.

## REQ-013: Inferencia de tipo de asset efectivo
- `_infer_effective_asset_type(candidate, declared_type)` debe determinar si un candidato es realmente un mapa, documento o fotografía basándose en indicadores en su título, descripción y URL.
- La metadata de cada asset debe registrar `declaredAssetType`, `effectiveAssetType` y `assetTypeValidationStatus`.
- Los indicadores de documento deben evaluarse antes que los de mapa (un documento SOBRE un mapa sigue siendo un documento).

## REQ-010: Reutilización segura de assets
- Solo se permite reutilizar el asset válido anterior en la última escena o en escenas `consequence_or_legacy`.
- Para `event_depiction`, no se permite reusar assets clasificados como `modern_legacy` ni `unknown`.
- La compatibilidad de reuso debe comparar años extraídos del asset reusado y de la escena destino (`period` + `voiceover`); si no hay intersección, se bloquea.
- Al reusar, se debe re-evaluar `assetTemporalMatch` en el contexto de la escena destino y actualizarlo en el asset y sus segmentos.
- El asset reusado debe conservar `title`, `description` y metadatos de provenancia original (`originalSceneNumber`, `originalEditorialRole`, `originalVisualTemporalIntent`, `reuseCompatibilityReason`).

## REQ-011: Queries históricas para event_depiction
- Cuando el intent temporal de una escena sea `event_depiction`, deben generarse queries históricas (`build_historical_queries`) independientemente de si el `editorialRole` está en `HARD_HISTORICAL_ROLES`.

## REQ-012: Metadata de evidencia semántica
- `semanticEvidence` debe incluir `roleEvidence` y `assetTypeEvidence` además de términos coincidentes y confianza.

## REQ-014: Aislamiento de artefactos derivados entre jobs
- Al clonar un job, el nuevo `metadata.json` no debe contener `assets`, `timeline`, `renderTimeline`, `subtitles`, `render`, `assetValidation`, `validation`, `review` ni `resolvedConfig` del job origen.
- El estado inicial de un job clonado debe ser `SCRIPT_READY`.
- Las rutas locales en `metadata.json` deben pertenecer únicamente al directorio del job actual.

## REQ-015: Validación de referencias cruzadas
- `render_job.py` debe fallar con `CROSS_JOB_ARTIFACT_REFERENCE` durante el preflight si cualquier campo de ruta local apunta fuera del directorio del job.

## REQ-016: Rol `border_closure_construction`
- `border_closure_construction` es un rol hard histórico: solo fuentes de archivo, sin stock ni IA.
- Debe aceptar evidencia directa de cierre de frontera/construcción de barreras: `barbed wire`, `barricades`, `road block`, `border closure`, `Stacheldraht`, `Mauerbau`, `Abriegelung`, `Grenzsperre`, `Sperranlagen`, etc.
- Debe rechazar fotos de separación familiar, conmemoraciones/aniversarios y checkpoints genéricos.
- El campo `semanticEvidence.borderClosureSubjectEvidence` debe ser no vacío y no debe contener indicadores de rechazo para que el asset pase el hard rule.

## REQ-017: Separación de evidencia de fecha depicted vs contexto
- `_classify_date_evidence()` debe separar `sourceDepictedDateEvidence` (años que el asset muestra realmente) de `sourceContextDateEvidence` (años mencionados como contexto, ej. rangos retrospectivos "1961 - 1989").
- Un rango con guión en el título (e.g. "The Berlin Wall 1961 - 1989") debe tratarse como contexto, no como depiction de cada año en el rango.
- Cada conjunto (depicted, context) se mantiene independiente. Un año se considera "depicted" si existe algún cue depictivo independiente.
- `has_event_year` para matching temporal debe excluir años que solo aparecen en rangos de contexto.

## REQ-018: Compatibilidad de reuso basada en fechas depicted
- El reuso debe comparar `sourceDepictedDateEvidence` del asset origen contra los años extraídos de la escena destino (`period` + `voiceover`). Si no hay intersección, se bloquea.
- El reuso debe rechazarse cuando el rol editorial original es `civilian_impact` y la escena destino difiere materialmente del evento origen (ej. asset de separación familiar de 1961 reusado para escena de caída de 1989).
- El reuso de assets con `divisionSubjectEvidence` (separación familiar) para escenas de caída/legado sin evidencia de caída debe bloquearse.
- El motivo del bloqueo o aprobación debe registrarse en `reuseCompatibilityReason`.
