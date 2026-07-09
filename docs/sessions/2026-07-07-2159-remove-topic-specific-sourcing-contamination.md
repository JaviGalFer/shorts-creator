# Session: Remove topic-specific sourcing contamination

**Started:** 2026-07-07 21:59 UTC
**Type:** Decontamination refactor (Level 1)
**OpenSpec change:** `improve-historical-visual-pipeline` (task note updated)

## Objective

Remove all Berlin-specific and Constantinople/Istanbul-specific hardcoded vocabulary from reusable production code (`bin/fetch_images.py`, `bin/asset_validation.py`). The pipeline must derive its visual search/scoring inputs only from job metadata (topic, scene entities, location, period, search queries).

## What was removed

### From `bin/fetch_images.py`:

1. **`_check_semantic_evidence`**: Removed hardcoded `topic_terms.update` with "berlin wall", "berliner mauer", "muro de berlín", "cold war", "guerra fría", "post-war", "posguerra". Removed hardcoded `location_terms.update` with "berlin", "berlín", "germany", "alemania". Removed hardcoded `period_terms.update` with "1961", "1989", "fall of the wall", "caída del muro", etc.

2. **`_build_scene_query_variants`**: Removed the entire hardcoded German query variant section (`german_loc = "Berlin"`, `german_terms` dict with Berliner-Mauer-specific templates, hardcoded 1961/1989 checks). Queries now derive exclusively from scene metadata.

3. **`_determine_asset_temporal_match`**: Removed Berlin-specific entries from `period_equivalents` ("fall of the berlin wall", 1989/1990 years from post-Guerra-Fría), `location_equivalents` (berlín→berlin, berlin→berliner, berlín/alemania combos), and `entity_equivalents` (muro de berlín→berlin wall, berlín→berlin). Kept generic terms: "alemania"→german translations, "familias"→family translations.

4. **`_MAP_INDICATORS`**: Removed Berlin-specific terms ("sectors of berlin", "east berlin west berlin", "berlin sectors", "allied sectors", "soviet sector", "zones of berlin", "berlin zones"). Kept generic terms: "map", "cartography", "division of", "occupation zones", "partition", "sectors".

5. **`_PHOTO_INDICATORS`**: Removed "berlin wall in".

6. **`_BORDER_CLOSURE_REJECT_INDICATORS`**: Removed "checkpoint charlie".

7. **`_FALL_OPENING_SUBJECT_INDICATORS`**: Removed Berlin-specific "fall of the berlin wall", "fall of the berlin", "mauerfall", "maueröffnung", "atop the berlin wall", "juggling on the berlin wall". Kept generic: "wall coming down", "border opening", "people on the wall".

8. **`_classify_date_evidence`**: Removed Berlin-specific retrospective cues ("the berlin wall", "berliner mauer") and depicting cue ("construction of the berlin"). Removed "juggling" from depicting cues.

9. **`_border_closure_subject_indicators`**: Removed "mauerbau", "berliner mauer bau", "bau der mauer". Kept generic: "barbed wire", "stacheldraht", "barricade", "grenzsperre", "abriegelung", "sperranlagen".

10. **`role_terms_by_role` in `_check_semantic_evidence`**: Removed Berlin-specific role terms: "berlin sectors", "east berlin", "west berlin" from context_map; "mauerbau" from border_closure_construction; "mauerfall" from consequence_or_legacy.

11. **Comments**: Cleaned Berlin references from code comments throughout.

### From `bin/asset_validation.py`:

1. **`THEME_CONSTRAINTS`**: Removed hardcoded Constantinople theme entry entirely. Dict is now empty.
2. **`LEGACY_KEYWORDS`**: Removed "Estambul", "estambul", "istanbul". Kept generic Spanish/English legacy terms.
3. **`MODERN_QUERY_KEYWORDS`**: Removed "istanbul", "estambul". Kept generic modern-city terms.
4. **`check_modern_asset_context`**: Removed Istanbul-specific location check.

## What was retained (generic concepts)

- **Editorial roles**: All role definitions (`context_map`, `battle_or_assault`, etc.) are topic-agnostic and remain unchanged in `editorial_asset_contract.py`.
- **German translation infrastructure**: Generic German terms remain: "stacheldraht" (barbed wire), "sperranlagen" (barrier installations), "abriegelung" (cordon), "grenzsperre" (border barrier), "strassensperre" (road closure), "besatzungszonen" (occupation zones), "sektoren" (sectors), "teilung" (division). These describe generic military/construction/border concepts.
- **Generic multilingual equivalents**: "alemania"→german translations, "familias"→family translations, "guerra fría"→cold war translations.
- **Generic map/photo/document indicators**: "map", "karte", "cartography", "photograph", "document", etc.
- **Generic border/construction terms**: "barbed wire", "barricades", "wall coming down", "construction workers".
- **Generic legacy/commemoration terms**: "hoy", "legado", "memoria", etc.
- **LLM system prompt**: Teaching examples in `generate_script.py` SYSTEM_PROMPT were not changed (Level 2 work).

## Tests added

- **`tests/test_no_topic_specific_contamination.py`** (22 tests):
  - Source-level regression: `bin/fetch_images.py` and `bin/asset_validation.py` reject prohibited Berlin/Constantinople terms
  - Photosynthesis fixture: queries and semantic evidence contain no Berlin/Mauer/Cold War contamination
  - French Revolution fixture: queries derive from Bastilla, París, 1789
  - Berlin fixture: still derives Berlin terms from its own metadata (not hardcoded lists)
  - Generic indicator tests: `_MAP_INDICATORS`, `_PHOTO_INDICATORS`, etc. are topic-agnostic
  - Contract tests: `THEME_CONSTRAINTS` empty, `LEGACY_KEYWORDS` no Istanbul
  - Source inspection: no `german_loc`, `german_terms` in `_build_scene_query_variants`

## Existing tests updated

- `test_border_closure_evidence_accepts_barbed_wire`: Relaxed `semanticConfidence` assertion (low is valid without hardcoded Berlin terms)
- `test_juggling_berlin_wall_1989_passes_target_event_1989`: Removed `fall_opening` evidence assertion (juggling indicator removed); kept 1989 date extraction assertion

## Result

- **328 tests passed**, 0 failed
- `git diff --check` clean
- No Berlin-specific production policy or compatibility module created
- No live provider run executed
- No mode flags, no new providers, no API changes
- Pipeline contracts, metadata shape, and fallback policy unchanged

## Remaining work before production modes

1. **German query derivation**: The generic query builder could be enhanced to derive language-specific query variants from metadata when a non-English language is requested (currently only English + scene entity terms)
2. **Multilingual equivalence expansion**: The `period_equivalents`/`location_equivalents`/`entity_equivalents` dictionaries could be supplemented with dynamic lookups from the scene metadata rather than being fully static
3. **LLM prompt generalization**: `generate_script.py` SYSTEM_PROMPT contains Berlin/Constantinople teaching examples; replacing with generic placeholders would level the LLM prompt bias
4. **`border_closure_construction` role documentation**: This role is generic but its origin is tied to Berlin Wall validation patterns; a naming review may be warranted
5. **Remove `LEGACY_KEYWORDS` from production**: The legacy keywords set in `asset_validation.py` contains Spanish words that bias toward Spanish-language topics; a dynamic topic/trigger approach should replace it
