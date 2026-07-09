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
