# Repository/Service Layer (RBAC Step 1) — Foundation + Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a Repository + Service layering into the FastAPI backend, establishing all shared scaffolding and proving the pattern end-to-end on two representative route modules (`devices`, a list endpoint; `patients`, a get-by-id endpoint with a 404 path).

**Architecture:** Route handlers become thin (parse → call Service → convert via existing `DTOConverter` → return). Services (`server/services/`) hold business logic, receive their Repository via constructor injection, and raise domain exceptions. Repositories (`orm/eyened_orm/repositories/`) hold named, framework-agnostic query methods that take a `Session` argument. A single central FastAPI exception handler maps domain exceptions (`ServiceError` subclasses) to HTTP responses.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (ORM `eyened_orm`), pytest with an in-memory SQLite `session` fixture.

## Global Constraints

Copied verbatim from `docs/superpowers/specs/2026-07-03-repository-service-layer-design.md`. Every task implicitly includes these:

- **Filenames:** snake_case, one file per model — `<model>_repository.py`, `<model>_service.py`.
- **Class names:** `<Model>Repository` / `<Model>Service` (e.g. `DeviceRepository`, `PatientService`).
- **Repositories** live in `orm/eyened_orm/repositories/`, take a `Session` as a method argument (never own/create sessions), have no FastAPI imports, and return `None`/empty on "not found" — they never raise HTTP-shaped errors.
- **Services** live in `server/services/`, receive their Repository via constructor injection, and raise the domain exceptions in `server/services/exceptions.py` — **never** raise `HTTPException` directly.
- **DTO conversion stays at the route boundary** (via `DTOConverter`), never inside a Service.
- **Package `__init__.py` files re-export** their public classes (with `__all__`) so `from eyened_orm.repositories import DeviceRepository` and `from server.services import DeviceService` work.
- **No mocking library** (`unittest.mock`/`pytest-mock`) is introduced. DB-backed tests use the real in-memory SQLite `session` fixture; any non-DB fake is a small hand-rolled object.
- **Do not touch:** CLI/worker code (`orm/eyened_orm/commands/`), `search.py`, `auth.py`, or `Base`'s existing generic classmethods.
- **Repository tests** go in `orm/eyened_orm/tests/`; **Service tests** go in `server/tests/`. Both are already covered by `testpaths = ["server", "orm"]` in `pyproject.toml`.

---

### Task 1: Domain exception hierarchy + central handler registration

**Files:**
- Create: `server/services/__init__.py`
- Create: `server/services/exceptions.py`
- Test: `server/tests/test_services_exceptions.py`
- Modify: `server/main.py` (register the handler on `app_api`)

**Interfaces:**
- Consumes: nothing (foundation task).
- Produces:
  - `ServiceError(Exception)` with class attribute `status_code: int = 500` and instance attribute `.detail: str` (constructor `ServiceError(detail: str)`).
  - `NotFoundError(ServiceError)` with `status_code = 404`.
  - `service_error_to_response(exc: ServiceError) -> fastapi.responses.JSONResponse`.
  - `register_exception_handlers(app: fastapi.FastAPI) -> None`.

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_services_exceptions.py`:

```python
import json

from fastapi import FastAPI

from server.services.exceptions import (
    NotFoundError,
    ServiceError,
    register_exception_handlers,
    service_error_to_response,
)


def test_not_found_error_maps_to_404_response():
    # A NotFoundError should become an HTTP 404 carrying its message.
    resp = service_error_to_response(NotFoundError("Patient 5 not found"))
    assert resp.status_code == 404
    assert json.loads(resp.body) == {"detail": "Patient 5 not found"}


def test_base_service_error_maps_to_500_response():
    # A plain ServiceError (no status override) falls back to HTTP 500.
    resp = service_error_to_response(ServiceError("boom"))
    assert resp.status_code == 500
    assert json.loads(resp.body) == {"detail": "boom"}


def test_register_exception_handlers_registers_service_error_base():
    # Registering the ServiceError base is what makes every subclass (incl.
    # Step 2's future PermissionDeniedError) dispatch through this one handler,
    # since Starlette resolves handlers by walking the exception's MRO.
    app = FastAPI()
    register_exception_handlers(app)
    assert ServiceError in app.exception_handlers
```

(This uses a throwaway `FastAPI()` app, not `TestClient` — httpx is not installed in the environment, so a real HTTP round-trip test is intentionally avoided. Asserting the handler is registered plus the pure-mapping tests above together cover the design.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest server/tests/test_services_exceptions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.services'`.

- [ ] **Step 3: Write the exceptions module**

Create `server/services/exceptions.py`:

```python
"""Domain exceptions raised by the service layer, plus their HTTP mapping.

Services raise these instead of ``HTTPException``. A single FastAPI handler
(registered via ``register_exception_handlers``) maps them to responses, so
new exception types (e.g. RBAC's future ``PermissionDeniedError``) only need
a subclass with a ``status_code`` — no per-route wiring.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ServiceError(Exception):
    """Base class for service-layer errors. Maps to HTTP ``status_code``."""

    status_code: int = 500

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class NotFoundError(ServiceError):
    """A requested entity does not exist."""

    status_code = 404


def service_error_to_response(exc: ServiceError) -> JSONResponse:
    """Map a ServiceError to the JSON error response shape used by the API."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def register_exception_handlers(app: FastAPI) -> None:
    """Register a single handler that maps every ServiceError subclass.

    Starlette resolves handlers by walking the exception's MRO, so registering
    the ``ServiceError`` base catches all subclasses; each subclass's
    ``status_code`` drives the response.
    """

    @app.exception_handler(ServiceError)
    async def _handle_service_error(request: Request, exc: ServiceError) -> JSONResponse:
        return service_error_to_response(exc)
```

Create `server/services/__init__.py`:

```python
from .exceptions import NotFoundError, ServiceError

__all__ = ["ServiceError", "NotFoundError"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest server/tests/test_services_exceptions.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Register the handler in `server/main.py`**

In `server/main.py`, add the import near the other `server.*` imports (after line 28, the `from server.config import ...` line):

```python
from server.services.exceptions import register_exception_handlers
```

Then, immediately after the router-registration block (after line 44, `app_api.include_router(patients.router)`), add:

```python
register_exception_handlers(app_api)
```

(Registered on `app_api` — the sub-app mounted at `/api` where all routes live — not `app`. Ordering relative to the existing `@app_api.exception_handler(...)` handlers does not matter; Starlette dispatches by exception type.)

- [ ] **Step 6: Verify the app still imports cleanly**

Run: `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password python -c "import server.main; print('ok')"`
Expected: prints `ok` with no traceback. (The dummy DB env vars mirror `server/tests/conftest.py`'s `pytest_configure`; `Database()` builds an engine lazily and does not connect at import.)

- [ ] **Step 7: Commit**

```bash
git add server/services/__init__.py server/services/exceptions.py server/tests/test_services_exceptions.py server/main.py
git commit -m "feat(services): add domain exception hierarchy and central handler"
```

---

### Task 2: DeviceRepository

**Files:**
- Create: `orm/eyened_orm/repositories/__init__.py`
- Create: `orm/eyened_orm/repositories/device_repository.py`
- Test: `orm/eyened_orm/tests/test_device_repository.py`

**Interfaces:**
- Consumes: `eyened_orm.DeviceModel` (existing ORM model, `image_instance.py:946`; columns `DeviceModelID`, `Manufacturer`, `ManufacturerModelName`).
- Produces: `DeviceRepository().list_all(session: Session) -> list[DeviceModel]`, ordered by `Manufacturer` then `ManufacturerModelName` ascending.

- [ ] **Step 1: Write the failing test**

Create `orm/eyened_orm/tests/test_device_repository.py`:

```python
from eyened_orm import DeviceModel
from eyened_orm.repositories.device_repository import DeviceRepository


def test_list_all_orders_by_manufacturer_then_model(session):
    # list_all returns every device sorted by manufacturer, then model name.
    session.add_all(
        [
            DeviceModel(Manufacturer="Zeiss", ManufacturerModelName="Cirrus"),
            DeviceModel(Manufacturer="Topcon", ManufacturerModelName="Maestro"),
            DeviceModel(Manufacturer="Topcon", ManufacturerModelName="Aladdin"),
        ]
    )
    session.flush()

    result = DeviceRepository().list_all(session)

    names = [(d.Manufacturer, d.ManufacturerModelName) for d in result]
    assert names == [
        ("Topcon", "Aladdin"),
        ("Topcon", "Maestro"),
        ("Zeiss", "Cirrus"),
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest orm/eyened_orm/tests/test_device_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eyened_orm.repositories'`.

- [ ] **Step 3: Write the repository**

Create `orm/eyened_orm/repositories/device_repository.py`:

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from eyened_orm import DeviceModel


class DeviceRepository:
    """Data access for DeviceModel rows."""

    def list_all(self, session: Session) -> list[DeviceModel]:
        """Return all device models, ordered by manufacturer then model name."""
        return list(
            session.scalars(
                select(DeviceModel).order_by(
                    DeviceModel.Manufacturer.asc(),
                    DeviceModel.ManufacturerModelName.asc(),
                )
            ).all()
        )
```

Create `orm/eyened_orm/repositories/__init__.py`:

```python
from .device_repository import DeviceRepository

__all__ = ["DeviceRepository"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest orm/eyened_orm/tests/test_device_repository.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add orm/eyened_orm/repositories/__init__.py orm/eyened_orm/repositories/device_repository.py orm/eyened_orm/tests/test_device_repository.py
git commit -m "feat(repositories): add DeviceRepository"
```

---

### Task 3: DeviceService (+ expose the SQLite session fixture to server tests)

**Files:**
- Create: `server/services/device_service.py`
- Modify: `server/services/__init__.py` (re-export `DeviceService`)
- Modify: `server/tests/conftest.py` (re-export the in-memory `session` fixture)
- Test: `server/tests/test_device_service.py`

**Interfaces:**
- Consumes: `DeviceRepository().list_all(session)` (Task 2).
- Produces:
  - `DeviceService(repository: DeviceRepository)` — constructor injection.
  - `DeviceService.list_devices(session: Session) -> list[DeviceModel]`.
  - `get_device_service() -> DeviceService` — default-wiring factory for `Depends()`.

- [ ] **Step 1: Expose the session fixture to server tests**

The in-memory SQLite `session` fixture lives in `orm/eyened_orm/utils/sqlite_testdb.py` and is re-exported by `orm/eyened_orm/tests/conftest.py`, but `server/tests/conftest.py` does not currently expose it. Add this import at the **top** of `server/tests/conftest.py` (above the existing `import os` / `pytest_configure`), so Service tests can request the `session` fixture:

```python
from eyened_orm.utils.sqlite_testdb import (  # noqa: F401
    SessionLocal,
    engine,
    session,
)
```

(Importing `eyened_orm` here is safe and needs no DB env — it only imports classes; the fixture builds its own in-memory engine.)

- [ ] **Step 2: Write the failing test**

Create `server/tests/test_device_service.py`:

```python
from eyened_orm import DeviceModel
from eyened_orm.repositories.device_repository import DeviceRepository

from server.services.device_service import DeviceService


def test_list_devices_returns_repository_rows_in_order(session):
    # The service hands back exactly what the repository returns, order intact.
    session.add_all(
        [
            DeviceModel(Manufacturer="Zeiss", ManufacturerModelName="Cirrus"),
            DeviceModel(Manufacturer="Topcon", ManufacturerModelName="Maestro"),
        ]
    )
    session.flush()

    service = DeviceService(DeviceRepository())
    result = service.list_devices(session)

    assert [d.Manufacturer for d in result] == ["Topcon", "Zeiss"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest server/tests/test_device_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.services.device_service'`.

- [ ] **Step 4: Write the service**

Create `server/services/device_service.py`:

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from eyened_orm import DeviceModel
from eyened_orm.repositories.device_repository import DeviceRepository


class DeviceService:
    """Business logic for device models."""

    def __init__(self, repository: DeviceRepository) -> None:
        self.repository = repository

    def list_devices(self, session: Session) -> list[DeviceModel]:
        """Return all device models, ordered by manufacturer then model name."""
        return self.repository.list_all(session)


def get_device_service() -> DeviceService:
    """Default DeviceService wiring for FastAPI ``Depends()``."""
    return DeviceService(DeviceRepository())
```

Update `server/services/__init__.py` to re-export it:

```python
from .device_service import DeviceService
from .exceptions import NotFoundError, ServiceError

__all__ = ["ServiceError", "NotFoundError", "DeviceService"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest server/tests/test_device_service.py -v`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git add server/services/device_service.py server/services/__init__.py server/tests/conftest.py server/tests/test_device_service.py
git commit -m "feat(services): add DeviceService and expose sqlite session fixture to server tests"
```

---

### Task 4: Rewire `routes/devices.py` to use DeviceService

**Files:**
- Modify: `server/routes/devices.py`

**Interfaces:**
- Consumes: `DeviceService.list_devices(session)` and `get_device_service` (Task 3); existing `DTOConverter.device_model_to_get`, `DeviceModelGET`, `get_db`, `get_current_user`.
- Produces: unchanged HTTP contract — `GET /devices` still returns `list[DeviceModelGET]`.

- [ ] **Step 1: Replace the inline query with a Service call**

Replace the entire contents of `server/routes/devices.py` with:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_main import DeviceModelGET
from ..services.device_service import DeviceService, get_device_service
from .auth import CurrentUser, get_current_user

router = APIRouter()


@router.get("/devices", response_model=list[DeviceModelGET])
async def list_devices(
    db: Session = Depends(get_db),
    service: DeviceService = Depends(get_device_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return all device models."""
    rows = service.list_devices(db)
    return [DTOConverter.device_model_to_get(r) for r in rows]
```

- [ ] **Step 2: Verify the router imports and exposes the route**

Run: `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password python -c "from server.routes import devices; print(sorted((r.path, tuple(sorted(r.methods))) for r in devices.router.routes))"`
Expected: prints `[('/devices', ('GET', 'HEAD'))]` (or similar) with no traceback.

- [ ] **Step 3: Run the full test suite to confirm no regressions**

Run: `pytest -q`
Expected: all tests pass (including the Task 1–3 tests); no import/collection errors.

- [ ] **Step 4: Commit**

```bash
git add server/routes/devices.py
git commit -m "refactor(routes): route devices endpoint through DeviceService"
```

---

### Task 5: PatientRepository

**Files:**
- Create: `orm/eyened_orm/repositories/patient_repository.py`
- Modify: `orm/eyened_orm/repositories/__init__.py` (add `PatientRepository`)
- Test: `orm/eyened_orm/tests/test_patient_repository.py`

**Interfaces:**
- Consumes: `eyened_orm.Patient` (`patient.py:27`; `PatientID`, `PatientIdentifier`, non-nullable `ProjectID`), `eyened_orm.AttributeValue`, `eyened_orm.Project` (`project.py`; requires `ProjectName` + `External`), `eyened_orm.project.ExternalEnum`.
- Produces: `PatientRepository().get_with_attributes(session: Session, patient_id: int, include_attributes: bool = True) -> Patient | None` — eager-loads `Patient.Project`, and (when `include_attributes`) both `Patient.AttributeValues -> AttributeValue.AttributeDefinition` and `Patient.AttributeValues -> AttributeValue.ProducingModel`. Returns `None` if no such patient. (The two attribute eager-loads mirror the current `server/routes/patients.py` `get_patient` handler exactly — `ProducingModel` is the attribute-provenance relationship added on the `development` branch; omitting it would reintroduce an N+1 when `DTOConverter.patient_to_detail_get` reads `av.ProducingModel`.)

- [ ] **Step 1: Write the failing test**

Create `orm/eyened_orm/tests/test_patient_repository.py`:

```python
from eyened_orm import Patient, Project
from eyened_orm.project import ExternalEnum
from eyened_orm.repositories.patient_repository import PatientRepository


def _make_patient(session, identifier: str = "ID1") -> Patient:
    project = Project(ProjectName=f"Project-{identifier}", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier=identifier, ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    return patient


def test_get_with_attributes_returns_the_patient(session):
    # Looking up an existing patient by id returns that patient.
    patient = _make_patient(session)

    result = PatientRepository().get_with_attributes(session, patient.PatientID)

    assert result is not None
    assert result.PatientIdentifier == "ID1"


def test_get_with_attributes_unknown_id_returns_none(session):
    # An unknown id returns None — the repository never raises for "not found".
    assert PatientRepository().get_with_attributes(session, 999_999) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest orm/eyened_orm/tests/test_patient_repository.py -v`
Expected: FAIL — `ImportError: cannot import name 'PatientRepository'`.

- [ ] **Step 3: Write the repository**

Create `orm/eyened_orm/repositories/patient_repository.py`:

```python
from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from eyened_orm import AttributeValue, Patient


class PatientRepository:
    """Data access for Patient rows."""

    def get_with_attributes(
        self,
        session: Session,
        patient_id: int,
        include_attributes: bool = True,
    ) -> Patient | None:
        """Return a patient by id with Project (and optionally attributes) eager-loaded."""
        opts = [selectinload(Patient.Project)]
        if include_attributes:
            # Mirror server/routes/patients.py: load the attribute definition AND
            # its producing-model provenance so patient_to_detail_get stays N+1-free.
            opts.append(
                selectinload(Patient.AttributeValues).selectinload(
                    AttributeValue.AttributeDefinition
                )
            )
            opts.append(
                selectinload(Patient.AttributeValues).selectinload(
                    AttributeValue.ProducingModel
                )
            )
        return session.get(Patient, patient_id, options=tuple(opts))
```

Update `orm/eyened_orm/repositories/__init__.py`:

```python
from .device_repository import DeviceRepository
from .patient_repository import PatientRepository

__all__ = ["DeviceRepository", "PatientRepository"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest orm/eyened_orm/tests/test_patient_repository.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add orm/eyened_orm/repositories/patient_repository.py orm/eyened_orm/repositories/__init__.py orm/eyened_orm/tests/test_patient_repository.py
git commit -m "feat(repositories): add PatientRepository"
```

---

### Task 6: PatientService

**Files:**
- Create: `server/services/patient_service.py`
- Modify: `server/services/__init__.py` (re-export `PatientService`)
- Test: `server/tests/test_patient_service.py`

**Interfaces:**
- Consumes: `PatientRepository.get_with_attributes(session, patient_id, include_attributes)` (Task 5); `NotFoundError` (Task 1).
- Produces:
  - `PatientService(repository: PatientRepository)`.
  - `PatientService.get_patient(session: Session, patient_id: int, include_attributes: bool = True) -> Patient` — raises `NotFoundError` if the patient does not exist.
  - `get_patient_service() -> PatientService` — default-wiring factory.

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_patient_service.py`:

```python
import pytest

from eyened_orm import Patient, Project
from eyened_orm.project import ExternalEnum
from eyened_orm.repositories.patient_repository import PatientRepository

from server.services.exceptions import NotFoundError
from server.services.patient_service import PatientService


def _make_patient(session, identifier: str = "ID1") -> Patient:
    project = Project(ProjectName=f"Project-{identifier}", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier=identifier, ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    return patient


def test_get_patient_returns_the_patient(session):
    # An existing patient is returned by the service unchanged.
    patient = _make_patient(session)

    service = PatientService(PatientRepository())
    result = service.get_patient(session, patient.PatientID)

    assert result.PatientIdentifier == "ID1"


def test_get_patient_unknown_id_raises_not_found(session):
    # A missing patient makes the service raise NotFoundError (→ 404 via handler).
    service = PatientService(PatientRepository())

    with pytest.raises(NotFoundError):
        service.get_patient(session, 999_999)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest server/tests/test_patient_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.services.patient_service'`.

- [ ] **Step 3: Write the service**

Create `server/services/patient_service.py`:

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from eyened_orm import Patient
from eyened_orm.repositories.patient_repository import PatientRepository

from .exceptions import NotFoundError


class PatientService:
    """Business logic for patients."""

    def __init__(self, repository: PatientRepository) -> None:
        self.repository = repository

    def get_patient(
        self,
        session: Session,
        patient_id: int,
        include_attributes: bool = True,
    ) -> Patient:
        """Return the patient with the given id.

        Raises:
            NotFoundError: If no patient with ``patient_id`` exists.
        """
        patient = self.repository.get_with_attributes(
            session, patient_id, include_attributes
        )
        if patient is None:
            raise NotFoundError(f"Patient {patient_id} not found")
        return patient


def get_patient_service() -> PatientService:
    """Default PatientService wiring for FastAPI ``Depends()``."""
    return PatientService(PatientRepository())
```

Update `server/services/__init__.py`:

```python
from .device_service import DeviceService
from .exceptions import NotFoundError, ServiceError
from .patient_service import PatientService

__all__ = ["ServiceError", "NotFoundError", "DeviceService", "PatientService"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest server/tests/test_patient_service.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add server/services/patient_service.py server/services/__init__.py server/tests/test_patient_service.py
git commit -m "feat(services): add PatientService with NotFoundError on missing patient"
```

---

### Task 7: Rewire `routes/patients.py` to use PatientService

**Files:**
- Modify: `server/routes/patients.py`

**Interfaces:**
- Consumes: `PatientService.get_patient(session, patient_id, include_attributes)` and `get_patient_service` (Task 6); existing `DTOConverter.patient_to_detail_get`, `PatientDetailGET`, `get_db`, `get_current_user`. The old inline `raise HTTPException(404, "Patient not found")` is removed — the 404 now flows from `NotFoundError` through the central handler registered in Task 1.
- Produces: unchanged HTTP contract — `GET /patients/{patient_id}` returns `PatientDetailGET`, still 404 for unknown ids.

- [ ] **Step 1: Replace the handler body with a Service call**

Replace the entire contents of `server/routes/patients.py` with:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_instances import PatientDetailGET
from ..services.patient_service import PatientService, get_patient_service
from .auth import CurrentUser, get_current_user

router = APIRouter()


@router.get("/patients/{patient_id}", response_model=PatientDetailGET)
async def get_patient(
    patient_id: int,
    include_attributes: bool = True,
    db: Session = Depends(get_db),
    service: PatientService = Depends(get_patient_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    patient = service.get_patient(db, patient_id, include_attributes)
    return DTOConverter.patient_to_detail_get(
        patient, include_attributes=include_attributes
    )
```

- [ ] **Step 2: Verify the router imports and exposes the route**

Run: `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password python -c "from server.routes import patients; print(sorted(r.path for r in patients.router.routes))"`
Expected: prints `['/patients/{patient_id}']` with no traceback.

- [ ] **Step 3: Run the full test suite to confirm no regressions**

Run: `pytest -q`
Expected: all tests pass; no import/collection errors.

- [ ] **Step 4: Commit**

```bash
git add server/routes/patients.py
git commit -m "refactor(routes): route patient endpoint through PatientService"
```

---

## Verification (end-to-end)

After all tasks, confirm the whole vertical slice:

1. **Full suite green:** `pytest -q` — all new Repository/Service/exception tests plus the pre-existing suite pass.
2. **App boots:** `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password python -c "import server.main; print('ok')"` prints `ok`.
3. **Manual smoke (optional, needs a real dev DB + running server):** start the API and hit `GET /api/devices` (expect a JSON list) and `GET /api/patients/999999` (expect HTTP 404 with body `{"detail": "Patient 999999 not found"}` — proving `NotFoundError` → central handler → 404). This 404 message text is the observable signal that the new exception path is live rather than the old inline `HTTPException`.

## Out of scope / follow-up plans

Each remaining phase from the spec repeats the exact pattern established here (Repository → Service → thin route, tested at Repository + Service layers with the SQLite `session` fixture) and gets its own plan/PR:

- `form_schema` (identical shape to `devices`), then Phase 2 (`studies`, `feature`, `tag`), Phase 3 (`subtask`, `task`), Phase 4 (`import_api`, `instances`, `form_annotations`, `segmentations`).
- `search.py`, `auth.py`, and CLI/worker adoption remain explicitly out of scope (see spec Non-goals).
- RBAC enforcement itself is **Step 2** — a separate brainstorm/spec that adds `PermissionDeniedError` (a new `ServiceError` subclass, auto-handled by Task 1's handler) and per-method authz checks in the Services created here.
