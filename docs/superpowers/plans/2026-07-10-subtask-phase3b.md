# subtask Repository/Service Migration (RBAC Step 1, Phase 3b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route the `subtask.py` endpoints — by-id subtask read/update/delete (`GET/PATCH/DELETE /subtasks/{id}`) plus the image-link mutations (`POST /subtasks/{id}/images`, `DELETE /subtasks/{id}/images/{instance_id}`) — through a new `SubTaskService` backed by the existing `SubTaskRepository`, committing directly onto the current `feature/rbac-step1-service-layer` branch (never touching `development`).

**Architecture:** Same layering as the reviewed Device/Patient/FormSchema/Study/Feature/Tag/Task slices — thin route (parse → Service → `DTOConverter` → return), a Service with a constructor-injected Repository that raises domain exceptions and owns the commit, and a framework-agnostic Repository that takes a `Session`. This phase completes the spec's "Phase 3" (Phase 3a shipped `task.py` + `TaskService` + the task-rooted subtask reads; **3b, this plan**, ships `subtask.py` + `SubTaskService`, the per-subtask-id CRUD and image-link mutations under `/subtasks/...`). It **extends the existing `SubTaskRepository`** (added in 3a to `task_repository.py`) with by-id and image-link data-access methods, and **adds `SubTaskService` to the existing `task_service.py`** alongside `TaskService` (per the spec's directory table: `task_service.py` holds `TaskService`, `SubTaskService`).

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (ORM `eyened_orm`), pytest with the in-memory SQLite `session` fixture.

## Global Constraints

Copied verbatim from `docs/superpowers/specs/2026-07-03-repository-service-layer-design.md`. Every task implicitly includes these:

- **Filenames:** snake_case, one file per model module — `task_repository.py`, `task_service.py`. Per the spec's directory table, `task_repository.py` holds `TaskRepository`, `SubTaskRepository`; `task_service.py` holds `TaskService`, `SubTaskService`. (`TaskDefinitionRepository`/`SubTaskImageLinkRepository` are **not** created: YAGNI — no endpoint does that CRUD, and image-instance resolution / link lookups are reads that belong on `SubTaskRepository` since they exist only to serve subtask image linking.)
- **Class names:** `SubTaskRepository` / `SubTaskService`.
- **Repositories** live in `orm/eyened_orm/repositories/`, take a `Session` as a method argument (never own/create sessions), have no FastAPI imports, and return `None`/empty on "not found" — never raise HTTP-shaped errors.
- **Services** live in `server/services/`, receive their Repositories via constructor injection, and raise the domain exceptions in `server/services/exceptions.py` — **never** raise `HTTPException` directly.
- **DTO conversion stays at the route boundary** (via `DTOConverter`), never inside a Service.
- **Package `__init__.py` files re-export** their public classes (with `__all__`), keeping all existing exports.
- **No mocking library.** DB-backed tests use the real in-memory SQLite `session` fixture (already exposed to `server/tests/` by the foundation's `server/tests/conftest.py`). Any non-DB fake is a small hand-rolled object.
- **Do not touch:** CLI/worker code, `search.py`, `auth.py`, `Base`'s generic classmethods, the pre-existing Device/Patient/FormSchema/Study/Feature/Tag slices, or `TaskService`/`task.py` (that was 3a — `SubTaskService` is additive to the same module).
- **Repository tests** → `orm/eyened_orm/tests/`; **Service tests** → `server/tests/`.

### Conventions reused from the `task` (3a) phase

- **Commit ownership:** `get_db` (`server/db.py`) yields a session that is only *closed*, never committed, by its context manager. Every mutating Service method calls `session.commit()` itself — the Service is the transaction boundary. (The spec's deferred "transaction ownership" follow-up will revisit this layer-wide; do not change it here.)
- **Audit logging is injected, not global-reached.** The Service takes `logger: DatabaseModificationLogger | None = None` via its constructor and calls it inside the mutating method. `get_subtask_service()` wires the real logger via `get_db_logger()`; Service tests inject `None` or a small hand-rolled fake. Every logging call stays guarded by `if self.logger is not None:` (matching today's `if logger:` guard, since `get_db_logger()` returns `None` when DB logging is disabled).
- **Acting user:** routes map their handler-layer `CurrentUser` onto the framework-agnostic `ActingUser(id, username)` value object (`server/services/acting_user.py`, already exists) before calling a Service.
- **Lean test granularity:** thin `session.get(...)` wrappers (`SubTaskRepository.get_by_id`, `get_image_link`) get **no** dedicated Repository test — they are exercised through the Service tests. Every test carries a one-line docstring as its description.

> **Interpreter note:** no `python`/`pytest` on `PATH`; the venv is at `dev/.venv`. Every command uses `dev/.venv/bin/python` / `dev/.venv/bin/pytest`. The two commands that import `server.*` (app-boot / router-introspection checks) need dummy DB env vars, mirroring `server/tests/conftest.py`: prefix them with `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password`.

> **Reused from earlier work on `feature/rbac-step1-service-layer`:** `NotFoundError` and the central handler (`server/services/exceptions.py`, registered in `server/main.py` via `register_exception_handlers` — the handler dispatches every `ServiceError` subclass by MRO, so this phase needs **no** `main.py` change); the `session` fixture already imported in `server/tests/conftest.py`; the `ActingUser` value object; both `repositories/` and `services/` packages with their `__init__.py` re-exports; the `SubTaskRepository` class and its module-level `_SUBTASK_IMAGE_LOADER` eager-load chain (both in `orm/eyened_orm/repositories/task_repository.py`, added in 3a). **`subtask.router` is already registered** in `server/main.py` (`app_api.include_router(subtask.router)`), so no registration change is needed either. This phase introduces **no new exception type**: every `subtask.py` failure path today is a 404 (`GET`/`PATCH`/`DELETE` on a missing subtask; add-image on a missing subtask or missing `ImageInstance`; remove-image on a missing `ImageInstance` or missing link), all served by the existing `NotFoundError`.

> **Existing ORM facts confirmed for this plan** (verified against `orm/eyened_orm/task.py` and the in-memory SQLite test DB, `PRAGMA foreign_keys=ON`):
> - `SubTask` (`orm/eyened_orm/task.py:173`): `SubTaskID` (PK); `TaskID` (NOT NULL FK → `Task.TaskID`, `ondelete="CASCADE"`); `CreatorID` (nullable FK); `Comments` (`Text`, nullable); `TaskState` (`Mapped["SubTaskState"]`, **column default `SubTaskState.NotStarted`**). `SubTaskImageLinks` relationship (`passive_deletes=True`, `order_by="SubTaskImageLink.ImageIndex"`). `SubTaskState` members: `NotStarted`, `Busy`, `Ready`.
> - `SubTaskImageLink` (`orm/eyened_orm/task.py:142`): **composite PK `(SubTaskID, ImageInstanceID)`**, both FKs `ondelete="CASCADE"`; `ImageIndex` (`int`, NOT NULL); `UniqueConstraint(SubTaskID, ImageIndex)`. So `session.get(SubTaskImageLink, {"SubTaskID": ..., "ImageInstanceID": ...})` is the by-key lookup, and `session.delete(link)` removes one link. A minimal link row inserts fine given a real `SubTask` + `ImageInstance`.
> - `ImageInstance` has `PublicID` (the external string id the route resolves) and `ImageInstanceID` (int PK). A real `ImageInstance` row FK-requires a `Series`→`Study`→`Patient`→`Project` chain **and** a `DeviceInstance`→`DeviceModel`; the existing `_make_image` helper in `orm/eyened_orm/tests/test_task_repository.py` (added in 3a) builds exactly that minimal graph and returns the new `ImageInstanceID`.
> - The 3a `_SUBTASK_IMAGE_LOADER` chain (`selectinload(SubTask.SubTaskImageLinks).selectinload(SubTaskImageLink.ImageInstance).selectinload(ImageInstance.ImageStorages).selectinload(ImageStorage.StorageBackend)`) is already defined at module level in `task_repository.py` and is reused for by-id image loading here.

> **DTO facts confirmed:** `DTOConverter.subtask_to_get(subtask)` (`dto_converter.py:655`) and `DTOConverter.subtask_with_images_to_get(subtask)` (`dto_converter.py:666`) build `SubTaskGET`/`SubTaskWithImagesGET` (`server/dtos/dtos_tasks.py`). All DTO calls stay in the route. `SubTaskPATCH` and `AddImageRequest` are request bodies defined **inline in `subtask.py`** (they move with the rewritten route).

> **Behavior-preserving decisions (call out in review):**
> 1. **`SubTaskPATCH.task_state` is retyped from `Optional[str]` to `Optional[SubTaskState]`**, mirroring how 3a typed `TaskPATCH.task_state` as the enum. Accepted values are unchanged (the enum member names); the only difference is that an invalid value now 422s at the schema boundary instead of reaching the DB. The Service therefore takes `task_state: SubTaskState | None` and assigns the enum directly.
> 2. **The old `add_subtask_image` broad `try/except Exception → rollback → HTTP 500 "Error adding image link"` is dropped.** On the happy path (a not-yet-linked image) the `max(ImageIndex)+1` write cannot collide with `UniqueConstraint(SubTaskID, ImageIndex)`, so the add + commit succeeds without a guard. The one failing input is re-linking the **same** image to the **same** subtask: `SubTaskImageLink` has a composite PK `(SubTaskID, ImageInstanceID)` (`orm/eyened_orm/task.py:156-162`), so that commit raises `IntegrityError`. This is **behavior-preserving at the wire level** — the old route caught it and returned HTTP 500 (`"Error adding image link"`); the new code lets it propagate to FastAPI's default 500. Same status (500), only a generic body instead of the specific message; `get_session()` closes/rolls back the poisoned transaction in its `finally` and each request gets a fresh session, so there is no DB corruption. (Correction from the original draft, which wrongly claimed the same image could be linked twice: the composite PK forbids that.) A cleaner `IntegrityError → ConflictError` (409) contract is deliberately left to the spec's deferred transaction-ownership follow-up, not added per-method here.

---

## Task 0 (git): Confirm the working branch and a green baseline

Not a code task. All new work stays on `feature/rbac-step1-service-layer`; `development` is never touched.

- [ ] **Step 1: Confirm the working branch**

```bash
git branch --show-current   # expect: feature/rbac-step1-service-layer
```

- [ ] **Step 2: Confirm the pre-existing suite is green before adding anything**

Run: `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/pytest -q`
Expected: the existing suite (foundation + Device/Patient/FormSchema/Study/Feature/Tag/Task slices) collects and passes (baseline: **191 passed**). **If anything is already red, stop and surface it — do not build on a red baseline.**

---

## Task 1: SubTaskRepository — by-id + image-link data access

Extend the existing `SubTaskRepository` (in `task_repository.py`) with the reads/lookups the `subtask.py` handlers perform inline today: a by-id fetch, a by-id image-eager-loaded fetch (shared by `GET ?with_images` and the post-mutation refetch), `PublicID`→`ImageInstanceID` resolution, the next `ImageIndex` for a subtask, and a link-by-key lookup. `get_by_id` and `get_image_link` are thin `session.get(...)` wrappers (existence lookups for patch/delete/add/remove), so — following the `devices`/`feature`/`tag`/`task` precedent — they get no dedicated Repository test (they are exercised through the Task 2/3 Service tests). No method commits; the Service owns the transaction boundary.

**Files:**
- Modify: `orm/eyened_orm/repositories/task_repository.py` (add 5 methods to `SubTaskRepository`)
- Modify: `orm/eyened_orm/tests/test_task_repository.py` (append `SubTaskRepository` image/lookup tests)

**Interfaces:**
- Consumes: `eyened_orm.SubTask`, `eyened_orm.SubTaskImageLink`, `eyened_orm.ImageInstance` (all already imported at the top of `task_repository.py`).
- Produces (added to `SubTaskRepository`, all take `session: Session` first):
  - `get_by_id(session, subtask_id: int) -> SubTask | None` — thin `session.get`.
  - `get_with_images(session, subtask_id: int) -> SubTask | None` — the subtask with the `_SUBTASK_IMAGE_LOADER` chain applied, or `None`.
  - `resolve_image_instance_id(session, public_id: str) -> int | None` — the `ImageInstanceID` for that `PublicID`, or `None`.
  - `next_image_index(session, subtask_id: int) -> int` — `max(ImageIndex)+1` over the subtask's links, or `0` if it has none.
  - `get_image_link(session, subtask_id: int, image_instance_id: int) -> SubTaskImageLink | None` — thin composite-key `session.get`.

- [ ] **Step 1: Write the failing test**

Append to `orm/eyened_orm/tests/test_task_repository.py` (the helpers `_creator`, `_task_def`, `_make_task`, `_make_subtask`, `_make_image` and the `SubTaskRepository` import already exist at the top of the file from 3a):

```python
def test_get_with_images_loads_link_chain(session):
    """get_with_images returns the subtask with its image links eager-loaded."""
    creator = _creator(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, creator.CreatorID)
    st = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    image_id = _make_image(session, "pub-1")
    from eyened_orm import SubTaskImageLink

    session.add(
        SubTaskImageLink(SubTaskID=st.SubTaskID, ImageInstanceID=image_id, ImageIndex=0)
    )
    session.flush()

    loaded = SubTaskRepository().get_with_images(session, st.SubTaskID)

    assert loaded is not None
    assert [link.ImageInstance.PublicID for link in loaded.SubTaskImageLinks] == ["pub-1"]


def test_resolve_image_instance_id_found_and_missing(session):
    """resolve_image_instance_id maps a PublicID to its int id, or None if absent."""
    image_id = _make_image(session, "pub-42")
    repo = SubTaskRepository()

    assert repo.resolve_image_instance_id(session, "pub-42") == image_id
    assert repo.resolve_image_instance_id(session, "nope") is None


def test_next_image_index_starts_at_zero_then_increments(session):
    """next_image_index is 0 for a subtask with no links, else max(ImageIndex)+1."""
    creator = _creator(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, creator.CreatorID)
    st = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    image_id = _make_image(session, "pub-1")
    repo = SubTaskRepository()

    assert repo.next_image_index(session, st.SubTaskID) == 0

    from eyened_orm import SubTaskImageLink

    session.add(
        SubTaskImageLink(SubTaskID=st.SubTaskID, ImageInstanceID=image_id, ImageIndex=3)
    )
    session.flush()

    assert repo.next_image_index(session, st.SubTaskID) == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest orm/eyened_orm/tests/test_task_repository.py -v`
Expected: FAIL — `AttributeError: 'SubTaskRepository' object has no attribute 'get_with_images'`.

- [ ] **Step 3: Add the methods**

Add these five methods to the `SubTaskRepository` class in `orm/eyened_orm/repositories/task_repository.py` (append after the existing `list_for_task` method). `SubTask`, `SubTaskImageLink`, `ImageInstance`, `func`, `select`, and `_SUBTASK_IMAGE_LOADER` are all already in scope in this module:

```python
    def get_by_id(self, session: Session, subtask_id: int) -> SubTask | None:
        """Return the subtask with the given id, or None if absent."""
        return session.get(SubTask, subtask_id)

    def get_with_images(self, session: Session, subtask_id: int) -> SubTask | None:
        """Return the subtask with its image links eager-loaded, or None."""
        return (
            session.execute(
                select(SubTask)
                .options(_SUBTASK_IMAGE_LOADER)
                .where(SubTask.SubTaskID == subtask_id)
            )
            .scalars()
            .first()
        )

    def resolve_image_instance_id(
        self, session: Session, public_id: str
    ) -> int | None:
        """Return the ImageInstanceID for a PublicID, or None if no image matches."""
        return session.scalar(
            select(ImageInstance.ImageInstanceID).where(
                ImageInstance.PublicID == public_id
            )
        )

    def next_image_index(self, session: Session, subtask_id: int) -> int:
        """Return the next ImageIndex for the subtask (max+1, or 0 if it has none)."""
        current_max = session.scalar(
            select(func.max(SubTaskImageLink.ImageIndex)).where(
                SubTaskImageLink.SubTaskID == subtask_id
            )
        )
        return 0 if current_max is None else current_max + 1

    def get_image_link(
        self, session: Session, subtask_id: int, image_instance_id: int
    ) -> SubTaskImageLink | None:
        """Return the link for (subtask_id, image_instance_id), or None if absent."""
        return session.get(
            SubTaskImageLink,
            {"SubTaskID": subtask_id, "ImageInstanceID": image_instance_id},
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest orm/eyened_orm/tests/test_task_repository.py -v`
Expected: PASS (12 passed — the 9 from 3a plus these 3).

- [ ] **Step 5: Commit**

```bash
git add orm/eyened_orm/repositories/task_repository.py orm/eyened_orm/tests/test_task_repository.py
git commit -m "feat(repositories): add SubTaskRepository by-id and image-link reads"
```

---

## Task 2: SubTaskService — by-id read/update/delete

Holds the per-subtask business rules the `subtask.py` handlers encode today (read one subtask ± images; update `Comments`/`TaskState`; delete), owns the commit, and emits audit logging via an injected logger. The only failure path is a missing subtask (`NotFoundError` → 404). Lives in `task_service.py` alongside `TaskService`. The constructor takes just the `SubTaskRepository`; the default factory wires it plus the real logger.

**Files:**
- Modify: `server/services/task_service.py` (add `SubTaskService` + `get_subtask_service`)
- Modify: `server/services/__init__.py` (re-export `SubTaskService`)
- Test: `server/tests/test_subtask_service.py`

**Interfaces:**
- Consumes: `SubTaskRepository` (existing, extended in Task 1); `NotFoundError` (existing); `ActingUser` (existing); `DatabaseModificationLogger`/`get_db_logger` (`server/utils/db_logging.py`); `eyened_orm.SubTask`, `eyened_orm.task.SubTaskState`.
- Produces:
  - `SubTaskService(subtask_repository: SubTaskRepository, logger: DatabaseModificationLogger | None = None)`.
  - `get_subtask(session, subtask_id: int, *, with_images: bool) -> SubTask` — the subtask (image-loaded iff `with_images`); 404 if absent.
  - `update_subtask(session, subtask_id: int, comments: str | None, task_state: SubTaskState | None, actor: ActingUser) -> SubTask` — each field optional; 404 if absent.
  - `delete_subtask(session, subtask_id: int, actor: ActingUser) -> None` — 404 if absent.
  - `get_subtask_service() -> SubTaskService` — default-wiring factory (`SubTaskRepository()` + `get_db_logger()`).

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_subtask_service.py`:

```python
import pytest

from eyened_orm import Creator, SubTask, Task, TaskDefinition
from eyened_orm.task import SubTaskState, TaskState
from eyened_orm.repositories.task_repository import SubTaskRepository

from server.services.acting_user import ActingUser
from server.services.exceptions import NotFoundError
from server.services.task_service import SubTaskService


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


def _actor(session) -> ActingUser:
    creator = Creator(CreatorName="alice", IsHuman=True)
    session.add(creator)
    session.flush()
    return ActingUser(id=creator.CreatorID, username=creator.CreatorName)


def _task_def(session, name: str = "td") -> TaskDefinition:
    td = TaskDefinition(TaskDefinitionName=name)
    session.add(td)
    session.flush()
    return td


def _make_task(session, td_id: int, creator_id: int, name: str = "T") -> Task:
    task = Task(
        TaskName=name,
        TaskDefinitionID=td_id,
        CreatorID=creator_id,
        TaskState=TaskState.NotStarted,
    )
    session.add(task)
    session.flush()
    return task


def _make_subtask(session, task_id: int, state: SubTaskState = SubTaskState.NotStarted) -> SubTask:
    st = SubTask(TaskID=task_id, TaskState=state, Comments="orig")
    session.add(st)
    session.flush()
    return st


def _service(logger=None) -> SubTaskService:
    return SubTaskService(SubTaskRepository(), logger=logger)


def test_get_subtask_returns_it(session):
    """get_subtask returns the subtask at the given id."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    session.commit()

    got = _service().get_subtask(session, st.SubTaskID, with_images=False)

    assert got.SubTaskID == st.SubTaskID


def test_get_subtask_unknown_raises_not_found(session):
    """Getting a missing subtask is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().get_subtask(session, 999_999, with_images=False)


def test_update_subtask_changes_fields(session):
    """update_subtask overwrites the provided comments and task_state."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    session.commit()

    updated = _service().update_subtask(
        session, st.SubTaskID, "newcomment", SubTaskState.Ready, actor
    )

    assert updated.Comments == "newcomment"
    assert updated.TaskState == SubTaskState.Ready


def test_update_subtask_unknown_raises_not_found(session):
    """Updating a missing subtask is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    with pytest.raises(NotFoundError):
        _service().update_subtask(session, 999_999, "x", None, actor)


def test_update_subtask_logs_update(session):
    """update_subtask emits one update audit record for the SubTask entity."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    session.commit()
    logger = FakeAuditLogger()

    _service(logger).update_subtask(session, st.SubTaskID, "c", None, actor)

    assert len(logger.updates) == 1
    assert logger.updates[0]["entity"] == "SubTask"


def test_delete_subtask_removes_it(session):
    """delete_subtask removes the subtask row."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    session.commit()

    _service().delete_subtask(session, st.SubTaskID, actor)

    assert SubTaskRepository().get_by_id(session, st.SubTaskID) is None


def test_delete_subtask_unknown_raises_not_found(session):
    """Deleting a missing subtask is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    with pytest.raises(NotFoundError):
        _service().delete_subtask(session, 999_999, actor)


def test_delete_subtask_logs_delete(session):
    """delete_subtask emits one delete audit record for the SubTask entity."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    session.commit()
    logger = FakeAuditLogger()

    _service(logger).delete_subtask(session, st.SubTaskID, actor)

    assert len(logger.deletes) == 1
    assert logger.deletes[0]["entity"] == "SubTask"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest server/tests/test_subtask_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'SubTaskService' from 'server.services.task_service'`.

- [ ] **Step 3: Write the service**

Add `SubTaskService` and `get_subtask_service` to `server/services/task_service.py`. Insert the `SubTaskService` class after the `TaskService` class and before the module-level `get_task_service` function; add `get_subtask_service` at the end of the module. (`SubTask`, `SubTaskState`, `SubTaskRepository`, `Session`, `ActingUser`, `NotFoundError`, `DatabaseModificationLogger`, `get_db_logger` are all already imported at the top of the file from 3a.)

```python
class SubTaskService:
    """Business logic for individual subtasks and their image links."""

    def __init__(
        self,
        subtask_repository: SubTaskRepository,
        logger: DatabaseModificationLogger | None = None,
    ) -> None:
        self.subtasks = subtask_repository
        self.logger = logger

    def get_subtask(
        self, session: Session, subtask_id: int, *, with_images: bool
    ) -> SubTask:
        """Return a subtask, image-loaded iff ``with_images``.

        Raises:
            NotFoundError: If the subtask does not exist.
        """
        subtask = (
            self.subtasks.get_with_images(session, subtask_id)
            if with_images
            else self.subtasks.get_by_id(session, subtask_id)
        )
        if subtask is None:
            raise NotFoundError(f"SubTask {subtask_id} not found")
        return subtask

    def update_subtask(
        self,
        session: Session,
        subtask_id: int,
        comments: str | None,
        task_state: SubTaskState | None,
        actor: ActingUser,
    ) -> SubTask:
        """Update a subtask's comments/state (each optional).

        Raises:
            NotFoundError: If the subtask does not exist.
        """
        subtask = self.subtasks.get_by_id(session, subtask_id)
        if subtask is None:
            raise NotFoundError(f"SubTask {subtask_id} not found")

        changes: dict[str, str] = {}
        if comments is not None:
            changes["comments"] = f"{subtask.Comments} -> {comments}"
            subtask.Comments = comments
        if task_state is not None:
            changes["task_state"] = f"{subtask.TaskState} -> {task_state}"
            subtask.TaskState = task_state

        session.commit()
        session.refresh(subtask)
        if self.logger is not None:
            self.logger.log_update(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"PATCH /api/subtasks/{subtask_id}",
                entity="SubTask",
                entity_id=subtask_id,
                changes=changes if changes else None,
            )
        return subtask

    def delete_subtask(
        self, session: Session, subtask_id: int, actor: ActingUser
    ) -> None:
        """Delete a subtask (its image links cascade at the DB level).

        Raises:
            NotFoundError: If the subtask does not exist.
        """
        subtask = self.subtasks.get_by_id(session, subtask_id)
        if subtask is None:
            raise NotFoundError(f"SubTask {subtask_id} not found")

        deleted_data = {
            "task_id": subtask.TaskID,
            "comments": subtask.Comments,
            "task_state": str(subtask.TaskState) if subtask.TaskState else None,
            "creator_id": subtask.CreatorID,
        }
        session.delete(subtask)
        session.commit()
        if self.logger is not None:
            self.logger.log_delete(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"DELETE /api/subtasks/{subtask_id}",
                entity="SubTask",
                entity_id=subtask_id,
                deleted_data=deleted_data,
            )
        return None
```

Add at the very end of the module (after `get_task_service`):

```python
def get_subtask_service() -> SubTaskService:
    """Default SubTaskService wiring for FastAPI ``Depends()``."""
    return SubTaskService(SubTaskRepository(), logger=get_db_logger())
```

Update `server/services/__init__.py` (add the import + `__all__` entry, keeping all existing exports):

```python
from .task_service import SubTaskService, TaskService
```

```python
    "TaskService",
    "SubTaskService",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest server/tests/test_subtask_service.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add server/services/task_service.py server/services/__init__.py server/tests/test_subtask_service.py
git commit -m "feat(services): add SubTaskService with subtask CRUD and injected audit logging"
```

---

## Task 3: SubTaskService — image link add/remove

Adds the two image-link mutations behind `POST /subtasks/{id}/images` (append a link at the next `ImageIndex`) and `DELETE /subtasks/{id}/images/{instance_id}` (remove a link by its image's `PublicID`). Both preserve today's lookup order and failure paths: add checks the subtask first (404) then resolves the image (404); remove resolves the image first (404) then the link (404). Both return the subtask re-fetched with its images so the route can serialize the updated set. See the "Behavior-preserving decisions" note in the header about dropping the old broad `except → 500`.

**Files:**
- Modify: `server/services/task_service.py` (add two methods to `SubTaskService`)
- Modify: `server/tests/test_subtask_service.py` (append tests + image-graph helper)

**Interfaces:**
- Consumes: `SubTaskRepository.get_by_id`, `.resolve_image_instance_id`, `.next_image_index`, `.get_image_link`, `.get_with_images` (Task 1); `eyened_orm.SubTaskImageLink`.
- Produces (added to `SubTaskService`):
  - `add_image(session, subtask_id: int, image_public_id: str, actor: ActingUser) -> SubTask` — appends a link at the next `ImageIndex`, returns the image-loaded subtask; 404 if the subtask or the image is absent.
  - `remove_image(session, subtask_id: int, image_public_id: str, actor: ActingUser) -> SubTask` — removes the link for that image, returns the image-loaded subtask; 404 if the image or the link is absent.

- [ ] **Step 1: Write the failing test**

Append to `server/tests/test_subtask_service.py`:

```python
def _make_image(session, public_id: str) -> int:
    """Build the minimal Series/Device graph an ImageInstance FK-requires.

    Returns the new ImageInstanceID (mirrors the helper in test_task_repository.py).
    """
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

    project = Project(ProjectName="P", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier="ID1", ProjectID=project.ProjectID)
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
        DatasetIdentifier="ds",
    )
    session.add(image)
    session.flush()
    return image.ImageInstanceID


def test_add_image_appends_link_at_next_index(session):
    """add_image links the image to the subtask at the next ImageIndex."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    _make_image(session, "pub-1")
    session.commit()

    updated = _service().add_image(session, st.SubTaskID, "pub-1", actor)

    assert [link.ImageInstance.PublicID for link in updated.SubTaskImageLinks] == ["pub-1"]
    assert [link.ImageIndex for link in updated.SubTaskImageLinks] == [0]


def test_add_image_second_image_gets_next_index(session):
    """A second add_image lands at ImageIndex 1, keeping insertion order."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    _make_image(session, "pub-1")
    _make_image(session, "pub-2")
    session.commit()
    service = _service()

    service.add_image(session, st.SubTaskID, "pub-1", actor)
    updated = service.add_image(session, st.SubTaskID, "pub-2", actor)

    assert [link.ImageIndex for link in updated.SubTaskImageLinks] == [0, 1]


def test_add_image_unknown_subtask_raises_not_found(session):
    """add_image on a missing subtask is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    session.commit()
    with pytest.raises(NotFoundError):
        _service().add_image(session, 999_999, "pub-1", actor)


def test_add_image_unknown_image_raises_not_found(session):
    """add_image with an unknown PublicID is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    session.commit()
    with pytest.raises(NotFoundError):
        _service().add_image(session, st.SubTaskID, "nope", actor)


def test_add_image_logs_insert(session):
    """add_image emits one insert audit record for the SubTaskImageLink entity."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    _make_image(session, "pub-1")
    session.commit()
    logger = FakeAuditLogger()

    _service(logger).add_image(session, st.SubTaskID, "pub-1", actor)

    assert len(logger.inserts) == 1
    assert logger.inserts[0]["entity"] == "SubTaskImageLink"


def test_remove_image_deletes_the_link(session):
    """remove_image deletes the link for that image, leaving the subtask empty."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    _make_image(session, "pub-1")
    session.commit()
    service = _service()
    service.add_image(session, st.SubTaskID, "pub-1", actor)

    updated = service.remove_image(session, st.SubTaskID, "pub-1", actor)

    assert updated.SubTaskImageLinks == []


def test_remove_image_unknown_image_raises_not_found(session):
    """remove_image with an unknown PublicID is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    session.commit()
    with pytest.raises(NotFoundError):
        _service().remove_image(session, st.SubTaskID, "nope", actor)


def test_remove_image_unlinked_image_raises_not_found(session):
    """remove_image for an image not linked to the subtask raises NotFoundError."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    _make_image(session, "pub-1")  # exists, but never linked
    session.commit()
    with pytest.raises(NotFoundError):
        _service().remove_image(session, st.SubTaskID, "pub-1", actor)


def test_remove_image_logs_delete(session):
    """remove_image emits one delete audit record for the SubTaskImageLink entity."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    _make_image(session, "pub-1")
    session.commit()
    service = _service()
    service.add_image(session, st.SubTaskID, "pub-1", actor)
    logger = FakeAuditLogger()
    SubTaskService(SubTaskRepository(), logger=logger).remove_image(
        session, st.SubTaskID, "pub-1", actor
    )

    assert len(logger.deletes) == 1
    assert logger.deletes[0]["entity"] == "SubTaskImageLink"
```

> **Note — imports:** `SubTaskImageLink` is only needed inside the Service (Task 3 body), not the test. The test builds links via `add_image`, so no extra test import beyond `_make_image`'s local imports is required.

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest server/tests/test_subtask_service.py -v`
Expected: FAIL — `AttributeError: 'SubTaskService' object has no attribute 'add_image'`.

- [ ] **Step 3: Add the two methods**

Add these methods to the `SubTaskService` class in `server/services/task_service.py` (after `delete_subtask`, before the module-level factories). Add `SubTaskImageLink` to the top-of-file `eyened_orm` import (currently `from eyened_orm import SubTask, Task`):

```python
# extend the existing top-of-file import:
from eyened_orm import SubTask, SubTaskImageLink, Task
```

```python
    def add_image(
        self,
        session: Session,
        subtask_id: int,
        image_public_id: str,
        actor: ActingUser,
    ) -> SubTask:
        """Link an image (by PublicID) to a subtask at the next ImageIndex.

        Raises:
            NotFoundError: If the subtask or the image does not exist.
        """
        if self.subtasks.get_by_id(session, subtask_id) is None:
            raise NotFoundError(f"SubTask {subtask_id} not found")
        image_instance_id = self.subtasks.resolve_image_instance_id(
            session, image_public_id
        )
        if image_instance_id is None:
            raise NotFoundError("ImageInstance not found")

        link = SubTaskImageLink(
            SubTaskID=subtask_id,
            ImageInstanceID=image_instance_id,
            ImageIndex=self.subtasks.next_image_index(session, subtask_id),
        )
        session.add(link)
        session.commit()
        if self.logger is not None:
            self.logger.log_insert(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"POST /api/subtasks/{subtask_id}/images",
                entity="SubTaskImageLink",
                fields={
                    "subtask_id": subtask_id,
                    "image_instance_id": image_instance_id,
                },
            )
        return self.subtasks.get_with_images(session, subtask_id)

    def remove_image(
        self,
        session: Session,
        subtask_id: int,
        image_public_id: str,
        actor: ActingUser,
    ) -> SubTask:
        """Unlink an image (by PublicID) from a subtask.

        Raises:
            NotFoundError: If the image or the (subtask, image) link is absent.
        """
        image_instance_id = self.subtasks.resolve_image_instance_id(
            session, image_public_id
        )
        if image_instance_id is None:
            raise NotFoundError("ImageInstance not found")
        link = self.subtasks.get_image_link(session, subtask_id, image_instance_id)
        if link is None:
            raise NotFoundError("Link not found")

        session.delete(link)
        session.commit()
        if self.logger is not None:
            self.logger.log_delete(
                user=actor.username,
                user_id=actor.id,
                endpoint=(
                    f"DELETE /api/subtasks/{subtask_id}/images/{image_public_id}"
                ),
                entity="SubTaskImageLink",
                deleted_data={
                    "subtask_id": subtask_id,
                    "image_instance_id": image_instance_id,
                },
            )
        return self.subtasks.get_with_images(session, subtask_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest server/tests/test_subtask_service.py -v`
Expected: PASS (17 passed — the 8 from Task 2 plus these 9).

- [ ] **Step 5: Commit**

```bash
git add server/services/task_service.py server/tests/test_subtask_service.py
git commit -m "feat(services): add SubTaskService image-link add/remove"
```

---

## Task 4: Route `subtask.py` through `SubTaskService`

Rewrite the five `subtask.py` handlers to be thin: parse → build `ActingUser` → call `SubTaskService` → `DTOConverter` → return. No handler contains inline queries, `raise HTTPException`, `session.commit`, or direct `get_db_logger()` calls anymore — those move into the Service; the central `NotFoundError` handler (already registered) maps the 404s. The `SubTaskPATCH` and `AddImageRequest` request bodies stay defined inline in `subtask.py`; `SubTaskPATCH.task_state` is retyped to the `SubTaskState` enum (see header decision #1). Verified by the full suite still passing and an app-boot smoke check — matching how 3a's `task.py` refactor was verified (no route-level test files exist for these slices).

**Files:**
- Modify: `server/routes/subtask.py` (full rewrite of the 5 handlers + inline DTOs)

**Interfaces:**
- Consumes: `SubTaskService`, `get_subtask_service` (Task 2/3); `ActingUser` (existing); `DTOConverter` (existing); `eyened_orm.task.SubTaskState`.
- Produces: no new symbols other Python imports — this is the HTTP boundary.

- [ ] **Step 1: Rewrite the route module**

Replace the entire contents of `server/routes/subtask.py` with:

```python
from typing import Optional, Union

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from eyened_orm.task import SubTaskState

from ..db import get_db
from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_tasks import SubTaskGET, SubTaskWithImagesGET
from ..services.acting_user import ActingUser
from ..services.task_service import SubTaskService, get_subtask_service
from .auth import CurrentUser, get_current_user

router = APIRouter()


class SubTaskPATCH(BaseModel):
    comments: Optional[str] = None
    task_state: Optional[SubTaskState] = None


class AddImageRequest(BaseModel):
    instance_id: str


@router.get(
    "/subtasks/{subtaskid}", response_model=Union[SubTaskWithImagesGET, SubTaskGET]
)
async def get_subtask(
    subtaskid: int,
    with_images: bool = False,
    db: Session = Depends(get_db),
    service: SubTaskService = Depends(get_subtask_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single subtask, optionally with its images."""
    st = service.get_subtask(db, subtaskid, with_images=with_images)
    if with_images:
        return DTOConverter.subtask_with_images_to_get(st)
    return DTOConverter.subtask_to_get(st)


@router.patch("/subtasks/{subtaskid}", response_model=SubTaskGET)
async def patch_subtask(
    subtaskid: int,
    dto: SubTaskPATCH,
    db: Session = Depends(get_db),
    service: SubTaskService = Depends(get_subtask_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a subtask's comments and/or state."""
    st = service.update_subtask(
        db,
        subtaskid,
        dto.comments,
        dto.task_state,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.subtask_to_get(st)


@router.delete("/subtasks/{subtaskid}", status_code=204)
async def delete_subtask(
    subtaskid: int,
    db: Session = Depends(get_db),
    service: SubTaskService = Depends(get_subtask_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a subtask."""
    service.delete_subtask(
        db,
        subtaskid,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return Response(status_code=204)


@router.post("/subtasks/{subtaskid}/images", response_model=SubTaskWithImagesGET)
async def add_subtask_image(
    subtaskid: int,
    body: AddImageRequest,
    db: Session = Depends(get_db),
    service: SubTaskService = Depends(get_subtask_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Link an image to a subtask at the next available index."""
    st = service.add_image(
        db,
        subtaskid,
        body.instance_id,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.subtask_with_images_to_get(st)


@router.delete(
    "/subtasks/{subtaskid}/images/{instance_id}", response_model=SubTaskWithImagesGET
)
async def remove_subtask_image(
    subtaskid: int,
    instance_id: str,
    db: Session = Depends(get_db),
    service: SubTaskService = Depends(get_subtask_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Unlink an image from a subtask."""
    st = service.remove_image(
        db,
        subtaskid,
        instance_id,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.subtask_with_images_to_get(st)
```

- [ ] **Step 2: App-boot smoke check (imports + routes register)**

Run:

```bash
EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password \
  dev/.venv/bin/python -c "
from server.main import app
paths = {r.path for r in app.routes}
assert '/api/subtasks/{subtaskid}' in paths, sorted(p for p in paths if 'subtask' in p)
assert '/api/subtasks/{subtaskid}/images' in paths
assert '/api/subtasks/{subtaskid}/images/{instance_id}' in paths
print('subtask routes OK')
"
```

Expected: prints `subtask routes OK` (the app imports cleanly and every rewritten subtask route is registered under the `/api` prefix).

- [ ] **Step 3: Run the full suite to confirm no regression**

Run: `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/pytest -q`
Expected: PASS — **211 passed** (191 baseline + 3 repository tests from Task 1 + 17 service tests from Tasks 2–3), no failures.

- [ ] **Step 4: Commit**

```bash
git add server/routes/subtask.py
git commit -m "refactor(routes): route subtask endpoints through SubTaskService"
```

---

## Phase 3b done — completes spec Phase 3

After Task 4, `subtask.py` no longer queries the ORM directly: it parses, calls `SubTaskService`, and converts DTOs. Together with 3a (`task.py`/`TaskService`), this finishes the spec's **Phase 3**. Do **not** merge `feature/rbac-step1-service-layer` to `development`; the next slice is spec **Phase 4** (`import_api.py`, `instances.py`, `form_annotations.py`, `segmentations.py`), a separate plan.

Update the `rbac-step1-migration-state` memory: subtask (3b) done; Phase 3 complete; Phase 4 next; test count **211**.
