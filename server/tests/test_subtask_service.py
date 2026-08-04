import pytest
from sqlalchemy import select

from eyened_orm import Creator, Project, SubTask, SubTaskImageLink, Task, TaskDefinition
from eyened_orm.project import ExternalEnum
from eyened_orm.task import SubTaskState, TaskState
from eyened_orm.repositories.task_repository import SubTaskRepository

from server.services.acting_user import ActingUser
from server.services.exceptions import NotFoundError
from server.services.task_service import SubTaskService


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


def _project_for(session, name: str) -> Project:
    """One project per task name -- derived from the name, never a counter, so
    it is stable under `pytest -k` selection. Re-used if it already exists."""
    existing = session.scalar(
        select(Project).where(Project.ProjectName == f"proj-{name}")
    )
    if existing is not None:
        return existing
    project = Project(ProjectName=f"proj-{name}", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    return project


def _make_task(session, td_id: int, creator_id: int, name: str = "T") -> Task:
    task = Task(
        TaskName=name,
        TaskDefinitionID=td_id,
        CreatorID=creator_id,
        TaskState=TaskState.NotStarted,
        ProjectID=_project_for(session, name).ProjectID,
    )
    session.add(task)
    session.flush()
    return task


def _make_subtask(session, task_id: int, state: SubTaskState = SubTaskState.NotStarted) -> SubTask:
    st = SubTask(TaskID=task_id, TaskState=state, Comments="orig")
    session.add(st)
    session.flush()
    return st


def _service(session, audit=None) -> SubTaskService:
    return SubTaskService(SubTaskRepository(session), audit=audit)


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

    updated = _service(session).update_subtask(
        st.SubTaskID, "newcomment", SubTaskState.Ready, actor
    )

    assert updated.Comments == "newcomment"
    assert updated.TaskState == SubTaskState.Ready


def test_update_subtask_unknown_raises_not_found(session):
    """Updating a missing subtask is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    with pytest.raises(NotFoundError):
        _service(session).update_subtask(999_999, "x", None, actor)


def test_update_subtask_logs_update_as_diff(session):
    """Updating a subtask's comments emits an UPDATE record diff-shaped {old, new}."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    audit = FakeAudit()

    _service(session, audit).update_subtask(st.SubTaskID, "c", None, actor)

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "UPDATE"
    assert audit.records[0]["entity"] == "SubTask"
    assert audit.records[0]["changes"] == {"Comments": {"old": "orig", "new": "c"}}


def test_delete_subtask_removes_it(session):
    """delete_subtask removes the subtask row."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)

    _service(session).delete_subtask(st.SubTaskID, actor)

    assert SubTaskRepository(session).get_by_id(st.SubTaskID) is None


def test_delete_subtask_unknown_raises_not_found(session):
    """Deleting a missing subtask is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    with pytest.raises(NotFoundError):
        _service(session).delete_subtask(999_999, actor)


def test_delete_subtask_logs_delete(session):
    """delete_subtask emits one DELETE audit record for the SubTask entity."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    audit = FakeAudit()

    _service(session, audit).delete_subtask(st.SubTaskID, actor)

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "DELETE"
    assert audit.records[0]["entity"] == "SubTask"


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


def test_add_image_appends_link_at_next_index(session):
    """add_image links the image to the subtask at the next ImageIndex."""
    from eyened_orm.utils.factories import make_image_in_project

    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    project = session.get(Project, task.ProjectID)
    make_image_in_project(session, project, "pub-1")

    updated = _service(session).add_image(st.SubTaskID, "pub-1", actor)

    assert [link.ImageInstance.PublicID for link in updated.SubTaskImageLinks] == ["pub-1"]
    assert [link.ImageIndex for link in updated.SubTaskImageLinks] == [0]


def test_add_image_second_image_gets_next_index(session):
    """A second add_image lands at ImageIndex 1, keeping insertion order."""
    from eyened_orm.utils.factories import make_image_in_project

    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    project = session.get(Project, task.ProjectID)
    make_image_in_project(session, project, "pub-1")
    make_image_in_project(session, project, "pub-2")
    service = _service(session)

    service.add_image(st.SubTaskID, "pub-1", actor)
    # The service no longer commits (get_db owns the request-scoped
    # transaction); commit here to cross the same request boundary a second
    # real HTTP call would get for free via a brand-new session, so the
    # eager-loaded SubTaskImageLinks collection below is reloaded fresh
    # rather than served stale from the identity map.
    session.commit()
    updated = service.add_image(st.SubTaskID, "pub-2", actor)

    assert [link.ImageIndex for link in updated.SubTaskImageLinks] == [0, 1]


def test_add_image_unknown_subtask_raises_not_found(session):
    """add_image on a missing subtask is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    with pytest.raises(NotFoundError):
        _service(session).add_image(999_999, "pub-1", actor)


def test_add_image_unknown_image_raises_not_found(session):
    """add_image with an unknown PublicID is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    with pytest.raises(NotFoundError):
        _service(session).add_image(st.SubTaskID, "nope", actor)


def test_add_image_logs_insert(session):
    """add_image emits one INSERT audit record for the SubTaskImageLink entity."""
    from eyened_orm.utils.factories import make_image_in_project

    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    project = session.get(Project, task.ProjectID)
    make_image_in_project(session, project, "pub-1")
    audit = FakeAudit()

    _service(session, audit).add_image(st.SubTaskID, "pub-1", actor)

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "INSERT"
    assert audit.records[0]["entity"] == "SubTaskImageLink"


def test_remove_image_deletes_the_link(session):
    """remove_image deletes the link for that image, leaving the subtask empty."""
    from eyened_orm.utils.factories import make_image_in_project

    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    project = session.get(Project, task.ProjectID)
    make_image_in_project(session, project, "pub-1")
    service = _service(session)
    service.add_image(st.SubTaskID, "pub-1", actor)
    # Cross the request boundary a real second HTTP call would get for free
    # via a brand-new session (see test_add_image_second_image_gets_next_index).
    session.commit()

    updated = service.remove_image(st.SubTaskID, "pub-1", actor)

    assert updated.SubTaskImageLinks == []


def test_remove_image_unknown_image_raises_not_found(session):
    """remove_image with an unknown PublicID is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    with pytest.raises(NotFoundError):
        _service(session).remove_image(st.SubTaskID, "nope", actor)


def test_remove_image_unlinked_image_raises_not_found(session):
    """remove_image for an image not linked to the subtask raises NotFoundError."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    _make_image(session, "pub-1")  # exists, but never linked
    with pytest.raises(NotFoundError):
        _service(session).remove_image(st.SubTaskID, "pub-1", actor)


def test_remove_image_logs_delete(session):
    """remove_image emits one DELETE audit record for the SubTaskImageLink entity."""
    from eyened_orm.utils.factories import make_image_in_project

    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    project = session.get(Project, task.ProjectID)
    make_image_in_project(session, project, "pub-1")
    service = _service(session)
    service.add_image(st.SubTaskID, "pub-1", actor)
    audit = FakeAudit()
    SubTaskService(SubTaskRepository(session), audit=audit).remove_image(
        st.SubTaskID, "pub-1", actor
    )

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "DELETE"
    assert audit.records[0]["entity"] == "SubTaskImageLink"


def test_add_image_refuses_an_image_from_another_project(session):
    """The invariant is a data rule, enforced for every caller regardless of role."""
    from server.services.exceptions import BadRequestError
    from eyened_orm.utils.factories import make_image_in_project, make_project

    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id, "anchored")
    subtask = SubTask(TaskID=task.TaskID, TaskState=SubTaskState.NotStarted)
    session.add(subtask)
    session.flush()

    other = make_project(session, "P-foreign")
    foreign = make_image_in_project(session, other, "foreign-1")

    with pytest.raises(BadRequestError) as exc:
        _service(session).add_image(subtask.SubTaskID, foreign.PublicID, actor)

    # Both projects named: the operator has to know which side to fix.
    assert str(task.ProjectID) in str(exc.value)
    assert str(other.ProjectID) in str(exc.value)


def test_add_image_compares_against_the_task_not_its_sibling_links(session):
    """The subtask's existing links are irrelevant -- the task's anchor decides.

    A subtask holding a grandfathered cross-project link must still accept an
    image from its own task's project.
    """
    from eyened_orm.utils.factories import make_image_in_project, make_project

    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id, "sibling")
    subtask = SubTask(TaskID=task.TaskID, TaskState=SubTaskState.NotStarted)
    session.add(subtask)
    session.flush()

    # A pre-existing link into some *other* project, written directly (the API
    # path being tested is what now refuses to create one).
    other = make_project(session, "P-legacy")
    legacy = make_image_in_project(session, other, "legacy-1")
    session.add(
        SubTaskImageLink(
            SubTaskID=subtask.SubTaskID,
            ImageInstanceID=legacy.ImageInstanceID,
            ImageIndex=0,
        )
    )
    session.flush()

    own_project = session.get(Project, task.ProjectID)
    ours = make_image_in_project(session, own_project, "ours-1")

    result = _service(session).add_image(subtask.SubTaskID, ours.PublicID, actor)

    assert ours.ImageInstanceID in {
        link.ImageInstanceID for link in result.SubTaskImageLinks
    }
