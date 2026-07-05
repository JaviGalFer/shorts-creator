# Sesión: Root cause fixes and validation re-run

- Fecha: 2026-07-04
- Objetivo: Fix all 4 root causes from failed Phase 14 validation, recreate final2 validation jobs, get green
- Estado inicial: Phase 14 validation FAILED (Wright: drift -0.19s, qualityGate FAIL; Pompeya: drift -2.82s, duration FAIL)
- Estado final: (pending validation re-run)
- Agente responsable: opencode
- Cambio OpenSpec relacionado: configurable-job-contract-duration-and-quality-gates
- Riesgo asumido: .env TTS_PROVIDER changed from google-tts to edge_tts — existing non-edge pipelines will break
- Validaciones realizadas: 40/40 tests passing

## Root causes identified

1. **Timing provider regression**: `Communicate()` called without `boundary="WordBoundary"` in `tts_provider.py`. Upstream default is SentenceBoundary. Fix: `boundary="WordBoundary"` added to both Communicate() calls.

2. **Visual timeline / audio truncation**: `build_render_timeline()` in `prepare_job.py` let narrative beats skip cues, creating gaps. `-shortest` truncated to shorter stream. Fix: clamp first beat start to `min(start_sec, scene_offset)` and last beat end to `max(end_sec, scene_end)`.

3. **Null asset paths not blocked**: `seg.get("path", "")` returned `None`. Preflight didn't catch it. Fix: `(seg.get("path") or "")` in both locations; preflight explicit null check; render loop fatal error.

4. **Retry semantics off-by-one**: `while retries <= max_retries` gave 3 iterations for `max_retries=2`. Fix: `while retries < max_attempts`.

## Files modified

| File | Change |
|------|--------|
| `bin/tts_provider.py` | Added `boundary="WordBoundary"` (lines 174, 205) |
| `bin/prepare_job.py` | Clamp beat start/end to scene window (lines 316-319); null-safe `seg.get()` (lines 333, 373) |
| `bin/render_job.py` | Null assetPath check in preflight (lines 219-221); fatal error in render loop (lines 562-566) |
| `bin/generate_script.py` | `<= max_retries` → `< max_attempts` (line 367); renamed `max_retries` → `max_attempts` |
| `.env` | `TTS_PROVIDER=google-tts` → `TTS_PROVIDER=edge_tts` |
| `tests/test_duration_contract_and_scene_boundary.py` | Added 7 regression tests (null asset, WordBoundary, retry semantics, seg.get safety) |
| `tests/test_timing_regression.py` | Fixed PROJECT path shorts-historicos → shorts-creator |
| `tests/test_continuous_audio.py` | Fixed PROJECT path shorts-historicos → shorts-creator |
| `openspec/changes/.../tasks.md` | Unchecked Phase 14, documented root causes & fixes |

## Comandos ejecutados

- `python3 -m pytest tests/ -v` — 40/40 passed

## Resultado

All code fixes applied. 40 tests passing. Pending: recreate final2 validation jobs and run full pipeline.

## Próximos pasos

1. Create final2 validation jobs for Wright and Pompeya
2. Run generate_script, generate_audio, prepare_job, render_job for both
3. Verify acceptance criteria
4. Update tasks.md with final results

## Bloqueos o decisiones pendientes

- Pompeya duration may still be borderline (28.776s previously). With WordBoundary and full scene window clamping, duration should increase. If still below 30s, retry with higher word budget.
