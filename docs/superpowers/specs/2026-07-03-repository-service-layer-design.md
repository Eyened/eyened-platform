# Repository/Service Layer Design (RBAC Step 1)

## Context

This is the first of two planned projects. The eventual goal is to add
role-based access control (RBAC) to the eyened-platform backend, scoped to
Projects and Tasks (see brainstorming discussion for full RBAC requirements —
that design is deferred to a follow-up spec, "Step 2").

RBAC needs a natural place to put per-request authorization checks. Today,
`server/routes/*.py` handlers query the ORM directly in the route function
body (e.g. `db.get(Patient, patient_id, options=...)` inline in
`patients.py`), so there is no single place to add access checks without
duplicating them across ~50 endpoints.

This project (Step 1) introduces a Repository + Service layering so that
Step 2 has a natural home for authorization logic, without bundling RBAC
itself into this change.

## Goals

- Give every route module a Service to call instead of querying the ORM
  directly, so Step 2 can add authz checks in one place per entity.
- Extract the ad hoc, endpoint-specific queries currently embedded in route
  handlers (joins, `selectinload` chains, filters) into named, testable
  Repository methods.
- Keep `orm/eyened_orm` usable exactly as it is today by non-web consumers
  (RQ worker, CLI commands in `orm/eyened_orm/commands/`, data-scientist
  scripts/notebooks) — this project does not touch that code path.

## Non-goals

- RBAC itself (roles, permissions, membership tables, enforcement) — Step 2,
  separate spec.
- Migrating CLI/worker code (`orm/eyened_orm/commands/`) to use the new
  Repositories. Explicitly desired for the future, but out of scope here.
- Converting `search.py` (1257 lines, a large cross-cutting/ad hoc query
  surface), `auth.py` (831 lines, token/session logic, not model-CRUD
  shaped), or `import_api.py` (341 lines, import-pipeline and RQ job
  orchestration built on the `eyened_orm.importer` subsystem, not
  model-CRUD shaped) to this pattern.
- Deprecating or removing `Base`'s existing generic query classmethods
  (`where`, `by_columns`, `get_or_create`, `by_name`, `select`) — they stay
  as-is and may still be used, including internally by new Repositories.
- Any frontend (SvelteKit client) changes — API response shapes (DTOs) do
  not change.

## Architecture

```
server/routes/<module>.py  →  server/services/<model>_service.py  →  orm/eyened_orm/repositories/<model>_repository.py  →  DB
```

**Repository** (`orm/eyened_orm/repositories/`, one per ORM model)
- Pure data access. Named, intention-revealing query methods (e.g.
  `PatientRepository.get_with_attributes(session, patient_id)`) that replace
  the inline query-building currently written in route handlers.
- May use `Base`'s existing generic helpers (`by_columns`, `where`, `select`)
  internally where that's simplest, or raw SQLAlchemy `select()` for
  anything more specific to that call site. Repositories exist for the
  complex, endpoint-shaped queries — not to reimplement basic CRUD that
  `Base` already provides.
- Takes a `Session` as a method argument; does not own or create sessions.
- Framework-agnostic: no FastAPI imports, no knowledge of HTTP. This is what
  makes future reuse from CLI/worker code possible.
- Returns `None` (or an empty list) for "not found" — never raises
  HTTP-shaped errors.

**Service** (`server/services/`, one per ORM model)
- Holds business logic/orchestration, calls one or more Repositories.
- Lives only in `server/` since it's web-app-specific. This is where a
  future RBAC authz check will be added per method in Step 2.
- Takes its Repository via constructor injection (e.g.
  `PatientService(repository: PatientRepository)`), not module-level
  instantiation or an internal import. A FastAPI `Depends()`-based factory
  wires the default `Repository` instance at the route layer; tests
  construct a `Service` directly with whatever `Repository`/session they
  need. This is what makes the Testing section below possible.
- Translates a Repository's `None`/empty result and other business-rule
  violations (including future Step 2 authz denials) into the domain
  exceptions defined in `server/services/exceptions.py` — never raises
  `HTTPException` directly (see Error Handling).
- Deals in ORM/domain objects, not API response shapes.

**Route handlers**
- Become thin: parse/validate request → call Service method → convert
  result via the existing `DTOConverter` → return.
- DTO conversion stays at the route boundary, as it is today — not inside
  the Service.
- A route module touching multiple models (e.g. `task.py` uses `Task`,
  `SubTask`, `TaskDefinition`) calls multiple Services directly — no
  additional facade layer.

**CLI/worker** (`orm/eyened_orm/commands/`)
- Untouched by this project. Keeps using today's classmethods
  (`Patient.by_columns`, `ImageInstance.where`, etc.). Adopting Repositories
  there is explicit future work — Services are not part of that future
  reuse, since CLI/worker operations are trusted/unrestricted batch jobs
  with no per-request "current user," and Services are the layer that will
  carry per-user authz in Step 2.

## Directory Structure & Naming

```
orm/eyened_orm/
  repositories/
    __init__.py
    patient_repository.py       # PatientRepository
    project_repository.py       # ProjectRepository
    task_repository.py          # TaskRepository, SubTaskRepository, TaskDefinitionRepository
    ...

server/
  services/
    __init__.py
    exceptions.py                # ServiceError, NotFoundError, ...
    patient_service.py          # PatientService
    project_service.py          # ProjectService
    task_service.py             # TaskService, SubTaskService
    ...
  routes/
    patients.py                  # unchanged filename, now calls PatientService
    ...
```

- One file per model, snake_case filenames (`<model>_repository.py`,
  `<model>_service.py`), matching the existing one-model-per-file convention
  in `orm/eyened_orm/*.py` (`patient.py`, `project.py`, `task.py`, ...).
- Class names: `<Model>Repository` / `<Model>Service` (e.g.
  `PatientRepository`, `PatientService`).
- Method names describe intent, not generic CRUD verbs only:
  `get_by_id`, `get_with_attributes`, `list_visible_to_project`, `create`,
  `update`, `delete`, etc. — each documents what query/rule it encodes.
- `repositories/__init__.py` and `services/__init__.py` re-export their
  module's public classes via `from .<model>_repository import *` /
  `from .<model>_service import *`, following the same convention already
  used in `orm/eyened_orm/__init__.py` (`from .patient import *`, etc.) —
  so `from eyened_orm.repositories import PatientRepository` and
  `from server.services import PatientService` work directly.

## Migration Order & Phasing

Each phase is its own PR: add the Repository + Service for that phase's
model(s), switch the corresponding route module to use them, ship.

| Phase | Modules | Why |
|---|---|---|
| 0 — Pilot | `devices.py` (18 lines) | Smallest, lowest risk; establishes the pattern/conventions as a template PR to review before scaling up |
| 1 | `form_schema.py` (25 lines), `patients.py` (34 lines) | Still small; `patients.py` is RBAC-relevant (Step 2), an early real-world validation of the pattern on a meaningful model |
| 2 | `studies.py`, `feature.py`, `tag.py` | Medium-sized, self-contained |
| 3 | `subtask.py`, `task.py` | RBAC-relevant (Step 2); larger, touch `Task`, `SubTask`, `TaskDefinition` |
| 4 | `instances.py`, `form_annotations.py`, `segmentations.py` | RBAC-relevant (Step 2: `FormAnnotation`, `Segmentation`); largest, most complex query logic to extract |
| Out of scope | `search.py`, `auth.py`, `import_api.py` | See Non-goals |

## Error Handling

- Repositories: return `None`/empty list on "not found," never raise.
- `server/services/exceptions.py` defines a small domain exception
  hierarchy: `ServiceError` (base), `NotFoundError` for this project. Step 2
  will add `PermissionDeniedError` to the same hierarchy for authz denials.
- Services translate a Repository's `None`/empty result into `NotFoundError`,
  and raise the appropriate domain exception for any other business-rule
  violation — never raise `HTTPException` directly.
- `server/main.py` registers one FastAPI exception handler per domain
  exception (`@app.exception_handler(NotFoundError)`, etc.), mapping each to
  the `HTTPException` status/detail routes raise today (e.g. `NotFoundError`
  → 404). This is a single, central place to add the Step 2
  `PermissionDeniedError` → 403 mapping, instead of repeating
  `raise HTTPException(403, ...)` in every authz-checking Service method.
- Routes: no longer contain `if not X: raise HTTPException(...)` — that
  check moves into the Service method, and routes don't catch the domain
  exceptions either (the central handlers do).

## Testing

- **Repositories**: tests in `orm/eyened_orm/tests/` using the existing
  function-scoped, in-memory SQLite `session` fixture
  (`orm/eyened_orm/utils/sqlite_testdb.py`, already re-exported by
  `orm/eyened_orm/tests/conftest.py`) — verify the actual query returns the
  right rows, joins, and filtering against a real (in-memory) database. No
  mocking library is used anywhere in this codebase; this project doesn't
  introduce one.
- **Services**: tests in `server/tests/`, constructed with a real
  `Repository` backed by the same in-memory SQLite `session` fixture (via
  constructor injection — see Architecture) — verify business logic and
  error translation (e.g. `pytest.raises(NotFoundError)`) against real data,
  matching the existing style in `orm/eyened_orm/tests/test_feature_from_list.py`.
  If a specific Repository-level edge case needs to be forced without
  touching the DB, use a small hand-rolled fake object passed to the
  Service's constructor (matching the existing `FakeClient`/`FakeResponse`
  pattern in `server/tests/test_config.py`), not a mocking library.
- **Routes**: existing route-level tests continue to exercise the full
  stack end-to-end as a thinner smoke-test layer, not the primary place new
  logic is tested.

## Follow-up work (not this spec)

- Step 2: RBAC design (Project/Task membership, roles, superadmin,
  enforcement via Service-layer authz checks) — separate brainstorm.
- Migrate CLI/worker code in `orm/eyened_orm/commands/` to use Repositories.
- Decide whether/how to convert `search.py` and `auth.py`.
- **Transaction ownership — revisit across all Services once the layer
  refactoring is done.** The mutating Services carried over today's
  route behavior of calling `session.commit()` (and `session.refresh()`)
  directly inside each method. This couples the Service to the transaction
  lifecycle, has no explicit rollback on error, and runs audit logging
  *after* commit (so a logging failure can't undo a persisted write). It
  matches the pre-refactor behavior, so it is not a regression, but the
  boundary should be decided deliberately for the layer as a whole rather
  than per-method. Once all phases have migrated, review every Service and
  pick one consistent model — e.g. move the commit boundary into the
  `get_db` dependency / a unit-of-work context manager (Services `flush`,
  the caller commits once), so rollback-on-error and audit-inside-the-
  transaction come for free. Check for double-commit before changing
  (`grep -rn "\.commit()" server/services server/routes server/db.py`).
