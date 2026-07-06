# Sesión: Phase 23 follow-up — prompt improvements + hard role fallback

- Fecha: 2026-07-05
- Objetivo: Fix asset resolution failures discovered in Phase 23 real-run verification. Original diagnosis was wrong — `editorialRole` WAS populated by LLM; real issue was hard historical roles restrict provider chain to Wikimedia Commons only.
- Cambio OpenSpec: improve-historical-visual-pipeline (Phase 23 follow-up)

## Cambios realizados

### 1. generate_script.py — prompt improvements

- **Added `visualTemporalIntent` field** to scene-level JSON schema (`event_depiction|legacy_or_commemoration|context_or_setup`)
- **Added `visualTemporalIntent` rules section** with classification guidance based on editorialRole and voiceover content
- **Improved Wikimedia Commons query guidance**: each searchQuery must include named entity + year, minimum 2 queries per scene, avoid generic queries
- **Added editorialRole decision tree** (8-step deterministic evaluation order)
- **Added `context_map` exclusion rule**: explicitly forbid using context_map for events (caída, batalla, protesta, celebración) — use civilian_impact, battle_or_assault or consequence_or_legacy instead
- **Added detailed role descriptions** with explicit restrictions per role
- **Added `character_portrait` exclusion**: NO use if no specific historical person mentioned

### 2. fetch_images.py — hard role fallback

- **Added `_try_hard_role_fallback()`** function (lines 1806-1990)
- Triggered when Wikimedia Commons exhausts queries for hard historical roles
- Tries Pexels then Pixabay with strict relevance filters:
  - Reject negative score
  - Reject low semantic confidence
  - Reject modern_legacy for event_depiction scenes
  - Reject render-failing candidates
  - Require topic or location match
- Fallback assets carry provenance metadata:
  - `provenanceType: "illustrative"` (vs "documentary" for Wikimedia)
  - `fallbackReason: "Wikimedia returned no candidates for editorialRole=X"`
  - `originalEditorialRole: <original role>`
- Preserves ASSET_UNRESOLVED blocking state if no acceptable fallback found
- Modified main loop (lines 2334-2358) to call fallback before marking ASSET_UNRESOLVED

### 3. Tests

- **10 new tests** in `tests/test_generate_script.py` (prompt content validation)
- **4 new tests** in `tests/test_semantic_asset_validation.py`:
  - `test_hard_role_fallback_to_pexels_with_acceptable_candidate` — Wikimedia exhausts → Pexels fallback with acceptable candidate → returns seg_entry with provenance
  - `test_hard_role_fallback_rejected_for_weak_relevance` — fallback candidate rejected for low semantic confidence → returns None
  - `test_hard_role_fallback_all_providers_exhausted` — no candidates from any fallback provider → returns None (preserves blocking state)
  - `test_hard_role_fallback_no_api_keys` — no API keys configured → returns None
- **Total: 209/209 tests pass** (was 195 before this session)

## Real-run verification

### Job la-2026-07-05-193524 (Berlin Wall, --duration 30 --duration-max 35)

| Scene | editorialRole | visualTemporalIntent | Provider | Provenance | Result |
|-------|---------------|----------------------|----------|------------|--------|
| 1 | context_map | event_depiction | wikimedia_commons | documentary | ✅ selected |
| 2 | civilian_impact | event_depiction | pexels (fallback) | illustrative | ✅ selected |
| 3 | battle_or_assault | event_depiction | pexels (fallback) | illustrative | ✅ selected |
| 4 | consequence_or_legacy | legacy_or_commemoration | — | — | ❌ download failed |
| 5 | consequence_or_legacy | legacy_or_commemoration | — | — | ❌ download failed |

**Improvement**: 1/5 → 3/5 scenes resolved. Fallback provenance correctly tagged as `illustrative`.

**Remaining failures**: Scenes 4-5 use `atmospheric_broll` strategy (soft role, not hard historical) — fallback does not apply. Failed on download (Pexels/Pixabay returned no candidates for "Berlin Wall memorial today" / "Unity in Berlin").

### Editorial role assignment verification

The new decision tree correctly classified:
- Scene 1 with voiceover about 1961 construction + map content → context_map ✅
- Scene 2 with voiceover about oppression/daily life → civilian_impact ✅
- Scene 3 with voiceover about "el muro finalmente cayó" → battle_or_assault ✅
- Scenes 4-5 with voiceover about legacy/unity → consequence_or_legacy ✅

No scenes were incorrectly assigned context_map for event content.

## Files changed

### Modified
- `bin/generate_script.py` — prompt improvements (visualTemporalIntent, query guidance, editorialRole decision tree)
- `bin/fetch_images.py` — added `_try_hard_role_fallback()` + main loop integration
- `tests/test_semantic_asset_validation.py` — 4 new fallback tests
- `openspec/changes/improve-historical-visual-pipeline/tasks.md` — corrected root cause, added follow-up section
- `docs/sessions/2026-07-05-1849-runner-real-staged-verification.md` — corrected root cause

### Created
- `tests/test_generate_script.py` — 10 new prompt content tests

## Limitations

1. **Real-run through prepare/validate not completed** — assets stage still partially fails for atmospheric_broll scenes (not a hard-role issue). Audio/prepare/validate stages remain unit-tested only for the runner contract verification.
2. **LLM duration contract variability** — additional prompt rules about editorialRole/visualTemporalIntent/queries may cause the LLM to generate more words, occasionally triggering REVIEW_REQUIRED. Looser `--duration-max` values (e.g., 35) help.
3. **Fallback provenance is `illustrative`** — Pexels/Pixabay assets are not archival documentary evidence. The `provenanceType` field distinguishes them from Wikimedia Commons documentary assets.
## Segunda iteración (2026-07-05): soft-role classification defect

### Diagnóstico

Tras los cambios anteriores, las escenas 4 y 5 del job `la-2026-07-05-193524` seguían fallando aunque el fallback de roles duros no aplicaba. Diagnóstico puntual de cada segmento:

- **API search OK**: 60 candidatos recibidos de Pexels + Pixabay por escena ( algunos claramente relevantes: "berlin, berlin wall, fall of the wall" en Pixabay).
- **Fallo en filtrado de stage 1**:
  1. `_classify_temporal_intent()` ignoraba el campo LLM `scene.visualTemporalIntent` y usaba solo una heurística de substring sobre el voiceover. Para escenas `consequence_or_legacy` con voiceover "La caída del muro..." (escena 4) o sin indicadores (escena 5), la heurística devolvía `event_depiction` (default). La hard rule "event_depiction + assetTemporalMatch in {unknown, modern_legacy} → reject" descartaba los 60 candidatos modernos.
  2. `EDITORIAL_ROLE_PREFERENCES["consequence_or_legacy"].forbidden = {atmospheric_broll, broll, generated_reconstruction}` combinado con `c["strategy"] = strategy` (la strategy de la escena) en `_fetch_one_asset` rechazaba cualquier candidato si la escena tenía strategy=atmospheric_broll.
- **No fallo de descarga, scoring, renderabilidad ni path/metadata.**

### Corrección mínima (bin/fetch_images.py)

1. `_classify_temporal_intent()` ahora respeta el campo LLM `scene.visualTemporalIntent` cuando está presente y es válido (`event_depiction|legacy_or_commemoration|context_or_setup`). Sólo cae a la heurística si falta el campo (backward compatibility con jobs antiguos y unit tests existentes).
2. En `_fetch_one_asset` stage 1, calculamos `forbidden_types` como copia mutable y descartamos `atmospheric_broll`/`broll` cuando `editorialRole=consequence_or_legacy` y `_classify_temporal_intent(scene) == "legacy_or_commemoration"`. Las scenes de event_depiction mantienen su set estricto original.
3. Endurecemos el rechazo de baja evidencia: si `semanticConfidence == "low"` Y no hay `topicTermsMatched` Y no hay `locationTermsMatched` → rechazo (antes solo se rechazaba si no había `sourceTitle`). Defensa contra stock genérico sin traslape temático.

### Tests añadidos (tests/test_semantic_asset_validation.py)

- `test_classify_temporal_intent_respects_llm_legacy_field_despite_event_keywords`
- `test_classify_temporal_intent_respects_llm_legacy_field_when_no_indicator_matches`
- `test_classify_temporal_intent_respects_llm_event_depiction_field`
- `test_classify_temporal_intent_falls_back_to_heuristic_when_field_absent`
- `test_classify_temporal_intent_ignores_invalid_llm_field`
- `test_soft_role_legacy_scene_accepts_modern_legacy_candidate_regression`
- `test_soft_role_legacy_scene_rejects_unrelated_candidate`
- `test_soft_role_legacy_scene_blocks_when_no_candidate`

**Suite completa: 216/216 pass.**

### Verificación real del runner (job la-2026-07-05-203359)

Comando:

```
python3 bin/run_job.py --topic "La caída del Muro de Berlín" \
  --duration 30 --duration-max 35 --stop-after prepare --verbose
```

**Resultado**: pipeline completó script → assets → audio → prepare.

| Stage | statusHistory | Result |
|-------|---------------|--------|
| script | SCRIPT_DRAFT | ✅ PASS |
| assets | ASSETS_FETCHING → ASSETS_READY | ✅ PASS |
| audio | AUDIO_GENERATING → AUDIO_READY | ✅ PASS |
| prepare | PREPARING → SUBTITLES_READY | ✅ PASS |

**Status final**: SUBTITLES_READY

#### Job identity
- jobId: `la-2026-07-05-203359`
- jobPath: `data/videos/la-2026-07-05-203359/`

#### Orchestration statusHistory (7 entries, truthfully covering only script/assets/audio/prepare)

1. `script: SCRIPT_DRAFT @ startedAt → finishedAt 20:33:59`
2. `assets: ASSETS_FETCHING @ 20:33:59`
3. `assets: ASSETS_READY @ 20:39:23`
4. `audio: AUDIO_GENERATING @ 20:39:23`
5. `audio: AUDIO_READY @ 20:39:23`
6. `prepare: PREPARING @ 20:39:28`
7. `prepare: SUBTITLES_READY @ 20:39:28`

`render`, `validate`, `review_job` NO ejecutados.

#### Scene/segment resolution

| Scene | editorialRole | visualTemporalIntent | Provider | Provenance | selected | pathOnDisk |
|-------|---------------|----------------------|---------|------------|----------|-------------|
| 1 | battle_or_assault | event_depiction | pexels (fallback) | illustrative | TRUE | scenes/scene-01-01.jpg |
| 2 | context_map | event_depiction | wikimedia_commons | documentary | TRUE | scenes/scene-02-01.jpg |
| 3 | civilian_impact | event_depiction | pexels (fallback) | illustrative | TRUE | scenes/scene-03-01.jpg |
| 4 | consequence_or_legacy | legacy_or_commemoration | wikimedia_commons | documentary | TRUE | scenes/scene-04-01.jpg |
| 5 | consequence_or_legacy | legacy_or_commemoration | wikimedia_commons (reuse of escena 4) | documentary | TRUE | scenes/scene-04-01.jpg |

Provider/provenance distribution:
- 3 documentary assets from Wikimedia Commons (escenas 2, 4, 5)
- 2 illustrative assets from Pexels fallback (escenas 1 y 3, hard historical roles — provenance=rather than silently treating stock as archival)
- 0 Pixabay, 0 FreeAI, 0 Pollinations

#### Audio stage

Edge TTS generó 5 narration files (scene-01..05.mp3) en `scenes/`. AUDIO_READY.

#### Prepare stage artefactos

- `subtitle.ass` existente, 1661 bytes.
- `renderTimeline` (5 events, list) starts at startSec=0.0 ends at endSec=30.0 — covers full narration duration (~30s target).
- `render.path = ...video.mp4` (path planeado; el archivo físico no existe porque `--stop-after prepare` detiene antes del render).

#### Cross-job paths

Verificado: 0 referencias fuera de `data/videos/la-2026-07-05-203359/`. Scene 5 reusa scene-04-01.jpg (reuso permitido para última escena / consequence_or_legacy, ambas condiciones cumplidas) — path dentro del job.

#### video.mp4 NO existe (correcto)

```
ls: cannot access 'video.mp4': No such file or directory
```

#### Runner verdict: VERIFICADO through prepare.

- Todas las 5 escenas resolvieron assets (no FAILED/ASSET_UNRESOLVED).
- Audio generado para 5 escenas (AUDIO_READY).
- Subtítulos generados (SUBTITLES_READY).
- renderTimeline tracks 0.0-30.0s.
- Paths absolutos todos dentro del job directory.
- Orchestration truthfully cubre solo script/assets/audio/prepare.

### Stages STILL unverified (not closed)

- `render` — no ejecutado; `run_job.py` con `--stop-after prepare` detiene antes.
- `validate` — no ejecutado; llegue el paso del runner OK.

OpenSpec change `improve-historical-visual-pipeline` NO se cierra.

### Archivos changados (segunda iteración)

- `bin/fetch_images.py`: `_classify_temporal_intent()` respeta LLM field; `_fetch_one_asset` stage 1 relaxes atmospheric_broll forbiddance para legacy_or_commemo scenes; stage 1 low-confidence rejection strengthened para sin topic/location match.
- `tests/test_semantic_asset_validation.py`: 8 nuevos regression tests; corregido `assert result is None` del test previo (ahora `is not None`).
