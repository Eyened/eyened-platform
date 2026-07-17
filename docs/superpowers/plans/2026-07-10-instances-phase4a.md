# instances Repository/Service Migration (RBAC Step 1, Phase 4a) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route the `instances.py` endpoints — the two `ImageInstance` graph reads (`GET /instances/{id}`, `GET /images/{public_id}`), the storage-redirect reads (`GET /images/{id}/data`, `/thumbnail`), and the three instance-tag mutations (`POST/PATCH/DELETE /instances/{id}/tags[/{tag_id}]`) — through a new `ImageInstanceService` backed by a new `ImageInstanceRepository`, committing directly onto the current `feature/rbac-step1-service-layer` branch (never touching `development`).

**Architecture:** Same layering as the shipped Device/Patient/FormSchema/Study/Feature/Tag/Task/SubTask slices — thin route (parse → build `ActingUser` → Service → `DTOConverter` → return), a Service with constructor-injected Repositories that raises domain exceptions and owns the commit, and a framework-agnostic Repository that takes a `Session`. This is the **first slice of the spec's Phase 4** (the largest, most complex phase); `form_annotations.py` (4b) and `segmentations.py` (4c) follow as their own plans. `ImageInstanceRepository` created here (with `PublicID`→instance resolution) is reused by 4b/4c.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (ORM `eyened_orm`), pytest with the in-memory SQLite `session` fixture.

## Global Constraints

Copied verbatim from `docs/superpowers/specs/2026-07-03-repository-service-layer-design.md`. Every task implicitly includes these:

- **Filenames:** snake_case, one file per model module — `image_instance_repository.py`, `image_instance_service.py`.
- **Class names:** `ImageInstanceRepository` / `ImageInstanceService`.
- **Repositories** live in `orm/eyened_orm/repositories/`, take a `Session` as a method argument (never own/create sessions), have no FastAPI imports, and return `None`/empty on "not found" — never raise HTTP-shaped errors.
- **Services** live in `server/services/`, receive their Repositories via constructor injection, and raise the domain exceptions in `server/services/exceptions.py` — **never** raise `HTTPException` directly.
- **DTO conversion stays at the route boundary** (via `DTOConverter`), never inside a Service.
- **Package `__init__.py` files re-export** their public classes (with `__all__`), keeping all existing exports.
- **No mocking library.** DB-backed tests use the real in-memory SQLite `session` fixture (already exposed to `server/tests/` by `server/tests/conftest.py`). Any non-DB fake is a small hand-rolled object.
- **Do not touch:** CLI/worker code, `search.py`, `auth.py`, `import_api.py`, `Base`'s generic classmethods, or any pre-existing shipped slice.
- **Repository tests** → `orm/eyened_orm/tests/`; **Service tests** → `server/tests/`.

### Conventions reused from earlier phases

- **Commit ownership:** `get_db` (`server/db.py`) yields a session that is only *closed*, never committed, by its context manager. Every mutating Service method calls `session.commit()` itself — the Service is the transaction boundary. (The spec's deferred "transaction ownership" follow-up will revisit this layer-wide; do not change it here.)
- **Audit logging is injected, not global-reached.** The Service takes `logger: DatabaseModificationLogger | None = None` via its constructor and calls it inside the mutating method, guarded by `if self.logger is not None:`. The default factory wires the real logger via `get_db_logger()` (which returns `None` when DB logging is disabled); Service tests inject `None` or a small hand-rolled fake.
- **Acting user:** routes map their handler-layer `CurrentUser` onto the framework-agnostic `ActingUser(id, username)` value object (`server/services/acting_user.py`, already exists) before calling a mutating Service method.
- **Lean test granularity:** thin `session.get(...)` wrappers get **no** dedicated Repository test — they are exercised through the Service tests. Every test carries a one-line docstring as its description.

> **Interpreter note:** no `python`/`pytest` on `PATH`; the venv is at `dev/.venv`. Every command uses `dev/.venv/bin/python` / `dev/.venv/bin/pytest`. The two commands that import `server.*` (app-boot / router-introspection checks) need dummy DB env vars, mirroring `server/tests/conftest.py`: prefix them with `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password`.

> **Reused from earlier work on `feature/rbac-step1-service-layer`:** `NotFoundError` **and `BadRequestError`** (400) already exist in `server/services/exceptions.py`, registered in `server/main.py` via `register_exception_handlers` — the single handler dispatches every `ServiceError` subclass by MRO, so **this phase needs no `main.py` change**. `ActingUser`, `TagRepository` (`get_by_id`), the `session` fixture in `server/tests/conftest.py`, and both `repositories/`/`services/` packages with their `__init__.py` re-exports all already exist. **`instances.router` is already registered** in `server/main.py` (`app_api.include_router(instances.router)`), so no registration change is needed.

> **Existing facts confirmed for this plan** (verified against the route source and the ORM):
> - `ImageInstance` (`orm/eyened_orm/image_instance.py:187`): `ImageInstanceID` (int PK); `PublicID` (`str`, the external id the API resolves, `_name_column`); relationships `Series`→`Study`→`Patient`→`Project`, `DeviceInstance`→`DeviceModel`, `Scan` (nullable), `ImageStorages`→`StorageBackend`, `ImageInstanceTagLinks`, `Segmentations`, `FormAnnotations`, `ModelSegmentations`.
> - `ImageInstanceTagLink` (`orm/eyened_orm/tag.py:135`): **composite PK `(TagID, ImageInstanceID)`**, both FKs `ondelete="CASCADE"`; `CreatorID` (FK, NOT NULL); `Comment` (`String(256)`, nullable); `Tag`/`ImageInstance` relationships, `Creator` (`lazy="selectin"`). So `session.get(ImageInstanceTagLink, {"TagID": ..., "ImageInstanceID": ...})` is the by-key lookup.
> - `Tag` (`orm/eyened_orm/tag.py:46`): `TagID` (PK); `TagName`, `TagType` (`SAEnum(TagType)`), **`TagDescription` (NOT NULL)**, `CreatorID` (NOT NULL). `TagType` members include `ImageInstance`, `Segmentation`, `FormAnnotation`.
> - A real `ImageInstance` row FK-requires a `Series`→`Study`→`Patient`→`Project` chain **and** a `DeviceInstance`→`DeviceModel`. The `_make_image` helper below builds exactly that minimal graph (mirrors the one added to `test_task_repository.py` in phase 3).

> **DTO facts confirmed:** `DTOConverter.image_instance_to_get(item, with_tag_metadata=, with_segmentations=, with_form_annotations=, with_model_segmentations=)` and `DTOConverter.link_to_tag_metadata(link)` are the two converters the route uses; both stay in the route. `ImageGET`/`TagMeta`/`ObjectTagPOST`/`ObjectTagPATCH` DTOs are unchanged.

> **Behavior-preserving decisions (call out in review):**
> 1. **The wrong-tag-type check (`Tag.TagType != TagType.ImageInstance`) becomes a `BadRequestError` (400)** in the Service instead of an inline `HTTPException(400)`. Same wire status (400); the central handler maps it.
> 2. **The legacy `PublicID` resolvers keep their exact fallback behavior.** `_get_image_instance_by_public_id` (storage-loaded, try `PublicID` then fall back to `session.get(ImageInstance, public_id)` on `NoResultFound`) and the `GET /images/{id}` reader (try `PublicID`, else `session.get(ImageInstance, int(image_id))` when `image_id.isdigit()`) are moved verbatim into `ImageInstanceRepository` methods that return `None` (never raise); the Service raises `NotFoundError`. The stray `print(...)` warning in the old fallback is dropped (logging noise, not behavior).
> 3. **Storage-ref resolution and the `X-Accel-Redirect` response building stay in the route.** The Service only resolves the `ImageInstance` (raising `NotFoundError` if absent) for the `/data` and `/thumbnail` endpoints; `resolve_image_data_ref` / `resolve_thumbnail_ref` (framework-agnostic `eyened_orm` helpers) and the `index < 0` (400) / `ValueError` (422) request-shaped validation remain at the HTTP boundary, as they are not model-CRUD.
> 4. **The two pure-redirect endpoints** (`GET /instances/images/{dataset_identifier:path}`, `GET /instances/thumbnails/{thumbnail_identifier:path}`) touch no DB and are left **exactly as-is** — no Service involvement.

---

## Task 0 (git): Confirm the working branch and a green baseline

Not a code task. All new work stays on `feature/rbac-step1-service-layer`; `development` is never touched.

- [ ] **Step 1: Confirm the working branch**

```bash
git branch --show-current   # expect: feature/rbac-step1-service-layer
```

- [ ] **Step 2: Confirm the pre-existing suite is green before adding anything**

Run: `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/pytest -q`
Expected: the existing suite passes (baseline: **211 passed**). **If anything is already red, stop and surface it — do not build on a red baseline.**

---

## Task 1: ImageInstanceRepository — graph reads, PublicID resolution, tag-link lookup

Create `ImageInstanceRepository` with the reads the `instances.py` handlers perform inline today: the conditional eager-load graph (shared by the by-id and by-PublicID readers), the storage-loaded PublicID resolver used by the data/thumbnail/tag handlers, and a composite-key tag-link lookup. Following precedent (lean test granularity), the two thin `session.get(...)`-shaped methods get no dedicated Repository test: `get_tag_link` is exercised through the Task 3 Service tests, and `get_full_graph_by_id` (a plain `session.get` + shared options builder) through the Task 2 Service tests. The two tests here cover the methods with real branching — the PublicID/digit fallback (with every eager-load branch on) and the storage-resolver fallback. No method commits; the Service owns the transaction boundary.

**Files:**
- Create: `orm/eyened_orm/repositories/image_instance_repository.py`
- Modify: `orm/eyened_orm/repositories/__init__.py` (re-export `ImageInstanceRepository`)
- Test: `orm/eyened_orm/tests/test_image_instance_repository.py`

**Interfaces:**
- Consumes: `eyened_orm` models `ImageInstance`, `ImageInstanceTagLink`, `ImageStorage`, `Series`, `Study`, `Patient`, `DeviceInstance`, `Segmentation`, `ModelSegmentation`, `FormAnnotation`; `eyened_orm.tag.SegmentationTagLink`, `FormAnnotationTagLink`.
- Produces (all take `session: Session` first):
  - `get_full_graph_by_id(session, instance_id: int, *, with_segmentations: bool, with_form_annotations: bool, with_model_segmentations: bool) -> ImageInstance | None`
  - `get_full_graph_by_public_id(session, image_id: str, *, with_segmentations: bool, with_form_annotations: bool, with_model_segmentations: bool) -> ImageInstance | None` — try `PublicID`, else `session.get(int(image_id))` when `image_id.isdigit()`.
  - `get_with_storage_by_public_id(session, public_id: str) -> ImageInstance | None` — storage-loaded, with the legacy `session.get(public_id)` fallback.
  - `get_tag_link(session, tag_id: int, image_instance_id: int) -> ImageInstanceTagLink | None` — thin composite-key `session.get`.

- [ ] **Step 1: Write the failing test**

Create `orm/eyened_orm/tests/test_image_instance_repository.py`:

```python
import datetime

from eyened_orm import (
    DeviceInstance,
    DeviceModel,
    ImageInstance,
    Patient,
    Project,
    Series,
    Study,
)
from eyened_orm.project import ExternalEnum
from eyened_orm.repositories.image_instance_repository import ImageInstanceRepository


def _make_image(session, public_id: str) -> int:
    """Build the minimal Series/Device graph an ImageInstance FK-requires.

    Returns the new ImageInstanceID.
    """
    project = Project(ProjectName=f"P-{public_id}", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier=f"ID-{public_id}", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    study = Study(PatientID=patient.PatientID, StudyDate=datetime.date(2020, 1, 1))
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


def test_get_full_graph_by_public_id_resolves_graph_and_digit_fallback(session):
    """Resolve by PublicID (all eager-load branches on), else by numeric PK string."""
    image_id = _make_image(session, "pub-str")
    _make_image(session, "9999")  # a PublicID that is itself a digit string
    repo = ImageInstanceRepository()
    # all flags True so the conditional selectinload branches are exercised
    kw = dict(
        with_segmentations=True,
        with_form_annotations=True,
        with_model_segmentations=True,
    )

    by_public = repo.get_full_graph_by_public_id(session, "pub-str", **kw)
    assert by_public is not None and by_public.ImageInstanceID == image_id
    assert by_public.Series.Study.Patient.Project is not None  # base graph loaded

    # A numeric string that is not a PublicID falls back to session.get(int)
    by_pk = repo.get_full_graph_by_public_id(session, str(image_id), **kw)
    assert by_pk is not None and by_pk.ImageInstanceID == image_id

    assert repo.get_full_graph_by_public_id(session, "no-such-id", **kw) is None


def test_get_with_storage_by_public_id_found_and_missing(session):
    """get_with_storage_by_public_id resolves by PublicID, or None if absent."""
    image_id = _make_image(session, "pub-store")
    repo = ImageInstanceRepository()

    item = repo.get_with_storage_by_public_id(session, "pub-store")
    assert item is not None and item.ImageInstanceID == image_id

    assert repo.get_with_storage_by_public_id(session, "missing") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest orm/eyened_orm/tests/test_image_instance_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eyened_orm.repositories.image_instance_repository'`.

- [ ] **Step 3: Write the repository**

Create `orm/eyened_orm/repositories/image_instance_repository.py`:

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, selectinload

from eyened_orm import (
    DeviceInstance,
    FormAnnotation,
    ImageInstance,
    ImageInstanceTagLink,
    ImageStorage,
    ModelSegmentation,
    Patient,
    Segmentation,
    Series,
    Study,
)
from eyened_orm.tag import FormAnnotationTagLink, SegmentationTagLink

_STORAGE_LOADER = selectinload(ImageInstance.ImageStorages).selectinload(
    ImageStorage.StorageBackend
)


def _full_graph_options(
    with_segmentations: bool,
    with_form_annotations: bool,
    with_model_segmentations: bool,
) -> list:
    """Build the conditional selectinload chain the two GET readers share."""
    opts = [
        selectinload(ImageInstance.Series)
        .selectinload(Series.Study)
        .selectinload(Study.Patient)
        .selectinload(Patient.Project),
        selectinload(ImageInstance.DeviceInstance).selectinload(
            DeviceInstance.DeviceModel
        ),
        selectinload(ImageInstance.Scan),
        _STORAGE_LOADER,
        selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(
            ImageInstanceTagLink.Tag
        ),
        selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(
            ImageInstanceTagLink.Creator
        ),
    ]
    if with_segmentations:
        opts += [
            selectinload(ImageInstance.Segmentations).selectinload(
                Segmentation.Feature
            ),
            selectinload(ImageInstance.Segmentations).selectinload(
                Segmentation.Creator
            ),
            selectinload(ImageInstance.Segmentations)
            .selectinload(Segmentation.SegmentationTagLinks)
            .selectinload(SegmentationTagLink.Tag),
            selectinload(ImageInstance.Segmentations)
            .selectinload(Segmentation.SegmentationTagLinks)
            .selectinload(SegmentationTagLink.Creator),
        ]
    if with_form_annotations:
        opts += [
            selectinload(ImageInstance.FormAnnotations)
            .selectinload(FormAnnotation.FormAnnotationTagLinks)
            .selectinload(FormAnnotationTagLink.Tag),
            selectinload(ImageInstance.FormAnnotations)
            .selectinload(FormAnnotation.FormAnnotationTagLinks)
            .selectinload(FormAnnotationTagLink.Creator),
        ]
    if with_model_segmentations:
        opts += [
            selectinload(ImageInstance.ModelSegmentations).selectinload(
                ModelSegmentation.Model
            ),
        ]
    return opts


class ImageInstanceRepository:
    """Data access for ImageInstance reads and its Tag links."""

    def get_full_graph_by_id(
        self,
        session: Session,
        instance_id: int,
        *,
        with_segmentations: bool,
        with_form_annotations: bool,
        with_model_segmentations: bool,
    ) -> ImageInstance | None:
        """Return the instance by int id with the conditional graph, or None."""
        opts = _full_graph_options(
            with_segmentations, with_form_annotations, with_model_segmentations
        )
        return session.get(ImageInstance, instance_id, options=tuple(opts))

    def get_full_graph_by_public_id(
        self,
        session: Session,
        image_id: str,
        *,
        with_segmentations: bool,
        with_form_annotations: bool,
        with_model_segmentations: bool,
    ) -> ImageInstance | None:
        """Return the instance by PublicID (numeric-PK fallback), or None."""
        opts = _full_graph_options(
            with_segmentations, with_form_annotations, with_model_segmentations
        )
        item = (
            session.scalars(
                select(ImageInstance)
                .options(*opts)
                .where(ImageInstance.PublicID == image_id)
            )
            .first()
        )
        if item is None and image_id.isdigit():
            item = session.get(ImageInstance, int(image_id), options=tuple(opts))
        return item

    def get_with_storage_by_public_id(
        self, session: Session, public_id: str
    ) -> ImageInstance | None:
        """Return the instance by PublicID with storage loaded (PK fallback), or None.

        Mirrors the legacy ``_get_image_instance_by_public_id`` resolver: try the
        PublicID; on no match fall back to ``session.get`` with the raw id.
        """
        try:
            return session.scalars(
                select(ImageInstance)
                .options(_STORAGE_LOADER)
                .where(ImageInstance.PublicID == public_id)
            ).one()
        except NoResultFound:
            return session.get(ImageInstance, public_id)

    def get_tag_link(
        self, session: Session, tag_id: int, image_instance_id: int
    ) -> ImageInstanceTagLink | None:
        """Return the link for (tag_id, image_instance_id), or None if absent."""
        return session.get(
            ImageInstanceTagLink,
            {"TagID": tag_id, "ImageInstanceID": image_instance_id},
        )
```

Update `orm/eyened_orm/repositories/__init__.py` (add the import + `__all__` entry, keeping all existing exports):

```python
from .image_instance_repository import ImageInstanceRepository
```

```python
    "ImageInstanceRepository",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest orm/eyened_orm/tests/test_image_instance_repository.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add orm/eyened_orm/repositories/image_instance_repository.py orm/eyened_orm/repositories/__init__.py orm/eyened_orm/tests/test_image_instance_repository.py
git commit -m "feat(repositories): add ImageInstanceRepository reads and tag-link lookup"
```

---

## Task 2: ImageInstanceService — instance reads

Create `ImageInstanceService` with the three read paths the handlers use: by-id graph read, by-PublicID graph read, and storage-resolution for the data/thumbnail endpoints. The only failure path is a missing instance (`NotFoundError` → 404). The constructor takes `ImageInstanceRepository` **and** `TagRepository` (the tag mutations in Task 3 need it); the default factory wires both plus the real logger.

**Files:**
- Create: `server/services/image_instance_service.py`
- Modify: `server/services/__init__.py` (re-export `ImageInstanceService`)
- Test: `server/tests/test_image_instance_service.py`

**Interfaces:**
- Consumes: `ImageInstanceRepository` (Task 1); `TagRepository` (existing); `NotFoundError`, `BadRequestError` (existing); `ActingUser` (existing); `DatabaseModificationLogger`/`get_db_logger` (`server/utils/db_logging.py`); `eyened_orm.ImageInstance`.
- Produces:
  - `ImageInstanceService(repository: ImageInstanceRepository, tag_repository: TagRepository, logger: DatabaseModificationLogger | None = None)`
  - `get_instance(session, instance_id: int, *, with_segmentations: bool, with_form_annotations: bool, with_model_segmentations: bool) -> ImageInstance` — 404 if absent.
  - `get_by_public_id(session, image_id: str, *, with_segmentations: bool, with_form_annotations: bool, with_model_segmentations: bool) -> ImageInstance` — 404 if absent.
  - `get_for_storage(session, public_id: str) -> ImageInstance` — storage-loaded resolver for the data/thumbnail endpoints; 404 if absent.
  - `get_image_instance_service() -> ImageInstanceService` — default-wiring factory.

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_image_instance_service.py`:

```python
import datetime

import pytest

from eyened_orm import (
    DeviceInstance,
    DeviceModel,
    ImageInstance,
    Patient,
    Project,
    Series,
    Study,
)
from eyened_orm.project import ExternalEnum
from eyened_orm.repositories.image_instance_repository import ImageInstanceRepository
from eyened_orm.repositories.tag_repository import TagRepository

from server.services.exceptions import NotFoundError
from server.services.image_instance_service import ImageInstanceService


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


def _make_image(session, public_id: str) -> int:
    """Build the minimal graph an ImageInstance FK-requires; return its id."""
    project = Project(ProjectName=f"P-{public_id}", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier=f"ID-{public_id}", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    study = Study(PatientID=patient.PatientID, StudyDate=datetime.date(2020, 1, 1))
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


def _service(logger=None) -> ImageInstanceService:
    return ImageInstanceService(
        ImageInstanceRepository(), TagRepository(), logger=logger
    )


_READ_KW = dict(
    with_segmentations=False,
    with_form_annotations=False,
    with_model_segmentations=False,
)


def test_get_instance_returns_it(session):
    """get_instance returns the instance at the given id."""
    image_id = _make_image(session, "pub-1")
    session.commit()

    got = _service().get_instance(session, image_id, **_READ_KW)

    assert got.ImageInstanceID == image_id


def test_get_instance_unknown_raises_not_found(session):
    """Getting a missing instance is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().get_instance(session, 999_999, **_READ_KW)


def test_get_by_public_id_unknown_raises_not_found(session):
    """Resolving a missing PublicID is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().get_by_public_id(session, "nope", **_READ_KW)


def test_get_for_storage_unknown_raises_not_found(session):
    """get_for_storage on a missing PublicID raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().get_for_storage(session, "missing")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest server/tests/test_image_instance_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.services.image_instance_service'`.

- [ ] **Step 3: Write the service**

Create `server/services/image_instance_service.py`:

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from eyened_orm import ImageInstance
from eyened_orm.repositories.image_instance_repository import ImageInstanceRepository
from eyened_orm.repositories.tag_repository import TagRepository

from ..utils.db_logging import DatabaseModificationLogger, get_db_logger
from .exceptions import NotFoundError


class ImageInstanceService:
    """Business logic for ImageInstance reads and its Tag links."""

    def __init__(
        self,
        repository: ImageInstanceRepository,
        tag_repository: TagRepository,
        logger: DatabaseModificationLogger | None = None,
    ) -> None:
        self.repository = repository
        self.tags = tag_repository
        self.logger = logger

    def get_instance(
        self,
        session: Session,
        instance_id: int,
        *,
        with_segmentations: bool,
        with_form_annotations: bool,
        with_model_segmentations: bool,
    ) -> ImageInstance:
        """Return an instance by int id, with the requested eager-load graph.

        Raises:
            NotFoundError: If the instance does not exist.
        """
        item = self.repository.get_full_graph_by_id(
            session,
            instance_id,
            with_segmentations=with_segmentations,
            with_form_annotations=with_form_annotations,
            with_model_segmentations=with_model_segmentations,
        )
        if item is None:
            raise NotFoundError("ImageInstance not found")
        return item

    def get_by_public_id(
        self,
        session: Session,
        image_id: str,
        *,
        with_segmentations: bool,
        with_form_annotations: bool,
        with_model_segmentations: bool,
    ) -> ImageInstance:
        """Return an instance by PublicID, with the requested eager-load graph.

        Raises:
            NotFoundError: If the instance does not exist.
        """
        item = self.repository.get_full_graph_by_public_id(
            session,
            image_id,
            with_segmentations=with_segmentations,
            with_form_annotations=with_form_annotations,
            with_model_segmentations=with_model_segmentations,
        )
        if item is None:
            raise NotFoundError("ImageInstance not found")
        return item

    def get_for_storage(self, session: Session, public_id: str) -> ImageInstance:
        """Return the storage-loaded instance for a data/thumbnail request.

        Raises:
            NotFoundError: If the instance does not exist.
        """
        item = self.repository.get_with_storage_by_public_id(session, public_id)
        if item is None:
            raise NotFoundError("ImageInstance not found")
        return item


def get_image_instance_service() -> ImageInstanceService:
    """Default ImageInstanceService wiring for FastAPI ``Depends()``."""
    return ImageInstanceService(
        ImageInstanceRepository(), TagRepository(), logger=get_db_logger()
    )
```

Update `server/services/__init__.py` (add the import + `__all__` entry, keeping all existing exports):

```python
from .image_instance_service import ImageInstanceService
```

```python
    "ImageInstanceService",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest server/tests/test_image_instance_service.py -v`
Expected: PASS (4 passed). (`get_instance` carries the base-graph happy path; the `get_by_public_id`/`get_for_storage` happy paths are already covered by the Task 1 repository tests, so only their `NotFoundError` translation is asserted here.)

- [ ] **Step 5: Commit**

```bash
git add server/services/image_instance_service.py server/services/__init__.py server/tests/test_image_instance_service.py
git commit -m "feat(services): add ImageInstanceService instance reads"
```

---

## Task 3: ImageInstanceService — instance tag add/patch/remove

Add the three instance-tag mutations. Each preserves today's lookup order and failure paths: **tag_instance** resolves the instance (404), the tag (404), checks the tag type (400 → `BadRequestError`), then creates the link (or updates its comment if it already exists); **patch_instance_tag** resolves instance (404), tag (404), type (400), then the link (404), and updates the comment if provided; **untag_instance** resolves the instance (404) then deletes the link if present (idempotent — no error when the link is absent). Each returns the `ImageInstanceTagLink` (with `.Tag` set to avoid a lazy-load) for the route to convert, except `untag_instance` which returns `None`.

**Files:**
- Modify: `server/services/image_instance_service.py` (add three methods)
- Modify: `server/tests/test_image_instance_service.py` (append tag tests + a `_make_tag` helper)

**Interfaces:**
- Consumes: `ImageInstanceRepository.get_with_storage_by_public_id`, `.get_tag_link` (Task 1); `TagRepository.get_by_id` (existing); `ActingUser`, `BadRequestError` (existing); `eyened_orm.ImageInstanceTagLink`; `eyened_orm.tag.TagType`.
- Produces (added to `ImageInstanceService`):
  - `tag_instance(session, public_id: str, tag_id: int, comment: str | None, actor: ActingUser) -> ImageInstanceTagLink` — create-or-update-comment; 404 instance/tag, 400 wrong type.
  - `patch_instance_tag(session, public_id: str, tag_id: int, comment: str | None, actor: ActingUser) -> ImageInstanceTagLink` — 404 instance/tag/link, 400 wrong type.
  - `untag_instance(session, public_id: str, tag_id: int, actor: ActingUser) -> None` — 404 instance; idempotent delete.

- [ ] **Step 1: Write the failing test**

Append to `server/tests/test_image_instance_service.py` (add the imports `ActingUser`, `BadRequestError`, `Creator`, `Tag`, `TagType` at the top of the file alongside the existing imports):

```python
# add to the existing imports at the top of the file:
from eyened_orm import Creator, Tag
from eyened_orm.tag import TagType
from server.services.acting_user import ActingUser
from server.services.exceptions import BadRequestError
```

```python
def _actor(session) -> ActingUser:
    creator = Creator(CreatorName="alice", IsHuman=True)
    session.add(creator)
    session.flush()
    return ActingUser(id=creator.CreatorID, username=creator.CreatorName)


def _make_tag(session, creator_id: int, tag_type: TagType = TagType.ImageInstance) -> Tag:
    tag = Tag(
        TagName=f"t-{tag_type.name}",
        TagDescription="d",
        TagType=tag_type,
        CreatorID=creator_id,
    )
    session.add(tag)
    session.flush()
    return tag


def test_tag_instance_creates_link(session):
    """tag_instance links a tag to an instance and returns the link."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    session.commit()

    link = _service().tag_instance(session, "pub-1", tag.TagID, "hi", actor)

    assert link.TagID == tag.TagID
    assert link.Comment == "hi"
    assert link.Tag.TagID == tag.TagID


def test_tag_instance_unknown_instance_raises_not_found(session):
    """tag_instance on a missing instance is translated to NotFoundError."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    session.commit()
    with pytest.raises(NotFoundError):
        _service().tag_instance(session, "nope", tag.TagID, None, actor)


def test_tag_instance_unknown_tag_raises_not_found(session):
    """tag_instance with an unknown tag id is translated to NotFoundError."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    session.commit()
    with pytest.raises(NotFoundError):
        _service().tag_instance(session, "pub-1", 999_999, None, actor)


def test_tag_instance_wrong_tag_type_raises_bad_request(session):
    """tag_instance with a non-ImageInstance tag raises BadRequestError (-> 400)."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id, tag_type=TagType.Segmentation)
    session.commit()
    with pytest.raises(BadRequestError):
        _service().tag_instance(session, "pub-1", tag.TagID, None, actor)


def test_tag_instance_existing_updates_comment(session):
    """A second tag_instance with a comment updates the existing link, not duplicates."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    session.commit()
    service = _service()

    service.tag_instance(session, "pub-1", tag.TagID, "first", actor)
    link = service.tag_instance(session, "pub-1", tag.TagID, "second", actor)

    assert link.Comment == "second"


def test_tag_instance_logs_insert(session):
    """tag_instance emits one insert audit record for ImageInstanceTagLink."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    session.commit()
    logger = FakeAuditLogger()

    _service(logger).tag_instance(session, "pub-1", tag.TagID, None, actor)

    assert len(logger.inserts) == 1
    assert logger.inserts[0]["entity"] == "ImageInstanceTagLink"


def test_patch_instance_tag_updates_comment(session):
    """patch_instance_tag overwrites the comment on an existing link."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    session.commit()
    service = _service()
    service.tag_instance(session, "pub-1", tag.TagID, "old", actor)

    link = service.patch_instance_tag(session, "pub-1", tag.TagID, "new", actor)

    assert link.Comment == "new"


def test_patch_instance_tag_unknown_link_raises_not_found(session):
    """patch_instance_tag with no existing link raises NotFoundError (-> 404)."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    session.commit()
    with pytest.raises(NotFoundError):
        _service().patch_instance_tag(session, "pub-1", tag.TagID, "x", actor)


def test_untag_instance_removes_link(session):
    """untag_instance deletes the link for that (instance, tag)."""
    actor = _actor(session)
    image_id = _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    session.commit()
    service = _service()
    service.tag_instance(session, "pub-1", tag.TagID, None, actor)

    service.untag_instance(session, "pub-1", tag.TagID, actor)

    assert ImageInstanceRepository().get_tag_link(session, tag.TagID, image_id) is None


def test_untag_instance_absent_link_is_idempotent(session):
    """untag_instance with no link present is a no-op (no error)."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    session.commit()

    # Does not raise even though no link exists.
    _service().untag_instance(session, "pub-1", tag.TagID, actor)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest server/tests/test_image_instance_service.py -v`
Expected: FAIL — `AttributeError: 'ImageInstanceService' object has no attribute 'tag_instance'`.

- [ ] **Step 3: Add the three methods**

Add `ImageInstanceTagLink` and `TagType` to the top-of-file imports and `ActingUser`/`BadRequestError` to the service module, then add the methods to `ImageInstanceService` (after `get_for_storage`, before the module-level factory):

```python
# extend the top-of-file imports:
from eyened_orm import ImageInstance, ImageInstanceTagLink
from eyened_orm.tag import TagType
```

```python
# add to the existing "from .exceptions import ..." line and add ActingUser:
from .acting_user import ActingUser
from .exceptions import BadRequestError, NotFoundError
```

```python
    def tag_instance(
        self,
        session: Session,
        public_id: str,
        tag_id: int,
        comment: str | None,
        actor: ActingUser,
    ) -> ImageInstanceTagLink:
        """Attach a Tag to an instance (idempotent; updates comment if re-tagged).

        Raises:
            NotFoundError: If the instance or the tag does not exist.
            BadRequestError: If the tag is not an ImageInstance-type tag.
        """
        instance = self.repository.get_with_storage_by_public_id(session, public_id)
        if instance is None:
            raise NotFoundError("ImageInstance not found")
        tag = self.tags.get_by_id(session, tag_id)
        if tag is None:
            raise NotFoundError("Tag not found")
        if tag.TagType != TagType.ImageInstance:
            raise BadRequestError("Tag type must be ImageInstance")

        link = self.repository.get_tag_link(
            session, tag.TagID, instance.ImageInstanceID
        )
        if link is None:
            link = ImageInstanceTagLink(
                TagID=tag.TagID,
                ImageInstanceID=instance.ImageInstanceID,
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
                    endpoint=f"POST /api/instances/{public_id}/tags",
                    entity="ImageInstanceTagLink",
                    fields={
                        "tag_id": tag.TagID,
                        "image_instance_id": instance.ImageInstanceID,
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
                    endpoint=f"POST /api/instances/{public_id}/tags",
                    entity="ImageInstanceTagLink",
                    fields={
                        "tag_id": tag.TagID,
                        "image_instance_id": public_id,
                    },
                    changes={"comment": f"{old_comment} -> {comment}"},
                )

        link.Tag = tag  # avoid a Tag lazy-load at DTO time
        return link

    def patch_instance_tag(
        self,
        session: Session,
        public_id: str,
        tag_id: int,
        comment: str | None,
        actor: ActingUser,
    ) -> ImageInstanceTagLink:
        """Update the comment on an existing instance tag link.

        Raises:
            NotFoundError: If the instance, tag, or link does not exist.
            BadRequestError: If the tag is not an ImageInstance-type tag.
        """
        instance = self.repository.get_with_storage_by_public_id(session, public_id)
        if instance is None:
            raise NotFoundError("ImageInstance not found")
        tag = self.tags.get_by_id(session, tag_id)
        if tag is None:
            raise NotFoundError("Tag not found")
        if tag.TagType != TagType.ImageInstance:
            raise BadRequestError("Tag type must be ImageInstance")

        link = self.repository.get_tag_link(
            session, tag_id, instance.ImageInstanceID
        )
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
                    endpoint=f"PATCH /api/instances/{public_id}/tags/{tag_id}",
                    entity="ImageInstanceTagLink",
                    fields={
                        "tag_id": tag_id,
                        "image_instance_id": instance.ImageInstanceID,
                    },
                    changes={"comment": f"{old_comment} -> {comment}"},
                )

        link.Tag = tag
        return link

    def untag_instance(
        self, session: Session, public_id: str, tag_id: int, actor: ActingUser
    ) -> None:
        """Remove a Tag from an instance (idempotent; no error if not linked).

        Raises:
            NotFoundError: If the instance does not exist.
        """
        instance = self.repository.get_with_storage_by_public_id(session, public_id)
        if instance is None:
            raise NotFoundError("ImageInstance not found")

        link = self.repository.get_tag_link(
            session, tag_id, instance.ImageInstanceID
        )
        if link is not None:
            deleted_data = {
                "tag_id": tag_id,
                "image_instance_id": instance.ImageInstanceID,
                "comment": link.Comment,
                "creator_id": link.CreatorID,
            }
            session.delete(link)
            session.commit()
            if self.logger is not None:
                self.logger.log_delete(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=f"DELETE /api/instances/{public_id}/tags/{tag_id}",
                    entity="ImageInstanceTagLink",
                    fields={"tag_id": tag_id, "image_instance_id": public_id},
                    deleted_data=deleted_data,
                )
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest server/tests/test_image_instance_service.py -v`
Expected: PASS (14 passed — the 4 from Task 2 plus these 10).

- [ ] **Step 5: Commit**

```bash
git add server/services/image_instance_service.py server/tests/test_image_instance_service.py
git commit -m "feat(services): add ImageInstanceService instance tag add/patch/remove"
```

---

## Task 4: Route `instances.py` through `ImageInstanceService`

Rewrite the DB-touching `instances.py` handlers to be thin: parse → build `ActingUser` (mutations only) → call `ImageInstanceService` → `DTOConverter` → return. The two pure-redirect endpoints (`/instances/images/{...}`, `/instances/thumbnails/{...}`) are untouched. No handler contains inline queries, `raise HTTPException` for not-found/wrong-type, `session.commit`, or direct `get_db_logger()` calls anymore — those move into the Service; the central `NotFoundError`/`BadRequestError` handlers (already registered) map the 404s/400s. Storage-ref resolution and redirect building stay in the `/data` and `/thumbnail` handlers (request/response shaping, not model-CRUD). Verified by the full suite still passing and an app-boot smoke check — matching how the earlier route slices were verified (no route-level test files exist for these slices).

**Files:**
- Modify: `server/routes/instances.py` (rewrite the DB-touching handlers)

**Interfaces:**
- Consumes: `ImageInstanceService`, `get_image_instance_service` (Task 2/3); `ActingUser` (existing); `DTOConverter` (existing); `resolve_image_data_ref`, `resolve_thumbnail_ref` (existing `eyened_orm.storage_access`).
- Produces: no new symbols — this is the HTTP boundary.

- [ ] **Step 1: Rewrite the route module**

Replace the entire contents of `server/routes/instances.py` with:

```python
from typing import Optional

from eyened_orm.storage_access import resolve_image_data_ref, resolve_thumbnail_ref
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_instances import ImageGET
from ..dtos.dtos_aux import ObjectTagPOST, ObjectTagPATCH, TagMeta
from ..services.acting_user import ActingUser
from ..services.image_instance_service import (
    ImageInstanceService,
    get_image_instance_service,
)
from .auth import CurrentUser, get_current_user, is_authenticated

router = APIRouter()


@router.get("/instances/{instance_id}", response_model=ImageGET)
async def get_instance(
    instance_id: int,
    with_segmentations: bool = False,
    with_form_annotations: bool = False,
    with_model_segmentations: bool = False,
    with_tag_metadata: bool = False,
    db: Session = Depends(get_db),
    service: ImageInstanceService = Depends(get_image_instance_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single image instance by id, with optional related graphs."""
    item = service.get_instance(
        db,
        instance_id,
        with_segmentations=with_segmentations,
        with_form_annotations=with_form_annotations,
        with_model_segmentations=with_model_segmentations,
    )
    return DTOConverter.image_instance_to_get(
        item,
        with_tag_metadata=with_tag_metadata,
        with_segmentations=with_segmentations,
        with_form_annotations=with_form_annotations,
        with_model_segmentations=with_model_segmentations,
    )


@router.get("/images/{image_id}", response_model=ImageGET)
async def get_public_image(
    image_id: str,
    with_segmentations: bool = False,
    with_form_annotations: bool = False,
    with_model_segmentations: bool = False,
    with_tag_metadata: bool = False,
    db: Session = Depends(get_db),
    service: ImageInstanceService = Depends(get_image_instance_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single image instance by PublicID, with optional related graphs."""
    item = service.get_by_public_id(
        db,
        image_id,
        with_segmentations=with_segmentations,
        with_form_annotations=with_form_annotations,
        with_model_segmentations=with_model_segmentations,
    )
    return DTOConverter.image_instance_to_get(
        item,
        with_tag_metadata=with_tag_metadata,
        with_segmentations=with_segmentations,
        with_form_annotations=with_form_annotations,
        with_model_segmentations=with_model_segmentations,
    )


def build_storage_redirect_response(path: str) -> Response:
    response = Response()
    response.headers["X-Accel-Redirect"] = path
    return response


@router.get("/images/{image_id}/data")
async def get_public_image_data(
    image_id: str,
    index: Optional[int] = None,
    meta: bool = False,
    _: bool = Depends(is_authenticated),
    db: Session = Depends(get_db),
    service: ImageInstanceService = Depends(get_image_instance_service),
):
    """Redirect to the stored image data for an instance (by PublicID)."""
    item = service.get_for_storage(db, image_id)
    if index is not None and index < 0:
        raise HTTPException(400, "index must be >= 0")
    try:
        ref = resolve_image_data_ref(item, index=index, meta=meta)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return build_storage_redirect_response(ref.nginx_path)


@router.get("/images/{image_id}/thumbnail")
async def get_public_image_thumbnail(
    image_id: str,
    size: int = 144,
    _: bool = Depends(is_authenticated),
    db: Session = Depends(get_db),
    service: ImageInstanceService = Depends(get_image_instance_service),
):
    """Redirect to the stored thumbnail for an instance (by PublicID)."""
    item = service.get_for_storage(db, image_id)
    try:
        ref = resolve_thumbnail_ref(item, size=size)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return build_storage_redirect_response(ref.nginx_path)


@router.get("/instances/images/{dataset_identifier:path}")
async def get_file(
    dataset_identifier: str,
    _: bool = Depends(is_authenticated),
):
    # Set X-Accel-Redirect header to tell NGINX to serve the file
    response = Response()
    response.headers["X-Accel-Redirect"] = "/files/" + dataset_identifier
    return response


@router.get("/instances/thumbnails/{thumbnail_identifier:path}")
async def get_thumb(
    thumbnail_identifier: str,
    _: bool = Depends(is_authenticated),
):
    response = Response()
    response.headers["X-Accel-Redirect"] = "/thumbnails/" + thumbnail_identifier
    return response


@router.post("/instances/{instance_id}/tags", response_model=TagMeta)
async def tag_instance(
    instance_id: str,
    body: ObjectTagPOST,
    db: Session = Depends(get_db),
    service: ImageInstanceService = Depends(get_image_instance_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> TagMeta:
    """Attach a Tag to an ImageInstance by tag ID (idempotent)."""
    link = service.tag_instance(
        db,
        instance_id,
        body.tag_id,
        body.comment,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.link_to_tag_metadata(link)


@router.patch("/instances/{instance_id}/tags/{tag_id}", response_model=TagMeta)
async def patch_instance_tag(
    instance_id: str,
    tag_id: int,
    body: ObjectTagPATCH,
    db: Session = Depends(get_db),
    service: ImageInstanceService = Depends(get_image_instance_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> TagMeta:
    """Update comment on an existing ImageInstance tag link."""
    link = service.patch_instance_tag(
        db,
        instance_id,
        tag_id,
        body.comment,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.link_to_tag_metadata(link)


@router.delete("/instances/{instance_id}/tags/{tag_id}", status_code=204)
async def untag_instance(
    instance_id: str,
    tag_id: int,
    db: Session = Depends(get_db),
    service: ImageInstanceService = Depends(get_image_instance_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Remove a Tag from an ImageInstance (idempotent)."""
    service.untag_instance(
        db,
        instance_id,
        tag_id,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return Response(status_code=204)
```

- [ ] **Step 2: App-boot smoke check (imports + routes register)**

Run:

> **Note:** the routers are mounted as a sub-app (`server/main.py:109` does `app.mount("/api", app_api)`), so the route paths live on **`app_api.routes`** and carry **no** `/api` prefix. Introspect `app_api`, not `app`.

```bash
EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password \
  dev/.venv/bin/python -c "
from server.main import app_api
paths = {r.path for r in app_api.routes}
for p in [
    '/instances/{instance_id}',
    '/images/{image_id}',
    '/images/{image_id}/data',
    '/images/{image_id}/thumbnail',
    '/instances/{instance_id}/tags',
    '/instances/{instance_id}/tags/{tag_id}',
    '/instances/images/{dataset_identifier:path}',
    '/instances/thumbnails/{thumbnail_identifier:path}',
]:
    assert p in paths, (p, sorted(x for x in paths if 'instance' in x or 'image' in x))
print('instance routes OK')
"
```

Expected: prints `instance routes OK` (the app imports cleanly and every route is registered on the mounted `/api` sub-app).

- [ ] **Step 3: Run the full suite to confirm no regression**

Run: `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/pytest -q`
Expected: PASS — **227 passed** (211 baseline + 2 repository tests from Task 1 + 14 service tests from Tasks 2–3), no failures.

- [ ] **Step 4: Commit**

```bash
git add server/routes/instances.py
git commit -m "refactor(routes): route instance endpoints through ImageInstanceService"
```

---

## Phase 4a done — first slice of spec Phase 4

After Task 4, `instances.py` no longer queries the ORM directly: it parses, calls `ImageInstanceService`, and converts DTOs (the two pure-redirect endpoints stay as-is). Do **not** merge `feature/rbac-step1-service-layer` to `development`; the next slices are spec **Phase 4b** (`form_annotations.py`) and **4c** (`segmentations.py`), each a separate plan — both can reuse the `ImageInstanceRepository` PublicID resolvers added here.

Update the `rbac-step1-migration-state` memory: instances (4a) done; Phase 4b/4c next; test count **227**.
```
