# task Repository/Service Migration (RBAC Step 1, Phase 3a) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route the `task.py` endpoints — task CRUD (`POST/GET/GET{id}/PATCH{id}/DELETE{id} /task`) plus the task-rooted subtask reads (`GET /task/{id}/subtasks`, `GET /task/{id}/subtask/{index}`) — through a `TaskService` backed by a `TaskRepository` + `SubTaskRepository`, committing directly onto the current `feature/rbac-step1-service-layer` branch (never touching `development`).

**Architecture:** Same layering as the reviewed Device/Patient/FormSchema/Study/Feature/Tag slices — thin route (parse → Service → `DTOConverter` → return), a Service with constructor-injected Repositories that raises domain exceptions and owns the commit, and framework-agnostic Repositories that take a `Session`. This phase splits the spec's "Phase 3" (which groups `task.py` + `subtask.py`) into **3a (`task.py`, this plan)** and **3b (`subtask.py`, a later plan)**, mirroring how Phase 2 was executed as 2a/2b/2c for reviewability. To keep a class from being split across two PRs, the **task-rooted subtask reads live in `TaskService`** (they hang off a `task_id` and are served by `task.py`); **`SubTaskService`** — the by-id subtask CRUD and image-link mutations under `/subtasks/...` — is introduced wholly in **3b**.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (ORM `eyened_orm`), pytest with the in-memory SQLite `session` fixture.

## Global Constraints

Copied verbatim from `docs/superpowers/specs/2026-07-03-repository-service-layer-design.md`. Every task implicitly includes these:

- **Filenames:** snake_case, one file per model module — `task_repository.py`, `task_service.py`. Per the spec's directory table, `task_repository.py` holds `TaskRepository`, `SubTaskRepository` (and `TaskDefinitionRepository` *if needed* — it is **not** needed here: no endpoint does TaskDefinition CRUD, so YAGNI); `task_service.py` holds `TaskService` (and `SubTaskService`, added in 3b).
- **Class names:** `TaskRepository` / `SubTaskRepository` / `TaskService`.
- **Repositories** live in `orm/eyened_orm/repositories/`, take a `Session` as a method argument (never own/create sessions), have no FastAPI imports, and return `None`/empty on "not found" — never raise HTTP-shaped errors.
- **Services** live in `server/services/`, receive their Repositories via constructor injection, and raise the domain exceptions in `server/services/exceptions.py` — **never** raise `HTTPException` directly.
- **DTO conversion stays at the route boundary** (via `DTOConverter`), never inside a Service.
- **Package `__init__.py` files re-export** their public classes (with `__all__`), keeping all existing exports.
- **No mocking library.** DB-backed tests use the real in-memory SQLite `session` fixture (already exposed to `server/tests/` by the foundation's `server/tests/conftest.py`). Any non-DB fake is a small hand-rolled object.
- **Do not touch:** CLI/worker code, `search.py`, `auth.py`, `Base`'s generic classmethods, `subtask.py` (that is 3b), or the pre-existing Device/Patient/FormSchema/Study/Feature/Tag slices.
- **Repository tests** → `orm/eyened_orm/tests/`; **Service tests** → `server/tests/`.

### Conventions reused from the `studies`/`feature`/`tag` phases

- **Commit ownership:** `get_db` (`server/db.py`) yields a session that is only *closed*, never committed, by its context manager. Every mutating Service method calls `session.commit()` itself — the Service is the transaction boundary.
- **Audit logging is injected, not global-reached.** The Service takes `logger: DatabaseModificationLogger | None = None` via its constructor and calls it inside the mutating method. `get_task_service()` wires the real logger via `get_db_logger()`; Service tests inject `None` or a small hand-rolled fake. Every logging call stays guarded by `if self.logger is not None:` (matching today's `if logger:` guard, since `get_db_logger()` returns `None` when DB logging is disabled).
- **Acting user:** routes map their handler-layer `CurrentUser` onto the framework-agnostic `ActingUser(id, username)` value object (`server/services/acting_user.py`, already exists) before calling a Service.

> **Interpreter note:** no `python`/`pytest` on `PATH`; the venv is at `dev/.venv`. Every command uses `dev/.venv/bin/python` / `dev/.venv/bin/pytest`. The two commands that import `server.*` (router-introspection / app-boot checks) need dummy DB env vars, mirroring `server/tests/conftest.py`: prefix them with `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password`.

> **Reused from earlier work on `feature/rbac-step1-service-layer`:** `NotFoundError` and the central handler (`server/services/exceptions.py`, registered in `server/main.py` via `register_exception_handlers` — the handler dispatches every `ServiceError` subclass by MRO, so this phase needs **no** `main.py` change); the `session` fixture already imported in `server/tests/conftest.py`; the `ActingUser` value object; both `repositories/` and `services/` packages with their `__init__.py` re-exports. **`task.router` is already registered** in `server/main.py` (`app_api.include_router(task.router)`), so no registration change is needed either. This phase introduces **no new exception type**: every `task.py` failure path today is a 404 (`GET`/`PATCH`/`DELETE` on a missing task; `GET /task/{id}/subtask/{index}` out of range), all served by the existing `NotFoundError`.

> **Existing ORM facts confirmed for this plan** (verified against the in-memory SQLite test DB, `PRAGMA foreign_keys=ON`):
> - `Task` (`orm/eyened_orm/task.py`): `TaskID` (PK); `TaskName` (`String(256)`, NOT NULL); `Description` (`Text`, nullable); `CreatorID` (**nullable FK → `Creator.CreatorID`**); `ContactID` (**nullable FK → `Contact.ContactID`**); `TaskDefinitionID` (**NOT NULL FK → `TaskDefinition.TaskDefinitionID`**); `TaskState` (`Mapped["TaskState"]`, **NOT NULL, no column/server default**); `DateInserted` (server default). Relationships `Creator`, `TaskDefinition`, `Contact`, and `SubTasks` (`passive_deletes=True`).
> - **`TaskState` is NOT NULL with no default.** Today's `POST /task` handler does *not* set it, relying on MySQL's implicit enum default (the first member, `NotStarted`). SQLite rejects that insert. `create_from_imagesets` (`task.py`) sets `TaskState=TaskState.NotStarted` explicitly. So `TaskService.create_task` **sets `TaskState.NotStarted` explicitly** — behavior-preserving (same value MySQL implicitly picks) and portable to SQLite. `TaskState` enum members: `NotStarted`, `Busy`, `Finished`, `Aborted`, `Archived`.
> - `SubTask` (`orm/eyened_orm/task.py`): `SubTaskID` (PK); `TaskID` (**NOT NULL FK → `Task.TaskID`, `ondelete="CASCADE"`**); `CreatorID` (nullable FK); `Comments` (`Text`, nullable); `TaskState` (`Mapped["SubTaskState"]`, **column default `SubTaskState.NotStarted`** — a minimal `SubTask(TaskID=...)` inserts fine). `SubTaskState` members: `NotStarted`, `Busy`, `Ready`. `SubTaskImageLinks` relationship ordered by `ImageIndex`.
> - **`session.delete(task)` cascades** to the task's `SubTask` rows via the DB-level `ON DELETE CASCADE` + `passive_deletes=True` (verified: task gone, subtasks gone, no FK error). So `delete_task` uses ORM `session.delete`, not a Core `delete()` statement.
> - The `with_images` eager-load chain `selectinload(SubTask.SubTaskImageLinks).selectinload(SubTaskImageLink.ImageInstance).selectinload(ImageInstance.ImageStorages).selectinload(ImageStorage.StorageBackend)` is valid and populates links. A real `ImageInstance` row requires a `Series`→`Study`→`Patient`→`Project` chain **and** a `DeviceInstance`→`DeviceModel`; the Task 2 test helper builds exactly that minimal graph. (DTO conversion of images — `image_instance_to_get` — stays at the route boundary and is covered by route-level smoke tests, not here.)

> **DTO facts confirmed:** `DTOConverter.task_to_get(task, *, num_tasks, num_tasks_ready)` (`dto_converter.py:619`) reads `TaskID/TaskName/Description/ContactID/TaskDefinitionID/DateInserted/Creator/TaskState/TaskDefinition`; `subtask_to_get` / `subtask_with_images_to_get` (`dto_converter.py:654`/`:665`) build `SubTaskGET`/`SubTaskWithImagesGET`. `TaskPUT(name, description, contact_id, task_definition_id)`, `TaskPATCH(name?, description?, contact_id?, task_definition_id?, task_state?: TaskState)`, and the `SubTasksResponse`/`SubTasksWithImagesResponse` envelopes all live in `server/dtos/dtos_tasks.py`. All DTO calls stay in the route.

---

## Task 0 (git): Confirm the working branch and a green baseline

Not a code task. All new work stays on `feature/rbac-step1-service-layer`; `development` is never touched.

- [ ] **Step 1: Confirm the working branch**

```bash
git branch --show-current   # expect: feature/rbac-step1-service-layer
```

- [ ] **Step 2: Confirm the pre-existing suite is green before adding anything**

Run: `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/pytest -q`
Expected: the existing suite (foundation + Device/Patient/FormSchema/Study/Feature/Tag slices) collects and passes (baseline: **165 passed**). **If anything is already red, stop and surface it — do not build on a red baseline.**

---

## Task 1: TaskRepository

Named read/query methods for the task lookups the `task.py` handlers perform inline today. Extracts the `_task_query_options()` eager-load (`Creator` + `TaskDefinition`, avoiding a fan-out over every `SubTask`) into `get_with_relations`/`list_all`, and the `_subtask_counts_by_task_id` aggregate into `subtask_counts`. `get_by_id` is a thin `session.get(...)` wrapper (existence lookup for update/delete/subtask-route checks), so — following the `devices`/`feature`/`tag` precedent — it gets no dedicated Repository test (it is exercised through the Task 3/4 Service tests). No method commits; the Service owns the transaction boundary.

**Files:**
- Create: `orm/eyened_orm/repositories/task_repository.py`
- Modify: `orm/eyened_orm/repositories/__init__.py` (add `TaskRepository`)
- Test: `orm/eyened_orm/tests/test_task_repository.py`

**Interfaces:**
- Consumes: `eyened_orm.Task`, `eyened_orm.SubTask`, `eyened_orm.task.SubTaskState`.
- Produces (all take `session: Session` first):
  - `get_by_id(session, task_id: int) -> Task | None`
  - `get_with_relations(session, task_id: int) -> Task | None` — one task with `Creator` + `TaskDefinition` eager-loaded, or `None`.
  - `list_all(session) -> list[Task]` — every task ordered by `TaskID`, with `Creator` + `TaskDefinition` eager-loaded.
  - `subtask_counts(session, task_ids: list[int]) -> dict[int, tuple[int, int]]` — `{task_id: (num_subtasks, num_ready)}`, filling `(0, 0)` for every requested id with no subtasks; `{}` for an empty `task_ids`.

- [ ] **Step 1: Write the failing test**

Create `orm/eyened_orm/tests/test_task_repository.py`:

```python
from eyened_orm import Creator, SubTask, Task, TaskDefinition
from eyened_orm.task import SubTaskState, TaskState
from eyened_orm.repositories.task_repository import TaskRepository


def _creator(session, name: str = "tester") -> Creator:
    creator = Creator(CreatorName=name, IsHuman=True)
    session.add(creator)
    session.flush()
    return creator


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


def _make_subtask(session, task_id: int, state: SubTaskState) -> SubTask:
    st = SubTask(TaskID=task_id, TaskState=state)
    session.add(st)
    session.flush()
    return st


def test_list_all_orders_by_id_with_relations(session):
    """list_all returns every task in TaskID order, Creator/TaskDefinition eager."""
    creator = _creator(session)
    td = _task_def(session)
    _make_task(session, td.TaskDefinitionID, creator.CreatorID, "A")
    _make_task(session, td.TaskDefinitionID, creator.CreatorID, "B")

    tasks = TaskRepository().list_all(session)

    assert [t.TaskName for t in tasks] == ["A", "B"]
    # Eager-loaded: reading these needs no extra lazy query.
    assert tasks[0].Creator.CreatorName == "tester"
    assert tasks[0].TaskDefinition.TaskDefinitionName == "td"


def test_get_with_relations_eager_loads_creator_and_definition(session):
    """get_with_relations returns the task with Creator + TaskDefinition loaded."""
    creator = _creator(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, creator.CreatorID)

    loaded = TaskRepository().get_with_relations(session, task.TaskID)

    assert loaded is not None
    assert loaded.Creator.CreatorName == "tester"
    assert loaded.TaskDefinition.TaskDefinitionName == "td"


def test_subtask_counts_totals_and_ready(session):
    """subtask_counts returns (total, ready) per task id."""
    creator = _creator(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, creator.CreatorID)
    _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    _make_subtask(session, task.TaskID, SubTaskState.Ready)
    _make_subtask(session, task.TaskID, SubTaskState.Ready)

    counts = TaskRepository().subtask_counts(session, [task.TaskID])

    assert counts[task.TaskID] == (3, 2)


def test_subtask_counts_fills_zero_for_task_without_subtasks(session):
    """A requested task id with no subtasks maps to (0, 0), not a missing key."""
    creator = _creator(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, creator.CreatorID)

    counts = TaskRepository().subtask_counts(session, [task.TaskID])

    assert counts == {task.TaskID: (0, 0)}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest orm/eyened_orm/tests/test_task_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eyened_orm.repositories.task_repository'`.

- [ ] **Step 3: Write the repository**

Create `orm/eyened_orm/repositories/task_repository.py`:

```python
from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from eyened_orm import (
    ImageInstance,
    ImageStorage,
    SubTask,
    SubTaskImageLink,
    Task,
)
from eyened_orm.task import SubTaskState

# Load task metadata without eager-loading every SubTask row (mirrors the
# route's former ``_task_query_options``).
_TASK_RELATIONS = (
    selectinload(Task.Creator),
    selectinload(Task.TaskDefinition),
)


class TaskRepository:
    """Data access for Task rows and their subtask counts."""

    def get_by_id(self, session: Session, task_id: int) -> Task | None:
        """Return the task with the given id, or None if absent."""
        return session.get(Task, task_id)

    def get_with_relations(self, session: Session, task_id: int) -> Task | None:
        """Return the task with Creator + TaskDefinition eager-loaded, or None."""
        return (
            session.execute(
                select(Task).options(*_TASK_RELATIONS).where(Task.TaskID == task_id)
            )
            .scalars()
            .first()
        )

    def list_all(self, session: Session) -> list[Task]:
        """Return all tasks (TaskID order) with Creator + TaskDefinition loaded."""
        return list(
            session.execute(
                select(Task).options(*_TASK_RELATIONS).order_by(Task.TaskID)
            )
            .scalars()
            .all()
        )

    def subtask_counts(
        self, session: Session, task_ids: list[int]
    ) -> dict[int, tuple[int, int]]:
        """Return {task_id: (num_subtasks, num_ready)} for the given task ids.

        One grouped aggregate over ``SubTask`` (mirrors the route's former
        ``_subtask_counts_by_task_id``). Every requested id is present in the
        result: ids with no subtasks map to ``(0, 0)``.
        """
        if not task_ids:
            return {}
        rows = session.execute(
            select(
                SubTask.TaskID,
                func.count().label("num"),
                func.coalesce(
                    func.sum(
                        case((SubTask.TaskState == SubTaskState.Ready, 1), else_=0)
                    ),
                    0,
                ).label("ready"),
            )
            .where(SubTask.TaskID.in_(task_ids))
            .group_by(SubTask.TaskID)
        ).all()
        counts = {int(tid): (int(n), int(r)) for tid, n, r in rows}
        return {tid: counts.get(tid, (0, 0)) for tid in task_ids}
```

Update `orm/eyened_orm/repositories/__init__.py` (add the new import + `__all__` entry, keeping all existing exports):

```python
from .device_repository import DeviceRepository
from .feature_repository import FeatureRepository
from .form_schema_repository import FormSchemaRepository
from .patient_repository import PatientRepository
from .study_repository import StudyRepository
from .tag_repository import TagRepository
from .task_repository import TaskRepository

__all__ = [
    "DeviceRepository",
    "PatientRepository",
    "FormSchemaRepository",
    "StudyRepository",
    "FeatureRepository",
    "TagRepository",
    "TaskRepository",
]
```

> **Note:** the `ImageInstance`, `ImageStorage`, `SubTaskImageLink` imports are unused by `TaskRepository` but are consumed by `SubTaskRepository`, added to this same module in Task 2. Leaving them in now keeps Task 2 to a pure append; if a linter flags them between tasks, that resolves the moment Task 2 lands. (If you prefer zero interim warnings, add them in Task 2 instead — either is fine.)

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest orm/eyened_orm/tests/test_task_repository.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add orm/eyened_orm/repositories/task_repository.py orm/eyened_orm/repositories/__init__.py orm/eyened_orm/tests/test_task_repository.py
git commit -m "feat(repositories): add TaskRepository"
```

---

## Task 2: SubTaskRepository

The subtask read/query methods `task.py` needs for its two task-rooted subtask endpoints: the ordered id list backing the "absolute index" (`GET /task/{id}/subtasks`), the paginated/filtered/optionally-image-loaded row fetch (shared by both endpoints), and the matching count. Lives in `task_repository.py` alongside `TaskRepository` (per the spec's directory table). The by-id and image-link mutation methods are **3b** (`subtask.py`), not here.

**Files:**
- Modify: `orm/eyened_orm/repositories/task_repository.py` (add `SubTaskRepository`)
- Modify: `orm/eyened_orm/repositories/__init__.py` (add `SubTaskRepository`)
- Modify: `orm/eyened_orm/tests/test_task_repository.py` (append `SubTaskRepository` tests + the image-graph helper)

**Interfaces:**
- Consumes: `eyened_orm.SubTask`, `eyened_orm.SubTaskImageLink`, `eyened_orm.ImageInstance`, `eyened_orm.ImageStorage`, `eyened_orm.task.SubTaskState`.
- Produces (all take `session: Session` first):
  - `all_ids_for_task(session, task_id: int) -> list[int]` — every `SubTaskID` for the task, ordered by `SubTaskID`.
  - `count_for_task(session, task_id: int, *, status: SubTaskState | None = None) -> int` — subtask count, optionally filtered by state.
  - `list_for_task(session, task_id: int, *, status: SubTaskState | None = None, limit: int, offset: int, with_images: bool = False) -> list[SubTask]` — subtasks for the task ordered by `SubTaskID`, optional state filter, `limit`/`offset` window, optional image eager-load chain.

- [ ] **Step 1: Write the failing test**

Append to `orm/eyened_orm/tests/test_task_repository.py` (add the import to the existing top-of-file import line, then the helper and tests):

```python
# add to the existing imports at the top of the file:
from eyened_orm.repositories.task_repository import SubTaskRepository
```

```python
def _make_image(session, public_id: str) -> "int":
    """Build the minimal Series/Device graph an ImageInstance FK-requires.

    Returns the new ImageInstanceID. Mirrors the smallest row set that
    satisfies ImageInstance's NOT NULL FKs under PRAGMA foreign_keys=ON.
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


def test_all_ids_for_task_ordered(session):
    """all_ids_for_task returns the task's SubTaskIDs ascending."""
    creator = _creator(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, creator.CreatorID)
    a = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    b = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)

    ids = SubTaskRepository().all_ids_for_task(session, task.TaskID)

    assert ids == [a.SubTaskID, b.SubTaskID]


def test_count_for_task_with_and_without_status(session):
    """count_for_task counts all subtasks, or only those in the given state."""
    creator = _creator(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, creator.CreatorID)
    _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    _make_subtask(session, task.TaskID, SubTaskState.Ready)
    _make_subtask(session, task.TaskID, SubTaskState.Ready)
    repo = SubTaskRepository()

    assert repo.count_for_task(session, task.TaskID) == 3
    assert repo.count_for_task(session, task.TaskID, status=SubTaskState.Ready) == 2


def test_list_for_task_paginates_in_id_order(session):
    """list_for_task returns a limit/offset window ordered by SubTaskID."""
    creator = _creator(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, creator.CreatorID)
    made = [
        _make_subtask(session, task.TaskID, SubTaskState.NotStarted) for _ in range(5)
    ]

    rows = SubTaskRepository().list_for_task(
        session, task.TaskID, limit=2, offset=1
    )

    assert [r.SubTaskID for r in rows] == [made[1].SubTaskID, made[2].SubTaskID]


def test_list_for_task_filters_by_status(session):
    """list_for_task with a status returns only subtasks in that state."""
    creator = _creator(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, creator.CreatorID)
    _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    ready = _make_subtask(session, task.TaskID, SubTaskState.Ready)

    rows = SubTaskRepository().list_for_task(
        session, task.TaskID, status=SubTaskState.Ready, limit=10, offset=0
    )

    assert [r.SubTaskID for r in rows] == [ready.SubTaskID]


def test_list_for_task_with_images_loads_links(session):
    """with_images eager-loads the SubTaskImageLinks -> ImageInstance chain."""
    creator = _creator(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, creator.CreatorID)
    st = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    image_id = _make_image(session, "pub-1")
    from eyened_orm import SubTaskImageLink

    session.add(
        SubTaskImageLink(
            SubTaskID=st.SubTaskID, ImageInstanceID=image_id, ImageIndex=0
        )
    )
    session.flush()

    rows = SubTaskRepository().list_for_task(
        session, task.TaskID, limit=10, offset=0, with_images=True
    )

    assert len(rows) == 1
    assert [link.ImageInstance.PublicID for link in rows[0].SubTaskImageLinks] == [
        "pub-1"
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest orm/eyened_orm/tests/test_task_repository.py -v`
Expected: FAIL — `ImportError: cannot import name 'SubTaskRepository' from 'eyened_orm.repositories.task_repository'`.

- [ ] **Step 3: Write the repository**

Append to `orm/eyened_orm/repositories/task_repository.py` (module-level loader constant + class):

```python
# Eager-load the subtask's images down to their storage backend (mirrors the
# route's former with_images option chain).
_SUBTASK_IMAGE_LOADER = (
    selectinload(SubTask.SubTaskImageLinks)
    .selectinload(SubTaskImageLink.ImageInstance)
    .selectinload(ImageInstance.ImageStorages)
    .selectinload(ImageStorage.StorageBackend)
)


class SubTaskRepository:
    """Data access for a task's SubTask rows (reads used by task.py)."""

    def all_ids_for_task(self, session: Session, task_id: int) -> list[int]:
        """Return the task's SubTaskIDs ordered ascending (backs absolute index)."""
        return list(
            session.execute(
                select(SubTask.SubTaskID)
                .where(SubTask.TaskID == task_id)
                .order_by(SubTask.SubTaskID)
            )
            .scalars()
            .all()
        )

    def count_for_task(
        self,
        session: Session,
        task_id: int,
        *,
        status: SubTaskState | None = None,
    ) -> int:
        """Return the task's subtask count, optionally filtered by state."""
        stmt = select(func.count()).select_from(SubTask).where(
            SubTask.TaskID == task_id
        )
        if status is not None:
            stmt = stmt.where(SubTask.TaskState == status)
        return session.scalar(stmt) or 0

    def list_for_task(
        self,
        session: Session,
        task_id: int,
        *,
        status: SubTaskState | None = None,
        limit: int,
        offset: int,
        with_images: bool = False,
    ) -> list[SubTask]:
        """Return a limit/offset window of the task's subtasks (SubTaskID order).

        Optionally filters by ``status`` and eager-loads each subtask's images.
        """
        stmt = select(SubTask).where(SubTask.TaskID == task_id)
        if status is not None:
            stmt = stmt.where(SubTask.TaskState == status)
        stmt = stmt.order_by(SubTask.SubTaskID)
        if with_images:
            stmt = stmt.options(_SUBTASK_IMAGE_LOADER)
        return list(
            session.execute(stmt.limit(limit).offset(offset)).scalars().all()
        )
```

Update `orm/eyened_orm/repositories/__init__.py` (add `SubTaskRepository` to the `task_repository` import and to `__all__`):

```python
from .task_repository import SubTaskRepository, TaskRepository
```

```python
    "TaskRepository",
    "SubTaskRepository",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest orm/eyened_orm/tests/test_task_repository.py -v`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add orm/eyened_orm/repositories/task_repository.py orm/eyened_orm/repositories/__init__.py orm/eyened_orm/tests/test_task_repository.py
git commit -m "feat(repositories): add SubTaskRepository read methods"
```

---

## Task 3: TaskService (task CRUD)

Holds the task business rules the `task.py` handlers encode today (create with `TaskState.NotStarted`; list with per-task subtask counts; get; update the mutable fields; delete with cascade), owns the commit, and emits audit logging via an injected logger. The only failure path is a missing task (`NotFoundError` → 404) on `get`/`update`/`delete`. The constructor takes **both** repositories (`TaskRepository` for tasks/counts, `SubTaskRepository` for the Task 4 subtask reads); the default factory wires both.

**Files:**
- Create: `server/services/task_service.py`
- Modify: `server/services/__init__.py` (re-export `TaskService`)
- Test: `server/tests/test_task_service.py`

**Interfaces:**
- Consumes: `TaskRepository`, `SubTaskRepository` (Tasks 1–2); `NotFoundError` (existing); `ActingUser`; `DatabaseModificationLogger`/`get_db_logger` (`server/utils/db_logging.py`); `eyened_orm.Task`, `eyened_orm.task.TaskState`.
- Produces:
  - `TaskService(task_repository: TaskRepository, subtask_repository: SubTaskRepository, logger: DatabaseModificationLogger | None = None)`.
  - `create_task(session, name: str, description: str | None, contact_id: int | None, task_definition_id: int, actor: ActingUser) -> Task` — new task (reloaded with relations); `TaskState.NotStarted`.
  - `list_tasks(session) -> tuple[list[Task], dict[int, tuple[int, int]]]` — tasks (TaskID order) + `{task_id: (num, ready)}`.
  - `get_task(session, task_id: int) -> tuple[Task, tuple[int, int]]` — task + its `(num, ready)`; 404 if absent.
  - `update_task(session, task_id: int, name, description, contact_id, task_definition_id, task_state, actor) -> tuple[Task, tuple[int, int]]` — each field optional; 404 if absent.
  - `delete_task(session, task_id: int, actor: ActingUser) -> None` — 404 if absent.
  - `get_task_service() -> TaskService` — default-wiring factory (`TaskRepository()` + `SubTaskRepository()` + `get_db_logger()`).

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_task_service.py`:

```python
import pytest

from eyened_orm import Creator, SubTask, Task, TaskDefinition
from eyened_orm.task import SubTaskState, TaskState
from eyened_orm.repositories.task_repository import SubTaskRepository, TaskRepository

from server.services.acting_user import ActingUser
from server.services.exceptions import NotFoundError
from server.services.task_service import TaskService


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
    """An ActingUser backed by a real Creator row (Task.CreatorID is a FK)."""
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


def _service(logger=None) -> TaskService:
    return TaskService(TaskRepository(), SubTaskRepository(), logger=logger)


def test_create_task_persists_with_defaults(session):
    """create_task stores the task with the actor as owner and TaskState.NotStarted."""
    actor = _actor(session)
    td = _task_def(session)

    task = _service().create_task(
        session, "New", "desc", None, td.TaskDefinitionID, actor
    )

    assert task.TaskName == "New"
    assert task.Description == "desc"
    assert task.ContactID is None
    assert task.TaskDefinitionID == td.TaskDefinitionID
    assert task.CreatorID == actor.id
    assert task.TaskState == TaskState.NotStarted


def test_create_task_logs_insert(session):
    """create_task emits one insert audit record naming the entity and user."""
    actor = _actor(session)
    td = _task_def(session)
    logger = FakeAuditLogger()

    _service(logger).create_task(
        session, "New", None, None, td.TaskDefinitionID, actor
    )

    assert len(logger.inserts) == 1
    assert logger.inserts[0]["entity"] == "Task"
    assert logger.inserts[0]["user"] == actor.username


def test_list_tasks_returns_tasks_with_counts(session):
    """list_tasks returns tasks in id order and a (total, ready) count per task."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    session.add(SubTask(TaskID=task.TaskID, TaskState=SubTaskState.Ready))
    session.add(SubTask(TaskID=task.TaskID, TaskState=SubTaskState.NotStarted))
    session.commit()

    tasks, counts = _service().list_tasks(session)

    assert [t.TaskID for t in tasks] == [task.TaskID]
    assert counts[task.TaskID] == (2, 1)


def test_get_task_returns_task_and_counts(session):
    """get_task returns the task and its (total, ready) subtask counts."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    session.add(SubTask(TaskID=task.TaskID, TaskState=SubTaskState.Ready))
    session.commit()

    got, counts = _service().get_task(session, task.TaskID)

    assert got.TaskID == task.TaskID
    assert counts == (1, 1)


def test_get_task_unknown_raises_not_found(session):
    """Getting a missing task is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().get_task(session, 999_999)


def test_update_task_changes_fields(session):
    """update_task overwrites the provided fields (name, description, task_state)."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id, "Old")
    session.commit()

    updated, _counts = _service().update_task(
        session, task.TaskID, "New", "newdesc", None, None, TaskState.Busy, actor
    )

    assert updated.TaskName == "New"
    assert updated.Description == "newdesc"
    assert updated.TaskState == TaskState.Busy


def test_update_task_unknown_raises_not_found(session):
    """Updating a missing task is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    with pytest.raises(NotFoundError):
        _service().update_task(
            session, 999_999, "x", None, None, None, None, actor
        )


def test_update_task_logs_update(session):
    """update_task emits one update audit record for the Task entity."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id, "Old")
    session.commit()
    logger = FakeAuditLogger()

    _service(logger).update_task(
        session, task.TaskID, "New", None, None, None, None, actor
    )

    assert len(logger.updates) == 1
    assert logger.updates[0]["entity"] == "Task"


def test_delete_task_removes_it_and_cascades_subtasks(session):
    """delete_task removes the task and (via DB cascade) its subtasks."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    session.add(SubTask(TaskID=task.TaskID, TaskState=SubTaskState.NotStarted))
    session.commit()

    _service().delete_task(session, task.TaskID, actor)

    assert TaskRepository().get_by_id(session, task.TaskID) is None
    assert SubTaskRepository().all_ids_for_task(session, task.TaskID) == []


def test_delete_task_unknown_raises_not_found(session):
    """Deleting a missing task is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    with pytest.raises(NotFoundError):
        _service().delete_task(session, 999_999, actor)


def test_delete_task_logs_delete(session):
    """delete_task emits one delete audit record for the Task entity."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    session.commit()
    logger = FakeAuditLogger()

    _service(logger).delete_task(session, task.TaskID, actor)

    assert len(logger.deletes) == 1
    assert logger.deletes[0]["entity"] == "Task"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest server/tests/test_task_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.services.task_service'`.

- [ ] **Step 3: Write the service**

Create `server/services/task_service.py`:

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from eyened_orm import Task
from eyened_orm.task import TaskState
from eyened_orm.repositories.task_repository import SubTaskRepository, TaskRepository

from ..utils.db_logging import DatabaseModificationLogger, get_db_logger
from .acting_user import ActingUser
from .exceptions import NotFoundError


class TaskService:
    """Business logic for tasks and their subtask listings."""

    def __init__(
        self,
        task_repository: TaskRepository,
        subtask_repository: SubTaskRepository,
        logger: DatabaseModificationLogger | None = None,
    ) -> None:
        self.tasks = task_repository
        self.subtasks = subtask_repository
        self.logger = logger

    def create_task(
        self,
        session: Session,
        name: str,
        description: str | None,
        contact_id: int | None,
        task_definition_id: int,
        actor: ActingUser,
    ) -> Task:
        """Create a task owned by the acting user (TaskState.NotStarted)."""
        task = Task(
            TaskName=name,
            Description=description,
            ContactID=contact_id,
            TaskDefinitionID=task_definition_id,
            CreatorID=actor.id,
            TaskState=TaskState.NotStarted,
        )
        session.add(task)
        session.commit()
        task = self.tasks.get_with_relations(session, task.TaskID)
        if self.logger is not None:
            self.logger.log_insert(
                user=actor.username,
                user_id=actor.id,
                endpoint="POST /api/task",
                entity="Task",
                entity_id=task.TaskID,
                fields={
                    "name": task.TaskName,
                    "description": task.Description,
                    "contact_id": task.ContactID,
                    "task_definition_id": task.TaskDefinitionID,
                },
            )
        return task

    def list_tasks(
        self, session: Session
    ) -> tuple[list[Task], dict[int, tuple[int, int]]]:
        """Return all tasks (TaskID order) and their {id: (total, ready)} counts."""
        tasks = self.tasks.list_all(session)
        counts = self.tasks.subtask_counts(session, [t.TaskID for t in tasks])
        return tasks, counts

    def get_task(
        self, session: Session, task_id: int
    ) -> tuple[Task, tuple[int, int]]:
        """Return a task and its (total, ready) subtask counts.

        Raises:
            NotFoundError: If the task does not exist.
        """
        task = self.tasks.get_with_relations(session, task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")
        return task, self.tasks.subtask_counts(session, [task_id])[task_id]

    def update_task(
        self,
        session: Session,
        task_id: int,
        name: str | None,
        description: str | None,
        contact_id: int | None,
        task_definition_id: int | None,
        task_state: TaskState | None,
        actor: ActingUser,
    ) -> tuple[Task, tuple[int, int]]:
        """Update a task's mutable fields (each optional).

        Raises:
            NotFoundError: If the task does not exist.
        """
        task = self.tasks.get_by_id(session, task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")

        changes: dict[str, str] = {}
        if name is not None:
            changes["name"] = f"{task.TaskName} -> {name}"
            task.TaskName = name
        if description is not None:
            changes["description"] = f"{task.Description} -> {description}"
            task.Description = description
        if contact_id is not None:
            changes["contact_id"] = f"{task.ContactID} -> {contact_id}"
            task.ContactID = contact_id
        if task_definition_id is not None:
            changes["task_definition_id"] = (
                f"{task.TaskDefinitionID} -> {task_definition_id}"
            )
            task.TaskDefinitionID = task_definition_id
        if task_state is not None:
            changes["task_state"] = f"{task.TaskState} -> {task_state}"
            task.TaskState = task_state

        session.commit()
        task = self.tasks.get_with_relations(session, task_id)
        counts = self.tasks.subtask_counts(session, [task_id])[task_id]
        if self.logger is not None:
            self.logger.log_update(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"PATCH /api/task/{task_id}",
                entity="Task",
                entity_id=task_id,
                changes=changes if changes else None,
            )
        return task, counts

    def delete_task(
        self, session: Session, task_id: int, actor: ActingUser
    ) -> None:
        """Delete a task (its subtasks cascade at the DB level).

        Raises:
            NotFoundError: If the task does not exist.
        """
        task = self.tasks.get_by_id(session, task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")

        deleted_data = {
            "name": task.TaskName,
            "description": task.Description,
            "contact_id": task.ContactID,
            "task_definition_id": task.TaskDefinitionID,
            "creator_id": task.CreatorID,
            "task_state": str(task.TaskState) if task.TaskState else None,
        }
        session.delete(task)
        session.commit()
        if self.logger is not None:
            self.logger.log_delete(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"DELETE /api/task/{task_id}",
                entity="Task",
                entity_id=task_id,
                deleted_data=deleted_data,
            )
        return None


def get_task_service() -> TaskService:
    """Default TaskService wiring for FastAPI ``Depends()``."""
    return TaskService(
        TaskRepository(), SubTaskRepository(), logger=get_db_logger()
    )
```

Update `server/services/__init__.py` (add the import + `__all__` entry, keeping all existing exports):

```python
from .acting_user import ActingUser
from .device_service import DeviceService
from .exceptions import BadRequestError, ConflictError, NotFoundError, ServiceError
from .feature_service import FeatureService
from .form_schema_service import FormSchemaService
from .patient_service import PatientService
from .study_service import StudyService
from .tag_service import TagService
from .task_service import TaskService

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
    "TagService",
    "TaskService",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest server/tests/test_task_service.py -v`
Expected: PASS (11 passed).

- [ ] **Step 5: Commit**

```bash
git add server/services/task_service.py server/services/__init__.py server/tests/test_task_service.py
git commit -m "feat(services): add TaskService with task CRUD and injected audit logging"
```

---

## Task 4: TaskService — task-rooted subtask reads

Adds the two read methods behind `GET /task/{id}/subtasks` (paginated, optional status filter, optional images, each row carrying its **absolute** index across the unfiltered ordered list) and `GET /task/{id}/subtask/{index}` (fetch by absolute index, optionally with the following subtask). These are task-rooted (they 404 via the task, or return an empty page) and belong in `TaskService`; the per-subtask-id CRUD is 3b's `SubTaskService`.

> **Note — `with_images` is a passthrough at this layer.** Both methods forward `with_images` straight to `SubTaskRepository.list_for_task`; the Service adds no logic for it, and the DTO that actually differs by `with_images` is built in the route. So the tests below deliberately use `with_images=False` — the eager-load itself is covered once, at the repository level, by `test_list_for_task_with_images_loads_links` (Task 2). Per the lean-test-granularity convention, we do not add a Service test that only re-asserts a boolean passthrough.

**Files:**
- Modify: `server/services/task_service.py` (add two methods to `TaskService`)
- Modify: `server/tests/test_task_service.py` (append tests)

**Interfaces:**
- Consumes: `SubTaskRepository.all_ids_for_task`, `.list_for_task`, `.count_for_task` (Task 2); `TaskRepository.get_by_id` (Task 1); `eyened_orm.SubTask`, `eyened_orm.task.SubTaskState`.
- Produces (added to `TaskService`):
  - `list_task_subtasks(session, task_id: int, *, with_images: bool, limit: int, page: int, status: SubTaskState | None) -> tuple[list[tuple[SubTask, int]], int]` — `[(subtask, absolute_index), ...]` for the requested page + total count (honoring `status`); 404 if the task is absent. `absolute_index` is the subtask's 0-based position within *all* the task's subtasks ordered by `SubTaskID` (computed **before** any status filter), matching today's handler.
  - `get_task_subtask(session, task_id: int, subtask_index: int, *, with_images: bool, with_next: bool) -> tuple[SubTask, SubTask | None]` — the subtask at that absolute index and, if `with_next`, the one after it (`None` if there is none); 404 if no subtask sits at `subtask_index`.

- [ ] **Step 1: Write the failing test**

Append to `server/tests/test_task_service.py`:

```python
def _make_subtask(session, task_id: int, state: SubTaskState) -> SubTask:
    st = SubTask(TaskID=task_id, TaskState=state)
    session.add(st)
    session.flush()
    return st


def test_list_task_subtasks_paginates_with_absolute_index(session):
    """list_task_subtasks returns a page, each row tagged with its absolute index."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    made = [_make_subtask(session, task.TaskID, SubTaskState.NotStarted) for _ in range(5)]
    session.commit()

    rows, count = _service().list_task_subtasks(
        session, task.TaskID, with_images=False, limit=2, page=1, status=None
    )

    assert count == 5
    assert [(st.SubTaskID, idx) for st, idx in rows] == [
        (made[2].SubTaskID, 2),
        (made[3].SubTaskID, 3),
    ]


def test_list_task_subtasks_filters_by_status_keeps_absolute_index(session):
    """A status filter narrows rows/count but indices stay absolute (pre-filter)."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    _make_subtask(session, task.TaskID, SubTaskState.NotStarted)  # abs index 0
    ready = _make_subtask(session, task.TaskID, SubTaskState.Ready)  # abs index 1
    session.commit()

    rows, count = _service().list_task_subtasks(
        session, task.TaskID, with_images=False, limit=10, page=0,
        status=SubTaskState.Ready,
    )

    assert count == 1
    assert [(st.SubTaskID, idx) for st, idx in rows] == [(ready.SubTaskID, 1)]


def test_list_task_subtasks_unknown_task_raises_not_found(session):
    """Listing subtasks of a missing task is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().list_task_subtasks(
            session, 999_999, with_images=False, limit=10, page=0, status=None
        )


def test_get_task_subtask_returns_by_index(session):
    """get_task_subtask returns the subtask at the given absolute index."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    made = [_make_subtask(session, task.TaskID, SubTaskState.NotStarted) for _ in range(3)]
    session.commit()

    main, nxt = _service().get_task_subtask(
        session, task.TaskID, 1, with_images=False, with_next=False
    )

    assert main.SubTaskID == made[1].SubTaskID
    assert nxt is None


def test_get_task_subtask_with_next_returns_following(session):
    """with_next also returns the subtask after the requested index."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    made = [_make_subtask(session, task.TaskID, SubTaskState.NotStarted) for _ in range(3)]
    session.commit()

    main, nxt = _service().get_task_subtask(
        session, task.TaskID, 1, with_images=False, with_next=True
    )

    assert main.SubTaskID == made[1].SubTaskID
    assert nxt is not None
    assert nxt.SubTaskID == made[2].SubTaskID


def test_get_task_subtask_out_of_range_raises_not_found(session):
    """An index past the last subtask is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    session.commit()

    with pytest.raises(NotFoundError):
        _service().get_task_subtask(
            session, task.TaskID, 5, with_images=False, with_next=False
        )
```

> **Note — imports:** `SubTask` and `SubTaskState` are already imported at the top of `test_task_service.py` (Task 3). The appended `_make_subtask` helper reuses them.

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/pytest server/tests/test_task_service.py -v`
Expected: FAIL — `AttributeError: 'TaskService' object has no attribute 'list_task_subtasks'`.

- [ ] **Step 3: Add the two methods**

Add these methods to the `TaskService` class in `server/services/task_service.py` (place them after `delete_task`, before the module-level `get_task_service`). Also add `SubTask` and `SubTaskState` to the `eyened_orm` / `eyened_orm.task` imports at the top of the file:

```python
# extend the existing imports at the top of task_service.py:
from eyened_orm import SubTask, Task
from eyened_orm.task import SubTaskState, TaskState
```

```python
    def list_task_subtasks(
        self,
        session: Session,
        task_id: int,
        *,
        with_images: bool,
        limit: int,
        page: int,
        status: SubTaskState | None,
    ) -> tuple[list[tuple[SubTask, int]], int]:
        """Return one page of a task's subtasks, each with its absolute index.

        ``absolute_index`` is the subtask's 0-based position within *all* the
        task's subtasks ordered by SubTaskID (computed before the ``status``
        filter). The returned count honors ``status``.

        Raises:
            NotFoundError: If the task does not exist.
        """
        if self.tasks.get_by_id(session, task_id) is None:
            raise NotFoundError(f"Task {task_id} not found")

        index_of = {
            sid: i
            for i, sid in enumerate(self.subtasks.all_ids_for_task(session, task_id))
        }
        rows = self.subtasks.list_for_task(
            session,
            task_id,
            status=status,
            limit=limit,
            offset=limit * page,
            with_images=with_images,
        )
        count = self.subtasks.count_for_task(session, task_id, status=status)
        # Every returned row is one of the task's subtasks, so its id is always
        # in index_of (rows are a subset of all_ids_for_task).
        return [(st, index_of[st.SubTaskID]) for st in rows], count

    def get_task_subtask(
        self,
        session: Session,
        task_id: int,
        subtask_index: int,
        *,
        with_images: bool,
        with_next: bool,
    ) -> tuple[SubTask, SubTask | None]:
        """Return the subtask at ``subtask_index`` and, if asked, the next one.

        Raises:
            NotFoundError: If no subtask sits at ``subtask_index``.
        """
        rows = self.subtasks.list_for_task(
            session,
            task_id,
            status=None,
            limit=2 if with_next else 1,
            offset=subtask_index,
            with_images=with_images,
        )
        if not rows:
            raise NotFoundError("SubTask not found")
        nxt = rows[1] if (with_next and len(rows) > 1) else None
        return rows[0], nxt
```

- [ ] **Step 4: Run test to verify it passes**

Run: `dev/.venv/bin/pytest server/tests/test_task_service.py -v`
Expected: PASS (17 passed).

- [ ] **Step 5: Commit**

```bash
git add server/services/task_service.py server/tests/test_task_service.py
git commit -m "feat(services): add task-rooted subtask reads to TaskService"
```

---

## Task 5: Rewire `routes/task.py` to use TaskService

Make every `task.py` handler thin: build an `ActingUser`, call the Service, convert the ORM result via `DTOConverter`, return. All inline `select(...)`/`db.get(...)`, `raise HTTPException(...)`, `db.commit()`/`db.refresh()`, `delete(...)`, `get_db_logger()` calls, and the `_task_query_options`/`_subtask_counts_by_task_id`/`bisect` helpers are removed — they now live in the Repository/Service.

**Files:**
- Modify: `server/routes/task.py` (full replacement)

**Interfaces:**
- Consumes: `TaskService` + `get_task_service` (Tasks 3–4); `ActingUser`; existing `DTOConverter.task_to_get`/`subtask_to_get`/`subtask_with_images_to_get`, the `dtos_tasks` DTOs, `get_db`, `get_current_user`, and `eyened_orm.SubTaskState` (the `subtask_status` query-param type).
- Produces: unchanged HTTP contract — `POST /task` → `TaskGET`; `GET /task` → `list[TaskGET]`; `GET /task/{id}` → `TaskGET`; `PATCH /task/{id}` → `TaskGET`; `DELETE /task/{id}` → 204; `GET /task/{id}/subtasks` → `SubTasksWithImagesResponse | SubTasksResponse`; `GET /task/{id}/subtask/{index}` → `SubTaskWithImagesGET | SubTaskGET`. Same 404s (now via the central handler).

> **Note — route-only test coverage (accepted gap):** `server/tests/` has no task route test today (only `test_routes_auth.py`), and this phase adds none — matching how 2a/2b/2c shipped. So the route-only logic left here (converter selection by `with_images`, response-envelope assembly, and applying the Service-returned `index` / `next_task` via `.copy(update=...)`) is exercised **only** by the optional manual smoke in Verification, not automatically. The risk is low because the index computation and all 404s now live in the Service and are unit-tested; the residual untested surface is the thin converter-choice + envelope wiring. If you want it covered, add a single FastAPI `TestClient` test with `app.dependency_overrides` for `get_db`/`get_current_user` — but that is new shared route-test infrastructure, so treat it as its own task rather than folding it in here.

- [ ] **Step 1: Replace the module contents with thin Service-backed handlers**

Replace the entire contents of `server/routes/task.py` with:

```python
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from eyened_orm import SubTaskState

from ..db import get_db
from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_tasks import (
    SubTaskGET,
    SubTasksResponse,
    SubTasksWithImagesResponse,
    SubTaskWithImagesGET,
    TaskGET,
    TaskPATCH,
    TaskPUT,
)
from ..services.acting_user import ActingUser
from ..services.task_service import TaskService, get_task_service
from .auth import CurrentUser, get_current_user

router = APIRouter()


@router.post("/task", response_model=TaskGET)
async def create_task(
    dto: TaskPUT,
    db: Session = Depends(get_db),
    service: TaskService = Depends(get_task_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a task owned by the current user."""
    task = service.create_task(
        db,
        dto.name,
        dto.description,
        dto.contact_id,
        dto.task_definition_id,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.task_to_get(task, num_tasks=0, num_tasks_ready=0)


@router.get("/task", response_model=List[TaskGET])
async def list_tasks(
    db: Session = Depends(get_db),
    service: TaskService = Depends(get_task_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all tasks (no pagination)."""
    tasks, counts = service.list_tasks(db)
    return [
        DTOConverter.task_to_get(
            t,
            num_tasks=counts[t.TaskID][0],
            num_tasks_ready=counts[t.TaskID][1],
        )
        for t in tasks
    ]


@router.get("/task/{task_id}", response_model=TaskGET)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    service: TaskService = Depends(get_task_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single task with its subtask counts."""
    task, (num_tasks, num_tasks_ready) = service.get_task(db, task_id)
    return DTOConverter.task_to_get(
        task, num_tasks=num_tasks, num_tasks_ready=num_tasks_ready
    )


@router.patch("/task/{task_id}", response_model=TaskGET)
async def patch_task(
    task_id: int,
    dto: TaskPATCH,
    db: Session = Depends(get_db),
    service: TaskService = Depends(get_task_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a task's name/description/contact/definition/state."""
    task, (num_tasks, num_tasks_ready) = service.update_task(
        db,
        task_id,
        dto.name,
        dto.description,
        dto.contact_id,
        dto.task_definition_id,
        dto.task_state,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.task_to_get(
        task, num_tasks=num_tasks, num_tasks_ready=num_tasks_ready
    )


@router.delete("/task/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    service: TaskService = Depends(get_task_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a task."""
    service.delete_task(
        db,
        task_id,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return Response(status_code=204)


@router.get(
    "/task/{task_id}/subtasks",
    response_model=Union[SubTasksWithImagesResponse, SubTasksResponse],
)
async def list_subtasks(
    task_id: int,
    with_images: bool = False,
    limit: int = 200,
    page: int = 0,
    subtask_status: Optional[SubTaskState] = None,
    db: Session = Depends(get_db),
    service: TaskService = Depends(get_task_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List subtasks of a task (pagination, optional images, optional status filter).

    ``index`` is the 0-based position within all subtasks of the task ordered by
    SubTaskID (computed before any subtask_status filtering).
    """
    rows_with_index, count = service.list_task_subtasks(
        db,
        task_id,
        with_images=with_images,
        limit=limit,
        page=page,
        status=subtask_status,
    )
    convert = (
        DTOConverter.subtask_with_images_to_get
        if with_images
        else DTOConverter.subtask_to_get
    )
    subtasks = [
        convert(st).copy(update={"index": index}) for st, index in rows_with_index
    ]
    return {"subtasks": subtasks, "limit": limit, "page": page, "count": count}


@router.get(
    "/task/{task_id}/subtask/{subtask_index}",
    response_model=Union[SubTaskWithImagesGET, SubTaskGET],
)
async def get_subtask(
    task_id: int,
    subtask_index: int,
    with_images: bool = False,
    with_next: bool = False,
    db: Session = Depends(get_db),
    service: TaskService = Depends(get_task_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single subtask by index, optionally with images and the next subtask."""
    main, nxt = service.get_task_subtask(
        db,
        task_id,
        subtask_index,
        with_images=with_images,
        with_next=with_next,
    )
    convert = (
        DTOConverter.subtask_with_images_to_get
        if with_images
        else DTOConverter.subtask_to_get
    )
    main_dto = convert(main).copy(update={"index": subtask_index})
    if nxt is not None:
        next_dto = convert(nxt).copy(update={"index": subtask_index + 1})
        main_dto = main_dto.copy(update={"next_task": next_dto})
    return main_dto
```

- [ ] **Step 2: Verify the router imports and exposes all seven routes**

Run: `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/python -c "from server.routes import task; print(sorted((r.path, tuple(sorted(r.methods))) for r in task.router.routes))"`
Expected: prints the routes — `/task` (GET, POST), `/task/{task_id}` (GET, PATCH, DELETE), `/task/{task_id}/subtasks` (GET), `/task/{task_id}/subtask/{subtask_index}` (GET) — with no traceback.

- [ ] **Step 3: Confirm the app still boots**

Run: `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/python -c "import server.main; print('ok')"`
Expected: prints `ok` with no traceback.

- [ ] **Step 4: Run the full test suite to confirm no regressions**

Run: `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/pytest -q`
Expected: all tests pass (prior 165 + Task 1–2 repository tests: 9 + Task 3–4 service tests: 17 = **191 passed**); no import/collection errors.

- [ ] **Step 5: Commit**

```bash
git add server/routes/task.py
git commit -m "refactor(routes): route task endpoints through TaskService"
```

---

## Verification (end-to-end, on `feature/rbac-step1-service-layer`)

1. **Full suite green:** `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/pytest -q` — prior suite plus the new TaskRepository/SubTaskRepository/TaskService tests pass (191 passed).
2. **All seven routes exposed:** the Task 5 Step 2 command prints GET/POST `/task`, GET/PATCH/DELETE `/task/{task_id}`, GET `/task/{task_id}/subtasks`, and GET `/task/{task_id}/subtask/{subtask_index}`.
3. **App boots:** `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/python -c "import server.main; print('ok')"` → `ok`.
4. **Manual smoke (optional, real dev DB + server):**
   - `POST /api/task` with `{"name": "X", "task_definition_id": <valid>}` → 200 `TaskGET` with `task_state: "NotStarted"`, `num_tasks: 0`; `PATCH` its name/state → 200; `DELETE` it → 204.
   - `GET`/`PATCH`/`DELETE` on `/api/task/999999` → HTTP 404 `{"detail": "Task 999999 not found"}` (proves the `NotFoundError` → central-handler path is live).
   - For a task with subtasks: `GET /api/task/{id}/subtasks?limit=2&page=1` → each subtask's `index` is its absolute position; `?subtask_status=Ready` narrows the page but keeps absolute indices; `GET /api/task/{id}/subtask/0?with_next=true` → the first subtask plus `next_task`; an out-of-range index → 404 `{"detail": "SubTask not found"}`.
5. **Branch isolation:** `git log development..HEAD` shows only the RBAC-step1 commits; `development` has not moved.

## Out of scope / follow-up

- **Phase 3b (`subtask.py`)** — next plan/PR on this branch, same pattern: introduces `SubTaskService` (+ `get_subtask` by id, `patch`/`delete`, `add_image`/`remove_image`) and extends `SubTaskRepository` with `get_by_id`, `get_with_images`, and the image-link methods (`resolve_image_instance_id`, `max_image_index`, `get_image_link`). Note `subtask.py` today wraps `add_subtask_image` in a `try/except → HTTPException(500)`; in 3b that becomes ordinary Service behavior (let the central handler map failures) — call it out in the 3b plan.
- Phase 4 (`import_api`, `instances`, `form_annotations`, `segmentations`) — later plans/PRs on this branch.
- Transaction-ownership review across all Services (spec "Follow-up work") once every phase has migrated.
- RBAC enforcement itself is **Step 2** (`PermissionDeniedError` + per-method authz checks that read `ActingUser`).
