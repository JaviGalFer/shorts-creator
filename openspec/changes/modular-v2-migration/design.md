# Design: modular-v2-migration

## Boundaries

`contracts/` is pure shared schema and validation logic. Domains depend on
contracts and technical interfaces; `infrastructure/` implements technical
concerns only. `pipeline/` coordinates domains. `bin/` must not receive new
domain logic after its corresponding domain migrates.

## Compatibility

During migration, a single `bin/_package_bootstrap.py` makes `<repo>/src`
importable for direct script execution. Each migrated legacy module becomes a
thin facade that reexports the canonical package API; it contains no duplicate
business logic.

## Slice 1

`src/shorts_creator/contracts/visual.py` owns every VisualPlan V2 constant and
validator/canonicalizer. `bin/visual_plan_v2.py` reexports its legacy API for
`generate_script.py`, `fetch_images_v2.py`, existing tests, and monkeypatch
targets. The risk is compatibility with legacy module-level monkeypatching, so
the facade preserves function object identity.
