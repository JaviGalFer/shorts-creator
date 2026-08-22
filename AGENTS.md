# shorts-creator

Python backend and media pipeline for Shorts Creator. The Angular frontend lives in the separate `shorts-creator-web` repository and integrates only through HTTP.

## Architecture

- V2-only pipeline.
- `run_pipeline()` is the canonical reusable pipeline boundary.
- `bin/run_job.py` is a thin CLI adapter, not the Web API boundary.
- `src/shorts_creator/web/` contains the FastAPI backend only.
- Preserve existing module boundaries under `src/shorts_creator/`.
- Do not introduce new architectural layers unless explicitly required.

## API invariants

- Frontends never send or receive local filesystem paths.
- Web job resources use opaque job IDs.
- Video preview/download remain job-scoped HTTP resources.
- Never expose raw metadata, subprocess commands, stdout/stderr, secrets, or internal paths.
- Do not change existing API or pipeline contracts outside task scope.

## Token-efficient workflow

- Inspect only files directly relevant to the requested change and their direct dependencies.
- Do not scan the repository globally unless explicitly required.
- Do not inspect `data/`, `logs/`, generated media, job artifacts, or historical sessions unless directly required.
- Do not load OpenSpec, project docs, skills, MCP, or historical context by default.
- Load only the specific additional document needed when the task explicitly requires it.
- Do not launch subagents by default.
- Do not perform separate Plan, Review, or Closure phases unless explicitly requested or justified by concrete risk/findings.
- Do not refactor unrelated code.
- Prefer focused tests during implementation.
- Run the full suite at most once at the end when the change warrants it.
- Keep shell/test output concise.

## Git

- `main` is stable; implementation uses dedicated branches.
- Do not create, switch, merge, commit, or push unless explicitly authorized.

## Verification

Git, pytest, linters, type checkers, and runtime tooling are authoritative over assumptions.
