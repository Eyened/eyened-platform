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
