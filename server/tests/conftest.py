from eyened_orm.utils.sqlite_testdb import (  # noqa: F401
    SessionLocal,
    engine,
    session,
)

import os


def pytest_configure(config):
    # Note: due to the way application configuration is created and imported throughout the application,
    # there is no clean way to test code that imports (database) settings, which is virtually everything.
    # Below is a rather ugly hack to work around this, that will probably result in new issues when we
    # want to add database-backend tests for the server. The correct solution is to handle settings
    # loading differently in the application.

    # Add mock values for required configuration values
    os.environ.setdefault("EYENED_DATABASE_USER", "test_user")
    os.environ.setdefault("EYENED_DATABASE_PASSWORD", "test_password")


import pytest
from contextlib import contextmanager
from types import SimpleNamespace

from fastapi.testclient import TestClient


class _SessionBoundDatabase:
    """Stand-in for eyened_orm.Database exposing get_session() bound to a
    fixed Session (the `session` fixture), rather than creating a fresh one
    per call: HTTP tests seed/verify data through the same Session object the
    request handler receives, and the `session` fixture (sqlite_testdb.py)
    already owns opening/closing it -- this stand-in must not close it.

    Monkeypatching server.db.database to this lets the client fixture drive
    the real, unmodified server.db.get_db -- matching production at the
    fixture rather than in production code -- instead of a hand-copied
    re-implementation of its commit/rollback body.
    """

    def __init__(self, session) -> None:
        self._session = session

    @contextmanager
    def get_session(self):
        yield self._session


@pytest.fixture()
def client(session, monkeypatch):
    """TestClient bound to app_api, with the DB engine and auth dependency overridden.

    app_api is the sub-app mounted at /api in server.main, so paths here carry no
    /api prefix. Binding to it (rather than to `app`) also skips the lifespan and
    the Redis connection, which tests neither have nor need.
    """
    # Imported lazily: pytest_configure above must set the DB env vars first.
    import server.db as server_db
    from server.main import app_api
    from server.routes.auth import CurrentUser, get_current_user

    # Bind server.db.database to this test's session, so `Depends(get_db)` runs
    # the real, un-overridden server.db.get_db against it for every request.
    monkeypatch.setattr(server_db, "database", _SessionBoundDatabase(session))

    # A CurrentUser with no backing Creator row: search never calls get_creator(),
    # and seeding one would pollute /instances/search/signature's creator list.
    app_api.dependency_overrides[get_current_user] = lambda: CurrentUser(
        creator_id=1, username="tester"
    )

    from eyened_orm.utils.factories import admin_scope
    from server.services.access_scope import get_access_scope

    # Existing route tests are not about authorization; give them an admin
    # scope so they keep testing what they were written to test. Tests that ARE
    # about authorization use the `client_scoped` fixture below, and the
    # deactivated-user test deliberately uses neither -- it must exercise the
    # real resolution.
    app_api.dependency_overrides[get_access_scope] = lambda: admin_scope()

    with TestClient(app_api) as c:
        yield c
    # Pop only what this fixture installed: app_api is a module-level singleton, so
    # clear() would silently delete overrides another fixture or test owns.
    app_api.dependency_overrides.pop(get_current_user, None)
    app_api.dependency_overrides.pop(get_access_scope, None)


@pytest.fixture()
def client_scoped(session, monkeypatch):
    """TestClient whose AccessScope the test sets, for authorization tests.

    Yields ``(client, set_scope)``; call ``set_scope(scope)`` before the request.
    """
    import server.db as server_db
    from server.main import app_api
    from server.routes.auth import CurrentUser, get_current_user
    from server.services.access_scope import get_access_scope
    from eyened_orm.utils.factories import admin_scope

    monkeypatch.setattr(server_db, "database", _SessionBoundDatabase(session))
    holder = {"scope": admin_scope()}

    app_api.dependency_overrides[get_current_user] = lambda: CurrentUser(
        creator_id=holder["scope"].actor_id, username=holder["scope"].username
    )
    app_api.dependency_overrides[get_access_scope] = lambda: holder["scope"]

    def set_scope(scope):
        holder["scope"] = scope

    with TestClient(app_api) as c:
        yield c, set_scope

    app_api.dependency_overrides.pop(get_current_user, None)
    app_api.dependency_overrides.pop(get_access_scope, None)


@pytest.fixture()
def client_anonymous(session, monkeypatch):
    """TestClient with NO auth override, for routes that must reject anonymity.

    The DB still has to be bound: get_current_user takes
    ``session: Session = Depends(get_db)`` and FastAPI resolves that
    sub-dependency *before* the auth check runs, so a bare TestClient(app_api)
    would open a real connection against whatever server.db.database points at
    rather than failing cleanly at the credential.
    """
    import server.db as server_db
    from server.main import app_api
    from server.routes.auth import get_current_user

    monkeypatch.setattr(server_db, "database", _SessionBoundDatabase(session))
    # app_api.dependency_overrides is module-level singleton state, and this
    # fixture asserts an *absence*. A leak from elsewhere would surface as an
    # inscrutable 200 or 500; say so instead.
    assert get_current_user not in app_api.dependency_overrides, (
        "an override leaked from another fixture; anonymity cannot be observed"
    )
    with TestClient(app_api) as c:
        yield c


@pytest.fixture()
def queue_spy(monkeypatch):
    """Record enqueues instead of reaching Redis.

    First queue stub in the suite -- nothing in server/tests touched RQ before
    Task 18. Both handlers' imports are function-local (`from ..main import
    queue` / `get_rq_queue`), so patching the module attributes is enough.
    One object serves as both: `get_rq_queue(name)` returns itself.

    Without it a *regressed* gate would reach Redis, the ConnectionError would
    be swallowed by each route's `except Exception` into a 200 with
    success=False, and the failure would read as a queue problem. So
    `queue_spy.enqueued == []` is what makes every negative case mean
    something; a bare status assertion is not enough.
    """
    import server.main as server_main

    class _Spy:
        def __init__(self) -> None:
            self.enqueued: list[tuple] = []

        def __call__(self, name):  # stands in for get_rq_queue(name)
            return self

        def enqueue(self, func, *args, **kwargs):
            self.enqueued.append((getattr(func, "__name__", func), args, kwargs))
            return SimpleNamespace(id=kwargs.get("job_id"))

    spy = _Spy()
    monkeypatch.setattr(server_main, "queue", spy)
    monkeypatch.setattr(server_main, "get_rq_queue", spy)
    return spy


@pytest.fixture()
def spanning(session):
    """Four tasks: one spanning projects A and B, one empty, one in A, one in B.

    Shared rather than local: later tasks build on the same shape, and two
    fixtures that drift apart would make their assertions mean different things.

    Two of the shapes exist for the write-floor tests and are load-bearing:

    ``b_only_single`` is a subtask of the project-B-only task holding **exactly
    one** image. The count is the point. On a two-image subtask an unscoped
    delete of one link leaves the task still spanning B, so the out-of-scope
    re-read afterwards returns ``None``, the route 500s and ``get_db`` rolls the
    delete back -- a test written on two links passes without the fix. On one
    link the delete commits and the project-B subtask comes back in the body.

    ``empty_subtask`` is a subtask of the link-less task, so every check keyed
    on a resolved project set runs on the empty set there.
    """
    from datetime import date

    from eyened_orm import SubTask, Task, TaskDefinition
    from eyened_orm.task import SubTaskImageLink, SubTaskState, TaskState
    from eyened_orm.utils.factories import (
        make_device,
        make_image,
        make_patient,
        make_project,
        make_series,
        make_storage_backend,
        make_study,
    )

    backend = make_storage_backend(session)
    device = make_device(session, "d")
    projects, images, public_ids = {}, {}, {}
    for name in ("A", "B"):
        project = make_project(session, name)
        patient = make_patient(session, project, f"pat-{name}")
        study = make_study(session, patient, date(2024, 1, 1))
        series = make_series(session, study)
        image = make_image(session, series, device, backend, f"img-{name}")
        projects[name] = project.ProjectID
        images[name] = image.ImageInstanceID
        public_ids[name] = image.PublicID

    taskdef = TaskDefinition(TaskDefinitionName="def")
    session.add(taskdef)
    session.flush()
    taskdef_id = taskdef.TaskDefinitionID
    tasks = {}
    for label in ("spanning", "empty", "a_only", "b_only"):
        task = Task(
            TaskName=label,
            TaskDefinitionID=taskdef.TaskDefinitionID,
            TaskState=TaskState.NotStarted,
        )
        session.add(task)
        session.flush()
        tasks[label] = task.TaskID

    subtasks = {}
    for label, names in (
        ("spanning", ("A", "B")),
        ("a_only", ("A",)),
        ("b_only", ("B",)),
    ):
        for name in names:
            subtask = SubTask(TaskID=tasks[label], TaskState=SubTaskState.NotStarted)
            session.add(subtask)
            session.flush()
            session.add(
                SubTaskImageLink(
                    SubTaskID=subtask.SubTaskID,
                    ImageInstanceID=images[name],
                    ImageIndex=0,
                )
            )
            subtasks[f"{label}-{name}"] = subtask.SubTaskID

    linkless = SubTask(TaskID=tasks["empty"], TaskState=SubTaskState.NotStarted)
    session.add(linkless)
    session.flush()
    # Read the ids out before the commit: expire_on_commit=True, and an
    # expired instance re-loads through whatever session the test later has.
    linkless_id = linkless.SubTaskID
    session.commit()
    return {
        "projects": projects,
        "images": images,
        "public_ids": public_ids,
        "task_definition": taskdef_id,
        "task": tasks["spanning"],
        "empty": tasks["empty"],
        "a_only": tasks["a_only"],
        "b_only": tasks["b_only"],
        "subtasks": subtasks,
        "b_only_single": subtasks["b_only-B"],
        "empty_subtask": linkless_id,
    }


@pytest.fixture()
def one_project(session):
    """One project holding every shape the single-project role floors need.

    The gap tests in ``test_project_role_permissions.py`` all act inside one
    project -- containment across two is ``spanning``'s job -- and they share
    one shape, so a per-test fixture would triple that file.

    Attribute names mirror ``spanning``'s keys in the singular (``project``,
    ``image``, ``public_id``, ``task``, ``subtask``) so the two do not drift.

    Two segmentations, authored by two different creators: the delete-own cell
    needs a row the actor wrote, and the author-identity cell needs a row it
    did **not**, or "the response carries an author" would be satisfied by the
    caller's own name.

    Every value returned is a plain id read out *before* ``commit()``:
    ``expire_on_commit=True``, so returning live ORM instances would make each
    attribute access a fresh load through whatever session the test then has.
    """
    from datetime import date

    from eyened_orm import SubTask, Task, TaskDefinition
    from eyened_orm.task import SubTaskImageLink, SubTaskState, TaskState
    from eyened_orm.utils.factories import (
        make_creator,
        make_device,
        make_feature,
        make_image,
        make_patient,
        make_project,
        make_segmentation,
        make_series,
        make_storage_backend,
        make_study,
        scope_for,
    )

    backend = make_storage_backend(session)
    device = make_device(session, "d")
    project = make_project(session, "P")
    patient = make_patient(session, project, "pat")
    study = make_study(session, patient, date(2024, 1, 1))
    series = make_series(session, study)
    image = make_image(session, series, device, backend, "img")
    feature = make_feature(session, "feat")

    actor = make_creator(session, "actor")
    other = make_creator(session, "other")
    own_segmentation = make_segmentation(session, image, feature, actor)
    foreign_segmentation = make_segmentation(session, image, feature, other)

    taskdef = TaskDefinition(TaskDefinitionName="def")
    session.add(taskdef)
    session.flush()
    task = Task(
        TaskName="t",
        TaskDefinitionID=taskdef.TaskDefinitionID,
        TaskState=TaskState.NotStarted,
    )
    session.add(task)
    session.flush()
    subtask = SubTask(TaskID=task.TaskID, TaskState=SubTaskState.NotStarted)
    session.add(subtask)
    session.flush()
    # The link is what makes the task *populated*: without it the task touches
    # no projects and every floor on it fails closed, so the project-admin
    # delete cell would pass for the wrong reason.
    session.add(
        SubTaskImageLink(
            SubTaskID=subtask.SubTaskID,
            ImageInstanceID=image.ImageInstanceID,
            ImageIndex=0,
        )
    )
    session.flush()

    project_id = project.ProjectID
    actor_id = actor.CreatorID
    data = SimpleNamespace(
        project=project_id,
        patient=patient.PatientID,
        image=image.ImageInstanceID,
        public_id=image.PublicID,
        feature=feature.FeatureID,
        actor=actor_id,
        own_segmentation=own_segmentation.SegmentationID,
        foreign_segmentation=foreign_segmentation.SegmentationID,
        task=task.TaskID,
        subtask=subtask.SubTaskID,
        scope=lambda role: scope_for(project_id, role=role, actor_id=actor_id),
    )
    session.commit()
    return data


@pytest.fixture()
def signed_jwts(monkeypatch):
    """Give JWT issuance/verification a usable HMAC key.

    Default test settings leave Settings.secret_key empty, which HS256
    signing rejects; any auth test that hits a route issuing or verifying a
    JWT (login, refresh, oidc/authenticate, ...) needs this.
    """
    from server.config import Settings

    monkeypatch.setattr(
        Settings,
        "secret_key_value",
        property(lambda self: "test-secret-key-0123456789abcdef"),
    )
