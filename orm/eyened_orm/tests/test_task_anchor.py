"""Re-pointing a task's anchor -- one UPDATE, validated against its images."""
import pytest

from eyened_orm import SubTask, SubTaskImageLink, Task, TaskDefinition
from eyened_orm.task import TaskState
from eyened_orm.utils.factories import make_image_in_project, make_project
from eyened_orm.utils.task_projects import anchor_task


def _task_with_images_in(session, project, name: str) -> Task:
    td = TaskDefinition(TaskDefinitionName=f"td-{name}")
    session.add(td)
    session.flush()
    task = Task(
        TaskName=name,
        TaskDefinitionID=td.TaskDefinitionID,
        TaskState=TaskState.NotStarted,
        ProjectID=project.ProjectID,
    )
    session.add(task)
    session.flush()
    image = make_image_in_project(session, project, f"img-{name}")
    st = SubTask(TaskID=task.TaskID)
    session.add(st)
    session.flush()
    session.add(
        SubTaskImageLink(
            SubTaskID=st.SubTaskID,
            ImageInstanceID=image.ImageInstanceID,
            ImageIndex=0,
        )
    )
    session.flush()
    return task


def test_anchor_task_re_points_to_a_project_the_images_use(session):
    """A move returns the previous anchor and writes exactly one column."""
    home = make_project(session, "P-a")
    away = make_project(session, "P-b")
    task = _task_with_images_in(session, home, "movable")
    # Give it evidence in `away` too, so `away` is a legitimate anchor.
    image = make_image_in_project(session, away, "extra")
    st = SubTask(TaskID=task.TaskID)
    session.add(st)
    session.flush()
    session.add(
        SubTaskImageLink(
            SubTaskID=st.SubTaskID,
            ImageInstanceID=image.ImageInstanceID,
            ImageIndex=0,
        )
    )
    session.flush()

    previous = anchor_task(session, task.TaskID, away.ProjectID)

    assert previous == home.ProjectID
    assert session.get(Task, task.TaskID).ProjectID == away.ProjectID


def test_anchor_task_refuses_a_project_the_images_do_not_use(session):
    """Anchoring moves no images: a fresh project would make every subtask render
    as nothing but placeholders."""
    home = make_project(session, "P-home")
    unrelated = make_project(session, "P-unrelated")
    task = _task_with_images_in(session, home, "fixed")

    with pytest.raises(ValueError) as exc:
        anchor_task(session, task.TaskID, unrelated.ProjectID)

    # Not `str(home.ProjectID) in str(exc.value)`: with home=1 and task_id=1 the
    # message contains "1" regardless of which project is named, so that
    # assertion can't distinguish the right answer from the task id. Assert on
    # the rendered list instead.
    assert f"project(s) [{home.ProjectID}]" in str(exc.value)
    assert session.get(Task, task.TaskID).ProjectID == home.ProjectID
