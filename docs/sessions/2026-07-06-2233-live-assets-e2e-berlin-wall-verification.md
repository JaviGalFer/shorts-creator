# Sesión: E2E live assets Berlin Wall verification

- Fecha: 2026-07-07
- Objetivo: Verificación E2E del pipeline completo con live asset sourcing, fixture manual determinista, sin LLM.
- Cambio OpenSpec: `improve-historical-visual-pipeline`
- Modelo: DeepSeek V4 Pro

## Fixture

- jobId: `e2e-live-assets-berlin-wall-20260707-002651`
- Path: `data/videos/e2e-live-assets-berlin-wall-20260707-002651/`
- 4 scenes, 8 segments (2 per scene)
- Periodos: 1945 / 1961 / 1961 / 1989-presente
- Roles: context_map / border_closure_construction / civilian_impact / consequence_or_legacy
- Intents: event_depiction / event_depiction / event_depiction / legacy_or_commemoration
- Structure validation: PASSED (pre-fetch)

## Commands

```bash
python3 bin/fetch_images.py data/videos/e2e-live-assets-berlin-wall-20260707-002651/metadata.json
```

## Stage: fetch_images — FAILED

Exit code: non-zero (success=false)
Metadata status: ASSET_UNRESOLVED

### Resolved segments (3/8)

| Scene | Seg | Role | Intent | Requested Type | Effective Type | Provider | Score | SemConfidence | Path |
|-------|-----|------|--------|---------------|----------------|----------|-------|---------------|------|
| 1 | 1 | context_map | event_depiction | historical_map | historical_map | wikimedia_commons | 90 | medium | scene-01-01.jpg |
| 2 | 1 | border_closure_construction | event_depiction | historical_photograph | historical_photograph | wikimedia_commons | 105 | high | scene-02-01.jpg |
| 3 | 1 | civilian_impact | event_depiction | historical_photograph | historical_photograph | wikimedia_commons | 75 | high | scene-03-01.jpg |

### Unresolved segments (5/8)

| Scene | Seg | Role | Requested Type | Error | Classification |
|-------|-----|------|---------------|-------|---------------|
| 1 | 2 | context_map | document | ASSET_UNRESOLVED | Wikimedia exhaustion (no document with roleEvidence for "Berlin sectors occupation document 1945") |
| 2 | 2 | border_closure_construction | historical_photograph | ASSET_UNRESOLVED | Wikimedia exhaustion (no candidate with borderClosureSubjectEvidence for "Constructing Berlin Wall September 1961") |
| 3 | 2 | civilian_impact | historical_photograph | ASSET_UNRESOLVED | Wikimedia exhaustion (no candidate for "Bernauer Strasse families Berlin Wall 1961") |
| 4 | 1 | consequence_or_legacy | historical_photograph | Download failed | All providers exhausted (Wikimedia 0 results, Pexels no key, Pixabay no key, FreeAI no key, Pollinations failed) |
| 4 | 2 | consequence_or_legacy | atmospheric_broll | Download failed | All providers exhausted (same chain, no API keys for stock providers) |

### Asset details for resolved segments

**Scene 1 Seg 1** (context_map → historical_map):
- Source: `https://upload.wikimedia.org/.../1945_Berlin_Zones_(30249103203).jpg`
- License: Public domain, CIA from Flickr
- Dimensions: 1762×1330
- Temporal match: historical_event
- Depicted dates: [1945]
- Role evidence: [zones]

**Scene 2 Seg 1** (border_closure_construction → historical_photograph):
- Source: `https://upload.wikimedia.org/.../Constructing_Berlin_Wall_-_Flickr_-_The_Central_Intelligence_Agency.jpg`
- License: Public domain, CIA from Flickr
- Dimensions: 930×1234
- Temporal match: historical_event
- Depicted dates: [1961]
- Role evidence: [construction, building]
- Border closure evidence: [construction of the wall]

**Scene 3 Seg 1** (civilian_impact → historical_photograph):
- Source: `https://upload.wikimedia.org/.../The_Berlin_Wall_1961_-_1989_HU99516.jpg`
- License: Public domain, Siegmann, Horst
- Dimensions: 1800×1200
- Temporal match: archival_context
- Depicted dates: [1961]
- Role evidence: [family, families, familie, separated]

### Provider summary

- wikimedia_commons: 3 resolved
- pexels: 0 (no API key)
- pixabay: 0 (no API key)
- freeai: 0 (no API key)
- pollinations: 0 (download failed)

### Anti-repetition

Not exercised meaningfully (only 3 segments resolved, each from distinct queries).

### Fallback

No fallback triggered. Hard-role scenes 1-3 exhausted Wikimedia with no Pexels/Pixabay keys for fallback. Scene 4 (soft role) exhausted all providers including Pollinations.

## Stop reason

- `fetch_images.py` returned non-zero exit code
- Metadata status = `ASSET_UNRESOLVED`
- 5 of 8 segments unresolved

## Stages NOT executed

- generate_audio.py
- prepare_job.py
- render_job.py
- validate_job.py

## Files created

- `e2e-live-assets-berlin-wall-20260707-002651/metadata.json` (updated with assets)
- `e2e-live-assets-berlin-wall-20260707-002651/scenes/scene-01-01.jpg` (1.5 MB)
- `e2e-live-assets-berlin-wall-20260707-002651/scenes/scene-02-01.jpg` (283 KB)
- `e2e-live-assets-berlin-wall-20260707-002651/scenes/scene-03-01.jpg` (364 KB)

## Source-code changes

Zero. No source code modified.

## Root cause analysis

The hard historical role provider restriction (wikimedia_commons only) limits asset diversity. For topics like the Berlin Wall, Wikimedia has a finite set of relevant images. The 8-segment requirement (2 per scene) exceeds the available pool when:
1. The second segment per scene needs a DIFFERENT image from the first (anti-repetition)
2. The strict editorial validators reject candidates that don't precisely match role evidence
3. No stock photo API keys are configured for soft-role fallback

Scene 4 (consequence_or_legacy) failed because no API keys are set and Pollinations download failed.

## Mitigation

To pass this E2E test with live assets:
- Configure PEXELS_API_KEY and/or PIXABAY_API_KEY for soft-role fallback
- Or reduce segment count per scene to 1 for hard historical roles
- Or relax the strict 2-segment requirement for 4-scene jobs

## Verdict

**E2E verification FAILED** at fetch_images stage. Asset resolution was incomplete (3/8 segments). The pipeline correctly detected the failure and set ASSET_UNRESOLVED status (non-zero exit). The prepare gate was not reached.
