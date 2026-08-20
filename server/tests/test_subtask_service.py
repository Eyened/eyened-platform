import pytest

from eyened_orm import Creator, SubTask, Task, TaskDefinition
from eyened_orm.task import SubTaskState, TaskState
from eyened_orm.repositories.task_repository import SubTaskRepository

from server.services.acting_user import ActingUser
from server.services.exceptions import NotFoundError
from server.services.task_service import SubTaskService
from eyened_orm.utils.factories import admin_scope


class FakeAudit:
    """Records .record() calls without touching the filesystem (no mock lib)."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def record(self, **kwargs) -> None:
        self.records.append(kwargs)


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


def _service(
    session, actor: ActingUser | None = None, *, audit=None
) -> SubTaskService:
    scope = (
        admin_scope(actor_id=actor.id, username=actor.username)
        if actor is not None
        else admin_scope()
    )
    return SubTaskService(
        SubTaskRepository(session, scope=scope),
        scope=scope,
        audit=audit,
    )


def test_get_subtask_unknown_raises_not_found(session):
    """Getting a missing subtask is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).get_subtask(999_999, with_images=False)


def test_update_subtask_changes_fields(session):
    """update_subtask overwrites the provided comments and task_state."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)

    updated = _service(session, actor).update_subtask(
        st.SubTaskID, "newcomment", SubTaskState.Ready
    )

    assert updated.Comments == "newcomment"
    assert updated.TaskState == SubTaskState.Ready


def test_update_subtask_unknown_raises_not_found(session):
    """Updating a missing subtask is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    with pytest.raises(NotFoundError):
        _service(session, actor).update_subtask(999_999, "x", None)


def test_update_subtask_logs_update_as_diff(session):
    """Updating a subtask's comments emits an UPDATE record diff-shaped {old, new}."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    audit = FakeAudit()

    _service(session, actor, audit=audit).update_subtask(st.SubTaskID, "c", None)

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "UPDATE"
    assert audit.records[0]["entity"] == "SubTask"
    assert audit.records[0]["changes"] == {"Comments": {"old": "orig", "new": "c"}}
    assert audit.records[0]["actor"] == actor


def test_delete_subtask_removes_it(session):
    """delete_subtask removes the subtask row."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)

    _service(session, actor).delete_subtask(st.SubTaskID)

    assert SubTaskRepository(session, scope=admin_scope()).get_by_id(st.SubTaskID) is None


def test_delete_subtask_unknown_raises_not_found(session):
    """Deleting a missing subtask is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    with pytest.raises(NotFoundError):
        _service(session, actor).delete_subtask(999_999)


def test_delete_subtask_logs_delete(session):
    """delete_subtask emits one DELETE audit record for the SubTask entity."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    audit = FakeAudit()

    _service(session, actor, audit=audit).delete_subtask(st.SubTaskID)

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "DELETE"
    assert audit.records[0]["entity"] == "SubTask"


def _make_image(session, public_id: str, project_id: int | None = None) -> int:
    """Build the minimal Series/Device graph an ImageInstance FK-requires.

    ``project_id`` lets two calls in the same test share one project; the
    default -- a fresh project per call -- is unchanged everywhere except
    test_add_image_second_image_gets_next_index, the one site that needs it.

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

    if project_id is None:
        project = Project(ProjectName=f"P-{public_id}", External=ExternalEnum.N)
        session.add(project)
        session.flush()
        project_id = project.ProjectID
    patient = Patient(PatientIdentifier=f"ID-{public_id}", ProjectID=project_id)
    session.add(patient)
    session.flush()
    study = Study(PatientID=patient.PatientID, StudyDate=datetime.date(2020, 1, 1))
    session.add(study)
    session.flush()
    series = Series(StudyID=study.StudyID)
    session.add(series)
    session.flush()
    model = DeviceModel(Manufacturer=f"Mf-{public_id}", ManufacturerModelName=f"M-{public_id}")
    session.add(model)
    session.flush()
    device = DeviceInstance(DeviceModelID=model.DeviceModelID, Description=f"d-{public_id}")
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


def _declare(session, task_id: int, image_id: int) -> None:
    """Declare, on ``task_id``, the project the image sits in.

    Same helper as orm/eyened_orm/tests/test_task_repository.py's _declare:
    read off the image rather than passed in, so the declaration cannot
    drift from the project _make_image actually built.
    """
    from eyened_orm import ImageInstance, TaskProject

    project_id = session.get(ImageInstance, image_id).ProjectID
    session.add(TaskProject(TaskID=task_id, ProjectID=project_id))
    session.flush()


def test_add_image_appends_link_at_next_index(session):
    """add_image links the image to the subtask at the next ImageIndex."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    image_id = _make_image(session, "pub-1")
    _declare(session, task.TaskID, image_id)

    updated = _service(session, actor).add_image(st.SubTaskID, "pub-1")

    assert [link.ImageInstance.PublicID for link in updated.SubTaskImageLinks] == ["pub-1"]
    assert [link.ImageIndex for link in updated.SubTaskImageLinks] == [0]


def test_add_image_second_image_gets_next_index(session):
    """A second add_image lands at ImageIndex 1, keeping insertion order."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    from eyened_orm import ImageInstance

    # One project for both images, and therefore one declaration. The
    # two-project shape this replaces was an artifact of _make_image minting a
    # fresh project per call, not something the ImageIndex ordering under test
    # needs.
    id1 = _make_image(session, "pub-1")
    project_id = session.get(ImageInstance, id1).ProjectID
    _make_image(session, "pub-2", project_id=project_id)
    _declare(session, task.TaskID, id1)
    service = _service(session, actor)

    service.add_image(st.SubTaskID, "pub-1")
    # The service no longer commits (get_db owns the request-scoped
    # transaction); commit here to cross the same request boundary a second
    # real HTTP call would get for free via a brand-new session, so the
    # eager-loaded SubTaskImageLinks collection below is reloaded fresh
    # rather than served stale from the identity map.
    session.commit()
    updated = service.add_image(st.SubTaskID, "pub-2")

    assert [link.ImageIndex for link in updated.SubTaskImageLinks] == [0, 1]


def test_add_image_unknown_subtask_raises_not_found(session):
    """add_image on a missing subtask is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    with pytest.raises(NotFoundError):
        _service(session, actor).add_image(999_999, "pub-1")


def test_add_image_unknown_image_raises_not_found(session):
    """add_image with an unknown PublicID is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    with pytest.raises(NotFoundError):
        _service(session, actor).add_image(st.SubTaskID, "nope")


def test_add_image_logs_insert(session):
    """add_image emits one INSERT audit record for the SubTaskImageLink entity."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    image_id = _make_image(session, "pub-1")
    _declare(session, task.TaskID, image_id)
    audit = FakeAudit()

    _service(session, actor, audit=audit).add_image(st.SubTaskID, "pub-1")

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "INSERT"
    assert audit.records[0]["entity"] == "SubTaskImageLink"


def test_remove_image_deletes_the_link(session):
    """remove_image deletes the link for that image, leaving the subtask empty."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    image_id = _make_image(session, "pub-1")
    _declare(session, task.TaskID, image_id)
    service = _service(session, actor)
    service.add_image(st.SubTaskID, "pub-1")
    # Cross the request boundary a real second HTTP call would get for free
    # via a brand-new session (see test_add_image_second_image_gets_next_index).
    session.commit()

    updated = service.remove_image(st.SubTaskID, "pub-1")

    assert updated.SubTaskImageLinks == []


def test_remove_image_unknown_image_raises_not_found(session):
    """remove_image with an unknown PublicID is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    with pytest.raises(NotFoundError):
        _service(session, actor).remove_image(st.SubTaskID, "nope")


def test_remove_image_unlinked_image_raises_not_found(session):
    """remove_image for an image not linked to the subtask raises NotFoundError."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    _make_image(session, "pub-1")  # exists, but never linked
    with pytest.raises(NotFoundError):
        _service(session, actor).remove_image(st.SubTaskID, "pub-1")


def test_remove_image_logs_delete(session):
    """remove_image emits one DELETE audit record for the SubTaskImageLink entity."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    image_id = _make_image(session, "pub-1")
    _declare(session, task.TaskID, image_id)
    service = _service(session, actor)
    service.add_image(st.SubTaskID, "pub-1")
    audit = FakeAudit()
    _service(session, actor, audit=audit).remove_image(st.SubTaskID, "pub-1")

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "DELETE"
    assert audit.records[0]["entity"] == "SubTaskImageLink"
