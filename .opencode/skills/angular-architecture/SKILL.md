---
name: angular-architecture
description: Apply the shorts-creator modern Angular architecture when planning, implementing or reviewing web/frontend. Enforces standalone Angular, feature-first boundaries, application/data-access/presentation separation, signal-based feature state, RxJS lifecycle-safe async flows, typed HTTP adapters and maintainable tests.
compatibility: opencode
metadata:
  scope: shorts-creator
  framework: angular
---

# Angular Architecture Skill

Use this skill for every task that creates, modifies, restructures or reviews code under `web/frontend/`.

Before making architectural changes, read:

`references/architecture.md`

## Mandatory principles

1. Use modern standalone Angular only.
   - `bootstrapApplication`
   - `app.config`
   - standalone components/routes
   - NO new `NgModule`
   - NO `AppModule`

2. Organize primarily by feature.
   Do not create global folders such as `components/`, `services/`, `models/` or `utils/`.

3. Components are presentation boundaries.
   They must not own backend orchestration, polling loops or unrelated application workflows.

4. Feature orchestration belongs in an application-level facade/store.

5. HTTP belongs behind a typed data-access adapter/client.

6. Transport DTOs do not become application models automatically.
   Map external API DTOs into frontend application/domain models when their shape or naming leaks transport concerns.

7. Use Angular signals for synchronous UI/application state:
   - `signal`
   - `computed`
   - readonly exposed state

8. Use RxJS for asynchronous processes and event streams.

9. Never use manual `setInterval`/`setTimeout` polling when an RxJS lifecycle-safe pipeline is appropriate.

10. Polling must:
    - avoid overlapping HTTP requests;
    - stop on terminal domain state;
    - stop when the owning feature is destroyed;
    - prefer `timer` + `exhaustMap` + `takeUntilDestroyed`.

11. Prefer `inject()` for Angular dependency injection.

12. Prefer built-in Angular control flow (`@if`, `@for`, etc.) in new templates.

13. Do not introduce NgRx, Nx, a global event bus or another state library without demonstrated complexity requiring it.

14. Do not create empty `core`, `shared`, `common`, `utils` or abstraction folders for hypothetical future reuse.

15. `shared` means actually reused by multiple features. Create it only when reuse exists.

16. Keep the application shell thin.
    `App` must not become the coordinator for business/application workflows.

17. Backend capabilities are authoritative.
    Do not duplicate provider lists, duration presets, visual modes, voices or pipeline semantics in Angular.

18. Browser code never knows filesystem paths.
    Jobs are addressed only by the public HTTP resource contract and opaque job UUID.

19. API errors must be mapped to safe frontend error models.
    Never render raw exception objects.

20. Tests live next to the unit/feature being tested where practical.

## Quality gate

Before declaring an Angular task complete:

- inspect architecture boundaries;
- run frontend unit tests;
- run Angular production build;
- run relevant backend regression tests when API integration changed;
- run `git diff --check`.

Never claim completion if dependencies are not installed and the Angular build has not actually run.

## Stop conditions

Stop and report instead of improvising when:

- Angular dependencies cannot be installed;
- the installed Angular/Node versions are incompatible;
- the backend contract required by the UI does not exist;
- satisfying the requested change would require violating the architecture reference.
