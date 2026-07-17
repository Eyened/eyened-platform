# feature Repository/Service Migration (RBAC Step 1, Phase 2b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route the five `features` endpoints (`GET /features`, `POST /features`, `GET /features/{id}`, `PATCH /features/{id}`, `DELETE /features/{id}`) through a `FeatureService`/`FeatureRepository`, committing directly onto the current `feature/rbac-step1-service-layer` branch (never touching `development`).

**Architecture:** Same layering as the reviewed Device/Patient/FormSchema/Study slices — thin route (parse → Service → `DTOConverter` → return), Service with a constructor-injected Repository raising domain exceptions and owning the commit, framework-agnostic Repository taking a `Session`. This phase reuses the conventions the `studies` slice introduced (Service owns `session.commit()`; audit logging is a constructor-injected dependency; routes pass an `ActingUser`), and adds **one new element**: `ConflictError` (409) carrying a **structured dict** detail body (`{code, message, ...}`), which requires widening `ServiceError.detail` from `str` to `str | dict`.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (ORM `eyened_orm`), pytest with the in-memory SQLite `session` fixture.

## Global Constraints

Copied verbatim from `docs/superpowers/specs/2026-07-03-repository-service-layer-design.md`. Every task implicitly includes these:

- **Filenames:** snake_case, one file per model — `feature_repository.py`, `feature_service.py`.
- **Class names:** `FeatureRepository` / `FeatureService`.
- **Repositories** live in `orm/eyened_orm/repositories/`, take a `Session` as a method argument (never own/create sessions), have no FastAPI imports, and return `None`/empty on "not found" — never raise HTTP-shaped errors.
- **Services** live in `server/services/`, receive their Repository via constructor injection, and raise the domain exceptions in `server/services/exceptions.py` — **never** raise `HTTPException` directly.
- **DTO conversion stays at the route boundary** (via `DTOConverter`), never inside a Service.
- **Package `__init__.py` files re-export** their public classes (with `__all__`), keeping all existing exports.
- **No mocking library.** DB-backed tests use the real in-memory SQLite `session` fixture (already exposed to `server/tests/` by the foundation's `server/tests/conftest.py`). Any non-DB fake is a small hand-rolled object.
- **Do not touch:** CLI/worker code, `search.py`, `auth.py`, `Base`'s generic classmethods, or the pre-existing Device/Patient/FormSchema/Study slices.
- **Repository tests** → `orm/eyened_orm/tests/`; **Service tests** → `server/tests/`.

### Conventions reused from the `studies` phase (Phase 2a)

- **Commit ownership:** `get_db` (`server/db.py`) yields a session that is only *closed*, never committed, by its context manager. Every mutating Service method calls `session.commit()` itself — the Service is the transaction boundary.
- **Audit logging is injected, not global-reached.** The Service takes `logger: DatabaseModificationLogger | None = None` via its constructor and calls it inside the mutating method. `get_feature_service()` wires the real logger via `get_db_logger()`; Service tests inject `None` or a small hand-rolled fake. Every logging call stays guarded by `if self.logger is not None:` (matching today's `if logger:` guard, since `get_db_logger()` returns `None` when DB logging is disabled).
- **Acting user:** routes map their handler-layer `CurrentUser` onto the framework-agnostic `ActingUser(id, username)` value object (`server/services/acting_user.py`, already exists) before calling a Service.

> **Interpreter note:** no `python`/`pytest` on `PATH`; the venv is at `dev/.venv`. Every command uses `dev/.venv/bin/python` / `dev/.venv/bin/pytest`.

> **Reused from earlier work on `feature/rbac-step1-service-layer`:** `ServiceError`/`NotFoundError`/`BadRequestError` and the central handler (`server/services/exceptions.py`, registered in `server/main.py` via `register_exception_handlers` — the handler dispatches every `ServiceError` subclass by MRO, so the new `ConflictError` needs **no** `main.py` change); the `session` fixture already imported in `server/tests/conftest.py`; the `ActingUser` value object; both `repositories/` and `services/` packages with their `__init__.py` re-exports.

> **Existing ORM/DTO facts confirmed for this plan:**
> - `Feature` (`orm/eyened_orm/segmentation.py:590`): `FeatureID` (PK), `FeatureName` (`String(60)`, **unique**), `DateInserted` (server default). Properties: `subfeatures -> dict[int, str]`, `has_segmentations`, `is_child`.
> - `FeatureFeatureLink` (`orm/eyened_orm/segmentation.py:562`, table `CompositeFeature`): composite PK `(ParentFeatureID, ChildFeatureID, FeatureIndex)`. `ParentFeatureID` FK → `Feature` `ON DELETE CASCADE` (`passive_deletes=True` on `Feature.FeatureAssociations`); `ChildFeatureID` FK → `Feature` `ON DELETE RESTRICT`. **`FeatureIndex` is 0-based** in the API path (the route uses `enumerate(...)` starting at 0 — preserve this; note `Feature.from_list` uses 1-based indices for a different, CLI code path we do not touch).
> - `Segmentation.FeatureID` FK → `Feature`; used only to *count* references when guarding delete.
> - DTOs (`server/dtos/dtos_main.py`): `FeaturePUT(name: str, subfeature_ids: list[int] | None)`, `FeaturePATCH(name: str | None, subfeature_ids: list[int] | None)`, `FeatureGET(...)`. `DTOConverter.feature_to_get(feature, segmentation_count=None)` (`server/dtos/dto_converter.py:479`) already exists and stays at the route boundary unchanged.
> - The in-memory SQLite test DB runs with `PRAGMA foreign_keys=ON`, so every FK (a `FeatureFeatureLink`'s child id, a `Segmentation`'s feature id) must reference a real row.

---

## Task 0 (git): Confirm the working branch and a green baseline

Not a code task. All new work stays on `feature/rbac-step1-service-layer`; `development` is never touched.

- [ ] **Step 1: Confirm the working branch**

```bash
git branch --show-current   # expect: feature/rbac-step1-service-layer
```

- [ ] **Step 2: Confirm the pre-existing suite is green before adding anything**

Run: `dev/.venv/bin/pytest -q`
Expected: the existing suite (foundation + Device/Patient/FormSchema/Study slices) collects and passes (baseline: 125 passed). **If anything is already red, stop and surface it — do not build on a red baseline.**

---

## Task 1: Add `ConflictError` (409) and widen `ServiceError.detail` to accept a dict

The `DELETE /features/{id}` endpoint raises HTTP 409 with a **structured** detail body (`{code, message, segmentation_count}` or `{code, message, parents}`), which the hierarchy cannot express yet: `ServiceError.__init__` currently types `detail` as `str`. Widen it to `str | dict` and add one subclass; the central handler already dispatches by MRO and already serializes `exc.detail` straight into `{"detail": exc.detail}`, so a dict detail flows through unchanged and **no `main.py` change** is needed.

**Files:**
- Modify: `server/services/exceptions.py` (widen `detail` type; add `ConflictError`)
- Modify: `server/services/__init__.py` (re-export `ConflictError`)
- Test: `server/tests/test_services_exceptions.py` (extend — file already exists)

**Interfaces:**
- Consumes: existing `ServiceError` base + `service_error_to_response`.
- Produces: `ConflictError(ServiceError)` with `status_code = 409`, constructor `ConflictError(detail: str | dict)`; `ServiceError.detail` now `str | dict`.

- [ ] **Step 1: Write the failing test**

Append to `server/tests/test_services_exceptions.py`:

```python
def test_conflict_error_maps_to_409_with_structured_detail():
    """ConflictError maps to HTTP 409 and preserves a structured (dict) detail body."""
    from server.services.exceptions import ConflictError

    detail = {
        "code": "FEATURE_HAS_SEGMENTATIONS",
        "message": "Cannot delete feature 'X' because it has 3 linked segmentation(s).",
        "segmentation_count": 3,
    }
    resp = service_error_to_response(ConflictError(detail))
    assert resp.status_code == 409
    assert json.loads(resp.body) == {"detail": detail}
```

> This test relies on `json` and `service_error_to_response` already being imported at the top of `test_services_exceptions.py` (they are — the existing `BadRequestError`/`NotFoundError` tests use them). Only `ConflictError` is imported inline, matching the existing `BadRequestError` test's style.

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest server/tests/test_services_exceptions.py::test_conflict_error_maps_to_409_with_structured_detail -v`
Expected: FAIL — `ImportError: cannot import name 'ConflictError'`.

- [ ] **Step 3: Widen the base type and add the exception**

In `server/services/exceptions.py`, change the `ServiceError.__init__` signature so `detail` accepts a dict:

```python
class ServiceError(Exception):
    """Base class for service-layer errors. Maps to HTTP ``status_code``."""

    status_code: int = 500

    def __init__(self, detail: str | dict) -> None:
        self.detail = detail
        super().__init__(detail)
```

Then add this class immediately after `BadRequestError`:

```python
class ConflictError(ServiceError):
    """A request conflicts with the current state of a resource (maps to HTTP 409).

    Its ``detail`` is a structured dict (``{"code", "message", ...}``) so the
    client can branch on a stable ``code`` rather than parsing a message string.
    The central handler serializes it into ``{"detail": <dict>}`` unchanged.
    """

    status_code = 409
```

Update `server/services/__init__.py` to re-export it:

```python
from .acting_user import ActingUser
from .device_service import DeviceService
from .exceptions import BadRequestError, ConflictError, NotFoundError, ServiceError
from .form_schema_service import FormSchemaService
from .patient_service import PatientService
from .study_service import StudyService

__all__ = [
    "ServiceError",
    "NotFoundError",
    "BadRequestError",
    "ConflictError",
    "ActingUser",
    "DeviceService",
    "PatientService",
    "FormSchemaService",
    "StudyService",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest server/tests/test_services_exceptions.py -v`
Expected: PASS (all pre-existing exception tests + the new 409 test).

- [ ] **Step 5: Commit**

```bash
git add server/services/exceptions.py server/services/__init__.py server/tests/test_services_exceptions.py
git commit -m "feat(services): add ConflictError (409) with structured dict detail"
```

---

## Task 2: FeatureRepository

Named read/query methods for the lookups the `features` handlers perform inline today, plus `replace_subfeatures` (the module-level `set_subfeatures` helper moved down from the route — it is a query-shaped delete+reinsert, not a trivial single-row op, so it belongs in the Repository). No method commits; the Service owns the transaction boundary.

**Files:**
- Create: `orm/eyened_orm/repositories/feature_repository.py`
- Modify: `orm/eyened_orm/repositories/__init__.py` (add `FeatureRepository`)
- Test: `orm/eyened_orm/tests/test_feature_repository.py`

**Interfaces:**
- Consumes: `eyened_orm.Feature`, `eyened_orm.segmentation.FeatureFeatureLink`, `eyened_orm.segmentation.Segmentation`.
- Produces (all take `session: Session` first):
  - `get_by_id(session, feature_id: int) -> Feature | None`
  - `list_all(session) -> list[Feature]` — ordered by `FeatureName` ascending.
  - `segmentation_counts(session) -> dict[int, int]` — `{FeatureID: count}` over all features that have segmentations.
  - `count_segmentations(session, feature_id: int) -> int`
  - `parent_names_of_child(session, feature_id: int) -> list[str]` — names of features that list this feature as a child.
  - `list_subfeature_ids(session, feature_id: int) -> list[int]` — child ids ordered by `FeatureIndex`.
  - `replace_subfeatures(session, parent_id: int, sub_ids: list[int] | None) -> None` — delete existing parent→child links, re-add 0-indexed; flushes, does **not** commit.

- [ ] **Step 1: Write the failing test**

Create `orm/eyened_orm/tests/test_feature_repository.py`:

```python
from eyened_orm import Feature
from eyened_orm.repositories.feature_repository import FeatureRepository


def _feat(session, name: str) -> Feature:
    f = Feature(FeatureName=name)
    session.add(f)
    session.flush()
    return f


def test_list_all_orders_by_name(session):
    """list_all returns every feature sorted by FeatureName ascending."""
    _feat(session, "Zeta")
    _feat(session, "Alpha")
    _feat(session, "Mu")
    names = [f.FeatureName for f in FeatureRepository().list_all(session)]
    assert names == ["Alpha", "Mu", "Zeta"]


def test_replace_subfeatures_sets_ordered_children(session):
    """replace_subfeatures writes child links preserving list order as 0-based FeatureIndex."""
    parent = _feat(session, "parent")
    a = _feat(session, "a")
    b = _feat(session, "b")
    repo = FeatureRepository()

    repo.replace_subfeatures(session, parent.FeatureID, [b.FeatureID, a.FeatureID])

    assert repo.list_subfeature_ids(session, parent.FeatureID) == [b.FeatureID, a.FeatureID]


def test_replace_subfeatures_overwrites_previous(session):
    """replace_subfeatures clears prior links before writing the new set."""
    parent = _feat(session, "parent")
    a = _feat(session, "a")
    b = _feat(session, "b")
    repo = FeatureRepository()
    repo.replace_subfeatures(session, parent.FeatureID, [a.FeatureID])

    repo.replace_subfeatures(session, parent.FeatureID, [b.FeatureID])

    assert repo.list_subfeature_ids(session, parent.FeatureID) == [b.FeatureID]


def test_parent_names_of_child_lists_parents(session):
    """parent_names_of_child returns the names of features linking to this child."""
    parent = _feat(session, "parent")
    child = _feat(session, "child")
    FeatureRepository().replace_subfeatures(session, parent.FeatureID, [child.FeatureID])

    assert FeatureRepository().parent_names_of_child(session, child.FeatureID) == ["parent"]


def test_count_segmentations_zero_when_none(session):
    """count_segmentations returns 0 for a feature with no linked segmentations."""
    f = _feat(session, "lonely")
    assert FeatureRepository().count_segmentations(session, f.FeatureID) == 0


def test_segmentation_counts_empty_when_no_segmentations(session):
    """segmentation_counts returns an empty mapping when no segmentations exist."""
    _feat(session, "x")
    assert FeatureRepository().segmentation_counts(session) == {}
```

> **Note — why no dedicated `get_by_id` test:** it is a thin `session.get(...)` wrapper whose happy and not-found paths are exercised through the Task 3 Service tests (e.g. `test_get_feature_returns_it`, `test_get_feature_unknown_raises_not_found`). The `>0`/non-empty segmentation-count paths are forced with a hand-rolled fake in the Service tests (building a full `Segmentation` graph would add FK setup unrelated to what is being verified).

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest orm/eyened_orm/tests/test_feature_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eyened_orm.repositories.feature_repository'`.

- [ ] **Step 3: Write the repository**

Create `orm/eyened_orm/repositories/feature_repository.py`:

```python
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from eyened_orm import Feature
from eyened_orm.segmentation import FeatureFeatureLink, Segmentation


class FeatureRepository:
    """Data access for Feature rows and their parent/child (composite) links."""

    def get_by_id(self, session: Session, feature_id: int) -> Feature | None:
        """Return the feature with the given id, or None if absent."""
        return session.get(Feature, feature_id)

    def list_all(self, session: Session) -> list[Feature]:
        """Return all features ordered by name (ascending)."""
        return list(
            session.scalars(select(Feature).order_by(Feature.FeatureName.asc())).all()
        )

    def segmentation_counts(self, session: Session) -> dict[int, int]:
        """Return {FeatureID: segmentation count} for features that have any."""
        rows = session.execute(
            select(Segmentation.FeatureID, func.count()).group_by(Segmentation.FeatureID)
        ).all()
        return {fid: cnt for fid, cnt in rows}

    def count_segmentations(self, session: Session, feature_id: int) -> int:
        """Return how many segmentations reference this feature."""
        return session.execute(
            select(func.count())
            .select_from(Segmentation)
            .where(Segmentation.FeatureID == feature_id)
        ).scalar_one()

    def parent_names_of_child(self, session: Session, feature_id: int) -> list[str]:
        """Return the names of features that list this feature as a child."""
        return list(
            session.execute(
                select(Feature.FeatureName)
                .join(
                    FeatureFeatureLink,
                    Feature.FeatureID == FeatureFeatureLink.ParentFeatureID,
                )
                .where(FeatureFeatureLink.ChildFeatureID == feature_id)
            )
            .scalars()
            .all()
        )

    def list_subfeature_ids(self, session: Session, feature_id: int) -> list[int]:
        """Return this feature's child ids, ordered by FeatureIndex."""
        return list(
            session.execute(
                select(FeatureFeatureLink.ChildFeatureID)
                .where(FeatureFeatureLink.ParentFeatureID == feature_id)
                .order_by(FeatureFeatureLink.FeatureIndex)
            )
            .scalars()
            .all()
        )

    def replace_subfeatures(
        self, session: Session, parent_id: int, sub_ids: list[int] | None
    ) -> None:
        """Replace all of a feature's child links with ``sub_ids`` (0-indexed).

        Deletes existing parent->child links, then re-adds one link per id in
        order. Flushes so a following read in the same transaction sees the new
        state; does not commit (the Service owns the transaction boundary).
        """
        session.execute(
            delete(FeatureFeatureLink).where(
                FeatureFeatureLink.ParentFeatureID == parent_id
            )
        )
        for idx, child_id in enumerate(sub_ids or []):
            session.add(
                FeatureFeatureLink(
                    ParentFeatureID=parent_id,
                    ChildFeatureID=child_id,
                    FeatureIndex=idx,
                )
            )
        session.flush()
```

Update `orm/eyened_orm/repositories/__init__.py`:

```python
from .device_repository import DeviceRepository
from .feature_repository import FeatureRepository
from .form_schema_repository import FormSchemaRepository
from .patient_repository import PatientRepository
from .study_repository import StudyRepository

__all__ = [
    "DeviceRepository",
    "PatientRepository",
    "FormSchemaRepository",
    "StudyRepository",
    "FeatureRepository",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest orm/eyened_orm/tests/test_feature_repository.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add orm/eyened_orm/repositories/feature_repository.py orm/eyened_orm/repositories/__init__.py orm/eyened_orm/tests/test_feature_repository.py
git commit -m "feat(repositories): add FeatureRepository"
```

---

## Task 3: FeatureService

Holds the business rules the `features` handlers encode today (existence → 404, two delete guards → 409, create/update-with-subfeatures orchestration), owns the commit, and emits audit logging via an injected logger.

**Files:**
- Create: `server/services/feature_service.py`
- Modify: `server/services/__init__.py` (re-export `FeatureService`)
- Test: `server/tests/test_feature_service.py`

**Interfaces:**
- Consumes: `FeatureRepository` (Task 2); `NotFoundError`/`ConflictError` (Task 1); `ActingUser`; `DatabaseModificationLogger`/`get_db_logger` (`server/utils/db_logging.py`); `eyened_orm.Feature`.
- Produces:
  - `FeatureService(repository: FeatureRepository, logger: DatabaseModificationLogger | None = None)`.
  - `list_features(session, with_counts: bool) -> tuple[list[Feature], dict[int, int]]` — features ordered by name; counts is `{}` unless `with_counts`.
  - `get_feature(session, feature_id) -> Feature` — 404 if absent.
  - `create_feature(session, name, subfeature_ids, actor) -> Feature` — inserts a feature + its subfeature links.
  - `update_feature(session, feature_id, name, subfeature_ids, actor) -> Feature` — 404 if absent; updates name and/or subfeatures (each optional).
  - `delete_feature(session, feature_id, actor) -> None` — 404 if absent; 409 (`FEATURE_HAS_SEGMENTATIONS`) if any segmentation references it; 409 (`FEATURE_IS_CHILD`) if it is a child of any feature; else deletes.
  - `get_feature_service() -> FeatureService` — default-wiring factory (`FeatureRepository()` + `get_db_logger()`).

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_feature_service.py`:

```python
import pytest

from eyened_orm import Feature
from eyened_orm.repositories.feature_repository import FeatureRepository

from server.services.acting_user import ActingUser
from server.services.exceptions import ConflictError, NotFoundError
from server.services.feature_service import FeatureService


def _make_feature(session, name: str) -> Feature:
    f = Feature(FeatureName=name)
    session.add(f)
    session.flush()
    return f


def _service(logger=None) -> FeatureService:
    return FeatureService(FeatureRepository(), logger=logger)


def _actor() -> ActingUser:
    return ActingUser(id=1, username="alice")


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


class _SegBlockingRepo:
    """Hand-rolled fake forcing the 'has segmentations' guard without a real Segmentation."""

    def get_by_id(self, session, feature_id):
        f = Feature(FeatureName="Retina")
        f.FeatureID = feature_id
        return f

    def count_segmentations(self, session, feature_id):
        return 3


def test_create_feature_persists_with_subfeatures(session):
    """Creating a feature with subfeature ids writes the ordered child links."""
    child = _make_feature(session, "child")

    feature = _service().create_feature(session, "parent", [child.FeatureID], _actor())

    assert feature.FeatureName == "parent"
    assert FeatureRepository().list_subfeature_ids(session, feature.FeatureID) == [
        child.FeatureID
    ]


def test_create_feature_without_subfeatures(session):
    """Creating a feature with no subfeatures leaves it childless."""
    feature = _service().create_feature(session, "solo", None, _actor())

    assert feature.FeatureName == "solo"
    assert FeatureRepository().list_subfeature_ids(session, feature.FeatureID) == []


def test_create_feature_logs_insert(session):
    """Creating a feature emits one insert audit record naming the entity and user."""
    logger = FakeAuditLogger()

    _service(logger).create_feature(session, "solo", None, _actor())

    assert len(logger.inserts) == 1
    assert logger.inserts[0]["entity"] == "Feature"
    assert logger.inserts[0]["user"] == "alice"


def test_get_feature_returns_it(session):
    """get_feature returns the ORM object for an existing id."""
    feature = _make_feature(session, "x")
    assert _service().get_feature(session, feature.FeatureID).FeatureID == feature.FeatureID


def test_get_feature_unknown_raises_not_found(session):
    """get_feature on a missing id is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().get_feature(session, 999_999)


def test_list_features_orders_by_name_and_omits_counts(session):
    """list_features(with_counts=False) returns name-sorted features and an empty count map."""
    _make_feature(session, "Zeta")
    _make_feature(session, "Alpha")

    features, counts = _service().list_features(session, with_counts=False)

    assert [f.FeatureName for f in features] == ["Alpha", "Zeta"]
    assert counts == {}


def test_update_feature_changes_name(session):
    """Updating name overwrites FeatureName in place."""
    feature = _make_feature(session, "old")

    updated = _service().update_feature(
        session, feature.FeatureID, "new", None, _actor()
    )

    assert updated.FeatureName == "new"


def test_update_feature_replaces_subfeatures(session):
    """Updating subfeature_ids replaces the child link set."""
    parent = _make_feature(session, "parent")
    a = _make_feature(session, "a")
    b = _make_feature(session, "b")
    service = _service()
    service.update_feature(session, parent.FeatureID, None, [a.FeatureID], _actor())

    service.update_feature(session, parent.FeatureID, None, [b.FeatureID], _actor())

    assert FeatureRepository().list_subfeature_ids(session, parent.FeatureID) == [
        b.FeatureID
    ]


def test_update_feature_unknown_raises_not_found(session):
    """Updating a missing feature is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().update_feature(session, 999_999, "x", None, _actor())


def test_update_feature_logs_update(session):
    """Updating a feature emits one update audit record."""
    feature = _make_feature(session, "old")
    logger = FakeAuditLogger()

    _service(logger).update_feature(session, feature.FeatureID, "new", None, _actor())

    assert len(logger.updates) == 1
    assert logger.updates[0]["entity"] == "Feature"


def test_delete_feature_removes_it(session):
    """Deleting an unreferenced feature removes it from the database."""
    feature = _make_feature(session, "gone")

    _service().delete_feature(session, feature.FeatureID, _actor())

    assert FeatureRepository().get_by_id(session, feature.FeatureID) is None


def test_delete_feature_unknown_raises_not_found(session):
    """Deleting a missing feature is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().delete_feature(session, 999_999, _actor())


def test_delete_feature_blocked_by_child_link_raises_conflict(session):
    """A feature that is a child of another cannot be deleted (409 FEATURE_IS_CHILD)."""
    parent = _make_feature(session, "parent")
    child = _make_feature(session, "child")
    FeatureRepository().replace_subfeatures(session, parent.FeatureID, [child.FeatureID])

    with pytest.raises(ConflictError) as exc:
        _service().delete_feature(session, child.FeatureID, _actor())

    detail = exc.value.detail
    assert detail["code"] == "FEATURE_IS_CHILD"
    assert detail["parents"] == ["parent"]


def test_delete_feature_blocked_by_segmentations_raises_conflict(session):
    """A feature with linked segmentations cannot be deleted (409 FEATURE_HAS_SEGMENTATIONS)."""
    service = FeatureService(_SegBlockingRepo())

    with pytest.raises(ConflictError) as exc:
        service.delete_feature(session, 7, _actor())

    detail = exc.value.detail
    assert detail["code"] == "FEATURE_HAS_SEGMENTATIONS"
    assert detail["segmentation_count"] == 3


def test_delete_feature_logs_delete(session):
    """Deleting a feature emits one delete audit record."""
    feature = _make_feature(session, "gone")
    logger = FakeAuditLogger()

    _service(logger).delete_feature(session, feature.FeatureID, _actor())

    assert len(logger.deletes) == 1
    assert logger.deletes[0]["entity"] == "Feature"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest server/tests/test_feature_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.services.feature_service'`.

- [ ] **Step 3: Write the service**

Create `server/services/feature_service.py`:

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from eyened_orm import Feature
from eyened_orm.repositories.feature_repository import FeatureRepository

from ..utils.db_logging import DatabaseModificationLogger, get_db_logger
from .acting_user import ActingUser
from .exceptions import ConflictError, NotFoundError


class FeatureService:
    """Business logic for features and their composite (parent/child) links."""

    def __init__(
        self,
        repository: FeatureRepository,
        logger: DatabaseModificationLogger | None = None,
    ) -> None:
        self.repository = repository
        self.logger = logger

    def list_features(
        self, session: Session, with_counts: bool
    ) -> tuple[list[Feature], dict[int, int]]:
        """Return all features (name-sorted); counts is {} unless with_counts."""
        features = self.repository.list_all(session)
        counts = self.repository.segmentation_counts(session) if with_counts else {}
        return features, counts

    def get_feature(self, session: Session, feature_id: int) -> Feature:
        """Return a feature by id.

        Raises:
            NotFoundError: If the feature does not exist.
        """
        feature = self.repository.get_by_id(session, feature_id)
        if feature is None:
            raise NotFoundError(f"Feature {feature_id} not found")
        return feature

    def create_feature(
        self,
        session: Session,
        name: str,
        subfeature_ids: list[int] | None,
        actor: ActingUser,
    ) -> Feature:
        """Create a feature and set its subfeature links."""
        feature = Feature(FeatureName=name)
        session.add(feature)
        session.flush()
        self.repository.replace_subfeatures(session, feature.FeatureID, subfeature_ids)
        session.commit()
        session.refresh(feature)
        if self.logger is not None:
            self.logger.log_insert(
                user=actor.username,
                user_id=actor.id,
                endpoint="POST /api/features",
                entity="Feature",
                entity_id=feature.FeatureID,
                fields={"name": feature.FeatureName, "subfeature_ids": subfeature_ids or []},
            )
        return feature

    def update_feature(
        self,
        session: Session,
        feature_id: int,
        name: str | None,
        subfeature_ids: list[int] | None,
        actor: ActingUser,
    ) -> Feature:
        """Update a feature's name and/or subfeature links (each optional).

        Raises:
            NotFoundError: If the feature does not exist.
        """
        feature = self.repository.get_by_id(session, feature_id)
        if feature is None:
            raise NotFoundError(f"Feature {feature_id} not found")

        changes: dict[str, str] = {}
        if name is not None:
            changes["name"] = f"{feature.FeatureName} -> {name}"
            feature.FeatureName = name
        if subfeature_ids is not None:
            current = self.repository.list_subfeature_ids(session, feature_id)
            changes["subfeature_ids"] = f"{current} -> {subfeature_ids}"
            self.repository.replace_subfeatures(session, feature_id, subfeature_ids)

        session.commit()
        session.refresh(feature)
        if self.logger is not None:
            self.logger.log_update(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"PATCH /api/features/{feature_id}",
                entity="Feature",
                entity_id=feature_id,
                changes=changes if changes else None,
            )
        return feature

    def delete_feature(
        self, session: Session, feature_id: int, actor: ActingUser
    ) -> None:
        """Delete a feature, unless it is referenced by segmentations or is a child.

        Raises:
            NotFoundError: If the feature does not exist.
            ConflictError: If segmentations reference it (FEATURE_HAS_SEGMENTATIONS)
                or it is a child of another feature (FEATURE_IS_CHILD).
        """
        feature = self.repository.get_by_id(session, feature_id)
        if feature is None:
            raise NotFoundError(f"Feature {feature_id} not found")

        seg_count = self.repository.count_segmentations(session, feature_id)
        if seg_count > 0:
            raise ConflictError(
                {
                    "code": "FEATURE_HAS_SEGMENTATIONS",
                    "message": (
                        f"Cannot delete feature '{feature.FeatureName}' because it has "
                        f"{seg_count} linked segmentation(s)."
                    ),
                    "segmentation_count": seg_count,
                }
            )

        parents = self.repository.parent_names_of_child(session, feature_id)
        if parents:
            raise ConflictError(
                {
                    "code": "FEATURE_IS_CHILD",
                    "message": (
                        f"Cannot delete feature '{feature.FeatureName}' because it is a "
                        f"child of {len(parents)} feature(s). Remove those links first."
                    ),
                    "parents": parents,
                }
            )

        deleted_data = {"name": feature.FeatureName}
        session.delete(feature)
        session.commit()
        if self.logger is not None:
            self.logger.log_delete(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"DELETE /api/features/{feature_id}",
                entity="Feature",
                entity_id=feature_id,
                deleted_data=deleted_data,
            )
        return None


def get_feature_service() -> FeatureService:
    """Default FeatureService wiring for FastAPI ``Depends()``."""
    return FeatureService(FeatureRepository(), logger=get_db_logger())
```

Update `server/services/__init__.py`:

```python
from .acting_user import ActingUser
from .device_service import DeviceService
from .exceptions import BadRequestError, ConflictError, NotFoundError, ServiceError
from .feature_service import FeatureService
from .form_schema_service import FormSchemaService
from .patient_service import PatientService
from .study_service import StudyService

__all__ = [
    "ServiceError",
    "NotFoundError",
    "BadRequestError",
    "ConflictError",
    "ActingUser",
    "DeviceService",
    "PatientService",
    "FormSchemaService",
    "StudyService",
    "FeatureService",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest server/tests/test_feature_service.py -v`
Expected: PASS (15 passed).

- [ ] **Step 5: Commit**

```bash
git add server/services/feature_service.py server/services/__init__.py server/tests/test_feature_service.py
git commit -m "feat(services): add FeatureService with ConflictError delete guards and injected audit logging"
```

---

## Task 4: Rewire `routes/feature.py` to use FeatureService

**Files:**
- Modify: `server/routes/feature.py`

**Interfaces:**
- Consumes: `FeatureService` + `get_feature_service` (Task 3); `ActingUser`; existing `DTOConverter.feature_to_get`, `FeatureGET`/`FeaturePUT`/`FeaturePATCH`, `get_db`, `get_current_user`. The module-level `set_subfeatures` helper, all inline `db.get(...)`/`select(...)` queries, `raise HTTPException(...)`, `db.commit()`, and `get_db_logger()` calls are removed — they now live in the Repository/Service.
- Produces: unchanged HTTP contract — `GET /features` → `list[FeatureGET]` (optional `?with_counts=`); `POST /features` → `FeatureGET`; `GET /features/{id}` → `FeatureGET`; `PATCH /features/{id}` → `FeatureGET`; `DELETE /features/{id}` → 204. Same 404 for unknown feature and same **structured** 409 bodies for the two delete guards (now flowing through the central handler).

- [ ] **Step 1: Replace the module contents with thin Service-backed handlers**

Replace the entire contents of `server/routes/feature.py` with:

```python
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_main import FeatureGET, FeaturePATCH, FeaturePUT
from ..services.acting_user import ActingUser
from ..services.feature_service import FeatureService, get_feature_service
from .auth import CurrentUser, get_current_user

router = APIRouter()


@router.get("/features", response_model=list[FeatureGET])
async def list_features(
    with_counts: bool = False,
    db: Session = Depends(get_db),
    service: FeatureService = Depends(get_feature_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return all features (optionally with a per-feature segmentation count)."""
    features, counts = service.list_features(db, with_counts)
    if not with_counts:
        return [DTOConverter.feature_to_get(f) for f in features]
    return [DTOConverter.feature_to_get(f, counts.get(f.FeatureID, 0)) for f in features]


@router.post("/features", response_model=FeatureGET)
async def create_feature(
    dto: FeaturePUT,
    db: Session = Depends(get_db),
    service: FeatureService = Depends(get_feature_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a feature and set its subfeature links."""
    feature = service.create_feature(
        db,
        dto.name,
        dto.subfeature_ids,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.feature_to_get(feature)


@router.get("/features/{feature_id}", response_model=FeatureGET)
async def get_feature(
    feature_id: int,
    db: Session = Depends(get_db),
    service: FeatureService = Depends(get_feature_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return a single feature by id."""
    return DTOConverter.feature_to_get(service.get_feature(db, feature_id))


@router.patch("/features/{feature_id}", response_model=FeatureGET)
async def patch_feature(
    feature_id: int,
    dto: FeaturePATCH,
    db: Session = Depends(get_db),
    service: FeatureService = Depends(get_feature_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a feature's name and/or subfeature links."""
    feature = service.update_feature(
        db,
        feature_id,
        dto.name,
        dto.subfeature_ids,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.feature_to_get(feature)


@router.delete("/features/{feature_id}", status_code=204)
async def delete_feature(
    feature_id: int,
    db: Session = Depends(get_db),
    service: FeatureService = Depends(get_feature_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a feature (409 if it has segmentations or is a child of another)."""
    service.delete_feature(
        db,
        feature_id,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return Response(status_code=204)
```

- [ ] **Step 2: Verify the router imports and exposes all five routes**

Run: `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/python -c "from server.routes import feature; print(sorted((r.path, tuple(sorted(r.methods))) for r in feature.router.routes))"`
Expected: prints the routes — `/features` (GET and POST), `/features/{feature_id}` (GET, PATCH, DELETE) — with no traceback.

- [ ] **Step 3: Run the full test suite to confirm no regressions**

Run: `dev/.venv/bin/pytest -q`
Expected: all tests pass (prior suite + the new Task 1–3 tests); no import/collection errors.

- [ ] **Step 4: Commit**

```bash
git add server/routes/feature.py
git commit -m "refactor(routes): route feature endpoints through FeatureService"
```

---

## Task 5 (fix): Populate `FeatureGET.subfeature_ids` from the ORM

**Not a refactor step — a standalone bug fix, committed separately.** Today
`DTOConverter.feature_to_get` reads `getattr(feature, "subfeature_ids_list", None)`
and falls back to `getattr(feature, "ChildLinks", [])`, but **neither attribute
exists on `Feature`** — so `GET /features` always returns `subfeature_ids: []`.
The frontend relies on this field to pre-select a composite feature's current
subfeatures when editing (`client/src/lib/components/FeatureForm.svelte:16`:
`feature?.subfeature_ids?.map(String) ?? []`), so editing a composite feature
currently shows none of its existing subfeatures checked.

The converter already looks for a `subfeature_ids_list` property; the fix is to
add that property to the `Feature` model (mirroring the adjacent `subfeatures`
property). The `FeatureGET` schema is unchanged (`subfeature_ids: list[int]`),
so **no `openapi.ts` regeneration is needed** — only the values become correct.

**Files:**
- Modify: `orm/eyened_orm/segmentation.py` (add `Feature.subfeature_ids_list`)
- Test: `orm/eyened_orm/tests/test_feature_model.py` (new file)

**Interfaces:**
- Consumes: `Feature.FeatureAssociations` (existing parent→child link relationship).
- Produces: `Feature.subfeature_ids_list -> list[int]` — child ids ordered by `FeatureIndex`.

- [ ] **Step 1: Write the failing test**

Create `orm/eyened_orm/tests/test_feature_model.py`:

```python
from eyened_orm import Feature
from eyened_orm.segmentation import FeatureFeatureLink


def _feat(session, name: str) -> Feature:
    f = Feature(FeatureName=name)
    session.add(f)
    session.flush()
    return f


def test_subfeature_ids_list_returns_child_ids_in_index_order(session):
    """subfeature_ids_list returns child ids ordered by FeatureIndex, not id."""
    parent = _feat(session, "parent")
    a = _feat(session, "a")
    b = _feat(session, "b")
    # Link out of natural id order to prove ordering is by FeatureIndex.
    session.add(
        FeatureFeatureLink(ParentFeatureID=parent.FeatureID, ChildFeatureID=b.FeatureID, FeatureIndex=0)
    )
    session.add(
        FeatureFeatureLink(ParentFeatureID=parent.FeatureID, ChildFeatureID=a.FeatureID, FeatureIndex=1)
    )
    session.flush()
    # The parent's FeatureAssociations collection was initialized empty when the
    # object was created; expire it so the property reloads the links from the DB
    # (this is exactly what happens for a feature freshly loaded in a request).
    session.expire(parent, ["FeatureAssociations"])

    assert parent.subfeature_ids_list == [b.FeatureID, a.FeatureID]


def test_subfeature_ids_list_empty_without_children(session):
    """A feature with no child links has an empty subfeature_ids_list."""
    assert _feat(session, "solo").subfeature_ids_list == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest orm/eyened_orm/tests/test_feature_model.py -v`
Expected: FAIL — `AttributeError: 'Feature' object has no attribute 'subfeature_ids_list'`.

- [ ] **Step 3: Add the property**

In `orm/eyened_orm/segmentation.py`, add this property to the `Feature` class,
immediately after the existing `subfeatures` property (around line 722):

```python
    @property
    def subfeature_ids_list(self) -> List[int]:
        """Child feature ids ordered by FeatureIndex (drives FeatureGET.subfeature_ids)."""
        assocs = sorted(self.FeatureAssociations, key=lambda x: x.FeatureIndex)
        return [assoc.ChildFeatureID for assoc in assocs]
```

> `List` is already imported in this module (used by the surrounding relationship
> annotations), so no new import is required.

- [ ] **Step 4: Run tests to verify they pass**

Run: `dev/.venv/bin/pytest orm/eyened_orm/tests/test_feature_model.py -v`
Expected: PASS (2 passed).

Then confirm the converter now emits real ids (the property it already reaches for
via `getattr` now exists):

Run: `dev/.venv/bin/pytest -q`
Expected: full suite still green.

- [ ] **Step 5: Commit**

```bash
git add orm/eyened_orm/segmentation.py orm/eyened_orm/tests/test_feature_model.py
git commit -m "fix(orm): populate FeatureGET.subfeature_ids via Feature.subfeature_ids_list"
```

---

## Verification (end-to-end, on `feature/rbac-step1-service-layer`)

1. **Full suite green:** `dev/.venv/bin/pytest -q` — prior suite plus the new exception/FeatureRepository/FeatureService tests pass.
2. **All five routes exposed:** the Task 4 Step 2 command prints GET/POST `/features` and GET/PATCH/DELETE `/features/{feature_id}`.
3. **App boots:** `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/python -c "import server.main; print('ok')"` → `ok`.
4. **Manual smoke (optional, real dev DB + server):**
   - `GET /api/features/999999` → HTTP 404 `{"detail": "Feature 999999 not found"}` (proves the `NotFoundError` → central-handler path is live).
   - `DELETE` a feature that has linked segmentations → HTTP 409 `{"detail": {"code": "FEATURE_HAS_SEGMENTATIONS", ...}}` (proves the new structured `ConflictError` → 409 path).
   - `DELETE` a feature that is a subfeature of another → HTTP 409 `{"detail": {"code": "FEATURE_IS_CHILD", ...}}`.
   - `POST /api/features` with `{"name": "X", "subfeature_ids": [<id>]}` → 200 `FeatureGET`; `PATCH` its name → 200; `DELETE` an unreferenced feature → 204.
5. **Subfeature ids populated (Task 5 fix):** `GET /api/features/{id}` for a composite feature returns a **non-empty** `subfeature_ids` matching its links (was always `[]` before); opening that feature in the frontend edit dialog now pre-selects its current subfeatures.
6. **Branch isolation:** `git log development..HEAD` shows only the RBAC-step1 commits; `development` has not moved.

## Out of scope / follow-up

- Phase 2c `tag` — its own plan/PR on this branch, same pattern (reuses `ConflictError`/`BadRequestError`/`ActingUser`, adds nothing new to the exception hierarchy).
- Phase 3 (`subtask`, `task`), Phase 4 (`import_api`, `instances`, `form_annotations`, `segmentations`).
- Transaction-ownership review across all Services (spec "Follow-up work") once every phase has migrated.
- RBAC enforcement itself is **Step 2** (`PermissionDeniedError` + per-method authz checks that read `ActingUser`).
