"""A task names the projects it spans, for anyone who can see the task."""
from __future__ import annotations

from eyened_orm import Task, TaskProject
from eyened_orm.authz.scoping import projects_of
from eyened_orm.repositories.task_repository import TaskRepository
from eyened_orm.task import TaskState
from eyened_orm.utils.factories import admin_scope, scope_for


def test_a_member_of_both_sees_both_project_names(client_scoped, spanning):
    """This discloses nothing: a task is only visible to a member of every
    project it spans, so anyone who can see it is already a member of every
    project named. There is no filtering to do on the list itself."""
    client, set_scope = client_scoped
    set_scope(scope_for(*spanning["projects"].values()))
    resp = client.get(f"/task/{spanning['task']}")
    assert resp.status_code == 200
    assert sorted(p["name"] for p in resp.json()["projects"]) == ["A", "B"]


def test_a_task_with_no_images_reports_an_empty_list(client_scoped, spanning):
    """An honest empty list, not an error: the scope sees every project, so
    ``[]`` can only mean the task genuinely has no images."""
    client, set_scope = client_scoped
    set_scope(scope_for(*spanning["projects"].values()))
    resp = client.get(f"/task/{spanning['empty']}")
    assert resp.status_code == 200
    assert resp.json()["projects"] == []


def test_the_task_list_carries_the_field_too(client_scoped, spanning):
    """The collection route reports the same spanned projects the detail route does."""
    client, set_scope = client_scoped
    set_scope(scope_for(*spanning["projects"].values()))
    rows = client.get("/task?include_projects=true").json()
    by_id = {t["id"]: t for t in rows}
    assert sorted(p["name"] for p in by_id[spanning["task"]]["projects"]) == ["A", "B"]


def test_it_agrees_with_the_enforcement_path(session, spanning):
    """The batched query and projects_of must not answer differently:
    grant-for-task and this endpoint are the two sides of one promise."""
    repo = TaskRepository(session, scope=admin_scope())
    ids = [spanning[k] for k in ("task", "empty", "a_only", "b_only")]
    batched = repo.projects_for_tasks(ids)
    for tid in ids:
        assert {pid for pid, _ in batched[tid]} == projects_of(session, Task, tid)


def test_a_task_touching_an_invisible_project_resolves_to_nothing(session, spanning):
    """The scope predicate filters: a project the caller cannot see is absent,
    which is what makes a hidden task report ``[]`` rather than a partial view.

    Repository-level by necessity -- an A-only member 404s on the spanning task
    before the field is ever read, so no route test can reach this.
    """
    repo = TaskRepository(session, scope=scope_for(spanning["projects"]["A"]))
    got = repo.projects_for_tasks([spanning["task"], spanning["a_only"]])
    # Filtering happens: the A-visible half of the spanning task is not a
    # partial view, it is nothing at all.
    assert got[spanning["task"]] == []
    # ...and it does not over-filter: what the scope *can* see still resolves.
    assert got[spanning["a_only"]] == [(spanning["projects"]["A"], "A")]


def test_a_declared_project_the_scope_lacks_resolves_to_nothing(session, spanning):
    """The same predicate on ``declared_projects``, on the shape it exists for.

    That method answers the create route, where the task has a declaration and
    no image links yet. While the read predicate walked the image links, such a
    task was visible to every scope, so its ``apply_scope`` call could not bite
    on its own subject -- structural coverage only. Reading ``TaskProject``
    makes it bite.

    Repository-level for the same reason as the test above, and the held-scope
    half is the control: without it, a method that returned ``[]`` for
    everything would pass.
    """
    task = Task(
        TaskName="declared, no images",
        TaskDefinitionID=spanning["task_definition"],
        TaskState=TaskState.NotStarted,
    )
    session.add(task)
    session.flush()
    task_id = task.TaskID
    session.add(TaskProject(TaskID=task_id, ProjectID=spanning["projects"]["B"]))
    session.commit()

    held = TaskRepository(session, scope=scope_for(spanning["projects"]["B"]))
    assert held.declared_projects(task_id) == [(spanning["projects"]["B"], "B")]

    lacking = TaskRepository(session, scope=scope_for(spanning["projects"]["A"]))
    assert lacking.declared_projects(task_id) == []
