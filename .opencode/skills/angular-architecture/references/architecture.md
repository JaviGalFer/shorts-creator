# shorts-creator Angular Architecture

## Goal

The Angular frontend is a maintainable client for the existing FastAPI domain API.

It must remain replaceable and independently testable. It must not duplicate the Python pipeline.

## Target structure

web/frontend/src/app/
├── app.ts
├── app.config.ts
├── app.routes.ts
└── features/
    └── generator/
        ├── generator.routes.ts
        ├── generator-page/
        ├── generator-form/
        ├── job-progress/
        ├── job-result/
        ├── application/
        │   └── generator.facade.ts
        ├── data-access/
        │   ├── shorts-api.client.ts
        │   ├── shorts-api.dto.ts
        │   ├── shorts-api.mapper.ts
        │   └── api-error.mapper.ts
        └── model/
            ├── job.model.ts
            ├── capabilities.model.ts
            └── generation-command.model.ts

Do not create empty global `core/` or `shared/` directories.

## Dependency direction

UI components
    ↓
GeneratorFacade
    ↓
ShortsApiClient
    ↓
FastAPI

Transport DTO
    ↓
mapper
    ↓
frontend model

Dependencies must not point upward.

## App shell

The root App is shell-only.

Allowed responsibilities:
- router outlet;
- global page shell/layout if needed.

Forbidden:
- generation form state;
- job polling;
- backend orchestration;
- pipeline state interpretation.

## GeneratorPage

Composition root for the feature.

Responsibilities:
- provide/inject GeneratorFacade;
- compose generator form, job progress and job result;
- connect presentation events to facade commands.

Do not put HTTP code here.

## GeneratorForm

Presentation/form component.

Responsibilities:
- reactive form;
- display backend-provided capabilities;
- frontend validation;
- emit a generation command.

Forbidden:
- HttpClient;
- polling;
- knowledge of job filesystem;
- duplicated backend provider/preset lists.

## JobProgress

Presentation component.

Responsibilities:
- display execution state;
- display pipeline stages;
- display sanitized warnings/review reasons.

Forbidden:
- timers;
- HttpClient;
- subscriptions that drive application workflows.

## JobResult

Presentation component.

Responsibilities:
- domain outcome;
- safe video preview URL;
- safe download URL.

It uses only:

`/api/v1/jobs/{uuid}/video`
`/api/v1/jobs/{uuid}/download`

No filesystem paths.

## GeneratorFacade

Feature application layer.

Prefer feature-scoped lifetime.

Owns state such as:

- capabilities
- currentJob
- creatingJob
- polling
- error

Expose readonly signals/computed state.

Own commands such as:

- initialize()
- generate(command)
- refreshJob()
- beginPolling()
- stopPolling()

Polling:

`timer(0, 1000)`
→ `exhaustMap(() => api.getJob(id))`
→ continue while QUEUED/RUNNING
→ include final terminal result
→ stop on FINISHED/FAILED/INTERRUPTED
→ lifecycle cleanup with `takeUntilDestroyed`

Never use `setInterval`.

## Data access

`ShortsApiClient` is stateless transport infrastructure.

Responsibilities:
- URLs;
- HttpClient;
- request DTOs;
- response DTOs;
- HTTP error conversion boundary.

It does not own UI state.

## DTO boundary

Keep FastAPI transport models separate from frontend application models where useful.

Example:

`JobResponseDto.execution_state`
→ mapper
→ `Job.executionState`

Templates should not become coupled to Pydantic serialization conventions.

## State management

Default:
- Angular signals for feature state;
- computed values for derived presentation state;
- RxJS for HTTP/process streams.

Do not add NgRx for this MVP.

Reassess only when there is meaningful cross-feature state, complex event coordination or state history that cannot be cleanly handled feature-locally.

## Dependency injection

Prefer `inject()`.

Feature-specific application services should be feature-scoped rather than accidental root singletons when their lifetime belongs to a route/page.

## Change detection

Prefer `ChangeDetectionStrategy.OnPush` for presentation components where applicable.

## API authority

`GET /api/v1/capabilities` is authoritative for selectable runtime capabilities.

Do not hardcode:
- visual modes;
- provider availability;
- duration presets;
- provider capabilities;
- voice catalogs that do not exist.

## Testing

Co-locate specs with implementation.

Minimum architectural tests/coverage:
- API DTO mapping;
- facade generation lifecycle;
- polling non-overlap;
- polling terminal stop;
- lifecycle cleanup;
- form command mapping;
- REVIEW_REQUIRED rendering;
- ASSETS_PARTIAL rendering;
- safe video/download resource URLs;
- error mapping.

No real LLM/provider calls in Angular tests.
