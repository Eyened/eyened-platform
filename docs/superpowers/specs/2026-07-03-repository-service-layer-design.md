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

### Deferred review findings (running list from the phased migration)

Minor findings surfaced by the per-phase code reviews that were consciously
deferred rather than fixed in-phase — none are correctness bugs. Appended per
phase so they can be swept up together; several belong to the transaction-
ownership review above. Listed earliest phase first.

**Cross-phase (recur across every slice):**
- Promote the per-handler `ActingUser(id=current_user.id, username=current_user.username)`
  construction (built in the mutating handlers of every route slice) into a
  single `get_acting_user` FastAPI dependency. First noted in Phase 2a; recurs
  through 4b.
- No route-level HTTP `TestClient` tests exist for any migrated slice — wiring
  is verified statically and via Service unit tests. Add a thin route-level
  smoke layer asserting the 404 body, the structured 409 bodies (feature delete
  guards), and 422 on a bad enum (`task`/`subtask` `task_state`).
- `routes/task.py` (and any slice reusing it) calls pydantic-v1
  `.copy(update=...)`; sweep to the v2 API to silence deprecation warnings —
  pre-existing, not introduced by the migration.
- Audit change-strings that now stringify enums on both sides (e.g.
  `"SubTaskState.NotStarted -> SubTaskState.Ready"` vs. the old
  `"... -> Ready"`) — cosmetic; use `.value` if a stable audit text is wanted.
  Same class as the Phase 4b decision-#3 item; fold into the audit cleanup.

**Phase 2a (`studies`):**
- Extract a shared `_require_study_and_study_tag(...)` validation helper once a
  3rd copy of the study/tag existence + type-check block appears (Rule of Three:
  2 copies today).
- Add a direct `StudyRepository.get_by_id`/`get_tag` repository test (currently
  covered only transitively via the Service tests) — low priority.
- No test for the existing-link + `comment=None` no-op branch; `patch_study_tag`
  has no dedicated unknown-study/tag 404 test (its paths are identical to
  `tag_study`'s, which are tested).

**Phase 2b (`features`):**
- `FeatureRepository.count_segmentations` / `segmentation_counts` positive
  (non-zero) path is tested nowhere against real `Segmentation` rows — only the
  empty branch and a fake-injected blocking-delete guard. Add a positive-path
  count test once a `Segmentation` test factory exists (needs the
  `ImageInstance → Series + Creator` + enum-FK graph). Regression risk only if
  these two queries are later refactored.
- Add a one-line comment documenting `_SegBlockingRepo`'s guard-order dependency
  (test helper).
- `dto_converter.py` (out of this project's scope, flagged in passing): a
  `ChildLinks` `getattr` fallback is structurally dead (the attribute never
  existed) — delete it and its misleading comment; `feature_to_get` double-sorts
  `FeatureAssociations` (CPU-only, cached collection).

**Phase 2c (`tag`):**
- Add an unstar-on-unknown-tag test (behaviorally identical to the existing
  no-op test; left out per lean-test-granularity).

**Phase 3a (`task`):**
- `TaskRepository.subtask_counts(session, [])` == `{}` empty-input case (part of
  the Interfaces contract) is untested — a one-line assert closes it.
- `count_for_task`'s zero-row/zero-match case is asserted only by reading the
  code (0-not-`None`), not by a test.
- Ordering tests for `list_all` (`order_by(Task.TaskID)`) and `all_ids_for_task`
  (`order_by(SubTaskID)`) pass trivially — SQLite insertion order coincides with
  id order, so they don't independently prove the `ORDER BY`. Strengthen with
  out-of-order inserts.
- `delete_task`'s deleted-data snapshot has a dead `else None` branch
  (`str(TaskState) if TaskState else None`; the enum is always truthy) —
  cosmetic cleanup.
- `create_task` audit fields omit `task_state`/`creator_id` (plan-mandated) —
  revisit only if a richer insert-audit is wanted; loses no real info today
  (`creator_id == actor.id` is logged as `user_id`; `task_state` is
  deterministically `NotStarted`).
- Perf (forward note only): `list_task_subtasks` issues 4 sequential queries and
  `all_ids_for_task` scans the full unfiltered set per page — brief-mandated;
  revisit if per-task subtask counts grow large.

**Phase 3b (`subtask`):**
- Re-linking the same image to the same subtask hits `SubTaskImageLink`'s
  composite PK → `IntegrityError` → HTTP 500 (behavior-preserving vs. the old
  route's caught 500). A proper 409 contract is deferred to the
  transaction-ownership review above.
- `add_image` / `remove_image` are annotated `-> SubTask` but can return
  `SubTask | None` (runtime-safe via pre-checks/FK; a mypy/pyright nit).
- `update_subtask`'s `session.refresh` is redundant under
  `expire_on_commit=True`; dropping it unifies the 3 mutators.

**Phase 4a (`instances`):**
- `ImageInstanceService.tag`/`patch`/`untag` inline the instance-resolve +
  None-check that duplicates `get_for_storage` — left self-contained
  deliberately (same duplication class as the Phase 4b `tag`/`patch_tag` guard
  block).

**Phase 4b (`form_annotations`):**
- `FormAnnotationService.update` reproduces a pre-refactor audit-log quirk
  verbatim: its `changes` dict does `getattr(annotation, <snake_case_key>, None)`
  on a PascalCase ORM object, so every logged change reads `None -> <new>`
  (audit-log-only, not an API response; now unpinned by any test). Correct
  source would be `_FIELD_MAP[key]` (and handling `image_id`). Fold into the
  transaction-ownership / audit-logging review above.
- `FormAnnotationService.tag` and `.patch_tag` duplicate an identical ~8-line
  annotation + tag + wrong-type guard block; extract a private
  `_load_annotation_and_typed_tag(...)` helper (Rule-of-Three: 2 copies today).
- `server/services/__init__.py` `__all__` reordered `FeatureService` while
  adding the new export (inert; drop to keep the diff minimal).
- Redundant explicit `return None` in `soft_delete` / `set_value` / `untag`
  (the methods are `-> None`).
- `get_annotation`'s happy path (returns the row with tag links loaded) has no
  direct Service-level test — only its 404 path; add a 2-line "returns the row"
  test when Phase 4c next touches this file. (The repo-level `get_with_tag_links`
  found/empty case IS tested.)
- Pre-existing `ImageInstance.DatasetIdentifier is deprecated` DeprecationWarning
  surfaces via the `_make_image` test helper (suite-wide, ~159 at baseline; not
  introduced by this phase).

**Phase 4c (`segmentations`):**
- **Zarr concurrency (follow-up, not a migration bug).** The known concurrent
  read/write failures are unchanged by this phase. The new `SegmentationDataStore`
  port is the intended seam for the fix — e.g. a `LockingSegmentationDataStore`
  decorator, or a backend with real concurrent-write support — swapped in
  `get_segmentation_data_store()` with no Service/route/test edits. Note two
  limits: `get_zarr_storage_manager()`/`get_data_access_adapter()` are
  process-global `@lru_cache` singletons, so an in-process lock won't cover the
  RQ-worker path; and the server path (this port) and the client path
  (`DataAccessAdapter`) are two seams to the same store — unifying them so the
  fix lives once is the real long-term win.
- `POST /segmentations/{id}/tags` ignores the client-supplied `ObjectTagPOST.comment`
  (no `Comment` persisted), unlike the instance/form-annotation taggers which do
  store it. Preserved verbatim from the pre-refactor handler; revisit for
  consistency (would change the `TagMeta.comment` in the response, hence deferred).
- `SegmentationService.patch` reproduces the pre-refactor audit double-apply
  quirk: `reference_segmentation_id`/`feature_id` are assigned before the
  change-string is built, so they log `<new> -> <new>` while `threshold` logs the
  correct `<old> -> <new>`. Audit-log-only; fold into the audit-logging cleanup.
- `PUT /segmentations/{id}/data` and `PUT /model-segmentations/{id}/data` return
  the raw ORM row (no `response_model`); fragile but behavior-preserving.
- `GET /segmentations/{id}` eager-loads tag links (`get_with_tag_links`) that the
  DTO then discards (`segmentation_to_get` called without `with_tag_metadata`).
  Faithful to the extracted query; drop the eager-load or pass the flag once the
  intended behavior is confirmed.
- Zarr binary I/O runs inside `async def` handlers (blocking-in-async); pre-existing,
  out of scope for a behavior-preserving migration.
- `ModelSegmentation` write happy-path and repository `get_by_id` positive path are
  unit-tested only via the 404 branches (a `SegmentationModel` test factory does
  not exist yet); add once one does, alongside the Phase 2b positive-count test.
