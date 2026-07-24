import uuid

import pytest

from eyened_orm import Creator, SubTask, Task, TaskDefinition
from eyened_orm.task import SubTaskState, TaskState
from eyened_orm.repositories.task_repository import SubTaskRepository

from server.services.acting_user import ActingUser
from server.services.exceptions import ConflictError, NotFoundError
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
    creator = Creator(CreatorName=f"alice-{uuid.uuid4().hex[:8]}", IsHuman=True)
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


def test_update_subtask_comments_claims_unassigned_subtask(session):
    """update_subtask with comments on an unassigned subtask claims it for the actor."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    session.commit()

    _service().update_subtask(session, st.SubTaskID, "hi", None, actor)

    session.refresh(st)
    assert st.CreatorID == actor.id


def test_update_subtask_state_claims_unassigned_subtask(session):
    """update_subtask with task_state on an unassigned subtask claims it for the actor."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    session.commit()

    _service().update_subtask(session, st.SubTaskID, None, SubTaskState.Ready, actor)

    session.refresh(st)
    assert st.CreatorID == actor.id


def test_update_subtask_comments_already_assigned_unchanged(session):
    """update_subtask with comments on an already-assigned subtask leaves CreatorID unchanged."""
    other_creator = Creator(CreatorName="owner", IsHuman=True)
    session.add(other_creator)
    session.flush()
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    st.CreatorID = other_creator.CreatorID
    session.commit()

    _service().update_subtask(session, st.SubTaskID, "hi", None, actor)

    session.refresh(st)
    assert st.CreatorID == other_creator.CreatorID


def test_update_subtask_claim_assigns(session):
    """claim=True on an unassigned subtask sets CreatorID to the actor."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    session.commit()

    updated = _service().update_subtask(
        session, st.SubTaskID, None, None, actor, claim=True
    )
    assert updated.CreatorID == actor.id


def test_update_subtask_claim_conflict_when_assigned(session):
    """claim=True on an already-assigned subtask raises ConflictError."""
    owner = _actor(session)
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, owner.id)
    st = _make_subtask(session, task.TaskID)
    st.CreatorID = owner.id
    session.commit()

    with pytest.raises(ConflictError) as exc:
        _service().update_subtask(
            session, st.SubTaskID, None, None, actor, claim=True
        )
    assert exc.value.detail["code"] == "subtask_already_claimed"


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
