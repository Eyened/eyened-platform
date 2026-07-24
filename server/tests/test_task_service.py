import pytest

from eyened_orm import Creator, SubTask, Task, TaskDefinition
from eyened_orm.task import SubTaskState, TaskState
from eyened_orm.repositories.task_repository import SubTaskRepository, TaskRepository

from server.services.acting_user import ActingUser
from server.services.exceptions import BadRequestError, NotFoundError
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


_actor_seq = 0


def _actor(session) -> ActingUser:
    """An ActingUser backed by a real Creator row (Task.CreatorID is a FK)."""
    global _actor_seq
    _actor_seq += 1
    creator = Creator(CreatorName=f"alice-{_actor_seq}", IsHuman=True)
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


def test_list_task_subtasks_filters_unassigned(session):
    """unassigned=True returns only subtasks with CreatorID NULL."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    unassigned = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    assigned = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    assigned.CreatorID = actor.id
    session.commit()

    rows, count = _service().list_task_subtasks(
        session,
        task.TaskID,
        with_images=False,
        limit=10,
        page=0,
        status=None,
        unassigned=True,
    )

    assert count == 1
    assert [st.SubTaskID for st, _ in rows] == [unassigned.SubTaskID]


def test_list_task_subtasks_rejects_unassigned_and_creator_id(session):
    """Passing both unassigned and creator_id raises BadRequestError."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    session.commit()

    with pytest.raises(BadRequestError):
        _service().list_task_subtasks(
            session,
            task.TaskID,
            with_images=False,
            limit=10,
            page=0,
            status=None,
            unassigned=True,
            creator_id=actor.id,
        )


def test_list_subtask_assignees_returns_distinct_creators(session):
    """list_subtask_assignees returns creators with at least one claimed subtask."""
    owner = _actor(session)
    other = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, owner.id)
    _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    a = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    a.CreatorID = owner.id
    b = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    b.CreatorID = other.id
    session.commit()

    assignees = _service().list_subtask_assignees(session, task.TaskID)
    assert {c.CreatorID for c in assignees} == {owner.id, other.id}
