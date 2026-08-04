"""The read-only breakdown: where a task's data lives, and who can already see it."""
from eyened_orm import ProjectMember, SubTask, SubTaskImageLink, Task, TaskDefinition
from eyened_orm.project_member import ProjectRole
from eyened_orm.task import TaskState
from eyened_orm.utils.factories import make_creator, make_image_in_project, make_project
from eyened_orm.utils.task_projects import project_breakdown

SENTINEL = "_test_sentinel"


def _task(session, name: str, project_id: int) -> Task:
    td = TaskDefinition(TaskDefinitionName=f"td-{name}")
    session.add(td)
    session.flush()
    task = Task(
        TaskName=name,
        TaskDefinitionID=td.TaskDefinitionID,
        TaskState=TaskState.NotStarted,
        ProjectID=project_id,
    )
    session.add(task)
    session.flush()
    return task


def _link(session, task: Task, image, count: int = 1) -> None:
    for i in range(count):
        st = SubTask(TaskID=task.TaskID)
        session.add(st)
        session.flush()
        session.add(
            SubTaskImageLink(
                SubTaskID=st.SubTaskID,
                ImageInstanceID=image.ImageInstanceID,
                ImageIndex=i,
            )
        )
    session.flush()


def test_project_breakdown_counts_subtasks_and_links_per_project(session):
    """Each project the task's images live in, with how much of the task is there."""
    home = make_project(session, "P-home")
    other = make_project(session, "P-other")
    task = _task(session, "spanning", home.ProjectID)
    _link(session, task, make_image_in_project(session, home, "h-1"), count=2)
    _link(session, task, make_image_in_project(session, other, "o-1"), count=1)

    anna = make_creator(session, "anna")
    session.add(
        ProjectMember(
            CreatorID=anna.CreatorID,
            ProjectID=home.ProjectID,
            Role=ProjectRole.grader,
        )
    )
    session.flush()

    result = project_breakdown(
        session, task.TaskID, sentinel_name=SENTINEL, for_creator_id=anna.CreatorID
    )

    by_id = {u.project_id: u for u in result.usage}
    assert by_id[home.ProjectID].subtasks == 2
    assert by_id[home.ProjectID].links == 2
    assert by_id[other.ProjectID].subtasks == 1
    # Visibility is the union of memberships -- "not the anchor" is not "cannot see".
    assert by_id[home.ProjectID].member is True
    assert by_id[other.ProjectID].member is False
    assert result.parked is False


def test_project_breakdown_flags_a_parked_task(session):
    """`parked` is derived from the caller-supplied sentinel name, not a constant."""
    sentinel = make_project(session, SENTINEL)
    task = _task(session, "parked", sentinel.ProjectID)

    result = project_breakdown(session, task.TaskID, sentinel_name=SENTINEL)

    assert result.parked is True
    assert result.anchor_project_name == SENTINEL
    assert result.usage == []
