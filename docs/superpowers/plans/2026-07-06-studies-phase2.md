# studies Repository/Service Migration (RBAC Step 1, Phase 2a) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route the three `studies` tag endpoints (`POST /studies/{id}/tags`, `DELETE /studies/{id}/tags/{tag_id}`, `PATCH /studies/{id}/tags/{tag_id}`) through a `StudyService`/`StudyRepository`, committing directly onto the current `feature/rbac-step1-service-layer` branch (never touching `development`).

**Architecture:** Same layering as the reviewed Device/Patient/FormSchema slices — thin route (parse → Service → `DTOConverter` → return), Service with a constructor-injected Repository raising domain exceptions, framework-agnostic Repository taking a `Session`. This is the **first write-carrying module**, so it introduces three conventions (documented below and reused by the `feature`/`tag` plans): the Service owns `session.commit()`; audit logging is a constructor-injected Service dependency (not the global reached from inside the Service); and routes pass a services-layer `ActingUser` value object instead of the handler-layer `CurrentUser`.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (ORM `eyened_orm`), pytest with the in-memory SQLite `session` fixture.

## Global Constraints

Copied verbatim from `docs/superpowers/specs/2026-07-03-repository-service-layer-design.md`. Every task implicitly includes these:

- **Filenames:** snake_case, one file per model — `study_repository.py`, `study_service.py`.
- **Class names:** `StudyRepository` / `StudyService`.
- **Repositories** live in `orm/eyened_orm/repositories/`, take a `Session` as a method argument (never own/create sessions), have no FastAPI imports, and return `None`/empty on "not found" — never raise HTTP-shaped errors.
- **Services** live in `server/services/`, receive their Repository via constructor injection, and raise the domain exceptions in `server/services/exceptions.py` — **never** raise `HTTPException` directly.
- **DTO conversion stays at the route boundary** (via `DTOConverter`), never inside a Service.
- **Package `__init__.py` files re-export** their public classes (with `__all__`), keeping all existing exports.
- **No mocking library.** DB-backed tests use the real in-memory SQLite `session` fixture (already exposed to `server/tests/` by the foundation's `server/tests/conftest.py`). Any non-DB fake is a small hand-rolled object.
- **Do not touch:** CLI/worker code, `search.py`, `auth.py`, `Base`'s generic classmethods, or the pre-existing Device/Patient/FormSchema slices.
- **Repository tests** → `orm/eyened_orm/tests/`; **Service tests** → `server/tests/`.

### Conventions introduced by this phase (reused by `feature`/`tag`)

- **Commit ownership:** `get_db` (`server/db.py`) yields a session whose context manager only *closes* — it does **not** commit. So any Service method that mutates must call `session.commit()` itself. The Service is the transaction boundary.
- **Audit logging is injected, not global-reached.** Per python-design-patterns Pattern 7 (Dependency Injection) and Pattern 2/3 (SRP / Separation of Concerns): the Service takes `logger: DatabaseModificationLogger | None = None` via its constructor and calls it inside the method that performs the mutation (so the old→new `changes` diff is computed next to the write). The `get_<model>_service()` factory wires the real logger via `get_db_logger()`; Service tests inject `None` (no logging) or a small hand-rolled fake. Every logging call stays guarded by `if self.logger is not None:` — matching today's `if logger:` guard, since `get_db_logger()` returns `None` when DB logging is disabled.
- **Acting user:** routes must not leak the handler-layer `CurrentUser` (defined in `server/routes/auth.py`) into a Service — that would invert the API→Service dependency arrow. Routes map it onto a minimal, framework-agnostic `ActingUser(id, username)` value object defined in the services layer; the Service (and Step 2's authz checks) read from that.

> **Interpreter note:** no `python`/`pytest` on `PATH`; the venv is at `dev/.venv`. Every command uses `dev/.venv/bin/python` / `dev/.venv/bin/pytest`.

> **Reused from earlier work on `feature/rbac-step1-service-layer`:** `ServiceError`/`NotFoundError` and the central handler (`server/services/exceptions.py`, registered in `server/main.py` — the handler dispatches every `ServiceError` subclass by MRO, so the new `BadRequestError` needs **no** `main.py` change); the `session` fixture already imported in `server/tests/conftest.py`; both `repositories/` and `services/` packages with their `__init__.py` re-exports. Existing ORM facts confirmed for this plan: `Study` (`orm/eyened_orm/study.py:21`) needs `PatientID` (FK) + `StudyDate` (a `date`); `Patient` needs `PatientIdentifier` + `ProjectID`; `Project` needs `ProjectName` + `External` (`ExternalEnum.N`); `Creator` (`orm/eyened_orm/creator.py:12`) needs `CreatorName` (unique) + `IsHuman` (bool); `Tag` (`orm/eyened_orm/tag.py:47`) needs `TagName` + `TagType` + `TagDescription` (non-null) + `CreatorID`; `StudyTagLink` (`orm/eyened_orm/tag.py:105`) has composite PK `(TagID, StudyID)` plus `CreatorID`, nullable `Comment`, `DateInserted`. The in-memory SQLite test DB runs with `PRAGMA foreign_keys=ON`, so every FK above must reference a real row. `DTOConverter.link_to_tag_metadata` (`server/dtos/dto_converter.py:143`), `TagMeta`, `ObjectTagPOST` (`tag_id`, `comment`), and `ObjectTagPATCH` (`comment`) already exist.

---

## Task 0 (git): Confirm the working branch and a green baseline

Not a code task. All new work stays on `feature/rbac-step1-service-layer`; `development` is never touched.

- [ ] **Step 1: Confirm the working branch**

```bash
git branch --show-current   # expect: feature/rbac-step1-service-layer
```

- [ ] **Step 2: Confirm the pre-existing suite is green before adding anything**

Run: `dev/.venv/bin/pytest -q`
Expected: the existing suite (foundation + Device/Patient/FormSchema slices) collects and passes. **If anything is already red, stop and surface it — do not build on a red baseline.**

---

### Task 1: Add `BadRequestError` (400) to the exception hierarchy

The `studies` endpoints raise HTTP 400 ("Tag type must be Study"), which the foundation's hierarchy (only `NotFoundError` → 404) cannot express yet. Add one subclass; the central handler already dispatches it by MRO, so no `main.py` change.

**Files:**
- Modify: `server/services/exceptions.py` (add `BadRequestError`)
- Modify: `server/services/__init__.py` (re-export `BadRequestError`)
- Test: `server/tests/test_services_exceptions.py` (extend — this file already exists from the foundation)

**Interfaces:**
- Consumes: existing `ServiceError` base + `service_error_to_response` (foundation).
- Produces: `BadRequestError(ServiceError)` with `status_code = 400`, constructor `BadRequestError(detail: str)`.

- [ ] **Step 1: Write the failing test**

Append to `server/tests/test_services_exceptions.py`:

```python
def test_bad_request_error_maps_to_400_response():
    """BadRequestError maps to HTTP 400, carrying its detail message in the body."""
    from server.services.exceptions import BadRequestError

    resp = service_error_to_response(BadRequestError("Tag type must be Study"))
    assert resp.status_code == 400
    assert json.loads(resp.body) == {"detail": "Tag type must be Study"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest server/tests/test_services_exceptions.py::test_bad_request_error_maps_to_400_response -v`
Expected: FAIL — `ImportError: cannot import name 'BadRequestError'`.

- [ ] **Step 3: Add the exception**

In `server/services/exceptions.py`, add this class immediately after `NotFoundError`:

```python
class BadRequestError(ServiceError):
    """A request violates a business precondition (maps to HTTP 400).

    Distinct from ``pydantic.ValidationError`` (request-schema validation,
    handled by FastAPI before the Service runs); this is a domain-rule
    violation raised by the Service itself.
    """

    status_code = 400
```

Update `server/services/__init__.py` to re-export it:

```python
from .device_service import DeviceService
from .exceptions import BadRequestError, NotFoundError, ServiceError
from .form_schema_service import FormSchemaService
from .patient_service import PatientService

__all__ = [
    "ServiceError",
    "NotFoundError",
    "BadRequestError",
    "DeviceService",
    "PatientService",
    "FormSchemaService",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest server/tests/test_services_exceptions.py -v`
Expected: PASS (all pre-existing exception tests + the new 400 test).

- [ ] **Step 5: Commit**

```bash
git add server/services/exceptions.py server/services/__init__.py server/tests/test_services_exceptions.py
git commit -m "feat(services): add BadRequestError (400) to the domain exception hierarchy"
```

---

### Task 2: Add the `ActingUser` value object

A minimal, framework-agnostic value object so Services never import the handler-layer `CurrentUser`. Routes map their `CurrentUser` onto it; Step 2's authz reads from it.

This is a pure, logic-free value object (two fields, no methods), so it carries
no unit test of its own — exercising it would only re-test stdlib `dataclass`
behavior. Its construction and use are covered end-to-end by the Task 4 Service
tests (which build an `ActingUser` for every call) and the Task 5 route.

**Files:**
- Create: `server/services/acting_user.py`
- Modify: `server/services/__init__.py` (re-export `ActingUser`)

**Interfaces:**
- Consumes: nothing.
- Produces: `ActingUser(id: int, username: str)` — a frozen dataclass.

- [ ] **Step 1: Write the value object**

Create `server/services/acting_user.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActingUser:
    """The authenticated user performing a service operation.

    A framework-agnostic value object so Services never import ``CurrentUser``
    from the routes/handler layer (which would invert the API -> Service
    dependency arrow). Routes build this from their ``CurrentUser``; the
    Service uses it for audit logging now and for Step 2 authz later.
    """

    id: int
    username: str
```

Update `server/services/__init__.py`:

```python
from .acting_user import ActingUser
from .device_service import DeviceService
from .exceptions import BadRequestError, NotFoundError, ServiceError
from .form_schema_service import FormSchemaService
from .patient_service import PatientService

__all__ = [
    "ServiceError",
    "NotFoundError",
    "BadRequestError",
    "ActingUser",
    "DeviceService",
    "PatientService",
    "FormSchemaService",
]
```

- [ ] **Step 2: Verify it imports and constructs**

Run: `dev/.venv/bin/python -c "from server.services import ActingUser; a = ActingUser(id=1, username='x'); print(a.id, a.username)"`
Expected: prints `1 x` with no traceback.

- [ ] **Step 3: Commit**

```bash
git add server/services/acting_user.py server/services/__init__.py
git commit -m "feat(services): add ActingUser value object for the service layer"
```

---

### Task 3: StudyRepository

Named read methods for the three lookups the `studies` handlers perform inline today. Writes (add/delete/commit) stay in the Service (they are trivial session ops, not endpoint-shaped queries), matching the spec's "Repositories exist for the complex, endpoint-shaped queries — not to reimplement basic CRUD."

**Files:**
- Create: `orm/eyened_orm/repositories/study_repository.py`
- Modify: `orm/eyened_orm/repositories/__init__.py` (add `StudyRepository`)
- Test: `orm/eyened_orm/tests/test_study_repository.py`

**Interfaces:**
- Consumes: `eyened_orm.Study`, `eyened_orm.Tag`, `eyened_orm.StudyTagLink`.
- Produces:
  - `StudyRepository().get_by_id(session: Session, study_id: int) -> Study | None`.
  - `StudyRepository().get_tag(session: Session, tag_id: int) -> Tag | None`.
  - `StudyRepository().get_link(session: Session, tag_id: int, study_id: int) -> StudyTagLink | None`.

- [ ] **Step 1: Write the failing test**

Create `orm/eyened_orm/tests/test_study_repository.py`:

```python
import datetime

from eyened_orm import Creator, Patient, Project, Study, StudyTagLink, Tag
from eyened_orm.project import ExternalEnum
from eyened_orm.tag import TagType
from eyened_orm.repositories.study_repository import StudyRepository


def _make_study(session) -> Study:
    project = Project(ProjectName="P", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier="ID1", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    study = Study(PatientID=patient.PatientID, StudyDate=datetime.date(2020, 1, 1))
    session.add(study)
    session.flush()
    return study


def _make_creator(session) -> Creator:
    creator = Creator(CreatorName="tester", IsHuman=True)
    session.add(creator)
    session.flush()
    return creator


def _make_study_tag(session, creator_id: int) -> Tag:
    tag = Tag(
        TagName="Baseline",
        TagType=TagType.Study,
        TagDescription="",
        CreatorID=creator_id,
    )
    session.add(tag)
    session.flush()
    return tag


def test_get_link_returns_the_link(session):
    """get_link resolves the StudyTagLink by its composite (TagID, StudyID) key."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_study_tag(session, creator.CreatorID)
    session.add(
        StudyTagLink(TagID=tag.TagID, StudyID=study.StudyID, CreatorID=creator.CreatorID)
    )
    session.flush()

    result = StudyRepository().get_link(session, tag.TagID, study.StudyID)
    assert result is not None
    assert result.TagID == tag.TagID
    assert result.StudyID == study.StudyID


def test_get_link_absent_returns_none(session):
    """get_link returns None (never raises) when the pair is not linked."""
    study = _make_study(session)
    assert StudyRepository().get_link(session, 999_999, study.StudyID) is None
```

> **Note — why no direct `get_by_id`/`get_tag` tests:** both are thin `session.get(...)`
> wrappers whose happy path *and* not-found path are already exercised through the
> Task 4 Service tests (e.g. `test_tag_study_unknown_study_raises_not_found`,
> `test_tag_study_unknown_tag_raises_not_found`). Only `get_link`'s composite-key
> lookup is fallible enough to warrant its own repository-level test.

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest orm/eyened_orm/tests/test_study_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eyened_orm.repositories.study_repository'`.

- [ ] **Step 3: Write the repository**

Create `orm/eyened_orm/repositories/study_repository.py`:

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from eyened_orm import Study, StudyTagLink, Tag


class StudyRepository:
    """Data access for Study rows and their Tag links."""

    def get_by_id(self, session: Session, study_id: int) -> Study | None:
        """Return the study with the given id, or None if absent."""
        return session.get(Study, study_id)

    def get_tag(self, session: Session, tag_id: int) -> Tag | None:
        """Return the tag with the given id, or None if absent.

        Kept here (rather than depending on a future TagRepository) so this
        module migrates independently; ``studies`` only needs to read a Tag to
        validate its ``TagType`` before linking.
        """
        return session.get(Tag, tag_id)

    def get_link(
        self, session: Session, tag_id: int, study_id: int
    ) -> StudyTagLink | None:
        """Return the StudyTagLink for (tag, study), or None if not linked."""
        return session.get(StudyTagLink, {"TagID": tag_id, "StudyID": study_id})
```

Update `orm/eyened_orm/repositories/__init__.py`:

```python
from .device_repository import DeviceRepository
from .form_schema_repository import FormSchemaRepository
from .patient_repository import PatientRepository
from .study_repository import StudyRepository

__all__ = [
    "DeviceRepository",
    "PatientRepository",
    "FormSchemaRepository",
    "StudyRepository",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest orm/eyened_orm/tests/test_study_repository.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add orm/eyened_orm/repositories/study_repository.py orm/eyened_orm/repositories/__init__.py orm/eyened_orm/tests/test_study_repository.py
git commit -m "feat(repositories): add StudyRepository"
```

---

### Task 4: StudyService

Holds the business rules the `studies` handlers encode today (existence → 404, wrong tag type → 400, create-vs-update-comment), owns the commit, and emits audit logging via an injected logger.

**Files:**
- Create: `server/services/study_service.py`
- Modify: `server/services/__init__.py` (re-export `StudyService`)
- Test: `server/tests/test_study_service.py`

**Interfaces:**
- Consumes: `StudyRepository` (Task 3); `NotFoundError`/`BadRequestError` (Task 1); `ActingUser` (Task 2); `DatabaseModificationLogger`/`get_db_logger` (`server/utils/db_logging.py`); `eyened_orm.StudyTagLink`, `eyened_orm.tag.TagType`.
- Produces:
  - `StudyService(repository: StudyRepository, logger: DatabaseModificationLogger | None = None)`.
  - `StudyService.tag_study(session, study_id, tag_id, comment, actor) -> StudyTagLink` — 404 if study/tag absent, 400 if tag not a Study tag; creates the link (or updates its comment if already linked).
  - `StudyService.untag_study(session, study_id, tag_id, actor) -> None` — 404 if study absent; idempotent delete (no error if not linked).
  - `StudyService.patch_study_tag(session, study_id, tag_id, comment, actor) -> StudyTagLink` — 404 if study/tag/link absent, 400 if tag not a Study tag; updates the comment.
  - `get_study_service() -> StudyService` — default-wiring factory (`StudyRepository()` + `get_db_logger()`).

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_study_service.py`:

```python
import datetime

import pytest

from eyened_orm import Creator, Patient, Project, Study, StudyTagLink, Tag
from eyened_orm.project import ExternalEnum
from eyened_orm.tag import TagType
from eyened_orm.repositories.study_repository import StudyRepository

from server.services.acting_user import ActingUser
from server.services.exceptions import BadRequestError, NotFoundError
from server.services.study_service import StudyService


def _make_study(session) -> Study:
    project = Project(ProjectName="P", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier="ID1", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    study = Study(PatientID=patient.PatientID, StudyDate=datetime.date(2020, 1, 1))
    session.add(study)
    session.flush()
    return study


def _make_creator(session) -> Creator:
    creator = Creator(CreatorName="tester", IsHuman=True)
    session.add(creator)
    session.flush()
    return creator


def _make_tag(session, creator_id: int, tag_type: TagType = TagType.Study) -> Tag:
    tag = Tag(
        TagName=f"Tag-{tag_type.value}",
        TagType=tag_type,
        TagDescription="",
        CreatorID=creator_id,
    )
    session.add(tag)
    session.flush()
    return tag


class FakeAuditLogger:
    """Records logging calls without touching the filesystem (no mock lib)."""

    def __init__(self) -> None:
        self.inserts: list[dict] = []
        self.updates: list[dict] = []
        self.deletes: list[dict] = []

    def log_insert(self, **kwargs) -> None:
        self.inserts.append(kwargs)

    def log_update(self, **kwargs) -> None:
        self.updates.append(kwargs)

    def log_delete(self, **kwargs) -> None:
        self.deletes.append(kwargs)


def _service(logger=None) -> StudyService:
    return StudyService(StudyRepository(), logger=logger)


def _actor() -> ActingUser:
    return ActingUser(id=1, username="alice")


def test_tag_study_creates_a_new_link(session):
    """First-time tagging inserts a StudyTagLink carrying the comment and actor id."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)

    link = _service().tag_study(session, study.StudyID, tag.TagID, "hi", _actor())

    assert link.TagID == tag.TagID
    assert link.StudyID == study.StudyID
    assert link.Comment == "hi"
    assert link.CreatorID == 1


def test_tag_study_unknown_study_raises_not_found(session):
    """Tagging a non-existent study is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().tag_study(session, 999_999, 1, None, _actor())


def test_tag_study_unknown_tag_raises_not_found(session):
    """A valid study but unknown tag id is translated to NotFoundError (-> 404)."""
    study = _make_study(session)
    with pytest.raises(NotFoundError):
        _service().tag_study(session, study.StudyID, 999_999, None, _actor())


def test_tag_study_wrong_tag_type_raises_bad_request(session):
    """A non-Study tag is rejected with BadRequestError (-> 400), not linked."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID, tag_type=TagType.ImageInstance)

    with pytest.raises(BadRequestError):
        _service().tag_study(session, study.StudyID, tag.TagID, None, _actor())


def test_tag_study_existing_link_updates_comment(session):
    """Re-tagging an already-linked pair updates the comment in place (idempotent)."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)
    service = _service()
    service.tag_study(session, study.StudyID, tag.TagID, "first", _actor())

    link = service.tag_study(session, study.StudyID, tag.TagID, "second", _actor())

    assert link.Comment == "second"
    # Still a single link (no duplicate row created).
    assert StudyRepository().get_link(session, tag.TagID, study.StudyID) is not None


def test_tag_study_logs_insert_when_logger_present(session):
    """When a logger is injected, creating a link emits one insert audit record."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)
    logger = FakeAuditLogger()

    _service(logger).tag_study(session, study.StudyID, tag.TagID, "hi", _actor())

    assert len(logger.inserts) == 1
    assert logger.inserts[0]["user"] == "alice"
    assert logger.inserts[0]["entity"] == "StudyTagLink"


def test_untag_study_removes_the_link(session):
    """Untagging deletes the existing StudyTagLink for the (study, tag) pair."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)
    service = _service()
    service.tag_study(session, study.StudyID, tag.TagID, None, _actor())

    service.untag_study(session, study.StudyID, tag.TagID, _actor())

    assert StudyRepository().get_link(session, tag.TagID, study.StudyID) is None


def test_untag_study_unknown_study_raises_not_found(session):
    """Untagging a non-existent study is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().untag_study(session, 999_999, 1, _actor())


def test_untag_study_no_link_is_idempotent(session):
    """Untagging a study that has no such link is a silent no-op, not an error."""
    study = _make_study(session)
    # No link exists; deleting is a no-op, not an error.
    _service().untag_study(session, study.StudyID, 999_999, _actor())


def test_patch_study_tag_updates_comment(session):
    """Patching an existing link overwrites its comment with the new value."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)
    service = _service()
    service.tag_study(session, study.StudyID, tag.TagID, "old", _actor())

    link = service.patch_study_tag(session, study.StudyID, tag.TagID, "new", _actor())

    assert link.Comment == "new"


def test_patch_study_tag_missing_link_raises_not_found(session):
    """Patching when study+tag exist but no link does raises NotFoundError (-> 404)."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)

    with pytest.raises(NotFoundError):
        _service().patch_study_tag(session, study.StudyID, tag.TagID, "x", _actor())


def test_patch_study_tag_wrong_tag_type_raises_bad_request(session):
    """Patching a link via a non-Study tag is rejected with BadRequestError (-> 400)."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID, tag_type=TagType.Segmentation)

    with pytest.raises(BadRequestError):
        _service().patch_study_tag(session, study.StudyID, tag.TagID, "x", _actor())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest server/tests/test_study_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.services.study_service'`.

- [ ] **Step 3: Write the service**

Create `server/services/study_service.py`:

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from eyened_orm import StudyTagLink
from eyened_orm.tag import TagType
from eyened_orm.repositories.study_repository import StudyRepository

from ..utils.db_logging import DatabaseModificationLogger, get_db_logger
from .acting_user import ActingUser
from .exceptions import BadRequestError, NotFoundError


class StudyService:
    """Business logic for tagging studies."""

    def __init__(
        self,
        repository: StudyRepository,
        logger: DatabaseModificationLogger | None = None,
    ) -> None:
        self.repository = repository
        self.logger = logger

    def tag_study(
        self,
        session: Session,
        study_id: int,
        tag_id: int,
        comment: str | None,
        actor: ActingUser,
    ) -> StudyTagLink:
        """Attach a Study tag to a study (idempotent; updates comment if linked).

        Raises:
            NotFoundError: If the study or tag does not exist.
            BadRequestError: If the tag's type is not ``TagType.Study``.
        """
        study = self.repository.get_by_id(session, study_id)
        if study is None:
            raise NotFoundError(f"Study {study_id} not found")
        tag = self.repository.get_tag(session, tag_id)
        if tag is None:
            raise NotFoundError(f"Tag {tag_id} not found")
        if tag.TagType != TagType.Study:
            raise BadRequestError("Tag type must be Study")

        link = self.repository.get_link(session, tag_id, study_id)
        if link is None:
            link = StudyTagLink(
                TagID=tag.TagID,
                StudyID=study_id,
                CreatorID=actor.id,
                Comment=comment,
            )
            session.add(link)
            session.commit()
            session.refresh(link)
            link.Tag = tag
            if self.logger is not None:
                self.logger.log_insert(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=f"POST /api/studies/{study_id}/tags",
                    entity="StudyTagLink",
                    fields={
                        "tag_id": tag.TagID,
                        "study_id": study_id,
                        "comment": comment,
                    },
                )
        elif comment is not None:
            old_comment = link.Comment
            link.Comment = comment
            session.commit()
            session.refresh(link)
            link.Tag = tag
            if self.logger is not None:
                self.logger.log_update(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=f"POST /api/studies/{study_id}/tags",
                    entity="StudyTagLink",
                    fields={"tag_id": tag.TagID, "study_id": study_id},
                    changes={"comment": f"{old_comment} -> {comment}"},
                )
        return link

    def untag_study(
        self,
        session: Session,
        study_id: int,
        tag_id: int,
        actor: ActingUser,
    ) -> None:
        """Remove a Study tag from a study (idempotent).

        Raises:
            NotFoundError: If the study does not exist.
        """
        study = self.repository.get_by_id(session, study_id)
        if study is None:
            raise NotFoundError(f"Study {study_id} not found")
        link = self.repository.get_link(session, tag_id, study_id)
        if link is None:
            return None

        deleted_data = {
            "tag_id": tag_id,
            "study_id": study_id,
            "comment": link.Comment,
            "creator_id": link.CreatorID,
        }
        session.delete(link)
        session.commit()
        if self.logger is not None:
            self.logger.log_delete(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"DELETE /api/studies/{study_id}/tags/{tag_id}",
                entity="StudyTagLink",
                fields={"tag_id": tag_id, "study_id": study_id},
                deleted_data=deleted_data,
            )
        return None

    def patch_study_tag(
        self,
        session: Session,
        study_id: int,
        tag_id: int,
        comment: str | None,
        actor: ActingUser,
    ) -> StudyTagLink:
        """Update the comment on an existing Study tag link.

        Raises:
            NotFoundError: If the study, tag, or link does not exist.
            BadRequestError: If the tag's type is not ``TagType.Study``.
        """
        study = self.repository.get_by_id(session, study_id)
        if study is None:
            raise NotFoundError(f"Study {study_id} not found")
        tag = self.repository.get_tag(session, tag_id)
        if tag is None:
            raise NotFoundError(f"Tag {tag_id} not found")
        if tag.TagType != TagType.Study:
            raise BadRequestError("Tag type must be Study")
        link = self.repository.get_link(session, tag_id, study_id)
        if link is None:
            raise NotFoundError(f"Tag {tag_id} is not linked to study {study_id}")

        if comment is not None:
            old_comment = link.Comment
            link.Comment = comment
            session.commit()
            session.refresh(link)
            if self.logger is not None:
                self.logger.log_update(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=f"PATCH /api/studies/{study_id}/tags/{tag_id}",
                    entity="StudyTagLink",
                    fields={"tag_id": tag_id, "study_id": study_id},
                    changes={"comment": f"{old_comment} -> {comment}"},
                )
        link.Tag = tag
        return link


def get_study_service() -> StudyService:
    """Default StudyService wiring for FastAPI ``Depends()``."""
    return StudyService(StudyRepository(), logger=get_db_logger())
```

Update `server/services/__init__.py`:

```python
from .acting_user import ActingUser
from .device_service import DeviceService
from .exceptions import BadRequestError, NotFoundError, ServiceError
from .form_schema_service import FormSchemaService
from .patient_service import PatientService
from .study_service import StudyService

__all__ = [
    "ServiceError",
    "NotFoundError",
    "BadRequestError",
    "ActingUser",
    "DeviceService",
    "PatientService",
    "FormSchemaService",
    "StudyService",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest server/tests/test_study_service.py -v`
Expected: PASS (12 passed).

- [ ] **Step 5: Commit**

```bash
git add server/services/study_service.py server/services/__init__.py server/tests/test_study_service.py
git commit -m "feat(services): add StudyService with injected audit logging"
```

---

### Task 5: Rewire `routes/studies.py` to use StudyService

**Files:**
- Modify: `server/routes/studies.py`

**Interfaces:**
- Consumes: `StudyService` + `get_study_service` (Task 4); `ActingUser` (Task 2); existing `DTOConverter.link_to_tag_metadata`, `TagMeta`, `ObjectTagPOST`, `ObjectTagPATCH`, `get_db`, `get_current_user`. The inline `db.get(...)`, `raise HTTPException(...)`, `db.commit()`, and `get_db_logger()` calls are removed — existence/type checks now raise domain exceptions handled centrally, the Service owns the commit, and the Service emits the audit log.
- Produces: unchanged HTTP contract — `POST /studies/{id}/tags` → `TagMeta`; `DELETE /studies/{id}/tags/{tag_id}` → 204; `PATCH /studies/{id}/tags/{tag_id}` → `TagMeta`. Same 404 for unknown study/tag/link and 400 for wrong tag type (now flowing through the central handler).

- [ ] **Step 1: Replace the handler bodies with Service calls**

Replace the entire contents of `server/routes/studies.py` with:

```python
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_aux import ObjectTagPATCH, ObjectTagPOST, TagMeta
from ..services.acting_user import ActingUser
from ..services.study_service import StudyService, get_study_service
from .auth import CurrentUser, get_current_user

router = APIRouter()


@router.post("/studies/{study_id}/tags", response_model=TagMeta)
async def tag_study(
    study_id: int,
    body: ObjectTagPOST,
    db: Session = Depends(get_db),
    service: StudyService = Depends(get_study_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> TagMeta:
    """Attach a Tag to a Study by tag ID (idempotent)."""
    link = service.tag_study(
        db,
        study_id,
        body.tag_id,
        body.comment,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.link_to_tag_metadata(link)


@router.delete("/studies/{study_id}/tags/{tag_id}", status_code=204)
async def untag_study(
    study_id: int,
    tag_id: int,
    db: Session = Depends(get_db),
    service: StudyService = Depends(get_study_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Remove a Tag from a Study (idempotent)."""
    service.untag_study(
        db,
        study_id,
        tag_id,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return Response(status_code=204)


@router.patch("/studies/{study_id}/tags/{tag_id}", response_model=TagMeta)
async def patch_study_tag(
    study_id: int,
    tag_id: int,
    body: ObjectTagPATCH,
    db: Session = Depends(get_db),
    service: StudyService = Depends(get_study_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> TagMeta:
    """Update comment on an existing Study tag link."""
    link = service.patch_study_tag(
        db,
        study_id,
        tag_id,
        body.comment,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.link_to_tag_metadata(link)
```

- [ ] **Step 2: Verify the router imports and exposes all three routes**

Run: `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/python -c "from server.routes import studies; print(sorted((r.path, tuple(sorted(r.methods))) for r in studies.router.routes))"`
Expected: prints the three routes — `/studies/{study_id}/tags` (POST), `/studies/{study_id}/tags/{tag_id}` (DELETE and PATCH) — with no traceback.

- [ ] **Step 3: Run the full test suite to confirm no regressions**

Run: `dev/.venv/bin/pytest -q`
Expected: all tests pass (prior suite + the new Task 1–4 tests); no import/collection errors.

- [ ] **Step 4: Commit**

```bash
git add server/routes/studies.py
git commit -m "refactor(routes): route studies tag endpoints through StudyService"
```

---

## Verification (end-to-end, on `feature/rbac-step1-service-layer`)

1. **Full suite green:** `dev/.venv/bin/pytest -q` — prior suite plus the new exception/ActingUser/StudyRepository/StudyService tests pass.
2. **All three routes exposed:** the Task 5 Step 2 command prints the POST/DELETE/PATCH routes.
3. **App boots:** `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/python -c "import server.main; print('ok')"` → `ok`.
4. **Manual smoke (optional, real dev DB + server):**
   - `POST /api/studies/999999/tags` with a JSON body `{"tag_id": 1}` → HTTP 404 `{"detail": "Study 999999 not found"}` (proves the `NotFoundError` → central-handler path is live).
   - Tag a real study with a non-Study tag → HTTP 400 `{"detail": "Tag type must be Study"}` (proves the new `BadRequestError` → 400 path).
   - Tag a real study with a real Study tag → HTTP 200 `TagMeta`; repeat → still 200 (idempotent); `DELETE` → 204.
5. **Branch isolation:** `git log development..HEAD` shows only the RBAC-step1 commits; `development` has not moved.

## Out of scope / follow-up

- Phase 2b `feature` and Phase 2c `tag` — each its own plan/PR on this branch, same pattern. `feature` additionally introduces `ConflictError` (409) with a **structured** detail body (`{code, message, ...}`), which will widen `ServiceError`'s `detail` to accept a dict; `tag` reuses everything here.
- Phase 3 (`subtask`, `task`), Phase 4 (`import_api`, `instances`, `form_annotations`, `segmentations`).
- RBAC enforcement itself is **Step 2** (`PermissionDeniedError` + per-method authz checks that read `ActingUser`).
```
