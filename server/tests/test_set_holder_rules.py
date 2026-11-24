"""Who may change a set's status and comments, and which set "next" opens."""
from __future__ import annotations

import pytest

from eyened_orm import SubTask, Task, TaskDefinition, TaskProject
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.task import SubTaskState, TaskState
from eyened_orm.utils.factories import admin_scope, make_creator, make_project, scope_for

from server.services.task_service import can_edit_status_and_comments

ME, OTHER = 1, 2
P, Q = 10, 20


@pytest.mark.parametrize(
    ("scope", "projects", "holder", "expected"),
    [
        pytest.param(scope_for(P, Q, actor_id=ME), {P, Q}, ME, True, id="my set"),
        pytest.param(scope_for(P, Q, actor_id=ME), {P, Q}, None, True, id="unclaimed"),
        pytest.param(
            scope_for(P, Q, actor_id=ME), {P, Q}, OTHER, False, id="another grader's set"
        ),
        pytest.param(
            scope_for(P, Q, role=ProjectRole.project_admin, actor_id=ME),
            {P, Q},
            OTHER,
            True,
            id="project admin in every project",
        ),
        pytest.param(
            scope_for(
                roles={P: ProjectRole.project_admin, Q: ProjectRole.grader}, actor_id=ME
            ),
            {P, Q},
            OTHER,
            False,
            id="project admin in one of two",
        ),
        pytest.param(admin_scope(actor_id=ME), {P, Q}, OTHER, True, id="global admin"),
        pytest.param(
            scope_for(P, Q, role=ProjectRole.read_only, actor_id=ME),
            {P, Q},
            None,
            False,
            id="read-only member, unclaimed",
        ),
        pytest.param(
            scope_for(P, actor_id=ME), set(), None, False, id="task declares no projects"
        ),
    ],
)
def test_who_may_change_status_and_comments(scope, projects, holder, expected):
    assert can_edit_status_and_comments(scope, projects, holder) is expected


@pytest.fixture()
def worked_example(session):
    """One task in project P with six sets, in this order (0-based index):

    0 mine Busy, 1 another grader's NotStarted, 2 unclaimed Ready,
    3 unclaimed NotStarted, 4 mine NotStarted, 5 another grader's Busy.
    A set in another task comes first, so no SubTaskID equals its index + 1.
    """
    me = make_creator(session, "grader-a")
    other = make_creator(session, "grader-b")
    project = make_project(session, "P-holder")
    definition = TaskDefinition(TaskDefinitionName="td-holder")
    session.add(definition)
    session.flush()
    elsewhere, task = (
        Task(
            TaskName=name,
            TaskDefinitionID=definition.TaskDefinitionID,
            TaskState=TaskState.NotStarted,
        )
        for name in ("T-elsewhere", "T-holder")
    )
    session.add_all([elsewhere, task])
    session.flush()
    session.add(TaskProject(TaskID=task.TaskID, ProjectID=project.ProjectID))
    session.add(SubTask(TaskID=elsewhere.TaskID, TaskState=SubTaskState.NotStarted))
    session.flush()
    rows = [
        (me, SubTaskState.Busy),
        (other, SubTaskState.NotStarted),
        (None, SubTaskState.Ready),
        (None, SubTaskState.NotStarted),
        (me, SubTaskState.NotStarted),
        (other, SubTaskState.Busy),
    ]
    for holder, state in rows:
        session.add(
            SubTask(
                TaskID=task.TaskID,
                CreatorID=holder.CreatorID if holder else None,
                TaskState=state,
            )
        )
        session.flush()  # one at a time, so SubTaskIDs follow the list
    return {"task": task.TaskID, "project": project.ProjectID, "me": me}


@pytest.mark.parametrize(
    ("index", "next_open", "can_edit"),
    [
        pytest.param(0, 3, True, id="set 1, mine: next skips a held and a Ready set"),
        pytest.param(1, 3, False, id="set 2, another grader's: locked"),
        pytest.param(3, 4, True, id="set 4, unclaimed: next is my open set"),
        pytest.param(4, None, True, id="set 5, mine: no open set after it"),
    ],
)
def test_the_set_response_carries_the_next_open_set_and_the_lock(
    client_scoped, worked_example, index, next_open, can_edit
):
    client, set_scope = client_scoped
    set_scope(
        scope_for(
            worked_example["project"],
            actor_id=worked_example["me"].CreatorID,
            username="grader-a",
        )
    )

    body = client.get(f"/task/{worked_example['task']}/subtask/{index}").json()

    assert body["next_open_index"] == next_open
    assert body["can_edit_status_and_comments"] is can_edit
