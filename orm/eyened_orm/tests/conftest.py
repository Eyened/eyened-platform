"""Pytest fixtures for ORM unit tests."""
from __future__ import annotations

from datetime import date

import pytest

from eyened_orm import SubTask, Task, TaskDefinition, TaskProject
from eyened_orm.task import SubTaskImageLink, SubTaskState, TaskState
from eyened_orm.utils.factories import (
    make_device,
    make_image,
    make_patient,
    make_project,
    make_series,
    make_storage_backend,
    make_study,
)
from eyened_orm.utils.sqlite_testdb import SessionLocal, engine, session

__all__ = ["SessionLocal", "engine", "session"]


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

    # Before the subtask/link loop, not after: that loop flushes *inside* each
    # iteration, so every link but the last is already in the database by the
    # time it ends, and the containment foreign key rejects a link inserted
    # before the declaration it needs. `empty` declares nothing on purpose --
    # it is the vacuity case the scoping tests turn on, and holds no links.
    for label, names in (("spanning", ("A", "B")), ("a_only", ("A",))):
        for name in names:
            session.add(TaskProject(TaskID=tasks[label], ProjectID=projects[name]))
    session.flush()

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
