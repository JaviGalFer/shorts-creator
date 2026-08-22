"""Web backend / Job API for short-form video jobs.

Exposes the canonical ``run_pipeline`` runner through a small FastAPI
job API. The HTTP layer exposes only domain resources (jobs), never
filesystem paths. See ``openspec/changes/web-ui-mvp/``.
"""