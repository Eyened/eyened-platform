"""Containment at the repository: a whole task, or none of it."""
from __future__ import annotations

from datetime import date

import pytest

from eyened_orm import SubTask, Task, TaskDefinition
from eyened_orm.repositories import SubTaskRepository, TaskRepository
from eyened_orm.task import SubTaskImageLink, SubTaskState, TaskState
from eyened_orm.utils.factories import (
    admin_scope,
    make_device,
    make_image,
    make_patient,
    make_project,
    make_series,
    make_storage_backend,
    make_study,
    scope_for,
)


@pytest.fixture()
def spanning(session):
    """Three tasks: one spanning A and B, one empty, one wholly inside A."""
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    projects, images = {}, {}
    for name in ("A", "B"):
        project = make_project(session, name)
        patient = make_patient(session, project, f"pat-{name}")
        study = make_study(session, patient, date(2024, 1, 1))
        series = make_series(session, study)
        image = make_image(session, series, device, backend, f"img-{name}")
        projects[name] = project.ProjectID
        images[name] = image.ImageInstanceID

    taskdef = TaskDefinition(TaskDefinitionName="def")
    session.add(taskdef)
    session.flush()
    tasks = {}
    for label in ("spanning", "empty", "a_only"):
        task = Task(
            TaskName=label,
            TaskDefinitionID=taskdef.TaskDefinitionID,
            TaskState=TaskState.NotStarted,
        )
        session.add(task)
        session.flush()
        tasks[label] = task.TaskID

    subtasks = {}
    for label, names in (("spanning", ("A", "B")), ("a_only", ("A",))):
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
    session.commit()
    return {
        "projects": projects,
        "images": images,
        "task": tasks["spanning"],
        "empty": tasks["empty"],
        "a_only": tasks["a_only"],
        "subtasks": subtasks,
    }


def test_a_member_of_one_project_does_not_see_a_spanning_task(session, spanning):
    """Absent from every read -- and the A-only task is still there, so the
    predicate is hiding the right row rather than hiding everything."""
    repo = TaskRepository(session, scope=scope_for(spanning["projects"]["A"]))
    assert repo.get_by_id(spanning["task"]) is None
    assert repo.get_with_relations(spanning["task"]) is None
    assert [t.TaskName for t in repo.list_all()] == ["empty", "a_only"]


def test_a_member_of_both_sees_the_task_and_every_subtask(session, spanning):
    scope = scope_for(*spanning["projects"].values())
    tasks = TaskRepository(session, scope=scope)
    subtasks = SubTaskRepository(session, scope=scope)
    assert tasks.get_by_id(spanning["task"]) is not None
    assert subtasks.count_for_task(spanning["task"]) == 2
    assert len(subtasks.list_for_task(spanning["task"], limit=10, offset=0)) == 2
    assert len(subtasks.all_ids_for_task(spanning["task"])) == 2


def test_a_subtask_of_a_hidden_task_is_not_reachable_on_its_own_merits(
    session, spanning
):
    """The A-side subtask sits entirely in A, but its parent task does not."""
    repo = SubTaskRepository(session, scope=scope_for(spanning["projects"]["A"]))
    assert repo.get_by_id(spanning["subtasks"]["spanning-A"]) is None
    assert repo.get_with_images(spanning["subtasks"]["spanning-A"]) is None
    assert repo.count_for_task(spanning["task"]) == 0
    assert repo.all_ids_for_task(spanning["task"]) == []
    assert repo.list_for_task(spanning["task"], limit=10, offset=0) == []
    # ... while the subtask of the A-only task, which IS contained, still reads.
    assert repo.get_by_id(spanning["subtasks"]["a_only-A"]) is not None
    assert len(repo.list_for_task(spanning["a_only"], limit=10, offset=0)) == 1


def test_subtask_counts_report_zero_for_a_hidden_task(session, spanning):
    """Never a partial view: not 'the task with fewer subtasks'."""
    repo = TaskRepository(session, scope=scope_for(spanning["projects"]["A"]))
    counts = repo.subtask_counts([spanning["task"], spanning["a_only"]])
    assert counts[spanning["task"]] == (0, 0)
    assert counts[spanning["a_only"]] == (1, 0)


def test_a_task_with_no_images_is_visible_to_anyone(session, spanning):
    """Vacuity, accepted in v0.3 (Visibility, consequence 4)."""
    repo = TaskRepository(session, scope=scope_for())
    assert repo.get_by_id(spanning["empty"]) is not None
    assert [t.TaskName for t in repo.list_all()] == ["empty"]


def test_an_admin_sees_the_spanning_task(session, spanning):
    assert TaskRepository(session, scope=admin_scope()).get_by_id(spanning["task"])
