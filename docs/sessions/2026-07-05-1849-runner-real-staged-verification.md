# Sesión: Real-run verification of Phase 23 unified job runner (through prepare)

- Fecha: 2026-07-05
- Objetivo: Verify `bin/run_job.py` orchestrates script → assets → audio → prepare stages correctly with real LLM, API fetches, and Edge TTS.
- Comando: `python3 bin/run_job.py --topic "La caída del Muro de Berlín" --duration 30 --duration-max 31 --stop-after prepare --verbose`
- Cambio OpenSpec: improve-historical-visual-pipeline (Phase 23)
- Resultado: **Blocked at assets stage** — `fetch_images.py` exit code 1 (scenes 1–4 unresolvable).

## Preconditions

- LLM_API_KEY: SET (OpenAI)
- PEXELS_API_KEY: SET
- PIXABAY_API_KEY: SET
- FREEAI_API_KEY: NOT IN .env (known limitation)
- Edge TTS: available
- Docker: available
- FFmpeg: not found (not needed for this run)
- OS: Linux

## Attempt 1: `--duration 28`

| Stage | Result | Detail |
|-------|--------|--------|
| script | REVIEW_REQUIRED | Script 54 words / 4 scenes → estimated 30.5s > max 30s. Duration contract FAIL. |

Script out of range by 0.5 seconds (maxWords=53, actual=54). Two retries failed to reduce below 54 words. Runner correctly blocked at REVIEW_REQUIRED.

## Attempt 2: `--duration 30 --duration-max 31`

| Stage | Result | Detail |
|-------|--------|--------|
| script | ✅ SCRIPT_DRAFT | 53 words / 5 scenes, estimated 30.3s within 27–31s window. 0 retries. Duration contract PASS. |
| assets | ❌ FAILED (exit 1) | `fetch_images.py` exit code 1. Scenes 1–4: "Some segments failed". Scene 5: ✅ selected via Wikimedia Commons (7.1 MB). |

## Job identity

- Job ID: `la-2026-07-05-185053`
- Job directory: `data/videos/la-2026-07-05-185053/`
- Final status: `FAILED` (failedStage: "assets")
- No paths point to previous jobs.

## Artifact inspection

### Script stage (PASS)
- `request.duration.requestedSec`: 30
- `durationContract.status`: PASS
- `durationContract`: targetSec=30, minSec=27, maxSec=31, wordCount=53, sceneCount=5, wordsPerScene=10/9/9/11/14
- Script has 5 scenes (valid, ≤ MAX_SCENES=6)
- No REVIEW_REQUIRED

### Asset stage (FAIL)
- `metadata.status` after fetch_images: `ASSETS_PARTIAL` (overwritten to `FAILED` by runner failure handler)
- Scenes 1–4: no image downloaded (`selected=false`, `error="Some segments failed"`)
- Scene 5: downloaded from `wikimedia_commons`, `selected=true`, file `scene-05-01.jpg` (7,170,839 bytes)
- Provider distribution: 0/5 Pexels, 0/5 Pixabay, 1/5 Wikimedia, 0/5 Pollinations
- No ASSET_UNRESOLVED status (the errors are "ASSETS_PARTIAL" level)
- **`editorialRole` IS populated** in every scene's `visualPlan` (e.g., scene 1: `context_map`, scene 5: `consequence_or_legacy`). The previous diagnosis was incorrect — the LLM prompt already includes `editorialRole` at line 199 of `generate_script.py`.
- **`visualTemporalIntent` is NOT populated** at the scene level (fetch_images.py computes it heuristically via `_classify_temporal_intent()`).
- **Actual failure mechanism**: Hard historical roles (`context_map`, `civilian_impact`, `battle_or_assault`) restrict provider chain to `["wikimedia_commons"]` only (`fetch_images.py:73-75`). Wikimedia Commons didn't match the generated queries for scenes 1–4.

### Audio stage — NOT REACHED (blocked by assets failure)

### Prepare stage — NOT REACHED (blocked by assets failure)

## Orchestration verification

```json
{
  "runnerVersion": "1",
  "currentStage": "assets",
  "statusHistory": [
    {"stage": "script", "status": "SCRIPT_DRAFT", ...},
    {"stage": "assets", "status": "ASSETS_FETCHING", ...},
    {"stage": "assets", "status": "FAILED", ...}
  ]
}
```

- ✅ runnerVersion: "1"
- ✅ currentStage: "assets" (not a later stage)
- ✅ No false completions
- ✅ FAILED entry includes error, failedStage, childCommand, exitCode
- ❌ No later stages present

## Cross-job path verification

All asset paths resolve inside `data/videos/la-2026-07-05-185053/`. No references to previous jobs.

## Failure analysis (corrected)

The assets stage failure is a **content/asset-resolution issue**:
- **Actual root cause**: `editorialRole` IS correctly populated by the LLM (present in prompt schema and output). The failure is that scenes 1–4 have hard historical roles (`context_map`, `civilian_impact`, `battle_or_assault`) which restrict the provider chain to **only** `["wikimedia_commons"]` (`fetch_images.py:73-75`). Wikimedia Commons did not find matching CC-licensed assets for the generated queries. Scene 5's soft role (`consequence_or_legacy`) used the full provider chain and succeeded.
- **Prompt gap**: `visualTemporalIntent` was missing from the LLM schema (now added). Query guidance for Wikimedia Commons was too generic (now improved with specific named entity + year requirements).
- Not a runner orchestration bug.
- Not an environment/provider configuration issue (API keys are set; scene 5 succeeded).
- Not a child-stage contract bug (fetch_images.py correctly returned exit 1 for partial success).

## Runner behavior assessment

| Aspect | Verdict |
|--------|---------|
| Script stage orchestration | ✅ Correct — called generate_script.py, parsed JSON output, extracted jobId/path, set status, appended orchestration |
| Script stage REVIEW_REQUIRED | ✅ Correct — detected status, appended orchestration, stopped, returned 0 |
| Assets stage execution | ✅ Correct — called fetch_images.py with correct metadata_path |
| Assets stage non-zero exit | ✅ Correct — detected exit code 1, set FAILED metadata, appended FAILED orchestration, stopped, returned 1 |
| Assets → audio gate | ✅ Correct — did NOT proceed to audio after assets failure |
| Contract verification | N/A — exit code was non-zero, contract verification is for exit-0-with-wrong-output scenarios |
| Error metadata | ✅ Correct — failedStage="assets", exitCode=1, childCommand captured, no secrets |
| Orchestration history | ✅ Truthful — 3 entries: SCRIPT_DRAFT, ASSETS_FETCHING, FAILED |

## Files changed

None. This is a read-only verification run. No code was modified.

## Remaining unverified stages

- **Audio** — `generate_audio.py` via runner (unit tested but not real-run)
- **Prepare** — `prepare_job.py` via runner (unit tested but not real-run)
- **Render** — `render_job.py` via runner (unit tested but not real-run)
- **Validate** — `validate_job.py` via runner (unit tested but not real-run)

## Prompt fix applied (2026-07-05)

Changed `bin/generate_script.py`:
1. Added `visualTemporalIntent` field (`event_depiction|legacy_or_commemoration|context_or_setup`) to scene-level JSON schema
2. Added `visualTemporalIntent` rules section with classification guidance based on editorialRole and voiceover
3. Added Wikimedia Commons query guidance: each searchQuery must include named entity + year, minimum 2 queries per scene, avoid generic queries

## Next recommended verification command

Re-run to test whether improved queries help Wikimedia Commons find assets for hard historical roles:

```bash
python3 bin/run_job.py \
  --topic "La caída del Muro de Berlín" \
  --duration 30 \
  --duration-max 31 \
  --stop-after prepare \
  --verbose
```
