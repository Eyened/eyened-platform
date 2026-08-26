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

    Plus one ``ImageStorage`` on its own ``StorageBackend``: those are not FK
    requirements, they are the last two legs of ``_SUBTASK_IMAGE_LOADER``, and
    the eager-load tests below cannot observe a leg with no row at the end of
    it. Keys are derived from ``public_id`` so two images in one test do not
    collide.
    """
    import datetime

    from eyened_orm import (
        DeviceInstance,
        DeviceModel,
        ImageInstance,
        ImageStorage,
        Patient,
        Project,
        Series,
        StorageBackend,
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
    backend = StorageBackend(Key=f"backend-{public_id}", Kind="local")
    session.add(backend)
    session.flush()
    session.add(
        ImageStorage(
            ImageInstanceID=image.ImageInstanceID,
            StorageBackendID=backend.StorageBackendID,
            ObjectKey=f"obj-{public_id}",
            Format="png",
            IsPrimary=True,
        )
    )
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


def _seed_subtask_with_one_image(session) -> tuple[int, int]:
    """Seed a task/subtask/image link and COMMIT. Returns (task_id, subtask_id).

    Committing rather than flushing, and returning ids rather than instances, is
    what makes the two eager-load tests below able to fail. Seeding and reading
    on one uncommitted session serves every relationship access out of the
    identity map, so the loader's presence is unobservable -- these two tests
    were fully green with the eager loading deleted outright.

    Ids are captured before the commit: ``expire_on_commit=True`` (production's
    setting, mirrored by the fixture) expires every attribute, and after
    ``expunge_all()`` a re-read would raise ``DetachedInstanceError``.
    """
    from eyened_orm import SubTaskImageLink

    creator = _creator(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, creator.CreatorID)
    st = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    image_id = _make_image(session, "pub-1")
    session.add(
        SubTaskImageLink(
            SubTaskID=st.SubTaskID, ImageInstanceID=image_id, ImageIndex=0
        )
    )
    task_id, subtask_id = task.TaskID, st.SubTaskID
    session.commit()
    session.expunge_all()
    return task_id, subtask_id


def test_list_for_task_with_images_loads_links(session):
    """with_images eager-loads the SubTaskImageLinks -> ImageInstance chain.

    The chain is walked while the rows are **detached**, which is the only way
    to tell an eager load from a lazy one: an attached row lazy-loads on demand
    and looks identical. Detaching reproduces the production failure -- the
    request session closes before subtask DTO conversion finishes walking
    SubTaskImageLinks -> ImageInstance -> ImageStorages -> StorageBackend per
    row -- so dropping the loader raises DetachedInstanceError here instead of
    silently issuing ~4 queries per subtask.

    Walked to the **end** of that chain, not to its second leg. Asserting only
    ``link.ImageInstance.PublicID`` stopped two legs short of what DTO
    conversion actually walks, so nothing here observed whether the deeper ones
    resolve at all.

    What that covers, precisely, because it is not what it looks like: dropping
    the last two legs from ``_SUBTASK_IMAGE_LOADER`` alone is **not** a
    degradation and this test correctly stays green for it. ``ImageStorages``
    and ``ImageStorage.StorageBackend`` are ``lazy="selectin"`` on the mappers,
    so they load either way -- measured at 14 statements and **zero** lazy
    loads during a full attached walk, with and without those legs. The legs
    are redundant belt-and-braces, and a test made to fail on their removal
    would be pinning a spelling rather than a behaviour.

    What this does pin is the behaviour: the chain is available on a detached
    row, whichever declaration provides it. It goes red when that stops being
    true from either direction -- truncating the loader *and* taking
    ``lazy="selectin"`` off either mapper raises ``DetachedInstanceError`` on
    exactly the leg that lost its loader.
    """
    task_id, _ = _seed_subtask_with_one_image(session)

    rows = SubTaskRepository(session, scope=admin_scope()).list_for_task(
        task_id, limit=10, offset=0, with_images=True
    )
    assert len(rows) == 1
    session.expunge_all()

    assert [link.ImageInstance.PublicID for link in rows[0].SubTaskImageLinks] == [
        "pub-1"
    ]
    assert [
        storage.StorageBackend.Key
        for link in rows[0].SubTaskImageLinks
        for storage in link.ImageInstance.ImageStorages
    ] == ["backend-pub-1"]


def test_get_with_images_loads_link_chain(session):
    """get_with_images returns the subtask with its image links eager-loaded.

    Detached read, and walked to the end of the four-leg chain, for the two
    reasons given on the sibling test above.
    """
    _, subtask_id = _seed_subtask_with_one_image(session)

    loaded = SubTaskRepository(session, scope=admin_scope()).get_with_images(subtask_id)
    assert loaded is not None
    session.expunge_all()

    assert [link.ImageInstance.PublicID for link in loaded.SubTaskImageLinks] == ["pub-1"]
    assert [
        storage.StorageBackend.Key
        for link in loaded.SubTaskImageLinks
        for storage in link.ImageInstance.ImageStorages
    ] == ["backend-pub-1"]


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


def test_claim_if_unassigned_sets_creator(session):
    """Unassigned subtask is claimed by the given creator_id."""
    actor = _creator(session, "claimer")
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.CreatorID)
    st = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    session.commit()

    claimed = SubTaskRepository(session, scope=admin_scope()).claim_if_unassigned(
        st.SubTaskID, actor.CreatorID
    )
    session.commit()

    assert claimed is True
    assert session.get(SubTask, st.SubTaskID).CreatorID == actor.CreatorID


def test_claim_if_unassigned_does_not_steal(session):
    """Already-assigned subtask is left unchanged."""
    owner = _creator(session, "owner")
    other = _creator(session, "other")
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, owner.CreatorID)
    st = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    st.CreatorID = owner.CreatorID
    session.commit()

    claimed = SubTaskRepository(session, scope=admin_scope()).claim_if_unassigned(
        st.SubTaskID, other.CreatorID
    )
    session.commit()

    assert claimed is False
    assert session.get(SubTask, st.SubTaskID).CreatorID == owner.CreatorID


def test_list_for_task_filters_unassigned_and_creator(session):
    """list_for_task honors unassigned=True and creator_id filters."""
    owner = _creator(session, "owner")
    other = _creator(session, "other")
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, owner.CreatorID)
    unassigned = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    owned = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    owned.CreatorID = owner.CreatorID
    other_st = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    other_st.CreatorID = other.CreatorID
    session.commit()

    repo = SubTaskRepository(session, scope=admin_scope())
    only_unassigned = repo.list_for_task(
        task.TaskID, unassigned=True, limit=50, offset=0
    )
    assert [r.SubTaskID for r in only_unassigned] == [unassigned.SubTaskID]

    only_owner = repo.list_for_task(
        task.TaskID,
        creator_id=owner.CreatorID,
        limit=50,
        offset=0,
    )
    assert [r.SubTaskID for r in only_owner] == [owned.SubTaskID]


def test_list_assignees_for_task_returns_distinct_non_null_creators(session):
    """list_assignees_for_task returns distinct creators, ordered by name."""
    zed = _creator(session, "zed")
    amy = _creator(session, "amy")
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, amy.CreatorID)
    unassigned = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    st1 = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    st1.CreatorID = zed.CreatorID
    st2 = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    st2.CreatorID = amy.CreatorID
    st3 = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    st3.CreatorID = amy.CreatorID
    session.commit()

    assignees = SubTaskRepository(session, scope=admin_scope()).list_assignees_for_task(task.TaskID)

    assert [c.CreatorName for c in assignees] == ["amy", "zed"]
