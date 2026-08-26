import uuid

import pytest

from eyened_orm import Creator, SubTask, Task, TaskDefinition
from eyened_orm.task import SubTaskState, TaskState
from eyened_orm.repositories.task_repository import SubTaskRepository

from server.services.acting_user import ActingUser
from server.services.exceptions import ConflictError, NotFoundError
from server.services.task_service import SubTaskService
from eyened_orm.utils.factories import admin_scope


class FakeAudit:
    """Records .record() calls without touching the filesystem (no mock lib)."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def record(self, **kwargs) -> None:
        self.records.append(kwargs)


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


def test_update_subtask_comments_claims_unassigned_subtask(session):
    """update_subtask with comments on an unassigned subtask claims it for the actor."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    session.commit()

    _service(session, actor).update_subtask(st.SubTaskID, "hi", None)

    session.refresh(st)
    assert st.CreatorID == actor.id


def test_update_subtask_state_claims_unassigned_subtask(session):
    """update_subtask with task_state on an unassigned subtask claims it for the actor."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    session.commit()

    _service(session, actor).update_subtask(st.SubTaskID, None, SubTaskState.Ready)

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

    _service(session, actor).update_subtask(st.SubTaskID, "hi", None)

    session.refresh(st)
    assert st.CreatorID == other_creator.CreatorID


def test_update_subtask_claim_assigns(session):
    """claim=True on an unassigned subtask sets CreatorID to the actor."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    session.commit()

    updated = _service(session, actor).update_subtask(
        st.SubTaskID, None, None, claim=True
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
        _service(session, actor).update_subtask(
            st.SubTaskID, None, None, claim=True
        )
    assert exc.value.detail["code"] == "subtask_already_claimed"
    assert exc.value.detail["creator_id"] == owner.id


def test_update_subtask_claim_conflict_when_concurrent_claim_wins(session):
    """claim=True raises ConflictError if the conditional UPDATE loses the race.

    Simulates another writer assigning the subtask after our load: UPDATE the
    row out from under the identity map, then claim must fail (not succeed).
    """
    owner = _actor(session)
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, owner.id)
    st = _make_subtask(session, task.TaskID)
    session.commit()

    # Concurrent winner: assign via repository UPDATE (does not sync identity).
    assert SubTaskRepository(session, scope=admin_scope()).claim_if_unassigned(
        st.SubTaskID, owner.id
    )
    session.commit()

    with pytest.raises(ConflictError) as exc:
        _service(session, actor).update_subtask(
            st.SubTaskID, None, None, claim=True
        )
    assert exc.value.detail["code"] == "subtask_already_claimed"
    assert exc.value.detail["creator_id"] == owner.id


def test_update_subtask_unclaim_releases_own(session):
    """claim=False clears CreatorID when the actor owns the subtask."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    st.CreatorID = actor.id
    session.commit()

    updated = _service(session, actor).update_subtask(
        st.SubTaskID, None, None, claim=False
    )
    assert updated.CreatorID is None


def test_update_subtask_unclaim_conflict_when_owned_by_other(session):
    """claim=False raises ConflictError when a different creator owns it."""
    owner = _actor(session)
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, owner.id)
    st = _make_subtask(session, task.TaskID)
    st.CreatorID = owner.id
    session.commit()

    with pytest.raises(ConflictError) as exc:
        _service(session, actor).update_subtask(
            st.SubTaskID, None, None, claim=False
        )
    assert exc.value.detail["code"] == "subtask_not_owned"


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
    st.CreatorID = actor.id  # already assigned: isolate comments diff from auto-claim
    session.flush()
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

    updated = _service(session, actor).add_image(st.SubTaskID, "pub-1")

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
    _make_image(session, "pub-1")
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
    _make_image(session, "pub-1")
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
    _make_image(session, "pub-1")
    service = _service(session, actor)
    service.add_image(st.SubTaskID, "pub-1")
    audit = FakeAudit()
    _service(session, actor, audit=audit).remove_image(st.SubTaskID, "pub-1")

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "DELETE"
    assert audit.records[0]["entity"] == "SubTaskImageLink"
