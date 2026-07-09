# form_schema Repository/Service Migration (RBAC Step 1, Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route the two `form_schema` endpoints (`GET /form-schemas` list, `GET /form-schemas/{id}` get-by-id-with-404) through a `FormSchemaService`/`FormSchemaRepository`, reusing the foundation scaffolding, committing directly onto the current `feature/rbac-step1-service-layer` branch (which is not merged to `development` as part of this work, so `development` is never touched).

**Architecture:** Identical to the reviewed Device/Patient slices — thin route (parse → Service → `DTOConverter` → return), Service with constructor-injected Repository raising `NotFoundError`, framework-agnostic Repository taking a `Session`. No new exception types, handler, or fixtures: all exist from the foundation.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (ORM `eyened_orm`), pytest with the in-memory SQLite `session` fixture.

## Global Constraints

Copied verbatim from `docs/superpowers/specs/2026-07-03-repository-service-layer-design.md`. Every task implicitly includes these:

- **Filenames:** snake_case, one file per model — `form_schema_repository.py`, `form_schema_service.py`.
- **Class names:** `FormSchemaRepository` / `FormSchemaService`.
- **Repositories** live in `orm/eyened_orm/repositories/`, take a `Session` as a method argument (never own/create sessions), have no FastAPI imports, and return `None`/empty on "not found" — never raise HTTP-shaped errors.
- **Services** live in `server/services/`, receive their Repository via constructor injection, and raise the domain exceptions in `server/services/exceptions.py` — **never** raise `HTTPException` directly.
- **DTO conversion stays at the route boundary** (via `DTOConverter`), never inside a Service.
- **Package `__init__.py` files re-export** their public classes (with `__all__`), keeping all existing exports.
- **No mocking library.** DB-backed tests use the real in-memory SQLite `session` fixture (already exposed to `server/tests/` by the foundation's `server/tests/conftest.py`).
- **Do not touch:** CLI/worker code, `search.py`, `auth.py`, `Base`'s generic classmethods, or the foundation's `exceptions.py`/`main.py` (reused as-is).
- **Repository tests** → `orm/eyened_orm/tests/`; **Service tests** → `server/tests/`.

> **Interpreter note:** no `python`/`pytest` on `PATH`; the venv is at `dev/.venv`. Every command uses `dev/.venv/bin/python` / `dev/.venv/bin/pytest`.

> **Reused from the foundation (`feature/rbac-step1-service-layer`):** `NotFoundError` (`server/services/exceptions.py`), the central handler in `server/main.py`, the `session` fixture already imported in `server/tests/conftest.py`, and both `__init__.py` packages. `FormSchema` (`orm/eyened_orm/form_annotation.py:32`) needs only `SchemaName` (unique `str`) to construct — `FormSchemaID` autoincrements; `Schema`/`EntityType` are optional. `DTOConverter.form_schema_to_get` (`server/dtos/dto_converter.py:552`) and `FormSchemaGET` (`server/dtos/dtos_main.py`) already exist.

---

## Task 0 (git): Continue on the current feature branch — do NOT touch `development`

Not a code task. All new work stays on `feature/rbac-step1-service-layer` (its existing commits are already pushed to remote); it is not merged to `development` as part of this work, so `development` is never touched.

- [ ] **Step 1: Confirm the working branch**

```bash
git branch --show-current   # expect: feature/rbac-step1-service-layer
```

All Task 1–3 commits land directly on `feature/rbac-step1-service-layer`, alongside the foundation commits.

---

### Task 1: FormSchemaRepository

**Files:**
- Create: `orm/eyened_orm/repositories/form_schema_repository.py`
- Modify: `orm/eyened_orm/repositories/__init__.py` (add `FormSchemaRepository`)
- Test: `orm/eyened_orm/tests/test_form_schema_repository.py`

**Interfaces:**
- Consumes: `eyened_orm.FormSchema` (columns `FormSchemaID`, `SchemaName`).
- Produces:
  - `FormSchemaRepository().list_all(session: Session) -> list[FormSchema]` — ordered by `SchemaName` ascending.
  - `FormSchemaRepository().get_by_id(session: Session, form_schema_id: int) -> FormSchema | None` — `None` if absent.

- [ ] **Step 1: Write the failing test**

Create `orm/eyened_orm/tests/test_form_schema_repository.py`:

```python
from eyened_orm import FormSchema
from eyened_orm.repositories.form_schema_repository import FormSchemaRepository


def test_list_all_orders_by_schema_name(session):
    # list_all returns every schema sorted by name ascending.
    session.add_all(
        [
            FormSchema(SchemaName="Zeta"),
            FormSchema(SchemaName="Alpha"),
            FormSchema(SchemaName="Mu"),
        ]
    )
    session.flush()

    result = FormSchemaRepository().list_all(session)

    assert [s.SchemaName for s in result] == ["Alpha", "Mu", "Zeta"]


def test_get_by_id_returns_the_schema(session):
    # A known id returns that schema.
    schema = FormSchema(SchemaName="Alpha")
    session.add(schema)
    session.flush()

    result = FormSchemaRepository().get_by_id(session, schema.FormSchemaID)

    assert result is not None
    assert result.SchemaName == "Alpha"


def test_get_by_id_unknown_id_returns_none(session):
    # An unknown id returns None — the repository never raises for "not found".
    assert FormSchemaRepository().get_by_id(session, 999_999) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest orm/eyened_orm/tests/test_form_schema_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eyened_orm.repositories.form_schema_repository'`.

- [ ] **Step 3: Write the repository**

Create `orm/eyened_orm/repositories/form_schema_repository.py`:

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from eyened_orm import FormSchema


class FormSchemaRepository:
    """Data access for FormSchema rows."""

    def list_all(self, session: Session) -> list[FormSchema]:
        """Return all form schemas, ordered by schema name ascending."""
        return list(
            session.scalars(
                select(FormSchema).order_by(FormSchema.SchemaName.asc())
            ).all()
        )

    def get_by_id(self, session: Session, form_schema_id: int) -> FormSchema | None:
        """Return the form schema with the given id, or None if absent."""
        return session.get(FormSchema, form_schema_id)
```

Update `orm/eyened_orm/repositories/__init__.py`:

```python
from .device_repository import DeviceRepository
from .form_schema_repository import FormSchemaRepository
from .patient_repository import PatientRepository

__all__ = ["DeviceRepository", "PatientRepository", "FormSchemaRepository"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest orm/eyened_orm/tests/test_form_schema_repository.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add orm/eyened_orm/repositories/form_schema_repository.py orm/eyened_orm/repositories/__init__.py orm/eyened_orm/tests/test_form_schema_repository.py
git commit -m "feat(repositories): add FormSchemaRepository"
```

---

### Task 2: FormSchemaService

**Files:**
- Create: `server/services/form_schema_service.py`
- Modify: `server/services/__init__.py` (re-export `FormSchemaService`)
- Test: `server/tests/test_form_schema_service.py`

**Interfaces:**
- Consumes: `FormSchemaRepository.list_all` / `.get_by_id` (Task 1); `NotFoundError` (foundation).
- Produces:
  - `FormSchemaService(repository: FormSchemaRepository)`.
  - `FormSchemaService.list_form_schemas(session: Session) -> list[FormSchema]`.
  - `FormSchemaService.get_form_schema(session: Session, form_schema_id: int) -> FormSchema` — raises `NotFoundError` if absent.
  - `get_form_schema_service() -> FormSchemaService` — default-wiring factory.

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_form_schema_service.py`:

```python
import pytest

from eyened_orm import FormSchema
from eyened_orm.repositories.form_schema_repository import FormSchemaRepository

from server.services.exceptions import NotFoundError
from server.services.form_schema_service import FormSchemaService


def test_list_form_schemas_returns_rows_in_order(session):
    # The service hands back the repository's rows, order intact.
    session.add_all([FormSchema(SchemaName="Zeta"), FormSchema(SchemaName="Alpha")])
    session.flush()

    service = FormSchemaService(FormSchemaRepository())
    result = service.list_form_schemas(session)

    assert [s.SchemaName for s in result] == ["Alpha", "Zeta"]


def test_get_form_schema_returns_the_schema(session):
    # An existing schema is returned by the service unchanged.
    schema = FormSchema(SchemaName="Alpha")
    session.add(schema)
    session.flush()

    service = FormSchemaService(FormSchemaRepository())
    result = service.get_form_schema(session, schema.FormSchemaID)

    assert result.SchemaName == "Alpha"


def test_get_form_schema_unknown_id_raises_not_found(session):
    # A missing schema makes the service raise NotFoundError (-> 404 via handler).
    service = FormSchemaService(FormSchemaRepository())

    with pytest.raises(NotFoundError):
        service.get_form_schema(session, 999_999)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest server/tests/test_form_schema_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.services.form_schema_service'`.

- [ ] **Step 3: Write the service**

Create `server/services/form_schema_service.py`:

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from eyened_orm import FormSchema
from eyened_orm.repositories.form_schema_repository import FormSchemaRepository

from .exceptions import NotFoundError


class FormSchemaService:
    """Business logic for form schemas."""

    def __init__(self, repository: FormSchemaRepository) -> None:
        self.repository = repository

    def list_form_schemas(self, session: Session) -> list[FormSchema]:
        """Return all form schemas, ordered by schema name."""
        return self.repository.list_all(session)

    def get_form_schema(self, session: Session, form_schema_id: int) -> FormSchema:
        """Return the form schema with the given id.

        Raises:
            NotFoundError: If no form schema with ``form_schema_id`` exists.
        """
        schema = self.repository.get_by_id(session, form_schema_id)
        if schema is None:
            raise NotFoundError(f"FormSchema {form_schema_id} not found")
        return schema


def get_form_schema_service() -> FormSchemaService:
    """Default FormSchemaService wiring for FastAPI ``Depends()``."""
    return FormSchemaService(FormSchemaRepository())
```

Update `server/services/__init__.py`:

```python
from .device_service import DeviceService
from .exceptions import NotFoundError, ServiceError
from .form_schema_service import FormSchemaService
from .patient_service import PatientService

__all__ = [
    "ServiceError",
    "NotFoundError",
    "DeviceService",
    "PatientService",
    "FormSchemaService",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest server/tests/test_form_schema_service.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add server/services/form_schema_service.py server/services/__init__.py server/tests/test_form_schema_service.py
git commit -m "feat(services): add FormSchemaService with NotFoundError on missing schema"
```

---

### Task 3: Rewire `routes/form_schema.py` to use FormSchemaService

**Files:**
- Modify: `server/routes/form_schema.py`

**Interfaces:**
- Consumes: `FormSchemaService.list_form_schemas` / `.get_form_schema` and `get_form_schema_service` (Task 2); existing `DTOConverter.form_schema_to_get`, `FormSchemaGET`, `get_db`, `get_current_user`. The old inline `raise HTTPException(404, "FormSchema not found")` is removed — the 404 now flows from `NotFoundError` through the foundation's central handler.
- Produces: unchanged HTTP contract — `GET /form-schemas` returns `list[FormSchemaGET]`; `GET /form-schemas/{form_schema_id}` returns `FormSchemaGET`, still 404 for unknown ids.

- [ ] **Step 1: Replace the inline queries with Service calls**

Replace the entire contents of `server/routes/form_schema.py` with:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_main import FormSchemaGET
from ..services.form_schema_service import FormSchemaService, get_form_schema_service
from .auth import CurrentUser, get_current_user

router = APIRouter()


@router.get("/form-schemas", response_model=list[FormSchemaGET])
async def list_form_schemas(
    db: Session = Depends(get_db),
    service: FormSchemaService = Depends(get_form_schema_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return all form schemas."""
    rows = service.list_form_schemas(db)
    return [DTOConverter.form_schema_to_get(s) for s in rows]


@router.get("/form-schemas/{form_schema_id}", response_model=FormSchemaGET)
async def get_form_schema(
    form_schema_id: int,
    db: Session = Depends(get_db),
    service: FormSchemaService = Depends(get_form_schema_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    schema = service.get_form_schema(db, form_schema_id)
    return DTOConverter.form_schema_to_get(schema)
```

- [ ] **Step 2: Verify the router imports and exposes both routes**

Run: `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/python -c "from server.routes import form_schema; print(sorted(r.path for r in form_schema.router.routes))"`
Expected: prints `['/form-schemas', '/form-schemas/{form_schema_id}']` with no traceback.

- [ ] **Step 3: Run the full test suite to confirm no regressions**

Run: `dev/.venv/bin/pytest -q`
Expected: all tests pass (foundation suite + the new Task 1–2 tests); no import/collection errors.

- [ ] **Step 4: Commit**

```bash
git add server/routes/form_schema.py
git commit -m "refactor(routes): route form_schema endpoints through FormSchemaService"
```

---

## Verification (end-to-end, on `feature/rbac-step1-service-layer`)

1. **Full suite green:** `dev/.venv/bin/pytest -q` — foundation suite plus the new FormSchema repository/service tests pass.
2. **Both routes exposed:** the Task 3 Step 2 command prints `['/form-schemas', '/form-schemas/{form_schema_id}']`.
3. **App boots:** `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/python -c "import server.main; print('ok')"` → `ok`.
4. **Manual smoke (optional, real dev DB + server):** `GET /api/form-schemas` returns a JSON list; `GET /api/form-schemas/999999` returns HTTP 404 `{"detail": "FormSchema 999999 not found"}` — proving the `NotFoundError` → central-handler path is live rather than the old inline `HTTPException`.
5. **Branch isolation:** `development` has not moved; `git log development..HEAD` shows only foundation + form_schema commits — confirming `development` was never touched.

## Post-implementation (push only — still no `development` change)

```bash
git push origin feature/rbac-step1-service-layer
```

This updates the remote with the form_schema commits. Do NOT open or merge a PR into `development` yet (per the current constraint). When you are ready to integrate later, the single `feature/rbac-step1-service-layer` branch carries the foundation + form_schema work together.

## Out of scope / follow-up

- Phase 2 (`studies`, `feature`, `tag`), Phase 3 (`subtask`, `task`), Phase 4 (`import_api`, `instances`, `form_annotations`, `segmentations`) — each a further increment on this branch (or its own PR later), same pattern.
- RBAC enforcement itself is **Step 2** (`PermissionDeniedError` + per-method authz).
