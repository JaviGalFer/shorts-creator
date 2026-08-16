# Tasks: modular-v2-migration

## Slice 1 — VisualPlan V2 contract
- [x] Move canonical VisualPlan V2 implementation to `contracts/visual.py`.
- [x] Add centralized `bin/` package bootstrap and a legacy reexport facade.
- [x] Verify canonical and legacy imports expose identical public objects.
- [x] Run VisualPlan V2 consumer tests and CLI smoke (`445 passed`).
- [x] Run full suite and scope checks (`1188 passed`); commit the validated slice.

## Slice 2 — Duration contract
- [x] Move pure duration profiles and resolution logic to `contracts/duration.py`.
- [x] Keep `add_duration_profile_args` as the sole CLI adaptation in `bin/`.
- [x] Verify canonical and legacy imports share the same duration objects.
- [x] Run duration tests (`38 passed`), CLI smokes, full suite (`1190 passed`), and scope checks; commit.

## Slice 3 — Metadata infrastructure
- [x] Move `run_job` JSON metadata persistence to `infrastructure/metadata_store.py`.
- [x] Preserve `run_job` module aliases for legacy monkeypatch targets.
- [x] Verify round-trip, JSON formatting, and canonical store use.
- [x] Run affected runner tests (`114 passed`), CLI smoke, full suite (`1193 passed`), scope checks, and commit.
- [x] Defer `contracts/job.py`, `contracts/states.py`, and `contracts/results.py` until script/pipeline consumers make their boundaries concrete; do not create speculative contracts.
- [x] Document `clone_job.py` and `generate_script.py` JSON persistence as future candidates without migrating them in this slice.

## Slice 4 — Metadata store adoption
- [x] Adopt the shared metadata store in equivalent `clone_job.py` persistence.
- [x] Adopt the shared metadata store in equivalent `generate_script.py` output persistence.
- [x] Retain local JSON operations unrelated to metadata persistence.
- [x] Run direct consumer tests and metadata-store tests (`170 passed`), CLI smokes, full suite (`1193 passed`), scope checks, and commit.

## Script domain
- [x] Move prompts, LLM integration, V2 validation, retry/compression, candidate ranking, metadata construction, and generation flow to `script/generator.py`.
- [x] Replace `bin/generate_script.py` with a thin argparse adapter calling explicit domain parameters.
- [x] Migrate internal-helper imports and monkeypatches to the canonical domain module.
- [x] Verify architectural ownership, direct consumers (`318 passed`), CLI smokes, and full suite (`1196 passed`).

## Migration milestones
1. [x] Contracts foundation — VisualPlan V2 and duration contracts canonical under `contracts/`.
2. [x] Metadata infrastructure — shared store extracted and adopted by equivalent consumers.
3. [x] Script domain — generation ownership moved to `script/`; `bin/` is a CLI adapter.
4. [x] Audio.
5. [x] Assets.
6. [x] Rendering + validation.
7. [x] Pipeline + `bin/` adapter reduction.
8. [ ] Stabilization and final review.

Additional infrastructure is extracted only when required by a migrating domain, not as an independent campaign. Job/state/result contracts remain deferred until concrete consumers establish their boundaries.

## Audio domain
- [x] Move per-scene and continuous generation, timing, duration probing, metadata updates, and audio-stage status decisions to `audio/generator.py`.
- [x] Replace `bin/generate_audio.py` with an argparse/async adapter using explicit domain parameters.
- [x] Move the required TTS provider implementation into `audio/tts_provider.py`; retain only a compatibility facade for its benchmark consumer.
- [x] Migrate internal helper imports and monkeypatches to the canonical audio modules.
- [x] Verify audio consumers (`209 passed`), CLI smokes, and full suite (`1199 passed`).
- [x] Preserve the existing `AUDIO_DURATION_MISSING`, `duration_estimated`, probing fallback, status, and exit-code behavior unchanged.

## Assets domain
- [x] Move fetch runtime, router, executor, bridge, renderability, provider config, Wikimedia, and Pixabay implementations under `assets/`.
- [x] Replace `bin/fetch_images_v2.py` with an argparse adapter calling `fetch_assets(...)`.
- [x] Remove all seven non-entrypoint Visual Assets V2 implementations from `bin/` without legacy facades.
- [x] Migrate internal imports, monkeypatches, source-isolation checks, and the `asset_validation` renderability consumer to canonical modules.
- [x] Preserve deliberate atomic metadata writes (`.tmp` + `os.replace`) inside Assets rather than replacing them with the non-atomic shared store.
- [x] Verify asset consumers (`517 passed`), CLI smokes, and full suite (`1203 passed`).

## Rendering + validation domains
- [x] Move prepare/timeline/subtitle runtime to `rendering/preparer.py` and FFmpeg/render runtime to `rendering/renderer.py`.
- [x] Replace `prepare_job.py` and `render_job.py` with explicit CLI adapters.
- [x] Move job, asset, audio, coverage, pacing, subtitle, and visual validation implementations under `validation/`.
- [x] Replace `validate_job.py` with an explicit CLI adapter and remove all migrated validation auxiliaries from `bin/` without facades.
- [x] Move Whisper subtitle alignment to `audio/whisper.py` and remove the remaining Audio dependency on `bin/`.
- [x] Verify no package source imports migrated `bin/` runtimes, focal consumers (`486 passed`), CLI smokes, and full suite (`1210 passed`).
- [x] Preserve `AUDIO_DURATION_MISSING`, rendering commands, metadata, gates, statuses, and exit-code behavior unchanged.

## Pipeline + bin adapter reduction
- [x] Move stage ordering, subprocess dispatch, contracts, status transitions, failure handling, V2 rejection, and orchestration history to `pipeline/orchestrator.py`.
- [x] Replace `bin/run_job.py` with an explicit CLI adapter while preserving process isolation, 600-second timeout, output capture, return-code handling, and metadata reloads.
- [x] Consume duration and metadata persistence directly from canonical contracts/infrastructure.
- [x] Move narration trimming runtime to `audio/trimming.py` and replace its `bin/` script with a CLI adapter.
- [x] Migrate orchestration helpers, monkeypatches, and trimming ownership checks to package modules without private reexports.
- [x] Verify package sources do not import top-level `bin/` modules, focal consumers (`320 passed`), eight CLI smokes, and full suite (`1215 passed`).
- [x] Preserve `AUDIO_DURATION_MISSING`, stage order/contracts, V2-only defensive rejection, metadata, statuses, and exit-code behavior unchanged.
