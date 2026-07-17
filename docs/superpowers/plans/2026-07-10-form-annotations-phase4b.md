# form_annotations Repository/Service Migration (RBAC Step 1, Phase 4b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route the `form_annotations.py` endpoints — the FormAnnotation CRUD (`POST/GET/GET{id}/PATCH{id}/DELETE{id}`), the raw-value read/write (`GET/PUT .../value`), and the three FormAnnotation-tag mutations (`POST/DELETE/PATCH .../tags`) — through a new `FormAnnotationService` backed by a new `FormAnnotationRepository`, committing directly onto the current `feature/rbac-step1-service-layer` branch (never touching `development`).

**Architecture:** Same layering as every shipped slice (Device/Patient/FormSchema/Study/Feature/Tag/Task/SubTask/ImageInstance): thin route (parse → build `ActingUser` for mutations → Service → `DTOConverter` → return), a Service with constructor-injected Repositories that raises domain exceptions and owns the commit, and framework-agnostic Repositories that take a `Session`. This is the **second slice of the spec's Phase 4** (after `instances.py` / 4a); `segmentations.py` (4c) is the last, a separate plan. `FormAnnotationService` reuses the existing `ImageInstanceRepository` (for `image_id`→instance resolution) and `TagRepository` (for the tag guard), both from earlier phases.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (ORM `eyened_orm`), pytest with the in-memory SQLite `session` fixture.

## Global Constraints

Copied verbatim from `docs/superpowers/specs/2026-07-03-repository-service-layer-design.md`. Every task implicitly includes these:

- **Filenames:** snake_case, one file per model module — `form_annotation_repository.py`, `form_annotation_service.py`.
- **Class names:** `FormAnnotationRepository` / `FormAnnotationService`.
- **Repositories** live in `orm/eyened_orm/repositories/`, take a `Session` as a method argument (never own/create sessions), have no FastAPI imports, and return `None`/empty on "not found" — never raise HTTP-shaped errors.
- **Services** live in `server/services/`, receive their Repositories via constructor injection, and raise the domain exceptions in `server/services/exceptions.py` — **never** raise `HTTPException` directly.
- **DTO conversion stays at the route boundary** (via `DTOConverter`), never inside a Service.
- **Package `__init__.py` files re-export** their public classes (with `__all__`), keeping all existing exports.
- **No mocking library.** DB-backed tests use the real in-memory SQLite `session` fixture (already exposed to `server/tests/` by `server/tests/conftest.py`). Any non-DB fake is a small hand-rolled object.
- **Do not touch:** CLI/worker code, `search.py`, `auth.py`, `import_api.py`, `Base`'s generic classmethods, or any pre-existing shipped slice (beyond the one additive `ImageInstanceRepository.get_by_public_id` method Task 1 appends).
- **Repository tests** → `orm/eyened_orm/tests/`; **Service tests** → `server/tests/`.

### Conventions reused from earlier phases

- **Commit ownership:** `get_db` (`server/db.py`) yields a session that is only *closed*, never committed, by its context manager. Every mutating Service method calls `session.commit()` itself — the Service is the transaction boundary. (The spec's deferred "transaction ownership" follow-up will revisit this layer-wide; do not change it here.)
- **Audit logging is injected, not global-reached.** The Service takes `logger: DatabaseModificationLogger | None = None` via its constructor and calls it inside the mutating method, guarded by `if self.logger is not None:`. The default factory wires the real logger via `get_db_logger()` (which returns `None` when DB logging is disabled); Service tests inject `None` or the small hand-rolled `FakeAuditLogger`.
- **Acting user:** routes map their handler-layer `CurrentUser` onto the framework-agnostic `ActingUser(id, username)` value object (`server/services/acting_user.py`, already exists) before calling a mutating Service method.
- **Lean test granularity:** thin `session.get(...)`/`.first()` wrappers get **no** dedicated Repository test — they are exercised through the Service tests. Every test carries a one-line docstring as its description.

> **Interpreter note:** no `python`/`pytest` on `PATH`; the venv is at `dev/.venv`. Every command uses `dev/.venv/bin/python` / `dev/.venv/bin/pytest`. The two commands that import `server.*` (app-boot / router-introspection checks) need dummy DB env vars, mirroring `server/tests/conftest.py`: prefix them with `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password`.

> **Reused from earlier work on `feature/rbac-step1-service-layer` (all already exist):** `NotFoundError` and `BadRequestError` (400) in `server/services/exceptions.py`, registered in `server/main.py` — the single handler dispatches every `ServiceError` subclass by MRO, so **this phase needs no `main.py` change**. `ActingUser`; `TagRepository.get_by_id`; `ImageInstanceRepository` (Task 1 only *appends* a `get_by_public_id` method); the `session` fixture in `server/tests/conftest.py`; both `repositories/`/`services/` packages with their `__init__.py` re-exports. **`form_annotations.router` is already registered** in `server/main.py` (`app_api.include_router(form_annotations.router)`, line 36), so no registration change is needed.

> **Existing facts confirmed for this plan** (verified against the route source and the ORM):
> - `FormAnnotation` (`orm/eyened_orm/form_annotation.py:44`): `FormAnnotationID` (int PK); NOT-NULL FKs `FormSchemaID`, `PatientID`, `CreatorID`; nullable FKs `StudyID`, `ImageInstanceID`, `SubTaskID`, `FormAnnotationReferenceID`; `Laterality` (nullable enum); `FormData` (nullable JSON); **`Inactive` (bool, default False)** — delete is a soft-delete (`Inactive = True`). Relationships: `FormSchema`, `Patient`, `Study`, `ImageInstance`, `Creator`, `SubTask`, `FormAnnotationTagLinks` (`lazy="selectin"`).
> - `FormAnnotationTagLink` (`orm/eyened_orm/tag.py:223`): **composite PK `(TagID, FormAnnotationID)`**; `CreatorID` (FK, NOT NULL); `Comment` (`String(256)`, nullable); `Tag`/`FormAnnotation` relationships, `Creator` (`lazy="selectin"`). So `session.get(FormAnnotationTagLink, {"TagID": ..., "FormAnnotationID": ...})` is the by-key lookup.
> - `Tag` (`orm/eyened_orm/tag.py:47`): `TagID` PK; `TagName`, `TagType` (`SAEnum(TagType)`), **`TagDescription` (NOT NULL)**, `CreatorID` (NOT NULL). `TagType` members include `FormAnnotation`.
> - A minimal `FormAnnotation` row FK-requires a `Project`→`Patient` chain, a `FormSchema` (`SchemaName` is `unique`), and a `Creator`. `Study`/`ImageInstance` are optional. The `_make_annotation` helper below builds exactly that minimal graph.
> - `FormSchema(SchemaName=...)`, `Project(ProjectName=..., External=ExternalEnum.N)`, `Patient(PatientIdentifier=..., ProjectID=...)`, `Creator(CreatorName=..., IsHuman=True)` are the minimal constructors (mirrors the helpers in `test_image_instance_service.py` / `test_task_repository.py`).

> **DTO facts confirmed:** `DTOConverter.form_annotation_to_get(annotation, with_tag_metadata=False)` and `DTOConverter.link_to_tag_metadata(link)` are the converters the route uses; both stay in the route. **The route calls `form_annotation_to_get(row)` with the default `with_tag_metadata=False` everywhere** — so `tags` is always `[]` in the response today; this plan preserves that call exactly. `FormAnnotationGET`/`FormAnnotationPUT`/`FormAnnotationPATCH`/`TagMeta`/`ObjectTagPOST`/`ObjectTagPATCH` DTOs are unchanged. `FormAnnotationPUT`/`FormAnnotationBase` fields are exactly: `form_schema_id, patient_id, study_id, image_id, laterality, sub_task_id, form_data, form_annotation_reference_id` — so `service.create(session, actor=..., **annotation.dict())` maps cleanly.

> **Behavior-preserving decisions (call out in review):**
> 1. **All inline `raise HTTPException(404/400)` move into the Service** as `NotFoundError` (404) / `BadRequestError` (400). Same wire status; the central handlers map them. The wrong-tag-type guard (`Tag.TagType != TagType.FormAnnotation`) becomes `BadRequestError`.
> 2. **The legacy `image_id`→`ImageInstanceID` resolver keeps its exact behavior.** `_resolve_image_instance_id` (plain `PublicID` equality, no PK/digit fallback, 404 when absent) is reproduced as a new `ImageInstanceRepository.get_by_public_id` (returns `None`) + a private Service helper that raises `NotFoundError`. This is intentionally *not* the fallback-carrying `get_full_graph_by_public_id`/`get_with_storage_by_public_id` — those have a `session.get(int/raw id)` fallback the legacy resolver never had.
> 3. **The PATCH `changes` audit dict keeps its pre-refactor formatting quirk verbatim** (pinned by a test, matching the 4a "pin the quirk" precedent). Today's route computes `changes = {k: f"{getattr(annotation, k, None)} -> {v}" for k, v in payload.items()}` where `k` is the **snake_case** DTO key, so `getattr(<ORM>, "form_schema_id", None)` is always `None` and every logged change reads `None -> <new>`. This is audit-log-only (not an API response), so this refactor preserves it exactly rather than silently changing observable behavior; a reviewer may file a separate fix.
> 4. **`PUT .../value` uses `log_simple`** (one-line high-frequency log), not `log_update`; `GET .../value` returns raw `FormData` (not a DTO). Both preserved.
> 5. **DTO conversion is unchanged** — the route keeps calling `form_annotation_to_get(row)` with `with_tag_metadata=False`, so the always-`[]` `tags` behavior is untouched. The list query's eager-load graph is moved verbatim into the Repository (behavior-preserving; harmless even though the default converter ignores it).

---

## Task 0 (git): Confirm the working branch and a green baseline

Not a code task. All new work stays on `feature/rbac-step1-service-layer`; `development` is never touched.

- [ ] **Step 1: Confirm the working branch**

```bash
git branch --show-current   # expect: feature/rbac-step1-service-layer
```

- [ ] **Step 2: Confirm the pre-existing suite is green before adding anything**

Run: `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/pytest -q`
Expected: the existing suite passes (baseline after 4a landed: **227 passed**). If the number differs, that count is your real baseline — proceed as long as it is green. **If anything is already red, stop and surface it — do not build on a red baseline.**

---

## Task 1: FormAnnotationRepository + `ImageInstanceRepository.get_by_public_id`

Create `FormAnnotationRepository` with the reads the `form_annotations.py` handlers perform inline today: the filtered active-list with its eager-load graph, the by-id read with tag links, a plain by-id `session.get`, and a composite-key tag-link lookup. Append one small `get_by_public_id` resolver to the existing `ImageInstanceRepository` (the faithful equivalent of the legacy `_resolve_image_instance_id`). Following precedent (lean granularity), the thin wrappers — `FormAnnotationRepository.get_by_id`, `.get_tag_link`, and `ImageInstanceRepository.get_by_public_id` — get **no** dedicated Repository test; they are exercised through the Task 2–4 Service tests. The two tests here cover the methods with real branching: the filtered/active list and the tag-link-loaded read. No method commits; the Service owns the transaction boundary.

**Files:**
- Create: `orm/eyened_orm/repositories/form_annotation_repository.py`
- Modify: `orm/eyened_orm/repositories/image_instance_repository.py` (append `get_by_public_id`)
- Modify: `orm/eyened_orm/repositories/__init__.py` (re-export `FormAnnotationRepository`)
- Test: `orm/eyened_orm/tests/test_form_annotation_repository.py`

**Interfaces:**
- Consumes: `eyened_orm` models `FormAnnotation`, `FormAnnotationTagLink`, `ImageInstance`, `ImageInstanceTagLink`, `Study`, `StudyTagLink`.
- Produces (all take `session: Session` first):
  - `FormAnnotationRepository.get_by_id(session, annotation_id: int) -> FormAnnotation | None` — thin `session.get`.
  - `FormAnnotationRepository.get_with_tag_links(session, annotation_id: int) -> FormAnnotation | None` — by id with `FormAnnotationTagLinks`→`Tag`/`Creator` eager-loaded.
  - `FormAnnotationRepository.list_active(session, *, patient_id: int | None = None, study_id: int | None = None, image_instance_id: int | None = None, form_schema_id: int | None = None, sub_task_id: int | None = None) -> list[FormAnnotation]` — `~Inactive`, filtered, with the list eager-load graph.
  - `FormAnnotationRepository.get_tag_link(session, tag_id: int, annotation_id: int) -> FormAnnotationTagLink | None` — thin composite-key `session.get`.
  - `ImageInstanceRepository.get_by_public_id(session, public_id: str) -> ImageInstance | None` — plain `PublicID` equality, no eager loads, no PK/digit fallback.

- [ ] **Step 1: Write the failing test**

Create `orm/eyened_orm/tests/test_form_annotation_repository.py`:

```python
from eyened_orm import Creator, FormAnnotation, FormSchema, Patient, Project
from eyened_orm.project import ExternalEnum
from eyened_orm.repositories.form_annotation_repository import (
    FormAnnotationRepository,
)


def _make_annotation(
    session,
    key: str,
    *,
    inactive: bool = False,
    study_id: int | None = None,
    image_instance_id: int | None = None,
) -> FormAnnotation:
    """Build the minimal FK graph a FormAnnotation requires; return the row."""
    project = Project(ProjectName=f"P-{key}", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier=f"ID-{key}", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    schema = FormSchema(SchemaName=f"S-{key}")
    session.add(schema)
    session.flush()
    creator = Creator(CreatorName=f"c-{key}", IsHuman=True)
    session.add(creator)
    session.flush()
    ann = FormAnnotation(
        FormSchemaID=schema.FormSchemaID,
        PatientID=patient.PatientID,
        CreatorID=creator.CreatorID,
        StudyID=study_id,
        ImageInstanceID=image_instance_id,
        Inactive=inactive,
        FormData={"k": "v"},
    )
    session.add(ann)
    session.flush()
    return ann


def test_list_active_excludes_inactive_and_filters_by_schema(session):
    """list_active drops Inactive rows and applies the form_schema_id filter."""
    keep = _make_annotation(session, "keep")
    _make_annotation(session, "gone", inactive=True)
    repo = FormAnnotationRepository()

    rows = repo.list_active(session)
    ids = {r.FormAnnotationID for r in rows}
    assert keep.FormAnnotationID in ids
    assert all(not r.Inactive for r in rows)

    by_schema = repo.list_active(session, form_schema_id=keep.FormSchemaID)
    assert [r.FormAnnotationID for r in by_schema] == [keep.FormAnnotationID]

    assert repo.list_active(session, form_schema_id=999_999) == []


def test_get_with_tag_links_found_and_missing(session):
    """get_with_tag_links returns the row (tag links loaded) or None if absent."""
    ann = _make_annotation(session, "one")
    repo = FormAnnotationRepository()

    got = repo.get_with_tag_links(session, ann.FormAnnotationID)
    assert got is not None and got.FormAnnotationID == ann.FormAnnotationID
    assert list(got.FormAnnotationTagLinks) == []  # eager-loaded, empty

    assert repo.get_with_tag_links(session, 999_999) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest orm/eyened_orm/tests/test_form_annotation_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eyened_orm.repositories.form_annotation_repository'`.

- [ ] **Step 3: Write the repository and append the resolver**

Create `orm/eyened_orm/repositories/form_annotation_repository.py`:

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from eyened_orm import (
    FormAnnotation,
    FormAnnotationTagLink,
    ImageInstance,
    ImageInstanceTagLink,
    Study,
    StudyTagLink,
)


class FormAnnotationRepository:
    """Data access for FormAnnotation reads and its Tag links."""

    def get_by_id(
        self, session: Session, annotation_id: int
    ) -> FormAnnotation | None:
        """Return the annotation by id, or None if absent."""
        return session.get(FormAnnotation, annotation_id)

    def get_with_tag_links(
        self, session: Session, annotation_id: int
    ) -> FormAnnotation | None:
        """Return the annotation by id with its tag links loaded, or None."""
        return session.get(
            FormAnnotation,
            annotation_id,
            options=(
                selectinload(
                    FormAnnotation.FormAnnotationTagLinks
                ).selectinload(FormAnnotationTagLink.Tag),
                selectinload(
                    FormAnnotation.FormAnnotationTagLinks
                ).selectinload(FormAnnotationTagLink.Creator),
            ),
        )

    def list_active(
        self,
        session: Session,
        *,
        patient_id: int | None = None,
        study_id: int | None = None,
        image_instance_id: int | None = None,
        form_schema_id: int | None = None,
        sub_task_id: int | None = None,
    ) -> list[FormAnnotation]:
        """Return active (``~Inactive``) annotations matching the given filters.

        Mirrors the eager-load graph the ``GET /form-annotations`` handler
        built inline. ``image_instance_id`` is already resolved from a
        PublicID by the Service; ``None`` filters are not applied.
        """
        query = (
            select(FormAnnotation)
            .filter(~FormAnnotation.Inactive)
            .options(
                selectinload(
                    FormAnnotation.FormAnnotationTagLinks
                ).selectinload(FormAnnotationTagLink.Tag),
                selectinload(
                    FormAnnotation.FormAnnotationTagLinks
                ).selectinload(FormAnnotationTagLink.Creator),
                selectinload(FormAnnotation.Study)
                .selectinload(Study.StudyTagLinks)
                .selectinload(StudyTagLink.Tag),
                selectinload(FormAnnotation.Study)
                .selectinload(Study.StudyTagLinks)
                .selectinload(StudyTagLink.Creator),
                selectinload(FormAnnotation.ImageInstance)
                .selectinload(ImageInstance.ImageInstanceTagLinks)
                .selectinload(ImageInstanceTagLink.Tag),
                selectinload(FormAnnotation.ImageInstance)
                .selectinload(ImageInstance.ImageInstanceTagLinks)
                .selectinload(ImageInstanceTagLink.Creator),
            )
        )
        if patient_id is not None:
            query = query.filter(FormAnnotation.PatientID == patient_id)
        if study_id is not None:
            query = query.filter(FormAnnotation.StudyID == study_id)
        if image_instance_id is not None:
            query = query.filter(
                FormAnnotation.ImageInstanceID == image_instance_id
            )
        if form_schema_id is not None:
            query = query.filter(FormAnnotation.FormSchemaID == form_schema_id)
        if sub_task_id is not None:
            query = query.filter(FormAnnotation.SubTaskID == sub_task_id)
        return list(session.scalars(query).all())

    def get_tag_link(
        self, session: Session, tag_id: int, annotation_id: int
    ) -> FormAnnotationTagLink | None:
        """Return the link for (tag_id, annotation_id), or None if absent."""
        return session.get(
            FormAnnotationTagLink,
            {"TagID": tag_id, "FormAnnotationID": annotation_id},
        )
```

Append `get_by_public_id` to the existing `ImageInstanceRepository` class in `orm/eyened_orm/repositories/image_instance_repository.py` (add it after the existing `get_tag_link` method; `select` is already imported at the top of that module):

```python
    def get_by_public_id(
        self, session: Session, public_id: str
    ) -> ImageInstance | None:
        """Return the instance with this PublicID (no eager loads), or None.

        Plain PublicID resolver used to map an external image id to its row —
        the faithful equivalent of the legacy ``_resolve_image_instance_id``
        helper (no PK/digit fallback, unlike ``get_full_graph_by_public_id``).
        """
        return session.scalars(
            select(ImageInstance).where(ImageInstance.PublicID == public_id)
        ).first()
```

Update `orm/eyened_orm/repositories/__init__.py` (add the import + `__all__` entry, keeping all existing exports):

```python
from .form_annotation_repository import FormAnnotationRepository
```

```python
    "FormAnnotationRepository",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest orm/eyened_orm/tests/test_form_annotation_repository.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add orm/eyened_orm/repositories/form_annotation_repository.py orm/eyened_orm/repositories/image_instance_repository.py orm/eyened_orm/repositories/__init__.py orm/eyened_orm/tests/test_form_annotation_repository.py
git commit -m "feat(repositories): add FormAnnotationRepository and ImageInstance PublicID resolver"
```

---

## Task 2: FormAnnotationService — reads (list, get, value)

Create `FormAnnotationService` with the three read paths: the filtered list (resolving an optional `image_id` first), the by-id read with tag links, and the raw `FormData` read. Missing rows translate to `NotFoundError` (→404); an `image_id` filter that resolves to nothing also raises `NotFoundError`, matching today's `_resolve_image_instance_id` 404. The constructor takes all three Repositories (`FormAnnotationRepository`, `ImageInstanceRepository`, `TagRepository` — the last two are needed by Tasks 3–4) plus the injected logger; the default factory wires them and the real logger.

**Files:**
- Create: `server/services/form_annotation_service.py`
- Modify: `server/services/__init__.py` (re-export `FormAnnotationService`)
- Test: `server/tests/test_form_annotation_service.py`

**Interfaces:**
- Consumes: `FormAnnotationRepository` (Task 1); `ImageInstanceRepository.get_by_public_id`, `TagRepository` (existing); `NotFoundError` (existing); `DatabaseModificationLogger`/`get_db_logger` (`server/utils/db_logging.py`); `eyened_orm.FormAnnotation`.
- Produces:
  - `FormAnnotationService(repository, image_repository, tag_repository, logger=None)`
  - `list_annotations(session, *, patient_id, study_id, image_id, form_schema_id, sub_task_id) -> list[FormAnnotation]` — resolves `image_id` (404 if given & unknown).
  - `get_annotation(session, annotation_id: int) -> FormAnnotation` — 404 if absent.
  - `get_value(session, annotation_id: int) -> Any` — returns `FormData`; 404 if absent.
  - `get_form_annotation_service() -> FormAnnotationService` — default-wiring factory.

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_form_annotation_service.py`:

```python
import pytest

from eyened_orm import (
    Creator,
    DeviceInstance,
    DeviceModel,
    FormAnnotation,
    FormSchema,
    ImageInstance,
    Patient,
    Project,
    Series,
    Study,
)
from eyened_orm.project import ExternalEnum
from eyened_orm.repositories.form_annotation_repository import (
    FormAnnotationRepository,
)
from eyened_orm.repositories.image_instance_repository import (
    ImageInstanceRepository,
)
from eyened_orm.repositories.tag_repository import TagRepository

from server.services.exceptions import NotFoundError
from server.services.form_annotation_service import FormAnnotationService


class FakeAuditLogger:
    """Records logging calls without touching the filesystem (no mock lib)."""

    def __init__(self) -> None:
        self.inserts: list[dict] = []
        self.updates: list[dict] = []
        self.deletes: list[dict] = []
        self.simples: list[dict] = []

    def log_insert(self, **kwargs) -> None:
        self.inserts.append(kwargs)

    def log_update(self, **kwargs) -> None:
        self.updates.append(kwargs)

    def log_delete(self, **kwargs) -> None:
        self.deletes.append(kwargs)

    def log_simple(self, **kwargs) -> None:
        self.simples.append(kwargs)


def _service(logger=None) -> FormAnnotationService:
    return FormAnnotationService(
        FormAnnotationRepository(),
        ImageInstanceRepository(),
        TagRepository(),
        logger=logger,
    )


def _make_patient_and_schema(session, key: str) -> tuple[int, int]:
    """Create a Project/Patient + FormSchema; return (patient_id, schema_id)."""
    project = Project(ProjectName=f"P-{key}", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier=f"ID-{key}", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    schema = FormSchema(SchemaName=f"S-{key}")
    session.add(schema)
    session.flush()
    return patient.PatientID, schema.FormSchemaID


def _make_annotation(session, key: str, *, inactive: bool = False) -> FormAnnotation:
    """Create a minimal active/inactive FormAnnotation; return the row."""
    patient_id, schema_id = _make_patient_and_schema(session, key)
    creator = Creator(CreatorName=f"c-{key}", IsHuman=True)
    session.add(creator)
    session.flush()
    ann = FormAnnotation(
        FormSchemaID=schema_id,
        PatientID=patient_id,
        CreatorID=creator.CreatorID,
        Inactive=inactive,
        FormData={"answer": 1},
    )
    session.add(ann)
    session.flush()
    return ann


def _make_image(session, public_id: str) -> int:
    """Build the minimal graph an ImageInstance FK-requires; return its id."""
    project = Project(ProjectName=f"IP-{public_id}", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier=f"IID-{public_id}", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    study = Study(PatientID=patient.PatientID)
    session.add(study)
    session.flush()
    series = Series(StudyID=study.StudyID)
    session.add(series)
    session.flush()
    model = DeviceModel(Manufacturer="Mf", ManufacturerModelName="M")
    session.add(model)
    session.flush()
    device = DeviceInstance(DeviceModelID=model.DeviceModelID, Description="d")
    session.add(device)
    session.flush()
    image = ImageInstance(
        PublicID=public_id,
        SeriesID=series.SeriesID,
        DeviceInstanceID=device.DeviceInstanceID,
        DatasetIdentifier=f"ds-{public_id}",
    )
    session.add(image)
    session.flush()
    return image.ImageInstanceID


def test_list_annotations_excludes_inactive(session):
    """list_annotations returns only active rows (no image_id filter)."""
    keep = _make_annotation(session, "keep")
    _make_annotation(session, "gone", inactive=True)
    session.commit()

    rows = _service().list_annotations(
        session,
        patient_id=None,
        study_id=None,
        image_id=None,
        form_schema_id=None,
        sub_task_id=None,
    )

    ids = {r.FormAnnotationID for r in rows}
    assert keep.FormAnnotationID in ids
    assert all(not r.Inactive for r in rows)


def test_list_annotations_unknown_image_id_raises_not_found(session):
    """An image_id filter that resolves to nothing raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().list_annotations(
            session,
            patient_id=None,
            study_id=None,
            image_id="no-such-image",
            form_schema_id=None,
            sub_task_id=None,
        )


def test_get_annotation_unknown_raises_not_found(session):
    """Getting a missing annotation is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().get_annotation(session, 999_999)


def test_get_value_returns_form_data(session):
    """get_value returns the annotation's FormData payload."""
    ann = _make_annotation(session, "val")
    session.commit()

    assert _service().get_value(session, ann.FormAnnotationID) == {"answer": 1}


def test_get_value_unknown_raises_not_found(session):
    """get_value on a missing annotation raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().get_value(session, 999_999)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest server/tests/test_form_annotation_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.services.form_annotation_service'`.

- [ ] **Step 3: Write the service**

Create `server/services/form_annotation_service.py`:

```python
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from eyened_orm import FormAnnotation
from eyened_orm.repositories.form_annotation_repository import (
    FormAnnotationRepository,
)
from eyened_orm.repositories.image_instance_repository import (
    ImageInstanceRepository,
)
from eyened_orm.repositories.tag_repository import TagRepository

from ..utils.db_logging import DatabaseModificationLogger, get_db_logger
from .exceptions import NotFoundError


class FormAnnotationService:
    """Business logic for FormAnnotation CRUD, values, and Tag links."""

    def __init__(
        self,
        repository: FormAnnotationRepository,
        image_repository: ImageInstanceRepository,
        tag_repository: TagRepository,
        logger: DatabaseModificationLogger | None = None,
    ) -> None:
        self.repository = repository
        self.images = image_repository
        self.tags = tag_repository
        self.logger = logger

    def _resolve_image_instance_id(
        self, session: Session, image_id: str | None
    ) -> int | None:
        """Map a PublicID to its ImageInstanceID (None passes through).

        Raises:
            NotFoundError: If a non-None image_id resolves to no instance.
        """
        if image_id is None:
            return None
        instance = self.images.get_by_public_id(session, image_id)
        if instance is None:
            raise NotFoundError("ImageInstance not found")
        return instance.ImageInstanceID

    def list_annotations(
        self,
        session: Session,
        *,
        patient_id: int | None,
        study_id: int | None,
        image_id: str | None,
        form_schema_id: int | None,
        sub_task_id: int | None,
    ) -> list[FormAnnotation]:
        """List active annotations matching the filters (resolving image_id).

        Raises:
            NotFoundError: If image_id is given but resolves to no instance.
        """
        image_instance_id = self._resolve_image_instance_id(session, image_id)
        return self.repository.list_active(
            session,
            patient_id=patient_id,
            study_id=study_id,
            image_instance_id=image_instance_id,
            form_schema_id=form_schema_id,
            sub_task_id=sub_task_id,
        )

    def get_annotation(
        self, session: Session, annotation_id: int
    ) -> FormAnnotation:
        """Return an annotation by id (with tag links loaded).

        Raises:
            NotFoundError: If the annotation does not exist.
        """
        item = self.repository.get_with_tag_links(session, annotation_id)
        if item is None:
            raise NotFoundError("FormAnnotation not found")
        return item

    def get_value(self, session: Session, annotation_id: int) -> Any:
        """Return an annotation's raw FormData payload.

        Raises:
            NotFoundError: If the annotation does not exist.
        """
        item = self.repository.get_by_id(session, annotation_id)
        if item is None:
            raise NotFoundError("FormAnnotation not found")
        return item.FormData


def get_form_annotation_service() -> FormAnnotationService:
    """Default FormAnnotationService wiring for FastAPI ``Depends()``."""
    return FormAnnotationService(
        FormAnnotationRepository(),
        ImageInstanceRepository(),
        TagRepository(),
        logger=get_db_logger(),
    )
```

Update `server/services/__init__.py` (add the import + `__all__` entry, keeping all existing exports):

```python
from .form_annotation_service import FormAnnotationService
```

```python
    "FormAnnotationService",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest server/tests/test_form_annotation_service.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add server/services/form_annotation_service.py server/services/__init__.py server/tests/test_form_annotation_service.py
git commit -m "feat(services): add FormAnnotationService reads (list, get, value)"
```

---

## Task 3: FormAnnotationService — CRUD mutations (create, update, soft-delete, set-value)

Add the four non-tag mutations. **create** resolves `image_id` (404 if unknown), inserts, commits, refreshes, and logs an insert; returns the new annotation. **update** loads the row (404), applies only the provided fields (`image_id` re-resolves; the field set mirrors the route's `exclude_unset` dict), commits, refreshes, and logs an update whose `changes` dict preserves the pre-refactor `None -> <new>` formatting quirk (decision #3). **soft_delete** loads the row (404), sets `Inactive = True`, commits, and logs a delete with the saved `deleted_data`. **set_value** loads the row (404), overwrites `FormData`, commits, and logs via `log_simple`.

**Files:**
- Modify: `server/services/form_annotation_service.py` (add four methods + `_FIELD_MAP`)
- Modify: `server/tests/test_form_annotation_service.py` (append CRUD tests + `_actor` helper)

**Interfaces:**
- Consumes: `FormAnnotationRepository.get_by_id` (Task 1); `ActingUser` (existing); `eyened_orm.FormAnnotation`.
- Produces (added to `FormAnnotationService`):
  - `create(session, *, form_schema_id, patient_id, study_id, image_id, laterality, sub_task_id, form_data, form_annotation_reference_id, actor: ActingUser) -> FormAnnotation` — 404 if `image_id` unknown.
  - `update(session, annotation_id: int, updates: dict[str, Any], actor: ActingUser) -> FormAnnotation` — 404 if annotation/`image_id` unknown; partial by `updates` keys.
  - `soft_delete(session, annotation_id: int, actor: ActingUser) -> None` — 404 if absent; sets `Inactive`.
  - `set_value(session, annotation_id: int, form_data: Any, actor: ActingUser) -> None` — 404 if absent.

- [ ] **Step 1: Write the failing test**

Append to `server/tests/test_form_annotation_service.py` (add `from server.services.acting_user import ActingUser` to the top-of-file imports alongside the existing imports):

```python
def _actor(session, key: str = "actor") -> ActingUser:
    creator = Creator(CreatorName=f"u-{key}", IsHuman=True)
    session.add(creator)
    session.flush()
    return ActingUser(id=creator.CreatorID, username=creator.CreatorName)


def test_create_resolves_image_and_logs_insert(session):
    """create resolves image_id, persists the row, and logs one insert."""
    actor = _actor(session)
    patient_id, schema_id = _make_patient_and_schema(session, "c1")
    image_id = _make_image(session, "img-1")
    session.commit()
    logger = FakeAuditLogger()

    ann = _service(logger).create(
        session,
        form_schema_id=schema_id,
        patient_id=patient_id,
        study_id=None,
        image_id="img-1",
        laterality=None,
        sub_task_id=None,
        form_data={"a": 1},
        form_annotation_reference_id=None,
        actor=actor,
    )

    assert ann.FormAnnotationID is not None
    assert ann.ImageInstanceID == image_id
    assert len(logger.inserts) == 1
    assert logger.inserts[0]["entity"] == "FormAnnotation"


def test_create_unknown_image_raises_not_found(session):
    """create with an unresolvable image_id raises NotFoundError (-> 404)."""
    actor = _actor(session)
    patient_id, schema_id = _make_patient_and_schema(session, "c2")
    session.commit()
    with pytest.raises(NotFoundError):
        _service().create(
            session,
            form_schema_id=schema_id,
            patient_id=patient_id,
            study_id=None,
            image_id="no-image",
            laterality=None,
            sub_task_id=None,
            form_data=None,
            form_annotation_reference_id=None,
            actor=actor,
        )


def test_update_applies_field_and_pins_changes_quirk(session):
    """update sets a provided field; the audit changes dict reads 'None -> ...'."""
    actor = _actor(session)
    ann = _make_annotation(session, "u1")
    session.commit()
    logger = FakeAuditLogger()

    updated = _service(logger).update(
        session, ann.FormAnnotationID, {"form_data": {"b": 2}}, actor
    )

    assert updated.FormData == {"b": 2}
    # Decision #3: pre-refactor quirk — snake_case getattr always yields None.
    assert logger.updates[0]["changes"]["form_data"].startswith("None -> ")


def test_update_unknown_raises_not_found(session):
    """update on a missing annotation raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().update(session, 999_999, {"form_data": {}}, _actor(session))


def test_soft_delete_sets_inactive(session):
    """soft_delete flags the row Inactive and logs one delete."""
    actor = _actor(session)
    ann = _make_annotation(session, "d1")
    session.commit()
    logger = FakeAuditLogger()

    _service(logger).soft_delete(session, ann.FormAnnotationID, actor)

    assert ann.Inactive is True
    assert len(logger.deletes) == 1


def test_soft_delete_unknown_raises_not_found(session):
    """soft_delete on a missing annotation raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().soft_delete(session, 999_999, _actor(session))


def test_set_value_overwrites_form_data_and_logs_simple(session):
    """set_value overwrites FormData and emits one log_simple record."""
    actor = _actor(session)
    ann = _make_annotation(session, "v1")
    session.commit()
    logger = FakeAuditLogger()

    _service(logger).set_value(session, ann.FormAnnotationID, {"new": 9}, actor)

    assert ann.FormData == {"new": 9}
    assert len(logger.simples) == 1


def test_set_value_unknown_raises_not_found(session):
    """set_value on a missing annotation raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().set_value(session, 999_999, {}, _actor(session))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest server/tests/test_form_annotation_service.py -v`
Expected: FAIL — `AttributeError: 'FormAnnotationService' object has no attribute 'create'`.

- [ ] **Step 3: Add the four methods**

Add a module-level `_FIELD_MAP` (below the imports, above the class) mapping the DTO snake_case update keys to ORM attributes, and add the four methods to `FormAnnotationService` (after `get_value`, before the module-level factory). Also extend the top-of-file import line to include `ActingUser`:

```python
# add to the existing "from .exceptions import NotFoundError" area:
from .acting_user import ActingUser
```

```python
# module-level, below imports and above the class:
_FIELD_MAP = {
    "form_schema_id": "FormSchemaID",
    "patient_id": "PatientID",
    "study_id": "StudyID",
    "laterality": "Laterality",
    "sub_task_id": "SubTaskID",
    "form_data": "FormData",
    "form_annotation_reference_id": "FormAnnotationReferenceID",
}
```

```python
    def create(
        self,
        session: Session,
        *,
        form_schema_id: int,
        patient_id: int,
        study_id: int | None,
        image_id: str | None,
        laterality: Any,
        sub_task_id: int | None,
        form_data: Any,
        form_annotation_reference_id: int | None,
        actor: ActingUser,
    ) -> FormAnnotation:
        """Create a FormAnnotation owned by the acting user.

        Raises:
            NotFoundError: If image_id is given but resolves to no instance.
        """
        image_instance_id = self._resolve_image_instance_id(session, image_id)
        annotation = FormAnnotation(
            FormSchemaID=form_schema_id,
            PatientID=patient_id,
            StudyID=study_id,
            ImageInstanceID=image_instance_id,
            Laterality=laterality,
            CreatorID=actor.id,
            SubTaskID=sub_task_id,
            FormData=form_data,
            FormAnnotationReferenceID=form_annotation_reference_id,
        )
        session.add(annotation)
        session.commit()
        session.refresh(annotation)
        if self.logger is not None:
            self.logger.log_insert(
                user=actor.username,
                user_id=actor.id,
                endpoint="POST /api/form-annotations",
                entity="FormAnnotation",
                entity_id=annotation.FormAnnotationID,
                fields={
                    "form_schema_id": annotation.FormSchemaID,
                    "patient_id": annotation.PatientID,
                    "study_id": annotation.StudyID,
                    "image_instance_id": annotation.ImageInstanceID,
                    "sub_task_id": annotation.SubTaskID,
                },
            )
        return annotation

    def update(
        self,
        session: Session,
        annotation_id: int,
        updates: dict[str, Any],
        actor: ActingUser,
    ) -> FormAnnotation:
        """Apply the provided (snake_case-keyed) fields to an annotation.

        ``updates`` carries only the fields the client set (the route's
        ``exclude_unset`` dict); ``image_id`` is re-resolved to an
        ImageInstanceID.

        Raises:
            NotFoundError: If the annotation, or a given image_id, is unknown.
        """
        annotation = self.repository.get_by_id(session, annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")

        if "image_id" in updates:
            annotation.ImageInstanceID = self._resolve_image_instance_id(
                session, updates["image_id"]
            )
        for key, attr in _FIELD_MAP.items():
            if key in updates:
                setattr(annotation, attr, updates[key])

        session.commit()
        session.refresh(annotation)
        if self.logger is not None:
            # Decision #3: preserve the pre-refactor audit formatting quirk —
            # snake_case getattr on the ORM object always yields None, so every
            # logged change reads "None -> <new>". Behavior-preserving on
            # purpose; not an API response. A reviewer may fix separately.
            changes = {
                key: f"{getattr(annotation, key, None)} -> {value}"
                for key, value in updates.items()
            }
            self.logger.log_update(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"PATCH /api/form-annotations/{annotation_id}",
                entity="FormAnnotation",
                entity_id=annotation_id,
                changes=changes if changes else None,
            )
        return annotation

    def soft_delete(
        self, session: Session, annotation_id: int, actor: ActingUser
    ) -> None:
        """Soft-delete an annotation (sets Inactive; row is kept).

        Raises:
            NotFoundError: If the annotation does not exist.
        """
        annotation = self.repository.get_by_id(session, annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")

        deleted_data = {
            "form_schema_id": annotation.FormSchemaID,
            "patient_id": annotation.PatientID,
            "study_id": annotation.StudyID,
            "image_instance_id": annotation.ImageInstanceID,
            "sub_task_id": annotation.SubTaskID,
            "laterality": annotation.Laterality,
            "creator_id": annotation.CreatorID,
        }
        annotation.Inactive = True
        session.commit()
        if self.logger is not None:
            self.logger.log_delete(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"DELETE /api/form-annotations/{annotation_id}",
                entity="FormAnnotation",
                entity_id=annotation_id,
                deleted_data=deleted_data,
            )
        return None

    def set_value(
        self,
        session: Session,
        annotation_id: int,
        form_data: Any,
        actor: ActingUser,
    ) -> None:
        """Overwrite an annotation's FormData payload (high-frequency op).

        Raises:
            NotFoundError: If the annotation does not exist.
        """
        annotation = self.repository.get_by_id(session, annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")

        annotation.FormData = form_data
        session.commit()
        if self.logger is not None:
            self.logger.log_simple(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"PUT /api/form-annotations/{annotation_id}/value",
                operation="UPDATE",
                entity="FormAnnotation",
                entity_id=annotation_id,
            )
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest server/tests/test_form_annotation_service.py -v`
Expected: PASS (13 passed — the 5 from Task 2 plus these 8).

- [ ] **Step 5: Commit**

```bash
git add server/services/form_annotation_service.py server/tests/test_form_annotation_service.py
git commit -m "feat(services): add FormAnnotationService CRUD and value mutations"
```

---

## Task 4: FormAnnotationService — tag add/patch/remove

Add the three tag mutations, preserving today's lookup order and failure paths: **tag** resolves the annotation (404), the tag (404), checks the tag type is `FormAnnotation` (400 → `BadRequestError`), then creates the link (or updates its comment when re-tagged with a comment). **patch_tag** resolves annotation (404), tag (404), type (400), then the link (404), and overwrites the comment if provided. **untag** resolves the annotation (404) then deletes the link if present (idempotent — no error when absent). `tag`/`patch_tag` return the `FormAnnotationTagLink` with `.Tag` set (to avoid a lazy-load at DTO time); `untag` returns `None`.

**Files:**
- Modify: `server/services/form_annotation_service.py` (add three methods)
- Modify: `server/tests/test_form_annotation_service.py` (append tag tests + a `_make_tag` helper)

**Interfaces:**
- Consumes: `FormAnnotationRepository.get_by_id`, `.get_tag_link` (Task 1); `TagRepository.get_by_id` (existing); `ActingUser`, `BadRequestError` (existing); `eyened_orm.FormAnnotationTagLink`; `eyened_orm.tag.TagType`.
- Produces (added to `FormAnnotationService`):
  - `tag(session, annotation_id: int, tag_id: int, comment: str | None, actor: ActingUser) -> FormAnnotationTagLink` — create-or-update-comment; 404 annotation/tag, 400 wrong type.
  - `patch_tag(session, annotation_id: int, tag_id: int, comment: str | None, actor: ActingUser) -> FormAnnotationTagLink` — 404 annotation/tag/link, 400 wrong type.
  - `untag(session, annotation_id: int, tag_id: int, actor: ActingUser) -> None` — 404 annotation; idempotent delete.

- [ ] **Step 1: Write the failing test**

Append to `server/tests/test_form_annotation_service.py` (add `from eyened_orm import Tag` — extend the existing `eyened_orm` import block — and `from eyened_orm.tag import TagType`, `from server.services.exceptions import BadRequestError` at the top of the file):

```python
def _make_tag(session, creator_id: int, tag_type: TagType = TagType.FormAnnotation) -> Tag:
    tag = Tag(
        TagName=f"t-{tag_type.name}-{creator_id}",
        TagDescription="d",
        TagType=tag_type,
        CreatorID=creator_id,
    )
    session.add(tag)
    session.flush()
    return tag


def test_tag_creates_link_and_logs(session):
    """tag links a FormAnnotation tag, returns the link, and logs one insert."""
    actor = _actor(session)
    ann = _make_annotation(session, "t1")
    tag = _make_tag(session, actor.id)
    session.commit()
    logger = FakeAuditLogger()

    link = _service(logger).tag(
        session, ann.FormAnnotationID, tag.TagID, "hi", actor
    )

    assert link.TagID == tag.TagID
    assert link.Comment == "hi"
    assert link.Tag.TagID == tag.TagID
    assert len(logger.inserts) == 1
    assert logger.inserts[0]["entity"] == "FormAnnotationTagLink"


def test_tag_unknown_annotation_raises_not_found(session):
    """tag on a missing annotation is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    session.commit()
    with pytest.raises(NotFoundError):
        _service().tag(session, 999_999, tag.TagID, None, actor)


def test_tag_unknown_tag_raises_not_found(session):
    """tag with an unknown tag id is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t2")
    session.commit()
    with pytest.raises(NotFoundError):
        _service().tag(session, ann.FormAnnotationID, 999_999, None, actor)


def test_tag_wrong_type_raises_bad_request(session):
    """tag with a non-FormAnnotation tag raises BadRequestError (-> 400)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t3")
    tag = _make_tag(session, actor.id, tag_type=TagType.ImageInstance)
    session.commit()
    with pytest.raises(BadRequestError):
        _service().tag(session, ann.FormAnnotationID, tag.TagID, None, actor)


def test_tag_existing_updates_comment(session):
    """A second tag with a comment updates the existing link, not duplicates."""
    actor = _actor(session)
    ann = _make_annotation(session, "t4")
    tag = _make_tag(session, actor.id)
    session.commit()
    service = _service()

    service.tag(session, ann.FormAnnotationID, tag.TagID, "first", actor)
    link = service.tag(session, ann.FormAnnotationID, tag.TagID, "second", actor)

    assert link.Comment == "second"


def test_patch_tag_updates_comment(session):
    """patch_tag overwrites the comment on an existing link."""
    actor = _actor(session)
    ann = _make_annotation(session, "t5")
    tag = _make_tag(session, actor.id)
    session.commit()
    service = _service()
    service.tag(session, ann.FormAnnotationID, tag.TagID, "old", actor)

    link = service.patch_tag(session, ann.FormAnnotationID, tag.TagID, "new", actor)

    assert link.Comment == "new"


def test_patch_tag_unknown_link_raises_not_found(session):
    """patch_tag with no existing link raises NotFoundError (-> 404)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t6")
    tag = _make_tag(session, actor.id)
    session.commit()
    with pytest.raises(NotFoundError):
        _service().patch_tag(session, ann.FormAnnotationID, tag.TagID, "x", actor)


def test_untag_removes_link(session):
    """untag deletes the link for that (annotation, tag)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t7")
    tag = _make_tag(session, actor.id)
    session.commit()
    service = _service()
    service.tag(session, ann.FormAnnotationID, tag.TagID, None, actor)

    service.untag(session, ann.FormAnnotationID, tag.TagID, actor)

    assert (
        FormAnnotationRepository().get_tag_link(
            session, tag.TagID, ann.FormAnnotationID
        )
        is None
    )


def test_untag_absent_link_is_idempotent(session):
    """untag with no link present is a no-op (no error)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t8")
    tag = _make_tag(session, actor.id)
    session.commit()

    # Does not raise even though no link exists.
    _service().untag(session, ann.FormAnnotationID, tag.TagID, actor)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest server/tests/test_form_annotation_service.py -v`
Expected: FAIL — `AttributeError: 'FormAnnotationService' object has no attribute 'tag'`.

- [ ] **Step 3: Add the three methods**

Extend the service module imports (add `FormAnnotationTagLink` to the `eyened_orm` import, add `TagType` and `BadRequestError`), then add the methods to `FormAnnotationService` (after `set_value`, before the module-level factory):

```python
# extend the existing eyened_orm import:
from eyened_orm import FormAnnotation, FormAnnotationTagLink
from eyened_orm.tag import TagType
```

```python
# extend the exceptions import:
from .exceptions import BadRequestError, NotFoundError
```

```python
    def tag(
        self,
        session: Session,
        annotation_id: int,
        tag_id: int,
        comment: str | None,
        actor: ActingUser,
    ) -> FormAnnotationTagLink:
        """Attach a Tag to an annotation (idempotent; updates comment if re-tagged).

        Raises:
            NotFoundError: If the annotation or the tag does not exist.
            BadRequestError: If the tag is not a FormAnnotation-type tag.
        """
        annotation = self.repository.get_by_id(session, annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")
        tag = self.tags.get_by_id(session, tag_id)
        if tag is None:
            raise NotFoundError("Tag not found")
        if tag.TagType != TagType.FormAnnotation:
            raise BadRequestError("Tag type must be FormAnnotation")

        link = self.repository.get_tag_link(session, tag.TagID, annotation_id)
        if link is None:
            link = FormAnnotationTagLink(
                TagID=tag.TagID,
                FormAnnotationID=annotation_id,
                CreatorID=actor.id,
                Comment=comment,
            )
            session.add(link)
            session.commit()
            session.refresh(link)
            if self.logger is not None:
                self.logger.log_insert(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=f"POST /api/form-annotations/{annotation_id}/tags",
                    entity="FormAnnotationTagLink",
                    fields={
                        "tag_id": tag.TagID,
                        "form_annotation_id": annotation_id,
                        "comment": comment,
                    },
                )
        elif comment is not None:
            old_comment = link.Comment
            link.Comment = comment
            session.commit()
            session.refresh(link)
            if self.logger is not None:
                self.logger.log_update(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=f"POST /api/form-annotations/{annotation_id}/tags",
                    entity="FormAnnotationTagLink",
                    fields={
                        "tag_id": tag.TagID,
                        "form_annotation_id": annotation_id,
                    },
                    changes={"comment": f"{old_comment} -> {comment}"},
                )

        link.Tag = tag  # avoid a Tag lazy-load at DTO time
        return link

    def patch_tag(
        self,
        session: Session,
        annotation_id: int,
        tag_id: int,
        comment: str | None,
        actor: ActingUser,
    ) -> FormAnnotationTagLink:
        """Update the comment on an existing annotation tag link.

        Raises:
            NotFoundError: If the annotation, tag, or link does not exist.
            BadRequestError: If the tag is not a FormAnnotation-type tag.
        """
        annotation = self.repository.get_by_id(session, annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")
        tag = self.tags.get_by_id(session, tag_id)
        if tag is None:
            raise NotFoundError("Tag not found")
        if tag.TagType != TagType.FormAnnotation:
            raise BadRequestError("Tag type must be FormAnnotation")

        link = self.repository.get_tag_link(session, tag_id, annotation_id)
        if link is None:
            raise NotFoundError("Link not found")

        if comment is not None:
            old_comment = link.Comment
            link.Comment = comment
            session.commit()
            session.refresh(link)
            if self.logger is not None:
                self.logger.log_update(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=(
                        f"PATCH /api/form-annotations/{annotation_id}"
                        f"/tags/{tag_id}"
                    ),
                    entity="FormAnnotationTagLink",
                    fields={
                        "tag_id": tag_id,
                        "form_annotation_id": annotation_id,
                    },
                    changes={"comment": f"{old_comment} -> {comment}"},
                )

        link.Tag = tag
        return link

    def untag(
        self, session: Session, annotation_id: int, tag_id: int, actor: ActingUser
    ) -> None:
        """Remove a Tag from an annotation (idempotent; no error if not linked).

        Raises:
            NotFoundError: If the annotation does not exist.
        """
        annotation = self.repository.get_by_id(session, annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")

        link = self.repository.get_tag_link(session, tag_id, annotation_id)
        if link is not None:
            deleted_data = {
                "tag_id": tag_id,
                "form_annotation_id": annotation_id,
                "comment": link.Comment,
                "creator_id": link.CreatorID,
            }
            session.delete(link)
            session.commit()
            if self.logger is not None:
                self.logger.log_delete(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=(
                        f"DELETE /api/form-annotations/{annotation_id}"
                        f"/tags/{tag_id}"
                    ),
                    entity="FormAnnotationTagLink",
                    fields={"tag_id": tag_id, "form_annotation_id": annotation_id},
                    deleted_data=deleted_data,
                )
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest server/tests/test_form_annotation_service.py -v`
Expected: PASS (22 passed — the 13 from Tasks 2–3 plus these 9).

- [ ] **Step 5: Commit**

```bash
git add server/services/form_annotation_service.py server/tests/test_form_annotation_service.py
git commit -m "feat(services): add FormAnnotationService tag add/patch/remove"
```

---

## Task 5: Route `form_annotations.py` through `FormAnnotationService`

Rewrite every DB-touching handler to be thin: parse → build `ActingUser` (mutations only) → call `FormAnnotationService` → `DTOConverter` → return. No handler contains inline queries, the `_resolve_image_instance_id` helper, `raise HTTPException` for not-found/wrong-type, `session.commit`, or direct `get_db_logger()` calls anymore — those move into the Service; the central `NotFoundError`/`BadRequestError` handlers (already registered) map the 404s/400s. DTO conversion stays at the boundary and keeps its exact `form_annotation_to_get(row)` call (default `with_tag_metadata=False`). Verified by the full suite still passing and an app-boot smoke check — matching how the earlier route slices were verified (no route-level test files exist for these slices).

**Files:**
- Modify: `server/routes/form_annotations.py` (rewrite the whole module)

**Interfaces:**
- Consumes: `FormAnnotationService`, `get_form_annotation_service` (Tasks 2–4); `ActingUser` (existing); `DTOConverter` (existing).
- Produces: no new symbols — this is the HTTP boundary.

- [ ] **Step 1: Rewrite the route module**

Replace the entire contents of `server/routes/form_annotations.py` with:

```python
from typing import List, Optional

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_aux import ObjectTagPATCH, ObjectTagPOST, TagMeta
from ..dtos.dtos_main import (
    FormAnnotationGET,
    FormAnnotationPATCH,
    FormAnnotationPUT,
)
from ..services.acting_user import ActingUser
from ..services.form_annotation_service import (
    FormAnnotationService,
    get_form_annotation_service,
)
from .auth import CurrentUser, get_current_user

router = APIRouter()


@router.post("/form-annotations", response_model=FormAnnotationGET)
async def create_form_annotation(
    annotation: FormAnnotationPUT,
    db: Session = Depends(get_db),
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a form annotation."""
    item = service.create(
        db,
        actor=ActingUser(id=current_user.id, username=current_user.username),
        **annotation.dict(),
    )
    return DTOConverter.form_annotation_to_get(item)


@router.get("/form-annotations", response_model=List[FormAnnotationGET])
async def get_form_annotations(
    patient_id: Optional[int] = None,
    study_id: Optional[int] = None,
    image_id: Optional[str] = None,
    form_schema_id: Optional[int] = None,
    sub_task_id: Optional[int] = None,
    db: Session = Depends(get_db),
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List active form annotations, optionally filtered."""
    rows = service.list_annotations(
        db,
        patient_id=patient_id,
        study_id=study_id,
        image_id=image_id,
        form_schema_id=form_schema_id,
        sub_task_id=sub_task_id,
    )
    return [DTOConverter.form_annotation_to_get(row) for row in rows]


@router.get("/form-annotations/{annotation_id}", response_model=FormAnnotationGET)
async def get_form_annotation(
    annotation_id: int,
    db: Session = Depends(get_db),
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single form annotation by id."""
    item = service.get_annotation(db, annotation_id)
    return DTOConverter.form_annotation_to_get(item)


@router.patch("/form-annotations/{annotation_id}", response_model=FormAnnotationGET)
async def update_form_annotation(
    annotation_id: int,
    annotation: FormAnnotationPATCH,
    db: Session = Depends(get_db),
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Partially update a form annotation."""
    item = service.update(
        db,
        annotation_id,
        annotation.dict(exclude_unset=True),
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.form_annotation_to_get(item)


@router.delete("/form-annotations/{annotation_id}", status_code=204)
async def delete_form_annotation(
    annotation_id: int,
    db: Session = Depends(get_db),
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Soft-delete a form annotation."""
    service.soft_delete(
        db,
        annotation_id,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return Response(status_code=204)


@router.get("/form-annotations/{form_annotation_id}/value")
async def get_form_annotation_value(
    form_annotation_id: int,
    db: Session = Depends(get_db),
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a form annotation's raw FormData payload."""
    return service.get_value(db, form_annotation_id)


@router.put("/form-annotations/{form_annotation_id}/value", status_code=204)
async def update_form_annotation_value(
    form_annotation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Overwrite a form annotation's FormData payload."""
    form_data = await request.json()
    service.set_value(
        db,
        form_annotation_id,
        form_data,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return Response(status_code=204)


@router.post("/form-annotations/{annotation_id}/tags", response_model=TagMeta)
async def tag_form_annotation(
    annotation_id: int,
    body: ObjectTagPOST,
    db: Session = Depends(get_db),
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> TagMeta:
    """Attach a Tag to a FormAnnotation by tag ID (idempotent)."""
    link = service.tag(
        db,
        annotation_id,
        body.tag_id,
        body.comment,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.link_to_tag_metadata(link)


@router.delete("/form-annotations/{annotation_id}/tags/{tag_id}", status_code=204)
async def untag_form_annotation(
    annotation_id: int,
    tag_id: int,
    db: Session = Depends(get_db),
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Remove a Tag from a FormAnnotation (idempotent)."""
    service.untag(
        db,
        annotation_id,
        tag_id,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return Response(status_code=204)


@router.patch(
    "/form-annotations/{annotation_id}/tags/{tag_id}", response_model=TagMeta
)
async def patch_form_annotation_tag(
    annotation_id: int,
    tag_id: int,
    body: ObjectTagPATCH,
    db: Session = Depends(get_db),
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> TagMeta:
    """Update comment on an existing FormAnnotation tag link."""
    link = service.patch_tag(
        db,
        annotation_id,
        tag_id,
        body.comment,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.link_to_tag_metadata(link)
```

- [ ] **Step 2: App-boot smoke check (imports + routes register)**

> **Note:** the routers are mounted as a sub-app (`server/main.py` does `app.mount("/api", app_api)`), so the route paths live on **`app_api.routes`** and carry **no** `/api` prefix. Introspect `app_api`, not `app`.

Run:

```bash
EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password \
  dev/.venv/bin/python -c "
from server.main import app_api
paths = {r.path for r in app_api.routes}
for p in [
    '/form-annotations',
    '/form-annotations/{annotation_id}',
    '/form-annotations/{form_annotation_id}/value',
    '/form-annotations/{annotation_id}/tags',
    '/form-annotations/{annotation_id}/tags/{tag_id}',
]:
    assert p in paths, (p, sorted(x for x in paths if 'form-annotation' in x))
print('form-annotation routes OK')
"
```

Expected: prints `form-annotation routes OK` (the app imports cleanly and every route is registered on the mounted `/api` sub-app).

- [ ] **Step 3: Run the full suite to confirm no regression**

Run: `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/pytest -q`
Expected: PASS — **251 passed** (227 baseline + 2 repository tests from Task 1 + 22 service tests from Tasks 2–4), no failures. (If your Task 0 baseline differed, the total is that baseline + 24.)

- [ ] **Step 4: Commit**

```bash
git add server/routes/form_annotations.py
git commit -m "refactor(routes): route form-annotation endpoints through FormAnnotationService"
```

---

## Phase 4b done — second slice of spec Phase 4

After Task 5, `form_annotations.py` no longer queries the ORM directly: it parses, calls `FormAnnotationService`, and converts DTOs. Do **not** merge `feature/rbac-step1-service-layer` to `development`; the last slice is spec **Phase 4c** (`segmentations.py`), a separate plan — it can reuse the `ImageInstanceRepository` resolvers and the `TagRepository` guard established here.

Update the `rbac-step1-migration-state` memory: form_annotations (4b) done; Phase 4c (`segmentations.py`) is the only remaining slice; test count **251**.
```
