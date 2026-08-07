from eyened_orm import Creator, SubTask, Task, TaskDefinition
from eyened_orm.task import SubTaskState, TaskState
from eyened_orm.repositories.task_repository import TaskRepository, SubTaskRepository
from eyened_orm.utils.factories import admin_scope


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

    tasks = TaskRepository(session, scope=admin_scope()).list_all()

    assert [t.TaskName for t in tasks] == ["A", "B"]
    # Eager-loaded: reading these needs no extra lazy query.
    assert tasks[0].Creator.CreatorName == "tester"
    assert tasks[0].TaskDefinition.TaskDefinitionName == "td"


def test_get_with_relations_eager_loads_creator_and_definition(session):
    """get_with_relations returns the task with Creator + TaskDefinition loaded."""
    creator = _creator(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, creator.CreatorID)

    loaded = TaskRepository(session, scope=admin_scope()).get_with_relations(task.TaskID)

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

    counts = TaskRepository(session, scope=admin_scope()).subtask_counts([task.TaskID])

    assert counts[task.TaskID] == (3, 2)


def test_subtask_counts_fills_zero_for_task_without_subtasks(session):
    """A requested task id with no subtasks maps to (0, 0), not a missing key."""
    creator = _creator(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, creator.CreatorID)

    counts = TaskRepository(session, scope=admin_scope()).subtask_counts([task.TaskID])

    assert counts == {task.TaskID: (0, 0)}


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

    ids = SubTaskRepository(session, scope=admin_scope()).all_ids_for_task(task.TaskID)

    assert ids == [a.SubTaskID, b.SubTaskID]


def test_count_for_task_with_and_without_status(session):
    """count_for_task counts all subtasks, or only those in the given state."""
    creator = _creator(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, creator.CreatorID)
    _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    _make_subtask(session, task.TaskID, SubTaskState.Ready)
    _make_subtask(session, task.TaskID, SubTaskState.Ready)
    repo = SubTaskRepository(session, scope=admin_scope())

    assert repo.count_for_task(task.TaskID) == 3
    assert repo.count_for_task(task.TaskID, status=SubTaskState.Ready) == 2


def test_list_for_task_paginates_in_id_order(session):
    """list_for_task returns a limit/offset window ordered by SubTaskID."""
    creator = _creator(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, creator.CreatorID)
    made = [
        _make_subtask(session, task.TaskID, SubTaskState.NotStarted) for _ in range(5)
    ]

    rows = SubTaskRepository(session, scope=admin_scope()).list_for_task(task.TaskID, limit=2, offset=1)

    assert [r.SubTaskID for r in rows] == [made[1].SubTaskID, made[2].SubTaskID]


def test_list_for_task_filters_by_status(session):
    """list_for_task with a status returns only subtasks in that state."""
    creator = _creator(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, creator.CreatorID)
    _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    ready = _make_subtask(session, task.TaskID, SubTaskState.Ready)

    rows = SubTaskRepository(session, scope=admin_scope()).list_for_task(
        task.TaskID, status=SubTaskState.Ready, limit=10, offset=0
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

    rows = SubTaskRepository(session, scope=admin_scope()).list_for_task(
        task.TaskID, limit=10, offset=0, with_images=True
    )

    assert len(rows) == 1
    assert [link.ImageInstance.PublicID for link in rows[0].SubTaskImageLinks] == [
        "pub-1"
    ]


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

    loaded = SubTaskRepository(session, scope=admin_scope()).get_with_images(st.SubTaskID)

    assert loaded is not None
    assert [link.ImageInstance.PublicID for link in loaded.SubTaskImageLinks] == ["pub-1"]


def test_resolve_image_instance_id_found_and_missing(session):
    """resolve_image_instance_id maps a PublicID to its int id, or None if absent."""
    image_id = _make_image(session, "pub-42")
    repo = SubTaskRepository(session, scope=admin_scope())

    assert repo.resolve_image_instance_id("pub-42") == image_id
    assert repo.resolve_image_instance_id("nope") is None


def test_next_image_index_starts_at_zero_then_increments(session):
    """next_image_index is 0 for a subtask with no links, else max(ImageIndex)+1."""
    creator = _creator(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, creator.CreatorID)
    st = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    image_id = _make_image(session, "pub-1")
    repo = SubTaskRepository(session, scope=admin_scope())

    assert repo.next_image_index(st.SubTaskID) == 0

    from eyened_orm import SubTaskImageLink

    session.add(
        SubTaskImageLink(SubTaskID=st.SubTaskID, ImageInstanceID=image_id, ImageIndex=3)
    )
    session.flush()

    assert repo.next_image_index(st.SubTaskID) == 4
