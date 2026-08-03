"""The task->project anchor: the column, its cascade, and the derivation path."""
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from eyened_orm import Task, TaskDefinition
from eyened_orm.task import TaskState
from eyened_orm.utils.factories import make_image_in_project, make_project


def _task_def(session, name: str = "td") -> TaskDefinition:
    td = TaskDefinition(TaskDefinitionName=name)
    session.add(td)
    session.flush()
    return td


def test_task_without_a_project_is_refused(session):
    """ProjectID is NOT NULL in the model, so create_all builds it that way too."""
    td = _task_def(session)
    session.add(
        Task(TaskName="orphan", TaskDefinitionID=td.TaskDefinitionID,
             TaskState=TaskState.NotStarted)
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_deleting_a_project_deletes_its_tasks(session):
    """ondelete=CASCADE -- matching Patient.ProjectID and ProjectMember.ProjectID."""
    td = _task_def(session)
    project = make_project(session, "P-cascade")
    session.add(
        Task(TaskName="doomed", TaskDefinitionID=td.TaskDefinitionID,
             TaskState=TaskState.NotStarted, ProjectID=project.ProjectID)
    )
    session.flush()

    session.delete(project)
    session.flush()

    assert session.scalar(select(Task).where(Task.TaskName == "doomed")) is None


def test_create_from_imagesets_derives_the_project_from_its_images(session):
    """The images' project is the anchor; nothing has to be passed in."""
    project = make_project(session, "P-derive")
    img = make_image_in_project(session, project, "d-1")

    task = Task.create_from_imagesets(session, "td", "derived", [[img]])
    session.add(task)
    session.flush()

    assert task.ProjectID == project.ProjectID


def test_create_from_imagesets_refuses_images_spanning_two_projects(session):
    """A task links to exactly one project, so a spanning image set has no answer."""
    a = make_project(session, "P-span-a")
    b = make_project(session, "P-span-b")
    img_a = make_image_in_project(session, a, "s-a")
    img_b = make_image_in_project(session, b, "s-b")

    with pytest.raises(ValueError) as exc:
        Task.create_from_imagesets(session, "td", "spanning", [[img_a], [img_b]])

    # The message must name what was found, or the caller cannot act on it.
    assert str(a.ProjectID) in str(exc.value)
    assert str(b.ProjectID) in str(exc.value)


def test_create_from_imagesets_accepts_an_explicit_project(session):
    """The imageset-less case: no image evidence, so the caller supplies the anchor."""
    project = make_project(session, "P-explicit")

    task = Task.create_from_imagesets(
        session, "td", "empty", [], project_id=project.ProjectID
    )
    session.add(task)
    session.flush()

    assert task.ProjectID == project.ProjectID


def test_create_from_imagesets_refuses_an_empty_image_set_without_a_project(session):
    """The error must name the argument that fixes it, not merely state the problem."""
    with pytest.raises(ValueError) as exc:
        Task.create_from_imagesets(session, "td", "empty", [])

    assert "project_id" in str(exc.value)
